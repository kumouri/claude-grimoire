"""`morpheus` command-line interface.

Subcommands over the same engine the hooks and MCP server use:

    morpheus dream --cwd DIR --transcript FILE [--session ID] [--mode MODE]
    morpheus wake  --cwd DIR [--light]
    morpheus dreams --cwd DIR [-n N]
    morpheus worker [--once|--watch]
    morpheus reconcile [--no-drain]
    morpheus install [--project DIR] [--uninstall] [--dry-run]
    morpheus selftest
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

PROG = "morpheus"


def _cmd_dream(args) -> int:
    import morpheus
    res = morpheus.dream(args.cwd, session_id=args.session or "",
                         transcript_path=args.transcript or "", mode=args.mode)
    print(json.dumps(res, indent=2))
    return 0


def _cmd_wake(args) -> int:
    import morpheus
    digest = morpheus.wake(args.cwd, light=args.light)
    if digest:
        print(digest)
    return 0


def _cmd_dreams(args) -> int:
    import morpheus
    for d in morpheus.list_dreams(args.cwd, n=args.n):
        print(d["path"])
    return 0


def _cmd_worker(args) -> int:
    from morpheus import worker
    return worker.main(["--watch"] if args.watch else ["--once"])


def _cmd_reconcile(args) -> int:
    from morpheus import reconcile
    return reconcile.main(["--no-drain"] if args.no_drain else [])


def _cmd_install(args) -> int:
    from morpheus import install
    argv = []
    if args.project:
        argv += ["--project", args.project]
    if args.uninstall:
        argv.append("--uninstall")
    if args.dry_run:
        argv.append("--dry-run")
    return install.main(argv)


def run_selftest() -> int:
    """Offline smoke test: a deterministic dream over a tiny transcript writes memory.

    Prints 'ALL PASS' on success (contract shared with the CI wrapper).
    """
    saved = {k: os.environ.get(k) for k in ("CLAUDE_CONFIG_DIR", "CLAUDE_MORPHEUS_HOME")}
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            os.environ["CLAUDE_CONFIG_DIR"] = str(root / ".claude")
            os.environ["CLAUDE_MORPHEUS_HOME"] = str(root / "morpheus")
            tp = root / "t.jsonl"
            tp.write_text(
                "\n".join([
                    json.dumps({"type": "user", "message": {"role": "user",
                                "content": "Refactor auth in src/auth.py; no, prefer dependency injection"}}),
                    json.dumps({"type": "assistant", "message": {"role": "assistant",
                                "content": [{"type": "text", "text": "Done, using DI."}]}}),
                ]),
                encoding="utf-8",
            )
            import morpheus
            res = morpheus.dream(str(root / "proj"), session_id="selftest",
                                 transcript_path=str(tp), mode="deterministic")
            digest = morpheus.wake(str(root / "proj"))
        checks = [
            ("dream wrote memory", res.get("outcome") == "ok"),
            ("wake digest built", bool(digest)),
        ]
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    ok = all(passed for _, passed in checks)
    for name, passed in checks:
        print(f"  [{'ok' if passed else 'XX'}] {name}")
    print("selftest: " + ("ALL PASS" if ok else "FAILED"))
    return 0 if ok else 1


def _cmd_selftest(_args) -> int:
    return run_selftest()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=PROG, description="Morpheus — session memory consolidation.")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("dream", help="consolidate a transcript delta into memory now")
    d.add_argument("--cwd", required=True, help="project working dir (keys the memory store)")
    d.add_argument("--transcript", help="path to the session transcript .jsonl")
    d.add_argument("--session", help="session id")
    d.add_argument("--mode", choices=["headless", "hybrid", "deterministic"], help="engine override")
    d.set_defaults(fn=_cmd_dream)

    w = sub.add_parser("wake", help="print the SessionStart recall digest")
    w.add_argument("--cwd", required=True)
    w.add_argument("--light", action="store_true")
    w.set_defaults(fn=_cmd_wake)

    ls = sub.add_parser("dreams", help="list recent dream-log entries")
    ls.add_argument("--cwd", required=True)
    ls.add_argument("-n", type=int, default=5)
    ls.set_defaults(fn=_cmd_dreams)

    wk = sub.add_parser("worker", help="drain the dream spool")
    wk.add_argument("--watch", action="store_true", help="keep draining on an interval")
    wk.set_defaults(fn=_cmd_worker)

    rc = sub.add_parser("reconcile", help="sweep crashed/archived sessions into the spool")
    rc.add_argument("--no-drain", action="store_true")
    rc.set_defaults(fn=_cmd_reconcile)

    ins = sub.add_parser("install", help="merge the morpheus hooks into settings.json")
    ins.add_argument("--project", help="install into DIR/.claude/settings.json")
    ins.add_argument("--uninstall", action="store_true")
    ins.add_argument("--dry-run", action="store_true")
    ins.set_defaults(fn=_cmd_install)

    st = sub.add_parser("selftest", help="run the offline smoke test")
    st.set_defaults(fn=_cmd_selftest)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
