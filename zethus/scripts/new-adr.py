#!/usr/bin/env python3
"""Create a new Architecture Decision Record from ``templates/adr.md`` and index it.

    python .github/zethus/scripts/new-adr.py "Use the outbox pattern for order events"

writes ``docs/adr/2026-01-15-use-the-outbox-pattern-for-order-events.md`` and adds a row to
``docs/adr/README.md`` (created if missing).

**Why the id is date-keyed, not a counter.** ``ADR-0042`` style numbering collides the moment two
branches each add "the next" ADR; a ``YYYY-MM-DD-slug`` id cannot, so parallel work never
renumbers anything at merge time.

**Why an index row.** A decision made in chat, a meeting or a PR thread binds nothing until it is
written down somewhere tracked. The index is the one place a reader can see every decision, and
the row is created in the same step as the record so the two never disagree.

Config (optional; the first Zethus config found, see ``_common.py``): ``adr.dir`` (default ``docs/adr``),
``adr.template`` (default this kit's ``templates/adr.md``).

Exit codes: 0 created · 2 usage error (bad date, empty title, file already exists).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    UsageError, cfg, check_date, fill, find_repo_root, load_config, read_template, rel, slugify,
    today, write_new,
)

STATUSES = ("Proposed", "Accepted", "Rejected", "Deprecated", "Superseded")
INDEX_HEADER = (
    "# Architecture decision records\n\n"
    "One row per decision, newest last. Each record is the source of truth; this table is the\n"
    "index. Rows are added by `new-adr.py`; update a row when its record's status changes.\n\n"
    "| ID | Title | Status | Date |\n"
    "|---|---|---|---|\n"
)


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def append_index(index: Path, adr_id: str, title: str, status: str, date: str) -> None:
    if not index.exists():
        index.parent.mkdir(parents=True, exist_ok=True)
        with open(index, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(INDEX_HEADER)
    existing = index.read_text(encoding="utf-8")
    row = f"| [{adr_id}]({adr_id}.md) | {_cell(title)} | {status} | {date} |\n"
    with open(index, "a", encoding="utf-8", newline="\n") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write(row)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="new-adr", description="Create a new ADR and index it.")
    p.add_argument("title", help="the decision, as a short title")
    p.add_argument("--status", default="Proposed", choices=STATUSES)
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--dir", help="ADR directory (default: adr.dir or docs/adr)")
    p.add_argument("--template", help="template path (default: adr.template or the kit's adr.md)")
    p.add_argument("--deciders", default="TBD", help="who decided (names or roles)")
    p.add_argument("--no-index", action="store_true", help="don't add a row to <dir>/README.md")
    p.add_argument("--repo", help="repository root (default: nearest .git ancestor of cwd)")
    p.add_argument("--config", help="config file")
    args = p.parse_args(argv)
    try:
        repo = Path(args.repo).resolve() if args.repo else find_repo_root()
        config, _ = load_config(repo, args.config)
        title = args.title.strip()
        date = check_date(args.date) if args.date else today()
        adr_id = f"{date}-{slugify(title)}"
        adr_dir = repo / (args.dir or cfg(config, "adr.dir", "docs/adr"))
        template = read_template("adr.md", args.template or cfg(config, "adr.template"), repo)
        path = adr_dir / f"{adr_id}.md"
        write_new(path, fill(template, {
            "id": adr_id, "title": title, "date": date, "status": args.status,
            "deciders": args.deciders,
        }))
        if not args.no_index:
            append_index(adr_dir / "README.md", adr_id, title, args.status, date)
        print(f"created {rel(path, repo)}")
        if not args.no_index:
            print(f"indexed in {rel(adr_dir / 'README.md', repo)}")
        return 0
    except UsageError as exc:
        print(f"new-adr: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
