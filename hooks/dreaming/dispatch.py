#!/usr/bin/env python3
"""Dreaming hook dispatcher.

Registered for PreCompact, SessionEnd, and SessionStart. Reads the hook JSON on
stdin, and:

- PreCompact / SessionEnd: recursion-guard + threshold check, enqueue a durable
  spool job, spawn the detached worker, and exit 0 fast (never blocks the
  session). SessionEnd cannot block anyway; we just fire-and-forget.
- SessionStart: drain any pending/interrupted jobs and inject a 'wake' digest as
  additionalContext.

This script never raises into the host session: any error is swallowed with a
clean exit 0.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import config, digest, projectdir, spool, transcript  # noqa: E402


def _read_event() -> dict:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _is_nested() -> bool:
    return (
        os.environ.get("CLAUDE_DREAMING") == "1"
        or os.environ.get("CLAUDE_CODE_CHILD_SESSION") == "1"
    )


def spawn_worker() -> None:
    if os.environ.get("CLAUDE_DREAMING_NOSPAWN") == "1":
        return
    worker = str(Path(__file__).resolve().parent / "worker.py")
    args = [sys.executable, worker, "--once"]
    env = dict(os.environ)
    env["CLAUDE_DREAMING"] = "1"
    kwargs = dict(
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(Path(__file__).resolve().parent),
    )
    try:
        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(args, **kwargs)
    except Exception:
        pass  # durability is via the spool; a failed spawn is retried next lifecycle


def _emit_session_start(ctx: str) -> None:
    if not ctx:
        return
    out = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": ctx,
        }
    }
    sys.stdout.write(json.dumps(out))


def handle_session_start(data: dict, cfg: dict) -> None:
    spawn_worker()  # drain anything left from last time
    cwd = data.get("cwd", "")
    light = data.get("source") in cfg.get("light_digest_sources", [])
    try:
        ctx = digest.build(cwd, cfg.get("digest_dreams", 3), light=light)
    except Exception:
        ctx = ""
    _emit_session_start(ctx)


def handle_dream_trigger(data: dict, cfg: dict) -> None:
    cwd = data.get("cwd", "")
    session_id = data.get("session_id", "")
    transcript_path = data.get("transcript_path", "")
    event = data.get("hook_event_name", "")
    forced = bool(data.get("force"))

    # threshold: only dream if enough new records since the last high-water
    if not forced:
        try:
            from lib import highwater
            total = len(transcript.read_records(transcript_path))
            if total - highwater.get(session_id) < cfg.get("min_delta_records", 6):
                return
        except Exception:
            pass

    spool.write(spool.Job(
        event=event or "manual",
        session_id=session_id,
        transcript_path=transcript_path,
        cwd=cwd,
        trigger=data.get("trigger", ""),
        reason=data.get("reason", ""),
    ))
    spawn_worker()


def main() -> int:
    data = _read_event()
    if _is_nested():
        return 0
    cfg = config.load()
    if not cfg.get("enabled", True):
        return 0
    try:
        projectdir.ensure_runtime_dirs()
    except Exception:
        return 0

    event = data.get("hook_event_name", "")
    try:
        if event == "SessionStart":
            handle_session_start(data, cfg)
        elif event in ("PreCompact", "SessionEnd") or data.get("force"):
            handle_dream_trigger(data, cfg)
    except Exception:
        pass  # never break the host session
    return 0


if __name__ == "__main__":
    sys.exit(main())
