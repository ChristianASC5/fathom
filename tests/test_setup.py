"""Run fathom_setup.py from the folder layouts each installer leaves behind."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "fathom-setup"


class SetupTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "fathom-home"
        self.user_claude = self.tmp / "user" / ".claude"
        self.env = {**os.environ, "FATHOM_HOME": str(self.home), "CLAUDE_CONFIG_DIR": str(self.user_claude)}

    def unpack_into(self, claude_dir):
        """Copy the skill the way APM does: into <claude_dir>/skills/, with no plugin manifest."""
        shutil.copytree(SKILL, claude_dir / "skills" / "fathom-setup")
        return claude_dir / "skills" / "fathom-setup" / "fathom_setup.py"

    def run_setup(self, script, *args):
        return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, env=self.env)

    def test_install_adds_the_style_and_selects_it_for_the_project(self):
        claude = self.tmp / "project" / ".claude"
        script = self.unpack_into(claude)
        (claude / "settings.local.json").write_text(json.dumps({"permissions": {"allow": ["Read"]}}))

        result = self.run_setup(script, "install")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((claude / "output-styles" / "fathom-partner.md").read_text(), (SKILL / "partner.md").read_text())
        settings = json.loads((claude / "settings.local.json").read_text())
        self.assertEqual(settings, {"permissions": {"allow": ["Read"]}, "outputStyle": "Partner"})
        self.assertFalse((claude / "settings.json").exists())
        self.assertIn("new Claude Code session", result.stdout)

    def test_install_at_user_level_writes_the_shared_settings_file(self):
        script = self.unpack_into(self.user_claude)
        self.run_setup(script, "install")
        self.assertEqual(json.loads((self.user_claude / "settings.json").read_text()), {"outputStyle": "Partner"})

    def test_remove_restores_the_style_the_user_had_even_after_two_installs(self):
        claude = self.tmp / "project" / ".claude"
        script = self.unpack_into(claude)
        (claude / "settings.local.json").write_text(json.dumps({"outputStyle": "Explanatory"}))
        self.run_setup(script, "install")
        self.run_setup(script, "install")

        result = self.run_setup(script, "remove")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((claude / "settings.local.json").read_text()), {"outputStyle": "Explanatory"})
        self.assertFalse((claude / "output-styles" / "fathom-partner.md").exists())

    def test_remove_clears_the_choice_when_there_was_no_earlier_style(self):
        claude = self.tmp / "project" / ".claude"
        script = self.unpack_into(claude)
        self.run_setup(script, "install")
        self.run_setup(script, "remove")
        self.assertEqual(json.loads((claude / "settings.local.json").read_text()), {})
        self.assertFalse((claude / "output-styles").exists())

    def test_remove_leaves_a_style_the_user_picked_after_setup(self):
        claude = self.tmp / "project" / ".claude"
        script = self.unpack_into(claude)
        self.run_setup(script, "install")
        (claude / "settings.local.json").write_text(json.dumps({"outputStyle": "Concise"}))
        self.run_setup(script, "remove")
        self.assertEqual(json.loads((claude / "settings.local.json").read_text()), {"outputStyle": "Concise"})

    def test_remove_keeps_learning_history_unless_asked_to_delete_it(self):
        claude = self.tmp / "project" / ".claude"
        script = self.unpack_into(claude)
        self.run_setup(script, "install")
        (self.home / "events.jsonl").write_text("{}\n")

        kept = self.run_setup(script, "remove")
        self.assertTrue((self.home / "events.jsonl").exists())
        self.assertIn("Kept your learning history", kept.stdout)

        deleted = self.run_setup(script, "remove", "--delete-data")
        self.assertFalse(self.home.exists())
        self.assertIn("Deleted your learning history", deleted.stdout)

    def test_install_stops_before_changing_anything_when_settings_are_broken(self):
        claude = self.tmp / "project" / ".claude"
        script = self.unpack_into(claude)
        (claude / "settings.local.json").write_text("{not json")

        result = self.run_setup(script, "install")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Nothing was changed", result.stderr)
        self.assertEqual((claude / "settings.local.json").read_text(), "{not json")
        self.assertFalse((claude / "output-styles").exists())

    def test_as_a_plugin_install_changes_nothing_and_remove_only_touches_history(self):
        script = SKILL / "fathom_setup.py"  # the repo itself has the plugin layout

        installed = self.run_setup(script, "install")
        self.assertIn("Nothing to set up", installed.stdout)
        self.assertFalse((REPO / "output-styles" / "fathom-partner.md").exists())

        removed = self.run_setup(script, "remove", "--delete-data")
        self.assertIn("claude plugin uninstall fathom", removed.stdout)
        self.assertFalse(self.home.exists())
        self.assertTrue((REPO / "output-styles" / "partner.md").exists())

    def test_the_skill_carries_the_same_style_text_the_plugin_ships(self):
        self.assertEqual((SKILL / "partner.md").read_text(), (REPO / "output-styles" / "partner.md").read_text())


if __name__ == "__main__":
    unittest.main()
