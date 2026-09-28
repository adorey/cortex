"""``cortex.toml`` and ``cortex.local.toml`` — ADR-008 §3.4.

``cortex.toml`` is committed at the project root: the Cortex ``version`` it uses, the team's
``theme``, and optionally how ``sync`` brings the spec to it. ``cortex.local.toml``, next to it and
ignored by git, is this developer on this machine: a ``theme`` of their own, and the ``spec``
``cortex sync`` writes. An unknown key is an error, never a warning: these are the files a later
ADR extends, and a typo that silently does nothing is the failure they must not start with.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass
from typing import Dict, Optional

from cortex_core import project
from cortex_core.project import LOCAL_FILE, MODES, PROJECT_FILE  # noqa: F401 — part of this module's API

from .semver import Version

PROJECT_HEADER = "# Written by `cortex init`. Committed: the Cortex version this project uses, and the team's theme.\n"
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

    @property
    def active_theme(self) -> str:
        return self.local_theme or self.theme

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


def load(root: str) -> Project:
    """Read and validate both files of the project at ``root`` — with the core's grammar, which
    the runtime reads them with too."""
    data = _read(os.path.join(root, PROJECT_FILE))
    local = {}
    try:
        project.check_project(data)
        if os.path.isfile(os.path.join(root, LOCAL_FILE)):
            local = _read(os.path.join(root, LOCAL_FILE))
            project.check_local(local)
    except project.ProjectFileError as error:
        raise ConfigError(str(error))
    return Project(root=root, version=Version(data["version"]), theme=data["theme"], sync=data.get("sync"),
                   local_theme=local.get("theme"), spec=local.get("spec"))


def toml_string(value: str) -> str:
    """``value`` as a TOML basic string — JSON's escapes are TOML's."""
    return json.dumps(value, ensure_ascii=False)


def toml_value(value) -> str:
    return ("true" if value else "false") if isinstance(value, bool) else toml_string(value)


def _read_text(path: str) -> Optional[str]:
    """The file as it is — its byte order mark too, which ``set_keys`` writes back."""
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8")
    except UnicodeDecodeError:
        raise ConfigError(f"{os.path.basename(path)}: not UTF-8 text")


def _comment(line: str, key: str) -> str:
    """The comment that ends ``line`` — with the blanks before it — or ``""``. A ``#`` inside a
    string is no comment: the comment starts at the first ``#`` before which the line reads as
    the key alone."""
    body = line.rstrip("\r\n")
    for index, char in enumerate(body):
        if char != "#":
            continue
        try:
            if key in tomllib.loads(body[:index]):
                return body[len(body[:index].rstrip()):]
        except tomllib.TOMLDecodeError:
            continue
    return ""


def set_keys(text: Optional[str], values: Dict[str, object], name: str, header: str,
             comments: Optional[Dict[str, str]] = None) -> str:
    """``text`` — the file ``name``, or ``None`` when it is not there yet — with each key of
    ``values`` set.

    ``tomllib`` reads TOML but does not write it: the one line that holds a key is rewritten, or
    added, and every other line — the developer's own keys, their comments, the file's line
    endings and byte order mark — is kept as it was, and so is the comment that ends the line
    rewritten. The result is read back: a key written some way a line cannot hold is refused.
    """
    comments = comments or {}
    if text is None:
        text = header
    bom = "\ufeff" if text.startswith("\ufeff") else ""
    text = text[len(bom):]
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines(keepends=True)
    for key, value in values.items():
        line = f"{key} = {toml_value(value)}"
        key_line = re.compile(rf"""^[ \t]*(?:{key}|"{key}"|'{key}')[ \t]*=""")
        for index, existing in enumerate(lines):
            if key_line.match(existing):
                kept = _comment(existing, key) or (f"    # {comments[key]}" if key in comments else "")
                lines[index] = line + kept + existing[len(existing.rstrip("\r\n")):]
                break
        else:
            if lines and not lines[-1].endswith(("\n", "\r")):
                lines[-1] += newline
            lines.append(line + (f"    # {comments[key]}" if key in comments else "") + newline)
    text = "".join(lines)
    try:
        written = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        written = {}
    for key, value in values.items():
        if written.get(key) != value:
            raise ConfigError(f"{name}: its {key} is written in a way cortex cannot rewrite — "
                              "remove that line and run the command again")
    return bom + text


def render_spec(root: str, spec: str) -> str:
    """``cortex.local.toml`` with ``spec`` set — computed, not written, so that sync validates it
    before it changes anything in the project."""
    return set_keys(_read_text(os.path.join(root, LOCAL_FILE)), {"spec": spec}, LOCAL_FILE, LOCAL_HEADER,
                    {"spec": "written by `cortex sync`"})


def render_project(root: str, values: Dict[str, object]) -> str:
    """``cortex.toml`` with each key of ``values`` set — a new file when there is none — checked
    against the grammar before anything is written."""
    text = set_keys(_read_text(os.path.join(root, PROJECT_FILE)), values, PROJECT_FILE, PROJECT_HEADER)
    try:
        project.check_project(tomllib.loads(text.lstrip("\ufeff")))
    except project.ProjectFileError as error:
        raise ConfigError(str(error))
    return text


def write_text(path: str, text: str) -> None:
    """Write ``text`` to ``path`` whole or not at all: a temporary file beside it, then a rename."""
    temporary = f"{path}.{os.getpid()}.tmp"
    try:
        with open(temporary, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def write_local_text(root: str, text: str) -> None:
    write_text(os.path.join(root, LOCAL_FILE), text)


def write_spec(root: str, spec: str) -> None:
    """Set ``spec`` in ``cortex.local.toml``, creating the file if needed."""
    write_local_text(root, render_spec(root, spec))
