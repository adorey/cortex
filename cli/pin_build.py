"""Write ``requirements-build.txt`` from ``requirements-build.in``, with the hashes of every file
PyPI holds for each pinned version, so that ``pip install --require-hashes`` installs the build's
tools, and only them, on every target (ADR-008 §3.1).

    python cli/pin_build.py
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

CLI = Path(__file__).resolve().parent
PIN = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)==(?P<version>[^\s;]+)\s*(?P<marker>;.*)?$")


def hashes(name: str, version: str):
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as response:
        release = json.load(response)
    return sorted({url["digests"]["sha256"] for url in release["urls"]})


def main() -> int:
    lines = ["# Written by cli/pin_build.py from requirements-build.in — edit that file, then run it again.\n"]
    for raw in (CLI / "requirements-build.in").read_text(encoding="utf-8").splitlines():
        match = PIN.match(raw.strip())
        if not match:
            continue
        name, version, marker = match["name"], match["version"], (match["marker"] or "").strip()
        requirement = f"{name}=={version}" + (f" {marker}" if marker else "")
        lines.append(requirement + " \\\n" + " \\\n".join(f"    --hash=sha256:{h}" for h in hashes(name, version)) + "\n")
    (CLI / "requirements-build.txt").write_text("".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
