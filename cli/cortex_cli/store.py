"""The store — ``~/.cortex/versions/X.Y.Z``, one read-only directory per version (ADR-008 §3.3).

A version directory holds the three trees the IDE's LLM and the runtime read — ``agents/``,
``templates/``, ``docs/`` — and nothing else. It is filled on demand: the binary's own version
from the spec archive it embeds, with no network; any other from its release's spec archive,
checked against the release's ``SHA256SUMS``. Once written it is read-only, so that an edit of
the spec, through any project, fails instead of changing every project on that version.

A version is written beside its final place and renamed into it: an interrupted write never
leaves a half-written version, and two syncs writing the same one at once both end with it. A
version is there only when its three trees are, and read-only: one left writable by an interrupted
sync is made read-only again, and a staging left behind for a day is removed.

A download is checked against ``SHA256SUMS``, which comes from where the archive does: that
proves it whole, not who published it. A built binary also carries the checksum of every spec
archive released before it, taken when it was built: a spec archive of those versions replaced
since — a release overwritten — is refused, whatever its ``SHA256SUMS`` says.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, Optional

from . import net
from .semver import FIRST_SPEC_ARCHIVE, Version
from .version import VERSION

SPEC_TREES = ("agents", "templates", "docs")
SPEC_ARCHIVE = "cortex-spec.tar.gz"
DEFAULT_RELEASES_URL = "https://github.com/adorey/cortex/releases"
# The largest spec archive and SHA256SUMS a download accepts: a version is under a megabyte.
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_SUMS = 1024 * 1024


class StoreError(Exception):
    """A version the store cannot provide — the message says why, and what to do."""


def cortex_home() -> Path:
    """``$CORTEX_HOME``, or ``~/.cortex``."""
    home = os.environ.get("CORTEX_HOME")
    return Path(os.path.abspath(home)) if home else Path.home() / ".cortex"


def releases_url() -> str:
    """Where releases are downloaded from — ``$CORTEX_RELEASES_URL``, as for the install scripts:
    https, or http to this machine for tests."""
    url = (os.environ.get("CORTEX_RELEASES_URL") or DEFAULT_RELEASES_URL).rstrip("/")
    try:
        net.check_url(url)
    except net.DownloadError as error:
        raise StoreError(f"CORTEX_RELEASES_URL: {error}")
    return url


def known_specs() -> Dict[str, str]:
    """The checksum of every spec archive released before this binary was built — written by
    ``cli/build.py`` for the build. A source checkout knows none."""
    try:
        from ._known_specs import KNOWN
    except ImportError:
        return {}
    return dict(KNOWN)


def upgrade_command(version: Version) -> str:
    if os.name == "nt":
        return ("& ([scriptblock]::Create((irm https://raw.githubusercontent.com/adorey/cortex/main/install.ps1)))"
                f" -Version {version}")
    return f"curl -fsSL https://raw.githubusercontent.com/adorey/cortex/main/install.sh | sh -s -- {version}"


# --------------------------------------------------------------------------- #
# The embedded spec
# --------------------------------------------------------------------------- #

def embedded_archive() -> Optional[Path]:
    """The spec archive a built binary carries — ``None`` for a source checkout."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / SPEC_ARCHIVE
    return None


def source_checkout() -> Optional[Path]:
    """The checkout a source run comes from: its spec is the one next to the code."""
    root = Path(__file__).resolve().parents[2]
    return root if all((root / tree).is_dir() for tree in SPEC_TREES) else None


# --------------------------------------------------------------------------- #
# Permissions
# --------------------------------------------------------------------------- #

def make_read_only(root: Path) -> None:
    """Remove every write permission under ``root``, ``root`` included.

    POSIX: files ``0444``, directories ``0555`` — nothing is modified, created or removed. On
    Windows the read-only attribute protects files, not directories: a file of the spec cannot
    be modified or deleted, but a new one can be created beside it (ADR-008 §9).
    """
    for directory, subdirs, files in os.walk(root, topdown=False):
        for name in files:
            os.chmod(os.path.join(directory, name), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        if os.name != "nt":
            os.chmod(directory, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)


def make_writable(root: Path) -> None:
    if os.name != "nt":
        os.chmod(root, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
    for directory, subdirs, files in os.walk(root):
        for name in subdirs:
            if os.name != "nt":
                os.chmod(os.path.join(directory, name), stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH)
        for name in files:
            os.chmod(os.path.join(directory, name), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)


def remove_tree(root: Path) -> None:
    """Remove a tree the store, or sync, made read-only."""
    make_writable(root)
    shutil.rmtree(root)


# --------------------------------------------------------------------------- #
# The store
# --------------------------------------------------------------------------- #

class Store:
    def __init__(self, home: Optional[Path] = None, own_version: str = VERSION,
                 embedded: Optional[Path] = None, checkout: Optional[Path] = None,
                 fetch: Callable[[str, int], bytes] = net.get, known: Optional[Dict[str, str]] = None):
        self.home = home or cortex_home()
        self.versions = self.home / "versions"
        self.own = Version(own_version)
        self.embedded = embedded if embedded is not None else embedded_archive()
        self.checkout = checkout if checkout is not None or self.embedded else source_checkout()
        self.fetch = fetch
        self.known = known_specs() if known is None else known

    def path(self, version: Version) -> Path:
        return self.versions / str(version)

    def has(self, version: Version) -> bool:
        """A version is there when its three trees are — an empty directory is none."""
        return all((self.path(version) / tree).is_dir() for tree in SPEC_TREES)

    def _tidy(self, version: Version) -> None:
        """Make a stored version read-only again — a sync interrupted between the rename and the
        chmod left it writable — and remove the stagings older than a day."""
        path = self.path(version)
        if os.name != "nt" and os.stat(path).st_mode & stat.S_IWUSR:
            make_read_only(path)
        cutoff = time.time() - 86400
        for entry in self.versions.glob(".*"):
            try:
                if entry.stat().st_mtime < cutoff:
                    remove_tree(entry) if entry.is_dir() else entry.unlink()
            except OSError:
                pass

    def check_served(self, version: Version) -> None:
        """Refuse a version this binary does not serve: newer than itself — the tool is newer than
        the data it reads, never older — or older than the first spec archive."""
        if version > self.own:
            raise StoreError(f"this project uses Cortex {version}, newer than this cortex, {self.own} — upgrade it:\n"
                             f"    {upgrade_command(version)}")
        if version != self.own and version < FIRST_SPEC_ARCHIVE:
            raise StoreError(f"Cortex {version} has no spec archive: the first one is {FIRST_SPEC_ARCHIVE}, "
                             "the release that ships the cortex command — pin that version or a later one")

    def ensure(self, version: Version) -> str:
        """Make sure ``version`` is in the store; say how it got there — ``"stored"``,
        ``"written"`` from this binary, or ``"downloaded"``."""
        self.check_served(version)
        if self.has(version):
            self._tidy(version)
            return "stored"
        if self.path(version).exists():
            raise StoreError(f"{self.path(version)} is there, and holds no complete spec — remove it, "
                             "then run the command again")
        self.versions.mkdir(parents=True, exist_ok=True)
        if version == self.own:
            if self.embedded is not None:
                self._install(version, lambda staging: _extract(self.embedded, staging))
            elif self.checkout is not None:
                self._install(version, lambda staging: _copy_trees(self.checkout, staging))
            else:
                raise StoreError(f"this cortex carries no spec of its own version, {version}")
            return "written"
        self._download(version)
        return "downloaded"

    def _download(self, version: Version) -> None:
        base = f"{releases_url()}/download/{version}"
        try:
            sums = self.fetch(f"{base}/SHA256SUMS", MAX_SUMS).decode("utf-8")
        except net.DownloadError as error:
            raise StoreError(f"could not download the SHA256SUMS of Cortex {version}: {error}")
        expected = next((line.split()[0].lower() for line in sums.splitlines()
                         if len(line.split()) == 2 and line.split()[1].lstrip("*") == SPEC_ARCHIVE), None)
        if expected is None:
            raise StoreError(f"the SHA256SUMS of Cortex {version} lists no {SPEC_ARCHIVE} — nothing was written")
        known = self.known.get(str(version))
        if known is not None and known != expected:
            raise StoreError(f"the SHA256SUMS of Cortex {version} names {expected}, and this cortex knows its spec "
                             f"archive as {known}: the release was changed since this binary was built. "
                             "Nothing was written.")
        try:
            data = self.fetch(f"{base}/{SPEC_ARCHIVE}", MAX_ARCHIVE)
        except net.DownloadError as error:
            raise StoreError(f"could not download the spec of Cortex {version}: {error}")
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise StoreError(f"the spec of Cortex {version} does not match its checksum — expected {expected}, "
                             f"got {actual}. Nothing was written.")
        # Checked before anything is extracted, then extracted from the bytes that were checked.
        fd, archive = tempfile.mkstemp(prefix=".download-", dir=self.versions)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            self._install(version, lambda staging: _extract(Path(archive), staging))
        finally:
            os.unlink(archive)

    def _install(self, version: Version, fill: Callable[[Path], None]) -> None:
        staging = Path(tempfile.mkdtemp(prefix=f".{version}-", dir=self.versions))
        try:
            fill(staging)
            found = sorted(entry.name for entry in staging.iterdir())
            if found != sorted(SPEC_TREES):
                raise StoreError(f"the spec of Cortex {version} holds {', '.join(found) or 'nothing'}, "
                                 f"not {', '.join(SPEC_TREES)} — nothing was written")
            try:
                os.rename(staging, self.path(version))
            except OSError:
                if not self.has(version):
                    raise
                # Another sync wrote it meanwhile: the same version, the same content.
                remove_tree(staging)
                return
        except BaseException:
            if staging.exists():
                remove_tree(staging)
            raise
        make_read_only(self.path(version))


def _copy_trees(source: Path, staging: Path) -> None:
    for tree in SPEC_TREES:
        shutil.copytree(source / tree, staging / tree, ignore=shutil.ignore_patterns(".active-theme"))


def _extract(archive: Path, staging: Path) -> None:
    """Extract a spec archive — regular files and directories only, all of them inside
    ``staging``: no absolute path, no ``..``, no link, no device."""
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            parts = member.name.split("/")
            if member.name.startswith("/") or ".." in parts or not (member.isfile() or member.isdir()):
                raise StoreError(f"{archive.name} holds {member.name!r}, which a spec archive cannot hold — "
                                 "nothing was written")
        if hasattr(tarfile, "data_filter"):
            tar.extractall(staging, members=members, filter="data")
        else:                                  # Python 3.11 before 3.11.4: checked above
            tar.extractall(staging, members=members)
