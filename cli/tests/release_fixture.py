"""A release as the install scripts see it, served over HTTP from this machine.

``CORTEX_RELEASES_URL`` points the scripts at it: the layout of GitHub's releases,
``latest/download/ASSET`` and ``download/VERSION/ASSET``, with each release's ``SHA256SUMS``. The
binaries in it are stand-ins: on POSIX a shell script printing ``cortex VERSION``, on Windows a
file that is no program at all — what is checked is how the scripts download, verify and install.
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


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class FakeRelease:
    """Releases ``versions``, the last one the latest, served until ``close``."""

    def __init__(self, versions=("9.9.8", "9.9.9")):
        self.root = Path(tempfile.mkdtemp(prefix="cortex-release-"))
        for version in versions:
            self.publish(self.root / "download" / version, version)
        shutil.copytree(self.root / "download" / versions[-1], self.root / "latest" / "download")
        handler = functools.partial(_Quiet, directory=str(self.root))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    @staticmethod
    def publish(directory, version):
        directory.mkdir(parents=True)
        for target in TARGETS:
            _asset(directory, target, version)
        build.checksums(directory)

    def asset(self, target, version=None):
        directory = self.root / ("latest/download" if version is None else f"download/{version}")
        return next(directory.glob(f"cortex-{target}.*"))

    def alter_one_byte(self, target):
        """Change one byte of the latest release's asset, after its checksum was written."""
        path = self.asset(target)
        data = bytearray(path.read_bytes())
        data[len(data) // 2] ^= 0x01
        path.write_bytes(bytes(data))

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.root, ignore_errors=True)
