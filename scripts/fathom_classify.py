"""Ask Claude Haiku which learning goal a piece of work exercises.

Runs the user's own `claude` CLI, so the call goes to the provider the session
already uses. Every failure returns None and the caller lets the work proceed.
FATHOM_FAKE_CLASSIFICATION replaces the call for tests.
"""
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIDENCE = {"high", "medium", "low"}
TIMEOUT_SECONDS = 20


def _valid(result) -> bool:
    return (isinstance(result, dict)
            and (result.get("goal") is None or isinstance(result.get("goal"), str))
            and result.get("confidence") in CONFIDENCE
            and isinstance(result.get("has_choice"), bool))


def _run_claude(prompt: str) -> dict | None:
    command = [
        "claude", "-p", prompt,
        "--model", os.environ.get("FATHOM_CLASSIFIER_MODEL", "haiku"),
        "--system-prompt", (HERE / "classifier-prompt.txt").read_text(),
        "--json-schema", (HERE / "classifier-schema.json").read_text(),
        "--output-format", "json", "--tools", "", "--strict-mcp-config",
        "--setting-sources", "", "--no-session-persistence", "--disable-slash-commands",
    ]
    done = subprocess.run(command, env={**os.environ, "FATHOM_CLASSIFIER": "1"},
                          capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
    return json.loads(done.stdout).get("structured_output")


def classify(goals: list, digest: str) -> dict | None:
    try:
        fake = os.environ.get("FATHOM_FAKE_CLASSIFICATION")
        if fake is not None:
            result = None if fake == "error" else json.loads(fake)
        else:
            lines = "\n".join(f"{g['id']}: {g['text']}" for g in goals)
            result = _run_claude(f"Goals:\n{lines}\n\nSession so far:\n{digest}")
    except Exception:
        return None
    return result if _valid(result) else None
