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
from cortex_core.project import shown

from . import config, store, sync
from .paths import display, working_directory


class RootsError(Exception):
    pass


def _synced_version(project: config.Project, base: str) -> str:
    """The version the spec at ``base`` is, when that is known — ``""`` for a checkout.

    A copy's marker says it. Otherwise the spec is the store's, read in place or through a link:
    a directory of some ``versions/``, whichever ``CORTEX_HOME`` it was synced with — a sync made
    with another home is still checked against the version pinned.
    """
    link = Path(project.root) / sync.LINK
    if project.spec == sync.LINK and sync.is_link(link):
        base = sync.link_target(link)
    elif project.spec == sync.LINK and (link / sync.MARKER).is_file():
        marker = sync.read_marker(link)
        return (marker.get("version") or "") if marker else ""
    resolved = Path(os.path.realpath(base))
    return resolved.name if resolved.parent.name == "versions" and store.Version.valid(resolved.name) else ""


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
            raise RootsError(f"the spec {config.LOCAL_FILE} names, {shown(display(base))}, is not there — run `cortex sync`")
        synced = _synced_version(project, base)
        if synced and synced != str(project.version):
            raise RootsError(f"{config.PROJECT_FILE} pins Cortex {project.version}, and the spec synced is {shown(synced)} "
                             "— run `cortex sync`")
        copy = Path(project.root) / sync.LINK
        marker = sync.read_marker(copy) if project.spec == sync.LINK and not sync.is_link(copy) else None
        if marker is not None:
            off = sync.changed_files(copy, marker) + sync.missing_files(copy, marker)
            if off:
                raise RootsError(f"{sync.LINK}/ no longer holds what sync copied — {len(off)} file(s) added, changed "
                                 f"or missing, {off[0]} first: it would be validated against another spec. "
                                 "Run `cortex sync`, which says what to do")
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
        return sync.failed("cortex validate", str(error), 2)
    except OSError as error:
        return sync.failed("cortex validate", sync.os_error(error), 2)
    return validate.main(args, project_root=project_root, base_root=base_root, prog="cortex validate")
