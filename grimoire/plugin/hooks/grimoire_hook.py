#!/usr/bin/env python3
"""Grimoire unified hook dispatcher — composes mnemosyne (memory) + morpheus (dreams).

The plugin registers this one script for SessionStart, UserPromptSubmit, PreCompact and
SessionEnd, so both engines' lifecycle concerns run from a single hook (no double-firing that
installing two separate plugins would cause):

  SessionStart     mnemosyne: git-pull shared memory   + morpheus: drain + wake digest
  UserPromptSubmit mnemosyne: recall lessons for the prompt (injected as context)
  PreCompact       morpheus:  dream (enqueue + spawn worker)
  SessionEnd       morpheus:  dream                     + mnemosyne: /reflect nudge

Fail-open: a missing engine package or any error exits 0 and stays silent, so it can never break
a session. Requires `pip install mnemosyne-reflexion morpheus-dreaming`.
"""
import json
import os
import sys


def _nested() -> bool:
    return (
        os.environ.get("CLAUDE_MORPHEUS") == "1"
        or os.environ.get("CLAUDE_CODE_CHILD_SESSION") == "1"
    )


def _event() -> dict:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _mnemosyne_sync() -> None:
    try:
        from mnemosyne import core, load_config, resolve_repo
        repo = resolve_repo(None)
        cfg = load_config(None, repo)
        core.sync(cfg, repo)  # best-effort git pull; ignores no-git / no-remote
    except Exception:
        pass


def _morpheus_wake(cwd: str) -> str:
    try:
        import morpheus
        from morpheus.dispatch import spawn_worker
        spawn_worker()  # drain any pending / interrupted dreams from last time
        return morpheus.wake(cwd) or ""
    except Exception:
        return ""


def on_session_start(data: dict) -> int:
    _mnemosyne_sync()
    ctx = _morpheus_wake(data.get("cwd", ""))
    if ctx:
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}
        }))
    return 0


def on_prompt(data: dict) -> int:
    try:
        import mnemosyne as mn
        prompt = (data.get("prompt") or "").strip()
        if prompt:
            digest = mn.recall(prompt, as_text=True)
            if digest and "no reflexion lessons matched" not in digest:
                print("[Mnemosyne reflexion memory] Relevant prior lessons — apply them and tell "
                      "the user which you applied:\n" + digest)
    except Exception:
        pass
    return 0


def on_dream(data: dict, event: str) -> int:
    try:
        from morpheus.lib import config, projectdir
        from morpheus import dispatch
        cfg = config.load()
        if cfg.get("enabled", True):
            projectdir.ensure_runtime_dirs()
            dispatch.handle_dream_trigger(data, cfg)  # threshold + enqueue + spawn (non-blocking)
    except Exception:
        pass
    if event == "SessionEnd":
        try:
            from mnemosyne import resolve_repo
            resolve_repo(None)  # only nudge if there's a memory repo to write to
            print("[Mnemosyne] If this session settled a decision or hit a real, reusable pitfall, "
                  "capture it with /reflect so the next run recalls it.")
        except Exception:
            pass
    return 0


def main() -> int:
    if _nested():
        return 0
    data = _event()
    event = data.get("hook_event_name", "")
    try:
        if event == "SessionStart":
            return on_session_start(data)
        if event == "UserPromptSubmit":
            return on_prompt(data)
        if event in ("PreCompact", "SessionEnd"):
            return on_dream(data, event)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
