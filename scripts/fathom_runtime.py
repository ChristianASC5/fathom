"""Helpers shared by Fathom's hook scripts.

Fathom can be installed two ways. As a Claude Code plugin it gets
CLAUDE_PLUGIN_DATA, a directory that survives plugin updates. Installers that
unpack a plugin into .claude/ (APM does this) never set that variable, so the
data directory falls back to a fixed path under the Claude config directory.

Nothing here opens a network connection, and nothing stores prompt or code
text. The event log holds move names, outcomes and the option label a user
picked.
"""
import json
import os
import sys
import time
from pathlib import Path


def data_dir() -> Path:
    root = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not root:
        config = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude")
        root = os.path.join(config, "fathom")
    path = Path(root)
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
