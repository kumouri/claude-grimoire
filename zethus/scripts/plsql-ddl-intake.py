#!/usr/bin/env python3
"""Intake for Oracle 12c-era PL/SQL DDL: the mechanical half of `recover-business-rules` for the
`dialect-oracle-plsql` reader (see `docs/batch-modernization.md`).

**Decided (2026-09-28), v1 source acquisition:** a source-controlled DDL repo is preferred when one
exists (``--repo-source``); DDL extracted from a live database is also allowed (``--extract-source``,
paired with ``--extract-date`` — the day it was pulled, not "as of the repo's history"). When both
are given, the extracted copy doubles as a **drift cross-check**: the same object with a different
body in each source is DRIFT, reported loudly, never silently preferred one way. A referenced
object whose body isn't visible — a package spec with no body anywhere, or a body Oracle's `wrap`
utility has obfuscated — is a flagged gap, **never treated as a no-op**: this script can't recover
rules for it, which is not the same as there being no rules to recover.

**Decided (2026-09-28), batch discovery:** some batch jobs are defined only in the DDL repo (a
`DBMS_SCHEDULER` job with no application-side caller), so this script also scans for
`DBMS_SCHEDULER.CREATE_JOB` and legacy `DBMS_JOB.SUBMIT` calls and reports them as scheduling facts,
not just the packages/procedures/triggers a narrower reader would stop at.

**What this script does not do:** author rule ledger rows. Turning "this procedure does X" into a
numbered, `file:line`-cited rule with a *why* is `recover-business-rules`'s job, done by whoever (or
whatever) is running that skill; this script only produces the structured facts — objects found,
their provenance, whether each is readable, and where they disagree — for that step to work from.

**Convention:** one PL/SQL object per file (packages as `.pks`/`.pkb` or matching `.sql`, the common
shape of a source-controlled DDL repo), with multiple `CREATE OR REPLACE` statements in one file
allowed too, separated the way SQL*Plus expects: a line holding only `/`.

**Never echoes repo history wholesale.** Provenance for a repo-sourced object is one `git log -1`
per file — the commit that last touched it — never a full log or the file's history, because a DDL
repo may carry old secrets in it that don't belong copied into a rule ledger or a chat transcript.

Exit codes: 0 clean (every object's body visible, no drift) · 1 findings (an invisible body and/or
drift — listed, not silenced) · 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import UsageError, check_date, find_repo_root, git, rel  # noqa: E402

STATEMENT_SPLIT_RE = re.compile(r"(?m)^\s*/\s*$")
PACKAGE_RE = re.compile(
    # Oracle's wrap utility replaces the body with "PACKAGE BODY name wrapped" and no IS/AS, so
    # WRAPPED is an alternative terminator for the header, not something that follows IS/AS.
    r"CREATE\s+(?:OR\s+REPLACE\s+)?PACKAGE\s+(?P<body>BODY\s+)?(?P<name>\"?\w+\"?)\s*"
    r"(?:(?P<wrapped>WRAPPED)\b|\bIS\b|\bAS\b)", re.I,
)
UNIT_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?P<kind>PROCEDURE|FUNCTION|TRIGGER)\s+(?P<name>\"?\w+\"?)", re.I,
)
KEYWORD_RE = re.compile(r"\b(BEGIN|END|PROCEDURE|FUNCTION|DECLARE|IF|LOOP|CURSOR)\b", re.I)
CREATE_JOB_RE = re.compile(r"DBMS_SCHEDULER\.CREATE_JOB\s*\((?P<args>.*?)\)\s*;", re.I | re.S)
LEGACY_JOB_RE = re.compile(r"DBMS_JOB\.SUBMIT\s*\((?P<args>.*?)\)\s*;", re.I | re.S)
NAMED_ARG_RE = re.compile(r"(\w+)\s*=>\s*'((?:[^']|'')*)'", re.S)


@dataclass
class DdlObject:
    name: str
    kind: str                 # package_spec | package_body | procedure | function | trigger
    source: str                # "repo" | "live-extract"
    path: str                  # relative to the source root
    provenance: str
    body_visible: bool
    body_invisible_reason: str | None
    body_text: str


@dataclass
class ScheduledJob:
    name: str
    job_type: str              # "dbms_scheduler" | "dbms_job"
    source: str
    path: str
    provenance: str
    attributes: dict[str, str]


def _normalize(body: str) -> str:
    return re.sub(r"\s+", " ", body).strip()


def _looks_wrapped(statement: str, header_end: int) -> bool:
    header = statement[:header_end]
    if re.search(r"\bWRAPPED\b", header, re.I):
        return True
    body = statement[header_end:]
    return bool(body.strip()) and not KEYWORD_RE.search(body)


def parse_objects(text: str, source: str, path: str, provenance: str) -> list[DdlObject]:
    objects = []
    for statement in STATEMENT_SPLIT_RE.split(text):
        statement = statement.strip()
        if not statement:
            continue
        m = PACKAGE_RE.search(statement)
        if m:
            kind = "package_body" if m.group("body") else "package_spec"
            wrapped = bool(m.group("wrapped")) or _looks_wrapped(statement, m.end())
            reason = "body is wrapped/obfuscated (Oracle wrap utility)" if wrapped else None
            objects.append(DdlObject(name=m.group("name").strip('"'), kind=kind, source=source,
                                     path=path, provenance=provenance,
                                     body_visible=not wrapped, body_invisible_reason=reason,
                                     body_text=_normalize(statement)))
            continue
        m = UNIT_RE.search(statement)
        if m:
            wrapped = _looks_wrapped(statement, m.end())
            reason = "body is wrapped/obfuscated (Oracle wrap utility)" if wrapped else None
            objects.append(DdlObject(name=m.group("name").strip('"'), kind=m.group("kind").lower(),
                                     source=source, path=path, provenance=provenance,
                                     body_visible=not wrapped, body_invisible_reason=reason,
                                     body_text=_normalize(statement)))
    return objects


def parse_jobs(text: str, source: str, path: str, provenance: str) -> list[ScheduledJob]:
    jobs = []
    for m in CREATE_JOB_RE.finditer(text):
        args = dict(NAMED_ARG_RE.findall(m.group("args")))
        name = args.pop("job_name", "?")
        jobs.append(ScheduledJob(name=name, job_type="dbms_scheduler", source=source, path=path,
                                 provenance=provenance, attributes=args))
    for m in LEGACY_JOB_RE.finditer(text):
        args = dict(NAMED_ARG_RE.findall(m.group("args")))
        jobs.append(ScheduledJob(name=args.get("job_name", "?"), job_type="dbms_job", source=source,
                                 path=path, provenance=provenance, attributes=args))
    return jobs


def git_provenance(repo_root: Path, file_path: Path) -> str:
    """One ``git log -1`` for this file only — never the file's full history."""
    proc = git(repo_root, "log", "-1", "--format=%h %ad", "--date=short", "--", str(file_path))
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        return f"repo commit {proc.stdout.strip()}"
    return "repo (no git history for this file)"


def scan_source(root: Path, source: str, extract_date: str | None) -> tuple[list[DdlObject], list[ScheduledJob]]:
    gitcheck = git(root, "rev-parse", "--git-dir")
    is_git = gitcheck is not None and gitcheck.returncode == 0
    objects: list[DdlObject] = []
    jobs: list[ScheduledJob] = []
    for path in sorted(root.rglob("*.sql")) + sorted(root.rglob("*.pks")) + sorted(root.rglob("*.pkb")):
        text = path.read_text(encoding="utf-8", errors="replace")
        relpath = path.relative_to(root).as_posix()
        if source == "repo":
            provenance = git_provenance(root, path.relative_to(root)) if is_git else "repo (not a git checkout)"
        else:
            provenance = f"extracted-on {extract_date}"
        objects.extend(parse_objects(text, source, relpath, provenance))
        jobs.extend(parse_jobs(text, source, relpath, provenance))
    return objects, jobs


def cross_check_drift(repo_objs: list[DdlObject], extract_objs: list[DdlObject]) -> list[str]:
    by_key_repo = {(o.name.lower(), o.kind): o for o in repo_objs}
    by_key_extract = {(o.name.lower(), o.kind): o for o in extract_objs}
    findings = []
    for key, r in by_key_repo.items():
        e = by_key_extract.get(key)
        if e is not None and r.body_visible and e.body_visible and r.body_text != e.body_text:
            findings.append(f"DRIFT {r.kind} {r.name}: repo ({r.path}, {r.provenance}) differs "
                           f"from the live extract ({e.path}, {e.provenance})")
    return findings


def report(objects: list[DdlObject], jobs: list[ScheduledJob], drift: list[str]) -> tuple[list[str], int]:
    lines = [f"{len(objects)} PL/SQL object(s) found, {len(jobs)} scheduled job(s) found"]
    invisible = [o for o in objects if not o.body_visible]
    for o in invisible:
        lines.append(f"INVISIBLE BODY  {o.kind} {o.name} ({o.source}:{o.path}) — "
                     f"{o.body_invisible_reason}")
    lines.extend(drift)
    lines.append(f"{len(invisible)} invisible-body object(s), {len(drift)} drift finding(s)")
    return lines, (1 if invisible or drift else 0)


def write_out(path: Path, objects: list[DdlObject], jobs: list[ScheduledJob], drift: list[str]) -> None:
    body = {"objects": [asdict(o) for o in objects], "scheduledJobs": [asdict(j) for j in jobs],
            "drift": drift}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(body, fh, indent=2)
        fh.write("\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="plsql-ddl-intake",
                                description="Intake PL/SQL DDL: objects, provenance, visibility, "
                                            "drift, and DBMS_SCHEDULER/DBMS_JOB batch discovery.")
    p.add_argument("--repo", help="repository root, for provenance only (default: nearest .git "
                                  "ancestor of cwd)")
    p.add_argument("--repo-source", help="source-controlled DDL repo directory")
    p.add_argument("--extract-source", help="directory of DDL extracted from a live database")
    p.add_argument("--extract-date", help="the day --extract-source was pulled (required with it)")
    p.add_argument("--out", help="write the structured intake as JSON to this path")
    args = p.parse_args(argv)
    try:
        if not args.repo_source and not args.extract_source:
            raise UsageError("give at least one of --repo-source or --extract-source")
        if args.extract_source and not args.extract_date:
            raise UsageError("--extract-source needs --extract-date (the day it was pulled)")
        if args.extract_date:
            check_date(args.extract_date)
        repo = Path(args.repo).resolve() if args.repo else find_repo_root()

        objects: list[DdlObject] = []
        jobs: list[ScheduledJob] = []
        repo_objs: list[DdlObject] = []
        extract_objs: list[DdlObject] = []
        if args.repo_source:
            root = Path(args.repo_source).resolve()
            if not root.is_dir():
                raise UsageError(f"--repo-source is not a directory: {args.repo_source}")
            repo_objs, repo_jobs = scan_source(root, "repo", None)
            objects += repo_objs
            jobs += repo_jobs
        if args.extract_source:
            root = Path(args.extract_source).resolve()
            if not root.is_dir():
                raise UsageError(f"--extract-source is not a directory: {args.extract_source}")
            extract_objs, extract_jobs = scan_source(root, "live-extract", args.extract_date)
            objects += extract_objs
            jobs += extract_jobs
        drift = cross_check_drift(repo_objs, extract_objs) if (repo_objs and extract_objs) else []
        lines, code = report(objects, jobs, drift)
        print("\n".join(lines))
        if args.out:
            write_out(Path(args.out), objects, jobs, drift)
            print(f"wrote {rel(Path(args.out), repo)}")
        return code
    except UsageError as exc:
        print(f"plsql-ddl-intake: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
