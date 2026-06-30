"""Per-session high-water mark.

Records how many transcript records have already been consolidated for a given
session, so a PreCompact dream mid-session and the later SessionEnd dream never
re-ingest the same messages.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from lib import projectdir
from lib.lock import FileLock


def _file() -> Path:
    return projectdir.state_dir() / "highwater.json"


def _load() -> dict:
    p = _file()
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    except Exception:
        return {}


def get(session_id: str) -> int:
    rec = _load().get(session_id)
    if isinstance(rec, dict):
        try:
            return int(rec.get("count", 0))
        except (TypeError, ValueError):
            return 0
    return 0


def set(session_id: str, count: int, ts: str = "") -> None:
    projectdir.state_dir().mkdir(parents=True, exist_ok=True)
    with FileLock(projectdir.locks_dir() / "highwater.lock"):
        data = _load()
        data[session_id] = {"count": int(count), "updated": ts}
        f = _file()
        tmp = f.with_name(f.name + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(tmp, f)
