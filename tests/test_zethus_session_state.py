"""Tests for the shared session/state ledger module (`zethus/scripts/_session_state.py`): the
SESSION STATE -> STATELESS inventory and classification shape used by the web-app target readers,
`strangler-planner.py`, and `overseer-gate.py session-state`. See
`zethus/docs/webapp-modernization.md`.
"""
from __future__ import annotations

import json

from tests.test_zethus import SCRIPTS, TempRepo, load

ss = load(SCRIPTS / "_session_state.py")


class SessionAttributeValidation(TempRepo):
    def test_unclassified_is_the_default(self):
        attr = ss.SessionAttribute(name="cartId", type="String")
        self.assertEqual(attr.destination, ss.UNCLASSIFIED)

    def test_a_valid_destination_is_accepted(self):
        attr = ss.SessionAttribute(name="cartId", type="String", destination="server-side-durable")
        self.assertEqual(attr.destination, "server-side-durable")

    def test_an_invalid_destination_raises(self):
        with self.assertRaises(ss.SessionStateError):
            ss.SessionAttribute(name="cartId", type="String", destination="somewhere-else")


class LedgerRoundTrip(TempRepo):
    def test_write_then_read_round_trips(self):
        attrs = [
            ss.SessionAttribute(name="cartId", type="String", writtenBy=["Cart.java:10"],
                               readBy=["Cart.java:20"], lifetime="login-session",
                               flows=["/cart"], destination="server-side-durable",
                               rationale="owned by the cart service"),
        ]
        path = self.repo / "session-state" / "cart.json"
        ss.write_session_ledger(path, "cart.jsp", attrs)
        unit, read_back = ss.read_session_ledger(path)
        self.assertEqual(unit, "cart.jsp")
        self.assertEqual(len(read_back), 1)
        self.assertEqual(read_back[0].name, "cartId")
        self.assertEqual(read_back[0].destination, "server-side-durable")

    def test_missing_required_field_raises(self):
        path = self.write("bad.json", json.dumps({"unit": "x", "attributes": [{"name": "a"}]}))
        with self.assertRaises(ss.SessionStateError):
            ss.read_session_ledger(path)

    def test_duplicate_name_raises(self):
        path = self.write("bad.json", json.dumps({"unit": "x", "attributes": [
            {"name": "a", "type": "String"}, {"name": "a", "type": "String"},
        ]}))
        with self.assertRaises(ss.SessionStateError):
            ss.read_session_ledger(path)

    def test_not_json_raises(self):
        path = self.write("bad.json", "not json")
        with self.assertRaises(ss.SessionStateError):
            ss.read_session_ledger(path)

    def test_no_attributes_key_raises(self):
        path = self.write("bad.json", json.dumps({"unit": "x"}))
        with self.assertRaises(ss.SessionStateError):
            ss.read_session_ledger(path)


class Unclassified(TempRepo):
    def test_filters_to_only_unclassified(self):
        a = ss.SessionAttribute(name="a", type="", destination=ss.UNCLASSIFIED)
        b = ss.SessionAttribute(name="b", type="", destination="derivable-per-request")
        self.assertEqual(ss.unclassified([a, b]), [a])


class HttpSessionScan(TempRepo):
    def test_get_and_set_are_merged_into_one_row(self):
        text = ('String uid = (String) session.getAttribute("userId");\n'
               'session.setAttribute("userId", newId);\n')
        rows = ss.scan_http_session_usage(text, "Foo.java")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].name, "userId")
        self.assertEqual(len(rows[0].readBy), 1)
        self.assertEqual(len(rows[0].writtenBy), 1)
        self.assertIn("Foo.java:1", rows[0].readBy[0])
        self.assertIn("Foo.java:2", rows[0].writtenBy[0])

    def test_no_session_calls_is_empty(self):
        self.assertEqual(ss.scan_http_session_usage("System.out.println(1);", "Foo.java"), [])

    def test_multiple_distinct_names_are_separate_rows(self):
        text = 'session.getAttribute("a");\nsession.getAttribute("b");\n'
        rows = ss.scan_http_session_usage(text, "Foo.java")
        self.assertEqual({r.name for r in rows}, {"a", "b"})


class StillReadsHttpSession(TempRepo):
    def test_finds_a_lingering_read(self):
        text = 'Object x = session.getAttribute("cartId");'
        self.assertEqual(ss.still_reads_http_session(text, {"cartId", "userId"}), ["cartId"])

    def test_clean_new_code_finds_nothing(self):
        text = "cartService.getCart(userId);"
        self.assertEqual(ss.still_reads_http_session(text, {"cartId"}), [])

    def test_only_names_of_interest_are_reported(self):
        text = 'session.getAttribute("somethingElse");'
        self.assertEqual(ss.still_reads_http_session(text, {"cartId"}), [])


class FlowsSharingState(TempRepo):
    def test_groups_attribute_names_by_flow(self):
        attrs = [
            ss.SessionAttribute(name="cartId", type="", flows=["/cart", "/checkout"]),
            ss.SessionAttribute(name="userId", type="", flows=["/cart"]),
        ]
        result = ss.flows_sharing_state(attrs)
        self.assertEqual(result["/cart"], {"cartId", "userId"})
        self.assertEqual(result["/checkout"], {"cartId"})
