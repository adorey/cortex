"""``cortex init`` — ``setup.sh``, at parity (ADR-008 §3.7).

Same options, same defaults (``--theme h2g2``, ``--tool copilot``), same files at the same paths
as ``setup.sh``: the tool's instructions file, the root ``project-overview.md`` and
``project-context.md`` when missing, and in workspace mode a pair per service carrying its
``@alias`` — the basename of its folder — plus the team tier when ``agents/`` is its own git
working tree. The files are written byte for byte as the script wrote them, from the templates of
the version the project pins, in the store.

It also writes ``cortex.toml`` at the binary's own version, adds ``cortex.local.toml`` to
``.gitignore`` — and ``/cortex`` in ``link`` and ``copy`` modes — then runs ``cortex sync``. In a
project that has one, ``cortex.toml`` keeps its version, and changes only for the options given:
``--theme`` or ``--no-personality``, ``--link`` or ``--copy``.

Two deliberate differences: services are named by a repeatable ``--service``, the interactive
prompt remaining only when stdin is a terminal and none was given; and an existing instructions
file is kept unless ``--force``, instead of a ``y/N`` prompt that blocks every unattended run —
``--force`` keeps the file it replaces as ``FILE.bak``.

Everything is checked before anything of the project is written: a refusal leaves it as it was.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Dict, List, TextIO

from cortex_core.project import is_theme

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
    """A service is a folder of the workspace: relative, never climbing out of it. A backslash
    separates folders on Windows only: elsewhere it is a character of the name."""
    path = PurePosixPath(name.replace("\\", "/") if os.name == "nt" else name)
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
        names.append(line.strip())
    return names


# --------------------------------------------------------------------------- #
# The command
# --------------------------------------------------------------------------- #

def add_to_gitignore(root: Path, entries: Dict[str, str]) -> List[str]:
    """Add to ``.gitignore`` each line of ``entries`` whose path — its value — git does not ignore
    yet, and return them. The file keeps its bytes: its encoding, its byte order mark, its line
    endings. Without a repository to ask, a line is added unless it, or one that means the same,
    is there."""
    path = root / ".gitignore"
    data = path.read_bytes() if path.is_file() else b""
    present = {line.strip().lstrip("\ufeff") for line in data.decode("utf-8", errors="replace").splitlines()}
    missing = []
    for line, probe in entries.items():
        state = sync.ignored(root, probe)
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


def _refuse_instructions_file(root: Path, path: Path) -> None:
    """``--instructions-file`` names the tool's file: never a directory, never a file cortex init
    writes for itself, never the spec."""
    if path.is_dir():
        raise InitError(f"--instructions-file {display(str(path))}: a directory")
    own = {os.path.normcase(os.path.abspath(root / name)) for name in
           (config.PROJECT_FILE, config.LOCAL_FILE, ".gitignore", "project-overview.md", "project-context.md")}
    target = os.path.normcase(os.path.abspath(path))
    spec = os.path.normcase(os.path.abspath(root / sync.LINK))
    if target in own or target.startswith(spec + os.sep):
        raise InitError(f"--instructions-file {display(str(path))}: a file cortex init writes for itself — "
                        "name the tool's instructions file")


def _services(options: argparse.Namespace, root: Path, out: TextIO, err: TextIO) -> List[str]:
    """The workspace's services, checked: each a folder inside it, none an existing file."""
    names = list(options.service)
    if options.workspace and not names:
        if sys.stdin is not None and sys.stdin.isatty():
            names = prompt_services(out)
        else:
            err.write("note: no service created — --service NAME adds one; names are asked for on a terminal only\n")
    for name in names:
        folder = root / service_path(name)
        if folder.exists() and not folder.is_dir():
            raise InitError(f"--service {name}: {display(str(folder))} is a file, not a folder")
    return [service_path(name) for name in names]


def init(options: argparse.Namespace, cwd: str, out: TextIO, err: TextIO) -> None:
    root = Path(display(os.path.normpath(os.path.join(cwd, options.dir) if options.dir else cwd)))
    personality = not options.no_personality
    theme = options.theme if personality else "none"
    mode = "link" if options.link else "copy" if options.copy else None

    # Everything is checked before anything of the project is written: its instructions file,
    # its services, its theme, its cortex.toml, what is at cortex/.
    if options.tool == "custom":
        if not options.instructions_file:
            raise InitError("--tool custom needs --instructions-file PATH")
        instructions_file = Path(os.path.join(cwd, options.instructions_file))
        _refuse_instructions_file(root, instructions_file)
    else:
        if options.instructions_file:
            raise InitError("--instructions-file goes with --tool custom")
        instructions_file = root / TOOLS[options.tool]
    if theme is not None and not is_theme(theme):
        raise InitError(f'--theme {theme}: no theme name — letters, digits, ".", "_" and "-"')
    services = _services(options, root, out, err) if options.workspace else []

    the_store = store.Store()
    existing_project = (root / config.PROJECT_FILE).is_file()
    try:
        project = config.load(str(root)) if existing_project else None
    except config.ConfigError as error:
        raise InitError(f"{error}\ncortex init keeps an existing {config.PROJECT_FILE}: fix it, or remove it to "
                        "start over")
    sync.existing_entry(root / sync.LINK, the_store, project or _blank(root))
    # A project keeps the version it pins — never another, older or newer; a new one takes this
    # binary's. A version newer than this binary is refused here.
    version = project.version if project else the_store.own
    the_store.ensure(version)
    spec = the_store.path(version)
    if project is None and theme is None:
        theme = "h2g2"
    if theme not in (None, "none") and not (spec / "agents" / "personalities" / theme).is_dir():
        themes = sorted(p.name for p in (spec / "agents" / "personalities").iterdir() if p.is_dir())
        raise InitError(f"theme '{theme}' is not in Cortex {version} — the themes are: {', '.join(themes)}")
    # cortex.toml: a new one, or only the keys the options name.
    if project is None:
        values = {"version": str(version), "theme": theme, **({"sync": mode} if mode else {})}
    else:
        values = {**({"theme": theme} if theme is not None and theme != project.theme else {}),
                  **({"sync": mode} if mode and mode != project.sync else {})}
    project_text = config.render_project(str(root), values) if values else None
    personality = (theme if theme is not None else project.theme) != "none"

    # Now the writes.
    root.mkdir(parents=True, exist_ok=True)
    if project_text is not None:
        config.write_text(str(root / config.PROJECT_FILE), project_text)
    if project is None:
        out.write(f"✓ {config.PROJECT_FILE}: Cortex {version}, theme {theme}\n")
    elif values:
        shown = ", ".join(f"{key} = {config.toml_value(value)}" for key, value in values.items())
        out.write(f"✓ {config.PROJECT_FILE}: {shown} — the rest kept, at Cortex {version}\n")
    else:
        out.write(f"✓ {config.PROJECT_FILE} kept, at Cortex {version}\n")
    spec_mode = mode or (project.sync if project else None)
    entries = {config.LOCAL_FILE: config.LOCAL_FILE}
    if spec_mode in ("link", "copy"):
        # A link is a file to git: `cortex/` would not match it. `/cortex` matches the link and the copy.
        entries[f"/{sync.LINK}"] = sync.LINK if spec_mode == "link" else f"{sync.LINK}/"
    ignored = add_to_gitignore(root, entries)
    if ignored:
        out.write(f"✓ .gitignore: {', '.join(ignored)}\n")
    if sync.ignored(root, config.LOCAL_FILE) is None:
        err.write(f"note: {display(str(root))} is in no git repository: {config.PROJECT_FILE} is committed nowhere, "
                  "and .gitignore does nothing here. Where the workspace root is no repository (ADR-006, 2.B), each "
                  "developer runs cortex init in their own, and pins the version of their own cortex (ADR-008 §9).\n")

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
        if replaced:
            backup = instructions_file.with_name(instructions_file.name + ".bak")
            os.replace(instructions_file, backup)
            out.write(f"✓ {display(str(backup))}: the file --force replaces, as it was\n")
        instructions_file.write_bytes(instructions(bootstrap.read_bytes(), personality))
        out.write(f"✓ {display(str(instructions_file))} {'replaced' if replaced else 'written'}\n")

    overview = (templates / "project-overview.md.template").read_bytes()
    context = (templates / "project-context.md.template").read_bytes()
    for name, content in (("project-overview.md", overview), ("project-context.md", context)):
        if not (root / name).exists():
            (root / name).write_bytes(content)
            out.write(f"✓ {name} written — fill it in\n")

    if workspace:
        for name in services:
            folder = root / name
            folder.mkdir(parents=True, exist_ok=True)
            alias = PurePosixPath(name).name
            for file, content in (("project-overview.md", overview), ("project-context.md", context)):
                if not (folder / file).exists():
                    (folder / file).write_bytes(with_alias(content, alias))
                    out.write(f"✓ {name}/{file} — @{alias}\n")
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
    parser.add_argument("--theme", help="the team's personality theme (default: h2g2, or the one cortex.toml names)")
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
    parser.add_argument("--force", action="store_true",
                        help="replace an existing instructions file, kept as FILE.bak — cortex.toml changes only "
                             "for the options given")
    options = parser.parse_args(args)
    if options.service and not options.workspace:
        parser.error("--service goes with --workspace")
    try:
        init(options, working_directory(), sys.stdout, sys.stderr)
    except (InitError, config.ConfigError, store.StoreError, sync.SyncError) as error:
        return sync.failed("cortex init", str(error))
    except OSError as error:
        return sync.failed("cortex init", sync.os_error(error))
    except subprocess.CalledProcessError as error:
        return sync.failed("cortex init", f"{' '.join(map(str, error.cmd))} failed: "
                                          f"{(error.stderr or b'').decode(errors='replace').strip() or error.returncode}")
    return 0
