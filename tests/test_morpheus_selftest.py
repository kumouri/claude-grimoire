"""CI coverage: wrap morpheus's CLI self-test into the unittest suite (parity with mnemosyne)."""
import io
import unittest
from contextlib import redirect_stdout

from tests._util import PKG  # noqa: F401  (ensures morpheus/src on sys.path)


class MorpheusSelfTest(unittest.TestCase):
    def test_selftest_passes(self):
        from morpheus.cli import run_selftest

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = run_selftest()
        self.assertEqual(rc, 0, msg="morpheus selftest failed:\n" + buf.getvalue())
        self.assertIn("ALL PASS", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
