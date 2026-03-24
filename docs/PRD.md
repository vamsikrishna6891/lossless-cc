# Lossless CC - Product Requirements Document

## Problem

When Claude Code compacts context (drops older messages to fit token limits), information is permanently lost. Users lose decisions, debugging context, and conversation history mid-session. The only mitigations today are manual (writing primer.md, MEMORY.md), which fail when context runs out unexpectedly.

## Solution

Lossless CC is an open-source Claude Code hook + CLI tool that:
1. Persists every conversation message to a local SQLite database (via `Stop` hook)
2. Builds hierarchical summaries before compaction (via `PreCompact` hook)
3. Injects relevant historical context back into the session (via `SessionStart` hook)
4. Provides CLI tools for the agent to search and recall past context

## Target Users

- Claude Code power users running long sessions
- Developers using Claude Squad (multi-session)
- Anyone who's lost context mid-session and had to re-explain

## Core Features

### P0 (MVP)

1. **Message Persistence**: `Stop` hook reads session JSONL, appends new messages to SQLite
2. **PreCompact Summary**: `PreCompact` hook generates a summary of what's about to be compacted, stores it in SQLite
3. **CLI Recall**: `lossless-cc recall "what did we decide about auth"` searches across all sessions
4. **CLI Grep**: `lossless-cc grep "supabase migration"` full-text search across message history
5. **Session Start Injection**: `SessionStart` hook injects relevant summaries from past sessions

### P1 (Post-MVP)

6. **DAG Summarization**: Hierarchical summary tree (like lossless-claw) for multi-level recall
7. **Cross-Session Context**: Agent can pull context from other project sessions
8. **Stats Dashboard**: `lossless-cc stats` shows token usage, session count, compaction events
9. **Export**: `lossless-cc export --format md` export full session history as markdown

### P2 (Future)

10. **Semantic Search**: Vector embeddings for better recall (local, via Ollama)
11. **Auto-Context**: Learns which context is most frequently recalled and pre-loads it
12. **Claude Squad Integration**: Share context between concurrent sessions

## Non-Goals

- Not replacing Claude Code's built-in context management
- Not a conversation viewer/browser (several exist already)
- Not cloud-based (everything local, privacy-first)

## Technical Constraints

- Must work as Claude Code hooks (Stop, PreCompact, SessionStart)
- CLI must be callable via Bash tool by the agent
- SQLite only (no external dependencies)
- Python (uv for package management)
- Must not slow down session (<500ms per hook execution)
- Must handle concurrent sessions (Claude Squad)

## Success Metrics

- Zero information loss across compaction events
- <500ms hook execution time
- Agent can recall decisions from 10+ sessions ago
- 500+ GitHub stars in first month (stretch)

## Competitive Landscape

| Tool | Platform | Approach |
|------|----------|----------|
| lossless-claw | OpenClaw only | DAG plugin, no Claude Code support |
| claude-session-restore | Claude Code | Restores context but no summarization |
| claude-history (various) | Claude Code | Read-only viewers, no active recall |
| **lossless-cc (us)** | **Claude Code** | **Active hooks + CLI recall + summarization** |

## Distribution

- Open source (MIT license)
- Install via `uv tool install lossless-cc` or `pip install lossless-cc`
- Published on personal GitHub (github.com/vamsikrishnateegavarapu/lossless-cc)
- Announced on HackerNews, Twitter, r/ClaudeAI
