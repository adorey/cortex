"""The parity matrix of ``cortex init`` — what ``setup.sh`` writes, captured (ADR-008 phase 4).

Each case is a throwaway project, set up once by ``setup.sh`` and once by ``cortex init`` with the
same options — services on the script's stdin, named by ``--service`` for the command. Both read
the same spec: this repository's, plus a second theme, ``acme``, for the case of a non-default
``--theme``. ``setup.sh`` finds it in the project's ``cortex/``; ``cortex init`` in its store.

``fixtures/init/expected.json`` holds, for each case, every file ``setup.sh`` wrote in the project
and the theme it wrote in its marker, ``cortex/agents/personalities/.active-theme``. ``cortex init``
writes no marker — the theme goes to ``cortex.toml`` — and three files the script did not:
``cortex.toml``, ``cortex.local.toml`` and ``.gitignore``. That is the one difference the matrix
records; any other byte is a failure.

Re-capture — only for a deliberate change of what ``setup.sh`` writes, and review the diff:

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
        shutil.copytree(REPO / tree, spec / tree, ignore=shutil.ignore_patterns(".active-theme"))
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


def run_setup(case, tmp, spec):
    """``setup.sh`` in a project that carries the spec at ``cortex/``, as a submodule would."""
    options, services, before = CASES[case]
    project = tmp / "setup" / "project"
    prepare(project, before)
    shutil.copytree(spec, project / "cortex")
    shutil.copy(REPO / "setup.sh", project / "cortex" / "setup.sh")
    stdin = "".join(f"{name}\n" for name in services)
    subprocess.run(["bash", str(project / "cortex" / "setup.sh"), *options], cwd=project, input=stdin.encode(),
                   capture_output=True, check=True)
    marker = project / "cortex" / "agents" / "personalities" / ".active-theme"
    return {"files": snapshot(project), "active_theme": marker.read_text(encoding="utf-8").strip()}


def capture():
    expected = {}
    for case in CASES:
        tmp = Path(tempfile.mkdtemp(prefix="cortex-init-"))
        try:
            expected[case] = run_setup(case, tmp, build_spec(tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    EXPECTED.parent.mkdir(parents=True, exist_ok=True)
    EXPECTED.write_text(json.dumps(expected, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return expected


if __name__ == "__main__":
    if sys.argv[1:] != ["--capture"]:
        sys.exit("usage: python3 -m tests.init_matrix --capture")
    captured = capture()
    print(f"captured {len(captured)} cases into {EXPECTED}")
