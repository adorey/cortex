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
import contextlib
import errno
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, TextIO, Tuple

from cortex_core.validate import shown

from . import claude, config, store
from .paths import display, working_directory

LINK = "cortex"
MARKER = ".synced"
MARKER_NOTE = "A read-only copy of the Cortex spec, written by `cortex sync`: run it again to change this copy, never edit it."
STAGING = ".cortex-sync-"


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


def is_checkout(path: Path) -> bool:
    """A checkout of Cortex holds the spec's three trees — ``--from`` copies or links all three."""
    return all((path / tree).is_dir() for tree in store.SPEC_TREES)


def _digest(path: Path) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _files(root: Path) -> Dict[str, Path]:
    return {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file() and p.name != MARKER}


def read_marker(copy: Path) -> Optional[dict]:
    """The ``.synced`` marker of a copy sync made — ``None`` when it is none: the version it copied
    (``None`` for a checkout), the checkout (``from``), and the digest of every file it wrote."""
    try:
        marker = json.loads((copy / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(marker, dict) or not isinstance(marker.get("files"), dict):
        return None
    return marker


def synced_version(copy: Path) -> Optional[str]:
    marker = read_marker(copy)
    return marker.get("version") if marker else None


def changed_files(copy: Path, marker: dict) -> List[str]:
    """What the copy holds that sync did not write: a file added since, or modified."""
    written = marker["files"]
    return sorted(rel for rel, path in _files(copy).items() if written.get(rel) != _digest(path))


def missing_files(copy: Path, marker: dict) -> List[str]:
    """What sync wrote in the copy and is no longer there."""
    return sorted(rel for rel in marker["files"] if not (copy / rel).is_file())


def _gitdir(path: Path) -> Optional[str]:
    """The repository a ``.git`` file names — a submodule's, or a worktree's — absolute."""
    try:
        text = (path / ".git").read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    if not text.startswith("gitdir:"):
        return None
    return os.path.normpath(os.path.join(path, text[len("gitdir:"):].strip()))


def is_submodule(path: Path) -> bool:
    """``.gitmodules`` has a ``path = cortex``: a submodule, whether its repository is under the
    superproject's ``.git/modules/`` or, as older git made them, in the ``.git`` it holds."""
    try:
        lines = (path.parent / ".gitmodules").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    for line in lines:
        key, _, value = line.partition("=")
        if key.strip() == "path" and value.strip().strip('"').rstrip("/") == path.name:
            return True
    return False


OLD_THEME_MARKER = "agents/personalities/.active-*"     # the theme the scripts chose, before 1.0.0


def only_submodule(path: Path) -> bool:
    """``.gitmodules`` holds this submodule and no other: once it is removed, the file is left
    empty, and still tracked."""
    try:
        lines = (path.parent / ".gitmodules").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    paths = {value.strip().strip('"').rstrip("/") for key, _, value in (line.partition("=") for line in lines)
             if key.strip() == "path"}
    return paths == {path.name}


def _git(root: str, *args: str) -> Optional[subprocess.CompletedProcess]:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        return subprocess.run([git, "-C", root, *args], capture_output=True, encoding="utf-8", errors="replace",
                              timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None


def in_index(path: Path) -> Optional[bool]:
    """Whether the project's index still holds ``cortex`` as a submodule — mode 160000 — as the
    migrator's does until the removal is committed. ``False`` once a pull brought the removal:
    git dropped the entry and left the rest. ``None`` without a repository, or git, to ask."""
    proc = _git(str(path.parent), "ls-files", "--stage", "--", path.name)
    if proc is None or proc.returncode != 0:
        return None
    return proc.stdout.startswith("160000 ")


def _top_and_prefix(root: str) -> Optional[Tuple[str, str]]:
    """The top of the repository the project is in, and the project's place in it, as git says."""
    proc = _git(root, "rev-parse", "--show-toplevel", "--show-prefix")
    if proc is None or proc.returncode != 0 or not proc.stdout.strip():
        return None
    top, _, rest = proc.stdout.partition("\n")
    return top, rest.split("\n", 1)[0]


def submodule_name(path: Path) -> str:
    """The name of the submodule at ``cortex/`` — its section in ``.gitmodules``, at the top of the
    repository, read by git — or, without one, the name ``git submodule add`` gives: its path there."""
    where = _top_and_prefix(str(path.parent))
    if where is not None:
        top, prefix = where
        proc = _git(top, "config", "-f", ".gitmodules", "-z", "--get-regexp", r"^submodule\..*\.path$")
        names = [key[len("submodule."):-len(".path")]
                 for key, _, value in (entry.partition("\n") for entry in
                                       (proc.stdout.split("\0") if proc is not None and proc.returncode == 0 else []))
                 if value.rstrip("/") == prefix + path.name]
        return names[-1] if names else prefix + path.name          # two sections with that path: git takes the last
    # Without git: the project's .gitmodules, read as git reads it — a header in any case, a comment
    # after it, and no section left open by a header of another kind.
    try:
        lines = (path.parent / ".gitmodules").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return path.name
    name, found = None, path.name
    for line in lines:
        if line.lstrip().startswith("["):
            section = re.fullmatch(r'\s*\[submodule\s+"(.+)"\s*\]\s*(?:[#;].*)?', line, flags=re.I)
            name = section.group(1) if section else None
            continue
        key, _, value = line.partition("=")
        if name and key.strip().lower() == "path" and value.strip().strip('"').rstrip("/") == path.name:
            found = name
    return found


def _named_in_gitmodules(path: Path) -> bool:
    """``.gitmodules`` gives the name the submodule at ``cortex/`` would have to another path: a
    submodule moved with ``git mv``, which owns the settings — ``cortex/`` is then a clone of its own."""
    where = _top_and_prefix(str(path.parent))
    if where is None:
        return False
    top, prefix = where
    proc = _git(top, "config", "-f", ".gitmodules", "--get", f"submodule.{submodule_name(path)}.path")
    return proc is not None and proc.returncode == 0 and proc.stdout.strip().rstrip("/") != prefix + path.name


def _left_by_submodule(path: Path) -> bool:
    """A ``cortex/`` whose repository is its own ``.git`` directory, in a project whose settings still
    hold the submodule: the one ``git submodule add`` was run on, as a clone, once a pull removed it."""
    if not (path / ".git").is_dir() or _named_in_gitmodules(path):
        return False
    section = _git(str(path.parent), "config", "--local", "--get-regexp",
                   rf"^submodule\.{re.escape(submodule_name(path))}\.")
    return section is not None and section.returncode == 0 and bool(section.stdout.strip())


def _staged(path: Path) -> bool:
    """The index holds for ``cortex`` what the last commit does not — a submodule never committed, or a
    new commit of it staged: ``git rm`` refuses it without ``-f``, even once ``deinit`` emptied it. git rm
    sees it whatever ``submodule.<name>.ignore`` or ``diff.ignoreSubmodules`` says, and so does this."""
    proc = _git(str(path.parent), "diff", "--cached", "--quiet", "--ignore-submodules=none", "--", path.name)
    return proc is not None and proc.returncode != 0


def _plain_name(name: str) -> bool:
    """A name git takes for a submodule — it ignores one with a ``..`` in its path — and that can be
    printed in a command as it is: no control character (#85)."""
    return bool(name) and ".." not in re.split(r"[/\\]", name) and shown(name) == name


def _absorbed(path: Path) -> Tuple[str, str, str]:
    """The submodule's name, where ``git submodule absorbgitdirs`` moves a repository kept in
    ``cortex/.git`` — ``modules/<name>``, under ``.git/worktrees/<worktree>/`` in a linked worktree —
    and that ``modules/``."""
    name = submodule_name(path)
    # --git-path answers relative to the directory git runs in, its real one — undoing a .. on the
    # side of a link would land elsewhere — or absolute in a linked worktree; git older than 2.31
    # knows no --path-format, and would print it back.
    proc = _git(str(path.parent), "rev-parse", "--git-path", "modules")
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        modules = os.path.normpath(os.path.join(os.path.realpath(str(path.parent)), proc.stdout.strip()))
    else:
        modules = os.path.normpath(os.path.join(str(path.parent), ".git", "modules"))
    return name, os.path.normpath(modules + os.sep + name), modules     # as git joins it: an absolute name too


def _empty_directory(path: str) -> bool:
    """An empty directory, no link: git moves a repository onto it, as rename does."""
    try:
        return os.path.isdir(path) and not os.path.islink(path) and not os.listdir(path)
    except OSError:
        return False


def _stuck(name: str, target: str, modules: str) -> str:
    """Why git cannot move a repository kept in ``cortex/.git`` under ``modules/`` — so that the
    commands removing the submodule would fail — or nothing."""
    if not _plain_name(name) or not target.startswith(modules + os.sep):
        return (f"Its repository is in {LINK}/.git, and the name .gitmodules gives the submodule, "
                f'"{shown(name)}", is not one Cortex can follow under .git/modules/: git ignores a name with .. in '
                f"its path, . would make the repository .git/modules/ itself, and a control character has no "
                f"place in a command. Give the submodule another name in .gitmodules and .git/config, or remove it "
                f"by hand.")
    if os.path.lexists(target) and not _empty_directory(target):
        return (f"Its repository is in {LINK}/.git, and git moves it to {display(target)} before the submodule goes "
                f"— but a repository is there already: one an earlier submodule of that name left, as git rm does, "
                f"or another submodule's. git cannot move {LINK}/.git there, and the commands that remove the "
                f"submodule would fail. Find out whose repository that is before you touch it: another submodule "
                f"may still use it.")
    return ""


def kind_of(path: Path) -> str:
    """What is at ``cortex/`` when sync did not make it."""
    gitdir = _gitdir(path) if (path / ".git").is_file() else None
    # A worktree of another repository has an administrative directory, …/worktrees/<name>, which holds
    # commondir; a submodule's repository — under modules/, of the project or of a linked worktree of
    # it — never does, whatever its directories are called.
    if gitdir is not None and os.path.isfile(os.path.join(gitdir, "commondir")):
        return "worktree"
    if is_submodule(path) or (path / ".git").is_file() or _left_by_submodule(path):
        return "submodule"
    if (path / ".git").is_dir():
        return "clone"
    return "directory" if path.is_dir() else "file"


def describe(path: Path) -> str:
    return {"worktree": "a git worktree", "submodule": "a git submodule", "clone": "a git clone",
            "directory": "a directory", "file": "a file"}[kind_of(path)]


def quote(path: str) -> str:
    """A path as the shell the commands are shown for reads it: PowerShell on Windows."""
    if os.name == "nt":
        return "'" + path.replace("'", "''") + "'"
    return shlex.quote(path)


def _word(text: str) -> str:
    """``text`` as one word of the shell the commands are shown for, quoted only when it needs it."""
    return text if re.fullmatch(r"[\w./-]+", text) else quote(text)


def _remove_command(path: str) -> str:
    return f"Remove-Item -Recurse -Force {quote(path)}" if os.name == "nt" else f"rm -rf {quote(path)}"


def _checks(path: Path) -> str:
    """The three checks that ``cortex/`` holds nothing of the developer's, before its repository goes."""
    target = quote(display(str(path)))
    # The scripts' theme marker, ignored in every Cortex before 1.0.0 and read by nothing now: any
    # agents/personalities/.active-*, as 1.0.0's own .gitignore treats them.
    marker = quote(f":(exclude){OLD_THEME_MARKER}")
    # The reflogs keep commits no Cortex branch holds any more — rewritten or deleted upstream — and
    # --not --remotes leaves them in: the author tells them apart.
    authored = quote("--format=%h %an: %s")
    return ("Check first that it holds nothing of yours: the first command lists the files changed, added or "
            "ignored in it, the second the commits no remote branch holds — the reflog's included — and the "
            "third the stashes. The reflog also keeps commits that no Cortex branch holds any more, rewritten or "
            "deleted upstream: their author tells them from yours.\n\n"
            f"    git -C {target} status --short --ignored -- . {marker}\n"
            f"    git -C {target} log {authored} HEAD --branches --reflog --not --remotes\n"
            f"    git -C {target} stash list\n\n")


def leaving(path: Path) -> str:
    """How to leave the submodule, the worktree or the clone at ``cortex/`` (ADR-008 §3.10): the
    commands, shown and never run — they rewrite the project's git state, and the developer should
    see them first. Every path in them is absolute: they run from any directory."""
    root = display(str(path.parent))
    kind = kind_of(path)
    if kind == "submodule" and in_index(path) is False:
        # A teammate who pulled the removal: git dropped the entry, and kept the directory, the
        # submodule's repository and its settings — deinit and rm have nothing left to act on.
        gitdir = _gitdir(path)
        modules = gitdir is not None and os.path.isdir(gitdir)
        kept = modules or (path / ".git").is_dir()          # a clone made a submodule in place keeps its .git
        commands = []
        # Its name: app/cortex, for one git submodule add made in the subdirectory app of the repository.
        name = submodule_name(path)
        section = _git(root, "config", "--local", "--get-regexp", rf"^submodule\.{re.escape(name)}\.")
        if section is not None and section.returncode == 0 and section.stdout.strip():
            commands.append(f"git -C {quote(root)} config --remove-section {_word(f'submodule.{name}')}")
        commands.append(_remove_command(display(str(path))))
        if modules:
            commands.append(_remove_command(display(gitdir)))
        shown = "".join(f"    {command}\n" for command in commands)
        if kept:
            check = f"here, with the submodule's repository. {_checks(path)}"
        else:
            # The third command 1.0.0 and 1.1.0 printed — the one that ran — removed the repository.
            check = (f"here. Its repository is already gone, so git cannot show what changed in it: look through "
                     f"{LINK}/ yourself first.\n\n")
        return (f"The submodule was removed by a commit you pulled: git no longer tracks {LINK}/, and left it {check}"
                f"These commands change the project at {root}, so they are shown here, not run:\n\n{shown}\n"
                "Then run the command again. The migration guide covers it: "
                "https://github.com/xod-labs/cortex/blob/main/docs/migrating-to-the-binary.md")
    if kind == "submodule":
        # git rm refuses without -f a submodule whose index entry is not the last commit's.
        force = "-f " if in_index(path) and _staged(path) else ""
        commands = [f"git -C {quote(root)} submodule deinit -f {LINK}", f"git -C {quote(root)} rm {force}{LINK}"]
        if (path / ".git").is_dir():
            # deinit refuses a repository kept in cortex/.git before git 2.35: absorbgitdirs, there since
            # 2.12, moves it under modules/ first.
            commands.insert(0, f"git -C {quote(root)} submodule absorbgitdirs {LINK}")
        if only_submodule(path):
            # git rm empties .gitmodules of its last section, and leaves the file, tracked.
            commands.append(f"git -C {quote(root)} rm -f .gitmodules")
        # A submodule's repository stays under the superproject's .git/modules/ once it is gone — and
        # one kept in cortex/.git goes there too, moved by absorbgitdirs.
        gitdir = _gitdir(path)
        if gitdir is None and (path / ".git").is_dir():
            name, gitdir, modules = _absorbed(path)
            stuck = _stuck(name, gitdir, modules)
            if stuck:
                # A removal there could only reach another repository; the commands, only fail.
                return (f"Cortex now lives in the store, and the submodule is to go. {stuck} Then run the command "
                        "again. The migration guide covers it: "
                        "https://github.com/xod-labs/cortex/blob/main/docs/migrating-to-the-binary.md")
        if gitdir is not None:
            commands.append(_remove_command(display(gitdir)))
        shown = "".join(f"    {command}\n" for command in commands)
        # A clone made a submodule in place is the likeliest to hold the developer's own work; any
        # submodule's repository may hold some, and deinit -f throws away its changes first (#170).
        if (path / ".git").is_dir():
            own = (f"The submodule keeps its repository in {LINK}/.git, as a clone made a submodule in place does, "
                   f"and it goes with the submodule. {_checks(path)}")
        elif gitdir is not None and os.path.isdir(gitdir):
            own = f"Its repository, {display(gitdir)}, goes with the submodule. {_checks(path)}"
        else:
            own = ""
        return (f"Cortex now lives in the store, and the submodule is to go. {own}These commands rewrite the git "
                f"state of the project at {root}, so they are shown here, not run:\n\n{shown}\n"
                "Then run the command again. The migration guide covers it: "
                "https://github.com/xod-labs/cortex/blob/main/docs/migrating-to-the-binary.md")
    if kind == "worktree":
        common = os.path.dirname(os.path.dirname(_gitdir(path)))       # …/.git/worktrees/<name> → …/.git
        return (f"Cortex now lives in the store, and this worktree of {display(common)} is to go. Once you have "
                f"checked it holds nothing of yours:\n\n    git --git-dir {quote(display(common))} worktree remove "
                f"{quote(display(str(path)))}\n\nThen run the command again.")
    if kind == "clone":
        return (f"Cortex now lives in the store, and the clone is to go. {_checks(path)}"
                f"Then remove it:\n\n    {_remove_command(display(str(path)))}\n\nThen run the command again.")
    return "Move or remove it, then run the command again."


def existing_entry(target: Path, the_store: store.Store, project: config.Project) -> Optional[str]:
    """What sync made at ``cortex/`` — ``"link"``, ``"copy"`` — or ``None`` when nothing is there.
    Anything else there is refused, and so is a copy holding a file sync did not write: removing
    it would lose that file."""
    if not os.path.lexists(target):
        return None
    if is_link(target):
        pointed = link_target(target)
        if _inside(pointed, the_store.versions) or (project.spec == LINK and is_checkout(Path(pointed))):
            return "link"
        raise SyncError(f"{LINK}/ is a link to {shown(display(pointed))}, which Cortex did not make. Move or remove it, "
                        "then run the command again.")
    if target.is_dir() and not (target / ".git").exists() and (target / MARKER).is_file():
        marker = read_marker(target)
        if marker is None:
            raise SyncError(f"{LINK}/ holds a {MARKER} file Cortex cannot read: Cortex did not write this directory. "
                            "Move or remove it, then run the command again.")
        changed = changed_files(target, marker)
        if changed:
            names = "\n".join(f"    {shown(rel)}" for rel in changed[:20]) + ("\n    …" if len(changed) > 20 else "")
            raise SyncError(f"{LINK}/ is a copy Cortex made, and it holds files Cortex did not write:\n{names}\n"
                            "Overlays belong in agents/, not in the copy. Move those files out, or remove cortex/ "
                            "yourself, then run the command again.")
        return "copy"
    raise SyncError(f"{LINK}/ is {describe(target)}, which Cortex did not write. It would shadow the spec "
                    f"{config.LOCAL_FILE} names, and Cortex never deletes what it did not write.\n{leaving(target)}")


# --------------------------------------------------------------------------- #
# Making, swapping and removing the link and the copy
# --------------------------------------------------------------------------- #

def _discard(path: Path) -> None:
    """Remove a link or a copy sync made — staged, or moved aside — by what it is now, not by
    what it was when sync looked: another sync may have swapped it meanwhile."""
    if is_link(path):
        if os.name == "nt":
            os.rmdir(path)                     # a junction, or a directory link: never what it points at
        else:
            os.unlink(path)
    elif path.is_dir():
        store.remove_tree(path)
    elif os.path.lexists(path):
        os.unlink(path)


LOCK_WAIT = 120   # seconds a sync waits for another sync of the same project
# What the lock answers when another process holds it. Anything else is a file system without
# the lock: NFS emulates flock with a POSIX lock, which a read-only descriptor cannot take (EBADF).
HELD = {errno.EACCES, errno.EDEADLOCK} if os.name == "nt" else {errno.EWOULDBLOCK, errno.EAGAIN}
LEFT_LOCAL = re.compile(re.escape(config.LOCAL_FILE) + r"\.[0-9]+\.tmp")   # config.write_local_text's


def lock_path(root: Path) -> Path:
    """What the lock is taken on. On POSIX, the project's directory: nothing is written for it. On
    Windows, one file of the user's temporary directory for every project, ``cortex-sync.lock``, of
    which each project locks a byte (``lock_offset``). Not ``cortex.toml``: a file held open cannot
    be replaced on Windows, and the lock failed a ``git pull``, or an editor that saves by renaming,
    for as long as a sync ran or waited. Not a file per project either: they piled up there."""
    return root if os.name != "nt" else Path(tempfile.gettempdir()) / "cortex-sync.lock"


def lock_offset(root: Path) -> int:
    """The byte of ``cortex-sync.lock`` a project locks, drawn from its path. Two projects that
    draw the same one — one chance in 2**40 — only wait for each other."""
    key = os.path.normcase(os.path.realpath(root)).encode("utf-8", "surrogatepass")
    return int.from_bytes(hashlib.sha256(key).digest()[:5], "big")


def _try_lock(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)       # the byte at the file's position
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _take(fd: int, at: int, root: Path) -> None:
    deadline = time.monotonic() + LOCK_WAIT
    while True:
        try:
            if os.name == "nt":
                os.lseek(fd, at, os.SEEK_SET)
            _try_lock(fd)
            return
        except OSError as error:
            if error.errno not in HELD:
                raise
        if time.monotonic() > deadline:
            raise SyncError(f"another cortex sync of {display(str(root))} has run for {LOCK_WAIT} seconds — "
                            "wait for it, then run the command again")
        time.sleep(0.1)


@contextlib.contextmanager
def project_lock(root: Path, err: TextIO):
    """One sync of a project at a time on this machine: the others wait for it. Where the lock
    cannot be taken at all, the sync runs without it, and says so."""
    fd, locked = None, False
    at = lock_offset(root) if os.name == "nt" else 0
    try:
        fd = os.open(lock_path(root), os.O_RDONLY if os.name != "nt" else os.O_RDWR | os.O_CREAT)
        _take(fd, at, root)
        locked = True
    except OSError as error:
        err.write(f"warning: {display(str(root))} cannot be locked here ({error.strerror}) — a sync of this project "
                  "run at the same time is not kept out\n")
    except BaseException:
        if fd is not None:
            os.close(fd)
        raise
    try:
        yield
    finally:
        if fd is not None:
            if locked and os.name == "nt":
                # The file serves every project: its byte is freed now, not when Windows gets to it.
                import msvcrt

                with contextlib.suppress(OSError):
                    os.lseek(fd, at, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            os.close(fd)                               # which releases the lock, on every system


def tidy(root: Path) -> None:
    """Remove what an interrupted sync left beside ``cortex/`` — a staged link or copy, an old
    entry moved aside, a ``cortex.local.toml`` half written, which names this machine's paths and
    which git does not ignore. Run under the project's lock: no other sync is using them. A link
    among them names this machine's store, and `/cortex` does not keep it out of a commit."""
    left = [entry for entry in root.glob(f"{config.LOCAL_FILE}.*.tmp") if LEFT_LOCAL.fullmatch(entry.name)]
    for entry in [*root.glob(f"{STAGING}*"), *left]:
        try:
            _discard(entry)
        except OSError:
            pass


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


def _aside(root: Path) -> Path:
    return root / f"{STAGING}{os.getpid()}-{secrets.token_hex(4)}"


def stage_link(root: Path, source: Path) -> Path:
    path = _aside(root)
    make_link(path, source)
    return path


def stage_copy(root: Path, source: Path, version: Optional[str], checkout: Optional[str]) -> Path:
    """A read-only copy of ``source``'s three trees, beside ``cortex/``, with its manifest."""
    staging = Path(tempfile.mkdtemp(prefix=STAGING, dir=root))
    try:
        for tree in store.SPEC_TREES:
            # A checkout's theme marker is its developer's choice, never the project's.
            shutil.copytree(source / tree, staging / tree, ignore=shutil.ignore_patterns(".active-*"))
        marker = {"note": MARKER_NOTE, "version": version, "from": checkout,
                  "files": {rel: _digest(path) for rel, path in sorted(_files(staging).items())}}
        (staging / MARKER).write_text(json.dumps(marker, indent=1) + "\n", encoding="utf-8")
        store.make_read_only(staging)
        _unseal(staging)                       # sealed once in place: see _seal
    except BaseException:
        if staging.exists():
            store.remove_tree(staging)
        raise
    return staging


def _seal(path: Path) -> None:
    """Make a copy's own directory read-only, once it is in place. Everything in it is read-only
    already; the directory itself stays writable while it is moved, since macOS renames no
    directory its owner may not write in — Linux does."""
    if os.name != "nt" and path.is_dir() and not is_link(path):
        os.chmod(path, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


def _unseal(path: Path) -> None:
    """Let a copy's own directory be moved — see ``_seal``."""
    if os.name != "nt" and path.is_dir() and not is_link(path):
        os.chmod(path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


def swap(target: Path, new: Optional[Path], old: Optional[str]) -> Optional[Path]:
    """Put ``new`` at ``target`` — or nothing — and return what was there, moved aside, for the
    caller to remove once everything else is written. On failure, the old entry goes back —
    unless another sync put its own at ``target`` meanwhile, and ours is not needed."""
    aside = None
    if old is not None:
        aside = _aside(target.parent)
        try:
            _unseal(target)
            os.rename(target, aside)
        except FileNotFoundError as error:
            raise SyncError(RACE) from error           # taken away since sync looked at it
    if new is not None:
        try:
            os.rename(new, target)
        except OSError as error:
            # Something is at cortex/ that neither this sync put there nor moved away: another sync
            # got there first. Every system says so its own way — ENOTEMPTY, EEXIST, EACCES on macOS.
            if aside is not None:
                try:
                    os.rename(aside, target)
                    _seal(target)
                except OSError:
                    _discard(aside)
                    raise SyncError(RACE) from error
            elif os.path.lexists(target):
                raise SyncError(RACE) from error
            raise
        _seal(target)
    return aside


RACE = (f"{LINK}/ was put back while this sync ran — by another cortex sync, most likely. "
        "Run the command again.")


def unswap(target: Path, aside: Optional[Path]) -> None:
    """Undo ``swap``: what it put at ``target`` goes, what it moved aside comes back."""
    if os.path.lexists(target):
        gone = _aside(target.parent)
        _unseal(target)
        os.rename(target, gone)
        _discard(gone)
    if aside is not None:
        os.rename(aside, target)
        _seal(target)


# --------------------------------------------------------------------------- #
# The command
# --------------------------------------------------------------------------- #

def sync(cwd: str, mode: Optional[str], source: Optional[str], out: TextIO, err: TextIO,
         claude_access: Optional[bool] = None, notes: bool = True) -> None:
    """Sync the project at or above ``cwd``. ``notes`` off, what git ignores is left to the
    caller — ``cortex init`` writes .gitignore once ``cortex/`` has its final form."""
    root = config.find_project(cwd)
    if root is None:
        raise SyncError(f"no {config.PROJECT_FILE} in {display(cwd)} or above it — `cortex init` makes a directory "
                        "a Cortex project")
    with project_lock(Path(root), err):
        _sync(root, mode, source, out, err, claude_access, notes)


def _sync(root: str, mode: Optional[str], source: Optional[str], out: TextIO, err: TextIO,
          claude_access: Optional[bool], notes: bool) -> None:
    project = config.load(root)
    out.write(f"Project: {display(root)}\n")
    if claude_access is not None:
        # This developer's choice, written with spec and kept for the next syncs: cortex.local.toml's
        # wins over the team's.
        project.local_claude_access = claude_access
    mode = mode or project.sync or "store"
    the_store = store.Store()
    target = Path(root) / LINK
    tidy(Path(root))
    existing = existing_entry(target, the_store, project)

    if source is not None:
        spec_source = Path(os.path.abspath(source))
        if not is_checkout(spec_source):
            raise SyncError(f"--from {display(source)}: no Cortex checkout there — it holds no agents/, templates/ "
                            "and docs/")
        err.write(f"warning: the spec is the checkout at {display(str(spec_source))}, not Cortex {project.version}: "
                  "no version is checked (--from)\n")
    else:
        how = the_store.ensure(project.version)
        spec_source = the_store.path(project.version)
        said = {"stored": "in the store", "written": "written to the store, from this cortex",
                "downloaded": "downloaded to the store, checked against its SHA256SUMS"}[how]
        out.write(f"Cortex {project.version}: {said} — {display(str(spec_source))}\n")

    # Everything is prepared and checked before anything of the project moves: the new
    # cortex.local.toml, the new link or copy beside cortex/. Then one rename puts it in place.
    spec = display(str(spec_source)) if mode == "store" else LINK
    local_text = config.render_local(root, {"spec": spec, **({"claude_access": claude_access}
                                                             if claude_access is not None else {})},
                                     {"spec": "written by `cortex sync`"})
    keep, new = False, None
    if mode == "link":
        keep = existing == "link" and os.path.normcase(link_target(target)) == os.path.normcase(str(spec_source))
        new = None if keep else stage_link(Path(root), spec_source)
    elif mode == "copy":
        marker = read_marker(target) if existing == "copy" else None
        keep = bool(marker) and source is None and marker.get("version") == str(project.version) \
            and marker.get("from") is None
        missing = missing_files(target, marker) if keep else []
        if missing:
            keep = False
            err.write(f"note: {LINK}/ lacked {len(missing)} of the files sync copied — "
                      f"{', '.join(missing[:3])}{', …' if len(missing) > 3 else ''}: copied again\n")
        new = None if keep else stage_copy(Path(root), spec_source, None if source else str(project.version),
                                           display(str(spec_source)) if source else None)
    if keep and mode == "copy":
        _seal(target)                          # a sync cut short between its rename and the seal left it open
    try:
        aside = None if keep else swap(target, new, existing)
    except BaseException:
        if new is not None and os.path.lexists(new):
            _discard(new)
        raise
    try:
        config.write_local_text(root, local_text)
    except BaseException:
        if not keep:
            unswap(target, aside)
        raise
    if aside is not None:
        _discard(aside)

    if mode == "store":
        out.write("The spec is read where it is: nothing of it is in the project.\n")
    elif mode == "link":
        out.write(f"{LINK}/ links to {display(str(spec_source))}.\n")
    else:
        out.write(f"{LINK}/ is a read-only copy of {display(str(spec_source))}.\n")
    out.write(f'{config.LOCAL_FILE}: spec = "{spec}"\n')
    if notes:
        _notes(Path(root), mode, err)
    _claude(Path(root), project, None if mode == "copy" else spec_source, out, err)
    theme = project.active_theme
    if theme != "none" and not any((base / "agents" / "personalities" / theme).is_dir()
                                   for base in (spec_source, Path(root))):
        err.write(f'warning: theme "{theme}" is neither in the spec nor in agents/personalities/ — '
                  "the Prompt Manager would not find it\n")


def _claude(root: Path, project: config.Project, spec: Optional[Path], out: TextIO, err: TextIO) -> None:
    """Keep Claude Code's permission to read the spec without asking, when the project or the
    developer asks for it (``claude_access``) — and only the entry Cortex wrote, recorded as
    ``claude_entry``. A copy is inside the project: nothing to allow. While neither file sets
    ``claude_access``, and Cortex wrote no entry, Claude Code's settings are left alone."""
    access = project.active_claude_access
    if access is None and project.claude_entry is None:
        return
    allow = claude.entry_for(spec) if access and spec is not None else None
    try:
        said, owned = claude.update(root, allow, project.claude_entry,
                                    claude.entry_for(spec) if spec is not None else None)
    except claude.ClaudeSettingsError as error:
        err.write(f"warning: {error}\n")
        return
    if owned != project.claude_entry:
        config.write_local(str(root), {"claude_entry": owned},
                           {"claude_entry": f"written by `cortex sync` — the entry it keeps in {claude.SETTINGS}"})
    if said:
        out.write(f"{said}\n")
    elif access is False and spec is not None and claude.allows(root, claude.entry_for(spec)):
        # Off, with nothing of Cortex's to remove: an entry of the developer's still grants it.
        err.write(f"note: {claude.SETTINGS} has an entry of your own that lets Claude Code read "
                  f"{claude.entry_for(spec)} without asking — remove it there for Claude Code to ask again\n")
    if allow is not None:
        added = add_to_gitignore(root, {claude.SETTINGS: claude.SETTINGS})
        if added:
            out.write(f".gitignore: {', '.join(added)}\n")


def add_to_gitignore(root: Path, entries: Dict[str, str]) -> List[str]:
    """Add to ``.gitignore`` each line of ``entries`` whose path — its value — git does not ignore
    yet, and return them. The file keeps its bytes: its encoding, its byte order mark, its line
    endings. Without a repository to ask, a line is added unless it, or one that means the same,
    is there — and no .gitignore is created: it would keep nothing out of any commit."""
    path = root / ".gitignore"
    if not path.is_file() and ignored(root, config.LOCAL_FILE) is None:
        return []
    data = path.read_bytes() if path.is_file() else b""
    present = {line.strip().lstrip("\ufeff") for line in data.decode("utf-8", errors="replace").splitlines()}
    missing = []
    for line, probe in entries.items():
        state = ignored(root, probe)
        if state is None:                       # no repository to ask
            name = probe.rstrip("/")
            state = bool(present & ({name, f"/{name}"} | ({f"{name}/", f"/{name}/"} if probe.endswith("/") else set())))
        if not state and line not in present:
            missing.append(line)
    if missing:
        newline = b"\r\n" if b"\r\n" in data else b"\n"
        if data and not data.endswith(b"\n"):
            data += newline
        path.write_bytes(data + b"".join(line.encode("utf-8") + newline for line in missing))
    return missing


def ignored(root: Path, name: str) -> Optional[bool]:
    """Whether git ignores ``name`` in the project: asked of git when the project is a repository
    of it; ``None`` when there is no repository to ask about."""
    git = shutil.which("git")
    if git is not None:
        try:
            proc = subprocess.run([git, "-C", str(root), "check-ignore", "-q", "--", name],
                                  capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            proc = None
        if proc is not None and proc.returncode in (0, 1):
            return proc.returncode == 0
        if proc is not None:
            return None                                    # no repository here
    if not (root / ".git").exists():
        return None
    # No git to ask: .gitignore's own lines. A link is a file to git — `cortex/` does not match it.
    directory = (root / name).is_dir() and not is_link(root / name)
    wanted = {name, f"/{name}"} | ({f"{name}/", f"/{name}/"} if directory else set())
    try:
        lines = (root / ".gitignore").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    return any(line.strip() in wanted for line in lines)


def _notes(root: Path, mode: str, err: TextIO) -> None:
    if mode != "store" and ignored(root, LINK) is False:
        err.write(f"note: git does not ignore {LINK}/ — add a `/{LINK}` line to .gitignore, without the final slash: "
                  "a link is a file to git\n")
    if ignored(root, config.LOCAL_FILE) is False:
        err.write(f"note: git does not ignore {config.LOCAL_FILE}, which holds this machine's paths — add it to "
                  ".gitignore\n")


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
    access = parser.add_mutually_exclusive_group()
    access.add_argument("--claude-access", dest="claude_access", action="store_const", const=True,
                        help="let Claude Code read the spec without asking, from now on, for you: "
                             "claude_access = true in cortex.local.toml")
    access.add_argument("--no-claude-access", dest="claude_access", action="store_const", const=False,
                        help="stop it: claude_access = false in cortex.local.toml")
    options = parser.parse_args(args)
    try:
        sync(working_directory(), options.mode, options.source, sys.stdout, sys.stderr, options.claude_access)
    except (config.ConfigError, store.StoreError, SyncError) as error:
        return failed("cortex sync", str(error))
    except OSError as error:
        return failed("cortex sync", os_error(error))
    except subprocess.CalledProcessError as error:
        return failed("cortex sync", f"{' '.join(map(str, error.cmd))} failed: "
                                     f"{(error.stderr or b'').decode(errors='replace').strip() or error.returncode}")
    return 0


def os_error(error: OSError) -> str:
    """An OSError as the user reads it: what failed, on which path."""
    paths = [display(str(p)) for p in (error.filename, error.filename2) if p]
    return f"{error.strerror or error}" + (f": {' → '.join(paths)}" if paths else "")


def failed(command: str, message: str, code: int = 1) -> int:
    sys.stdout.flush()
    sys.stderr.write(f"{command}: {message}\n")
    return code
