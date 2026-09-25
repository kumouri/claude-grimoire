#!/usr/bin/env python3
"""Dreaming background worker.

Drains the spool. For each job: acquire the project memory lock, compute the
transcript delta since the high-water mark, run the configured reflection
engine, write the resulting memories + a dream-log entry, advance the
high-water mark, and remove the job. Failures are retried (the job stays in the
spool) up to ``retry_max``, after which the job is quarantined in ``spool/failed``.

Usage:
    python worker.py --once     # drain the spool once and exit (default)
    python worker.py --watch    # keep draining on an interval
"""
from __future__ import annotations

import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from morpheus.engines.base import get_engine  # noqa: E402
from morpheus.lib import config, highwater, memory, projectdir, spool, transcript  # noqa: E402
from morpheus.lib.lock import FileLock  # noqa: E402
from morpheus.lib.redact import redact  # noqa: E402


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _log(msg: str) -> None:
    try:
        projectdir.morpheus_home().mkdir(parents=True, exist_ok=True)
        with open(projectdir.worker_log(), "a", encoding="utf-8") as fh:
            fh.write(f"{_now()} {msg}\n")
    except Exception:
        pass


def write_dream_log(job: spool.Job, result, memory_dir: Path) -> Path:
    ddir = projectdir.dreams_dir(job.cwd)
    ddir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = ddir / f"{stamp}-{(job.session_id or 'nosession')[:8]}.md"

    lines = [
        f"# Dream — {job.event} — {stamp}",
        "",
        f"- session: `{job.session_id}`",
        f"- engine: `{result.engine}`",
        f"- trigger: {job.trigger or job.reason or job.event}",
        f"- records consolidated: {result.processed_count}",
        "",
        "## Summary",
        "",
        result.summary or "(none)",
    ]
    names = [getattr(m, "name", str(m)) for m in result.memories] if not result.wrote_directly \
        else list(result.memories)
    if names:
        lines += ["", "## Memories written", ""] + [f"- `{n}`" for n in names]
    if result.associations:
        lines += ["", "## Associations (speculative)", ""] + [f"- {a}" for a in result.associations]
    if result.hypotheses:
        lines += ["", "## Hypotheses for next session", ""] + [f"- {h}" for h in result.hypotheses]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def maybe_commit(memory_dir: Path, cfg: dict) -> None:
    if not cfg.get("auto_commit_memory"):
        return
    import subprocess
    if not (memory_dir / ".git").exists() and not (memory_dir.parent / ".git").exists():
        return
    # No visible console window from the console-less worker (0 outside Windows).
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.run(["git", "-C", str(memory_dir), "add", "-A"],
                       capture_output=True, timeout=30, creationflags=flags)
        subprocess.run(["git", "-C", str(memory_dir), "commit", "-m",
                        "dream: consolidate session memory"],
                       capture_output=True, timeout=30, creationflags=flags)
    except Exception:
        pass


def process_job(path: Path, cfg: dict) -> str:
    job = spool.load(path)
    memory_dir = projectdir.memory_dir(job.cwd)
    lock_path = projectdir.locks_dir() / (projectdir.slug_for_cwd(job.cwd) + ".lock")

    with FileLock(lock_path):
        records = transcript.read_records(job.transcript_path)
        since = highwater.get(job.session_id)
        new_records, total = transcript.delta(records, since)
        if not new_records:
            spool.remove(path)
            return "empty"

        msgs = transcript.normalize(new_records)
        if cfg.get("redact_secrets", True):
            for m in msgs:
                m.text = redact(m.text)
        rendered = transcript.render(msgs)
        store = memory.list_memories(memory_dir)

        engine = get_engine(cfg.get("mode", "headless"))
        result = engine.run(
            messages=msgs, rendered=rendered, memory_store=store,
            memory_dir=memory_dir, cfg=cfg, session_id=job.session_id, cwd=job.cwd,
        )
        if not result.processed_count:
            result.processed_count = len(new_records)

        if not result.wrote_directly:
            for mem in result.memories[: cfg.get("max_new_memories", 8)]:
                memory.upsert(memory_dir, mem)

        write_dream_log(job, result, memory_dir)
        highwater.set(job.session_id, total, _now())
        maybe_commit(memory_dir, cfg)
        spool.remove(path)
        return "ok"


def drain_once(cfg: dict) -> dict:
    stats = {"ok": 0, "empty": 0, "failed": 0, "retry": 0}
    for path in spool.list_jobs():
        try:
            outcome = process_job(path, cfg)
            stats[outcome] = stats.get(outcome, 0) + 1
            _log(f"job {path.name}: {outcome}")
        except Exception as exc:  # noqa: BLE001
            try:
                job = spool.load(path)
                job.attempts += 1
                if job.attempts >= cfg.get("retry_max", 3):
                    spool.fail(path, job)
                    stats["failed"] += 1
                    _log(f"job {path.name}: FAILED (quarantined) {exc}")
                else:
                    spool.write(job)  # rewrite with bumped attempts; stays queued
                    stats["retry"] += 1
                    _log(f"job {path.name}: retry {job.attempts} ({exc})")
            except Exception:
                _log(f"job {path.name}: unrecoverable {exc}")
    return stats


def main(argv) -> int:
    cfg = config.load()
    projectdir.ensure_runtime_dirs()
    watch = "--watch" in argv
    if watch:
        interval = 30
        while True:
            drain_once(cfg)
            time.sleep(interval)
    drain_once(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
