"""Tiny ANSI colour helper — Ceryce's brand palette, stdlib-only.

Primary is **Kumouri Purple** ``#8e00ff``; the accent is **Toxic Green** ``#00ff0f``. Colour is
auto-disabled when output is not a TTY, when ``NO_COLOR`` is set, or ``TERM=dumb`` (``FORCE_COLOR``
overrides). On Windows it best-effort enables virtual-terminal processing so the escapes render in
older consoles. Everything degrades to plain text, so piped/redirected/test output stays clean.
"""
from __future__ import annotations

import os
import sys

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"

# 24-bit truecolor brand palette
PURPLE = "\x1b[38;2;142;0;255m"   # #8e00ff — Kumouri Purple (primary)
GREEN = "\x1b[38;2;0;255;15m"     # #00ff0f — Toxic Green (accent)
RED = "\x1b[38;2;255;92;92m"      # readable error red (not a brand colour; used sparingly)


def _enable_windows_vt() -> bool:
    """Best-effort enable ANSI/VT processing on Windows consoles. No-op elsewhere."""
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        return bool(kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING))
    except Exception:
        return False


def should_color(stream=None) -> bool:
    if "NO_COLOR" in os.environ:
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    stream = stream if stream is not None else sys.stdout
    try:
        if not stream.isatty():
            return False
    except Exception:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return _enable_windows_vt()


class Palette:
    """Colourises text when enabled; returns it unchanged otherwise."""

    def __init__(self, enabled: bool):
        self.enabled = bool(enabled)

    def _wrap(self, code: str, text: str) -> str:
        return f"{code}{text}{RESET}" if self.enabled else text

    def title(self, text: str) -> str:   # section headers, banner
        return self._wrap(BOLD + PURPLE, text)

    def label(self, text: str) -> str:   # prompt labels
        return self._wrap(PURPLE, text)

    def value(self, text: str) -> str:   # defaults, options, chosen values
        return self._wrap(GREEN, text)

    def ok(self, text: str) -> str:      # success lines
        return self._wrap(BOLD + GREEN, text)

    def dim(self, text: str) -> str:     # help / secondary text
        return self._wrap(DIM, text)

    def warn(self, text: str) -> str:    # inline validation hints / errors
        return self._wrap(RED, text)


def palette(enabled=None) -> Palette:
    """A Palette, auto-detecting colour support unless ``enabled`` is given explicitly."""
    return Palette(should_color() if enabled is None else enabled)
