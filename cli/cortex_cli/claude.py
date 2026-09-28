"""Claude Code reads the spec without asking — on request (ADR-008 §9).

Measured in phase 2: in its default permission mode, Claude Code asks before it reads outside
the project — the store — and checks the path a link resolves to, so a link asks too. With the
spec's directory in ``permissions.additionalDirectories`` of its settings, it reads without
asking. ``claude_access = true`` — in ``cortex.toml`` for the team, in ``cortex.local.toml`` for one
developer — has ``cortex sync`` keep that entry in ``.claude/settings.local.json``: Claude Code's
settings of this developer on this machine, which git ignores, where the store's path belongs.

Cortex owns one entry of that file, the one it wrote — ``claude_entry`` in ``cortex.local.toml``
records it — and no other. It replaces that entry when the spec moves, and removes it when access
is turned off or the spec is copied into the project. An entry the developer wrote, by hand or by
answering Claude Code's own prompt, is theirs, even when it names the store; and while neither
file sets ``claude_access``, sync does not touch the file at all.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

from .paths import display

SETTINGS = ".claude/settings.local.json"


class ClaudeSettingsError(Exception):
    pass


def entry_for(spec: Path) -> str:
    """The entry that lets Claude Code read ``spec``: the path it resolves to, which is the one
    Claude Code checks."""
    return display(os.path.realpath(spec))


def _same(entry: object, path: str) -> bool:
    if not isinstance(entry, str):
        return False
    return os.path.normcase(os.path.realpath(os.path.expanduser(entry))) == \
        os.path.normcase(os.path.realpath(os.path.expanduser(path)))


def _format(text: str) -> Tuple[bool, str, object, bool]:
    """How the file is written — its byte order mark, line ending, indent, final newline — to
    write it back the same way."""
    bom = text.startswith("\ufeff")
    newline = "\r\n" if "\r\n" in text else "\n"
    match = re.search(r"\n([ \t]+)\S", text)
    indent: object = 2
    if match:
        indent = "\t" if match.group(1).startswith("\t") else len(match.group(1))
    elif text.strip() and "\n" not in text.strip():
        indent = None                                   # all on one line
    return bom, newline, indent, text.endswith(("\n", "\r"))


def allows(root: Path, path: str) -> bool:
    """Whether an entry of the settings lets Claude Code read ``path`` — ``False`` when the file
    cannot be read: nothing is said of a file sync cannot read."""
    try:
        settings = json.loads((root / SETTINGS).read_bytes().decode("utf-8").lstrip("\ufeff"))
        entries = settings.get("permissions", {}).get("additionalDirectories", [])
    except (OSError, ValueError, AttributeError):
        return False
    return isinstance(entries, list) and any(_same(entry, path) for entry in entries)


def update(root: Path, allow: Optional[str], owned: Optional[str],
           spec: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Make ``allow`` — or nothing, when it is ``None`` — the entry Cortex keeps in the file.
    ``owned`` is the entry Cortex wrote before, the only one it may remove. ``spec``, the entry
    of the spec synced, tells whether an entry of the developer's still lets Claude Code read it.

    Return what to report — ``None`` when nothing changed — and the entry Cortex now owns: ``allow``
    when it wrote it or had written it, ``None`` when the developer's own entry already allows it.
    """
    path = root / SETTINGS
    real = Path(os.path.realpath(path))                  # a link — to a dotfiles repository — is written through
    try:
        text = real.read_bytes().decode("utf-8") if real.is_file() else None   # line endings as they are
    except (OSError, UnicodeDecodeError) as error:
        raise ClaudeSettingsError(f"{SETTINGS} cannot be read ({error}): left as it is")
    if text is None:
        if os.path.lexists(path) and not real.exists():
            pass                                         # a dangling link: its target is created
        elif os.path.lexists(path):
            raise ClaudeSettingsError(f"{SETTINGS} is no file: left as it is")
        if allow is None:
            return None, None
        settings: dict = {}
    else:
        try:
            settings = json.loads(text.lstrip("\ufeff"))
        except ValueError as error:
            raise ClaudeSettingsError(f"{SETTINGS} is no JSON Claude Code can read ({error}): left as it is")
        if not isinstance(settings, dict):
            raise ClaudeSettingsError(f"{SETTINGS} holds no JSON object: left as it is")
    permissions = settings.get("permissions", {})
    entries = permissions.get("additionalDirectories", []) if isinstance(permissions, dict) else None
    if not isinstance(entries, list):
        raise ClaudeSettingsError(f"{SETTINGS}: permissions.additionalDirectories is no list: left as it is")

    # The entry Cortex wrote is the string it wrote: an entry of the developer's that leads to the
    # same directory — `~/…`, a trailing slash — is theirs, and stays.
    keep_owned = owned is not None and owned == allow
    kept: List = [entry for entry in entries if keep_owned or entry != owned]
    if allow is not None and any(_same(entry, allow) for entry in kept):
        now_owned = owned if keep_owned else None        # already allowed — by Cortex before, or by the developer
    elif allow is not None:
        kept.append(allow)
        now_owned = allow
    else:
        now_owned = None
    if kept == entries:
        return None, now_owned
    if kept:
        permissions["additionalDirectories"] = kept
        settings["permissions"] = permissions
    else:
        permissions.pop("additionalDirectories", None)
        if not permissions:
            settings.pop("permissions", None)

    bom, newline, indent, final = _format(text) if text is not None else (False, "\n", 2, True)
    written = json.dumps(settings, indent=indent, ensure_ascii=False)
    written = ("\ufeff" if bom else "") + written.replace("\n", newline) + (newline if final else "")
    try:
        real.parent.mkdir(parents=True, exist_ok=True)
        temporary = real.with_name(f"{real.name}.{os.getpid()}.tmp")
        with open(temporary, "w", encoding="utf-8", newline="") as fh:
            fh.write(written)
        os.replace(temporary, real)
    except OSError as error:
        raise ClaudeSettingsError(f"{SETTINGS} cannot be written ({error.strerror or error}): left as it is")
    if allow is None:
        if spec is not None and any(_same(entry, spec) for entry in kept):
            return (f"{SETTINGS}: the entry cortex sync wrote is removed — an entry of your own still lets "
                    f"Claude Code read {display(spec)} without asking"), None
        return f"{SETTINGS}: Claude Code no longer reads the spec without asking", None
    return f"{SETTINGS}: Claude Code reads {display(allow)} without asking", now_owned
