#!/usr/bin/env python3
"""Read a Control-M job-definition export and map its dependency graph onto a modernization
target, for the `batch-type-cron-scheduler-wrappers` reader (see `docs/batch-modernization.md`).

**Decided (2026-09-28), orchestration readers:** the cron/scheduler reader generalizes to any
scheduler product, not only crontab — Control-M is the first one built. Its job doesn't change with
the target: recover the dependency and calendar rules from the job-definition export, then map
inter-job ordering onto whatever the modernization targets — a Spring Batch job flow (this spec's
default target architecture) or a cloud workflow orchestrator such as AWS Step Functions, if a
consuming engagement chooses one instead.

**Input format:** the common BMC Control-M/EM bulk-export shape — ``<DEFTABLE>`` containing
``<FOLDER>`` elements, each holding ``<JOB>`` elements with ``JOBNAME``/``CMDLINE`` attributes and
optional scheduling attributes (``DAYS``, ``WDAYS``, ``MONTHS``, ``TIME``), plus ``<INCOND>``/
``<OUTCOND>`` children recording in/out conditions. A job with no explicit ``<OUTCOND>`` is taken to
produce the conventional ``<JOBNAME>-OK`` condition on success — the common Control-M default; a job
whose export uses a different convention needs an explicit ``<OUTCOND>``.

**What this script does not do:** decide the target architecture, or write the target's actual
config/state-machine file. It produces a structural skeleton the implementing phase edits — a
mapping suggestion, not a deploy artifact — plus the scheduling facts (frequency, calendar, ordering)
in the same rule-ledger shape every other modernization reader uses.

Exit codes: 0 parsed and mapped, no cycle · 1 a dependency cycle was found — the graph can't be
topologically mapped, listed rather than guessed at · 2 usage error (bad path, unparsable XML).
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import UsageError, find_repo_root, rel  # noqa: E402

TARGETS = ("spring-batch-flow", "step-functions")
CALENDAR_ATTRS = ("DAYS", "WDAYS", "MONTHS", "TIME", "CONFCAL")


@dataclass
class ControlMJob:
    name: str
    folder: str
    cmdline: str
    calendar: dict[str, str]
    depends_on: list[str] = field(default_factory=list)


def parse_export(path: Path) -> list[ControlMJob]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise UsageError(f"{path.name} is not valid XML: {exc}") from exc
    jobs: dict[str, ControlMJob] = {}
    out_producers: dict[str, str] = {}          # condition name -> job that produces it
    in_conditions: dict[str, list[str]] = {}     # job name -> condition names it requires

    folders = root.iter("FOLDER") if root.tag != "FOLDER" else [root]
    for folder in folders:
        folder_name = folder.get("FOLDER_NAME", folder.get("NAME", ""))
        for job_el in folder.iter("JOB"):
            name = job_el.get("JOBNAME")
            if not name:
                raise UsageError(f"a <JOB> in {path.name} has no JOBNAME")
            calendar = {a: job_el.get(a) for a in CALENDAR_ATTRS if job_el.get(a) is not None}
            job = ControlMJob(name=name, folder=folder_name, cmdline=job_el.get("CMDLINE", ""),
                              calendar=calendar)
            jobs[name] = job
            outs = [o.get("NAME") for o in job_el.findall("OUTCOND") if o.get("NAME")]
            for out in outs:
                out_producers[out] = name
            if not outs:
                out_producers.setdefault(f"{name}-OK", name)
            in_conditions[name] = [i.get("NAME") for i in job_el.findall("INCOND") if i.get("NAME")]

    for name, conditions in in_conditions.items():
        for cond in conditions:
            producer = out_producers.get(cond)
            if producer and producer != name:
                jobs[name].depends_on.append(producer)
    return list(jobs.values())


def topological_order(jobs: list[ControlMJob]) -> tuple[list[str], list[str]]:
    """``(order, cycle_members)``. ``cycle_members`` is non-empty iff a cycle exists."""
    remaining = {j.name: set(j.depends_on) & {x.name for x in jobs} for j in jobs}
    order: list[str] = []
    while remaining:
        ready = sorted(name for name, deps in remaining.items() if not deps)
        if not ready:
            return order, sorted(remaining)
        for name in ready:
            del remaining[name]
        order.extend(ready)
        for deps in remaining.values():
            deps.difference_update(ready)
    return order, []


def scheduling_rules(jobs: list[ControlMJob]) -> list[dict]:
    rules = []
    for i, job in enumerate(jobs, 1):
        parts = [f"depends on {', '.join(job.depends_on)}"] if job.depends_on else ["no dependency"]
        if job.calendar:
            parts.append(", ".join(f"{k}={v}" for k, v in job.calendar.items()))
        rules.append({
            "id": f"SCHED-{i}", "rule": f"{job.name}: " + "; ".join(parts), "kind": "scheduling",
            "where": f"Control-M/{job.folder}/{job.name}",
            "confidence": "High" if (job.depends_on or job.calendar) else "Medium",
            "why": "explicit INCOND/OUTCOND and calendar attributes in the export",
        })
    return rules


def to_spring_batch_flow(jobs: list[ControlMJob], order: list[str]) -> dict:
    by_name = {j.name: j for j in jobs}
    steps = []
    for name in order:
        job = by_name[name]
        next_steps = sorted({j.name for j in jobs if name in j.depends_on})
        steps.append({"step": name, "cmdline": job.cmdline, "next": next_steps})
    folder = jobs[0].folder if jobs else ""
    return {"target": "spring-batch-flow", "job": folder, "steps": steps}


def to_step_functions(jobs: list[ControlMJob], order: list[str]) -> dict:
    by_name = {j.name: j for j in jobs}
    states = {}
    for i, name in enumerate(order):
        job = by_name[name]
        next_steps = sorted({j.name for j in jobs if name in j.depends_on})
        state = {"Type": "Task", "Comment": job.cmdline}
        if next_steps:
            state["Next"] = next_steps[0] if len(next_steps) == 1 else next_steps
        else:
            state["End"] = True
        states[name] = state
    return {"target": "step-functions", "StartAt": order[0] if order else None, "States": states}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="control-m-reader",
                                description="Read a Control-M export; map job ordering onto a "
                                            "modernization target.")
    p.add_argument("--repo", help="repository root, for display only (default: nearest .git "
                                  "ancestor of cwd)")
    p.add_argument("--export", required=True, help="Control-M job-definition export (XML)")
    p.add_argument("--target", choices=TARGETS, default="spring-batch-flow",
                   help="mapping target (default: spring-batch-flow)")
    p.add_argument("--out", help="write the structured mapping as JSON to this path")
    args = p.parse_args(argv)
    try:
        repo = Path(args.repo).resolve() if args.repo else find_repo_root()
        path = Path(args.export)
        if not path.is_file():
            raise UsageError(f"--export not found: {args.export}")
        jobs = parse_export(path)
        order, cycle = topological_order(jobs)
        rules = scheduling_rules(jobs)
        print(f"{len(jobs)} job(s) found in {rel(path, repo)}")
        for rule in rules:
            print(f"  {rule['id']}  {rule['rule']}")
        if cycle:
            print(f"CYCLE — {len(cycle)} job(s) can't be ordered: {', '.join(cycle)}")
            return 1
        mapping = (to_spring_batch_flow(jobs, order) if args.target == "spring-batch-flow"
                  else to_step_functions(jobs, order))
        print(f"mapped onto {args.target}: {' -> '.join(order) if order else '(no jobs)'}")
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            body = {"scheduling": rules, "mapping": mapping}
            with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(body, fh, indent=2)
                fh.write("\n")
            print(f"wrote {rel(out_path, repo)}")
        return 0
    except UsageError as exc:
        print(f"control-m-reader: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
