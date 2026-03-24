"""LLM summarization for compacted context. Uses Claude Haiku for cheap, fast summaries."""

import json
import os
import subprocess


SUMMARY_PROMPT = """Summarize the following conversation messages into a concise, information-dense summary.
Focus on:
- Decisions made
- Key facts discovered
- Technical choices and their reasoning
- Action items or next steps
- Important context that would be needed to continue this work

Be specific. Include names, numbers, file paths, and technical details. Do NOT use generic summaries.
Keep it under 500 words.

Messages:
{messages}"""


def summarize_messages(messages: list[dict], api_key: str | None = None) -> str:
    """Summarize a batch of messages using Claude Haiku via CLI.

    Falls back to a simple extractive summary if no API key is available.
    """
    if not messages:
        return ""

    formatted = _format_messages(messages)

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return _extractive_summary(messages)

    try:
        return _call_haiku(formatted, key)
    except Exception:
        return _extractive_summary(messages)


def _format_messages(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        role = m.get("role", m.get("type", "unknown"))
        content = m.get("content", "")
        if len(content) > 1000:
            content = content[:1000] + "..."
        parts.append(f"[{role}] {content}")
    return "\n\n".join(parts)


def _call_haiku(formatted_messages: str, api_key: str) -> str:
    """Call Claude Haiku via the Anthropic API using curl."""
    prompt = SUMMARY_PROMPT.format(messages=formatted_messages)

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }

    result = subprocess.run(
        [
            "curl", "-s",
            "https://api.anthropic.com/v1/messages",
            "-H", f"x-api-key: {api_key}",
            "-H", "anthropic-version: 2023-06-01",
            "-H", "content-type: application/json",
            "-d", json.dumps(payload),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )

    if result.returncode != 0:
        raise RuntimeError(f"API call failed: {result.stderr}")

    response = json.loads(result.stdout)
    if "content" in response and response["content"]:
        return response["content"][0].get("text", "")

    raise RuntimeError(f"Unexpected response: {result.stdout[:200]}")


def _extractive_summary(messages: list[dict]) -> str:
    """Fallback: extract key sentences from messages without LLM."""
    parts = []
    for m in messages:
        role = m.get("role", m.get("type", "unknown"))
        content = m.get("content", "")
        if not content.strip():
            continue
        # Take first 200 chars of each message
        preview = content[:200].replace("\n", " ").strip()
        if preview:
            parts.append(f"[{role}] {preview}")

    if not parts:
        return "No meaningful content to summarize."

    return "Extractive summary (no API key):\n" + "\n".join(parts[:20])
