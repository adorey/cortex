"""``cortex sync`` — where the project finds the spec (ADR-008 §3.5).

``cortex sync`` finds ``cortex.toml`` in the current directory or the nearest ancestor, validates
it and ``cortex.local.toml``, makes sure the pinned version is in the store, and writes ``spec``
in ``cortex.local.toml``. The spec reaches the project in one of three modes:

- ``store`` — nothing in the project: ``spec`` is the store's absolute path, and the spec is read
  where it lives;
- ``link`` — ``cortex/`` links to the store: a symbolic link on Linux and macOS, a directory
  junction on Windows, which needs no administrator right and no developer mode;
- ``copy`` — ``cortex/`` is a read-only copy, with a ``.synced`` marker naming the version.

``cortex/`` becomes a name: the directory ``spec`` names. Sync never deletes what it did not
write — a submodule, a clone, any other directory at ``cortex/`` is refused, in every mode — and
switching back to ``store`` removes the link or the copy it made, and nothing else.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, TextIO

from . import config, store
from .paths import display, working_directory

LINK = "cortex"
MARKER = ".synced"
MARKER_NOTE = "A read-only copy of the Cortex spec, written by `cortex sync`: run it again to change this copy, never edit it."


class SyncError(Exception):
    pass


# --------------------------------------------------------------------------- #
# What is at cortex/
# --------------------------------------------------------------------------- #

def is_junction(path: Path) -> bool:
    if hasattr(os.path, "isjunction"):                     # Python 3.12
        return os.path.isjunction(path)
    try:
        return getattr(os.lstat(path), "st_reparse_tag", None) == getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", -1)
    except OSError:
        return False


def is_link(path: Path) -> bool:
    return os.path.islink(path) or is_junction(path)


def link_target(path: Path) -> str:
    target = os.readlink(path)
    if target.startswith("\\\\?\\"):                        # how Windows spells a junction's target
        target = target[4:]
    return os.path.normpath(os.path.join(os.path.dirname(path), target))


def _inside(path: str, directory: Path) -> bool:
    path, directory = os.path.normcase(os.path.realpath(path)), os.path.normcase(os.path.realpath(directory))
    return path.startswith(directory + os.sep)


def synced_version(copy: Path) -> Optional[str]:
    try:
        return (copy / MARKER).read_text(encoding="utf-8").split("\n", 1)[0].strip()
    except OSError:
        return None


def describe(path: Path) -> str:
    if (path / ".git").is_file():
        return "a git submodule"
    if (path / ".git").is_dir():
        return "a git clone"
    return "a directory" if path.is_dir() else "a file"


def existing_entry(target: Path, the_store: store.Store, project: config.Project) -> Optional[str]:
    """What sync made at ``cortex/`` — ``"link"``, ``"copy"`` — or ``None`` when nothing is there.
    Anything else there is refused."""
    if not os.path.lexists(target):
        return None
    if is_link(target):
        pointed = link_target(target)
        if _inside(pointed, the_store.versions) or project.spec == LINK:
            return "link"
        raise SyncError(f"{LINK}/ is a link to {display(pointed)}, which cortex sync did not make. Move or remove it, "
                        "then run cortex sync again.")
    if target.is_dir() and (target / MARKER).is_file():
        return "copy"
    raise SyncError(f"{LINK}/ is {describe(target)}, which cortex sync did not write. It would shadow the spec "
                    f"{config.LOCAL_FILE} names, and sync never deletes what it did not write: move or remove it, "
                    "then run cortex sync again.")


# --------------------------------------------------------------------------- #
# Making and removing the link and the copy
# --------------------------------------------------------------------------- #

def remove_entry(kind: Optional[str], target: Path) -> None:
    if kind == "link":
        if os.name == "nt":
            os.rmdir(target)                   # a junction, or a directory link: never what it points at
        else:
            os.unlink(target)
    elif kind == "copy":
        store.remove_tree(target)


def make_link(target: Path, source: Path) -> None:
    if os.name != "nt":
        os.symlink(source, target, target_is_directory=True)
        return
    # A junction: no privilege, where a symbolic link needs administrator rights or developer
    # mode. _winapi is CPython's own, not public: mklink is the fallback if it goes.
    try:
        import _winapi

        _winapi.CreateJunction(str(source), str(target))
    except (ImportError, AttributeError):
        cmd = os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32", "cmd.exe")
        subprocess.run([cmd, "/c", "mklink", "/J", str(target), str(source)], check=True, capture_output=True)


def make_copy(target: Path, source: Path, label: str) -> None:
    staging = Path(tempfile.mkdtemp(prefix=".cortex-sync-", dir=target.parent))
    try:
        for tree in store.SPEC_TREES:
            shutil.copytree(source / tree, staging / tree, ignore=shutil.ignore_patterns(".active-theme"))
        (staging / MARKER).write_text(f"{label}\n{MARKER_NOTE}\n", encoding="utf-8")
        os.rename(staging, target)
    except BaseException:
        if staging.exists():
            store.remove_tree(staging)
        raise
    store.make_read_only(target)


def is_checkout(path: Path) -> bool:
    return all((path / tree).is_dir() for tree in ("agents", "templates"))


# --------------------------------------------------------------------------- #
# The command
# --------------------------------------------------------------------------- #

def sync(cwd: str, mode: Optional[str], source: Optional[str], out: TextIO, err: TextIO) -> None:
    root = config.find_project(cwd)
    if root is None:
        raise SyncError(f"no {config.PROJECT_FILE} in {display(cwd)} or above it — `cortex init` makes a directory "
                        "a Cortex project")
    project = config.load(root)
    mode = mode or project.sync or "store"
    the_store = store.Store()
    target = Path(root) / LINK
    existing = existing_entry(target, the_store, project)

    if source is not None:
        spec_source = Path(os.path.abspath(source))
        if not is_checkout(spec_source):
            raise SyncError(f"--from {display(source)}: no Cortex checkout there — it holds no agents/ and templates/")
        err.write(f"warning: the spec is the checkout at {display(str(spec_source))}, not Cortex {project.version}: "
                  "no version is checked (--from)\n")
        label = f"from {display(str(spec_source))}"
    else:
        how = the_store.ensure(project.version)
        spec_source = the_store.path(project.version)
        label = str(project.version)
        said = {"stored": "in the store", "written": "written to the store, from this cortex",
                "downloaded": "downloaded to the store, checked against its SHA256SUMS"}[how]
        out.write(f"Cortex {project.version}: {said} — {display(str(spec_source))}\n")

    if mode == "store":
        remove_entry(existing, target)
        spec = display(str(spec_source))
        out.write("The spec is read where it is: nothing of it is in the project.\n")
    elif mode == "link":
        if existing == "link" and os.path.normcase(link_target(target)) == os.path.normcase(str(spec_source)):
            pass
        else:
            remove_entry(existing, target)
            make_link(target, spec_source)
        spec = LINK
        out.write(f"{LINK}/ links to {display(str(spec_source))}.\n")
    else:
        if not (existing == "copy" and source is None and synced_version(target) == label):
            remove_entry(existing, target)
            make_copy(target, spec_source, label)
        spec = LINK
        out.write(f"{LINK}/ is a read-only copy of {display(str(spec_source))}.\n")

    config.write_spec(root, spec)
    out.write(f'{config.LOCAL_FILE}: spec = "{spec}"\n')
    if mode != "store" and not _ignored(Path(root)):
        err.write(f"note: {LINK}/ is not in {Path(root).name}/.gitignore — add a `/{LINK}/` line, so that git "
                  "does not track it\n")
    theme = project.active_theme
    if theme != "none" and not any((base / "agents" / "personalities" / theme).is_dir()
                                   for base in (spec_source, Path(root))):
        err.write(f'warning: theme "{theme}" is neither in the spec nor in agents/personalities/ — '
                  "the Prompt Manager would not find it\n")


def _ignored(root: Path) -> bool:
    try:
        lines = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    return any(line.strip() in (LINK, f"{LINK}/", f"/{LINK}", f"/{LINK}/") for line in lines)


def run(args: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cortex sync",
        description="Put the Cortex version cortex.toml pins in the store, and tell the project where it is "
                    "(spec, in cortex.local.toml). ADR-008 §3.5.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--store", dest="mode", action="store_const", const="store",
                       help="read the spec where it is, in the store (the default)")
    modes.add_argument("--link", dest="mode", action="store_const", const="link",
                       help="link cortex/ to it: a symbolic link, a junction on Windows")
    modes.add_argument("--copy", dest="mode", action="store_const", const="copy",
                       help="copy it into cortex/, read-only")
    parser.add_argument("--from", dest="source", metavar="PATH",
                        help="use a checkout of Cortex instead of the store: no version is checked")
    options = parser.parse_args(args)
    try:
        sync(working_directory(), options.mode, options.source, sys.stdout, sys.stderr)
    except (config.ConfigError, store.StoreError, SyncError) as error:
        sys.stdout.flush()
        sys.stderr.write(f"cortex sync: {error}\n")
        return 1
    return 0
