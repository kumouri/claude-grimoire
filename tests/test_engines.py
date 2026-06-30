import json
import tempfile
import unittest
from pathlib import Path

from tests._util import FIXTURES
from lib import transcript, config
from engines.deterministic import DeterministicEngine
from engines.headless import HeadlessEngine, parse_result_json
from engines.hybrid import HybridEngine


def _messages():
    return transcript.normalize(transcript.read_records(FIXTURES / "transcript_t1.jsonl"))


class DeterministicEngineTest(unittest.TestCase):
    def test_produces_project_and_feedback(self):
        res = DeterministicEngine().run(messages=_messages(), cfg=config.DEFAULTS,
                                        session_id="t1", cwd="/proj")
        self.assertFalse(res.wrote_directly)
        self.assertEqual(res.engine, "deterministic")
        types = sorted({m.type for m in res.memories})
        self.assertIn("project", types)
        self.assertIn("feedback", types)
        # the correction line should surface as a feedback memory
        fb = [m for m in res.memories if m.type == "feedback"]
        self.assertTrue(any("dependency injection" in m.description.lower() for m in fb))
        # files captured in the project body
        proj = [m for m in res.memories if m.type == "project"][0]
        self.assertIn("src/auth.py", proj.body)

    def test_respects_cap(self):
        cfg = dict(config.DEFAULTS, max_new_memories=1)
        res = DeterministicEngine().run(messages=_messages(), cfg=cfg, session_id="t1")
        self.assertLessEqual(len(res.memories), 1)


class HeadlessEngineTest(unittest.TestCase):
    def test_parse_result_json_envelope(self):
        inner = {"summary": "s", "associations": ["a"], "hypotheses": ["h"], "processed_count": 3}
        envelope = json.dumps({"result": json.dumps(inner)})
        self.assertEqual(parse_result_json(envelope)["summary"], "s")

    def test_parse_result_json_embedded(self):
        text = 'prose before {"summary": "x"} after'
        self.assertEqual(parse_result_json(text)["summary"], "x")

    def test_run_with_mock_runner(self):
        inner = {"summary": "consolidated", "associations": ["auth~tests"],
                 "hypotheses": ["check DI"], "processed_count": 5}

        def fake_runner(args, input_text, timeout, env):
            assert env.get("CLAUDE_DREAMING") == "1"  # recursion sentinel set
            assert "--bare" in args
            return 0, json.dumps({"result": json.dumps(inner)}), ""

        with tempfile.TemporaryDirectory() as d:
            res = HeadlessEngine(runner=fake_runner).run(
                rendered="delta", memory_dir=Path(d), cfg=config.DEFAULTS,
                session_id="t1", cwd="/proj",
            )
        self.assertTrue(res.wrote_directly)
        self.assertEqual(res.summary, "consolidated")
        self.assertEqual(res.associations, ["auth~tests"])

    def test_run_raises_on_nonzero(self):
        def fake_runner(args, input_text, timeout, env):
            return 1, "", "boom"
        with self.assertRaises(RuntimeError):
            HeadlessEngine(runner=fake_runner).run(
                rendered="x", memory_dir=Path("."), cfg=config.DEFAULTS)


class HybridEngineTest(unittest.TestCase):
    def test_run_with_mock_runner_builds_memories(self):
        inner = {
            "summary": "hybrid recap",
            "memories": [{"name": "prefer-di", "type": "feedback",
                          "description": "DI preferred", "body": "use DI",
                          "index_title": "DI", "index_hook": "no globals"}],
            "associations": [], "hypotheses": [],
        }

        def fake_runner(args, input_text, timeout, env):
            assert "--model" in args
            return 0, json.dumps({"result": json.dumps(inner)}), ""

        res = HybridEngine(runner=fake_runner).run(
            messages=_messages(), rendered="delta", memory_store={},
            cfg=config.DEFAULTS, session_id="t1", cwd="/proj",
        )
        self.assertFalse(res.wrote_directly)
        self.assertEqual(len(res.memories), 1)
        self.assertEqual(res.memories[0].type, "feedback")
        self.assertEqual(res.summary, "hybrid recap")


if __name__ == "__main__":
    unittest.main()
