#!/usr/bin/env python3
"""Read and change the learning goals in ~/.fathom/goals.json.

`list` prints the goals with their mastery. `add`, `edit` and `remove` change
goals.json and print the goal they touched. Goal ids are never reused, because a
removed goal's mastery and events stay in ~/.fathom and a new goal must not
inherit them. goals.json records the highest number issued as "last_id".
"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

USAGE = ("Usage: fathom_goals.py list\n"
         "       fathom_goals.py add <text>\n"
         "       fathom_goals.py edit <id> <text>\n"
         "       fathom_goals.py remove <id>")
ID_PATTERN = re.compile(r"g(\d+)")


def fathom_home() -> Path:
    return Path(os.environ.get("FATHOM_HOME") or os.path.expanduser("~/.fathom"))


def goals_file() -> Path:
    return fathom_home() / "goals.json"


def read_goals_file() -> dict:
    """The whole goals.json, so a write keeps keys this script does not know about."""
    path = goals_file()
    if not path.exists():
        return {"goals": []}
    try:
        data = json.loads(path.read_text())
    except ValueError as error:
        sys.exit(f"Stopped: {path} is not valid JSON ({error}). Nothing was changed.")
    if not isinstance(data, dict):
        sys.exit(f"Stopped: {path} does not hold a JSON object. Nothing was changed.")
    if not isinstance(data.get("goals", []), list):
        sys.exit(f"Stopped: \"goals\" in {path} is not a list. Nothing was changed.")
    data.setdefault("goals", [])
    return data


def learner_goals() -> dict:
    path = fathom_home() / "learner.json"
    try:
        goals = json.loads(path.read_text()).get("goals", {})
    except (OSError, ValueError, AttributeError):
        return {}
    return goals if isinstance(goals, dict) else {}


def write_goals_file(data: dict) -> None:
    path = goals_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".goals-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w") as temp:
            temp.write(json.dumps(data, indent=2) + "\n")
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def clean_text(text: str) -> str:
    text = text.strip()
    if not text:
        sys.exit("Stopped: the goal text is empty. Nothing was changed.")
    if "\n" in text or "\r" in text:
        sys.exit("Stopped: the goal text must be one line. Nothing was changed.")
    return text


def next_number(data: dict) -> int:
    """One past the highest g<N> in goals.json, its last_id, or learner.json."""
    ids = [entry.get("id") for entry in data["goals"] if isinstance(entry, dict)]
    ids += list(learner_goals())
    numbers = [int(m.group(1)) for i in ids if isinstance(i, str) and (m := ID_PATTERN.fullmatch(i))]
    last = data.get("last_id")
    if isinstance(last, int) and not isinstance(last, bool):
        numbers.append(last)
    return max(numbers, default=0) + 1


def find(goals: list, goal_id: str) -> dict:
    for entry in goals:
        if isinstance(entry, dict) and entry.get("id") == goal_id:
            return entry
    sys.exit(f"Stopped: there is no goal with id {goal_id!r}. Nothing was changed.")


def check_not_duplicate(goals: list, text: str, own_id: str = "") -> None:
    for entry in goals:
        if (isinstance(entry, dict) and entry.get("id") != own_id
                and isinstance(entry.get("text"), str)
                and entry["text"].strip().lower() == text.lower()):
            sys.exit(f"Stopped: goal {entry.get('id')!r} already says that. Nothing was changed.")


def show(goal: dict) -> None:
    print(json.dumps(goal, indent=2))


def list_goals() -> None:
    learned = learner_goals()
    rows = []
    for entry in read_goals_file()["goals"]:
        if not (isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("text"), str)):
            continue
        record = learned.get(entry["id"])
        mastery = record.get("mastery") if isinstance(record, dict) else None
        if isinstance(mastery, bool) or not isinstance(mastery, (int, float)):
            mastery = 0.0
        rows.append({"id": entry["id"], "text": entry["text"], "mastery": mastery})
    print(json.dumps({"goals": rows}, indent=2))


def add(text: str) -> None:
    data = read_goals_file()
    text = clean_text(text)
    check_not_duplicate(data["goals"], text)
    number = next_number(data)
    goal = {"id": f"g{number}", "text": text}
    data["goals"].append(goal)
    data["last_id"] = number
    write_goals_file(data)
    show(goal)


def edit(goal_id: str, text: str) -> None:
    data = read_goals_file()
    goal = find(data["goals"], goal_id)
    text = clean_text(text)
    check_not_duplicate(data["goals"], text, own_id=goal_id)
    goal["text"] = text
    write_goals_file(data)
    show(goal)


def remove(goal_id: str) -> None:
    data = read_goals_file()
    goal = find(data["goals"], goal_id)
    data["goals"].remove(goal)
    write_goals_file(data)
    show(goal)


def main() -> None:
    args = sys.argv[1:]
    command, rest = (args[0], args[1:]) if args else ("", [])
    if command == "list" and not rest:
        list_goals()
    elif command == "add" and len(rest) == 1:
        add(*rest)
    elif command == "edit" and len(rest) == 2:
        edit(*rest)
    elif command == "remove" and len(rest) == 1:
        remove(*rest)
    else:
        sys.exit(USAGE)


if __name__ == "__main__":
    main()
