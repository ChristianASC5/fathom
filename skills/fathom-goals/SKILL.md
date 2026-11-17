---
name: fathom-goals
description: Create, change or delete the user's Fathom learning goals. Use when the user asks to add, reword, replace or remove a goal, or to see their goals.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/fathom_goals.py *)
---

Fathom asks the user learning questions tied to their goals. This skill manages those goals.

1. Run `python3 ${CLAUDE_SKILL_DIR}/fathom_goals.py list` and show the user their goals with their mastery.
2. Change only what the user asked for. Before any add, edit or remove, show the exact final wording, or the goal to delete, and wait for the user's yes. Never write on your own initiative.
3. Run one of these, then tell the user what changed.
   - `python3 ${CLAUDE_SKILL_DIR}/fathom_goals.py add '<text>'`
   - `python3 ${CLAUDE_SKILL_DIR}/fathom_goals.py edit <id> '<text>'`
   - `python3 ${CLAUDE_SKILL_DIR}/fathom_goals.py remove <id>`

Pass the goal text as one argument in single quotes. Write an embedded single quote as `'\''`.

## Sharpening a goal

A good goal names one specific skill the user wants to own, and that skill shows up in the coding work they do with Claude. For example, "Write and debug Python list and slicing logic" or "Design SQL indexes for read-heavy queries".

Push back on three kinds of goal and offer a sharper rewrite. The user decides.
- Too broad, such as "get better at Python".
- A chore, not a skill, such as "write docs".
- Several skills in one. Suggest splitting it.

Fathom's classifier matches the user's work against the goal text. A vague goal matches everything or nothing. Suggest keeping about 1 to 5 goals active.

## Edit or replace

- Rewording that keeps the same skill: use `edit`. Mastery carries over.
- A change that makes it a different skill: use `remove`, then `add`. Tell the user the new goal starts at zero mastery.

When you remove a goal, tell the user its history stays in `~/.fathom` until they run Fathom's uninstall skill and choose to delete their data.

If the script stops with an error, show the error and end there. The user fixes the file themselves.
