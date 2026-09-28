"""Tests for the web-app HLA input-contract gate (`zethus/scripts/webapp-hla-input-check.py`): the
target frontend and auth strategy are both required pipeline inputs read from the HLA, neither with
a hardcoded default. See `zethus/docs/webapp-modernization.md`.
"""
from __future__ import annotations

from tests.test_zethus import SCRIPTS, TempRepo, load, run

hla_mod = load(SCRIPTS / "webapp-hla-input-check.py")


class WebappHlaInputCheck(TempRepo):
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

    def test_no_frontend_line_stops_and_asks_with_no_default(self):
        self.config({"modernization": {"hlaDoc": "docs/hla.md"}})
        self.write("docs/hla.md", "# Target architecture\n\nAuth strategy: shim\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("names no frontend", out)
        self.assertIn("no hardcoded default", out)

    def test_no_auth_strategy_line_stops_and_asks_recommending_shim(self):
        self.config({"modernization": {"hlaDoc": "docs/hla.md"}})
        self.write("docs/hla.md", "# Target architecture\n\nFrontend: Angular\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("no parseable 'Auth strategy", out)
        self.assertIn("Recommend: shim first", out)

    def test_both_missing_reports_both_gaps(self):
        self.config({"modernization": {"hlaDoc": "docs/hla.md"}})
        self.write("docs/hla.md", "# Target architecture\n\nSome unrelated prose.\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("names no frontend", out)
        self.assertIn("no parseable 'Auth strategy", out)

    def test_unknown_auth_strategy_word_stops_and_asks(self):
        self.config({"modernization": {"hlaDoc": "docs/hla.md"}})
        self.write("docs/hla.md", "Frontend: React + TypeScript + Vite\nAuth strategy: rewrite\n")
        code, out = self.check()
        self.assertEqual(code, 1, out)

    def test_both_present_passes(self):
        self.config({"modernization": {"hlaDoc": "docs/hla.md"}})
        self.write("docs/hla.md", "# Target architecture\n\nFrontend: Angular\n"
                                  "Auth strategy: shim\n\nMore prose.\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("frontend = 'Angular'", out)
        self.assertIn("auth strategy = shim", out)

    def test_labels_and_words_are_case_insensitive(self):
        self.config({"modernization": {"hlaDoc": "docs/hla.md"}})
        self.write("docs/hla.md", "FRONTEND: React\nAUTH STRATEGY: Replace\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("auth strategy = replace", out)

    def test_explicit_hla_flag_overrides_config(self):
        self.config({"modernization": {"hlaDoc": "docs/wrong.md"}})
        self.write("docs/right.md", "Frontend: Next.js\nAuth strategy: shim\n")
        code, out = self.check("--hla", "docs/right.md")
        self.assertEqual(code, 0, out)
        self.assertIn("frontend = 'Next.js'", out)

    def test_frontend_is_free_text_any_name_is_honored(self):
        self.config({"modernization": {"hlaDoc": "docs/hla.md"}})
        self.write("docs/hla.md", "Frontend: Vue 3 + Vite\nAuth strategy: shim\n")
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("frontend = 'Vue 3 + Vite'", out)
