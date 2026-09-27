"""Build the ``cortex`` binary with PyInstaller — ADR-008 §3.1.

    python cli/build.py --version 1.0.0

writes ``cli/build/dist/cortex`` — ``cortex.exe`` on Windows — and, next to it, the release asset
of the machine's target: ``cortex-{target}.tar.gz``, a ``.zip`` on Windows, holding the binary,
``LICENSE`` and ``NOTICE``. It needs PyInstaller (``cli/requirements-build.txt``) and nothing else.

    python cli/build.py --checksums DIR

writes ``DIR/SHA256SUMS`` over the release assets in ``DIR``.

The version is stamped into the binary for the duration of the build, in ``cortex_cli/_stamp.py``:
the release's, from the tag, or a pre-release — ``0.0.0-dev.N`` — for a build of no release.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import re
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path

CLI = Path(__file__).resolve().parent
REPO = CLI.parent
BUILD = CLI / "build"
STAMP = CLI / "cortex_cli" / "_stamp.py"
VERSION = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")
# (operating system, machine) as Python names them -> the target's name in the release (§3.1)
TARGETS = {
    ("linux", "x86_64"): "linux-x86_64",
    ("linux", "aarch64"): "linux-aarch64",
    ("darwin", "arm64"): "macos-arm64",
    ("windows", "amd64"): "windows-x86_64",
}


def machine_target() -> str:
    key = (platform.system().lower(), platform.machine().lower())
    if key not in TARGETS:
        sys.exit(f"build.py: {key[0]} {key[1]} is not a target of ADR-008 §3.1")
    return TARGETS[key]


def build(version: str) -> Path:
    """Run PyInstaller and return the binary it wrote."""
    STAMP.write_text(f'"""Written by cli/build.py for one build — never committed."""\n\nVERSION = "{version}"\n',
                     encoding="utf-8")
    try:
        subprocess.run([
            sys.executable, "-m", "PyInstaller",
            "--onefile", "--name", "cortex", "--console", "--clean", "--noconfirm",
            # The core and the command, from this checkout: nothing is installed.
            "--paths", str(REPO / "core"), "--paths", str(CLI),
            "--distpath", str(BUILD / "dist"), "--workpath", str(BUILD / "work"), "--specpath", str(BUILD),
            str(CLI / "cortex_cli" / "__main__.py"),
        ], check=True)
    finally:
        STAMP.unlink()
    return BUILD / "dist" / ("cortex.exe" if os.name == "nt" else "cortex")


def package(binary: Path, target: str) -> Path:
    """The release asset of ``target``: the binary with the licence it ships under."""
    files = [(binary, binary.name), (REPO / "LICENSE", "LICENSE"), (REPO / "NOTICE", "NOTICE")]
    mtime = int(os.environ.get("SOURCE_DATE_EPOCH", time.time()))
    if target.startswith("windows-"):
        asset = binary.parent / f"cortex-{target}.zip"
        with zipfile.ZipFile(asset, "w", zipfile.ZIP_DEFLATED) as archive:
            for path, name in files:
                info = zipfile.ZipInfo(name, time.gmtime(max(mtime, 315532800))[:6])
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
        return asset
    asset = binary.parent / f"cortex-{target}.tar.gz"
    with tarfile.open(asset, "w:gz") as archive:
        for path, name in files:
            info = archive.gettarinfo(str(path), arcname=name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = mtime
            info.mode = 0o755 if path == binary else 0o644
            with open(path, "rb") as fh:
                archive.addfile(info, fh)
    return asset


def checksums(directory: Path) -> Path:
    """``SHA256SUMS`` over the release assets in ``directory``, in ``sha256sum``'s format — what
    the install scripts check an asset against, and ``sha256sum -c`` reads."""
    lines = []
    for asset in sorted(directory.glob("cortex-*")):
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        lines.append(f"{digest}  {asset.name}\n")
    sums = directory / "SHA256SUMS"
    sums.write_text("".join(lines), encoding="utf-8", newline="\n")
    return sums


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the cortex binary (ADR-008 §3.1).")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--version", help="build the binary: the release's version, X.Y.Z, or a pre-release")
    action.add_argument("--checksums", metavar="DIR", type=Path, help="write DIR/SHA256SUMS over the assets in DIR")
    args = parser.parse_args()
    if args.checksums:
        print(checksums(args.checksums).read_text(encoding="utf-8"), end="")
        return 0
    if not VERSION.match(args.version):
        parser.error(f"not a version: {args.version!r}")
    target = machine_target()
    binary = build(args.version)
    asset = package(binary, target)
    print(f"built {binary}\npackaged {asset}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
