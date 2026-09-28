"""Tests for the Control-M scheduler reader (`zethus/scripts/control-m-reader.py`): dependency
graph recovery from INCOND/OUTCOND, cycle detection, and mapping onto a Spring Batch flow or a
Step Functions state machine skeleton. The export below is a synthetic, invented job table.
"""
from __future__ import annotations

import json

from tests.test_zethus import SCRIPTS, TempRepo, load, run

ctm_mod = load(SCRIPTS / "control-m-reader.py")

LINEAR_EXPORT = """<DEFTABLE>
  <FOLDER FOLDER_NAME="NIGHTLY_BATCH">
    <JOB JOBNAME="JOB_A" CMDLINE="/app/scripts/job_a.ksh" WDAYS="1,2,3,4,5" TIME="0200">
      <OUTCOND NAME="JOB_A-OK"/>
    </JOB>
    <JOB JOBNAME="JOB_B" CMDLINE="/app/scripts/job_b.ksh">
      <INCOND NAME="JOB_A-OK"/>
      <OUTCOND NAME="JOB_B-OK"/>
    </JOB>
    <JOB JOBNAME="JOB_C" CMDLINE="/app/scripts/job_c.ksh">
      <INCOND NAME="JOB_B-OK"/>
    </JOB>
  </FOLDER>
</DEFTABLE>
"""

DEFAULT_OUTCOND_EXPORT = """<DEFTABLE>
  <FOLDER FOLDER_NAME="NIGHTLY_BATCH">
    <JOB JOBNAME="JOB_A" CMDLINE="/app/scripts/job_a.ksh"/>
    <JOB JOBNAME="JOB_B" CMDLINE="/app/scripts/job_b.ksh">
      <INCOND NAME="JOB_A-OK"/>
    </JOB>
  </FOLDER>
</DEFTABLE>
"""

CYCLE_EXPORT = """<DEFTABLE>
  <FOLDER FOLDER_NAME="LOOP">
    <JOB JOBNAME="JOB_X" CMDLINE="x.ksh">
      <INCOND NAME="JOB_Y-OK"/>
      <OUTCOND NAME="JOB_X-OK"/>
    </JOB>
    <JOB JOBNAME="JOB_Y" CMDLINE="y.ksh">
      <INCOND NAME="JOB_X-OK"/>
      <OUTCOND NAME="JOB_Y-OK"/>
    </JOB>
  </FOLDER>
</DEFTABLE>
"""

NO_JOBNAME_EXPORT = """<DEFTABLE>
  <FOLDER FOLDER_NAME="BAD">
    <JOB CMDLINE="x.ksh"/>
  </FOLDER>
</DEFTABLE>
"""


class ControlMReader(TempRepo):
    def read(self, *argv):
        return run(ctm_mod, "--repo", str(self.repo), *argv)

    def test_linear_dependency_chain_orders_correctly(self):
        path = self.write("export.xml", LINEAR_EXPORT)
        code, out = self.read("--export", str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("JOB_A -> JOB_B -> JOB_C", out)

    def test_default_outcond_convention_when_none_explicit(self):
        path = self.write("export.xml", DEFAULT_OUTCOND_EXPORT)
        code, out = self.read("--export", str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("JOB_A -> JOB_B", out)

    def test_cycle_is_detected_and_blocks_mapping(self):
        path = self.write("export.xml", CYCLE_EXPORT)
        code, out = self.read("--export", str(path))
        self.assertEqual(code, 1, out)
        self.assertIn("CYCLE", out)
        self.assertIn("JOB_X", out)
        self.assertIn("JOB_Y", out)

    def test_spring_batch_flow_mapping_is_default_target(self):
        path = self.write("export.xml", LINEAR_EXPORT)
        out_path = self.repo / "mapping.json"
        code, out = self.read("--export", str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(data["mapping"]["target"], "spring-batch-flow")
        steps = {s["step"]: s for s in data["mapping"]["steps"]}
        self.assertEqual(steps["JOB_A"]["next"], ["JOB_B"])
        self.assertEqual(steps["JOB_C"]["next"], [])

    def test_step_functions_mapping(self):
        path = self.write("export.xml", LINEAR_EXPORT)
        out_path = self.repo / "mapping.json"
        code, out = self.read("--export", str(path), "--target", "step-functions",
                              "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(data["mapping"]["target"], "step-functions")
        self.assertEqual(data["mapping"]["StartAt"], "JOB_A")
        self.assertEqual(data["mapping"]["States"]["JOB_A"]["Next"], "JOB_B")
        self.assertTrue(data["mapping"]["States"]["JOB_C"]["End"])

    def test_scheduling_rules_capture_calendar_attributes(self):
        path = self.write("export.xml", LINEAR_EXPORT)
        out_path = self.repo / "mapping.json"
        code, out = self.read("--export", str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        job_a_rule = next(r for r in data["scheduling"] if r["where"].endswith("/JOB_A"))
        self.assertEqual(job_a_rule["confidence"], "High")
        self.assertIn("WDAYS=1,2,3,4,5", job_a_rule["rule"])

    def test_missing_jobname_is_usage_error(self):
        path = self.write("export.xml", NO_JOBNAME_EXPORT)
        code, out = self.read("--export", str(path))
        self.assertEqual(code, 2)

    def test_invalid_xml_is_usage_error(self):
        path = self.write("export.xml", "<DEFTABLE><FOLDER>")
        code, out = self.read("--export", str(path))
        self.assertEqual(code, 2)

    def test_missing_export_file_is_usage_error(self):
        code, out = self.read("--export", "nope.xml")
        self.assertEqual(code, 2)
