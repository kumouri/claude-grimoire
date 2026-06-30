import unittest

from tests._util import TempHomeTest
from lib import spool, highwater, projectdir
from lib.lock import FileLock, LockError


class SpoolTest(TempHomeTest):
    def test_write_list_load_remove(self):
        projectdir.ensure_runtime_dirs()
        job = spool.Job(event="SessionEnd", session_id="abc12345",
                        transcript_path="/t.jsonl", cwd="/proj")
        path = spool.write(job)
        self.assertTrue(path.is_file())
        jobs = spool.list_jobs()
        self.assertEqual(len(jobs), 1)
        loaded = spool.load(jobs[0])
        self.assertEqual(loaded.session_id, "abc12345")
        self.assertEqual(loaded.event, "SessionEnd")
        spool.remove(jobs[0])
        self.assertEqual(spool.list_jobs(), [])

    def test_fail_quarantines(self):
        projectdir.ensure_runtime_dirs()
        job = spool.Job(event="PreCompact", session_id="x", transcript_path="/t", cwd="/p")
        path = spool.write(job)
        spool.fail(path, job)
        self.assertFalse(path.is_file())
        self.assertEqual(len(list(projectdir.failed_dir().glob("*.json"))), 1)


class HighwaterTest(TempHomeTest):
    def test_get_set(self):
        self.assertEqual(highwater.get("s1"), 0)
        highwater.set("s1", 12, "now")
        self.assertEqual(highwater.get("s1"), 12)
        highwater.set("s2", 3, "now")
        self.assertEqual(highwater.get("s1"), 12)
        self.assertEqual(highwater.get("s2"), 3)


class LockTest(TempHomeTest):
    def test_exclusive(self):
        projectdir.ensure_runtime_dirs()
        p = projectdir.locks_dir() / "x.lock"
        with FileLock(p):
            with self.assertRaises(LockError):
                FileLock(p, timeout=0.3, poll=0.05).acquire()
        # released -> acquirable again
        FileLock(p, timeout=1).acquire().release()


if __name__ == "__main__":
    unittest.main()
