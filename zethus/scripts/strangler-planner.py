#!/usr/bin/env python3
"""Group routes into strangler-fig cutover units and emit a cutover-plan artifact, for
`docs/webapp-modernization.md`'s strangler-fig migration path.

**Decided (2026-09-28, Telegram picker, open question 2):** per-screen-flow where routes share
session state, per-route otherwise. This script applies that rule mechanically: two routes land in
the same cutover unit iff they share at least one session-attribute name (from the route manifests
`struts-reader.py` / `spring-mvc-jsp-reader.py` / `jsp-servlet-reader.py` emit, `_routes.py`) or an
explicit shared `flow` id; every other route is its own independent unit.

**Already-migrated detection** (the FIRST REAL TARGET SHAPE this build's readers understand: a
hybrid app already part-way onto REST microservices plus a new frontend): a route flagged
``alreadyMigrated`` in its manifest is excluded from cutover planning and reported separately —
this script plans only the remainder, never re-planning work that's already done.

**State extraction before cutover:** a unit with any session attribute gets an explicit
"extract session state" step ordered before "cut over router" in its plan, regardless of whether
that attribute has been classified into one of the five stateless destinations yet
(``_session_state.py``) — the ordering is structural, not conditional on classification being
finished; classification status is still recorded per unit so a person can see what's left.

Exit codes: 0 plan emitted (an empty plan, e.g. every route already migrated, is a valid result) ·
2 usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import UsageError, find_repo_root, rel  # noqa: E402
from _routes import Route, RouteError, read_routes  # noqa: E402
from _session_state import SessionStateError, read_session_ledger  # noqa: E402


@dataclass
class Unit:
    id: str
    kind: str                              # "flow" | "route"
    routeIds: list[str]
    sessionAttributes: list[str]
    sessionAttributeStatus: dict[str, str]  # name -> destination (or "unclassified"/"unknown")
    steps: list[str] = field(default_factory=list)


def load_routes(paths: list[Path]) -> list[Route]:
    seen: dict[str, Route] = {}
    for path in paths:
        try:
            for r in read_routes(path):
                if r.id in seen:
                    continue      # first occurrence wins; a route manifest is one reader's own view
                seen[r.id] = r
        except RouteError as exc:
            raise UsageError(str(exc)) from exc
    return list(seen.values())


def load_session_status(paths: list[Path]) -> dict[str, str]:
    status: dict[str, str] = {}
    for path in paths:
        try:
            _, attrs = read_session_ledger(path)
        except SessionStateError as exc:
            raise UsageError(str(exc)) from exc
        for a in attrs:
            status.setdefault(a.name, a.destination)
    return status


def group_routes(routes: list[Route]) -> list[list[Route]]:
    """Union-find over shared session-attribute names and explicit shared flow ids."""
    parent = {r.id: r.id for r in routes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    by_key: dict[str, list[str]] = {}
    for r in routes:
        for a in r.sessionAttributes:
            by_key.setdefault(f"attr:{a}", []).append(r.id)
        if r.flow:
            by_key.setdefault(f"flow:{r.flow}", []).append(r.id)
    for members in by_key.values():
        for other in members[1:]:
            union(members[0], other)

    grouped: dict[str, list[Route]] = {}
    for r in routes:
        grouped.setdefault(find(r.id), []).append(r)
    return list(grouped.values())


def build_units(groups: list[list[Route]], status: dict[str, str]) -> list[Unit]:
    units = []
    for group in groups:
        group = sorted(group, key=lambda r: r.id)
        attrs = sorted({a for r in group for a in r.sessionAttributes})
        kind = "flow" if len(group) > 1 else "route"
        uid = ("flow:" + "+".join(r.id for r in group)) if kind == "flow" else group[0].id
        steps = []
        if attrs:
            steps.append(f"extract session state ({', '.join(attrs)}) to its classified "
                         "destination before cutover")
        steps += [f"build modernized route(s): {', '.join(r.id for r in group)}",
                 "replay golden masters against the new path",
                 "cut over router (feature-flagged, reversible by flipping the route back)"]
        units.append(Unit(id=uid, kind=kind, routeIds=[r.id for r in group],
                          sessionAttributes=attrs,
                          sessionAttributeStatus={a: status.get(a, "unknown") for a in attrs},
                          steps=steps))
    return sorted(units, key=lambda u: u.id)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="strangler-planner",
                                description="Group routes into strangler-fig cutover units "
                                            "(per-screen-flow where session state is shared, "
                                            "per-route otherwise) and exclude already-migrated "
                                            "routes.")
    p.add_argument("--repo", help="repository root, for display only (default: nearest .git "
                                  "ancestor of cwd)")
    p.add_argument("--routes", nargs="+", required=True, help="route manifest JSON file(s), "
                                                              "merged")
    p.add_argument("--session-ledger", nargs="*", default=[], help="session-state ledger JSON "
                                                                    "file(s), for classification "
                                                                    "status annotation only")
    p.add_argument("--out", help="write the cutover plan as JSON to this path")
    args = p.parse_args(argv)
    try:
        repo = Path(args.repo).resolve() if args.repo else find_repo_root()
        route_paths = [Path(r) for r in args.routes]
        for rp in route_paths:
            if not rp.is_file():
                raise UsageError(f"no such route manifest: {rp}")
        ledger_paths = [Path(s) for s in args.session_ledger]
        for lp in ledger_paths:
            if not lp.is_file():
                raise UsageError(f"no such session ledger: {lp}")

        all_routes = load_routes(route_paths)
        status = load_session_status(ledger_paths)
        already_migrated = [r for r in all_routes if r.alreadyMigrated]
        remaining = [r for r in all_routes if not r.alreadyMigrated]
        groups = group_routes(remaining)
        units = build_units(groups, status)

        print(f"{len(all_routes)} route(s) total: {len(already_migrated)} already migrated "
              f"(excluded), {len(remaining)} planned into {len(units)} cutover unit(s)")
        for u in units:
            print(f"  [{u.kind}] {u.id}  routes: {', '.join(u.routeIds)}"
                 + (f"  session: {', '.join(u.sessionAttributes)}" if u.sessionAttributes else ""))
        if already_migrated:
            print("already migrated, excluded from planning:")
            for r in already_migrated:
                print(f"  {r.id} ({r.where or '?'})")

        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            body = {
                "units": [asdict(u) for u in units],
                "alreadyMigrated": [asdict(r) for r in already_migrated],
            }
            with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(body, fh, indent=2)
                fh.write("\n")
            print(f"wrote {rel(out_path, repo)}")
        return 0
    except UsageError as exc:
        print(f"strangler-planner: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
