"""Headless engine (default) — delegates reflection to a background ``claude -p``.

The subprocess reads the transcript delta, updates the memory store with its own
Read/Edit/Write tools, and returns a JSON object (summary + associations +
hypotheses) as its final message. ``--bare`` skips hook/skill/memory
auto-discovery (so this nested run does not itself trigger morpheus), and the
``CLAUDE_MORPHEUS=1`` sentinel is a second recursion guard.

The actual subprocess call is injected as ``runner`` so tests can mock it.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from morpheus.engines.base import DreamResult

HERE = Path(__file__).resolve().parent.parent  # the morpheus package dir
PROMPT = HERE / "prompts" / "dream.system.md"


def _default_runner(args, input_text, timeout, env):
    proc = subprocess.run(
        args, input=input_text, capture_output=True, text=True,
        timeout=timeout, env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def parse_result_json(stdout: str) -> dict:
    """Extract the model's JSON object from a ``--output-format json`` envelope."""
    text = stdout
    try:
        envelope = json.loads(stdout)
        if isinstance(envelope, dict) and "result" in envelope:
            text = envelope["result"]
    except Exception:
        pass
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text or "")
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return {"summary": (text or "").strip()[:4000]}


class HeadlessEngine:
    name = "headless"

    def __init__(self, runner=None):
        self.runner = runner or _default_runner

    def run(self, *, rendered, memory_dir, cfg, session_id="", cwd="", **_):
        env = dict(os.environ)
        env["CLAUDE_MORPHEUS"] = "1"
        args = [
            cfg.get("claude_bin", "claude"), "-p", "--bare",
            "--permission-mode", "acceptEdits",
            "--allowedTools", "Read,Edit,Write",
            "--add-dir", str(memory_dir),
            "--append-system-prompt-file", str(PROMPT),
            "--output-format", "json",
        ]
        if cfg.get("model"):
            args += ["--model", cfg["model"]]

        rc, out, err = self.runner(
            args, _task(memory_dir, session_id, cwd, rendered, cfg),
            cfg.get("dream_timeout_sec", 240), env,
        )
        if rc != 0:
            raise RuntimeError(f"claude headless failed rc={rc}: {(err or '')[:500]}")

        data = parse_result_json(out)
        return DreamResult(
            summary=str(data.get("summary", ""))[:4000],
            associations=list(data.get("associations", []))[:20],
            hypotheses=list(data.get("hypotheses", []))[:20],
            memories=[],            # claude wrote them directly via tools
            wrote_directly=True,
            processed_count=int(data.get("processed_count", 0) or 0),
            engine=self.name,
        )


def _task(memory_dir, session_id, cwd, rendered, cfg) -> str:
    return (
        "You are DREAMING: consolidating the memory of a Claude Code session that just "
        "paused or ended.\n\n"
        f"Project working dir: {cwd}\n"
        f"Origin session id: {session_id}\n"
        f"Memory store (Read/Edit/Write here): {memory_dir}\n"
        f"Max new memories this dream: {cfg.get('max_new_memories', 8)}\n\n"
        "Consolidate the transcript delta below per the dreaming system prompt: update the "
        "memory files and MEMORY.md index, then output the required JSON object as your final "
        "message.\n\n"
        "=== TRANSCRIPT DELTA ===\n"
        f"{rendered}\n"
        "=== END DELTA ==="
    )
