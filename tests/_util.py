"""Shared test helpers for the morpheus suite: make the package importable and
provide a temp Claude/morpheus home so tests never touch the real ~/.claude.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "morpheus" / "src"          # import root: `import morpheus...`
PKG = SRC / "morpheus"                    # package dir (dispatch.py lives here)
FIXTURES = Path(__file__).resolve().parent / "fixtures"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class TempHomeTest(unittest.TestCase):
    """Base class that isolates CLAUDE_CONFIG_DIR and the morpheus home."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self._saved = {k: os.environ.get(k) for k in (
            "CLAUDE_CONFIG_DIR", "CLAUDE_MORPHEUS_HOME", "CLAUDE_MORPHEUS_CONFIG",
            "CLAUDE_MORPHEUS", "CLAUDE_CODE_CHILD_SESSION", "CLAUDE_MORPHEUS_NOSPAWN",
        )}
        os.environ["CLAUDE_CONFIG_DIR"] = str(self.home / ".claude")
        os.environ["CLAUDE_MORPHEUS_HOME"] = str(self.home / "morpheus")
        os.environ.pop("CLAUDE_MORPHEUS", None)
        os.environ.pop("CLAUDE_CODE_CHILD_SESSION", None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()
