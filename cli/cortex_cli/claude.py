"""Claude Code reads the spec without asking — on request (ADR-008 §9).

Measured in phase 2: in its default permission mode, Claude Code asks before it reads outside
the project — the store — and checks the path a link resolves to, so a link asks too. With the
spec's directory in ``permissions.additionalDirectories`` of its settings, it reads without
asking. ``claude_access = true`` — in ``cortex.toml`` for the team, in ``cortex.local.toml`` for one
developer — has ``cortex sync`` keep that entry in ``.claude/settings.local.json``: Claude Code's
settings of this developer on this machine, which git ignores, where the store's path belongs.

Every entry inside the store's ``versions/`` is Cortex's: sync replaces it when the version
changes, and removes it when access is turned off or the spec is copied into the project. The
developer's own entries, and everything else in the file, are kept as they are — an entry
written for ``cortex sync --from``, a checkout outside the store, among them.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional

from .paths import display

SETTINGS = ".claude/settings.local.json"


class ClaudeSettingsError(Exception):
    pass


def _inside(entry: str, directory: Path) -> bool:
    path = os.path.normcase(os.path.realpath(os.path.expanduser(entry)))
    return path.startswith(os.path.normcase(os.path.realpath(directory)) + os.sep)


def update(root: Path, versions: Path, allow: Optional[str]) -> Optional[str]:
    """Make ``allow`` the one directory of the store Claude Code may read without asking — none
    when ``allow`` is ``None``. Return what the file now says for the report, or ``None`` when
    nothing changed."""
    path = root / SETTINGS
    if path.is_file():
        try:
            settings = json.loads(path.read_text(encoding="utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as error:
            raise ClaudeSettingsError(f"{SETTINGS} is no JSON Claude Code can read ({error}): left as it is")
        if not isinstance(settings, dict):
            raise ClaudeSettingsError(f"{SETTINGS} holds no JSON object: left as it is")
    elif allow is None:
        return None
    else:
        settings = {}
    permissions = settings.get("permissions", {})
    entries = permissions.get("additionalDirectories", []) if isinstance(permissions, dict) else None
    if not isinstance(entries, list):
        raise ClaudeSettingsError(f"{SETTINGS}: permissions.additionalDirectories is no list: left as it is")

    kept: List = [entry for entry in entries if not (isinstance(entry, str) and _inside(entry, versions))]
    wanted = kept + ([allow] if allow is not None and allow not in kept else [])
    if wanted == entries:
        return None
    if wanted:
        permissions["additionalDirectories"] = wanted
        settings["permissions"] = permissions
    else:
        permissions.pop("additionalDirectories", None)
        if not permissions:
            settings.pop("permissions", None)
    if not settings:
        path.unlink()
        return f"{SETTINGS} removed: it held nothing but the store's path"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)
    if allow is None:
        return f"{SETTINGS}: Claude Code no longer reads the store without asking"
    return f"{SETTINGS}: Claude Code reads {display(allow)} without asking"
