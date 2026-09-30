"""The command's two streams, the same on every platform (ADR-008 §3.1).

UTF-8 whatever the console's code page, ``\\n`` line endings where Windows would write
``\\r\\n``, and colours a Windows console shows instead of printing their escape codes.
"""

from __future__ import annotations

import os
import sys


def setup() -> None:
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
