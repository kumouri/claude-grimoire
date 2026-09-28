"""Tests for the Struts 1.x/2.x reader (`zethus/scripts/struts-reader.py`): route/form/validation/
session-scope/authz recovery, plus hybrid Spring-controller-delegates-to-Struts detection — the
FIRST REAL TARGET SHAPE this build's readers are built for. All sources below are synthetic,
invented Struts/Spring config and Java.
"""
from __future__ import annotations

import json

from tests.test_zethus import SCRIPTS, TempRepo, load, run

struts_mod = load(SCRIPTS / "struts-reader.py")

STRUTS1_CONFIG = """<?xml version="1.0"?>
<struts-config>
  <form-beans>
    <form-bean name="loginForm" type="com.example.LoginForm"/>
  </form-beans>
  <action-mappings>
    <action path="/login" type="com.example.LoginAction" name="loginForm" scope="session"
            validate="true" roles="USER">
      <forward name="success" path="/welcome.jsp"/>
      <forward name="failure" path="/login.jsp"/>
    </action>
    <action path="/logout" type="com.example.LogoutAction" scope="request" validate="false"/>
  </action-mappings>
</struts-config>
"""

STRUTS2_CONFIG = """<struts>
  <package name="default" extends="struts-default">
    <action name="viewCart" class="com.example.CartAction" method="view">
      <interceptor-ref name="validation"/>
      <result name="success">/cart.jsp</result>
      <result name="error">/error.jsp</result>
    </action>
  </package>
</struts>
"""

HYBRID_CONTROLLER = """package com.example;

import org.springframework.stereotype.Controller;
import com.example.LoginAction;

@Controller
public class LegacyLoginController {
    public String handle() {
        LoginAction action = new LoginAction();
        return action.execute();
    }
}
"""


class Struts1Reader(TempRepo):
    def read(self, *argv):
        return run(struts_mod, "--repo", str(self.repo), *argv)

    def test_action_mappings_container_is_not_mistaken_for_an_action(self):
        path = self.write("struts-config.xml", STRUTS1_CONFIG)
        out_path = self.repo / "rules.json"
        code, out = self.read(str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        # exactly two ACTION- rows: /login and /logout, never a false match on <action-mappings>
        action_rules = [r for r in data["rules"] if r["id"].startswith("ACTION-")]
        self.assertEqual(len(action_rules), 2)

    def test_login_route_recovers_validation_authz_and_session_state(self):
        path = self.write("struts-config.xml", STRUTS1_CONFIG)
        out_path = self.repo / "rules.json"
        session_path = self.repo / "session.json"
        code, out = self.read(str(path), "--out", str(out_path), "--session-out", str(session_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        kinds = {r["kind"] for r in data["rules"]}
        self.assertIn("validation", kinds)
        self.assertIn("orchestration", kinds)
        validate_rules = [r for r in data["rules"] if r["id"].startswith("VALIDATE-")]
        self.assertEqual(len(validate_rules), 1)
        authz_rules = [r for r in data["rules"] if r["id"].startswith("AUTHZ-")]
        self.assertEqual(len(authz_rules), 1)
        self.assertIn("USER", authz_rules[0]["rule"])
        sesstate_rules = [r for r in data["rules"] if r["id"].startswith("SESSTATE-")]
        self.assertEqual(len(sesstate_rules), 1)

        session_data = json.loads(session_path.read_text(encoding="utf-8"))
        self.assertEqual(len(session_data["attributes"]), 1)
        self.assertEqual(session_data["attributes"][0]["name"], "loginForm")
        self.assertEqual(session_data["attributes"][0]["destination"], "unclassified")

    def test_logout_route_has_no_validation_authz_or_session_state(self):
        path = self.write("struts-config.xml", STRUTS1_CONFIG)
        out_path = self.repo / "rules.json"
        code, out = self.read(str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        logout_action = next(r for r in data["rules"]
                             if r["id"].startswith("ACTION-") and "/logout" in r["rule"])
        self.assertNotIn("form", logout_action["rule"])

    def test_form_bean_recovered(self):
        path = self.write("struts-config.xml", STRUTS1_CONFIG)
        code, out = self.read(str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("form-bean 'loginForm'", out)

    def test_forwards_recovered(self):
        path = self.write("struts-config.xml", STRUTS1_CONFIG)
        out_path = self.repo / "rules.json"
        code, out = self.read(str(path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        fwd_rules = [r for r in data["rules"] if r["id"].startswith("FWD-")]
        self.assertEqual(len(fwd_rules), 2)

    def test_routes_manifest_written(self):
        path = self.write("struts-config.xml", STRUTS1_CONFIG)
        routes_path = self.repo / "routes.json"
        code, out = self.read(str(path), "--routes-out", str(routes_path))
        self.assertEqual(code, 0, out)
        data = json.loads(routes_path.read_text(encoding="utf-8"))
        self.assertEqual({r["id"] for r in data["routes"]}, {"/login", "/logout"})
        login_route = next(r for r in data["routes"] if r["id"] == "/login")
        self.assertEqual(login_route["sessionAttributes"], ["loginForm"])

    def test_hybrid_delegation_found_via_java_cross_reference(self):
        config_path = self.write("struts-config.xml", STRUTS1_CONFIG)
        java_path = self.write("LegacyLoginController.java", HYBRID_CONTROLLER)
        out_path = self.repo / "rules.json"
        code, out = self.read(str(config_path), "--java", str(java_path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        hybrid_rules = [r for r in data["rules"] if r["id"].startswith("HYBRID-")]
        self.assertEqual(len(hybrid_rules), 1)
        self.assertIn("LoginAction", hybrid_rules[0]["rule"])
        self.assertEqual(hybrid_rules[0]["confidence"], "Medium")

    def test_no_hybrid_finding_without_matching_class_reference(self):
        config_path = self.write("struts-config.xml", STRUTS1_CONFIG)
        java_path = self.write("Unrelated.java",
                               "@Controller\npublic class Unrelated { void m() {} }\n")
        code, out = self.read(str(config_path), "--java", str(java_path))
        self.assertEqual(code, 0, out)
        self.assertNotIn("HYBRID", out)

    def test_missing_config_is_usage_error(self):
        code, out = self.read(str(self.repo / "nope.xml"))
        self.assertEqual(code, 2)

    def test_missing_java_file_is_usage_error(self):
        path = self.write("struts-config.xml", STRUTS1_CONFIG)
        code, out = self.read(str(path), "--java", str(self.repo / "nope.java"))
        self.assertEqual(code, 2)


class Struts2Reader(TempRepo):
    def read(self, *argv):
        return run(struts_mod, "--repo", str(self.repo), *argv)

    def test_struts2_action_result_and_validation_interceptor_recovered(self):
        path = self.write("struts.xml", STRUTS2_CONFIG)
        out_path = self.repo / "rules.json"
        routes_path = self.repo / "routes.json"
        code, out = self.read(str(path), "--out", str(out_path), "--routes-out", str(routes_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertTrue(any(r["id"].startswith("ACTION2-") for r in data["rules"]))
        result_rules = [r for r in data["rules"] if r["id"].startswith("RESULT-")]
        self.assertEqual(len(result_rules), 2)
        self.assertTrue(any(r["id"].startswith("VALIDATE2-") for r in data["rules"]))
        routes = json.loads(routes_path.read_text(encoding="utf-8"))["routes"]
        self.assertEqual([r["id"] for r in routes], ["/viewCart"])

    def test_struts2_is_not_double_counted_as_struts1(self):
        path = self.write("struts.xml", STRUTS2_CONFIG)
        out_path = self.repo / "rules.json"
        self.read(str(path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertFalse(any(r["id"].startswith("ACTION-") for r in data["rules"]))
