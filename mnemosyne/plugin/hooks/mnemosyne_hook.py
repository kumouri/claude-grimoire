#!/usr/bin/env python3
"""Mnemosyne Claude Code hook bridge.

Invoked by the plugin's hooks.json with a mode argument. Reads the hook's JSON event on
stdin and drives the reflexion memory. It is deliberately fail-open: if the `mnemosyne`
package isn't installed, or there's no memory repo to point at, it exits 0 and stays silent
so it can never break a session.

Modes:
  prompt         (UserPromptSubmit) recall lessons for the user's prompt; print the digest,
                 which Claude Code injects as additional context. Silent when nothing matches.
  session-start  (SessionStart)     git-pull the shared memory so lessons are fresh. Silent.
  session-end    (SessionEnd)       one-line reminder to /reflect on anything durable learned.

Point it at a memory repo with $MNEMOSYNE_REPO (else it uses the cwd, and stays silent if
that isn't a memory repo). Optional $MNEMOSYNE_CONFIG selects a config.
"""
import json
import sys


def _load_event():
    try:
        return json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        return {}


def _mn():
    try:
        import mnemosyne as mn  # noqa: WPS433
        return mn
    except Exception:
        return None


def do_prompt():
    mn = _mn()
    if mn is None:
        return 0
    event = _load_event()
    prompt = (event.get("prompt") or "").strip()
    if not prompt:
        return 0
    try:
        digest = mn.recall(prompt, as_text=True)
    except Exception:
        return 0  # fail-open: no memory repo, bad config, etc.
    if not digest or "no reflexion lessons matched" in digest:
        return 0
    print("[Mnemosyne reflexion memory] Relevant prior lessons — apply them and tell the "
          "user which you applied:\n" + digest)
    return 0


def do_session_start():
    mn = _mn()
    if mn is None:
        return 0
    try:
        from mnemosyne import core, load_config, resolve_repo
        repo = resolve_repo(None)
        cfg = load_config(None, repo)
        core.sync(cfg, repo)  # best-effort git pull; ignores no-remote / no-git
    except Exception:
        return 0
    return 0


def do_session_end():
    mn = _mn()
    if mn is None:
        return 0
    # Only nudge if there's actually a memory repo to write to.
    try:
        from mnemosyne import resolve_repo
        resolve_repo(None)
    except Exception:
        return 0
    print("[Mnemosyne] If this session settled a decision or hit a real, reusable pitfall, "
          "capture it with /reflect (or /mnemosyne-reflect) so the next run recalls it.")
    return 0


MODES = {"prompt": do_prompt, "session-start": do_session_start, "session-end": do_session_end}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "prompt"
    fn = MODES.get(mode)
    if fn is None:
        return 0
    try:
        return fn()
    except Exception:
        return 0  # never let a hook error surface to the user


if __name__ == "__main__":
    sys.exit(main())
