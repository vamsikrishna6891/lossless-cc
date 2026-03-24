"""Tests for the ingest module."""

from pathlib import Path

import pytest

from lossless_cc.db import init_db, get_stats, search_messages
from lossless_cc.ingest import ingest_session, extract_project_path, parse_message


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample.jsonl"


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    yield conn
    conn.close()


def test_extract_project_path():
    path = "/Users/test/.claude/projects/-Users-test-CascadeProjects/abc-123.jsonl"
    assert extract_project_path(path) == "-Users-test-CascadeProjects"


def test_parse_user_message():
    data = {
        "type": "user",
        "sessionId": "s1",
        "uuid": "u1",
        "timestamp": "2026-01-01T00:00:00Z",
        "message": {
            "role": "user",
            "content": [{"type": "text", "text": "Hello world"}],
        },
    }
    msg = parse_message(data, "test-project")
    assert msg is not None
    assert msg["content"] == "Hello world"
    assert msg["role"] == "user"
    assert msg["type"] == "user"


def test_parse_assistant_with_tool_use():
    data = {
        "type": "assistant",
        "sessionId": "s1",
        "uuid": "u2",
        "timestamp": "2026-01-01T00:00:01Z",
        "message": {
            "model": "claude-opus-4-6",
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {}},
                {"type": "text", "text": "Running command."},
            ],
            "usage": {"input_tokens": 100, "output_tokens": 20},
        },
    }
    msg = parse_message(data, "test-project")
    assert msg is not None
    assert msg["is_tool_use"] == 1
    assert msg["tool_name"] == "Bash"
    assert "Running command." in msg["content"]


def test_parse_progress_returns_none():
    data = {"type": "progress", "sessionId": "s1", "uuid": "p1"}
    assert parse_message(data, "test") is None


def test_ingest_session_from_fixture(db):
    count = ingest_session(db, str(FIXTURE_PATH))
    assert count == 4  # 2 user + 2 assistant (both have text content)

    stats = get_stats(db)
    assert stats["total_messages"] == 4
    assert stats["total_sessions"] == 1


def test_ingest_incremental(db):
    count1 = ingest_session(db, str(FIXTURE_PATH))
    assert count1 == 4

    # Second ingest should add nothing (same file, no new data)
    count2 = ingest_session(db, str(FIXTURE_PATH))
    assert count2 == 0

    stats = get_stats(db)
    assert stats["total_messages"] == 4


def test_ingest_nonexistent_file(db):
    count = ingest_session(db, "/nonexistent/file.jsonl")
    assert count == 0


def test_search_after_ingest(db):
    ingest_session(db, str(FIXTURE_PATH))
    results = search_messages(db, "Supabase")
    assert len(results) >= 1
    assert any("Supabase" in r["content"] for r in results)


def test_search_decision(db):
    ingest_session(db, str(FIXTURE_PATH))
    results = search_messages(db, 'row-level security')
    assert len(results) == 1
    assert "multi-tenant" in results[0]["content"]
