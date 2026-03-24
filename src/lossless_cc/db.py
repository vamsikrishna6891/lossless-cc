"""SQLite database operations for lossless-cc."""

import sqlite3
from pathlib import Path

DB_DIR = Path.home() / ".lossless-cc"
DB_PATH = DB_DIR / "lossless.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    project_path TEXT NOT NULL,
    uuid TEXT UNIQUE NOT NULL,
    parent_uuid TEXT,
    type TEXT NOT NULL,
    role TEXT,
    content TEXT NOT NULL,
    model TEXT,
    timestamp TEXT NOT NULL,
    token_input INTEGER,
    token_output INTEGER,
    is_tool_use INTEGER DEFAULT 0,
    tool_name TEXT,
    ingested_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    project_path TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    source_message_ids TEXT NOT NULL,
    parent_summary_id INTEGER,
    summary_level INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (parent_summary_id) REFERENCES summaries(id)
);

CREATE TABLE IF NOT EXISTS ingest_state (
    session_id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    last_byte_offset INTEGER DEFAULT 0,
    last_ingested_at TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content=messages,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_project ON messages(project_path);
CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_summaries_session ON summaries(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_project_timestamp ON messages(project_path, timestamp);
CREATE INDEX IF NOT EXISTS idx_summaries_project_created ON summaries(project_path, created_at);
"""


def get_db(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path | None = None) -> sqlite3.Connection:
    conn = get_db(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def get_ingest_state(conn: sqlite3.Connection, session_id: str) -> int:
    row = conn.execute(
        "SELECT last_byte_offset FROM ingest_state WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return row["last_byte_offset"] if row else 0


def update_ingest_state(
    conn: sqlite3.Connection, session_id: str, project_path: str, byte_offset: int
) -> None:
    conn.execute(
        """INSERT INTO ingest_state (session_id, project_path, last_byte_offset, last_ingested_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT(session_id) DO UPDATE SET
               last_byte_offset = excluded.last_byte_offset,
               last_ingested_at = excluded.last_ingested_at""",
        (session_id, project_path, byte_offset),
    )
    conn.commit()


def insert_message(conn: sqlite3.Connection, msg: dict) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO messages
           (session_id, project_path, uuid, parent_uuid, type, role, content,
            model, timestamp, token_input, token_output, is_tool_use, tool_name)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            msg["session_id"],
            msg["project_path"],
            msg["uuid"],
            msg.get("parent_uuid"),
            msg["type"],
            msg.get("role"),
            msg["content"],
            msg.get("model"),
            msg["timestamp"],
            msg.get("token_input"),
            msg.get("token_output"),
            msg.get("is_tool_use", 0),
            msg.get("tool_name"),
        ),
    )


def _sanitize_fts5_query(query: str) -> str:
    """Sanitize a user query for FTS5 MATCH.

    Wraps each token in double quotes so special characters
    (parentheses, +, ', etc.) are treated as literals, not FTS5 operators.
    Returns empty string if there are no searchable tokens.
    """
    query = query.strip()
    if not query:
        return ""
    tokens = query.split()
    quoted = ['"' + tok.replace('"', '""') + '"' for tok in tokens]
    return " ".join(quoted)


def search_messages(
    conn: sqlite3.Connection,
    query: str,
    project_path: str | None = None,
    limit: int = 20,
) -> list[dict]:
    safe_query = _sanitize_fts5_query(query)
    if not safe_query:
        return []

    if project_path:
        rows = conn.execute(
            """SELECT m.* FROM messages m
               JOIN messages_fts f ON m.id = f.rowid
               WHERE messages_fts MATCH ? AND m.project_path = ?
               ORDER BY m.timestamp DESC LIMIT ?""",
            (safe_query, project_path, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT m.* FROM messages m
               JOIN messages_fts f ON m.id = f.rowid
               WHERE messages_fts MATCH ?
               ORDER BY m.timestamp DESC LIMIT ?""",
            (safe_query, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_sessions(
    conn: sqlite3.Connection,
    project_path: str | None = None,
    limit: int = 10,
) -> list[dict]:
    if project_path:
        rows = conn.execute(
            """SELECT session_id, project_path,
                      COUNT(*) as message_count,
                      MIN(timestamp) as first_message,
                      MAX(timestamp) as last_message
               FROM messages
               WHERE project_path = ?
               GROUP BY session_id
               ORDER BY last_message DESC LIMIT ?""",
            (project_path, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT session_id, project_path,
                      COUNT(*) as message_count,
                      MIN(timestamp) as first_message,
                      MAX(timestamp) as last_message
               FROM messages
               GROUP BY session_id
               ORDER BY last_message DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_stats(conn: sqlite3.Connection) -> dict:
    total_messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    total_sessions = conn.execute(
        "SELECT COUNT(DISTINCT session_id) FROM messages"
    ).fetchone()[0]
    total_projects = conn.execute(
        "SELECT COUNT(DISTINCT project_path) FROM messages"
    ).fetchone()[0]
    total_summaries = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
    by_type = dict(
        conn.execute(
            "SELECT type, COUNT(*) FROM messages GROUP BY type"
        ).fetchall()
    )
    return {
        "total_messages": total_messages,
        "total_sessions": total_sessions,
        "total_projects": total_projects,
        "total_summaries": total_summaries,
        "by_type": by_type,
    }
