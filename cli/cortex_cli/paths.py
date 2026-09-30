"""Paths as the user names them (ADR-008 §3.1)."""

from __future__ import annotations

import os


def working_directory() -> str:
    """The current directory as the user's shell names it — ``$PWD``, when that is this
    directory — rather than resolved through its links, as ``getcwd`` gives it.

    On macOS the temporary directories are behind a link, ``/var`` to ``/private/var``: resolved,
    the project root would no longer be a prefix of the paths the user types — ``--service
    $PWD/api`` — and the report would print them whole. ``$PWD`` naming another directory, or
    none — a process not started by a shell — leaves ``getcwd``'s answer.
    """
    cwd = os.getcwd()
    pwd = os.environ.get("PWD")
    if pwd and os.path.isabs(pwd):
        try:
            if os.path.samefile(pwd, cwd):
                return pwd
        except OSError:
            pass
    return cwd


def display(path: str) -> str:
    """``path`` with ``/`` on every platform (ADR-008 §3.1) — Windows accepts it, and it is how
    paths are printed and written in ``cortex.local.toml``."""
    return path.replace(os.sep, "/") if os.sep != "/" else path
