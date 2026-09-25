"""Overlay validation — ADR-001 Tier 1 and Tier 2 (ADR-007).

``bin/validate-overlays.sh`` runs this module. It is a literal port of the Bash implementation
that script held until Cortex 0.9.0: same checks in the same order, same messages, same exit
codes, byte-identical output — so that nothing a host project relied on changed with the port.

It then departed from that output on purpose (ADR-007 §3.6 and its amendments): a file without a
header at the path of a base is reported as ``MISSING_HEADER``; a header key that is absent — not
only empty — is reported as ``MISSING_FIELD`` instead of aborting the run; paths are taken from
the root being scanned, where the script cut absolute paths at their first ``/agents/``; and what
was read is printed as it was read, where the script passed it through ``echo -e``.

The cascade's own rules — which layer replaces, which file cannot be overridden — are not
restated here: they come from the resolver, the one implementation the runtime runs too.
"""

# The standard library and this package only: bin/validate-overlays.sh imports it under
# ``python -I`` from the Cortex checkout, with nothing installed (see the shim).
from __future__ import annotations

import fnmatch
import io
import os
import re
import signal
import sys
from typing import List, Optional, TextIO, Tuple

from . import catalog, resolver

LAYERS = ("roles", "capabilities", "personalities", "workflows")

USAGE = 'Usage: validate-overlays.sh [OPTIONS]\n\nOptions:\n  --service PATH     Validate overlays under a specific service folder only\n                     (path relative to project root or absolute)\n  --strict           Treat warnings as errors (CI-friendly)\n  -h, --help         Show this help\n\nExit codes:\n  0   No errors (and no warnings in --strict mode)\n  1   Errors detected (or warnings in --strict mode)\n  2   Bad arguments\n\nReference: ADR-001-layered-overrides.md\n'
SEPARATOR = '──────────────────────────────────────────'

_SPACE = "[ \t\n\v\f\r]"          # POSIX [[:space:]]
_ADDITIVE_TAG = re.compile(r"^##.*\(additive\)|^## 🚫 Disabled rules from base")
# C0, DEL and C1 — and C1 as the raw byte of a name that is not UTF-8, which surrogateescape
# decodes to U+DC80..U+DC9F
_CONTROL = re.compile("[\x00-\x1f\x7f-\x9f\udc80-\udc9f]")


class Colors:
    def __init__(self, enabled: bool):
        on = enabled
        self.GREEN = "\x1b[0;32m" if on else ""
        self.RED = "\x1b[0;31m" if on else ""
        self.YELLOW = "\x1b[1;33m" if on else ""
        self.BLUE = "\x1b[0;34m" if on else ""
        self.BOLD = "\x1b[1m" if on else ""
        self.NC = "\x1b[0m" if on else ""


def shown(value: str) -> str:
    """``value`` with its control characters written out — ``\\x1b`` for ESC — so that nothing
    read from a project reaches the terminal as a control sequence (#85)."""
    return _CONTROL.sub(lambda m: "\\x%02x" % (ord(m.group()) & 0xFF), value)


def strip_prefix(value: str, prefix: str) -> str:
    """Bash ``${value#prefix}`` for a literal prefix."""
    return value[len(prefix):] if value.startswith(prefix) else value


def read_text(path: str) -> str:
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8", "surrogateescape")


def extract_field(text: str, name: str) -> Optional[str]:
    """The script's ``sed -n '/<!-- OVERLAY/,/-->/p' | grep -E '^[[:space:]]*Name:' | head -1``.

    Returns ``None`` when no line matches — the key is absent.
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
    """Verdict lines and counters, as the script's ``report_*`` helpers print them.

    Paths and messages go through ``shown``: they carry what was read from the project.
    """

    def __init__(self, out: TextIO, colors: Colors):
        self.out, self.c = out, colors
        self.errors = self.warnings = self.checked = 0

    def echo(self, text: str) -> None:
        self.out.write(text + "\n")

    def error(self, rel_path: str, code: str, message: str) -> None:
        self.echo(f"{self.c.RED}✗{self.c.NC} {shown(rel_path)}")
        self.echo(f"  {self.c.RED}{code}{self.c.NC} — {shown(message)}")
        self.errors += 1

    def warning(self, rel_path: str, code: str, message: str) -> None:
        self.echo(f"{self.c.YELLOW}⚠{self.c.NC} {shown(rel_path)}")
        self.echo(f"  {self.c.YELLOW}{code}{self.c.NC} — {shown(message)}")
        self.warnings += 1

    def ok(self, rel_path: str) -> None:
        self.echo(f"{self.c.GREEN}✓{self.c.NC} {shown(rel_path)}")

    def info(self, rel_path: str, note: str) -> None:
        self.echo(f"{self.c.BLUE}ℹ{self.c.NC} {shown(rel_path)} ({note})")


def base_file(base: str, project_root: str, base_root: str) -> str:
    """Where a ``Base:`` header points. The logical ``cortex/agents/…`` identifier resolves
    against ``base_root`` (ADR-007 §3.4); anything else stays relative to the project, as in
    the script's ``"$PROJECT_DIR/$base"``."""
    if base.startswith("cortex/agents/"):
        return f"{base_root}/agents/{base[len('cortex/agents/'):]}"
    return f"{project_root}/{base}"


_NON_OVERRIDABLE = "characters.md is not overridable; fork the theme instead (see docs/creating-a-theme.md)"


def check_overlay(file: str, root: str, project_root: str, base_root: str, report: Report) -> None:
    """Validate one overlay file, found under ``{root}/agents/`` — the script's ``validate_overlay_file``.

    Its path under ``agents/`` and whether it is a workspace or a service overlay come from
    ``root``, never from the absolute path: where the project sits on disk changes nothing (#84).
    """
    rel_path = strip_prefix(file, f"{project_root}/")
    file_rel_to_agents = strip_prefix(file, f"{root}/agents/")
    in_workspace = os.path.normpath(root) == os.path.normpath(project_root)
    # The file's layer, and its path within it, as the resolver sees them
    layer, _, file_in_layer = file_rel_to_agents.partition("/")
    rule = resolver.semantic_for(layer, file_in_layer)
    report.checked += 1
    try:
        text = read_text(file)
    except OSError as error:
        # The script's head failed, said so on stderr, and so found no header.
        sys.stderr.write(f"head: cannot open '{file}' for reading: {error.strerror}\n")
        text = ""

    # Tier 1.1 — header presence, in the first ten lines. Without one, a file at the path of a
    # base shadows it — the resolver stacks it, so it is an overlay missing its header
    # (ADR-007 §3.6), unless it is one the resolver never stacks: characters.md is the same
    # error with a header or without. A README is documentation, which the cascade never reads.
    # Anywhere else it is a custom addition.
    if not any("<!-- OVERLAY" in line for line in text.split("\n")[:10]):
        if os.path.isfile(f"{base_root}/agents/{file_rel_to_agents}") and not catalog.is_readme(os.path.basename(file)):
            if rule is resolver.MergeSemantic.NOT_OVERRIDABLE:
                report.error(rel_path, "NON_OVERRIDABLE", _NON_OVERRIDABLE)
                return
            report.warning(rel_path, "MISSING_HEADER",
                           f"no <!-- OVERLAY --> header, yet it shadows the base 'cortex/agents/{file_rel_to_agents}' — "
                           "add the header, or rename the file if it is not meant to extend that base")
            return
        report.info(rel_path, "custom addition — no cortex base, skipping overlay checks")
        return

    # Tier 1.2 — required fields, absent or empty alike
    fields = {name: extract_field(text, name) for name in ("Base", "Scope", "Semantic")}
    for name, value in fields.items():
        if not value:
            report.error(rel_path, "MISSING_FIELD", f"{name}: is required in OVERLAY header")
            return
    base, scope, semantic = fields["Base"], fields["Scope"], fields["Semantic"]

    # Tier 1.3 — base exists
    if not os.path.isfile(base_file(base, project_root, base_root)):
        report.error(rel_path, "BASE_NOT_FOUND", f"Base: '{base}' does not exist (typo, or upstream removed it?)")
        return

    # Tier 1.4 — semantic valid
    if semantic not in ("additive", "replacement"):
        report.error(rel_path, "INVALID_SEMANTIC", f"Semantic: must be 'additive' or 'replacement' (got '{semantic}')")
        return

    # Tier 1.5 — replacement only where the resolver replaces: workflows
    if semantic == "replacement" and rule is not resolver.MergeSemantic.REPLACEMENT:
        report.error(rel_path, "REPLACEMENT_OUTSIDE_WORKFLOWS",
                     "Semantic: replacement is only allowed for files under agents/workflows/")
        return

    # Tier 1.6 — path mirroring
    base_rel_to_agents = strip_prefix(base, "cortex/agents/")
    if file_rel_to_agents != base_rel_to_agents:
        report.error(rel_path, "PATH_MIRROR",
                     f"overlay path 'agents/{file_rel_to_agents}' must mirror base 'cortex/agents/{base_rel_to_agents}'")
        return

    # Tier 2.1 — non-overridable, as the resolver says: characters.md (reported as an error,
    # as the script does). Past the mirror check, the base and the file share this path.
    if rule is resolver.MergeSemantic.NOT_OVERRIDABLE:
        report.error(rel_path, "NON_OVERRIDABLE", _NON_OVERRIDABLE)
        return

    # Tier 2.2 — the file is in a known layer: holds by construction, since discovery walks the
    # four layer directories only

    # Tier 2.3 — scope vs location
    if scope.startswith("workspace") and not in_workspace:
        report.warning(rel_path, "SCOPE_MISMATCH", f"Scope: '{scope}' but file is not at workspace root (agents/...)")
    if scope.startswith("service") and in_workspace:
        report.warning(rel_path, "SCOPE_MISMATCH",
                       f"Scope: '{scope}' but file is at workspace root — should be under {{service}}/agents/")

    # Tier 2.4 — an additive overlay tags at least one section
    if semantic == "additive" and not any(_ADDITIVE_TAG.search(line) for line in text.split("\n")):
        report.warning(rel_path, "SECTIONS_UNTAGGED",
                       "additive overlay should tag at least one section as '(additive)' or use '## 🚫 Disabled rules from base'")

    report.ok(rel_path)


# --------------------------------------------------------------------------- #
# Discovery — the script's two ``find`` calls
# --------------------------------------------------------------------------- #
def find(top: str, name: str, *, maxdepth: Optional[int] = None, regular_files: bool = False,
         prune_names: Tuple[str, ...] = (), prune_paths: Tuple[str, ...] = (),
         follow_links: bool = False) -> List[str]:
    """``find TOP [-maxdepth N] -name NAME [-type f]``, in ``find``'s order, without entering the
    directories below ``TOP`` that are named in ``prune_names`` or located at ``prune_paths``.

    Depth first, each directory's entries in the order the file system returns them — the
    order ``find`` prints, so the report lists files in the same sequence as the script did.
    Pruning looks below ``TOP`` only: what the directories above it are called changes nothing.
    With ``follow_links``, files and directories behind symbolic links count as the resolver
    reads them — ``find -L`` — and a directory reached twice, a link loop, is entered once.
    """
    found: List[str] = []
    pruned = {os.path.normpath(p) for p in prune_paths}
    entered = set()

    def visit(directory: str, depth: int) -> None:
        if follow_links:
            try:
                key = (os.stat(directory).st_dev, os.stat(directory).st_ino)
            except OSError:
                return
            if key in entered:
                return
            entered.add(key)
        try:
            entries = list(os.scandir(directory))
        except OSError:
            return                    # find reports it on stderr, which the script discards
        for entry in entries:
            path = f"{directory}/{entry.name}"
            if (maxdepth is None or depth + 1 <= maxdepth) and fnmatch.fnmatchcase(entry.name, name) \
                    and (not regular_files or entry.is_file(follow_symlinks=follow_links)):
                found.append(path)
            if entry.is_dir(follow_symlinks=follow_links) and (maxdepth is None or depth + 1 < maxdepth) \
                    and entry.name not in prune_names and os.path.normpath(path) not in pruned:
                visit(path, depth + 1)

    visit(top, 0)
    return found


def _same_directory(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.normpath(a) == os.path.normpath(b)


def overlay_roots(project_root: str, base_root: str, service: str) -> List[str]:
    """The workspace, when it has ``agents/``, then every service that has both a
    ``project-overview.md`` and an ``agents/`` — or the one ``--service`` names.

    A project root that is the base itself — Cortex validating itself — is no workspace tier:
    its files are the base, read once and never stacked onto themselves (ADR-007 §3.1).
    Services are looked for outside the base, wherever it is mounted and whatever it is called,
    and outside any directory named ``cortex`` or ``.git`` below the project root — a service
    may mount its own Cortex.
    """
    if service:
        return [service if os.path.isabs(service) else f"{project_root}/{service}"]
    is_base = _same_directory(project_root, base_root)
    roots = [project_root] if os.path.isdir(f"{project_root}/agents") and not is_base else []
    for overview in find(project_root, "project-overview.md", maxdepth=5,
                         prune_names=("cortex", ".git"), prune_paths=(base_root,)):
        service_dir = os.path.dirname(overview)
        if service_dir == project_root or not os.path.isdir(f"{service_dir}/agents"):
            continue
        roots.append(service_dir)
    return roots


# --------------------------------------------------------------------------- #
# The run
# --------------------------------------------------------------------------- #
def validate(project_root: str, base_root: str, service: str, strict: bool, out: TextIO, colors: Colors) -> int:
    """Validate every overlay under the overlay roots; return the script's exit code."""
    c = colors
    report = Report(out, c)
    report.echo(f"{c.BOLD}{c.BLUE}Cortex overlay validator{c.NC}")
    report.echo(f"  Project root:  {shown(project_root)}")
    report.echo(f"  Cortex dir:    {shown(base_root)}")
    report.echo(f"  Strict mode:   {'true' if strict else 'false'}")
    if service:
        report.echo(f"  Service only:  {shown(service)}")
    report.echo("")

    roots = overlay_roots(project_root, base_root, service)
    if not roots:
        report.echo(f"{c.YELLOW}ℹ{c.NC}  No overlay roots found (no agents/ directory at workspace or service level).")
        report.echo("   Nothing to validate. This is expected if you haven't created overlays yet.")
        return 0

    for root in roots:
        in_workspace = os.path.normpath(root) == os.path.normpath(project_root)
        rel_root = "." if in_workspace else strip_prefix(root, f"{project_root}/")
        report.echo(f"{c.BOLD}── Scope: {shown(rel_root)} ──{c.NC}")
        found = 0
        for layer in LAYERS:
            layer_dir = f"{root}/agents/{layer}"
            if not os.path.isdir(layer_dir):
                continue
            for path in find(layer_dir, "*.md", regular_files=True, follow_links=True):
                check_overlay(path, root, project_root, base_root, report)
                found += 1
        if found == 0:
            report.echo("  (no overlay files)")
        report.echo("")

    report.echo(SEPARATOR)
    report.echo(f"Checked:  {c.BOLD}{report.checked}{c.NC} files")
    report.echo(f"Errors:   {c.RED}{c.BOLD}{report.errors}{c.NC}" if report.errors else f"Errors:   {c.GREEN}0{c.NC}")
    report.echo(f"Warnings: {c.YELLOW}{c.BOLD}{report.warnings}{c.NC}" if report.warnings else f"Warnings: {c.GREEN}0{c.NC}")
    if report.errors:
        return 1
    if strict and report.warnings:
        report.echo(f"{c.RED}Strict mode: warnings count as errors.{c.NC}")
        return 1
    return 0


def _stream(stream: TextIO) -> TextIO:
    """Bytes out as the script writes them — file names that are not valid UTF-8 included."""
    return io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="surrogateescape", newline="\n", write_through=True)


def main(argv: Optional[List[str]] = None, *, project_root: Optional[str] = None,
         base_root: Optional[str] = None) -> int:
    """``bin/validate-overlays.sh [--service PATH] [--strict] [-h|--help]``.

    The two roots are no options: ``cli`` receives them from the script, which derives them from
    its own location. Left out, they are derived the same way from this file's location in a
    Cortex checkout — ``{project}/cortex/core/cortex_core/validate.py``.
    """
    args = sys.argv[1:] if argv is None else list(argv)
    if base_root is None:
        base_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root is None:
        project_root = os.path.dirname(base_root)
    out, err = _stream(sys.stdout), _stream(sys.stderr)
    try:
        return _main(args, project_root, base_root, out, err)
    finally:
        # The wrappers borrow the process's own streams: detached, returning leaves stdout and
        # stderr open for whatever runs next in this process.
        out.detach()
        err.detach()


def _main(args: List[str], project_root: str, base_root: str, out: TextIO, err: TextIO) -> int:
    service, strict = "", False
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--service":
            if i + 1 >= len(args):
                return 1          # the script's `shift 2` fails under errexit: exit 1, nothing printed
            service, i = args[i + 1], i + 2
        elif arg == "--strict":
            strict, i = True, i + 1
        elif arg in ("-h", "--help"):
            out.write(USAGE)
            return 0
        else:
            err.write(f"Unknown argument: {arg}\n")
            err.write(USAGE)
            return 2
    return validate(project_root, base_root, service, strict, out, Colors(out.isatty()))


def cli() -> int:
    """The command line ``bin/validate-overlays.sh`` runs: ``PROJECT_ROOT BASE_ROOT [OPTIONS]``,
    the two roots from the script, the options from its caller.

    A reader that goes away — ``| head`` — ends the run as it ended the script, by SIGPIPE and in
    silence, not with a BrokenPipeError.
    """
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    if len(sys.argv) < 3:
        sys.stderr.write("usage: PROJECT_ROOT BASE_ROOT [OPTIONS] — run it as bin/validate-overlays.sh\n")
        return 2
    return main(sys.argv[3:], project_root=sys.argv[1], base_root=sys.argv[2])


if __name__ == "__main__":
    sys.exit(cli())
