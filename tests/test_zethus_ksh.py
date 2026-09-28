"""Tests for the ksh wrapper reader (`zethus/scripts/ksh-wrapper-reader.py`): getopts argument
parsing, exit codes, trap handlers, file locking, and retry/backoff loops. All scripts below are
synthetic, invented ksh.
"""
from __future__ import annotations

import json

from tests.test_zethus import SCRIPTS, TempRepo, load, run

ksh_mod = load(SCRIPTS / "ksh-wrapper-reader.py")

SCRIPT = """#!/bin/ksh
set -e

while getopts "e:v" opt; do
  case $opt in
    e) ENV=$OPTARG ;;
    v) VERBOSE=1 ;;
  esac
done

trap 'echo cleanup; rm -f "$LOCKFILE"' INT TERM EXIT

flock -n 200 || exit 3

attempt=0
while [ $attempt -lt 5 ]; do
  do_the_call && break
  attempt=$((attempt + 1))
  sleep 5
done

if [ $attempt -ge 5 ]; then
  echo "gave up"
  exit 4
fi

exit 0
"""

MKDIR_LOCK_SCRIPT = """#!/bin/ksh
mkdir "$LOCKDIR" || exit 1
echo done
"""

UNBOUNDED_RETRY_SCRIPT = """#!/bin/ksh
while true; do
  try_thing
  sleep 10
done
"""

NO_FINDINGS_SCRIPT = """#!/bin/ksh
echo "hello world"
"""


class KshWrapperReader(TempRepo):
    def read(self, *argv):
        return run(ksh_mod, "--repo", str(self.repo), *argv)

    def test_getopts_exit_trap_and_flock_found(self):
        path = self.write("job.ksh", SCRIPT)
        out_path = self.repo / "rules.json"
        code, out = self.read(str(path), "--out", str(out_path))
        self.assertEqual(code, 0, out)
        data = json.loads(out_path.read_text(encoding="utf-8"))
        kinds = {r["kind"] for r in data["rules"]}
        self.assertIn("validation", kinds)
        self.assertIn("error-handling", kinds)
        self.assertIn("orchestration", kinds)
        exit_codes = {r["rule"] for r in data["rules"] if r["id"].startswith("EXIT")}
        self.assertTrue(any("code 0" in r for r in exit_codes))
        self.assertTrue(any("code 3" in r for r in exit_codes))
        self.assertTrue(any("code 4" in r for r in exit_codes))

    def test_trap_signals_and_command_captured(self):
        path = self.write("job.ksh", SCRIPT)
        out_path = self.repo / "rules.json"
        self.read(str(path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        trap = next(r for r in data["rules"] if r["id"].startswith("TRAP"))
        self.assertIn("INT", trap["rule"])
        self.assertIn("TERM", trap["rule"])
        self.assertIn("EXIT", trap["rule"])
        self.assertIn("rm -f", trap["rule"])

    def test_bounded_retry_loop_is_medium_confidence_with_count(self):
        path = self.write("job.ksh", SCRIPT)
        out_path = self.repo / "rules.json"
        self.read(str(path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        retry = next(r for r in data["rules"] if r["id"].startswith("RETRY"))
        self.assertEqual(retry["confidence"], "Medium")
        self.assertIn("5", retry["rule"])

    def test_mkdir_lock_idiom_is_medium_confidence(self):
        path = self.write("job.ksh", MKDIR_LOCK_SCRIPT)
        out_path = self.repo / "rules.json"
        self.read(str(path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        lock = next(r for r in data["rules"] if r["kind"] == "orchestration")
        self.assertEqual(lock["confidence"], "Medium")

    def test_unbounded_retry_is_low_confidence(self):
        path = self.write("job.ksh", UNBOUNDED_RETRY_SCRIPT)
        out_path = self.repo / "rules.json"
        self.read(str(path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        retry = next(r for r in data["rules"] if r["id"].startswith("RETRY"))
        self.assertEqual(retry["confidence"], "Low")

    def test_no_findings_is_a_valid_empty_result(self):
        path = self.write("job.ksh", NO_FINDINGS_SCRIPT)
        code, out = self.read(str(path))
        self.assertEqual(code, 0, out)
        self.assertIn("0 rule(s) recovered", out)

    def test_multiple_scripts_are_all_read(self):
        p1 = self.write("a.ksh", SCRIPT)
        p2 = self.write("b.ksh", MKDIR_LOCK_SCRIPT)
        code, out = self.read(str(p1), str(p2))
        self.assertEqual(code, 0, out)

    def test_missing_script_is_usage_error(self):
        code, out = self.read(str(self.repo / "nope.ksh"))
        self.assertEqual(code, 2)

    def test_citation_includes_file_and_line(self):
        path = self.write("subdir/job.ksh", SCRIPT)
        out_path = self.repo / "rules.json"
        self.read(str(path), "--out", str(out_path))
        data = json.loads(out_path.read_text(encoding="utf-8"))
        for r in data["rules"]:
            self.assertRegex(r["where"], r"subdir[/\\]job\.ksh:\d+")
