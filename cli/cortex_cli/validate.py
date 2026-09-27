"""``cortex validate`` — ADR-007's validator, run by the command (ADR-008 §3.8).

Same checks, same report, same exit codes as ``bin/validate-overlays.sh``: the options are the
core's own, and the core parses them. The command only says which two roots it validates:

- in a project — the nearest directory holding ``cortex.toml`` — the project root, and the spec
  ``cortex.local.toml`` names: the pinned version, or a checkout ``cortex sync --from`` gave;
- in a project that has not moved to ``cortex.toml`` yet, the ``cortex/`` directory of the
  current directory — where a submodule puts the spec, and where the script found it;
- in a checkout of Cortex, the checkout itself: the base as its own project (ADR-007 §3.1).

A project whose spec is missing, or synced for another version than the one ``cortex.toml`` pins,
is not validated: it would be checked against a spec it does not use.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple

from cortex_core import validate

from . import config, store, sync
from .paths import display, working_directory


class RootsError(Exception):
    pass


def _synced_version(project: config.Project, base: str) -> str:
    """The version the spec at ``base`` is, when sync says so — ``""`` for a checkout."""
    link = Path(project.root) / sync.LINK
    if project.spec == sync.LINK and sync.is_link(link):
        base = sync.link_target(link)
    elif project.spec == sync.LINK and (link / sync.MARKER).is_file():
        return sync.synced_version(link) or ""
    versions = store.cortex_home() / "versions"
    try:
        relative = Path(os.path.realpath(base)).relative_to(os.path.realpath(versions))
    except ValueError:
        return ""
    return relative.parts[0] if len(relative.parts) == 1 else ""


def roots(cwd: str) -> Tuple[str, str]:
    """The project root and the base root to validate from ``cwd``."""
    root = config.find_project(cwd)
    if root is not None:
        try:
            project = config.load(root)
        except config.ConfigError as error:
            raise RootsError(str(error))
        base = project.spec_directory()
        if base is None:
            raise RootsError(f"{config.LOCAL_FILE} names no spec yet — run `cortex sync`")
        if not os.path.isdir(base):
            raise RootsError(f"the spec {config.LOCAL_FILE} names, {display(base)}, is not there — run `cortex sync`")
        synced = _synced_version(project, base)
        if synced and synced != str(project.version):
            raise RootsError(f"{config.PROJECT_FILE} pins Cortex {project.version}, and the spec synced is {synced} "
                             "— run `cortex sync`")
        return root, base
    if os.path.isdir(os.path.join(cwd, "cortex")):
        return cwd, f"{cwd}/cortex"
    if sync.is_checkout(Path(cwd)) and os.path.isfile(os.path.join(cwd, "templates", "bootstrap-instructions.md")):
        return cwd, cwd
    raise RootsError(f"no {config.PROJECT_FILE} in {display(cwd)} or above it — `cortex init` makes a directory a "
                     "Cortex project")


def run(args: List[str]) -> int:
    if any(arg in ("-h", "--help") for arg in args):
        return validate.main(args, project_root=".", base_root="cortex", prog="cortex validate")
    try:
        project_root, base_root = roots(working_directory())
    except RootsError as error:
        import sys

        sys.stderr.write(f"cortex validate: {error}\n")
        return 2
    return validate.main(args, project_root=project_root, base_root=base_root, prog="cortex validate")
