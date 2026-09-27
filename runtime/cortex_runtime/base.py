"""Where a project's base is — ADR-008 §3.6, amending ADR-002 §3.4.

A project that uses the ``cortex`` binary holds no spec: its ``cortex.toml`` pins a version, and
the spec of that version is in the store, ``{CORTEX_HOME}/versions/{version}``. The runtime reads
the store itself — never ``spec`` in ``cortex.local.toml``, a path of the developer's machine that
the runtime's container does not see. A project without ``cortex.toml`` keeps its base where it
always was, ``{root}/cortex``.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Optional

PROJECT_FILE = "cortex.toml"
# A version names a directory of the store: X.Y.Z, or a pre-release — never a path.
_VERSION = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")


def cortex_home() -> Path:
    home = os.environ.get("CORTEX_HOME")
    return Path(home) if home else Path.home() / ".cortex"


def base_root_for(root: Path) -> Optional[Path]:
    """The base of the project at ``root``: the store's copy of the version its ``cortex.toml``
    pins, or ``None`` — the default ``{root}/cortex`` — when it has none.

    Raises ``ValueError`` — a ``422`` at the API — when ``cortex.toml`` names no usable version,
    or one the store does not hold: the run would otherwise resolve against no spec at all.
    """
    path = Path(root) / PROJECT_FILE
    if not path.is_file():
        return None
    try:
        data = tomllib.loads(path.read_bytes().decode("utf-8-sig"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"{PROJECT_FILE} of this workspace cannot be read: {error}")
    version = data.get("version")
    if not isinstance(version, str) or not _VERSION.match(version):
        raise ValueError(f"{PROJECT_FILE} of this workspace pins no Cortex version (got {version!r})")
    base = cortex_home() / "versions" / version
    if not base.is_dir():
        raise ValueError(f"this workspace uses Cortex {version}, which is not in the store the runtime reads "
                         f"({cortex_home()}/versions): run `cortex sync` in the project, and mount the store "
                         "— CORTEX_STORE_PATH in deploy/.env")
    return base
