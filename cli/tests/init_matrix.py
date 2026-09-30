"""The parity matrix of ``cortex init`` (ADR-008 phase 4).

Each case is a throwaway project that ``cortex init`` sets up — services named by ``--service`` —
from a spec: this repository's, plus a second theme, ``acme``, for the case of a non-default
``--theme``. The spec is put in the command's store beforehand, at its own version.

``fixtures/init/expected.json`` holds, for each case, every file written in the project but the
command's own three — ``cortex.toml``, ``cortex.local.toml`` and ``.gitignore`` — and the theme.
Until phase 5 it was captured from the setup script of Cortex 0.x, and ``cortex init`` matched it
byte for byte across every case; the script is gone, and the matrix now holds what the command
writes. Any other byte is a failure.

Re-capture — only for a deliberate change of what ``cortex init`` writes, the bootstrap templates
included, and review the diff:

    cd cli && python3 -m tests.init_matrix --capture
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
EXPECTED = HERE / "fixtures" / "init" / "expected.json"
SPEC_TREES = ("agents", "templates", "docs")
OWN_FILES = ("cortex.toml", "cortex.local.toml", ".gitignore")
CAPTURE_VERSION = "9.9.9"

# name -> options, services, what the project holds before
CASES = {
    "single-copilot": ([], [], {}),
    "single-cursor": (["--tool", "cursor"], [], {}),
    "single-claude": (["--tool", "claude"], [], {}),
    "single-agents": (["--tool", "agents"], [], {}),
    "single-custom": (["--tool", "custom", "--instructions-file", "docs/ai/instructions.md"], [], {}),
    "single-no-personality": (["--tool", "claude", "--no-personality"], [], {}),
    "single-other-theme": (["--tool", "claude", "--theme", "acme"], [], {}),
    "single-files-already-there": (["--tool", "claude"], [], {
        "project-overview.md": "# Ours\n", "project-context.md": "# Our stack <!-- ex: keep -->\n"}),
    # A hand-written CLAUDE.md in a new project, no --tool: copilot's file is written, the other kept.
    "single-own-instructions-file": ([], [], {"CLAUDE.md": "# Our own notes\n"}),
    "workspace-copilot": (["--workspace"], [], {}),
    "workspace-services": (["--workspace", "--tool", "claude"], ["api", "core/web"], {}),
    "workspace-no-personality": (["--workspace", "--tool", "agents", "--no-personality"], ["api"], {}),
    "workspace-team-tier": (["--workspace", "--tool", "claude"], ["api"], {"agents/": "git"}),
    "workspace-service-already-there": (["--workspace", "--tool", "claude"], ["api"], {
        "api/project-overview.md": "# Our API\n"}),
}


def build_spec(tmp):
    """This repository's spec, and a second theme."""
    spec = tmp / "spec"
    for tree in SPEC_TREES:
        shutil.copytree(REPO / tree, spec / tree)
    acme = spec / "agents" / "personalities" / "acme"
    acme.mkdir()
    (acme / "theme.md").write_text("# Acme\n", encoding="utf-8")
    (acme / "characters.md").write_text("# Acme characters\n", encoding="utf-8")
    return spec


def prepare(project, files):
    project.mkdir(parents=True)
    for path, content in files.items():
        if content == "git":
            subprocess.run(["git", "init", "-q", str(project / path)], check=True)
        else:
            (project / path).parent.mkdir(parents=True, exist_ok=True)
            (project / path).write_text(content, encoding="utf-8", newline="")     # LF on Windows too


def snapshot(project, skip=("cortex",)):
    """Every file under ``project`` as text — its ``cortex/`` and git's own files aside."""
    files = {}
    for path in sorted(project.rglob("*")):
        rel = path.relative_to(project)
        if rel.parts[0] in skip or ".git" in rel.parts or not path.is_file():
            continue
        files[rel.as_posix()] = path.read_bytes().decode("utf-8")
    return files


def run_init(case, tmp, spec, run):
    """``cortex init`` in the project of ``case``, with ``spec`` in its store — ``run`` runs the
    command: ``run(args, cwd, env)``."""
    options, services, before = CASES[case]
    project = tmp / "init" / "project"
    prepare(project, before)
    home = tmp / "cortex-home"
    if not (home / "versions" / CAPTURE_VERSION).exists():
        shutil.copytree(spec, home / "versions" / CAPTURE_VERSION)
    env = dict(os.environ, CORTEX_HOME=str(home), CORTEX_SOURCE_VERSION=CAPTURE_VERSION)
    run([*options, *[arg for name in services for arg in ("--service", name)]], project, env)
    theme = next(line.split('"')[1] for line in (project / "cortex.toml").read_text(encoding="utf-8").splitlines()
                 if line.startswith("theme = "))
    return {"files": snapshot(project, skip=("cortex", *OWN_FILES)), "active_theme": theme}


def _source(args, cwd, env):
    call = ("import sys; sys.path[:0] = [sys.argv.pop(1), sys.argv.pop(1)]; "
            "from cortex_cli.main import main; sys.exit(main())")
    subprocess.run([sys.executable, "-I", "-S", "-c", call, str(REPO / "core"), str(REPO / "cli"), "init", *args],
                   cwd=cwd, env=env, capture_output=True, check=True, stdin=subprocess.DEVNULL)


def capture():
    expected = {}
    for case in CASES:
        tmp = Path(tempfile.mkdtemp(prefix="cortex-init-"))
        try:
            expected[case] = run_init(case, tmp, build_spec(tmp), _source)
        finally:
            for directory, subdirs, files in os.walk(tmp):
                for name in subdirs + files:
                    os.chmod(os.path.join(directory, name), 0o700)
            shutil.rmtree(tmp, ignore_errors=True)
    EXPECTED.parent.mkdir(parents=True, exist_ok=True)
    EXPECTED.write_text(json.dumps(expected, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return expected


if __name__ == "__main__":
    if sys.argv[1:] != ["--capture"]:
        sys.exit("usage: python3 -m tests.init_matrix --capture")
    captured = capture()
    print(f"captured {len(captured)} cases into {EXPECTED}")
