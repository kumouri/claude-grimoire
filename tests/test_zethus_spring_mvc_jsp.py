"""Tests for the Spring MVC + JSP reader (`zethus/scripts/spring-mvc-jsp-reader.py`): route/view/
session/authz recovery, hybrid Struts delegation, and already-migrated-to-REST detection. All
sources below are synthetic, invented Spring MVC Java.
"""
from __future__ import annotations

import json

from tests.test_zethus import SCRIPTS, TempRepo, load, run

spring_mod = load(SCRIPTS / "spring-mvc-jsp-reader.py")

CONTROLLER = """package com.example;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.SessionAttributes;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.http.ResponseEntity;

@Controller
@SessionAttributes({"cartId", "userId"})
public class CartController {

    @GetMapping("/cart")
    @PreAuthorize("hasRole('USER')")
    public String viewCart(Model model) {
        return "cart";
    }

    @PostMapping("/cart/checkout")
    public ResponseEntity<Void> checkout() {
        return ResponseEntity.ok().build();
    }
}
"""

REST_CONTROLLER = """package com.example;

import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.GetMapping;

@RestController
public class ApiController {

    @GetMapping("/api/orders")
    public String orders() {
        return "[]";
    }
}
"""

HYBRID_IMPORT_CONTROLLER = """package com.example;

import org.springframework.stereotype.Controller;
import org.apache.struts.action.Action;

@Controller
public class LegacyWrapperController {
    public String handle() {
        return "ok";
    }
}
"""

NOT_A_CONTROLLER = "public class PlainOldClass { void m() {} }\n"


class SpringMvcJspReader(TempRepo):
    def read(self, *argv):
        return run(spring_mod, "--repo", str(self.repo), *argv)

    def test_routes_and_methods_recovered(self):
        path = self.write("CartController.java", CONTROLLER)
        routes_path = self.repo / "routes.json"
        code, out = self.read(str(path), "--routes-out", str(routes_path))
        self.assertEqual(code, 0, out)
        routes = json.loads(routes_path.read_text(encoding="utf-8"))["routes"]
        by_id = {r["id"]: r for r in routes}
        self.assertEqual(by_id["/cart"]["method"], "GET")
        self.assertEqual(by_id["/cart/checkout"]["method"], "POST")

    def test_already_migrated_only_the_response_entity_route_is_flagged(self):
        path = self.write("CartController.java", CONTROLLER)
        routes_path = self.repo / "routes.json"
        self.read(str(path), "--routes-out", str(routes_path))
        routes = json.loads(routes_path.read_text(encoding="utf-8"))["routes"]
        by_id = {r["id"]: r for r in routes}
        self.assertFalse(by_id["/cart"]["alreadyMigrated"])
        self.assertTrue(by_id["/cart/checkout"]["alreadyMigrated"])

    def test_rest_controller_marks_every_route_already_migrated(self):
        path = self.write("ApiController.java", REST_CONTROLLER)
        routes_path = self.repo / "routes.json"
        self.read(str(path), "--routes-out", str(routes_path))
        routes = json.loads(routes_path.read_text(encoding="utf-8"))["routes"]
        self.assertTrue(all(r["alreadyMigrated"] for r in routes))

    def test_view_return_recovered_at_medium_confidence(self):
        path = self.write("CartController.java", CONTROLLER)
        out_path = self.repo / "rules.json"
        code, out = self.read(str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        view_rules = [r for r in data["rules"] if r["id"].startswith("VIEW-")]
        self.assertEqual(len(view_rules), 1)
        self.assertEqual(view_rules[0]["confidence"], "Medium")
        self.assertIn("cart", view_rules[0]["rule"])

    def test_session_attributes_recovered(self):
        path = self.write("CartController.java", CONTROLLER)
        session_path = self.repo / "session.json"
        code, out = self.read(str(path), "--session-out", str(session_path))
        self.assertEqual(code, 0, out)
        data = json.loads(session_path.read_text(encoding="utf-8"))
        names = {a["name"] for a in data["attributes"]}
        self.assertEqual(names, {"cartId", "userId"})
        self.assertTrue(all(a["destination"] == "unclassified" for a in data["attributes"]))

    def test_authz_annotation_recovered(self):
        path = self.write("CartController.java", CONTROLLER)
        out_path = self.repo / "rules.json"
        self.read(str(path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        authz_rules = [r for r in data["rules"] if r["id"].startswith("AUTHZ-")]
        self.assertEqual(len(authz_rules), 1)
        self.assertIn("hasRole", authz_rules[0]["rule"])
        self.assertEqual(authz_rules[0]["kind"], "validation")

    def test_hybrid_struts_import_is_high_confidence(self):
        path = self.write("LegacyWrapperController.java", HYBRID_IMPORT_CONTROLLER)
        out_path = self.repo / "rules.json"
        code, out = self.read(str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        hybrid_rules = [r for r in data["rules"] if r["id"].startswith("HYBRID-")]
        self.assertEqual(len(hybrid_rules), 1)
        self.assertEqual(hybrid_rules[0]["confidence"], "High")

    def test_hybrid_struts_class_cross_reference_is_medium_confidence(self):
        path = self.write("CartController.java", CONTROLLER)
        code, out = self.read(str(path), "--struts-classes", "CartController")
        self.assertEqual(code, 0, out)
        self.assertIn("HYBRID", out)
        self.assertIn("Medium", out)

    def test_non_controller_file_is_skipped_entirely(self):
        path = self.write("PlainOldClass.java", NOT_A_CONTROLLER)
        code, out = self.read(str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("0 rule(s)", out)

    def test_missing_source_is_usage_error(self):
        code, out = self.read(str(self.repo / "nope.java"))
        self.assertEqual(code, 2)
