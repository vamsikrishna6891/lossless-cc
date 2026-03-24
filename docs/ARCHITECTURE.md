# Lossless CC - Architecture

## System Overview

```
Claude Code Runtime
    |
    ├── Stop hook ──────────────> lossless-cc ingest
    |                                 |
    ├── PreCompact hook ────────> lossless-cc compact
    |                                 |
    ├── SessionStart hook ──────> lossless-cc inject
    |                                 |
    └── Agent (via Bash) ───────> lossless-cc recall/grep
                                      |
                                      v
                                 SQLite DB
                            (~/.lossless-cc/lossless.db)
```

## Components

### 1. Ingest (Stop Hook)

Fires after every Claude response. Reads the session JSONL file path from stdin (`transcript_path`), diffs against what's already in SQLite, appends new messages.

**Performance target:** <200ms. Only reads tail of JSONL (tracks last ingested line number per session).

### 2. Compact (PreCompact Hook)

Fires before Claude Code compresses context. This is the critical hook.

Steps:
1. Read all messages that are about to be compacted (available via stdin)
2. Generate a summary using a fast, cheap LLM call (Claude Haiku or local Ollama)
3. Store summary in `summaries` table with links to source message IDs
4. Return summary text on stdout (Claude Code injects this as context)

**Performance target:** <3s (includes LLM call for summarization)

### 3. Inject (SessionStart Hook)

Fires at session start. Checks if this project has prior sessions in SQLite. If so:
1. Loads the most recent session's final summary
2. Loads any cross-session decisions/patterns
3. Outputs as context on stdout

### 4. CLI Tools (Agent-callable)

```bash
# Full-text search across all sessions
lossless-cc grep "supabase migration" --project CascadeProjects --limit 10

# Semantic recall (searches summaries first, then raw messages)
lossless-cc recall "what authentication approach did we choose"

# Show session history
lossless-cc sessions --project CascadeProjects --last 5

# Show compaction events
lossless-cc compactions --session <uuid>

# Stats
lossless-cc stats
```

## Database Schema

```sql
-- Every message from every session
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    project_path TEXT NOT NULL,
    uuid TEXT UNIQUE NOT NULL,        -- message UUID from JSONL
    parent_uuid TEXT,
    type TEXT NOT NULL,                -- user, assistant, progress, queue-operation
    role TEXT,                         -- user, assistant
    content TEXT NOT NULL,             -- full message content (JSON)
    model TEXT,                        -- claude-opus-4-6, etc.
    timestamp TEXT NOT NULL,
    token_input INTEGER,
    token_output INTEGER,
    is_tool_use BOOLEAN DEFAULT FALSE,
    tool_name TEXT,
    ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Summaries generated at compaction
CREATE TABLE summaries (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    project_path TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    source_message_ids TEXT NOT NULL,  -- JSON array of message IDs
    parent_summary_id INTEGER,        -- for DAG hierarchy (P1)
    level INTEGER DEFAULT 0,          -- 0 = leaf summary, 1+ = condensed
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_summary_id) REFERENCES summaries(id)
);

-- Track ingestion state per session
CREATE TABLE ingest_state (
    session_id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    last_line_number INTEGER DEFAULT 0,
    last_ingested_at TEXT
);

-- Full-text search index
CREATE VIRTUAL TABLE messages_fts USING fts5(
    content,
    content=messages,
    content_rowid=id
);
```

## File Structure

```
lossless-cc/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── MEMORY.md
│   └── PLAN.md
├── src/
│   └── lossless_cc/
│       ├── __init__.py
│       ├── cli.py          -- Click CLI entry point
│       ├── db.py           -- SQLite operations
│       ├── ingest.py       -- Stop hook: parse JSONL, store messages
│       ├── compact.py      -- PreCompact hook: summarize, store
│       ├── inject.py       -- SessionStart hook: load context
│       ├── search.py       -- grep + recall implementations
│       └── summarizer.py   -- LLM summarization (Haiku / Ollama)
└── tests/
    ├── test_ingest.py
    ├── test_compact.py
    ├── test_search.py
    └── fixtures/
        └── sample.jsonl
```

## Key Design Decisions

1. **SQLite, not Postgres**: Zero setup, portable, fast enough for local use
2. **FTS5 for search**: Built into SQLite, no external search engine needed
3. **Incremental ingest**: Track last line number per session, only read new lines
4. **Cheap summarization**: Use Haiku or Ollama for summaries, not Opus (cost)
5. **Privacy-first**: All data stays local, no cloud sync
6. **Hook-native**: Uses Claude Code's official hook system, no monkey-patching
