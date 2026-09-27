"""``cortex init`` — ``setup.sh``, at parity (ADR-008 §3.7).

Same options, same defaults (``--theme h2g2``, ``--tool copilot``), same files at the same paths
as ``setup.sh``: the tool's instructions file, the root ``project-overview.md`` and
``project-context.md`` when missing, and in workspace mode a pair per service carrying its
``@alias`` — the basename of its folder — plus the team tier when ``agents/`` is its own git
working tree. The files are written byte for byte as the script wrote them, from the templates of
the version the project pins, in the store.

It also writes ``cortex.toml`` at the binary's own version, adds ``cortex.local.toml`` to
``.gitignore`` — and ``cortex/`` in ``link`` and ``copy`` modes — then runs ``cortex sync``.

Two deliberate differences: services are named by a repeatable ``--service``, the interactive
prompt remaining only when stdin is a terminal and none was given; and an existing instructions
file is kept unless ``--force``, instead of a ``y/N`` prompt that blocks every unattended run.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path, PurePosixPath
from typing import List, Optional, TextIO

from . import config, store, sync
from .paths import display, working_directory

TOOLS = {
    "copilot": ".github/copilot-instructions.md",
    "cursor": ".cursor/rules/cortex.mdc",
    "claude": "CLAUDE.md",
    "agents": "AGENTS.md",
}
ALIAS_PLACEHOLDER = b"<!-- @alias: my-project -->"
PERSONALITY_BEGIN = b"<!-- PERSONALITY:BEGIN -->"
PERSONALITY_END = b"<!-- PERSONALITY:END -->"


class InitError(Exception):
    pass


# --------------------------------------------------------------------------- #
# The files, byte for byte as setup.sh wrote them
# --------------------------------------------------------------------------- #

def instructions(template: bytes, personality: bool) -> bytes:
    """The instructions file: ``echo "$(cat template)"`` — trailing newlines trimmed, one added —
    with the personality block deleted as ``sed '/BEGIN/,/END/d'`` deletes it."""
    if not personality:
        kept, in_block = [], False
        for line in template.split(b"\n"):
            if in_block:
                in_block = PERSONALITY_END not in line
            elif PERSONALITY_BEGIN in line:
                in_block = True             # sed does not look for the end on the line that starts it
            else:
                kept.append(line)
        template = b"\n".join(kept)
    return template.rstrip(b"\n") + b"\n"


def with_alias(template: bytes, alias: str) -> bytes:
    """``sed "s|<!-- @alias: my-project -->|<!-- @alias: ALIAS -->|"`` — once per line."""
    marker = f"<!-- @alias: {alias} -->".encode("utf-8")
    return b"".join(line.replace(ALIAS_PLACEHOLDER, marker, 1) for line in template.splitlines(keepends=True))


def is_git_working_tree(directory: Path) -> bool:
    """``agents/`` is its own git working tree: it holds a ``.git`` — a directory, or the file a
    worktree or a submodule has. ``setup.sh`` asked ``git -C agents rev-parse``, which is also true
    of any ``agents/`` inside the project's own repository (ADR-008 §9)."""
    return (directory / ".git").exists()


def service_path(name: str) -> str:
    """A service is a folder of the workspace: relative, never climbing out of it."""
    path = PurePosixPath(name.replace("\\", "/"))
    if not name or path.is_absolute() or ".." in path.parts or (len(name) > 1 and name[1] == ":"):
        raise InitError(f"--service {name}: a service is a folder inside the workspace")
    return str(path)


def prompt_services(out: TextIO) -> List[str]:
    out.write("   Enter the names of the services to create (empty entry to stop):\n")
    names = []
    while True:
        out.write("   Service name (e.g. api-backend, front-web): ")
        out.flush()
        line = sys.stdin.readline()
        if not line or not line.strip():
            break
        names.append(line.rstrip("\r\n"))
    return names


# --------------------------------------------------------------------------- #
# The command
# --------------------------------------------------------------------------- #

def add_to_gitignore(root: Path, lines: List[str]) -> List[str]:
    path = root / ".gitignore"
    existing = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    missing = [line for line in lines if line not in (entry.strip() for entry in existing)]
    if missing:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        if text and not text.endswith("\n"):
            text += "\n"
        path.write_text(text + "".join(f"{line}\n" for line in missing), encoding="utf-8", newline="")
    return missing


def init(options: argparse.Namespace, cwd: str, out: TextIO, err: TextIO) -> None:
    root = Path(os.path.join(cwd, options.dir) if options.dir else cwd)
    root.mkdir(parents=True, exist_ok=True)
    root = Path(display(os.path.normpath(str(root))))
    personality = not options.no_personality
    theme = options.theme if personality else "none"
    mode = "link" if options.link else "copy" if options.copy else None

    if options.tool == "custom":
        if not options.instructions_file:
            raise InitError("--tool custom needs --instructions-file PATH")
        instructions_file = Path(os.path.join(cwd, options.instructions_file))
    else:
        if options.instructions_file:
            raise InitError("--instructions-file goes with --tool custom")
        instructions_file = root / TOOLS[options.tool]

    # Nothing is written before every refusal had its chance: a submodule or a clone at cortex/,
    # a theme the spec does not have.
    the_store = store.Store()
    existing_project = (root / config.PROJECT_FILE).is_file()
    project = config.load(str(root)) if existing_project else None
    sync.existing_entry(root / sync.LINK, the_store, project or _blank(root))
    # The version the project pins, or — for a new project, or one --force rewrites — this binary's.
    version = project.version if project and not options.force else the_store.own
    the_store.ensure(version)
    spec = the_store.path(version)
    if personality and not (spec / "agents" / "personalities" / theme).is_dir():
        themes = sorted(p.name for p in (spec / "agents" / "personalities").iterdir() if p.is_dir())
        raise InitError(f"theme '{theme}' is not in Cortex {version} — the themes are: {', '.join(themes)}")

    # cortex.toml, and what git must ignore
    if existing_project and not options.force:
        out.write(f"✓ {config.PROJECT_FILE} kept, at Cortex {version} — --force rewrites it\n")
    else:
        text = f'version = "{version}"\ntheme = "{theme}"\n'
        if mode:
            text += f'sync = "{mode}"\n'
        (root / config.PROJECT_FILE).write_text(
            "# Written by `cortex init`. Committed: the Cortex version this project uses, and the team's theme.\n"
            + text, encoding="utf-8", newline="")
        out.write(f"✓ {config.PROJECT_FILE}: Cortex {version}, theme {theme}\n")
    ignored = add_to_gitignore(root, [config.LOCAL_FILE] + ([f"/{sync.LINK}/"] if mode else []))
    if ignored:
        out.write(f"✓ .gitignore: {', '.join(ignored)}\n")

    # The spec, where the project finds it
    sync.sync(str(root), mode, None, out, err)

    templates = spec / "templates"
    workspace = options.workspace
    bootstrap = templates / ("bootstrap-instructions-workspace.md" if workspace else "bootstrap-instructions.md")
    if instructions_file.exists() and not options.force:
        out.write(f"✓ {display(str(instructions_file))} kept — --force replaces it\n")
    else:
        replaced = instructions_file.exists()
        instructions_file.parent.mkdir(parents=True, exist_ok=True)
        instructions_file.write_bytes(instructions(bootstrap.read_bytes(), personality))
        out.write(f"✓ {display(str(instructions_file))} {'replaced' if replaced else 'written'}\n")

    overview = (templates / "project-overview.md.template").read_bytes()
    context = (templates / "project-context.md.template").read_bytes()
    for name, content in (("project-overview.md", overview), ("project-context.md", context)):
        if not (root / name).exists():
            (root / name).write_bytes(content)
            out.write(f"✓ {name} written — fill it in\n")

    if workspace:
        names = options.service
        if not names and sys.stdin is not None and sys.stdin.isatty():
            names = prompt_services(out)
        for name in names:
            folder = root / service_path(name)
            folder.mkdir(parents=True, exist_ok=True)
            alias = PurePosixPath(service_path(name)).name
            for file, content in (("project-overview.md", overview), ("project-context.md", context)):
                if not (folder / file).exists():
                    (folder / file).write_bytes(with_alias(content, alias))
                    out.write(f"✓ {service_path(name)}/{file} — @{alias}\n")
        agents = root / "agents"
        if is_git_working_tree(agents):
            for file, content in (("project-overview.md", overview), ("project-context.md", context)):
                if not (agents / file).exists():
                    (agents / file).write_bytes(content)
                    out.write(f"✓ agents/{file} — the team's, agents/ is its own git repository (ADR-006)\n")
    out.write(f"\nCortex {version} is ready in {display(str(root))}.\n")


def _blank(root: Path) -> config.Project:
    """A project not initialised yet: nothing sync made can be at cortex/."""
    return config.Project(root=str(root), version=store.Store().own, theme="none", sync=None,
                          local_theme=None, spec=None)


def run(args: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="cortex init",
        description="Make a directory a Cortex project: its cortex.toml, the AI tool's instructions file, "
                    "project-overview.md and project-context.md — setup.sh, at parity (ADR-008 §3.7).")
    parser.add_argument("dir", nargs="?", metavar="DIR", help="the project's root (default: the current directory)")
    parser.add_argument("--theme", default="h2g2", help="the team's personality theme (default: h2g2)")
    parser.add_argument("--no-personality", action="store_true", help="no personality layer — wins over --theme")
    parser.add_argument("--workspace", action="store_true", help="multi-service workspace mode")
    parser.add_argument("--service", action="append", default=[], metavar="NAME",
                        help="a service of the workspace, a folder — repeatable; asked for when omitted on a terminal")
    parser.add_argument("--tool", default="copilot", choices=[*TOOLS, "custom"],
                        help="the AI tool: copilot (default), cursor, claude, agents, custom")
    parser.add_argument("--instructions-file", metavar="PATH", help="the instructions file of --tool custom")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--link", action="store_true", help="link cortex/ to the spec: cortex.toml's sync = \"link\"")
    modes.add_argument("--copy", action="store_true", help="copy the spec into cortex/: cortex.toml's sync = \"copy\"")
    parser.add_argument("--force", action="store_true", help="replace an existing instructions file and cortex.toml")
    options = parser.parse_args(args)
    if options.service and not options.workspace:
        parser.error("--service goes with --workspace")
    try:
        init(options, working_directory(), sys.stdout, sys.stderr)
    except (InitError, config.ConfigError, store.StoreError, sync.SyncError) as error:
        sys.stdout.flush()
        sys.stderr.write(f"cortex init: {error}\n")
        return 1
    return 0
