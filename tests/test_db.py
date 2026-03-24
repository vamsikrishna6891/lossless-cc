"""Tests for the database layer."""

import sqlite3
from pathlib import Path

import pytest

from lossless_cc.db import (
    init_db,
    insert_message,
    get_ingest_state,
    update_ingest_state,
    search_messages,
    get_sessions,
    get_stats,
)


@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = init_db(db_path)
    yield conn
    conn.close()


@pytest.fixture
def sample_message():
    return {
        "session_id": "test-session-001",
        "project_path": "-Users-test-project",
        "uuid": "msg-001",
        "parent_uuid": None,
        "type": "user",
        "role": "user",
        "content": "How do I set up Supabase authentication?",
        "model": None,
        "timestamp": "2026-03-24T10:00:00Z",
        "token_input": None,
        "token_output": None,
        "is_tool_use": 0,
        "tool_name": None,
    }


def test_init_db_creates_tables(db):
    tables = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = {r["name"] for r in tables}
    assert "messages" in table_names
    assert "summaries" in table_names
    assert "ingest_state" in table_names
    assert "messages_fts" in table_names


def test_insert_and_search_message(db, sample_message):
    insert_message(db, sample_message)
    db.commit()

    results = search_messages(db, "Supabase")
    assert len(results) == 1
    assert "Supabase" in results[0]["content"]


def test_insert_duplicate_uuid_ignored(db, sample_message):
    insert_message(db, sample_message)
    insert_message(db, sample_message)
    db.commit()

    count = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert count == 1


def test_search_by_project(db, sample_message):
    insert_message(db, sample_message)

    other = sample_message.copy()
    other["uuid"] = "msg-002"
    other["project_path"] = "-Users-other-project"
    other["content"] = "Supabase in another project"
    insert_message(db, other)
    db.commit()

    results = search_messages(db, "Supabase", project_path="-Users-test-project")
    assert len(results) == 1
    assert results[0]["project_path"] == "-Users-test-project"


def test_ingest_state_tracking(db):
    assert get_ingest_state(db, "session-1") == 0

    update_ingest_state(db, "session-1", "-Users-test", 1024)
    assert get_ingest_state(db, "session-1") == 1024

    update_ingest_state(db, "session-1", "-Users-test", 2048)
    assert get_ingest_state(db, "session-1") == 2048


def test_get_sessions(db, sample_message):
    insert_message(db, sample_message)

    msg2 = sample_message.copy()
    msg2["uuid"] = "msg-002"
    msg2["session_id"] = "test-session-002"
    msg2["content"] = "Another session message"
    insert_message(db, msg2)
    db.commit()

    sessions = get_sessions(db)
    assert len(sessions) == 2


def test_get_stats(db, sample_message):
    insert_message(db, sample_message)
    db.commit()

    s = get_stats(db)
    assert s["total_messages"] == 1
    assert s["total_sessions"] == 1
    assert s["total_projects"] == 1
    assert s["total_summaries"] == 0
    assert s["by_type"]["user"] == 1
