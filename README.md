# Fathom

Fathom is a Claude Code plugin that keeps you learning while an agent does the work. At a few points in a task it hands you a decision or a check to make yourself, then tells you how your answer held up.

The research on AI and learning points one way. People who hand the thinking to an AI finish faster and learn less. In [one randomized trial](https://econpapers.repec.org/RePEc:nas:journl:v:122:y:2025:p:e2422633122), students with unrestricted GPT-4 scored 17% worse on exams they took without it. People who use AI to understand keep what they learn. Fathom pushes you toward the second habit, inside the work you were already doing.

## Status

Early. The moves work, and you set your goals by editing a file.

**The trigger.** Any file edit by Claude can start a move. Fathom first checks that you have goals, that you are not in ship mode, and that you have not used up the day's moves. If those pass, it asks Claude Haiku once per task which of your goals the work exercises. If none does, nothing happens and the edit goes through.

**Approach, before the edit.** If you have shown some mastery of the goal and the task has a real design choice, Fathom holds the first edit and has Claude ask you to pick the approach. Claude then builds the one you picked.

**Check, after the edit.** Otherwise Claude finishes the work, then asks one question about whether the change does what was needed. Your answer is judged Held or Missed, and that moves your mastery of the goal.

Fathom asks at most once per prompt. If you skip, or the session can't show you a question, the work carries on.

## Goals and settings

Until setup has a skill for it, write your goals by hand in `~/.fathom/goals.json`:

```json
{"goals": [{"id": "g1", "text": "Write and debug Python list and slicing logic"}]}
```

With no goals, Fathom does nothing. Optional settings go in `~/.fathom/config.json`:

| Key | Default | Meaning |
| --- | --- | --- |
| `mode` | `learn` | `ship` turns every move off. |
| `moves_per_day` | `3` | Moves Fathom offers per day, counted across all sessions. |
| `mastery_threshold` | `0.5` | Mastery of a goal at which Fathom switches from Check to Approach moves. |

## Install

```sh
claude plugin install fathom --marketplace ChristianASC5/fathom
```

You need `python3` on your PATH. I have only tested Python 3.14.

Installing Fathom turns on its output style, Partner, and that replaces any output style you had selected. Disable the plugin to get yours back.

### With APM

```sh
apm install ChristianASC5/fathom --target claude
```

APM copies Fathom's hooks and skills into your project's `.claude/` folder and never loads it as a plugin. The moves work straight away. The Partner output style is missing, because only a plugin can ship one. Run `/fathom-setup` once in Claude Code to add it, then start a new session.

[docs/apm-compatibility.md](docs/apm-compatibility.md) has the details.

## Uninstall

Run `/fathom:fathom-uninstall` first. After an APM install the command is `/fathom-uninstall`. It asks whether to delete your learning history, undoes what setup changed, and prints the command that removes Fathom itself.

Removing the plugin on its own leaves `~/.fathom` in place.

## What Fathom stores

Fathom keeps its files on your machine, in `~/.fathom`, whichever way you installed. Set `FATHOM_HOME` to keep the folder somewhere else.

| File | Holds |
| --- | --- |
| `goals.json` | Your goals, as you wrote them. |
| `config.json` | Your settings. Optional. |
| `learner.json` | A mastery score and a check count for each goal. |
| `events.jsonl` | One line per event: a timestamp, the move, what happened, the goal id, and the label of the option you picked. Never your prompts, your code, or the question text. |
| `state/` | Which move each session is in the middle of. |
| `installs.json` | Written by `/fathom-setup`. The output style each `.claude/` folder had before setup changed it, so uninstall can put it back. |

## Privacy

When you have goals and a task edits a file, Fathom runs your own `claude` CLI with Claude Haiku, once per task. The call sends your goal statements, the prompts of the session so far, the names of the tools Claude used with their file paths or commands, and the pending edit, up to 4,000 characters. It goes to the same provider your session already uses. Fathom stores none of it. The classifier's reasoning is discarded too, and only the goal id, the confidence, whether there was a real choice and the call's duration reach the event log.

Setting `FATHOM_DEBUG=1` breaks the no-content rule on purpose. It writes the raw input of every hook, prompts and commands included, to `debug-hook-inputs.jsonl` in the same folder. It is off unless you set it.

## Development

The unit tests run the hook scripts the way Claude Code does, with JSON on stdin. They need nothing but Python.

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

To watch the moves in a real session, put goals in `~/.fathom/goals.json`, start Claude Code in the sandbox project and ask it to change `chunks.py`.

```sh
cd tests/sandbox
claude --plugin-dir ../..
```

`tests/harness/run-headless` does the same with no human present, in a throwaway copy of the sandbox. A test-only hook answers each question, and Fathom's data goes to a throwaway folder seeded with `tests/harness/goals.json`. `AUTO_PICK` chooses which option an Approach question takes, and `FATHOM_SEED_MASTERY="g3=0.6"` starts a goal with mastery so the Approach move fires. It needs `claude`, `jq` and `uv`, and each run spends real tokens on the session and on the classifier.

```sh
FATHOM_SEED_MASTERY="g3=0.6" tests/harness/run-headless 'Add input validation to chunks.py.' run.jsonl
```

## License

MIT. See [LICENSE](LICENSE).
