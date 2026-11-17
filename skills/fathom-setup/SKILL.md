---
name: fathom-setup
description: Finish a Fathom install that did not go through Claude Code's plugin system, such as an APM install.
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/fathom_setup.py *)
---

Run `python3 ${CLAUDE_SKILL_DIR}/fathom_setup.py install` and relay what it printed to the user.

If the script stops with an error, show the error and end there. The user repairs their settings file themselves.
