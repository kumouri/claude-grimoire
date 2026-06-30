import unittest

from tests._util import FIXTURES  # noqa: F401
from lib import transcript


class TranscriptTest(unittest.TestCase):
    def setUp(self):
        self.path = FIXTURES / "transcript_t1.jsonl"
        self.records = transcript.read_records(self.path)

    def test_read_records_parses_all_lines(self):
        self.assertEqual(len(self.records), 10)

    def test_missing_file_is_empty(self):
        self.assertEqual(transcript.read_records(FIXTURES / "nope.jsonl"), [])

    def test_normalize_filters_meta_and_sidechains(self):
        msgs = transcript.normalize(self.records)
        roles = [m.role for m in msgs]
        # meta/system + sidechain excluded; user+assistant kept
        self.assertNotIn("system", roles)
        self.assertTrue(all(r in ("user", "assistant") for r in roles))
        joined = "\n".join(m.text for m in msgs)
        self.assertNotIn("sidechain noise", joined)
        self.assertIn("dependency injection", joined)

    def test_normalize_extracts_files_and_tools(self):
        msgs = transcript.normalize(self.records)
        files = sorted({f for m in msgs for f in m.files})
        tools = sorted({t for m in msgs for t in m.tools})
        self.assertEqual(files, ["src/auth.py", "src/container.py"])
        self.assertEqual(tools, ["Edit", "Write"])

    def test_tool_result_text_captured(self):
        msgs = transcript.normalize(self.records)
        self.assertIn("edit applied", "\n".join(m.text for m in msgs))

    def test_delta(self):
        new, total = transcript.delta(self.records, 4)
        self.assertEqual(total, 10)
        self.assertEqual(len(new), 6)
        # since beyond total clamps
        new2, total2 = transcript.delta(self.records, 999)
        self.assertEqual(new2, [])
        self.assertEqual(total2, 10)

    def test_render_truncates(self):
        msgs = transcript.normalize(self.records)
        out = transcript.render(msgs, max_chars=20)
        self.assertTrue(out.endswith("[...truncated...]"))


if __name__ == "__main__":
    unittest.main()
