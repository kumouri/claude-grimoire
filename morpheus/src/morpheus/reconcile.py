#!/usr/bin/env python3
"""Reconciliation sweep.

Scans all project transcripts and enqueues a dream job for any session whose
transcript has grown well past its high-water mark but has no recent dream —
catching sessions that ended via a crash, or were archived/deleted without
firing a clean SessionEnd (Claude Code has no archive/delete hook).

Intended to be run on a schedule (see install/schtask.windows.ps1,
launchd.macos.plist, cron.linux.txt). Safe to run anytime; it only enqueues,
the worker does the consolidation. Usage:

    python reconcile.py            # scan + enqueue + drain once
    python reconcile.py --no-drain # scan + enqueue only
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from morpheus.lib import config, highwater, projectdir, spool, transcript  # noqa: E402


def _session_and_cwd(records):
    session_id, cwd = "", ""
    for rec in records:
        if not isinstance(rec, dict):
            continue
        session_id = session_id or rec.get("sessionId") or ""
        cwd = cwd or rec.get("cwd") or ""
        if session_id and cwd:
            break
    return session_id, cwd


def _already_queued(session_id: str) -> bool:
    for p in spool.list_jobs():
        try:
            if spool.load(p).session_id == session_id:
                return True
        except Exception:
            continue
    return False


def sweep(cfg: dict) -> int:
    projectdir.ensure_runtime_dirs()
    projects = projectdir.claude_home_projects()
    enqueued = 0
    if not projects.is_dir():
        return 0
    for proj in projects.iterdir():
        if not proj.is_dir():
            continue
        for tpath in proj.glob("*.jsonl"):
            records = transcript.read_records(tpath)
            if not records:
                continue
            session_id, cwd = _session_and_cwd(records)
            if not session_id or not cwd:
                continue
            if len(records) - highwater.get(session_id) < cfg.get("min_delta_records", 6):
                continue
            if _already_queued(session_id):
                continue
            spool.write(spool.Job(event="reconcile", session_id=session_id,
                                  transcript_path=str(tpath), cwd=cwd))
            enqueued += 1
    return enqueued


def main(argv) -> int:
    cfg = config.load()
    if not cfg.get("enabled", True):
        return 0
    n = sweep(cfg)
    print(f"reconcile: enqueued {n} job(s)")
    if "--no-drain" not in argv and n:
        from morpheus import worker
        worker.drain_once(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
