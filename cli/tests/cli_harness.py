"""How the CLI's tests run the ``cortex`` command.

From source by default: the interpreter running the tests, under ``-I -S``, with nothing but
``core/`` and ``cli/`` on ``sys.path`` — no working directory, no ``PYTHONPATH``, no
site-packages. With ``CORTEX_TEST_BINARY`` naming a built binary, the same tests run through it
instead (ADR-008 phase 1), and ``CORTEX_TEST_VERSION``, when set, is the version it must print.

Either way the command runs with a ``PATH`` that holds one empty directory: the binary must need
no Python on the host, and nothing else from ``PATH`` either.
"""

import atexit
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CLI = Path(__file__).resolve().parents[1]
REPO = CLI.parent
CORE = REPO / "core"
BINARY = os.environ.get("CORTEX_TEST_BINARY") or None
EXPECTED_VERSION = os.environ.get("CORTEX_TEST_VERSION") or None
SOURCE_CALL = ("import sys; sys.path[:0] = [sys.argv.pop(1), sys.argv.pop(1)]; "
               "from cortex_cli.main import main; sys.exit(main())")

# What the command may see of the environment: what an operating system needs to start a
# process, and where a user's files and temporary files are.
_KEPT = ("SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "LOCALAPPDATA")
_EMPTY_PATH = tempfile.mkdtemp(prefix="cortex-empty-path-")
atexit.register(shutil.rmtree, _EMPTY_PATH, ignore_errors=True)


def command(*args):
    if BINARY:
        return [BINARY, *args]
    return [sys.executable, "-I", "-S", "-c", SOURCE_CALL, str(CORE), str(CLI), *args]


def environment(**extra):
    env = {name: os.environ[name] for name in _KEPT if name in os.environ}
    env["PATH"] = _EMPTY_PATH
    env.update(extra)
    return env


def run(*args, cwd=None, env=None, stdin=subprocess.DEVNULL):
    """Run ``cortex ARGS`` and return the completed process, its output as bytes."""
    return subprocess.run(command(*args), cwd=cwd, env=environment() if env is None else env,
                          stdin=stdin, capture_output=True)
