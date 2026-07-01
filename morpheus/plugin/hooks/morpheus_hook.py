#!/usr/bin/env python3
"""Morpheus Claude Code hook bridge.

Invoked by the plugin's hooks.json for SessionStart / PreCompact / SessionEnd. Reads the hook's
JSON event on stdin and routes it to the morpheus dispatcher (which decides whether to dream,
build a wake digest, etc.). Deliberately fail-open: if the `morpheus` package isn't installed it
exits 0 and stays silent, so it can never break a session.

Requires `pip install morpheus-dreaming`. The dispatcher reads the event type from the stdin
JSON, so no mode argument is needed here.
"""
import sys


def main():
    try:
        from morpheus.dispatch import main as dispatch_main
    except Exception:
        return 0  # package not installed -> stay silent
    try:
        return dispatch_main()
    except Exception:
        return 0  # never let a hook error surface to the user


if __name__ == "__main__":
    sys.exit(main())
