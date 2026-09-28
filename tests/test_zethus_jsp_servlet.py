"""Tests for the plain JSP + servlet reader (`zethus/scripts/jsp-servlet-reader.py`): web.xml
route/authz/session-timeout recovery, scriptlet/JSTL business-logic detection, and the shared raw
HttpSession scan. All sources below are synthetic, invented web.xml/JSP/Java.
"""
from __future__ import annotations

import json

from tests.test_zethus import SCRIPTS, TempRepo, load, run

jsp_mod = load(SCRIPTS / "jsp-servlet-reader.py")

WEB_XML = """<?xml version="1.0"?>
<web-app>
  <servlet>
    <servlet-name>cartServlet</servlet-name>
    <servlet-class>com.example.CartServlet</servlet-class>
  </servlet>
  <servlet-mapping>
    <servlet-name>cartServlet</servlet-name>
    <url-pattern>/cart</url-pattern>
  </servlet-mapping>
  <security-constraint>
    <web-resource-collection>
      <url-pattern>/admin/*</url-pattern>
    </web-resource-collection>
    <auth-constraint>
      <role-name>ADMIN</role-name>
    </auth-constraint>
  </security-constraint>
  <session-config>
    <session-timeout>30</session-timeout>
  </session-config>
</web-app>
"""

JSP_PAGE = """<%@ page import="java.util.*" %>
<html>
<body>
<%
  String role = (String) session.getAttribute("role");
  if (role.equals("ADMIN")) {
    out.println("Welcome admin");
  }
%>
<c:if test="${user.role == 'ADMIN'}">
  <p>Admin panel</p>
</c:if>
<c:choose>
  <c:when test="${x}">A</c:when>
</c:choose>
</body>
</html>
"""

PLAIN_JAVA_SERVLET = """public class LegacyServlet {
    protected void doGet(HttpServletRequest req, HttpServletResponse resp) {
        session.setAttribute("lastVisited", req.getRequestURI());
    }
}
"""


class WebXmlReading(TempRepo):
    def read(self, *argv):
        return run(jsp_mod, "--repo", str(self.repo), *argv)

    def test_servlet_mapping_container_is_not_mistaken_for_a_servlet(self):
        path = self.write("web.xml", WEB_XML)
        out_path = self.repo / "rules.json"
        code, out = self.read(str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        route_rules = [r for r in data["rules"] if r["id"].startswith("ROUTE-")]
        self.assertEqual(len(route_rules), 1)
        self.assertIn("cartServlet", route_rules[0]["rule"])
        self.assertIn("com.example.CartServlet", route_rules[0]["rule"])

    def test_security_constraint_and_session_timeout_recovered(self):
        path = self.write("web.xml", WEB_XML)
        out_path = self.repo / "rules.json"
        code, out = self.read(str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        authz = next(r for r in data["rules"] if r["id"].startswith("AUTHZ-"))
        self.assertIn("ADMIN", authz["rule"])
        self.assertEqual(authz["kind"], "validation")
        timeout = next(r for r in data["rules"] if r["id"].startswith("TIMEOUT-"))
        self.assertIn("30", timeout["rule"])

    def test_routes_manifest_written(self):
        path = self.write("web.xml", WEB_XML)
        routes_path = self.repo / "routes.json"
        code, out = self.read(str(path), "--routes-out", str(routes_path))
        self.assertEqual(code, 0, out)
        data = json.loads(routes_path.read_text(encoding="utf-8"))
        self.assertEqual([r["id"] for r in data["routes"]], ["/cart"])


class JspReading(TempRepo):
    def read(self, *argv):
        return run(jsp_mod, "--repo", str(self.repo), *argv)

    def test_scriptlet_with_logic_is_flagged_medium_confidence(self):
        path = self.write("admin.jsp", JSP_PAGE)
        out_path = self.repo / "rules.json"
        code, out = self.read(str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        scriptlet_rules = [r for r in data["rules"] if r["id"].startswith("SCRIPTLET-")]
        self.assertEqual(len(scriptlet_rules), 1)
        self.assertEqual(scriptlet_rules[0]["confidence"], "Medium")
        self.assertEqual(scriptlet_rules[0]["kind"], "calculation")

    def test_jstl_if_and_choose_recovered(self):
        path = self.write("admin.jsp", JSP_PAGE)
        out_path = self.repo / "rules.json"
        self.read(str(path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        jstl_rules = [r for r in data["rules"] if r["id"].startswith("JSTL-")]
        self.assertEqual(len(jstl_rules), 2)
        self.assertTrue(all(r["kind"] == "validation" for r in jstl_rules))

    def test_session_get_attribute_recovered_from_scriptlet(self):
        path = self.write("admin.jsp", JSP_PAGE)
        session_path = self.repo / "session.json"
        code, out = self.read(str(path), "--session-out", str(session_path))
        self.assertEqual(code, 0, out)
        data = json.loads(session_path.read_text(encoding="utf-8"))
        self.assertEqual([a["name"] for a in data["attributes"]], ["role"])
        self.assertTrue(data["attributes"][0]["readBy"])
        self.assertFalse(data["attributes"][0]["writtenBy"])

    def test_plain_page_with_no_logic_has_no_scriptlet_finding(self):
        path = self.write("static.jsp", "<html><body>hello</body></html>\n")
        code, out = self.read(str(path))
        self.assertEqual(code, 0, out)
        self.assertNotIn("SCRIPTLET", out)


class RawHttpSessionAcrossFileTypes(TempRepo):
    def read(self, *argv):
        return run(jsp_mod, "--repo", str(self.repo), *argv)

    def test_java_servlet_also_gets_the_shared_session_scan(self):
        path = self.write("LegacyServlet.java", PLAIN_JAVA_SERVLET)
        session_path = self.repo / "session.json"
        code, out = self.read(str(path), "--session-out", str(session_path))
        self.assertEqual(code, 0, out)
        data = json.loads(session_path.read_text(encoding="utf-8"))
        self.assertEqual([a["name"] for a in data["attributes"]], ["lastVisited"])

    def test_java_file_recovers_no_routes(self):
        path = self.write("LegacyServlet.java", PLAIN_JAVA_SERVLET)
        routes_path = self.repo / "routes.json"
        code, out = self.read(str(path), "--routes-out", str(routes_path))
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(routes_path.read_text(encoding="utf-8"))["routes"], [])

    def test_missing_source_is_usage_error(self):
        code, out = self.read(str(self.repo / "nope.jsp"))
        self.assertEqual(code, 2)
