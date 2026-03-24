# lossless-cc

Lossless context management for Claude Code. Never lose conversation history again.

## The Problem

Claude Code compacts (drops) older messages when the context window fills up. Decisions you made, bugs you debugged, architecture you discussed... gone. You end up re-explaining context that was already established.

## The Solution

lossless-cc hooks into Claude Code's lifecycle and:

1. **Saves every message** to a local SQLite database (via `Stop` hook)
2. **Summarizes context before compaction** using Claude Haiku (via `PreCompact` hook)
3. **Injects prior session context** at startup (via `SessionStart` hook)
4. **Lets agents search history** via CLI commands callable from Bash

```
60,289 messages across 109 sessions? Fully searchable in <100ms.
```

## Install

```bash
# Via uv (recommended)
uv tool install lossless-cc

# Via pip
pip install lossless-cc
```

## Quick Start

```bash
# 1. Ingest your existing Claude Code history
lossless-cc ingest-all

# 2. Search across all sessions
lossless-cc grep "authentication middleware"

# 3. Recall with summary-first search
lossless-cc recall "what database did we choose"

# 4. List sessions
lossless-cc sessions

# 5. Stats
lossless-cc stats
```

## Set Up Hooks (Automatic Mode)

Add to your `~/.claude/settings.json` to make it fully automatic:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "lossless-cc hook-stop",
            "timeout": 5
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "lossless-cc hook-compact",
            "timeout": 10
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "lossless-cc hook-start",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

Once configured:
- **Stop hook**: After every Claude response, new messages are saved to SQLite
- **PreCompact hook**: Before context compression, a summary is generated and stored
- **SessionStart hook**: When a new session starts, prior context is injected

## How It Works

```
Claude Code Runtime
    |
    +-- Stop hook -----------> lossless-cc ingest (save messages)
    |
    +-- PreCompact hook -----> lossless-cc compact (summarize before drop)
    |
    +-- SessionStart hook ---> lossless-cc inject (load prior context)
    |
    +-- Agent (via Bash) ----> lossless-cc recall/grep (search history)
                                    |
                                    v
                               SQLite DB
                          (~/.lossless-cc/lossless.db)
```

### What Gets Stored

- Every `user` and `assistant` message with full content
- Session ID, project path, timestamps
- Token usage (input/output)
- Tool use tracking (which tools were called)
- Hierarchical summaries generated at compaction points

### Search

Two search modes:

- **`grep`**: Full-text search (FTS5) across raw messages. Fast, literal matching.
- **`recall`**: Searches summaries first, falls back to raw messages. Better for "what did we decide about X" queries.

## CLI Reference

```
lossless-cc grep <query>        Full-text search across all history
lossless-cc recall <query>      Summary-first search (agent-friendly)
lossless-cc sessions            List all recorded sessions
lossless-cc stats               Show database statistics
lossless-cc ingest <file>       Manually ingest a session JSONL file
lossless-cc ingest-all          Ingest all sessions from ~/.claude/projects/
lossless-cc hook-stop           Stop hook handler (reads stdin)
lossless-cc hook-compact        PreCompact hook handler (reads stdin)
lossless-cc hook-start          SessionStart hook handler (reads stdin)
```

## Architecture

- **Storage**: SQLite with WAL mode, FTS5 full-text search
- **Ingestion**: Incremental (tracks byte offset per session, only reads new data)
- **Summarization**: Claude Haiku API (falls back to extractive summary if no API key)
- **Privacy**: Everything stays local. No cloud sync, no telemetry.
- **Performance**: <200ms for Stop hook, <3s for PreCompact (includes LLM call)

## Requirements

- Python 3.11+
- Claude Code (for hooks integration)
- `ANTHROPIC_API_KEY` env var (optional, for Haiku-powered summaries)

## License

MIT
