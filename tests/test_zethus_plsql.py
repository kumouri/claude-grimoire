"""Tests for the PL/SQL DDL intake (`zethus/scripts/plsql-ddl-intake.py`): object discovery,
provenance, wrapped/invisible-body flagging, drift between a repo and a live extract, and
DBMS_SCHEDULER/DBMS_JOB batch discovery. All fixtures are synthetic, invented PL/SQL.
"""
from __future__ import annotations

import json

from tests.test_zethus import SCRIPTS, TempRepo, load, run

plsql_mod = load(SCRIPTS / "plsql-ddl-intake.py")

PACKAGE_SPEC = """CREATE OR REPLACE PACKAGE pkg_orders IS
  PROCEDURE approve_order(p_id IN NUMBER);
END pkg_orders;
/
"""

PACKAGE_BODY = """CREATE OR REPLACE PACKAGE BODY pkg_orders IS
  PROCEDURE approve_order(p_id IN NUMBER) IS
  BEGIN
    IF p_id > 10000 THEN
      NULL;
    END IF;
  END approve_order;
END pkg_orders;
/
"""

WRAPPED_BODY = """CREATE OR REPLACE PACKAGE BODY pkg_secret WRAPPED
a000000
abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ
/
"""

TRIGGER = """CREATE OR REPLACE TRIGGER trg_orders_audit
BEFORE UPDATE ON orders
FOR EACH ROW
BEGIN
  INSERT INTO orders_audit VALUES (:old.id, SYSDATE);
END;
/
"""

SCHEDULER_JOB = """BEGIN
  DBMS_SCHEDULER.CREATE_JOB(
    job_name => 'NIGHTLY_SETTLEMENT',
    job_type => 'PLSQL_BLOCK',
    job_action => 'BEGIN pkg_orders.settle_all; END;',
    repeat_interval => 'FREQ=DAILY;BYHOUR=2',
    enabled => TRUE
  );
END;
/
"""

LEGACY_JOB = """BEGIN
  DBMS_JOB.SUBMIT(:jobno, 'pkg_orders.legacy_batch;', SYSDATE, 'SYSDATE+1');
END;
/
"""


class PlsqlDdlIntake(TempRepo):
    def intake(self, *argv):
        return run(plsql_mod, "--repo", str(self.repo), *argv)

    def test_finds_package_spec_and_body(self):
        self.write("ddl/pkg_orders.pks", PACKAGE_SPEC)
        self.write("ddl/pkg_orders.pkb", PACKAGE_BODY)
        code, out = self.intake("--repo-source", str(self.repo / "ddl"))
        self.assertEqual(code, 0, out)
        self.assertIn("2 PL/SQL object(s) found", out)

    def test_wrapped_body_is_flagged_invisible(self):
        self.write("ddl/pkg_secret.pkb", WRAPPED_BODY)
        code, out = self.intake("--repo-source", str(self.repo / "ddl"))
        self.assertEqual(code, 1, out)
        self.assertIn("INVISIBLE BODY", out)
        self.assertIn("pkg_secret", out)
        self.assertIn("wrapped", out.lower())

    def test_trigger_is_found(self):
        self.write("ddl/trg_orders_audit.sql", TRIGGER)
        code, out = self.intake("--repo-source", str(self.repo / "ddl"))
        self.assertEqual(code, 0, out)
        self.assertIn("1 PL/SQL object(s) found", out)

    def test_extract_without_date_is_usage_error(self):
        self.write("extract/pkg_orders.pkb", PACKAGE_BODY)
        code, out = self.intake("--extract-source", str(self.repo / "extract"))
        self.assertEqual(code, 2)
        self.assertIn("--extract-date", out)

    def test_drift_between_repo_and_extract_is_flagged(self):
        self.write("ddl/pkg_orders.pkb", PACKAGE_BODY)
        changed = PACKAGE_BODY.replace("p_id > 10000", "p_id > 50000")
        self.write("extract/pkg_orders.pkb", changed)
        code, out = self.intake("--repo-source", str(self.repo / "ddl"),
                                "--extract-source", str(self.repo / "extract"),
                                "--extract-date", "2026-09-28")
        self.assertEqual(code, 1, out)
        self.assertIn("DRIFT", out)
        self.assertIn("pkg_orders", out)

    def test_identical_repo_and_extract_is_no_drift(self):
        self.write("ddl/pkg_orders.pkb", PACKAGE_BODY)
        self.write("extract/pkg_orders.pkb", PACKAGE_BODY)
        code, out = self.intake("--repo-source", str(self.repo / "ddl"),
                                "--extract-source", str(self.repo / "extract"),
                                "--extract-date", "2026-09-28")
        self.assertEqual(code, 0, out)
        self.assertIn("0 drift finding(s)", out)

    def test_extract_provenance_names_the_date_not_repo_history(self):
        self.write("extract/pkg_orders.pkb", PACKAGE_BODY)
        out_path = self.repo / "intake.json"
        code, out = self.intake("--extract-source", str(self.repo / "extract"),
                                "--extract-date", "2026-09-15", "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(data["objects"][0]["provenance"], "extracted-on 2026-09-15")

    def test_scheduler_job_discovered_with_attributes(self):
        self.write("ddl/jobs.sql", SCHEDULER_JOB)
        out_path = self.repo / "intake.json"
        code, out = self.intake("--repo-source", str(self.repo / "ddl"), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        self.assertIn("1 scheduled job(s) found", out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        job = data["scheduledJobs"][0]
        self.assertEqual(job["name"], "NIGHTLY_SETTLEMENT")
        self.assertEqual(job["job_type"], "dbms_scheduler")
        self.assertEqual(job["attributes"]["repeat_interval"], "FREQ=DAILY;BYHOUR=2")

    def test_legacy_dbms_job_is_discovered(self):
        self.write("ddl/legacy_job.sql", LEGACY_JOB)
        code, out = self.intake("--repo-source", str(self.repo / "ddl"))
        self.assertEqual(code, 0, out)
        self.assertIn("1 scheduled job(s) found", out)

    def test_bad_date_is_usage_error(self):
        self.write("extract/pkg_orders.pkb", PACKAGE_BODY)
        code, out = self.intake("--extract-source", str(self.repo / "extract"),
                                "--extract-date", "not-a-date")
        self.assertEqual(code, 2)

    def test_neither_source_is_usage_error(self):
        code, out = self.intake()
        self.assertEqual(code, 2)

    def test_missing_repo_source_directory_is_usage_error(self):
        code, out = self.intake("--repo-source", str(self.repo / "nope"))
        self.assertEqual(code, 2)

    def test_git_provenance_is_a_single_commit_not_full_history(self):
        # A DDL repo may carry old secrets in its history; provenance must cite one commit,
        # never dump the log.
        run_git = lambda *a: __import__("subprocess").run(
            ["git", "-C", str(self.repo), *a], capture_output=True, text=True)
        run_git("init", "-q")
        run_git("config", "user.email", "t@example.com")
        run_git("config", "user.name", "t")
        self.write("ddl/pkg_orders.pkb", PACKAGE_BODY)
        run_git("add", "-A")
        run_git("commit", "-q", "-m", "add package body")
        out_path = self.repo / "intake.json"
        code, out = self.intake("--repo-source", str(self.repo / "ddl"), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertTrue(data["objects"][0]["provenance"].startswith("repo commit "))
        self.assertNotIn("\n", data["objects"][0]["provenance"])
