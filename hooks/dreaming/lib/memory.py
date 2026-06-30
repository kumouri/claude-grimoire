"""Read/write the two-tier memory store.

Files: ``memory/<type>-<slug>.md`` with frontmatter (name, description,
metadata.{node_type, type, originSessionId}) and a wikilink-friendly body.
Index: ``memory/MEMORY.md`` with lines ``- [Title](file.md) — hook``.

A tiny purpose-built frontmatter parser is used so the package stays
dependency-free (no PyYAML).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

INDEX_NAME = "MEMORY.md"
INDEX_HEADER = "# Memory Index"
VALID_TYPES = ("user", "feedback", "project", "reference")

_FM = re.compile(r"^---\n(.*?)\n---\n?(.*)$", re.S)


@dataclass
class Memory:
    name: str
    description: str
    type: str
    body: str
    origin_session: str = ""
    index_title: str = ""
    index_hook: str = ""


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "untitled"


def canonical_name(mem: Memory) -> str:
    name = slugify(mem.name)
    if not name.startswith(mem.type + "-"):
        name = f"{mem.type}-{name}"
    return name


def filename(mem: Memory) -> str:
    return canonical_name(mem) + ".md"


def render(mem: Memory) -> str:
    fm = [
        "---",
        f"name: {canonical_name(mem)}",
        f"description: {mem.description}",
        "metadata:",
        "  node_type: memory",
        f"  type: {mem.type}",
    ]
    if mem.origin_session:
        fm.append(f"  originSessionId: {mem.origin_session}")
    fm.append("---")
    return "\n".join(fm) + "\n\n" + mem.body.rstrip() + "\n"


def parse(path) -> "Memory | None":
    try:
        text = Path(path).read_text(encoding="utf-8")
    except Exception:
        return None
    m = _FM.match(text)
    if not m:
        return None
    block, body = m.group(1), m.group(2).lstrip("\n")

    def grab(key, indented=False):
        pat = rf"^\s*{key}:\s*(.+)$" if indented else rf"^{key}:\s*(.+)$"
        r = re.search(pat, block, re.M)
        return r.group(1).strip() if r else ""

    typ = grab("type", indented=True) or "reference"
    return Memory(
        name=grab("name"),
        description=grab("description"),
        type=typ,
        body=body,
        origin_session=grab("originSessionId", indented=True),
    )


def list_memories(memory_dir) -> dict:
    d = Path(memory_dir)
    out = {}
    if not d.is_dir():
        return out
    for p in d.glob("*.md"):
        if p.name == INDEX_NAME:
            continue
        mem = parse(p)
        if mem:
            out[mem.name or p.stem] = mem
    return out


# --- index -----------------------------------------------------------------

def _index_line(mem: Memory) -> str:
    title = mem.index_title or (mem.description[:60] if mem.description else canonical_name(mem))
    hook = mem.index_hook or mem.description or "memory"
    return f"- [{title}]({filename(mem)}) — {hook}"


def read_index(memory_dir) -> list:
    p = Path(memory_dir) / INDEX_NAME
    lines = []
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("- ["):
                lines.append(line.rstrip())
    return lines


def update_index(memory_dir, mem: Memory) -> None:
    d = Path(memory_dir)
    d.mkdir(parents=True, exist_ok=True)
    fname = filename(mem)
    entries = [e for e in read_index(d) if f"({fname})" not in e]
    entries.append(_index_line(mem))
    entries.sort(key=str.lower)
    (d / INDEX_NAME).write_text(
        INDEX_HEADER + "\n\n" + "\n".join(entries) + "\n", encoding="utf-8"
    )


def upsert(memory_dir, mem: Memory) -> Path:
    d = Path(memory_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / filename(mem)
    path.write_text(render(mem), encoding="utf-8")
    update_index(d, mem)
    return path
