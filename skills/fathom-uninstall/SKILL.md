---
name: fathom-uninstall
description: Undo Fathom's setup, and optionally delete your learning history in ~/.fathom.
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/../fathom-setup/fathom_setup.py *)
---

1. Ask the user whether to also delete their learning history in `~/.fathom`. Keeping it is the default. Deleting it cannot be undone.
2. Run `python3 ${CLAUDE_SKILL_DIR}/../fathom-setup/fathom_setup.py remove`. Add `--delete-data` only when the user chose to delete.
3. Relay what the script printed. Its last line is the command that removes Fathom itself, which the user runs on their own.
