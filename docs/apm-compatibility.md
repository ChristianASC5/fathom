# APM compatibility

Fathom works after an `apm install`, with one extra step. Run `/fathom-setup` once to add the Partner output style, which APM cannot install.

Tested on 2026-11-10 with APM 0.35.0 and Claude Code 2.1.319, project scope, `--target claude`. User scope, `apm install -g`, is untested.

## Why the two installs differ

Claude Code's own installer registers Fathom as a plugin and runs it from a cache folder. APM does something else. It reads the plugin folder, copies the parts it understands into the project's `.claude/` folder, and merges the hooks into `.claude/settings.json`. Claude Code never learns that a plugin exists.

## What happened in the test

| Part of Fathom | After `apm install` |
| --- | --- |
| Hooks | Merged into `.claude/settings.json`. The `if` rules survive. |
| Hook scripts | Copied to `.claude/hooks/fathom/scripts/`, with `${CLAUDE_PLUGIN_ROOT}` in each hook command rewritten to that path. |
| Predict move | Worked in the 0.0.2 test. That move has since been replaced by the edit trigger. |
| Data | In `~/.fathom`, the same folder a plugin install uses. |
| Skills | Copied to `.claude/skills/`, each with the files in its folder. They are `/fathom-setup` and `/fathom-uninstall`, without the `fathom:` prefix a plugin gives them. |
| Partner output style | Not installed. APM has no output style type and skips the `output-styles/` folder. `/fathom-setup` adds it. |

## Hooks added in 0.0.3

The hooks now use a `Stop` event and a `PreToolUse` matcher for file edits (`Write|Edit|MultiEdit|NotebookEdit`). APM should merge them into `.claude/settings.json` the same way as before, but this is untested. The edit trigger also calls `claude` to classify the work, so `claude` must be on your PATH.

## Skill added in 0.0.4

`/fathom-goals` manages the goals in `~/.fathom/goals.json`. It follows the same rules as the other skills: its script sits in its own folder, and a unit test runs it from an APM-style `.claude/skills/` layout. A real APM install has not been tested yet.

## What `/fathom-setup` does

It runs `skills/fathom-setup/fathom_setup.py install`, which works out how Fathom was installed from where the script sits.

As a plugin, it changes nothing. The plugin already has the output style.

After an APM install, it copies the Partner style to `.claude/output-styles/fathom-partner.md` and sets `outputStyle` to `Partner`. For a project that goes in `.claude/settings.local.json`, the file git ignores. For a user-level install it goes in `~/.claude/settings.json`. It records the output style you had before in `~/.fathom/installs.json`.

`/fathom-uninstall` deletes the style file and puts your previous output style back. If you picked a different style after setup, it leaves your choice alone.

In the test, a new session in the APM project reported `Partner` as its output style and followed the style's instructions.

## Things to know

Hooks installed by APM belong to the project's settings file. Disabling a plugin in Claude Code does not turn them off. `apm uninstall` removes them.

APM copies the whole repository into the consumer's `apm_modules/` folder, tests included. The consumer's own `pytest` run collected Fathom's sandbox test and stopped with a collection error. That is why the sandbox test file is named `check_chunks.py`, which pytest ignores by default.

`apm install <local folder>` refuses a checkout that contains `tests/sandbox/.venv`, because the virtualenv holds symlinks that point outside the folder. Install from GitHub, or from a copy without the virtualenv.

## Rules Fathom follows because of this

- Everything Fathom writes goes to `~/.fathom`. Scripts never use `CLAUDE_PLUGIN_DATA`, which only a plugin gets.
- Scripts import their helpers from their own folder and never read `CLAUDE_PLUGIN_ROOT` at run time.
- A skill keeps the files it needs in its own folder and reaches them through `${CLAUDE_SKILL_DIR}`. That is why the Partner style exists twice, in `output-styles/` for the plugin and in `skills/fathom-setup/` for setup. A unit test fails if the two copies differ.
- Skill names start with `fathom-`, so they are safe without the plugin prefix.
- A move carries its instructions in the hook's own output, so it works before setup has added the output style.
- No file under `tests/` may match pytest's default patterns unless it passes in any project.
