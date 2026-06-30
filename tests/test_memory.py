import unittest
from pathlib import Path
import tempfile

from tests._util import PKG  # noqa: F401  (ensures sys.path)
from lib import memory


class MemoryStoreTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.mdir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_upsert_writes_file_and_index(self):
        mem = memory.Memory(
            name="prefer-di", description="User prefers dependency injection",
            type="feedback", body="Use DI, not global state.", origin_session="s1",
            index_title="Prefer DI", index_hook="no global state",
        )
        path = memory.upsert(self.mdir, mem)
        self.assertTrue(path.is_file())
        self.assertEqual(path.name, "feedback-prefer-di.md")
        text = path.read_text(encoding="utf-8")
        self.assertIn("name: feedback-prefer-di", text)
        self.assertIn("node_type: memory", text)
        self.assertIn("type: feedback", text)
        self.assertIn("originSessionId: s1", text)

        index = (self.mdir / "MEMORY.md").read_text(encoding="utf-8")
        self.assertIn("# Memory Index", index)
        self.assertIn("[Prefer DI](feedback-prefer-di.md) — no global state", index)

    def test_upsert_is_idempotent_in_index(self):
        mem = memory.Memory(name="topic", description="d", type="project", body="b")
        memory.upsert(self.mdir, mem)
        memory.upsert(self.mdir, mem)  # twice
        index = (self.mdir / "MEMORY.md").read_text(encoding="utf-8")
        self.assertEqual(index.count("(project-topic.md)"), 1)

    def test_parse_roundtrip(self):
        mem = memory.Memory(name="who", description="Ceryce is a dev", type="user",
                            body="Ceryce, she/her. [[project-x]]", origin_session="s9")
        path = memory.upsert(self.mdir, mem)
        parsed = memory.parse(path)
        self.assertEqual(parsed.name, "user-who")
        self.assertEqual(parsed.type, "user")
        self.assertEqual(parsed.origin_session, "s9")
        self.assertIn("[[project-x]]", parsed.body)

    def test_list_memories_skips_index(self):
        memory.upsert(self.mdir, memory.Memory(name="a", description="d", type="project", body="b"))
        memory.upsert(self.mdir, memory.Memory(name="b", description="d", type="reference", body="b"))
        store = memory.list_memories(self.mdir)
        self.assertEqual(set(store), {"project-a", "reference-b"})


if __name__ == "__main__":
    unittest.main()
