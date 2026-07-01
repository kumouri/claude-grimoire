"""Map a session's working directory to its Claude project + memory paths,
and expose the dreaming runtime directories.

Claude Code stores per-project data under ``~/.claude/projects/<slug>`` where
``<slug>`` is the absolute cwd with every non-alphanumeric character replaced by
``-`` (e.g. ``C:\\Users\\willa\\repo`` -> ``C--Users-willa-repo``).
"""
from __future__ import annotations

import re
from pathlib import Path

from morpheus.lib.config import claude_home, morpheus_home


def slug_for_cwd(cwd: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", cwd or "")


def claude_home_projects() -> Path:
    return claude_home() / "projects"


def project_dir(cwd: str) -> Path:
    return claude_home() / "projects" / slug_for_cwd(cwd)


def memory_dir(cwd: str) -> Path:
    return project_dir(cwd) / "memory"


def dreams_dir(cwd: str) -> Path:
    return memory_dir(cwd) / "dreams"


# --- dreaming runtime dirs -------------------------------------------------

def spool_dir() -> Path:
    return morpheus_home() / "spool"


def failed_dir() -> Path:
    return morpheus_home() / "spool" / "failed"


def state_dir() -> Path:
    return morpheus_home() / "state"


def locks_dir() -> Path:
    return morpheus_home() / "locks"


def worker_log() -> Path:
    return morpheus_home() / "worker.log"


def ensure_runtime_dirs() -> None:
    for d in (spool_dir(), failed_dir(), state_dir(), locks_dir()):
        d.mkdir(parents=True, exist_ok=True)
