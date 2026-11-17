#!/usr/bin/env python3
"""Finish or undo a Fathom install that did not go through Claude Code's plugin system.

Claude Code's own installer gives Fathom everything it needs. Installers that
unpack a plugin into a .claude/ folder (APM does this) leave out the Partner
output style, because only a plugin can ship one. `install` adds the style to
that same .claude/ folder and selects it. `remove` undoes that, and with
--delete-data also deletes the learning history in ~/.fathom.
"""
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent  # the folder that holds skills/
STYLE_SOURCE = HERE / "partner.md"
STYLE_NAME = "Partner"  # the `name` in partner.md's frontmatter
USAGE = "Usage: fathom_setup.py install\n       fathom_setup.py remove [--delete-data]"


def fathom_home() -> Path:
    return Path(os.environ.get("FATHOM_HOME") or os.path.expanduser("~/.fathom"))


def install_kind() -> str:
    if (ROOT / ".claude-plugin" / "plugin.json").exists():
        return "plugin"
    if HERE.parent.name == "skills":
        return "unpacked"
    return "unknown"


def settings_file() -> Path:
    """Where Claude Code keeps one person's choices for the .claude/ folder at ROOT."""
    user_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"))
    if ROOT == user_dir.resolve():
        return ROOT / "settings.json"
    return ROOT / "settings.local.json"  # project folder: the file git ignores


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except ValueError as error:
        sys.exit(f"Stopped: {path} is not valid JSON ({error}). Nothing was changed.")
    if not isinstance(data, dict):
        sys.exit(f"Stopped: {path} does not hold a JSON object. Nothing was changed.")
    return data


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def style_file() -> Path:
    return ROOT / "output-styles" / "fathom-partner.md"


def records_file() -> Path:
    """Remembers the output style each .claude/ folder had selected before setup."""
    return fathom_home() / "installs.json"


def install() -> None:
    home = fathom_home()
    home.mkdir(parents=True, exist_ok=True)
    kind = install_kind()
    if kind == "plugin":
        print("Fathom is running as a Claude Code plugin, which already includes the "
              "Partner output style. Nothing to set up.")
        print(f"Learning history: {home}")
        return
    if kind == "unknown":
        sys.exit(f"Stopped: {HERE} is not inside a skills/ folder, so there is no "
                 ".claude/ folder to set up. Nothing was changed.")

    settings_path = settings_file()
    settings = read_json(settings_path)
    records = read_json(records_file())

    style_file().parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(STYLE_SOURCE, style_file())

    previous = settings.get("outputStyle")
    if previous != STYLE_NAME:
        # Recorded once, so running setup twice can't forget the user's own style.
        records[str(ROOT)] = {"previous_output_style": previous}
        write_json(records_file(), records)
        settings["outputStyle"] = STYLE_NAME
        write_json(settings_path, settings)

    print(f"Added the Partner output style: {style_file()}")
    print(f"Selected it in: {settings_path}")
    if previous not in (None, STYLE_NAME):
        print(f"Your previous output style, {previous!r}, comes back when you run fathom-uninstall.")
    print(f"Learning history: {home}")
    print("Start a new Claude Code session for the output style to take effect.")


def remove(delete_data: bool) -> None:
    kind = install_kind()
    if kind == "unpacked":
        settings_path = settings_file()
        settings = read_json(settings_path)
        records = read_json(records_file())
        record = records.pop(str(ROOT), {})

        if style_file().exists():
            style_file().unlink()
            if not any(style_file().parent.iterdir()):
                style_file().parent.rmdir()  # setup created it; leave nothing behind
            print(f"Removed the Partner output style: {style_file()}")
        if settings.get("outputStyle") == STYLE_NAME:
            previous = record.get("previous_output_style")
            if previous:
                settings["outputStyle"] = previous
                print(f"Restored your previous output style, {previous!r}, in {settings_path}")
            else:
                del settings["outputStyle"]
                print(f"Cleared the output style choice in {settings_path}")
            write_json(settings_path, settings)
        if records_file().exists():
            write_json(records_file(), records)

    home = fathom_home()
    if delete_data and home.exists():
        shutil.rmtree(home)
        print(f"Deleted your learning history: {home}")
    elif home.exists():
        print(f"Kept your learning history: {home}")

    if kind == "plugin":
        print("To remove Fathom itself, run: claude plugin uninstall fathom")
    else:
        print("To remove Fathom itself, use the installer that added it. "
              "For APM: apm uninstall ChristianASC5/fathom")


def main() -> None:
    args = sys.argv[1:]
    if args == ["install"]:
        install()
    elif args and args[0] == "remove" and set(args[1:]) <= {"--delete-data"}:
        remove(delete_data="--delete-data" in args)
    else:
        sys.exit(USAGE)


if __name__ == "__main__":
    main()
