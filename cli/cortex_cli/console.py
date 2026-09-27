"""The command's two streams, the same on every platform (ADR-008 §3.1).

UTF-8 whatever the console's code page, ``\\n`` line endings where Windows would write
``\\r\\n``, and colours a Windows console shows instead of printing their escape codes.
"""

from __future__ import annotations

import os
import signal
import sys


def setup() -> None:
    # A reader that goes away — `cortex validate | head` — ends the run by SIGPIPE, in silence,
    # as a shell command's does, not with a BrokenPipeError and its traceback.
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    for stream, errors in ((sys.stdout, "surrogateescape"), (sys.stderr, "backslashreplace")):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors=errors, newline="\n")
    if os.name == "nt":
        _enable_virtual_terminal()


def _enable_virtual_terminal() -> None:
    """Let a Windows console interpret ANSI colour codes — it prints them otherwise. Nothing
    changes when a stream is no console: the validator writes colours to a terminal only."""
    import ctypes

    kernel32 = ctypes.windll.kernel32
    for handle_id in (-11, -12):                      # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
        handle = kernel32.GetStdHandle(handle_id)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)   # ENABLE_VIRTUAL_TERMINAL_PROCESSING


def stdin_is_terminal() -> bool:
    """Whether someone can answer a question: stdin is a terminal. On Windows ``isatty`` also says
    yes of ``NUL`` — stdin closed, an unattended run — which is a character device, not a console:
    only a console handle has a console mode."""
    stdin = sys.stdin
    if stdin is None or not stdin.isatty():
        return False
    if os.name != "nt":
        return True
    import ctypes
    import msvcrt

    mode = ctypes.c_ulong()
    return bool(ctypes.windll.kernel32.GetConsoleMode(msvcrt.get_osfhandle(stdin.fileno()), ctypes.byref(mode)))
