"""The ``cortex`` command line (ADR-008).

The command behaves the same under either of its names, ``cortex`` or ``cortex-ai`` (§3.1):
nothing here reads the name it was called by.
"""

from __future__ import annotations

import sys
from typing import Callable, Dict, List, Optional, Tuple

from . import console
from .version import VERSION

# name -> (summary, handler). Handlers import their module when called — statically, so that
# PyInstaller sees every module the binary needs.
def _validate(args: List[str]) -> int:
    from . import validate

    return validate.run(args)


COMMANDS: Dict[str, Tuple[str, Callable[[List[str]], int]]] = {
    "validate": ("Check the project's overlays against the spec (ADR-001)", _validate),
}


def usage() -> str:
    commands = "".join(f"  {name:<10} {summary}\n" for name, (summary, _) in COMMANDS.items())
    return ("Usage: cortex <command> [options]\n\n"
            + (f"Commands:\n{commands}\n" if commands else "")
            + "Options:\n"
              "  -V, --version   Print the version and exit\n"
              "  -h, --help      Show this help and exit\n\n"
              "`cortex <command> --help` shows the options of a command.\n")


def main(argv: Optional[List[str]] = None) -> int:
    console.setup()
    args = sys.argv[1:] if argv is None else list(argv)
    if not args:
        sys.stderr.write(usage())
        return 2
    command, rest = args[0], args[1:]
    if command in ("-h", "--help"):
        sys.stdout.write(usage())
        return 0
    if command in ("-V", "--version"):
        if rest:
            sys.stderr.write(f"cortex: unknown option '{rest[0]}' for --version\n")
            return 2
        sys.stdout.write(f"cortex {VERSION}\n")
        return 0
    if command not in COMMANDS:
        sys.stderr.write(f"cortex: unknown command '{command}'\n\n{usage()}")
        return 2
    sys.stdout.flush()
    return COMMANDS[command][1](rest)
