"""A release as the install scripts and ``cortex sync`` see it, served over HTTP from this machine.

``CORTEX_RELEASES_URL`` points them at it: the layout of GitHub's releases,
``latest/download/ASSET`` and ``download/VERSION/ASSET``, with each release's ``SHA256SUMS``. The
binaries in it are stand-ins: on POSIX a shell script printing ``cortex VERSION``, on Windows a
file that is no program at all — what is checked is how the scripts download, verify and install.
Each release also carries a spec archive, ``cortex-spec.tar.gz``: a spec of a few files whose
role card names the version. The server records the paths it was asked for.
"""

import functools
import importlib.util
import io
import shutil
import tarfile
import tempfile
import threading
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CLI = Path(__file__).resolve().parents[1]
TARGETS = ("linux-x86_64", "linux-aarch64", "macos-arm64", "windows-x86_64")

_spec = importlib.util.spec_from_file_location("cortex_build", CLI / "build.py")
build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build)


def stand_in(version, windows):
    if windows:
        return f"not a program: cortex {version} for Windows\n".encode()
    return f'#!/bin/sh\necho "cortex {version}"\n'.encode()


def _asset(directory, target, version):
    windows = target.startswith("windows-")
    binary = stand_in(version, windows)
    if windows:
        path = directory / f"cortex-{target}.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("cortex.exe", binary)
            archive.writestr("LICENSE", "licence\n")
        return path
    path = directory / f"cortex-{target}.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        for name, data, mode in (("cortex", binary, 0o755), ("LICENSE", b"licence\n", 0o644)):
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), mode
            archive.addfile(info, io.BytesIO(data))
    return path


def spec_archive(directory, version, extra=None):
    """A spec archive for ``version``: the three trees, one file each — and ``extra``, a
    ``{name: bytes}`` of members to add, to build archives a store must refuse."""
    path = directory / "cortex-spec.tar.gz"
    files = {
        "agents/roles/prompt-manager.md": f"# Prompt Manager — Cortex {version}\n".encode(),
        "agents/personalities/h2g2/theme.md": b"# h2g2\n",
        "templates/bootstrap-instructions.md": b"# Bootstrap\n",
        "docs/extending-layers.md": b"# Extending\n",
    }
    files.update(extra or {})
    with tarfile.open(path, "w:gz") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o644
            archive.addfile(info, io.BytesIO(data))
    return path


class _Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.server.requested.append(self.path)
        super().do_GET()


class FakeRelease:
    """Releases ``versions``, the last one the latest, served until ``close``."""

    def __init__(self, versions=("9.9.8", "9.9.9")):
        self.root = Path(tempfile.mkdtemp(prefix="cortex-release-"))
        for version in versions:
            self.publish(self.root / "download" / version, version)
        shutil.copytree(self.root / "download" / versions[-1], self.root / "latest" / "download")
        handler = functools.partial(_Handler, directory=str(self.root))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.server.requested = []
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    @staticmethod
    def publish(directory, version):
        directory.mkdir(parents=True)
        for target in TARGETS:
            _asset(directory, target, version)
        spec_archive(directory, version)
        build.checksums(directory)

    @property
    def requested(self):
        return list(self.server.requested)

    def replace_spec(self, version, extra):
        """Republish ``version``'s spec archive with ``extra`` members, its checksum rewritten."""
        directory = self.root / "download" / version
        spec_archive(directory, version, extra)
        build.checksums(directory)

    def asset(self, target, version=None):
        directory = self.root / ("latest/download" if version is None else f"download/{version}")
        return next(directory.glob(f"cortex-{target}.*"))

    def alter_one_byte(self, target, version=None):
        """Change one byte of an asset of the latest release — or of ``version`` — after its
        checksum was written. ``target`` ``"spec"`` names the spec archive."""
        path = self.asset(target, version) if target != "spec" else \
            self.root / ("latest/download" if version is None else f"download/{version}") / "cortex-spec.tar.gz"
        data = bytearray(path.read_bytes())
        data[len(data) // 2] ^= 0x01
        path.write_bytes(bytes(data))

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.root, ignore_errors=True)
