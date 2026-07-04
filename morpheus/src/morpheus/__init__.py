"""Morpheus — automatic session memory consolidation ("dreaming") for Claude Code.

Before a session loses context (compaction, end) Morpheus reflects over the transcript delta
and consolidates durable facts into the per-project two-tier memory store, with a bounded
creative "association" pass. Named for the Greek god of dreams — the dreaming counterpart to
mnemosyne (memory).

Public API (thin wrappers over the engine; used by the CLI, the MCP server, and the hooks):

    import morpheus
    morpheus.dream(cwd, session_id="s1", transcript_path="/path/to/transcript.jsonl")
    morpheus.wake(cwd)            # -> recall digest string for SessionStart
    morpheus.list_dreams(cwd)     # -> recent dream-log entries

The reflection engine is selected by config (`headless` / `hybrid` / `deterministic`).
"""
from __future__ import annotations

__all__ = ["dream", "wake", "list_dreams", "__version__"]
__version__ = "0.4.0"


def dream(cwd, session_id="", transcript_path="", mode=None):
    """Consolidate a session's transcript delta into memory now (synchronous).

    Returns a summary dict: {outcome, session_id, cwd, mode}. `outcome` is "ok" when memory was
    written, "empty" when nothing new was past the high-water mark.
    """
    from morpheus.lib import config as _config, projectdir, spool
    from morpheus import worker

    cfg = _config.load()
    if mode:
        cfg["mode"] = mode
    projectdir.ensure_runtime_dirs()
    job = spool.Job(event="manual", session_id=session_id,
                    transcript_path=transcript_path, cwd=cwd)
    path = spool.write(job)
    outcome = worker.process_job(path, cfg)
    return {"outcome": outcome, "session_id": session_id, "cwd": cwd, "mode": cfg.get("mode")}


def wake(cwd, light=False):
    """Return the SessionStart recall digest (long-term memory index + recent dreams)."""
    from morpheus.lib import config as _config, digest
    cfg = _config.load()
    return digest.build(cwd, cfg.get("digest_dreams", 3), light=light)


def list_dreams(cwd, n=5):
    """Return the most recent dream-log entries for a project (list of {file, path})."""
    from morpheus.lib import projectdir
    ddir = projectdir.dreams_dir(cwd)
    if not ddir.is_dir():
        return []
    return [{"file": p.name, "path": str(p)}
            for p in sorted(ddir.glob("*.md"), reverse=True)[:n]]
