# Fathom

Fathom is a Claude Code plugin that keeps you learning while an agent does the work. At a few points in a task it hands you a decision or a prediction to make yourself, then tells you how your answer held up.

The research on AI and learning points one way. People who hand the thinking to an AI finish faster and learn less. In [one randomized trial](https://econpapers.repec.org/RePEc:nas:journl:v:122:y:2025:p:e2422633122), students with unrestricted GPT-4 scored 17% worse on exams they took without it. People who use AI to understand keep what they learn. Fathom pushes you toward the second habit, inside the work you were already doing.

## Status

Early. One move works today, and it only knows about `pytest`.

**Predict, then run.** The first time Claude runs `pytest` after you send a prompt, Fathom holds the command and has Claude ask what you expect to happen. You pick an outcome in one click. The tests run, and Claude tells you in one line whether you were right. If you were wrong, it explains the gap in three sentences or fewer.

Fathom asks once per prompt. If you skip, or if the session can't show you a question, the tests run anyway.

Learning goals, more moves, and scaffolding that fades as you improve are designed and not built yet.

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

This works, with limits. APM copies Fathom's hooks into your project's `.claude/` folder and never loads it as a plugin, so you get the predict move without the Partner output style. [docs/apm-compatibility.md](docs/apm-compatibility.md) has the details.

## What Fathom stores

Everything stays on your machine. Fathom makes no network calls.

It keeps one log, `events.jsonl`, in the data directory Claude Code gives the plugin under `~/.claude/plugins/data/`. Each line holds a timestamp, the move, what happened, and the label of the option you picked. It never holds your prompts, your code, or the question text.

Setting `FATHOM_DEBUG=1` breaks that rule on purpose. It writes the raw input of every hook, prompts and commands included, to `debug-hook-inputs.jsonl` in the same directory. It is off unless you set it.

## Development

The unit tests run the hook scripts the way Claude Code does, with JSON on stdin. They need nothing but Python.

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

To watch the move in a real session, start Claude Code in the sandbox project and ask it to run the tests. One of the three sandbox tests fails on purpose, so a prediction can be wrong.

```sh
cd tests/sandbox
claude --plugin-dir ../..
```

`tests/harness/run-headless` does the same with no human present. A test-only hook picks the first option of every question. It needs `claude`, `jq` and `uv`, and each run costs about five cents on Sonnet.

```sh
tests/harness/run-headless 'Run the test suite with `pytest -q` and tell me the result.' run.jsonl
```

## License

MIT. See [LICENSE](LICENSE).
