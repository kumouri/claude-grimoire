"""Deterministic engine — zero added tokens, no LLM.

Heuristically extracts a project memory (session topic + files touched + user
corrections) plus a few feedback memories. Fully testable offline; output is
stable for a given transcript. No 'association' pass (that needs reflection).
"""
from __future__ import annotations

import re

from engines.base import DreamResult
from lib import memory as memlib
from lib.redact import redact

_CORRECTION = re.compile(
    r"\b(no,|actually|instead|don'?t|do not|stop|prefer|should(?:n'?t)?\b|not that|wrong|never\b)",
    re.I,
)


class DeterministicEngine:
    name = "deterministic"

    def run(self, *, messages, cfg, session_id="", cwd="", **_):
        user_msgs = [m for m in messages if m.role == "user"]
        files = sorted({f for m in messages for f in m.files})

        corrections = []
        for m in user_msgs:
            for line in m.text.splitlines():
                s = line.strip()
                if _CORRECTION.search(s) and len(s) > 12:
                    corrections.append(redact(s))

        cap = int(cfg.get("max_new_memories", 8))
        mems = []

        topic = _topic(user_msgs)
        if topic:
            mems.append(memlib.Memory(
                name=memlib.slugify(topic)[:48],
                description=f"Session activity: {topic}"[:160],
                type="project",
                body=_project_body(topic, files, corrections),
                origin_session=session_id,
                index_title=topic[:60],
                index_hook="auto-captured by dreaming (deterministic)",
            ))

        for c in corrections[: max(0, cap - len(mems))][:3]:
            mems.append(memlib.Memory(
                name=memlib.slugify(c)[:48],
                description=c[:140],
                type="feedback",
                body=(
                    f"{c}\n\n"
                    "**Why:** user correction captured automatically during dreaming.\n"
                    "**How to apply:** honor this preference in future sessions."
                ),
                origin_session=session_id,
                index_title=c[:60],
                index_hook="user correction (deterministic capture)",
            ))

        summary = (
            f"Deterministic dream: {len(mems)} memory candidate(s); "
            f"{len(files)} file(s) touched; {len(corrections)} correction(s)."
        )
        return DreamResult(
            summary=summary, memories=mems[:cap],
            processed_count=len(messages), engine=self.name,
        )


def _topic(user_msgs) -> str:
    for m in user_msgs:
        t = (m.text or "").strip()
        if t and not t.startswith("<"):
            return t.splitlines()[0][:80]
    return ""


def _project_body(topic, files, corrections) -> str:
    lines = [f"Worked on: {topic}", ""]
    if files:
        lines.append("Files touched: " + ", ".join(f"`{f}`" for f in files[:20]))
    if corrections:
        lines.append("")
        lines.append("User corrections noted:")
        lines += [f"- {c}" for c in corrections[:8]]
    return "\n".join(lines)
