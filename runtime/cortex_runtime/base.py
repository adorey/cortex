"""Where a project's base is — ADR-008 §3.6, amending ADR-002 §3.4.

A project that uses the ``cortex`` binary holds no spec: its ``cortex.toml`` pins a version, and
the spec of that version is in the store, ``{CORTEX_HOME}/versions/{version}``. The runtime reads
the store itself — never ``spec`` in ``cortex.local.toml``, a path of the developer's machine that
the runtime's container does not see. A project without ``cortex.toml`` keeps its base where it
always was, ``{root}/cortex``.

``cortex.toml`` is read with the core's grammar, the one ``cortex sync`` reads it with: a file one
refuses, the other refuses too.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from cortex_core import project


@dataclass(frozen=True)
class Pin:
    """What a project's ``cortex.toml`` says the runtime needs: the version, and the team's theme."""

    version: str
    theme: str

    def to_job(self) -> dict:
        return {"version": self.version, "theme": self.theme}

    @classmethod
    def from_job(cls, data: Optional[Mapping[str, Any]]) -> Optional["Pin"]:
        return None if data is None else cls(version=data["version"], theme=data["theme"])


def cortex_home() -> Path:
    home = os.environ.get("CORTEX_HOME")
    return Path(home) if home else Path.home() / ".cortex"


def read_pin(root: Path) -> Optional[Pin]:
    """The version and theme the project at ``root`` pins, or ``None`` when it has no
    ``cortex.toml``.

    Raises ``ValueError`` — a ``422`` at the API — for a ``cortex.toml`` that is not one.
    """
    path = Path(root) / project.PROJECT_FILE
    if not os.path.lexists(path):
        return None
    if not path.is_file():
        raise ValueError(f"{project.PROJECT_FILE} of this workspace is not a file")
    try:
        data = tomllib.loads(path.read_bytes().decode("utf-8-sig"))
        project.check_project(data)
    except OSError as error:
        raise ValueError(f"{project.PROJECT_FILE} of this workspace cannot be read: {error.strerror or error}")
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"{project.PROJECT_FILE} of this workspace cannot be read: {error}")
    except project.ProjectFileError as error:
        raise ValueError(f"{error} — cortex sync refuses this file too")
    return Pin(version=data["version"], theme=data["theme"])


def base_for(pin: Optional[Pin]) -> Optional[Path]:
    """The store's copy of the pinned version, or ``None`` — the default ``{root}/cortex`` —
    without a pin.

    Raises ``ValueError`` when the store does not hold that version: the run would otherwise
    resolve against no spec at all.
    """
    if pin is None:
        return None
    base = cortex_home() / "versions" / pin.version
    if not (base / "agents").is_dir():
        raise ValueError(f"this workspace uses Cortex {pin.version}, which is not in the store the runtime reads "
                         f"({cortex_home()}/versions): run `cortex sync` in the project, and mount the store "
                         "— CORTEX_STORE_PATH in deploy/.env")
    return base


def base_root_for(root: Path) -> Optional[Path]:
    """The base of the project at ``root``, as its ``cortex.toml`` says now."""
    return base_for(read_pin(root))
