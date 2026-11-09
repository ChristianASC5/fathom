# APM compatibility

Fathom's predict move works after an `apm install`. The Partner output style does not come along, and neither does anything else that depends on Claude Code loading Fathom as a plugin.

Tested on 2026-11-09 with APM 0.35.0 and Claude Code 2.1.319, project scope, `--target claude`. User scope, `apm install -g`, is untested.

## Why the two installs differ

Claude Code's own installer registers Fathom as a plugin and runs it from a cache folder. APM does something else. It reads the plugin folder, copies the parts it understands into the project's `.claude/` folder, and merges the hooks into `.claude/settings.json`. Claude Code never learns that a plugin exists.

## What happened in the test

| Part of Fathom | After `apm install` |
| --- | --- |
| Hooks | Merged into `.claude/settings.json`. The `if` rules survive. |
| Hook scripts | Copied to `.claude/hooks/fathom/scripts/`, with `${CLAUDE_PLUGIN_ROOT}` in each hook command rewritten to that path. |
| Predict move | Works. Claude Code denied the test run, asked the question, recorded the answer and ran the tests. |
| Data directory | `CLAUDE_PLUGIN_DATA` is not set, so Fathom falls back to `~/.claude/fathom/`. |
| Partner output style | Not installed. APM has no output style type and skips the `output-styles/` folder. |
| Skills | Fathom ships none yet. A sample skill landed at `.claude/skills/goals/`, so it would be `/goals` and not `/fathom:goals`. APM left a `${CLAUDE_PLUGIN_ROOT}` reference inside the skill text unchanged, where it points at nothing. |
| Plugin options | Fathom declares none yet. APM does not read `userConfig` from `plugin.json`, going by its source. I did not test this. |

Two more things to know.

Hooks installed this way belong to the project's settings file. Disabling a plugin in Claude Code does not turn them off. `apm uninstall` removes them.

APM also copies the whole repository into the consumer's `apm_modules/` folder, tests included. The consumer's own `pytest` run collected Fathom's sandbox test and stopped with a collection error. That is why the sandbox test file is named `check_chunks.py`, which pytest ignores by default.

## Rules Fathom follows because of this

- Scripts find the data directory through `fathom_runtime.data_dir()`, which has the fallback. Nothing reads `CLAUDE_PLUGIN_DATA` directly.
- Scripts import their helpers from their own folder and never read `CLAUDE_PLUGIN_ROOT` at run time.
- A move carries its instructions in the hook's own output, so it works without the Partner output style.
- No file under `tests/` may match pytest's default patterns unless it passes in any project.

## What full compatibility would still need

- A stand-in for the output style. A SessionStart hook could inject the Partner instructions as context when Fathom is not running as a plugin. The text would have to live beside the hook scripts, because APM does not copy `output-styles/`.
- A config file in the data directory, to replace plugin options.
- Skill names that are safe without the `fathom:` prefix, such as `fathom-goals`, and no `${CLAUDE_PLUGIN_ROOT}` in skill text.
