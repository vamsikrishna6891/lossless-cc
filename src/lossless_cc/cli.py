"""CLI entry point for lossless-cc."""

import json
import sys

import click

from . import __version__
from .db import (
    init_db,
    search_messages,
    get_sessions,
    get_stats,
)
from .ingest import ingest_session, ingest_from_hook_stdin


@click.group()
@click.version_option(version=__version__)
def cli():
    """Lossless context management for Claude Code."""
    pass


@cli.command()
@click.argument("query")
@click.option("--project", "-p", help="Filter by project path")
@click.option("--limit", "-l", default=20, help="Max results")
@click.option("--json-output", "-j", is_flag=True, help="Output as JSON")
def grep(query, project, limit, json_output):
    """Full-text search across all conversation history."""
    conn = init_db()
    results = search_messages(conn, query, project, limit)
    conn.close()

    if not results:
        click.echo("No results found.")
        return

    if json_output:
        click.echo(json.dumps(results, indent=2, default=str))
        return

    for r in results:
        session_short = r["session_id"][:8]
        content_preview = r["content"][:200].replace("\n", " ")
        click.echo(f"[{session_short}] {r['role'] or r['type']} ({r['timestamp']})")
        click.echo(f"  {content_preview}")
        click.echo()


@cli.command()
@click.argument("query")
@click.option("--project", "-p", help="Filter by project path")
@click.option("--limit", "-l", default=5, help="Max results")
def recall(query, project, limit):
    """Search summaries first, then raw messages. Optimized for agent use."""
    conn = init_db()

    # Search summaries first
    summaries = conn.execute(
        """SELECT * FROM summaries
           WHERE summary_text LIKE ?
           ORDER BY created_at DESC LIMIT ?""",
        (f"%{query}%", limit),
    ).fetchall()

    if summaries:
        click.echo(f"Found {len(summaries)} relevant summaries:\n")
        for s in summaries:
            click.echo(f"[Session {s['session_id'][:8]}] (Level {s['summary_level']})")
            click.echo(s["summary_text"])
            click.echo()
    else:
        # Fall back to raw message search
        results = search_messages(conn, query, project, limit)
        if results:
            click.echo(f"Found {len(results)} relevant messages:\n")
            for r in results:
                session_short = r["session_id"][:8]
                content = r["content"][:500].replace("\n", " ")
                click.echo(f"[{session_short}] {r['role'] or r['type']} ({r['timestamp']})")
                click.echo(f"  {content}")
                click.echo()
        else:
            click.echo("No results found in summaries or messages.")

    conn.close()


@cli.command()
@click.option("--project", "-p", help="Filter by project path")
@click.option("--limit", "-l", default=10, help="Max sessions to show")
def sessions(project, limit):
    """List recorded sessions."""
    conn = init_db()
    rows = get_sessions(conn, project, limit)
    conn.close()

    if not rows:
        click.echo("No sessions recorded yet.")
        return

    click.echo(f"{'Session ID':<40} {'Messages':>8} {'First':>22} {'Last':>22}")
    click.echo("-" * 95)
    for r in rows:
        click.echo(
            f"{r['session_id']:<40} {r['message_count']:>8} "
            f"{r['first_message']!s:>22} {r['last_message']!s:>22}"
        )


@cli.command()
def stats():
    """Show database statistics."""
    conn = init_db()
    s = get_stats(conn)
    conn.close()

    click.echo(f"Sessions:  {s['total_sessions']}")
    click.echo(f"Messages:  {s['total_messages']}")
    click.echo(f"Projects:  {s['total_projects']}")
    click.echo(f"Summaries: {s['total_summaries']}")
    click.echo()
    click.echo("By type:")
    for t, c in sorted(s["by_type"].items()):
        click.echo(f"  {t}: {c}")


@cli.command()
@click.argument("jsonl_path")
def ingest(jsonl_path):
    """Manually ingest a session JSONL file."""
    conn = init_db()
    count = ingest_session(conn, jsonl_path)
    conn.close()
    click.echo(f"Ingested {count} new messages.")


@cli.command("ingest-all")
@click.option("--claude-dir", default=None, help="Claude projects directory")
def ingest_all(claude_dir):
    """Ingest all session JSONL files from Claude's project directories."""
    from pathlib import Path

    base = Path(claude_dir) if claude_dir else Path.home() / ".claude" / "projects"
    if not base.exists():
        click.echo(f"Directory not found: {base}")
        return

    conn = init_db()
    total = 0
    files = 0

    for jsonl_file in sorted(base.rglob("*.jsonl")):
        # Skip subagent files
        if "subagent" in str(jsonl_file):
            continue
        count = ingest_session(conn, str(jsonl_file))
        if count > 0:
            files += 1
            total += count

    conn.close()

    s = get_stats(init_db())
    click.echo(f"Ingested {total} new messages from {files} files.")
    click.echo(f"Total: {s['total_messages']} messages across {s['total_sessions']} sessions.")


@cli.command("hook-stop")
def hook_stop():
    """Stop hook handler. Reads stdin JSON, ingests session JSONL."""
    data = ingest_from_hook_stdin()
    transcript_path = data.get("transcript_path")
    if not transcript_path:
        return

    conn = init_db()
    ingest_session(conn, transcript_path)
    conn.close()


@cli.command("hook-compact")
def hook_compact():
    """PreCompact hook handler. Summarizes context before compaction."""
    data = ingest_from_hook_stdin()
    transcript_path = data.get("transcript_path")
    session_id = data.get("session_id", "")
    if not transcript_path:
        return

    conn = init_db()

    # First, ingest any new messages
    count = ingest_session(conn, transcript_path)

    # Get recent messages for summarization
    recent = conn.execute(
        """SELECT * FROM messages
           WHERE session_id = ?
           ORDER BY timestamp DESC LIMIT 50""",
        (session_id,),
    ).fetchall()

    if recent:
        from .summarizer import summarize_messages
        from .ingest import extract_project_path

        messages = [dict(r) for r in reversed(recent)]
        summary_text = summarize_messages(messages)

        if summary_text:
            message_ids = json.dumps([m["id"] for m in messages])
            project_path = extract_project_path(transcript_path)
            conn.execute(
                """INSERT INTO summaries
                   (session_id, project_path, summary_text, source_message_ids)
                   VALUES (?, ?, ?, ?)""",
                (session_id, project_path, summary_text, message_ids),
            )
            conn.commit()

            # Output summary for Claude to see as injected context
            click.echo(
                f"[lossless-cc] Saved {count} messages and generated summary before compaction.\n"
                f"Summary of compacted context:\n{summary_text}\n\n"
                f"Use `lossless-cc recall <query>` to search past context."
            )
    elif count > 0:
        click.echo(
            f"[lossless-cc] Saved {count} messages before compaction. "
            f"Use `lossless-cc grep <query>` to recall past context."
        )

    conn.close()


@cli.command("hook-start")
def hook_start():
    """SessionStart hook handler. Injects prior session context."""
    data = ingest_from_hook_stdin()
    transcript_path = data.get("transcript_path")
    if not transcript_path:
        return

    conn = init_db()
    from .ingest import extract_project_path

    project = extract_project_path(transcript_path)
    total = get_stats(conn)

    if total["total_messages"] == 0:
        conn.close()
        return

    # Check for recent summaries from this project
    summaries = conn.execute(
        """SELECT summary_text, created_at FROM summaries
           WHERE project_path = ?
           ORDER BY created_at DESC LIMIT 3""",
        (project,),
    ).fetchall()

    parts = [
        f"[lossless-cc] {total['total_messages']} messages across "
        f"{total['total_sessions']} sessions in database."
    ]

    if summaries:
        parts.append("Recent context summaries:")
        for s in summaries:
            parts.append(f"\n--- Summary ({s['created_at']}) ---")
            parts.append(s["summary_text"])

    parts.append("\nUse `lossless-cc recall <query>` or `lossless-cc grep <query>` to search history.")

    click.echo("\n".join(parts))
    conn.close()
