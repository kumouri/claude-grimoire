"""Tests for the web-app extension's two additions to the overseer (`zethus/scripts/overseer-gate.py`):
``session-state`` (a flow can't be marked migrated while any session attribute is unclassified or
still read from HttpSession by the new code) and ``http-fixtures`` (HTTP-shaped golden-master
fixtures have the fields a replay needs, and none looks like it captured real user data). See
`zethus/docs/webapp-modernization.md`.
"""
from __future__ import annotations

import json

from tests.test_zethus import SCRIPTS, TempRepo, load, run

overseer_mod = load(SCRIPTS / "overseer-gate.py")


def session_ledger(attrs: list[dict]) -> str:
    return json.dumps({"unit": "test", "attributes": attrs})


class SessionStateGate(TempRepo):
    def check(self, *argv):
        return run(overseer_mod, "--repo", str(self.repo), "session-state", *argv)

    def test_unclassified_attribute_is_a_gap(self):
        path = self.write("session.json", session_ledger([
            {"name": "cartId", "type": "String", "destination": "unclassified"},
        ]))
        code, out = self.check("--session-ledger", str(path))
        self.assertEqual(code, 1, out)
        self.assertIn("[cartId] is unclassified", out)

    def test_fully_classified_with_no_new_source_passes(self):
        path = self.write("session.json", session_ledger([
            {"name": "cartId", "type": "String", "destination": "server-side-durable"},
        ]))
        code, out = self.check("--session-ledger", str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("clear", out)

    def test_new_code_still_reading_http_session_is_a_gap(self):
        path = self.write("session.json", session_ledger([
            {"name": "cartId", "type": "String", "destination": "server-side-durable"},
        ]))
        new_source = self.write("NewCartController.java",
                                'Object c = session.getAttribute("cartId");\n')
        code, out = self.check("--session-ledger", str(path), "--new-source", str(new_source))
        self.assertEqual(code, 1, out)
        self.assertIn("still reads HttpSession attribute 'cartId'", out)

    def test_new_code_reading_an_unrelated_attribute_does_not_block(self):
        path = self.write("session.json", session_ledger([
            {"name": "cartId", "type": "String", "destination": "server-side-durable"},
        ]))
        new_source = self.write("NewCartController.java",
                                'Object x = session.getAttribute("somethingElse");\n')
        code, out = self.check("--session-ledger", str(path), "--new-source", str(new_source))
        self.assertEqual(code, 0, out)

    def test_multiple_ledgers_merge(self):
        p1 = self.write("s1.json", session_ledger([
            {"name": "cartId", "type": "String", "destination": "server-side-durable"},
        ]))
        p2 = self.write("s2.json", session_ledger([
            {"name": "userId", "type": "String", "destination": "unclassified"},
        ]))
        code, out = self.check("--session-ledger", str(p1), str(p2))
        self.assertEqual(code, 1, out)
        self.assertIn("[userId] is unclassified", out)

    def test_missing_ledger_is_usage_error(self):
        code, out = self.check("--session-ledger", str(self.repo / "nope.json"))
        self.assertEqual(code, 2)

    def test_missing_new_source_is_usage_error(self):
        path = self.write("session.json", session_ledger([]))
        code, out = self.check("--session-ledger", str(path), "--new-source",
                               str(self.repo / "nope.java"))
        self.assertEqual(code, 2)


def http_manifest(fixtures: list[dict]) -> str:
    return json.dumps({"fixtures": fixtures})


class HttpFixturesGate(TempRepo):
    def check(self, *argv):
        return run(overseer_mod, "--repo", str(self.repo), "http-fixtures", *argv)

    def test_complete_http_fixture_passes(self):
        path = self.write("fixtures.json", http_manifest([
            {"id": "GM-1", "request": {"method": "GET", "path": "/cart"},
             "response": {"status": 200}},
        ]))
        code, out = self.check("--fixtures", str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("clear", out)

    def test_missing_request_method_is_a_gap(self):
        path = self.write("fixtures.json", http_manifest([
            {"id": "GM-1", "request": {"path": "/cart"}, "response": {"status": 200}},
        ]))
        code, out = self.check("--fixtures", str(path))
        self.assertEqual(code, 1, out)
        self.assertIn("missing 'method'", out)

    def test_missing_response_status_is_a_gap(self):
        path = self.write("fixtures.json", http_manifest([
            {"id": "GM-1", "request": {"method": "GET", "path": "/cart"}, "response": {}},
        ]))
        code, out = self.check("--fixtures", str(path))
        self.assertEqual(code, 1, out)
        self.assertIn("missing 'status'", out)

    def test_email_shaped_string_is_flagged_as_possible_real_user_data(self):
        path = self.write("fixtures.json", http_manifest([
            {"id": "GM-1", "request": {"method": "GET", "path": "/cart"},
             "response": {"status": 200, "body": "contact: jane.doe@example.com"}},
        ]))
        code, out = self.check("--fixtures", str(path))
        self.assertEqual(code, 1, out)
        self.assertIn("real user data", out)

    def test_ssn_shaped_string_is_flagged(self):
        path = self.write("fixtures.json", http_manifest([
            {"id": "GM-1", "request": {"method": "GET", "path": "/cart"},
             "response": {"status": 200, "body": "ssn: 123-45-6789"}},
        ]))
        code, out = self.check("--fixtures", str(path))
        self.assertEqual(code, 1, out)

    def test_non_http_fixtures_are_skipped_not_a_gap(self):
        path = self.write("fixtures.json", http_manifest([
            {"id": "GM-1", "ruleIds": ["R1"], "source": "legacy-run",
             "legacyCommand": "sqlplus ...", "input": "x.csv", "expectedOutput": "y.csv"},
        ]))
        code, out = self.check("--fixtures", str(path))
        self.assertEqual(code, 0, out)

    def test_mixed_manifest_only_checks_http_shaped_fixtures(self):
        path = self.write("fixtures.json", http_manifest([
            {"id": "GM-1", "ruleIds": ["R1"], "source": "legacy-run",
             "legacyCommand": "sqlplus ...", "input": "x.csv", "expectedOutput": "y.csv"},
            {"id": "GM-2", "request": {"method": "GET", "path": "/cart"},
             "response": {"status": 200}},
        ]))
        code, out = self.check("--fixtures", str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("1 HTTP-shaped fixture(s)", out)

    def test_missing_manifest_is_usage_error(self):
        code, out = self.check("--fixtures", "nope.json")
        self.assertEqual(code, 2)
