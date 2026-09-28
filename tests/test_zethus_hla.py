"""Tests for the HLA input-contract gate (`zethus/scripts/hla-input-check.py`): the target
High-Level Architecture document is a required pipeline input, and the default keep/wrap/port
stored-procedure disposition is read from it — never assumed. See
`zethus/docs/batch-modernization.md`.
"""
from __future__ import annotations

from tests.test_zethus import SCRIPTS, TempRepo, load, run

hla_mod = load(SCRIPTS / "hla-input-check.py")


class HlaInputCheck(TempRepo):
    def check(self, *argv):
        return run(hla_mod, "--repo", str(self.repo), *argv)

    def test_no_hla_configured_stops_and_asks(self):
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("no HLA document configured", out)

    def test_configured_but_missing_file_stops_and_asks(self):
        self.config({"modernization": {"hlaDoc": "docs/hla.md"}})
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("no such file", out)

    def test_hla_with_no_default_line_stops_and_asks(self):
        self.config({"modernization": {"hlaDoc": "docs/hla.md"}})
        self.write("docs/hla.md", "# Target architecture\n\nSpring Boot 3 + Spring Batch 5.\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("no parseable", out)

    def test_hla_with_default_disposition_passes(self):
        self.config({"modernization": {"hlaDoc": "docs/hla.md"}})
        self.write("docs/hla.md", "# Target architecture\n\n"
                                  "Default stored-procedure disposition: wrap\n\nMore prose.\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("= wrap", out)

    def test_label_and_disposition_word_are_both_case_insensitive(self):
        self.config({"modernization": {"hlaDoc": "docs/hla.md"}})
        self.write("docs/hla.md", "default STORED-PROCEDURE disposition: Port\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("= port", out)

    def test_unknown_disposition_word_stops_and_asks(self):
        self.config({"modernization": {"hlaDoc": "docs/hla.md"}})
        self.write("docs/hla.md", "Default stored-procedure disposition: rewrite\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)

    def test_explicit_hla_flag_overrides_config(self):
        self.config({"modernization": {"hlaDoc": "docs/wrong.md"}})
        self.write("docs/right.md", "Default stored-procedure disposition: keep\n")
        code, out = self.check("--hla", "docs/right.md")
        self.assertEqual(code, 0, out)
        self.assertIn("= keep", out)
