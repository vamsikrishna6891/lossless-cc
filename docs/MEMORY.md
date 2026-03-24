# Lossless CC - Memory

## Key Discoveries

- Claude Code has a `PreCompact` hook (fires before context compression). This is the critical hook that makes lossless context possible.
- Session JSONL files are at `~/.claude/projects/<escaped-path>/<session-uuid>.jsonl`
- JSONL has 5 message types: queue-operation, file-history-snapshot, user, assistant, progress
- Messages are linked via `parentUuid` to form a conversation tree
- `Stop` hook receives `transcript_path` on stdin (path to session JSONL)
- `SessionStart` hook receives `source` field: "startup", "resume", "clear", or "compact"
- Several session viewers exist (claude-history, claude-session-viewer, etc.) but NONE do active context recall or summarization
- lossless-claw (OpenClaw only, 3.3K stars) is the closest prior art but doesn't work with Claude Code

## Decisions

- SQLite for storage (zero setup, portable)
- FTS5 for full-text search
- Python + Click for CLI
- Haiku for cheap summarization (fallback: Ollama for offline)
- MIT license, open source under Vamsi's personal GitHub (H1B safe, no CobbleLabs branding)
