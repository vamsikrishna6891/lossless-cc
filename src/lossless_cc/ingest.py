"""Ingest JSONL session files into SQLite. Used by Stop hook."""

import json
from pathlib import Path

from .db import get_ingest_state, insert_message, update_ingest_state


def extract_project_path(jsonl_path: str) -> str:
    """Extract project path from JSONL file path.

    JSONL files are at: ~/.claude/projects/<escaped-path>/<session-uuid>.jsonl
    The escaped path uses dashes instead of slashes.
    """
    p = Path(jsonl_path)
    return p.parent.name


def parse_message(line_data: dict, project_path: str) -> dict | None:
    """Parse a JSONL line into a message dict for storage."""
    msg_type = line_data.get("type")

    if msg_type not in ("user", "assistant"):
        return None

    session_id = line_data.get("sessionId", "")
    uuid = line_data.get("uuid", "")
    if not uuid:
        return None

    message = line_data.get("message", {})
    role = message.get("role")
    content_blocks = message.get("content", [])

    content_text = ""
    is_tool_use = False
    tool_name = None

    for block in content_blocks:
        if isinstance(block, str):
            content_text += block
            continue
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            content_text += block.get("text", "")
        elif block.get("type") == "tool_use":
            is_tool_use = True
            tool_name = block.get("name")
            content_text += f"[tool_use: {tool_name}] "
        elif block.get("type") == "tool_result":
            result_content = block.get("content", "")
            if isinstance(result_content, list):
                for sub in result_content:
                    if isinstance(sub, dict):
                        content_text += sub.get("text", "")
                    elif isinstance(sub, str):
                        content_text += sub
            elif isinstance(result_content, str):
                content_text += result_content

    if not content_text.strip():
        return None

    usage = message.get("usage", {})

    return {
        "session_id": session_id,
        "project_path": project_path,
        "uuid": uuid,
        "parent_uuid": line_data.get("parentUuid"),
        "type": msg_type,
        "role": role,
        "content": content_text,
        "model": message.get("model"),
        "timestamp": line_data.get("timestamp", ""),
        "token_input": usage.get("input_tokens"),
        "token_output": usage.get("output_tokens"),
        "is_tool_use": 1 if is_tool_use else 0,
        "tool_name": tool_name,
    }


def ingest_session(conn, jsonl_path: str) -> int:
    """Ingest new messages from a session JSONL file. Returns count of new messages."""
    path = Path(jsonl_path)
    if not path.exists():
        return 0

    project_path = extract_project_path(jsonl_path)

    first_line = None
    with open(path, "r") as f:
        first_line = f.readline()
    if not first_line:
        return 0

    first_data = json.loads(first_line)
    session_id = first_data.get("sessionId", path.stem)

    last_offset = get_ingest_state(conn, session_id)
    file_size = path.stat().st_size

    if last_offset >= file_size:
        return 0

    count = 0
    with open(path, "r") as f:
        f.seek(last_offset)
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg = parse_message(data, project_path)
            if msg:
                if not msg["session_id"]:
                    msg["session_id"] = session_id
                insert_message(conn, msg)
                count += 1

    conn.commit()
    update_ingest_state(conn, session_id, project_path, file_size)
    return count


def ingest_from_hook_stdin() -> dict:
    """Read hook stdin JSON and return parsed data."""
    import sys

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        data = {}
    return data
