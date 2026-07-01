"""Durable job spool.

Hooks enqueue a small JSON job descriptor and exit immediately; the background
worker drains the spool. The spool is the source of truth: a job survives
process death and is retried on the next drain, so a dream interrupted by the
session/app exiting is never lost.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from lib import projectdir


@dataclass
class Job:
    event: str                 # PreCompact | SessionEnd | manual
    session_id: str
    transcript_path: str
    cwd: str
    created_at: str = ""
    trigger: str = ""          # PreCompact: auto | manual
    reason: str = ""           # SessionEnd: clear | logout | ...
    attempts: int = 0
    id: str = ""


def _new_id(job: Job) -> str:
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    short = (job.session_id or "nosession")[:8]
    return f"{stamp}-{short}-{os.getpid()}"


def _atomic_write(path: Path, payload: dict) -> Path:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return path


def write(job: Job) -> Path:
    projectdir.spool_dir().mkdir(parents=True, exist_ok=True)
    if not job.id:
        job.id = _new_id(job)
    if not job.created_at:
        job.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return _atomic_write(projectdir.spool_dir() / f"{job.id}.json", asdict(job))


def list_jobs() -> list:
    d = projectdir.spool_dir()
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.json") if p.is_file())


def load(path) -> Job:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    fields = Job.__dataclass_fields__
    return Job(**{k: data[k] for k in fields if k in data and data[k] is not None})


def remove(path) -> None:
    Path(path).unlink(missing_ok=True)


def fail(path, job: Job) -> Path:
    """Move a job that exhausted its retries into the failed/ quarantine dir."""
    projectdir.failed_dir().mkdir(parents=True, exist_ok=True)
    dest = projectdir.failed_dir() / Path(path).name
    _atomic_write(dest, asdict(job))
    remove(path)
    return dest
