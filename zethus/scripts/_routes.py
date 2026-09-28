"""Shared route-manifest shape the web-app target readers (``struts-reader.py``,
``spring-mvc-jsp-reader.py``, ``jsp-servlet-reader.py``) emit and ``strangler-planner.py`` consumes.

One entry per route or route-like unit (a Struts action, a Spring ``@RequestMapping`` method, a
servlet mapping):

- ``id`` — a short id, usually the mapped path.
- ``path`` — the URL pattern.
- ``method`` — HTTP method(s), or ``""`` if unknown/any.
- ``where`` — a ``file:line`` citation.
- ``sessionAttributes`` — names cited from the session-state ledger (``_session_state.py``) this
  route depends on; this is what the strangler planner groups cutover units by (decided
  2026-09-28, ``docs/webapp-modernization.md``: per-screen-flow where routes share session state,
  per-route otherwise).
- ``alreadyMigrated`` — ``true`` when the reader found evidence this route is already served by a
  REST service or a new frontend rather than the legacy code path — the hybrid target shape this
  build's readers are built for (Struts/Spring MVC mid-migration to REST + Angular/React).
- ``flow`` — an optional screen-flow id, when the reader can name one directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


class RouteError(Exception):
    """A route manifest file is malformed. Printed without a traceback."""


@dataclass
class Route:
    id: str
    path: str
    method: str = ""
    where: str = ""
    sessionAttributes: list[str] = field(default_factory=list)
    alreadyMigrated: bool = False
    flow: str = ""


def read_routes(path: Path) -> list[Route]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RouteError(f"can't read route manifest {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RouteError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or "routes" not in data:
        raise RouteError(f"{path} must be a JSON object with a 'routes' list")
    routes: list[Route] = []
    for i, row in enumerate(data["routes"]):
        if not isinstance(row, dict):
            raise RouteError(f"{path}: routes[{i}] must be an object")
        try:
            routes.append(Route(
                id=str(row["id"]), path=str(row["path"]), method=str(row.get("method", "")),
                where=str(row.get("where", "")),
                sessionAttributes=list(row.get("sessionAttributes", [])),
                alreadyMigrated=bool(row.get("alreadyMigrated", False)),
                flow=str(row.get("flow", "")),
            ))
        except KeyError as exc:
            raise RouteError(f"{path}: routes[{i}] missing required field {exc}") from exc
    return routes


def write_routes(path: Path, routes: list[Route]) -> None:
    body = {"routes": [
        {"id": r.id, "path": r.path, "method": r.method, "where": r.where,
         "sessionAttributes": r.sessionAttributes, "alreadyMigrated": r.alreadyMigrated,
         "flow": r.flow} for r in routes
    ]}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(body, fh, indent=2)
        fh.write("\n")
