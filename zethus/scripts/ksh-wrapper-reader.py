#!/usr/bin/env python3
"""Read a `ksh` (or adjacent POSIX shell) batch wrapper for the shell-specific facts a generic
reader would miss: `batch-type-ksh-scripts` in `docs/batch-modernization.md`'s skill family.

Recovers, each as a rule-ledger-shaped row cited to `file:line`:

- **Argument parsing** (`getopts`) — the flags/options the script accepts, `kind: validation`.
- **Exit codes** (`exit N`) — the caller-facing contract; batch jobs are usually invoked by
  something that only sees the exit code, so this matters more here than in most code,
  `kind: error-handling`.
- **`trap` handlers** — signal names and the handler command, `kind: error-handling`.
- **File locking** (`flock`, or the `mkdir`-as-mutex idiom) — mutual exclusion between runs,
  `kind: orchestration`.
- **Retry/backoff loops** — a loop whose body both sleeps and compares an attempt counter against a
  limit. This is a heuristic over the script's *text*, not a shell parser, so it is reported at
  `Medium` confidence unless the loop's shape is unambiguous.

This is line-based pattern matching, not a POSIX shell parser — deliberately: a real parser is a
large dependency for what is, in every real script, a small and stereotyped set of idioms. What it
finds is a starting point for `recover-business-rules`, not the end of the reading.

Exit codes: 0 read the script, findings printed (empty is a valid finding: report it, don't guess) ·
2 usage error (matching every other Zethus script's convention).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import UsageError, find_repo_root, rel  # noqa: E402

GETOPTS_RE = re.compile(r"\bgetopts\s+[\"']?([A-Za-z0-9:]+)[\"']?\s+(\w+)")
EXIT_RE = re.compile(r"\bexit\s+(\d+)\b")
TRAP_RE = re.compile(r"\btrap\s+(['\"])(.*?)\1\s+((?:[A-Z0-9]+\s*)+)$")
FLOCK_RE = re.compile(r"\bflock\b")
LOCKFILE_MKDIR_RE = re.compile(r"\bmkdir\b.*\b(lock|LOCK)\w*")
LOOP_START_RE = re.compile(r"^\s*(while|until)\b")
LOOP_END_RE = re.compile(r"^\s*done\b")
SLEEP_RE = re.compile(r"\bsleep\s+")
COUNTER_CMP_RE = re.compile(r"\$\{?(\w*(?:retr(?:y|ies)|attempt|count)\w*)\}?\s*"
                            r"(?:-ge|-gt|-le|-lt|>=|<=|>|<)\s*(\d+)", re.I)


@dataclass
class Rule:
    id: str
    rule: str
    kind: str
    where: str
    confidence: str
    why: str


def find_arg_parsing(lines: list[str], display: str) -> list[Rule]:
    rules = []
    for lineno, line in enumerate(lines, 1):
        m = GETOPTS_RE.search(line)
        if m:
            rules.append(Rule(id=f"ARG-{lineno}",
                              rule=f"accepts options matching getopts spec {m.group(1)!r}",
                              kind="validation", where=f"{display}:{lineno}", confidence="High",
                              why="explicit getopts call"))
    return rules


def find_exit_codes(lines: list[str], display: str) -> list[Rule]:
    rules = []
    for lineno, line in enumerate(lines, 1):
        m = EXIT_RE.search(line)
        if m and not line.strip().startswith("#"):
            rules.append(Rule(id=f"EXIT-{lineno}", rule=f"exits with code {m.group(1)}",
                              kind="error-handling", where=f"{display}:{lineno}", confidence="High",
                              why="explicit exit statement"))
    return rules


def find_traps(lines: list[str], display: str) -> list[Rule]:
    rules = []
    for lineno, line in enumerate(lines, 1):
        m = TRAP_RE.search(line.strip())
        if m:
            signals = m.group(3).split()
            rules.append(Rule(id=f"TRAP-{lineno}",
                              rule=f"on {'/'.join(signals)}, runs: {m.group(2)}",
                              kind="error-handling", where=f"{display}:{lineno}", confidence="High",
                              why="explicit trap statement"))
    return rules


def find_locking(lines: list[str], display: str) -> list[Rule]:
    rules = []
    for lineno, line in enumerate(lines, 1):
        if FLOCK_RE.search(line):
            rules.append(Rule(id=f"LOCK-{lineno}", rule="uses flock for mutual exclusion",
                              kind="orchestration", where=f"{display}:{lineno}", confidence="High",
                              why="explicit flock call"))
        elif LOCKFILE_MKDIR_RE.search(line):
            rules.append(Rule(id=f"LOCK-{lineno}",
                              rule="uses a mkdir-as-mutex lock idiom for mutual exclusion",
                              kind="orchestration", where=f"{display}:{lineno}", confidence="Medium",
                              why="mkdir call naming a lock directory; inferred idiom, not a "
                                  "dedicated locking primitive"))
    return rules


def find_retry_loops(lines: list[str], display: str) -> list[Rule]:
    rules = []
    i = 0
    while i < len(lines):
        if LOOP_START_RE.match(lines[i]):
            start = i
            depth = 1
            j = i + 1
            while j < len(lines) and depth > 0:
                if LOOP_START_RE.match(lines[j]):
                    depth += 1
                elif LOOP_END_RE.match(lines[j]):
                    depth -= 1
                j += 1
            body = lines[start:j]
            text = "\n".join(body)
            if SLEEP_RE.search(text):
                m = COUNTER_CMP_RE.search(text)
                if m:
                    rules.append(Rule(
                        id=f"RETRY-{start + 1}",
                        rule=f"retries with a sleep, up to {m.group(2)} attempt(s) "
                             f"(counter {m.group(1)})",
                        kind="error-handling", where=f"{display}:{start + 1}-{j}",
                        confidence="Medium",
                        why="loop body has both a sleep and an attempt-counter comparison; "
                            "inferred from shape, not a dedicated retry construct",
                    ))
                else:
                    rules.append(Rule(
                        id=f"RETRY-{start + 1}",
                        rule="loop sleeps on each iteration; no bounded attempt count found",
                        kind="error-handling", where=f"{display}:{start + 1}-{j}",
                        confidence="Low",
                        why="sleep found in a loop body but no attempt-counter comparison; "
                            "may be unbounded or the bound isn't a simple numeric compare",
                    ))
            i = j
        else:
            i += 1
    return rules


def read_script(path: Path, display: str) -> list[Rule]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return (find_arg_parsing(lines, display) + find_exit_codes(lines, display)
           + find_traps(lines, display) + find_locking(lines, display)
           + find_retry_loops(lines, display))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ksh-wrapper-reader",
                                description="Recover argument, exit-code, trap, locking and "
                                            "retry-loop rules from a ksh batch wrapper.")
    p.add_argument("--repo", help="repository root, for display only (default: nearest .git "
                                  "ancestor of cwd)")
    p.add_argument("scripts", nargs="+", help="ksh script file(s) to read")
    p.add_argument("--out", help="write the rule ledger as JSON to this path")
    args = p.parse_args(argv)
    try:
        repo = Path(args.repo).resolve() if args.repo else find_repo_root()
        all_rules: list[Rule] = []
        for script in args.scripts:
            path = Path(script)
            if not path.is_file():
                raise UsageError(f"no such file: {script}")
            display = rel(path.resolve(), repo)
            all_rules.extend(read_script(path, display))
        print(f"{len(all_rules)} rule(s) recovered from {len(args.scripts)} script(s)")
        for r in all_rules:
            print(f"  [{r.id}] {r.rule} ({r.where}, confidence: {r.confidence})")
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump({"rules": [asdict(r) for r in all_rules]}, fh, indent=2)
                fh.write("\n")
            print(f"wrote {rel(out_path, repo)}")
        return 0
    except UsageError as exc:
        print(f"ksh-wrapper-reader: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
