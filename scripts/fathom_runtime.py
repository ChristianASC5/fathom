"""Helpers shared by Fathom's hook scripts.

Fathom keeps everything it writes in one folder, ~/.fathom, whichever way it
was installed. FATHOM_HOME moves that folder, which the tests use.

Fathom's only network use is the classifier call in fathom_classify.py, which
runs the user's own `claude` CLI. The event log holds move names, goal ids,
outcomes, the option label a user picked and timings, never prompt or code
text.
"""
import json
import os
import sys
import time
from pathlib import Path


def data_dir() -> Path:
    path = Path(os.environ.get("FATHOM_HOME") or os.path.expanduser("~/.fathom"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_input() -> dict:
    try:
        return json.load(sys.stdin)
    except ValueError:
        return {}


def record_event(move: str, event: str, **fields) -> None:
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "move": move, "event": event, **fields}
    with open(data_dir() / "events.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")


def debug_dump(script: str, hook_input: dict) -> None:
    """Write the raw hook input, prompts and commands included, when FATHOM_DEBUG=1.

    Off by default because it breaks the no-content rule above. It exists for
    working out what Claude Code sends a hook.
    """
    if os.environ.get("FATHOM_DEBUG") != "1":
        return
    with open(data_dir() / "debug-hook-inputs.jsonl", "a") as f:
        f.write(json.dumps({"script": script, "input": hook_input}) + "\n")


def _state_path(session_id: str) -> Path:
    directory = data_dir() / "state"
    directory.mkdir(exist_ok=True)
    return directory / f"{session_id or 'unknown'}.json"


def load_state(session_id: str) -> dict:
    try:
        return json.loads(_state_path(session_id).read_text())
    except (OSError, ValueError):
        return {}


def save_state(session_id: str, state: dict) -> None:
    _state_path(session_id).write_text(json.dumps(state))


DEFAULT_CONFIG = {"mode": "learn", "moves_per_day": 3, "mastery_threshold": 0.5}


def _load_json(name: str):
    try:
        return json.loads((data_dir() / name).read_text())
    except (OSError, ValueError):
        return None


def load_goals() -> list:
    """Return the learner's goals as [{"id", "text"}], or [] if none are usable."""
    data = _load_json("goals.json")
    goals = data.get("goals") if isinstance(data, dict) else None
    if not isinstance(goals, list):
        return []
    return [g for g in goals if isinstance(g, dict) and isinstance(g.get("id"), str)
            and isinstance(g.get("text"), str)]


def load_config() -> dict:
    data = _load_json("config.json")
    config = dict(DEFAULT_CONFIG)
    if isinstance(data, dict):
        config.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
    return config


def load_learner() -> dict:
    data = _load_json("learner.json")
    if isinstance(data, dict) and isinstance(data.get("goals"), dict):
        return data
    return {"goals": {}}


def save_learner(learner: dict) -> None:
    (data_dir() / "learner.json").write_text(json.dumps(learner))


def mastery_for(learner: dict, goal_id: str) -> float:
    entry = learner.get("goals", {}).get(goal_id)
    value = entry.get("mastery") if isinstance(entry, dict) else None
    return float(value) if isinstance(value, (int, float)) else 0.0


def count_events_today(event: str) -> int:
    today = time.strftime("%Y-%m-%d")
    try:
        lines = (data_dir() / "events.jsonl").read_text().splitlines()
    except OSError:
        return 0
    count = 0
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get("event") == event and str(record.get("ts", "")).startswith(today):
            count += 1
    return count


HISTORY_LINES = 30
EDIT_BODY_LIMIT = 4000


def _text_of(content) -> str | None:
    """Text of a user message, or None if it is not plain prompt text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list) and content and all(
            isinstance(b, dict) and b.get("type") == "text" for b in content):
        return "\n".join(str(b.get("text", "")) for b in content)
    return None


def _tool_target(tool_input: dict) -> str:
    for key in ("file_path", "notebook_path", "command", "pattern"):
        if isinstance(tool_input.get(key), str):
            return tool_input[key][:200]
    return ""


def _history(transcript_path: str) -> list:
    lines = []
    try:
        with open(transcript_path) as f:
            raw = f.read().splitlines()
    except (OSError, TypeError):
        return lines
    for line in raw:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message") if isinstance(entry, dict) else None
        if not isinstance(message, dict):
            continue
        if entry.get("type") == "user" and not entry.get("isMeta"):
            text = _text_of(message.get("content"))
            if text:
                lines.append(f'User: "{text[:300]}"')
        elif entry.get("type") == "assistant" and isinstance(message.get("content"), list):
            for block in message["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    target = _tool_target(block.get("input") or {})
                    lines.append(f"Claude used {block.get('name')}: {target}")
    return lines[-HISTORY_LINES:]


def _edit_body(tool_name: str, tool_input: dict) -> str:
    def replacement(item: dict) -> str:
        return f"Replace:\n{item.get('old_string', '')}\nWith:\n{item.get('new_string', '')}"

    if tool_name == "Write":
        body = tool_input.get("content", "")
    elif tool_name == "Edit":
        body = replacement(tool_input)
    elif tool_name == "MultiEdit":
        body = "\n".join(replacement(e) for e in tool_input.get("edits", []) if isinstance(e, dict))
    elif tool_name == "NotebookEdit":
        body = tool_input.get("new_source", "")
    else:
        body = ""
    return str(body)[:EDIT_BODY_LIMIT]


def session_digest(transcript_path: str, tool_name: str, tool_input: dict) -> str:
    """Summarise the session for the classifier: prompts, tool names and targets, the pending edit.

    Tool results and file contents from the transcript are never included.
    """
    target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    pending = f"Claude is about to {tool_name} {target}:\n{_edit_body(tool_name, tool_input)}"
    return "\n".join(_history(transcript_path) + [pending])
