#!/usr/bin/env python3
"""Installer for the morpheus hooks (standalone, non-plugin path).

Idempotently merges the PreCompact / SessionEnd / SessionStart hook commands into
``~/.claude/settings.json`` (global) or a project ``.claude/settings.json``,
creates the runtime dirs, and seeds ``config.json`` from the example. Prefer the
Morpheus/Grimoire *plugin* for a one-click install; use this for a manual global setup.

Usage (via the CLI):
    morpheus install                 # global (~/.claude/settings.json)
    morpheus install --project DIR   # DIR/.claude/settings.json
    morpheus install --uninstall     # remove the morpheus hooks
    morpheus install --dry-run       # show changes without writing
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent   # the morpheus package dir
DATA = HERE / "data"
DISPATCH = HERE / "dispatch.py"
SNIPPET = DATA / "settings.snippet.json"
CONFIG_EXAMPLE = DATA / "config.example.json"
EVENTS = ("PreCompact", "SessionEnd", "SessionStart")
MARKER = "dispatch.py"                  # identifies our hook entries


def claude_home() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(env) if env else Path.home() / ".claude"


def morpheus_home() -> Path:
    env = os.environ.get("CLAUDE_MORPHEUS_HOME")
    return Path(env) if env else claude_home() / "morpheus"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except Exception as exc:
        print(f"! could not parse {path}: {exc}", file=sys.stderr)
        return {}


def _our_groups() -> dict:
    # Parse first, then substitute into the decoded strings — never string-replace
    # into raw JSON (Windows paths contain backslashes that break JSON escapes).
    groups = json.loads(SNIPPET.read_text(encoding="utf-8"))["hooks"]
    py, disp = sys.executable, str(DISPATCH)
    for glist in groups.values():
        for group in glist:
            for h in group.get("hooks", []):
                if "command" in h:
                    h["command"] = h["command"].replace("<PY>", py).replace("<DISPATCH>", disp)
    return groups


def _is_ours(group: dict) -> bool:
    for h in group.get("hooks", []):
        if MARKER in (h.get("command") or ""):
            return True
    return False


def merge(settings: dict, uninstall: bool) -> dict:
    hooks = settings.setdefault("hooks", {})
    ours = _our_groups()
    for event in EVENTS:
        existing = [g for g in hooks.get(event, []) if not _is_ours(g)]
        if not uninstall:
            existing.extend(ours.get(event, []))
        if existing:
            hooks[event] = existing
        elif event in hooks:
            del hooks[event]
    if not hooks:
        settings.pop("hooks", None)
    return settings


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", metavar="DIR", help="install into DIR/.claude/settings.json")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.project:
        settings_path = Path(args.project).resolve() / ".claude" / "settings.json"
    else:
        settings_path = claude_home() / "settings.json"

    settings = _load_json(settings_path)
    updated = merge(dict(settings), args.uninstall)

    print(f"settings file : {settings_path}")
    print(f"dispatch      : {DISPATCH}")
    print(f"python        : {sys.executable}")
    print(f"action        : {'uninstall' if args.uninstall else 'install'}")
    print("hooks after   :")
    print(json.dumps(updated.get("hooks", {}), indent=2))

    if args.dry_run:
        print("\n(dry run — nothing written)")
        return 0

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    if settings_path.is_file():
        shutil.copy2(settings_path, settings_path.with_suffix(".json.bak"))
        print(f"backed up     : {settings_path.with_suffix('.json.bak')}")
    settings_path.write_text(json.dumps(updated, indent="\t") + "\n", encoding="utf-8")

    if not args.uninstall:
        # runtime dirs + seed config
        dh = morpheus_home()
        for sub in ("spool/failed", "state", "locks"):
            (dh / sub).mkdir(parents=True, exist_ok=True)
        cfg = dh / "config.json"
        if not cfg.is_file():
            shutil.copy2(CONFIG_EXAMPLE, cfg)
            print(f"seeded config : {cfg}")
        print("\n✓ morpheus installed. New sessions will dream on compaction & end.")
    else:
        print("\n✓ morpheus hooks removed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
