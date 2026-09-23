"""Overlay validation — ADR-001 Tier 1 and Tier 2 (ADR-007).

A literal port of ``bin/validate-overlays.sh``: same checks in the same order, same messages,
same exit codes, and output that is byte-identical to the script's. Literal means literal — the
string arithmetic the script does on absolute paths (``${file#*/agents/}``, ``"$PROJECT_DIR/$base"``)
and its ``echo -e`` escapes are reproduced as they are, so that nothing a host project relied on
changes when the script becomes a shim over this module.
"""

from __future__ import annotations

import fnmatch
import os
import re
from typing import List, Optional, TextIO, Tuple

LAYERS = ("roles", "capabilities", "personalities", "workflows")

_SPACE = "[ \t\n\v\f\r]"          # POSIX [[:space:]]
_ADDITIVE_TAG = re.compile(r"^##.*\(additive\)|^## 🚫 Disabled rules from base")
_ESCAPE = re.compile(r"\\(0[0-7]{0,3}|x[0-9A-Fa-f]{1,2}|u[0-9A-Fa-f]{1,4}|U[0-9A-Fa-f]{1,8}|.)", re.S)
_SIMPLE = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "n": "\n", "r": "\r",
           "t": "\t", "v": "\v", "\\": "\\"}


class Abort(Exception):
    """The script dies under ``set -e`` when a header key is missing: an empty ``grep`` fails the
    pipeline, and the assignment exits the shell before any verdict is printed."""


class Colors:
    def __init__(self, enabled: bool):
        on = enabled
        self.GREEN = "\x1b[0;32m" if on else ""
        self.RED = "\x1b[0;31m" if on else ""
        self.YELLOW = "\x1b[1;33m" if on else ""
        self.BLUE = "\x1b[0;34m" if on else ""
        self.BOLD = "\x1b[1m" if on else ""
        self.NC = "\x1b[0m" if on else ""


def echo_e(text: str) -> Tuple[str, bool]:
    """What Bash's ``echo -e`` prints for ``text``, and whether a ``\\c`` cut it short.

    ``\\c`` stops the output there, trailing newline included.
    """
    out: List[str] = []
    pos = 0
    for m in _ESCAPE.finditer(text):
        out.append(text[pos:m.start()])
        esc = m.group(1)
        head = esc[0]
        if head == "c":
            return "".join(out), True
        if head == "0":
            out.append(chr(int(esc[1:] or "0", 8)))
        elif head in ("x", "u", "U"):
            out.append(chr(int(esc[1:], 16)))
        elif head in _SIMPLE:
            out.append(_SIMPLE[head])
        else:
            out.append("\\" + esc)          # unknown escape: printed as it is
        pos = m.end()
    out.append(text[pos:])
    return "".join(out), False


def echo_e_line(text: str) -> str:
    rendered, cut = echo_e(text)
    return rendered if cut else rendered + "\n"


def strip_prefix(value: str, prefix: str) -> str:
    """Bash ``${value#prefix}`` for a literal prefix."""
    return value[len(prefix):] if value.startswith(prefix) else value


def after_first(value: str, marker: str) -> str:
    """Bash ``${value#*marker}`` — everything after the first occurrence of ``marker``."""
    idx = value.find(marker)
    return value[idx + len(marker):] if idx >= 0 else value


def read_text(path: str) -> str:
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8", "surrogateescape")


def extract_field(text: str, name: str) -> Optional[str]:
    """The script's ``sed -n '/<!-- OVERLAY/,/-->/p' | grep -E '^[[:space:]]*Name:' | head -1``.

    Returns ``None`` when no line matches — where the script's pipeline fails.
    """
    block: List[str] = []
    in_range = False
    for line in text.split("\n"):
        if in_range:
            block.append(line)
            if "-->" in line:
                in_range = False
        elif "<!-- OVERLAY" in line:
            block.append(line)          # sed does not test the end address on the start line
            in_range = True
    key = re.compile(f"^{_SPACE}*{re.escape(name)}:")
    for line in block:
        if key.match(line):
            value = re.sub(f"^{_SPACE}*{re.escape(name)}:{_SPACE}*", "", line, count=1)
            return re.sub(f"{_SPACE}*$", "", value)
    return None


class Report:
    """Verdict lines and counters, as the script's ``report_*`` helpers print them."""

    def __init__(self, out: TextIO, colors: Colors):
        self.out, self.c = out, colors
        self.errors = self.warnings = self.checked = 0

    def echo(self, text: str) -> None:
        self.out.write(text + "\n")

    def echo_e(self, text: str) -> None:
        self.out.write(echo_e_line(text))

    def error(self, rel_path: str, code: str, message: str) -> None:
        self.echo_e(f"{self.c.RED}✗{self.c.NC} {rel_path}")
        self.echo_e(f"  {self.c.RED}{code}{self.c.NC} — {message}")
        self.errors += 1

    def warning(self, rel_path: str, code: str, message: str) -> None:
        self.echo_e(f"{self.c.YELLOW}⚠{self.c.NC} {rel_path}")
        self.echo_e(f"  {self.c.YELLOW}{code}{self.c.NC} — {message}")
        self.warnings += 1

    def ok(self, rel_path: str) -> None:
        self.echo_e(f"{self.c.GREEN}✓{self.c.NC} {rel_path}")


def base_file(base: str, project_root: str, base_root: str) -> str:
    """Where a ``Base:`` header points. The logical ``cortex/agents/…`` identifier resolves
    against ``base_root`` (ADR-007 §3.4); anything else stays relative to the project, as in
    the script's ``"$PROJECT_DIR/$base"``."""
    if base.startswith("cortex/agents/"):
        return f"{base_root}/agents/{base[len('cortex/agents/'):]}"
    return f"{project_root}/{base}"


def check_overlay(file: str, project_root: str, base_root: str, report: Report) -> None:
    """Validate one overlay file — the script's ``validate_overlay_file``."""
    rel_path = strip_prefix(file, f"{project_root}/")
    report.checked += 1
    text = read_text(file)

    # Tier 1.1 — header presence, in the first ten lines; otherwise a custom addition
    if not any("<!-- OVERLAY" in line for line in text.split("\n")[:10]):
        report.echo_e(f"{report.c.BLUE}ℹ{report.c.NC} {rel_path} (custom addition — no cortex base, skipping overlay checks)")
        return

    # Tier 1.2 — required fields
    fields = [extract_field(text, name) for name in ("Base", "Scope", "Semantic")]
    if any(value is None for value in fields):
        raise Abort()
    base, scope, semantic = fields
    for name, value in (("Base", base), ("Scope", scope), ("Semantic", semantic)):
        if not value:
            report.error(rel_path, "MISSING_FIELD", f"{name}: is required in OVERLAY header")
            return

    # Tier 1.3 — base exists
    if not os.path.isfile(base_file(base, project_root, base_root)):
        report.error(rel_path, "BASE_NOT_FOUND", f"Base: '{base}' does not exist (typo, or upstream removed it?)")
        return

    # Tier 1.4 — semantic valid
    if semantic not in ("additive", "replacement"):
        report.error(rel_path, "INVALID_SEMANTIC", f"Semantic: must be 'additive' or 'replacement' (got '{semantic}')")
        return

    # Tier 1.5 — replacement only for workflows
    if semantic == "replacement" and "/agents/workflows/" not in file:
        report.error(rel_path, "REPLACEMENT_OUTSIDE_WORKFLOWS",
                     "Semantic: replacement is only allowed for files under agents/workflows/")
        return

    # Tier 1.6 — path mirroring
    file_rel_to_agents = after_first(file, "/agents/")
    base_rel_to_agents = strip_prefix(base, "cortex/agents/")
    if file_rel_to_agents != base_rel_to_agents:
        report.error(rel_path, "PATH_MIRROR",
                     f"overlay path 'agents/{file_rel_to_agents}' must mirror base 'cortex/agents/{base_rel_to_agents}'")
        return

    # Tier 2.1 — non-overridable: characters.md (reported as an error, as the script does)
    if fnmatch.fnmatchcase(base, "*/personalities/*/characters.md"):
        report.error(rel_path, "NON_OVERRIDABLE",
                     "characters.md is not overridable; fork the theme instead (see docs/creating-a-theme.md)")
        return

    # Tier 2.2 — layer is known; a warning, checking goes on
    file_layer = file_rel_to_agents.split("/")[0]
    if file_layer not in LAYERS:
        report.warning(rel_path, "UNKNOWN_LAYER", f"'{file_layer}' is not a known layer (expected: {' '.join(LAYERS)})")

    # Tier 2.3 — scope vs location: a workspace overlay has 3 slashes below the project,
    # a service overlay 4 or more
    depth_from_project = strip_prefix(file, f"{project_root}/").count("/")
    if scope.startswith("workspace") and depth_from_project > 3 and not rel_path.startswith("agents/"):
        report.warning(rel_path, "SCOPE_MISMATCH", f"Scope: '{scope}' but file is not at workspace root (agents/...)")
    if scope.startswith("service") and rel_path.startswith("agents/"):
        report.warning(rel_path, "SCOPE_MISMATCH",
                       f"Scope: '{scope}' but file is at workspace root — should be under {{service}}/agents/")

    # Tier 2.4 — an additive overlay tags at least one section
    if semantic == "additive" and not any(_ADDITIVE_TAG.search(line) for line in text.split("\n")):
        report.warning(rel_path, "SECTIONS_UNTAGGED",
                       "additive overlay should tag at least one section as '(additive)' or use '## 🚫 Disabled rules from base'")

    report.ok(rel_path)
