#!/usr/bin/env python3
"""Create a new spec from the full or minimum template.

    python .github/zethus/scripts/new-spec.py full "Retry failed webhook deliveries"
    python .github/zethus/scripts/new-spec.py minimum "Trim the audit log" --owner "Payments team"

writes ``docs/specs/<slug>.md`` with status ``DRAFT``.

**Full or minimum?** Use ``minimum`` when the change is one PR, the facts fit in a short table, and
there is at most one open decision. Use ``full`` when there is more than one phase, a measurement
behind the ask, or anything a reviewer will want to argue with. When in doubt, start minimum —
the minimum template's headings are a strict subset of the full one's, so promoting it later is
additive, never a rewrite.

Config (optional; the first Zethus config found, see ``_common.py``): ``spec.dir`` (default ``docs/specs``),
``spec.templates.full`` / ``spec.templates.minimum`` (default this kit's templates).

Exit codes: 0 created · 2 usage error (bad kind or date, empty title, file already exists).
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

KINDS = {"full": "spec-full.md", "minimum": "spec-minimum.md"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="new-spec", description="Create a new spec from a template.")
    p.add_argument("kind", choices=sorted(KINDS), help="which template")
    p.add_argument("title", help="what the spec is for, as a short title")
    p.add_argument("--owner", default="TBD", help="who signs the spec off")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--dir", help="spec directory (default: spec.dir or docs/specs)")
    p.add_argument("--template", help="template path (overrides the kind's default)")
    p.add_argument("--repo", help="repository root (default: nearest .git ancestor of cwd)")
    p.add_argument("--config", help="config file")
    args = p.parse_args(argv)
    try:
        repo = Path(args.repo).resolve() if args.repo else find_repo_root()
        config, _ = load_config(repo, args.config)
        title = args.title.strip()
        date = check_date(args.date) if args.date else today()
        spec_dir = repo / (args.dir or cfg(config, "spec.dir", "docs/specs"))
        override = args.template or cfg(config, f"spec.templates.{args.kind}")
        template = read_template(KINDS[args.kind], override, repo)
        path = spec_dir / f"{slugify(title)}.md"
        write_new(path, fill(template, {
            "title": title, "date": date, "owner": args.owner, "status": "DRAFT",
        }))
        print(f"created {rel(path, repo)} ({args.kind}, DRAFT)")
        return 0
    except UsageError as exc:
        print(f"new-spec: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
