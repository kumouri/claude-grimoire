"""Tolerant reader for Claude Code session transcripts (JSONL).

The on-disk format is internal and version-unstable, so this parser is
deliberately defensive: it skips anything it doesn't understand and never raises
on a malformed line. The high-water unit is the raw record (line) count, which
is stable because transcripts only ever append.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Msg:
    role: str
    text: str
    tools: list = field(default_factory=list)   # tool names used
    files: list = field(default_factory=list)   # file paths touched (Edit/Write)


def read_records(path) -> list:
    p = Path(path)
    if not p.is_file():
        return []
    records = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    return records


def _block_text(block) -> str:
    if isinstance(block, str):
        return block
    if not isinstance(block, dict):
        return ""
    t = block.get("type")
    if t == "text":
        return block.get("text", "") or ""
    if t == "tool_result":
        c = block.get("content")
        if isinstance(c, list):
            return " ".join(_block_text(b) for b in c)
        return str(c) if c else ""
    return ""


def _tool_info(block):
    if isinstance(block, dict) and block.get("type") == "tool_use":
        inp = block.get("input") or {}
        finfo = inp.get("file_path") or inp.get("path") or "" if isinstance(inp, dict) else ""
        return block.get("name", ""), finfo
    return None, None


def normalize(records) -> list:
    """Turn raw records into a list of Msg (user/assistant only, no sidechains)."""
    msgs = []
    for rec in records:
        if not isinstance(rec, dict) or rec.get("isSidechain"):
            continue
        if rec.get("type") not in ("user", "assistant"):
            continue
        message = rec.get("message")
        if not isinstance(message, dict):
            message = rec  # some shapes inline content at top level
        role = message.get("role") or rec.get("type")
        content = message.get("content")
        text_parts, tools, files = [], [], []
        if isinstance(content, str):
            text_parts.append(content)
        elif isinstance(content, list):
            for block in content:
                txt = _block_text(block)
                if txt:
                    text_parts.append(txt)
                name, finfo = _tool_info(block)
                if name:
                    tools.append(name)
                if finfo:
                    files.append(finfo)
        text = "\n".join(t for t in text_parts if t).strip()
        if not text and not tools:
            continue
        msgs.append(Msg(role=role, text=text, tools=tools, files=files))
    return msgs


def delta(records, since: int):
    """Return (new_records, new_total_count). ``since`` is a record-count high-water."""
    total = len(records)
    since = max(0, min(since, total))
    return records[since:], total


def render(msgs, max_chars: int = 24000) -> str:
    lines = []
    for m in msgs:
        head = f"## {m.role}"
        if m.tools:
            head += f"  (tools: {', '.join(sorted(set(m.tools)))})"
        lines.append(head)
        if m.text:
            lines.append(m.text)
        if m.files:
            lines.append(f"[files: {', '.join(sorted(set(m.files)))}]")
        lines.append("")
    out = "\n".join(lines).strip()
    if len(out) > max_chars:
        out = out[:max_chars] + "\n\n[...truncated...]"
    return out
