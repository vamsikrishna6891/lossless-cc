# CLAUDE.md - Lossless CC

## Project Overview

Lossless CC is an open-source Claude Code plugin (hooks + CLI) that provides lossless context management. It persists every conversation message to SQLite, generates summaries before context compaction, and lets agents recall past context via CLI.

## Architecture

- `src/lossless_cc/` - Python package
- `docs/` - PRD, ARCHITECTURE, PLAN, MEMORY
- Uses Claude Code hooks: Stop (ingest), PreCompact (summarize), SessionStart (inject)
- SQLite DB at `~/.lossless-cc/lossless.db`
- CLI via Click: `lossless-cc grep`, `lossless-cc recall`, `lossless-cc sessions`, `lossless-cc stats`

## Tech Stack

- Python 3.12+
- uv for package management
- Click for CLI
- SQLite + FTS5 for storage and search
- Claude Haiku API for summarization (fallback: Ollama)

## Development

```bash
uv sync                    # install deps
uv run pytest              # run tests
uv run lossless-cc --help  # test CLI
```

## Key Constraints

- Hook execution must be <500ms (Stop: <200ms, PreCompact: <3s)
- All data stays local (privacy-first)
- Must handle concurrent sessions (Claude Squad)
- No external dependencies beyond SQLite
