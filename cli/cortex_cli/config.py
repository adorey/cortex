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

_SPEC_LINE = re.compile(r"""^[ \t]*(?:spec|"spec"|'spec')[ \t]*=""")
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


def render_spec(root: str, spec: str) -> str:
    """``cortex.local.toml`` with ``spec`` set — computed, not written, so that sync validates it
    before it changes anything in the project.

    ``tomllib`` reads TOML but does not write it: the one line that holds ``spec`` is rewritten,
    or added, and every other line — the developer's ``theme``, their comments — is kept as it
    was. The result is read back: a ``spec`` written some way a line cannot hold is refused.
    """
    path = os.path.join(root, LOCAL_FILE)
    line = f"spec = {toml_string(spec)}    # written by `cortex sync`"
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8-sig")
        newline = "\r\n" if "\r\n" in text else "\n"
        lines = text.splitlines(keepends=True)
        for index, existing in enumerate(lines):
            if _SPEC_LINE.match(existing):
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
    if written.get("spec") != spec:
        raise ConfigError(f"{LOCAL_FILE}: its spec is written in a way cortex sync cannot rewrite — "
                          "remove that line and run cortex sync again")
    return text


def write_local_text(root: str, text: str) -> None:
    path = os.path.join(root, LOCAL_FILE)
    temporary = f"{path}.{os.getpid()}.tmp"
    with open(temporary, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    os.replace(temporary, path)


def write_spec(root: str, spec: str) -> None:
    """Set ``spec`` in ``cortex.local.toml``, creating the file if needed."""
    write_local_text(root, render_spec(root, spec))
