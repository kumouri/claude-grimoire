#!/usr/bin/env python3
"""Install the Zethus kit into a repository's ``.github/`` directory.

    python zethus/install.py --target path/to/your-repo            # install
    python zethus/install.py --target path/to/your-repo --dry-run  # show the plan only

What goes where (all under the target's ``.github/``):

    copilot-instructions.md        -> copilot-instructions.md
    instructions/*.instructions.md -> instructions/
    agents/*.agent.md              -> agents/
    skills/<name>/                 -> skills/<name>/
    templates/*.md                 -> zethus/templates/
    scripts/*.py                   -> zethus/scripts/
    zethus.config.example.json     -> zethus.config.json   (only if absent; never overwritten)

Two files belong to the repo, not the kit, and are never clobbered:

- If the repo already has a ``copilot-instructions.md``, the kit's rules go into
  ``instructions/zethus.instructions.md`` with ``applyTo: "**"``. Copilot combines the two, so
  the repo keeps its own file untouched.
- An existing ``zethus.config.json`` is left alone, even with ``--force``.

Any other file that already exists is a conflict. Without ``--force`` the installer lists every
conflict and writes **nothing**, so a repo is never left half-installed.

Exit codes: 0 installed (or dry run) · 1 conflicts, nothing written · 2 usage error.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
FALLBACK_INSTRUCTIONS = Path("instructions") / "zethus.instructions.md"
FALLBACK_FRONTMATTER = (
    "---\n"
    "name: Zethus working agreement\n"
    "description: Standing delivery rules installed by the Zethus kit.\n"
    'applyTo: "**"\n'
    "---\n\n"
)


def plan(target_github: Path) -> list[tuple[Path | None, Path, str]]:
    """Return ``(source, dest, action)``; action is create | overwrite-candidate | keep | adapt."""
    items: list[tuple[Path | None, Path]] = []
    for src in sorted((KIT / "instructions").glob("*.instructions.md")):
        items.append((src, Path("instructions") / src.name))
    for src in sorted((KIT / "agents").glob("*.agent.md")):
        items.append((src, Path("agents") / src.name))
    for skill in sorted(p for p in (KIT / "skills").iterdir() if p.is_dir()):
        for src in sorted(f for f in skill.rglob("*") if f.is_file()):
            items.append((src, Path("skills") / skill.name / src.relative_to(skill)))
    for src in sorted((KIT / "templates").glob("*.md")):
        items.append((src, Path("zethus") / "templates" / src.name))
    for src in sorted((KIT / "scripts").glob("*.py")):
        items.append((src, Path("zethus") / "scripts" / src.name))

    steps: list[tuple[Path | None, Path, str]] = []
    instructions = KIT / "copilot-instructions.md"
    if (target_github / "copilot-instructions.md").exists():
        dest = FALLBACK_INSTRUCTIONS
        steps.append((instructions, dest, "conflict" if (target_github / dest).exists() else "adapt"))
    else:
        steps.append((instructions, Path("copilot-instructions.md"), "create"))
    for src, dest in items:
        steps.append((src, dest, "conflict" if (target_github / dest).exists() else "create"))
    config = Path("zethus.config.json")
    steps.append((KIT / "zethus.config.example.json", config,
                  "keep" if (target_github / config).exists() else "create"))
    return steps


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="install", description="Install the Zethus kit into a repo.")
    p.add_argument("--target", required=True, help="root of the repository to install into")
    p.add_argument("--force", action="store_true", help="overwrite existing kit files")
    p.add_argument("--dry-run", action="store_true", help="print the plan; write nothing")
    args = p.parse_args(argv)

    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"install: target is not a directory: {args.target}", file=sys.stderr)
        return 2
    github = target / ".github"
    steps = plan(github)
    conflicts = [d for _, d, a in steps if a == "conflict"]
    if conflicts and not args.force:
        print("install: these files already exist; nothing was written. Re-run with --force to "
              "overwrite them:")
        for dest in conflicts:
            print(f"  .github/{dest.as_posix()}")
        return 1

    for src, dest, action in steps:
        label = {"create": "create", "adapt": "create", "conflict": "overwrite", "keep": "keep"}[action]
        note = ""
        if action == "adapt":
            note = "  (repo has its own copilot-instructions.md; installed as path-scoped instructions)"
        if action == "keep":
            note = "  (existing config left untouched)"
        print(f"{label:9} .github/{dest.as_posix()}{note}")
        if args.dry_run or action == "keep" or src is None:
            continue
        out = github / dest
        out.parent.mkdir(parents=True, exist_ok=True)
        if action == "adapt" or (action == "conflict" and dest == FALLBACK_INSTRUCTIONS):
            text = src.read_text(encoding="utf-8")
            with open(out, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(FALLBACK_FRONTMATTER + text)
        else:
            shutil.copyfile(src, out)
    if args.dry_run:
        print("dry run: nothing written")
    else:
        print("installed. Next: edit .github/zethus.config.json (gates.steps first), then run "
              "python .github/zethus/scripts/run-local-gates.py --list")
    return 0


if __name__ == "__main__":
    sys.exit(main())
