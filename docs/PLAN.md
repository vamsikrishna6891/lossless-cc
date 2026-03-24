# Lossless CC - Build Plan

Each step is one atomic session.

## Step 1: Project Scaffolding + DB Layer
- [ ] Set up pyproject.toml with uv, click, sqlite dependencies
- [ ] Implement db.py: create tables, migrations, connection management
- [ ] Implement ingest_state tracking
- [ ] Write tests for DB layer
- [ ] Create sample JSONL fixture from real Claude Code session

## Step 2: Ingest (Stop Hook)
- [ ] Implement ingest.py: parse JSONL, extract messages, store in SQLite
- [ ] Handle incremental ingestion (only new lines)
- [ ] Handle all message types (user, assistant, progress, queue-operation)
- [ ] Wire up as Stop hook script
- [ ] Test with real Claude Code session JSONL
- [ ] Verify <200ms execution time

## Step 3: Search (CLI)
- [ ] Implement cli.py with Click
- [ ] `lossless-cc grep` with FTS5
- [ ] `lossless-cc sessions` list
- [ ] `lossless-cc stats`
- [ ] Test all commands

## Step 4: Compact (PreCompact Hook)
- [ ] Implement summarizer.py (Haiku API call)
- [ ] Implement compact.py: read stdin, summarize, store, output
- [ ] Wire up as PreCompact hook
- [ ] Test with mock compaction event
- [ ] Verify <3s execution time

## Step 5: Inject (SessionStart Hook)
- [ ] Implement inject.py: load recent summaries, output context
- [ ] Smart context selection (most relevant, not just most recent)
- [ ] Wire up as SessionStart hook
- [ ] Test end-to-end: ingest -> compact -> inject across sessions

## Step 6: Recall Command
- [ ] `lossless-cc recall` that searches summaries first, then raw messages
- [ ] Rank results by relevance
- [ ] Format output for agent consumption (concise, structured)

## Step 7: Polish + Release
- [ ] README with install instructions, architecture diagram, demo GIF
- [ ] `uv tool install` / `pip install` packaging
- [ ] CLAUDE.md for the project itself
- [ ] GitHub repo under personal account (vamsikrishnateegavarapu)
- [ ] HackerNews / Reddit / Twitter launch posts
