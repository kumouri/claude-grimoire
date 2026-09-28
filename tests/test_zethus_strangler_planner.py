"""Tests for the strangler-fig cutover planner (`zethus/scripts/strangler-planner.py`): routes that
share session state group into one flow unit, independent routes stay per-route, already-migrated
routes are excluded and reported separately, and any unit with session state gets an explicit
state-extraction step ordered before cutover. Decided 2026-09-28 (Telegram picker), see
`zethus/docs/webapp-modernization.md`.
"""
from __future__ import annotations

import json

from tests.test_zethus import SCRIPTS, TempRepo, load, run

planner_mod = load(SCRIPTS / "strangler-planner.py")


def routes_manifest(routes: list[dict]) -> str:
    return json.dumps({"routes": routes})


class StranglerPlanner(TempRepo):
    def plan(self, *argv):
        return run(planner_mod, "--repo", str(self.repo), *argv)

    def test_independent_routes_are_separate_route_units(self):
        path = self.write("routes.json", routes_manifest([
            {"id": "/home", "path": "/home"},
            {"id": "/about", "path": "/about"},
        ]))
        out_path = self.repo / "plan.json"
        code, out = self.plan("--routes", str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["units"]), 2)
        self.assertTrue(all(u["kind"] == "route" for u in data["units"]))

    def test_routes_sharing_a_session_attribute_become_one_flow(self):
        path = self.write("routes.json", routes_manifest([
            {"id": "/cart", "path": "/cart", "sessionAttributes": ["cartId"]},
            {"id": "/checkout", "path": "/checkout", "sessionAttributes": ["cartId"]},
        ]))
        out_path = self.repo / "plan.json"
        code, out = self.plan("--routes", str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["units"]), 1)
        unit = data["units"][0]
        self.assertEqual(unit["kind"], "flow")
        self.assertEqual(set(unit["routeIds"]), {"/cart", "/checkout"})
        self.assertEqual(unit["sessionAttributes"], ["cartId"])

    def test_state_extraction_step_ordered_before_cutover(self):
        path = self.write("routes.json", routes_manifest([
            {"id": "/cart", "path": "/cart", "sessionAttributes": ["cartId"]},
        ]))
        out_path = self.repo / "plan.json"
        self.plan("--routes", str(path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        steps = data["units"][0]["steps"]
        extract_idx = next(i for i, s in enumerate(steps) if "extract session state" in s)
        cutover_idx = next(i for i, s in enumerate(steps) if "cut over router" in s)
        self.assertLess(extract_idx, cutover_idx)

    def test_route_with_no_session_state_has_no_extraction_step(self):
        path = self.write("routes.json", routes_manifest([{"id": "/home", "path": "/home"}]))
        out_path = self.repo / "plan.json"
        self.plan("--routes", str(path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertFalse(any("extract session state" in s for s in data["units"][0]["steps"]))

    def test_already_migrated_route_excluded_and_reported_separately(self):
        path = self.write("routes.json", routes_manifest([
            {"id": "/api/orders", "path": "/api/orders", "alreadyMigrated": True},
            {"id": "/home", "path": "/home"},
        ]))
        out_path = self.repo / "plan.json"
        code, out = self.plan("--routes", str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["units"]), 1)
        self.assertEqual(data["units"][0]["routeIds"], ["/home"])
        self.assertEqual(len(data["alreadyMigrated"]), 1)
        self.assertEqual(data["alreadyMigrated"][0]["id"], "/api/orders")

    def test_explicit_shared_flow_id_also_groups_routes(self):
        path = self.write("routes.json", routes_manifest([
            {"id": "/step1", "path": "/step1", "flow": "wizard"},
            {"id": "/step2", "path": "/step2", "flow": "wizard"},
        ]))
        out_path = self.repo / "plan.json"
        self.plan("--routes", str(path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["units"]), 1)
        self.assertEqual(data["units"][0]["kind"], "flow")

    def test_multiple_manifests_merge_and_duplicate_ids_are_not_double_counted(self):
        p1 = self.write("routes1.json", routes_manifest([{"id": "/home", "path": "/home"}]))
        p2 = self.write("routes2.json", routes_manifest([
            {"id": "/home", "path": "/home"}, {"id": "/about", "path": "/about"},
        ]))
        out_path = self.repo / "plan.json"
        code, out = self.plan("--routes", str(p1), str(p2), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["units"]), 2)

    def test_session_ledger_annotates_classification_status(self):
        routes_path = self.write("routes.json", routes_manifest([
            {"id": "/cart", "path": "/cart", "sessionAttributes": ["cartId"]},
        ]))
        ledger_path = self.write("session.json", json.dumps({"unit": "cart", "attributes": [
            {"name": "cartId", "type": "String", "destination": "server-side-durable"},
        ]}))
        out_path = self.repo / "plan.json"
        code, out = self.plan("--routes", str(routes_path), "--session-ledger", str(ledger_path),
                              "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(data["units"][0]["sessionAttributeStatus"]["cartId"], "server-side-durable")

    def test_unannotated_attribute_defaults_to_unknown_status(self):
        routes_path = self.write("routes.json", routes_manifest([
            {"id": "/cart", "path": "/cart", "sessionAttributes": ["cartId"]},
        ]))
        out_path = self.repo / "plan.json"
        self.plan("--routes", str(routes_path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(data["units"][0]["sessionAttributeStatus"]["cartId"], "unknown")

    def test_missing_routes_file_is_usage_error(self):
        code, out = self.plan("--routes", str(self.repo / "nope.json"))
        self.assertEqual(code, 2)

    def test_missing_session_ledger_is_usage_error(self):
        path = self.write("routes.json", routes_manifest([{"id": "/home", "path": "/home"}]))
        code, out = self.plan("--routes", str(path), "--session-ledger", str(self.repo / "nope.json"))
        self.assertEqual(code, 2)

    def test_malformed_route_manifest_is_usage_error(self):
        path = self.write("routes.json", "not json")
        code, out = self.plan("--routes", str(path))
        self.assertEqual(code, 2)

    def test_all_already_migrated_is_a_valid_empty_plan(self):
        path = self.write("routes.json", routes_manifest([
            {"id": "/api/orders", "path": "/api/orders", "alreadyMigrated": True},
        ]))
        code, out = self.plan("--routes", str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("0 planned into 0 cutover unit(s)", out)
