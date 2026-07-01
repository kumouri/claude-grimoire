"""Shared test helpers: ensure the dreaming package is importable and provide a
temp Claude/dreaming home so tests never touch the real ~/.claude.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PKG = REPO / "hooks" / "dreaming"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Make `lib` / `engines` importable even without PYTHONPATH set.
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))


class TempHomeTest(unittest.TestCase):
    """Base class that isolates CLAUDE_CONFIG_DIR and the dreaming home."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self._saved = {k: os.environ.get(k) for k in (
            "CLAUDE_CONFIG_DIR", "CLAUDE_DREAMING_HOME", "CLAUDE_DREAMING_CONFIG",
            "CLAUDE_DREAMING", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_DREAMING_NOSPAWN",
        )}
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.home / ".claude")
        os.environ["CLAUDE_DREAMING_HOME"] = str(self.home / "dreaming")
        os.environ.pop("CLAUDE_DREAMING", None)
        os.environ.pop("CLAUDE_CODE_CHILD_SESSION", None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()
