"""Run the hook scripts the way Claude Code does: JSON on stdin, JSON on stdout."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.dont_write_bytecode = True

from fathom_classify import classify  # noqa: E402
from fathom_runtime import session_digest  # noqa: E402

QUESTION = "Which case first?"
GOALS = {"goals": [{"id": "g1", "text": "Write and debug Python list and slicing logic"}]}


def fake(goal="g1", confidence="high", has_choice=True, why="because"):
    return json.dumps({"goal": goal, "confidence": confidence, "has_choice": has_choice, "why": why})


def edit_call(prompt_id="p1", transcript="", **extra):
    return {"session_id": "s1", "prompt_id": prompt_id, "hook_event_name": "PreToolUse",
            "transcript_path": transcript, "tool_name": "Edit",
            "tool_input": {"file_path": "/x.py", "old_string": "a", "new_string": "b"}, **extra}


def answer_call(label, header="Check"):
    questions = [{"question": QUESTION, "header": header,
                  "options": [{"label": "Empty list", "description": ""}, {"label": "Skip", "description": ""}]}]
    return {"session_id": "s1", "prompt_id": "p1", "hook_event_name": "PostToolUse",
            "tool_name": "AskUserQuestion", "tool_input": {"questions": questions},
            "tool_response": {"questions": questions, "answers": {QUESTION: label}}}


def stop_call(transcript="", **extra):
    return {"session_id": "s1", "hook_event_name": "Stop", "transcript_path": transcript, **extra}


def jsonl(*entries):
    return "\n".join(json.dumps(e) for e in entries) + "\n"


def user(content, **extra):
    return {"type": "user", "message": {"role": "user", "content": content}, **extra}


def assistant(*blocks):
    return {"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}}


class HookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.data = self.dir / "data"
        self.data.mkdir()
        self.env = {**os.environ, "FATHOM_HOME": str(self.data), "FATHOM_FAKE_CLASSIFICATION": fake()}
        for name in ("FATHOM_DEBUG", "FATHOM_CLASSIFIER"):
            self.env.pop(name, None)

    def write_data(self, name, value):
        (self.data / name).write_text(json.dumps(value))

    def set_goals(self):
        self.write_data("goals.json", GOALS)

    def set_mastery(self, value):
        self.write_data("learner.json", {"goals": {"g1": {"mastery": value, "checks": 1}}})

    def transcript(self, *entries):
        path = self.dir / "transcript.jsonl"
        path.write_text(jsonl(*entries))
        return str(path)

    def run_hook(self, script, hook_input, **env):
        result = subprocess.run([str(SCRIPTS / script)], input=json.dumps(hook_input),
                                capture_output=True, text=True, env={**self.env, **env}, check=True)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def denied(self, output):
        return bool(output) and output["hookSpecificOutput"]["permissionDecision"] == "deny"

    def blocked(self, output):
        return bool(output) and output.get("decision") == "block"

    def log(self):
        path = self.data / "events.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def events(self):
        return [(e["move"], e["event"]) for e in self.log()]

    def state(self):
        return json.loads((self.data / "state" / "s1.json").read_text())

    def mastery(self):
        return json.loads((self.data / "learner.json").read_text())["goals"]["g1"]["mastery"]

    # Trigger

    def test_no_goals_passes_and_is_logged(self):
        self.assertIsNone(self.run_hook("edit-gate", edit_call()))
        self.assertEqual(self.log()[0]["reason"], "no_goals")
        self.assertEqual(self.events(), [("trigger", "skipped")])

    def test_invalid_goals_file_counts_as_no_goals(self):
        (self.data / "goals.json").write_text("not json")
        self.run_hook("edit-gate", edit_call())
        self.assertEqual(self.log()[0]["reason"], "no_goals")

    def test_relevant_goal_at_zero_mastery_runs_an_after_move(self):
        self.set_goals()
        self.assertIsNone(self.run_hook("edit-gate", edit_call()))
        self.assertEqual(self.state()["move"], "after")
        output = self.run_hook("stop-check", stop_call())
        self.assertTrue(self.blocked(output))
        self.assertIn("'Check'", output["reason"])
        self.assertIn("Python list and slicing", output["reason"])
        self.assertIn(("check", "offered"), self.events())

    def test_stop_hook_active_does_not_block(self):
        self.set_goals()
        self.run_hook("edit-gate", edit_call())
        self.assertIsNone(self.run_hook("stop-check", stop_call(stop_hook_active=True)))
        self.assertNotIn(("check", "offered"), self.events())

    def test_after_move_blocks_only_once(self):
        self.set_goals()
        self.run_hook("edit-gate", edit_call())
        self.assertTrue(self.blocked(self.run_hook("stop-check", stop_call())))
        self.assertIsNone(self.run_hook("stop-check", stop_call()))

    def test_stop_without_a_move_does_nothing(self):
        self.assertIsNone(self.run_hook("stop-check", stop_call()))
        self.assertEqual(self.events(), [])

    def test_mastered_goal_with_a_choice_holds_the_edit_for_an_approach_question(self):
        self.set_goals()
        self.set_mastery(0.6)
        output = self.run_hook("edit-gate", edit_call())
        self.assertTrue(self.denied(output))
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("'Approach'", reason)
        self.assertTrue("option 1" in reason or "option 2" in reason)
        self.assertEqual(self.state()["move"], "before")
        self.assertIn(("approach", "offered"), self.events())

    def test_mastered_goal_without_a_choice_runs_an_after_move(self):
        self.set_goals()
        self.set_mastery(0.6)
        self.env["FATHOM_FAKE_CLASSIFICATION"] = fake(has_choice=False)
        self.assertIsNone(self.run_hook("edit-gate", edit_call()))
        self.assertEqual(self.state()["move"], "after")

    def test_retry_of_a_held_edit_passes(self):
        self.set_goals()
        self.set_mastery(0.6)
        self.assertTrue(self.denied(self.run_hook("edit-gate", edit_call())))
        self.assertIsNone(self.run_hook("edit-gate", edit_call(), FATHOM_FAKE_CLASSIFICATION="error"))

    def test_later_edit_in_the_same_task_skips_the_classifier(self):
        self.set_goals()
        self.run_hook("edit-gate", edit_call())
        before = self.events()
        self.assertIsNone(self.run_hook("edit-gate", edit_call(), FATHOM_FAKE_CLASSIFICATION="error"))
        self.assertEqual(self.events(), before)

    def test_new_prompt_is_classified_again(self):
        self.set_goals()
        self.run_hook("edit-gate", edit_call())
        self.run_hook("edit-gate", edit_call(prompt_id="p2"))
        self.assertEqual(self.events().count(("trigger", "classified")), 2)
        self.assertEqual(self.state()["task"], "p2")

    def test_ship_mode_skips(self):
        self.set_goals()
        self.write_data("config.json", {"mode": "ship"})
        self.assertIsNone(self.run_hook("edit-gate", edit_call()))
        self.assertEqual(self.log()[0]["reason"], "ship_mode")

    def test_exhausted_daily_budget_skips(self):
        self.set_goals()
        self.write_data("config.json", {"moves_per_day": 2})
        today = time.strftime("%Y-%m-%dT%H:%M:%S")
        (self.data / "events.jsonl").write_text(jsonl(
            {"ts": today, "move": "approach", "event": "offered"},
            {"ts": today, "move": "check", "event": "offered"}))
        self.assertIsNone(self.run_hook("edit-gate", edit_call()))
        self.assertEqual(self.log()[-1]["reason"], "budget")

    def test_yesterdays_offers_do_not_count_against_the_budget(self):
        self.set_goals()
        self.write_data("config.json", {"moves_per_day": 1})
        (self.data / "events.jsonl").write_text(jsonl(
            {"ts": "2020-01-01T10:00:00", "move": "check", "event": "offered"}))
        self.run_hook("edit-gate", edit_call())
        self.assertEqual(self.state()["move"], "after")

    def test_classifier_error_lets_the_edit_through(self):
        self.set_goals()
        self.set_mastery(0.6)
        self.assertIsNone(self.run_hook("edit-gate", edit_call(), FATHOM_FAKE_CLASSIFICATION="error"))
        self.assertEqual(self.events(), [("trigger", "classifier_error")])
        self.assertIsNone(self.state().get("move"))

    def test_irrelevant_classifications_start_no_move(self):
        self.set_goals()
        cases = {"low confidence": fake(confidence="low"), "unknown goal": fake(goal="g9"),
                 "null goal": fake(goal=None)}
        for i, (name, value) in enumerate(cases.items()):
            with self.subTest(name):
                self.assertIsNone(self.run_hook("edit-gate", edit_call(prompt_id=f"q{i}"),
                                                FATHOM_FAKE_CLASSIFICATION=value))
                self.assertIsNone(self.state().get("move"))

    def test_subagent_edits_are_ignored(self):
        self.set_goals()
        self.assertIsNone(self.run_hook("edit-gate", edit_call(agent_id="a1")))
        self.assertEqual(self.events(), [])

    def test_classifier_child_process_is_ignored(self):
        self.set_goals()
        self.assertIsNone(self.run_hook("edit-gate", edit_call(), FATHOM_CLASSIFIER="1"))
        self.assertIsNone(self.run_hook("stop-check", stop_call(), FATHOM_CLASSIFIER="1"))
        self.assertEqual(self.events(), [])

    # Recording answers

    def test_check_answer_is_recorded_with_its_label(self):
        self.set_goals()
        self.run_hook("edit-gate", edit_call())
        self.assertIsNone(self.run_hook("record-move", answer_call("Empty list")))
        self.assertEqual(self.log()[-1], {**self.log()[-1], "move": "check", "event": "answered",
                                          "goal": "g1", "label": "Empty list"})
        self.assertEqual(self.state()["answer"], "Empty list")

    def test_skipped_check_is_recorded_and_not_scored(self):
        self.set_goals()
        self.run_hook("edit-gate", edit_call())
        self.run_hook("stop-check", stop_call())
        self.run_hook("record-move", answer_call("skip"))
        self.assertEqual(self.events()[-1], ("check", "skipped"))
        self.run_hook("stop-check", stop_call(last_assistant_message="Held. Fine."))
        self.assertFalse((self.data / "learner.json").exists())
        self.assertNotIn(("check", "verdict"), self.events())

    def test_missing_answer_is_recorded_as_unanswered(self):
        call = answer_call("x")
        del call["tool_response"]
        self.run_hook("record-move", call)
        self.assertEqual(self.events(), [("check", "unanswered")])

    def test_other_questions_are_ignored(self):
        self.run_hook("record-move", answer_call("x", header="Something"))
        self.assertEqual(self.events(), [])

    # Scoring

    def answered_check(self):
        self.set_goals()
        self.run_hook("edit-gate", edit_call())
        self.run_hook("stop-check", stop_call())
        self.run_hook("record-move", answer_call("Empty list"))

    def stop_with(self, text):
        path = self.transcript(user("go"), assistant({"type": "text", "text": text}))
        self.run_hook("stop-check", stop_call(path, stop_hook_active=True))

    def test_held_raises_mastery(self):
        self.answered_check()
        self.stop_with("Held. Single-element input is the right first case.")
        self.assertAlmostEqual(self.mastery(), 0.3)
        self.assertEqual(self.log()[-1]["verdict"], "held")
        self.assertEqual(self.events()[-1], ("check", "verdict"))

    def test_missed_keeps_zero_mastery_and_counts_the_check(self):
        self.answered_check()
        self.stop_with("Missed. The empty list breaks it.")
        self.assertEqual(self.mastery(), 0.0)
        self.assertEqual(self.log()[-1]["verdict"], "missed")
        learner = json.loads((self.data / "learner.json").read_text())
        self.assertEqual(learner["goals"]["g1"]["checks"], 1)

    def test_missing_verdict_is_logged_as_unreadable(self):
        self.answered_check()
        self.stop_with("Looks fine to me.")
        self.assertEqual(self.events()[-1], ("check", "verdict_unreadable"))
        self.assertFalse((self.data / "learner.json").exists())

    def test_scoring_happens_once(self):
        self.answered_check()
        self.stop_with("Held. Yes.")
        self.stop_with("Held. Yes.")
        self.assertAlmostEqual(self.mastery(), 0.3)

    def test_last_assistant_message_takes_precedence_over_the_transcript(self):
        self.answered_check()
        path = self.transcript(assistant({"type": "text", "text": "Missed. No."}))
        self.run_hook("stop-check", stop_call(path, last_assistant_message="Held. Yes."))
        self.assertAlmostEqual(self.mastery(), 0.3)

    # Digest

    def test_digest_has_prompts_and_tool_calls_but_no_results(self):
        path = self.transcript(
            user("fix the slicing bug"),
            user("meta note", isMeta=True),
            assistant({"type": "tool_use", "name": "Read", "input": {"file_path": "/x.py"}}),
            user([{"type": "tool_result", "content": "SECRET FILE CONTENTS"}]),
            assistant({"type": "tool_use", "name": "Bash", "input": {"command": "pytest -q"}}))
        digest = session_digest(path, "Edit", {"file_path": "/x.py", "old_string": "OLD", "new_string": "NEW"})
        self.assertIn('User: "fix the slicing bug"', digest)
        self.assertIn("Claude used Read: /x.py", digest)
        self.assertIn("Claude used Bash: pytest -q", digest)
        self.assertNotIn("SECRET", digest)
        self.assertNotIn("meta note", digest)
        self.assertIn("Claude is about to Edit /x.py:\nReplace:\nOLD\nWith:\nNEW", digest)

    def test_digest_caps_the_pending_edit_and_keeps_thirty_history_lines(self):
        path = self.transcript(*[user(f"prompt {i}") for i in range(40)])
        digest = session_digest(path, "Write", {"file_path": "/big.py", "content": "x" * 10000})
        self.assertEqual(digest.count("x"), 4000)
        self.assertEqual(digest.count("User:"), 30)
        self.assertIn("prompt 39", digest)
        self.assertNotIn('"prompt 9"', digest)

    def test_digest_survives_a_missing_transcript(self):
        digest = session_digest(str(self.dir / "none.jsonl"), "NotebookEdit",
                                {"notebook_path": "/n.ipynb", "new_source": "print(1)"})
        self.assertEqual(digest, "Claude is about to NotebookEdit /n.ipynb:\nprint(1)")

    # Classifier

    def test_classify_returns_none_when_claude_is_not_installed(self):
        empty = self.dir / "empty"
        empty.mkdir()
        env = {k: v for k, v in os.environ.items() if k != "FATHOM_FAKE_CLASSIFICATION"}
        env["PATH"] = str(empty)
        original = os.environ.copy()
        os.environ.clear()
        os.environ.update(env)
        try:
            self.assertIsNone(classify(GOALS["goals"], "digest"))
        finally:
            os.environ.clear()
            os.environ.update(original)

    def test_classify_rejects_invalid_output(self):
        original = os.environ.get("FATHOM_FAKE_CLASSIFICATION")
        self.addCleanup(os.environ.__setitem__, "FATHOM_FAKE_CLASSIFICATION", original or "error")
        for value in (fake(confidence="maybe"), '{"goal": 3, "confidence": "high", "has_choice": true}',
                      fake().replace("true", '"yes"'), "not json", "error"):
            with self.subTest(value=value):
                os.environ["FATHOM_FAKE_CLASSIFICATION"] = value
                self.assertIsNone(classify(GOALS["goals"], "digest"))
        os.environ["FATHOM_FAKE_CLASSIFICATION"] = fake()
        self.assertEqual(classify(GOALS["goals"], "digest")["goal"], "g1")

    # Privacy and housekeeping

    def test_events_never_hold_the_classifier_reason_or_the_digest(self):
        self.set_goals()
        self.env["FATHOM_FAKE_CLASSIFICATION"] = fake(why="UNIQUE-WHY-TEXT")
        path = self.transcript(user("UNIQUE-PROMPT-TEXT"))
        self.run_hook("edit-gate", edit_call(transcript=path))
        self.run_hook("stop-check", stop_call(path))
        raw = (self.data / "events.jsonl").read_text()
        self.assertNotIn("UNIQUE", raw)
        self.assertNotIn("/x.py", raw)

    def test_data_defaults_to_dot_fathom_in_the_home_directory(self):
        del self.env["FATHOM_HOME"]
        self.env["HOME"] = self.tmp.name
        self.run_hook("edit-gate", edit_call())
        self.assertTrue((self.dir / ".fathom" / "events.jsonl").exists())

    def test_hooks_leave_no_bytecode_in_the_plugin_folder(self):
        self.set_goals()
        self.run_hook("edit-gate", edit_call())
        self.run_hook("stop-check", stop_call())
        self.run_hook("record-move", answer_call("Empty list"))
        self.assertFalse((SCRIPTS / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
