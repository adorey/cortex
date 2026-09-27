"""``cortex.toml`` and ``cortex.local.toml`` — ADR-008 §3.4.

``cortex.toml`` is committed at the project root: the Cortex ``version`` it uses, the team's
``theme``, and optionally how ``sync`` brings the spec to it and whether Claude Code may read it
without asking (``claude_access``). ``cortex.local.toml``, next to it and ignored by git, is this
developer on this machine: a ``theme`` and a ``claude_access`` of their own, and the ``spec``
``cortex sync`` writes. An unknown key is an error, never a warning: these are the files a later
ADR extends, and a typo that silently does nothing is the failure they must not start with.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from .semver import Version

PROJECT_FILE = "cortex.toml"
LOCAL_FILE = "cortex.local.toml"
MODES = ("store", "link", "copy")
# A theme names a directory: a name, never a path.
_THEME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
PROJECT_KEYS = ("version", "theme", "sync", "claude_access")
LOCAL_KEYS = ("theme", "spec", "claude_access")
BOOLEAN_KEYS = ("claude_access",)
LOCAL_HEADER = ("# This developer, on this machine — ignored by git (ADR-008 §3.4).\n"
                "# `cortex sync` writes spec. A theme set here overrides cortex.toml's.\n")


class ConfigError(Exception):
    """A configuration file cortex refuses — the message names the file and the key."""


@dataclass
class Project:
    root: str                  # the directory holding cortex.toml, as the shell names it
    version: Version
    theme: str
    sync: Optional[str]        # cortex.toml's sync, when set
    local_theme: Optional[str]
    spec: Optional[str]        # cortex.local.toml's spec, when synced
    claude_access: bool = False                 # cortex.toml's
    local_claude_access: Optional[bool] = None  # cortex.local.toml's, which wins

    @property
    def active_theme(self) -> str:
        return self.local_theme or self.theme

    @property
    def active_claude_access(self) -> bool:
        return self.claude_access if self.local_claude_access is None else self.local_claude_access

    def spec_directory(self) -> Optional[str]:
        """The directory ``spec`` names: absolute as written, or relative to the project root."""
        if self.spec is None:
            return None
        spec = self.spec
        return spec if os.path.isabs(spec) else f"{self.root}/{spec}"


def find_project(start: str) -> Optional[str]:
    """The directory holding ``cortex.toml``: ``start`` or its nearest ancestor that does."""
    current = start
    while True:
        if os.path.isfile(os.path.join(current, PROJECT_FILE)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _read(path: str) -> Dict:
    try:
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8-sig")    # a byte order mark, as Notepad writes one
    except UnicodeDecodeError:
        raise ConfigError(f"{os.path.basename(path)}: not UTF-8 text")
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{os.path.basename(path)}: {error}")


def _check_keys(name: str, data: Dict, allowed: Tuple[str, ...], required: Tuple[str, ...]) -> None:
    for key in data:
        if key not in allowed:
            raise ConfigError(f'{name}: unknown key "{key}" — {name} takes {_listed(allowed)}'
                              + (" only" if name == LOCAL_FILE else ""))
    for key in required:
        if key not in data:
            raise ConfigError(f'{name}: "{key}" is required')
    for key, value in data.items():
        if key in BOOLEAN_KEYS:
            if not isinstance(value, bool):
                raise ConfigError(f'{name}: "{key}" must be true or false, without quotes')
            continue
        if not isinstance(value, str):
            raise ConfigError(f'{name}: "{key}" must be a string, in quotes')
        if not value:
            raise ConfigError(f'{name}: "{key}" is empty')


def _listed(keys: Tuple[str, ...]) -> str:
    return ", ".join(keys[:-1]) + f" and {keys[-1]}" if len(keys) > 1 else keys[0]


def _check_theme(name: str, theme: str) -> None:
    if not _THEME.match(theme):
        raise ConfigError(f'{name}: theme "{theme}" is no theme name — letters, digits, ".", "_" and "-"')


def load(root: str) -> Project:
    """Read and validate both files of the project at ``root``."""
    data = _read(os.path.join(root, PROJECT_FILE))
    _check_keys(PROJECT_FILE, data, PROJECT_KEYS, ("version", "theme"))
    if not Version.valid(data["version"]):
        raise ConfigError(f'{PROJECT_FILE}: version "{data["version"]}" is no version — X.Y.Z, for instance 1.0.0')
    _check_theme(PROJECT_FILE, data["theme"])
    if "sync" in data and data["sync"] not in MODES:
        raise ConfigError(f'{PROJECT_FILE}: sync "{data["sync"]}" is none of {_listed(MODES)}')
    local = {}
    if os.path.isfile(os.path.join(root, LOCAL_FILE)):
        local = _read(os.path.join(root, LOCAL_FILE))
        _check_keys(LOCAL_FILE, local, LOCAL_KEYS, ())
        if "theme" in local:
            _check_theme(LOCAL_FILE, local["theme"])
    return Project(root=root, version=Version(data["version"]), theme=data["theme"], sync=data.get("sync"),
                   local_theme=local.get("theme"), spec=local.get("spec"),
                   claude_access=data.get("claude_access", False), local_claude_access=local.get("claude_access"))


def toml_string(value: str) -> str:
    """``value`` as a TOML basic string — JSON's escapes are TOML's."""
    return json.dumps(value, ensure_ascii=False)


def write_spec(root: str, spec: str) -> None:
    """Set ``spec`` in ``cortex.local.toml`` — see ``write_local``."""
    write_local(root, "spec", spec, "written by `cortex sync`")


def write_local(root: str, key: str, value, comment: str = "") -> None:
    """Set ``key`` in ``cortex.local.toml``, creating the file if needed.

    ``tomllib`` reads TOML but does not write it: the one line that holds ``key`` is rewritten,
    or added, and every other line — the developer's ``theme``, their comments — is kept as it
    was. The result is read back: a value written some way a line cannot hold is refused.
    """
    path = os.path.join(root, LOCAL_FILE)
    rendered = ("true" if value else "false") if isinstance(value, bool) else toml_string(value)
    line = f"{key} = {rendered}" + (f"    # {comment}" if comment else "")
    key_line = re.compile(rf"""^[ \t]*(?:{key}|"{key}"|'{key}')[ \t]*=""")
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8-sig")
        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines(keepends=True)
        for index, existing in enumerate(lines):
            if key_line.match(existing):
                ending = existing[len(existing.rstrip("\r\n")):]
                lines[index] = line + ending
                break
        else:
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += newline
            lines.append(line + newline)
        text = "".join(lines)
    else:
        text = LOCAL_HEADER + line + "\n"
    try:
        written = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        written = {}
    if written.get(key) != value:
        raise ConfigError(f"{LOCAL_FILE}: its {key} is written in a way cortex sync cannot rewrite — "
                          "remove that line and run cortex sync again")
    temporary = f"{path}.{os.getpid()}.tmp"
    with open(temporary, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(temporary, path)
