#!/usr/bin/env python3
"""Update session title using LLM at SessionEnd.

Reads the session's user messages, asks Claude for a concise title,
and updates the markdown frontmatter. Skips if title was manually set.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Reuse STRIP_PATTERNS from claude-sessions
STRIP_PATTERNS = [
    re.compile(r'<system-reminder>.*?</system-reminder>', re.DOTALL),
    re.compile(r'<local-command-caveat>.*?</local-command-caveat>', re.DOTALL),
    re.compile(r'<local-command-stdout>.*?</local-command-stdout>', re.DOTALL),
    re.compile(r'<command-name>.*?</command-name>\s*<command-message>.*?</command-message>\s*(?:<command-args>.*?</command-args>)?', re.DOTALL),
    re.compile(r'<command-message>.*?</command-message>', re.DOTALL),
    re.compile(r'<command-name>.*?</command-name>', re.DOTALL),
    re.compile(r'<command-args>.*?</command-args>', re.DOTALL),
    re.compile(r'<task-notification>.*?</task-notification>', re.DOTALL),
    re.compile(r'<teammate-message[^>]*>.*?</teammate-message>', re.DOTALL),
    re.compile(r'<ide_opened_file>.*?</ide_opened_file>', re.DOTALL),
]


def clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    for pat in STRIP_PATTERNS:
        text = pat.sub('', text)
    return text.strip()


def get_user_messages(jsonl_path: Path, max_messages: int = 30) -> list[str]:
    """Extract cleaned user messages from JSONL."""
    messages = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") != "user" or record.get("isMeta"):
                continue
            msg = record.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, str):
                cleaned = clean_text(content)
                if cleaned and not cleaned.startswith("Base directory for this skill:"):
                    messages.append(cleaned)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        cleaned = clean_text(item.get("text", ""))
                        if cleaned and not cleaned.startswith("Base directory for this skill:"):
                            messages.append(cleaned)
            if len(messages) >= max_messages:
                break
    return messages


def get_assistant_summaries(jsonl_path: Path, max_summaries: int = 5) -> list[str]:
    """Extract assistant's first lines for additional context."""
    summaries = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") != "assistant":
                continue
            msg = record.get("message", {})
            contents = msg.get("content", [])
            if isinstance(contents, list):
                for item in contents:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "").strip()
                        if text:
                            first_line = text.split("\n")[0][:200]
                            summaries.append(first_line)
                            break
            if len(summaries) >= max_summaries:
                break
    return summaries


def generate_title(messages: list[str], assistant_lines: list[str]) -> str | None:
    """Call claude CLI to generate a concise title."""
    # Build context: user messages + assistant first lines
    context_parts = []
    for i, msg in enumerate(messages[:20]):
        # Truncate long messages
        truncated = msg[:300] + "..." if len(msg) > 300 else msg
        context_parts.append(f"User: {truncated}")

    for line in assistant_lines[:3]:
        context_parts.append(f"Assistant: {line}")

    context = "\n".join(context_parts)

    prompt = f"""Below is a Claude Code session's conversation snippets. Generate a concise title (max 60 chars) that captures the main topic/task. Write the title in the same language the user primarily uses. Output ONLY the title, nothing else.

{context}"""

    try:
        env = os.environ.copy()
        # Allow running claude inside a Claude Code session (SessionEnd hook)
        env.pop("CLAUDECODE", None)
        result = subprocess.run(
            ["claude", "-p", "--model", "haiku", "--no-session-persistence"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode == 0 and result.stdout.strip():
            title = result.stdout.strip()
            # Remove quotes if wrapped
            if (title.startswith('"') and title.endswith('"')) or \
               (title.startswith("'") and title.endswith("'")):
                title = title[1:-1]
            # Take only first line in case of extra output
            title = title.split("\n")[0].strip()
            # Ensure max length
            return title[:80]
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Title generation failed: {e}", file=sys.stderr)
    return None


def find_session_markdown(vault_dir: Path, session_id: str) -> Path | None:
    """Find the markdown file for a session."""
    sessions_dir_env = os.environ.get("VAULT_SESSIONS_DIR")
    sessions_dir = Path(sessions_dir_env) if sessions_dir_env else vault_dir / "Claude-Sessions"
    if not sessions_dir.exists():
        return None
    short_id = session_id[:8]
    for f in sessions_dir.glob(f"*-{short_id}.md"):
        return f
    return None


def update_markdown_title(md_path: Path, new_title: str):
    """Update title in frontmatter and H1 heading."""
    content = md_path.read_text(encoding="utf-8")

    # Update frontmatter title
    escaped = new_title.replace('"', '\\"')
    content = re.sub(
        r'^title: ".*?"',
        f'title: "{escaped}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )

    # Update H1 heading
    content = re.sub(
        r'^# .+$',
        f'# {new_title}',
        content,
        count=1,
        flags=re.MULTILINE,
    )

    md_path.write_text(content, encoding="utf-8")


def find_latest_session_jsonl() -> tuple[str, Path] | None:
    """Find the most recently modified session JSONL."""
    projects_dir = Path.home() / ".claude" / "projects"
    if not projects_dir.exists():
        return None

    latest = None
    latest_mtime = 0

    for jsonl in projects_dir.glob("**/*.jsonl"):
        if jsonl.name.startswith("agent-"):
            continue
        mtime = jsonl.stat().st_mtime
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest = jsonl

    if latest:
        return latest.stem, latest
    return None


def main():
    vault_dir = os.environ.get("VAULT_DIR")
    if not vault_dir:
        print("VAULT_DIR not set", file=sys.stderr)
        return 1

    vault_path = Path(vault_dir)

    # Find the session that just ended (most recently modified JSONL)
    result = find_latest_session_jsonl()
    if not result:
        print("No session JSONL found", file=sys.stderr)
        return 1

    session_id, jsonl_path = result

    # Find corresponding markdown
    md_path = find_session_markdown(vault_path, session_id)
    if not md_path:
        print(f"No markdown found for {session_id[:8]}", file=sys.stderr)
        return 1

    # Check if title was manually set (has a custom-title record)
    has_custom_title = False
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                if record.get("type") == "custom-title":
                    has_custom_title = True
                    break
            except (json.JSONDecodeError, AttributeError):
                continue

    if has_custom_title:
        print(f"Skipping {session_id[:8]}: has custom title")
        return 0

    # Extract messages
    messages = get_user_messages(jsonl_path)
    if len(messages) < 2:
        print(f"Skipping {session_id[:8]}: too few messages ({len(messages)})")
        return 0

    assistant_lines = get_assistant_summaries(jsonl_path)

    # Generate LLM title
    new_title = generate_title(messages, assistant_lines)
    if not new_title:
        print(f"Failed to generate title for {session_id[:8]}")
        return 1

    # Update markdown
    update_markdown_title(md_path, new_title)
    print(f"Updated title for {session_id[:8]}: {new_title}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
