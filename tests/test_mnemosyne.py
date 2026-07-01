"""CI coverage for the mnemosyne reflexion-memory engine.

Wraps mnemosyne's own zero-dependency self-test into the repo unittest suite, plus a couple of
lightweight checks that the bundled configs load and the public API round-trips on a temp repo.
"""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MNEMOSYNE_SRC = REPO / "mnemosyne" / "src"

if str(MNEMOSYNE_SRC) not in sys.path:
    sys.path.insert(0, str(MNEMOSYNE_SRC))


class MnemosyneSelfTest(unittest.TestCase):
    def test_selftest_passes(self):
        from mnemosyne.cli import run_selftest

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = run_selftest()
        self.assertEqual(rc, 0, msg="mnemosyne selftest failed:\n" + buf.getvalue())
        self.assertIn("ALL PASS", buf.getvalue())


class BundledConfigs(unittest.TestCase):
    def test_default_and_software_eng_load(self):
        from mnemosyne.config import load_named_example

        default = load_named_example("default")
        self.assertEqual(default.axis_names, ["tags"])

        se = load_named_example("software-eng")
        self.assertIn("components", se.axis_names)
        self.assertIn("endpoint_patterns", se.axis_names)


class PublicApiRoundTrip(unittest.TestCase):
    def test_capture_then_recall(self):
        import mnemosyne as mn

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "memory").mkdir()
            saved = mn.capture(
                "Prefer feature flags for risky rollouts",
                "Wrap risky changes behind a feature flag and roll out gradually.",
                confidence="high", tags="feature-flag,rollback", repo=d,
            )
            self.assertEqual(saved["action"], "saved")

            hits = mn.recall("how should we do a risky rollout?", repo=d)
            self.assertTrue(any(h["id"] == saved["id"] for h in hits))


if __name__ == "__main__":
    unittest.main()
