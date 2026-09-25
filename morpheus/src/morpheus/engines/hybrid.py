"""Hybrid engine — deterministic prefilter, then a small bounded LLM pass.

The deterministic engine shrinks the transcript into candidate signals; a cheap
model (haiku by default) refines them into structured memories + associations.
Unlike headless, the model returns data and *this process* writes the memory
files (``wrote_directly=False``), so the write path is identical to deterministic.

The subprocess call is injected as ``runner`` for testing.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from morpheus.engines.base import DreamResult
from morpheus.engines.deterministic import DeterministicEngine
from morpheus.engines.headless import parse_result_json
from morpheus.lib import memory as memlib

HERE = Path(__file__).resolve().parent.parent
PROMPT = HERE / "prompts" / "dream.system.md"


def _default_runner(args, input_text, timeout, env):
    proc = subprocess.run(
        args, input=input_text, capture_output=True, text=True,
        timeout=timeout, env=env,
        # The worker is console-less (DETACHED_PROCESS), so on Windows a console
        # child would otherwise get a fresh visible window that steals focus.
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return proc.returncode, proc.stdout, proc.stderr


class HybridEngine:
    name = "hybrid"

    def __init__(self, runner=None):
        self.runner = runner or _default_runner

    def run(self, *, messages, rendered, memory_store, cfg, session_id="", cwd="", **_):
        pre = DeterministicEngine().run(
            messages=messages, cfg=cfg, session_id=session_id, cwd=cwd,
        )
        env = dict(os.environ)
        env["CLAUDE_MORPHEUS"] = "1"
        model = cfg.get("model") or cfg.get("hybrid_model", "haiku")
        args = [
            cfg.get("claude_bin", "claude"), "-p", "--bare",
            "--model", model, "--output-format", "json",
            "--append-system-prompt-file", str(PROMPT),
        ]
        rc, out, err = self.runner(
            args, _task(memory_store, pre, rendered, cfg, session_id),
            cfg.get("dream_timeout_sec", 240), env,
        )
        if rc != 0:
            raise RuntimeError(f"claude hybrid failed rc={rc}: {(err or '')[:500]}")

        data = parse_result_json(out)
        cap = int(cfg.get("max_new_memories", 8))
        mems = []
        for item in (data.get("memories") or [])[:cap]:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            mems.append(memlib.Memory(
                name=item["name"],
                description=item.get("description", ""),
                type=item.get("type", "reference"),
                body=item.get("body", ""),
                origin_session=session_id,
                index_title=item.get("index_title", ""),
                index_hook=item.get("index_hook", ""),
            ))
        return DreamResult(
            summary=str(data.get("summary", pre.summary))[:4000],
            memories=mems,
            associations=list(data.get("associations", []))[:20],
            hypotheses=list(data.get("hypotheses", []))[:20],
            processed_count=len(messages),
            engine=self.name,
        )


def _task(memory_store, pre, rendered, cfg, session_id) -> str:
    existing = "\n".join(f"- {k}" for k in sorted(memory_store)) or "(none yet)"
    candidates = "\n".join(f"- [{m.type}] {m.description}" for m in pre.memories) or "(none)"
    return (
        "You are DREAMING (hybrid mode): refine the pre-extracted candidates below into "
        "durable memories. Output ONLY the required JSON object (do not write files yourself).\n\n"
        f"Origin session id: {session_id}\n"
        f"Max new memories: {cfg.get('max_new_memories', 8)}\n\n"
        f"Existing memory names:\n{existing}\n\n"
        f"Deterministic candidates:\n{candidates}\n\n"
        "=== TRANSCRIPT DELTA ===\n"
        f"{rendered}\n"
        "=== END DELTA ===\n\n"
        'Return JSON: {"summary": str, "memories": [{"name","type","description",'
        '"body","index_title","index_hook"}], "associations": [str], "hypotheses": [str]}.'
    )
