"""Run fathom_goals.py against a throwaway FATHOM_HOME."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "fathom-goals"


class GoalsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "fathom-home"
        self.env = {**os.environ, "FATHOM_HOME": str(self.home)}
        self.script = SKILL / "fathom_goals.py"

    def run_goals(self, *args):
        return subprocess.run([sys.executable, str(self.script), *args], capture_output=True, text=True, env=self.env)

    def ok(self, *args):
        result = self.run_goals(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def write(self, name, data):
        self.home.mkdir(parents=True, exist_ok=True)
        text = data if isinstance(data, str) else json.dumps(data)
        (self.home / name).write_text(text)

    def goals_text(self):
        return (self.home / "goals.json").read_text()

    def assert_stopped(self, result):
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Stopped:", result.stderr)

    def test_list_with_no_goals_file_is_empty(self):
        self.assertEqual(self.ok("list"), {"goals": []})
        self.assertFalse(self.home.exists())

    def test_add_assigns_g1_then_g2(self):
        self.assertEqual(self.ok("add", "  Write slicing logic "), {"id": "g1", "text": "Write slicing logic"})
        self.assertEqual(self.ok("add", "Design SQL indexes")["id"], "g2")
        self.assertTrue(self.goals_text().endswith("\n"))
        self.assertEqual([g["id"] for g in json.loads(self.goals_text())["goals"]], ["g1", "g2"])

    def test_id_is_not_reused_after_removing_the_highest(self):
        self.ok("add", "One")
        self.ok("add", "Two")
        self.ok("remove", "g2")  # no learner.json record: last_id alone must prevent reuse
        self.assertEqual(self.ok("add", "Three")["id"], "g3")

    def test_id_skips_past_ids_that_only_learner_json_knows(self):
        self.write("learner.json", {"goals": {"g5": {"mastery": 0.3}, "other": {}, "gx": {}}})
        self.assertEqual(self.ok("add", "Fresh")["id"], "g6")

    def test_list_shows_mastery_and_defaults_to_zero(self):
        self.write("goals.json", {"goals": [{"id": "g1", "text": "A"}, {"id": "g2", "text": "B"}]})
        self.write("learner.json", {"goals": {"g1": {"mastery": 0.4, "checks": 2}}})
        self.assertEqual(self.ok("list"), {"goals": [
            {"id": "g1", "text": "A", "mastery": 0.4},
            {"id": "g2", "text": "B", "mastery": 0.0},
        ]})

    def test_edit_keeps_the_id_and_the_mastery(self):
        self.write("goals.json", {"goals": [{"id": "g1", "text": "Old"}]})
        self.write("learner.json", {"goals": {"g1": {"mastery": 0.4}}})
        self.assertEqual(self.ok("edit", "g1", "New wording"), {"id": "g1", "text": "New wording"})
        self.assertEqual(self.ok("list")["goals"], [{"id": "g1", "text": "New wording", "mastery": 0.4}])

    def test_remove_prints_the_goal_and_leaves_learner_json_alone(self):
        self.write("goals.json", {"goals": [{"id": "g1", "text": "A"}, {"id": "g2", "text": "B"}]})
        self.write("learner.json", '{"goals": {"g1": {"mastery": 0.4}}}')
        self.assertEqual(self.ok("remove", "g1"), {"id": "g1", "text": "A"})
        self.assertEqual(json.loads(self.goals_text()), {"goals": [{"id": "g2", "text": "B"}]})
        self.assertEqual((self.home / "learner.json").read_text(), '{"goals": {"g1": {"mastery": 0.4}}}')

    def test_unknown_id_fails_without_writing(self):
        self.write("goals.json", '{"goals": [{"id": "g1", "text": "A"}]}')
        for args in (("edit", "g9", "X"), ("remove", "g9")):
            self.assert_stopped(self.run_goals(*args))
        self.assertEqual(self.goals_text(), '{"goals": [{"id": "g1", "text": "A"}]}')

    def test_unreadable_goals_file_is_never_overwritten(self):
        for broken in ("{not json", "[1, 2]", '{"goals": "oops"}'):
            self.write("goals.json", broken)
            for args in (("add", "X"), ("edit", "g1", "X"), ("remove", "g1"), ("list",)):
                result = self.run_goals(*args)
                self.assert_stopped(result)
                self.assertIn("Nothing was changed.", result.stderr)
            self.assertEqual(self.goals_text(), broken)

    def test_other_keys_and_extra_goal_fields_are_preserved(self):
        self.write("goals.json", {"version": 2, "goals": [{"id": "g1", "text": "A", "note": "keep"}]})
        self.ok("add", "B")
        self.ok("edit", "g1", "A2")
        data = json.loads(self.goals_text())
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["last_id"], 2)
        self.assertEqual(data["goals"][0], {"id": "g1", "text": "A2", "note": "keep"})

    def test_bad_text_is_rejected_without_writing(self):
        self.write("goals.json", '{"goals": [{"id": "g1", "text": "Slicing Logic"}]}')
        for args in (("add", "   "), ("add", "two\nlines"), ("add", "  slicing logic "),
                     ("edit", "g1", ""), ("edit", "g1", "a\r\nb")):
            self.assert_stopped(self.run_goals(*args))
        self.assertEqual(self.goals_text(), '{"goals": [{"id": "g1", "text": "Slicing Logic"}]}')

    def test_edit_to_another_goals_text_is_rejected_but_own_text_is_fine(self):
        self.write("goals.json", {"goals": [{"id": "g1", "text": "A"}, {"id": "g2", "text": "B"}]})
        self.assert_stopped(self.run_goals("edit", "g2", "a"))
        self.assertEqual(self.ok("edit", "g1", "a"), {"id": "g1", "text": "a"})

    def test_usage_errors_exit_nonzero(self):
        for args in ((), ("bogus",), ("add",), ("add", "a", "b"), ("edit", "g1"), ("remove",), ("list", "x")):
            result = self.run_goals(*args)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Usage:", result.stderr)

    def test_works_from_an_apm_style_layout(self):
        shutil.copytree(SKILL, self.tmp / "project" / ".claude" / "skills" / "fathom-goals")
        self.script = self.tmp / "project" / ".claude" / "skills" / "fathom-goals" / "fathom_goals.py"
        self.assertEqual(self.ok("add", "From APM")["id"], "g1")
        self.assertEqual(self.ok("list")["goals"][0]["text"], "From APM")


if __name__ == "__main__":
    unittest.main()
