"""Golden fixtures for the overlay validator — ADR-007 phase 2.

Each case under ``fixtures/validator/cases/`` becomes a throwaway host project: the shared
base goes to ``{project}/cortex/agents/``, the case's own files on top. ``expected.json`` was
captured from the Bash implementation of ``bin/validate-overlays.sh`` (Cortex 0.9.0), before it
became a shim, then re-captured deliberately for each behaviour change of ADR-007 phase 4 —
``missing-header`` and ``header-after-line-10`` (#76), the ``absent-*`` cases (#81), the projects
inside a directory named ``agents`` or ``cortex`` and ``scope-workspace-in-service-shallow`` (#84),
the workspace's ``── Scope: . ──`` header, ``escape-in-field`` and ``control-char-in-field`` (#85).
The core must reproduce it byte for byte, the temporary directory aside.

A case may carry a ``case.json``:

- ``project`` — where the project root sits under the temporary directory (default ``host``);
- ``runs`` — the argument lists to run it with (default: none, then ``--strict``); ``{project}``
  in an argument stands for the project root, for an absolute path;
- ``crlf`` — files to rewrite with CRLF line endings at layout time (git keeps them LF).

Every run happens under ``LC_ALL=C``. The port reads bytes and ASCII character classes the way
the script's grep and sed did in the C locale; under a UTF-8 locale they also took Unicode
spaces for spaces (``unicode-space-in-field``). Pinning the locale measures the script in the
one the port reproduces, whatever the machine running the tests (ADR-007 §9).

Re-capturing now records what the core prints, through the shim. Do it only for a deliberate
change of the validator's behaviour, and review the diff of ``expected.json`` line by line:

    cd core && python3 -m tests.validator_harness --capture
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "validator"
CORE = HERE.parent
REPO = CORE.parent
SCRIPT = REPO / "bin" / "validate-overlays.sh"
EXPECTED = FIXTURES / "expected.json"
DEFAULT_RUNS = [[], ["--strict"]]


def cases():
    return sorted(p.name for p in (FIXTURES / "cases").iterdir() if p.is_dir())


def config(case):
    path = FIXTURES / "cases" / case / "case.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def runs(case):
    return config(case).get("runs", DEFAULT_RUNS)


def run_key(args):
    return " ".join(args) or "default"


def layout(case, tmp):
    """Build the host project of ``case`` under ``tmp`` and return its root."""
    cfg = config(case)
    project = tmp / cfg.get("project", "host")
    shutil.copytree(FIXTURES / "base", project / "cortex")
    source = FIXTURES / "cases" / case
    for src in sorted(source.rglob("*")):
        if src.is_file() and src.name != "case.json":
            dst = project / src.relative_to(source)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
    for rel in cfg.get("crlf", []):
        path = project / rel
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    return project


def _run(cmd, env=None):
    env = dict(os.environ if env is None else env, LC_ALL="C")
    proc = subprocess.run(cmd, capture_output=True, env=env)
    return proc.returncode, proc.stdout, proc.stderr


def run_script(project, args):
    """The validator as host projects run it: ``{project}/cortex/bin/validate-overlays.sh``, with
    the core it runs from at ``{project}/cortex/core`` — where a Cortex checkout has it."""
    bin_dir = project / "cortex" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPT, bin_dir / SCRIPT.name)
    shutil.copytree(CORE / "cortex_core", project / "cortex" / "core" / "cortex_core",
                    ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    return _run(["bash", str(bin_dir / SCRIPT.name), *args])


def run_core(project, args):
    """The Python port, from the core's source, given the two roots the script derives — as the
    script hands them to it, ahead of the options."""
    env = dict(os.environ, PYTHONPATH=str(CORE))
    return _run([sys.executable, "-m", "cortex_core.validate", str(project), str(project / "cortex"), *args], env=env)


def execute(case, args, runner):
    tmp = Path(tempfile.mkdtemp(prefix="cortex-validator-"))
    # A case that puts its project inside a directory named "agents" or "cortex" says so with
    # "project": the temporary directory itself must contain neither, so that no other case does.
    assert "/agents/" not in f"{tmp}/" and "/cortex/" not in f"{tmp}/", tmp
    try:
        project = layout(case, tmp)
        code, out, err = runner(project, [arg.replace("{project}", str(project)) for arg in args])
        norm = lambda b: b.decode("utf-8", "surrogateescape").replace(str(tmp), "<TMP>").split("\n")
        return {"code": code, "stdout": norm(out), "stderr": norm(err)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def capture():
    expected = {case: {run_key(a): execute(case, a, run_script) for a in runs(case)} for case in cases()}
    EXPECTED.write_text(json.dumps(expected, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return expected


if __name__ == "__main__":
    if sys.argv[1:] != ["--capture"]:
        sys.exit("usage: python3 -m tests.validator_harness --capture")
    captured = capture()
    print(f"captured {sum(len(r) for r in captured.values())} runs of {len(captured)} cases into {EXPECTED}")
