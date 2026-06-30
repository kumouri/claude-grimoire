"""Build the SessionStart 'wake' digest from long-term memory + recent dreams.

Returned as ``additionalContext`` so a new session starts already remembering
what prior sessions consolidated.
"""
from __future__ import annotations

from pathlib import Path

from lib import memory, projectdir


def _first_heading(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
            if line.strip():
                return line.strip()[:80]
    except Exception:
        pass
    return path.stem


def build(cwd: str, n_dreams: int = 3, light: bool = False) -> str:
    mdir = projectdir.memory_dir(cwd)
    parts = []

    idx = memory.read_index(mdir)
    if idx:
        parts.append("**Long-term memory (recalled):**")
        parts.extend(idx[:6] if light else idx)

    ddir = projectdir.dreams_dir(cwd)
    if ddir.is_dir() and not light:
        recent = sorted(ddir.glob("*.md"), reverse=True)[:n_dreams]
        if recent:
            parts.append("")
            parts.append("**Recent dreams:**")
            for f in recent:
                parts.append(f"- {_first_heading(f)}")

    if not parts:
        return ""
    return "🌙 Dreaming recall\n\n" + "\n".join(parts)
