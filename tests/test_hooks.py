"""Run the hook scripts the way Claude Code does: JSON on stdin, JSON on stdout."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
QUESTION = "What will this run do?"


def bash_call(command, prompt_id="p1", **extra):
    return {"session_id": "s1", "prompt_id": prompt_id, "hook_event_name": "PreToolUse",
            "tool_name": "Bash", "tool_input": {"command": command}, **extra}


def answer_call(label, header="Predict"):
    questions = [{"question": QUESTION, "header": header,
                  "options": [{"label": "All pass", "description": ""}, {"label": "Skip", "description": ""}]}]
    return {"session_id": "s1", "prompt_id": "p1", "hook_event_name": "PostToolUse",
            "tool_name": "AskUserQuestion", "tool_input": {"questions": questions},
            "tool_response": {"questions": questions, "answers": {QUESTION: label}}}


class HookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / "data"
        self.env = {**os.environ, "CLAUDE_PLUGIN_DATA": str(self.data)}
        self.env.pop("FATHOM_DEBUG", None)

    def run_hook(self, script, hook_input):
        result = subprocess.run([str(SCRIPTS / script)], input=json.dumps(hook_input),
                                capture_output=True, text=True, env=self.env, check=True)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def denied(self, output):
        return bool(output) and output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def events(self):
        log = self.data / "events.jsonl"
        if not log.exists():
            return []
        return [(e["move"], e["event"]) for e in map(json.loads, log.read_text().splitlines())]

    def test_first_test_run_is_denied_and_retry_passes_without_an_answer(self):
        self.assertTrue(self.denied(self.run_hook("predict-gate", bash_call("pytest -q"))))
        self.assertIsNone(self.run_hook("predict-gate", bash_call("pytest -q")))
        self.assertEqual(self.events(), [("predict", "offered"), ("predict", "unanswered")])

    def test_answer_is_recorded_and_tells_claude_to_run_the_tests(self):
        self.run_hook("predict-gate", bash_call("pytest -q"))
        output = self.run_hook("record-move", answer_call("All pass"))
        self.assertIn("Run the tests now", output["hookSpecificOutput"]["additionalContext"])
        self.assertIsNone(self.run_hook("predict-gate", bash_call("pytest -q")))
        self.assertEqual(self.events(), [("predict", "offered"), ("predict", "answered")])

    def test_skip_is_recorded_without_a_follow_up(self):
        self.run_hook("predict-gate", bash_call("pytest -q"))
        self.assertIsNone(self.run_hook("record-move", answer_call("Skip")))
        self.assertEqual(self.events(), [("predict", "offered"), ("predict", "skipped")])

    def test_later_runs_in_the_same_task_pass_and_a_new_prompt_is_gated_again(self):
        self.run_hook("predict-gate", bash_call("pytest -q"))
        self.run_hook("predict-gate", bash_call("pytest -q"))
        self.assertIsNone(self.run_hook("predict-gate", bash_call("pytest -q")))
        self.assertTrue(self.denied(self.run_hook("predict-gate", bash_call("pytest -q", prompt_id="p2"))))

    def test_gate_matches_pytest_inside_compound_and_module_commands(self):
        for i, command in enumerate(["cd api && pytest -q 2>&1 | tail -5", "python3 -m pytest tests", ".venv/bin/pytest"]):
            with self.subTest(command=command):
                self.assertTrue(self.denied(self.run_hook("predict-gate", bash_call(command, prompt_id=f"c{i}"))))

    def test_gate_ignores_other_commands_and_subagents(self):
        self.assertIsNone(self.run_hook("predict-gate", bash_call("pip install pytest-cov")))
        self.assertIsNone(self.run_hook("predict-gate", bash_call("pytest -q", agent_id="a1")))
        self.assertEqual(self.events(), [])

    def test_questions_fathom_did_not_ask_are_ignored(self):
        self.run_hook("predict-gate", bash_call("pytest -q"))
        self.assertIsNone(self.run_hook("record-move", answer_call("All pass", header="Approach")))
        self.assertEqual(self.events(), [("predict", "offered")])

    def test_data_falls_back_to_the_claude_config_dir_without_plugin_data(self):
        del self.env["CLAUDE_PLUGIN_DATA"]
        config = Path(self.tmp.name) / "config"
        self.env["CLAUDE_CONFIG_DIR"] = str(config)
        self.run_hook("predict-gate", bash_call("pytest -q"))
        self.assertTrue((config / "fathom" / "events.jsonl").exists())

    def test_hooks_leave_no_bytecode_in_the_plugin_folder(self):
        self.run_hook("predict-gate", bash_call("pytest -q"))
        self.run_hook("record-move", answer_call("All pass"))
        self.assertFalse((SCRIPTS / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
