import json
import subprocess
import sys
import unittest

from tests._util import TempHomeTest, FIXTURES, PKG
from lib import projectdir, memory, highwater, spool
import worker

DISPATCH = str(PKG / "dispatch.py")


def run_dispatch(event_json: str, extra_env: dict) -> subprocess.CompletedProcess:
    import os
    env = dict(os.environ)
    env.update(extra_env)
    env["CLAUDE_DREAMING_NOSPAWN"] = "1"
    return subprocess.run(
        [sys.executable, DISPATCH], input=event_json,
        capture_output=True, text=True, env=env, timeout=60,
    )


class DispatchTest(TempHomeTest):
    def _env(self):
        import os
        return {
            "CLAUDE_CONFIG_DIR": os.environ["CLAUDE_CONFIG_DIR"],
            "CLAUDE_DREAMING_HOME": os.environ["CLAUDE_DREAMING_HOME"],
        }

    def test_session_end_enqueues_job(self):
        payload = json.dumps({
            "hook_event_name": "SessionEnd", "reason": "clear",
            "session_id": "t1", "transcript_path": str(FIXTURES / "transcript_t1.jsonl"),
            "cwd": "/proj",
        })
        cp = run_dispatch(payload, self._env())
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertEqual(len(spool.list_jobs()), 1)

    def test_recursion_guard_blocks(self):
        payload = json.dumps({
            "hook_event_name": "SessionEnd", "session_id": "t1",
            "transcript_path": str(FIXTURES / "transcript_t1.jsonl"), "cwd": "/proj",
        })
        env = self._env()
        env["CLAUDE_DREAMING"] = "1"
        cp = run_dispatch(payload, env)
        self.assertEqual(cp.returncode, 0)
        self.assertEqual(spool.list_jobs(), [])

    def test_below_threshold_skips(self):
        # high-water already at end of transcript -> no delta -> no job
        highwater.set("t1", 10, "now")
        payload = json.dumps({
            "hook_event_name": "PreCompact", "trigger": "auto", "session_id": "t1",
            "transcript_path": str(FIXTURES / "transcript_t1.jsonl"), "cwd": "/proj",
        })
        cp = run_dispatch(payload, self._env())
        self.assertEqual(cp.returncode, 0)
        self.assertEqual(spool.list_jobs(), [])

    def test_session_start_emits_digest(self):
        mdir = projectdir.memory_dir("/proj")
        memory.upsert(mdir, memory.Memory(
            name="who", description="Ceryce prefers DI", type="user",
            body="she/her", index_title="About Ceryce", index_hook="prefers DI"))
        payload = json.dumps({"hook_event_name": "SessionStart", "source": "startup",
                              "cwd": "/proj"})
        cp = run_dispatch(payload, self._env())
        self.assertEqual(cp.returncode, 0, cp.stderr)
        out = json.loads(cp.stdout)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        self.assertIn("About Ceryce", ctx)
        self.assertIn("Dreaming recall", ctx)


class WorkerEndToEndTest(TempHomeTest):
    def test_process_job_deterministic(self):
        projectdir.ensure_runtime_dirs()
        cfg = {"mode": "deterministic", "max_new_memories": 8, "redact_secrets": True}
        job = spool.Job(event="SessionEnd", session_id="t1",
                        transcript_path=str(FIXTURES / "transcript_t1.jsonl"), cwd="/proj")
        path = spool.write(job)

        outcome = worker.process_job(path, cfg)
        self.assertEqual(outcome, "ok")

        mdir = projectdir.memory_dir("/proj")
        mem_files = [p.name for p in mdir.glob("*.md") if p.name != "MEMORY.md"]
        self.assertTrue(any(f.startswith("project-") for f in mem_files))
        self.assertTrue((mdir / "MEMORY.md").is_file())

        dreams = list(projectdir.dreams_dir("/proj").glob("*.md"))
        self.assertEqual(len(dreams), 1)
        self.assertIn("Dream", dreams[0].read_text(encoding="utf-8"))

        self.assertEqual(highwater.get("t1"), 10)   # advanced to full transcript
        self.assertEqual(spool.list_jobs(), [])     # job consumed

    def test_process_job_idempotent_second_run_is_empty(self):
        projectdir.ensure_runtime_dirs()
        cfg = {"mode": "deterministic"}
        tp = str(FIXTURES / "transcript_t1.jsonl")
        p1 = spool.write(spool.Job(event="SessionEnd", session_id="t1", transcript_path=tp, cwd="/proj"))
        self.assertEqual(worker.process_job(p1, cfg), "ok")
        p2 = spool.write(spool.Job(event="SessionEnd", session_id="t1", transcript_path=tp, cwd="/proj"))
        self.assertEqual(worker.process_job(p2, cfg), "empty")  # nothing new past high-water


if __name__ == "__main__":
    unittest.main()
