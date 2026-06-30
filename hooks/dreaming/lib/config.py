"""Configuration loading for the dreaming feature.

Defaults are overridden by ``~/.claude/dreaming/config.json`` (if present) and
then by a few environment variables for quick toggling and tests.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS = {
    "enabled": True,
    "mode": "headless",            # headless | hybrid | deterministic
    "model": None,                 # None => claude default; hybrid falls back to hybrid_model
    "hybrid_model": "haiku",
    "min_delta_records": 6,        # skip dreaming below this many new transcript records
    "max_new_memories": 8,
    "claude_bin": "claude",
    "dream_timeout_sec": 240,
    "retry_max": 3,
    "redact_secrets": True,
    "auto_commit_memory": False,
    "digest_dreams": 3,            # recent dream-log entries surfaced on wake
    "light_digest_sources": ["compact"],  # SessionStart sources that get a lighter digest
}


def claude_home() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env) if env else Path.home() / ".claude"


def dreaming_home() -> Path:
    env = os.environ.get("CLAUDE_DREAMING_HOME")
    return Path(env) if env else claude_home() / "dreaming"


def config_path() -> Path:
    env = os.environ.get("CLAUDE_DREAMING_CONFIG")
    return Path(env) if env else dreaming_home() / "config.json"


def load() -> dict:
    """Return the effective config (defaults <- file <- env)."""
    cfg = dict(DEFAULTS)
    try:
        p = config_path()
        if p.is_file():
            user = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(user, dict):
                cfg.update({k: v for k, v in user.items() if v is not None})
    except Exception:
        pass  # never let a bad config break a session

    mode = os.environ.get("CLAUDE_DREAMING_MODE")
    if mode:
        cfg["mode"] = mode
    if os.environ.get("CLAUDE_DREAMING_DISABLED") == "1":
        cfg["enabled"] = False
    return cfg
