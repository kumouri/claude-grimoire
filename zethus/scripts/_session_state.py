"""Shared parsing for the web-app extension's session/state inventory (see
``docs/webapp-modernization.md``'s SESSION STATE -> STATELESS design, decided 2026-09-28).

Every ``HttpSession`` / Struts ``ActionForm`` session-scope / Spring ``@SessionAttributes`` /
session-scoped bean attribute recovery finds is one row here, cited to ``file:line`` for every place
it's written and read, and classified into one of five stateless destinations:

- ``derivable-per-request`` — (1) recompute it, drop the session copy.
- ``identity-claim`` — (2) an identity/authz claim; lives behind the auth shim.
- ``client-held-ui-state`` — (3) frontend state, or a URL/route parameter.
- ``server-side-durable`` — (4) a keyed store or database owned by a service.
- ``workflow-state`` — (5) an explicit cross-request workflow/resource with its own id.

An attribute with no destination yet is ``unclassified`` — a valid, expected state before a person
(or Copilot, under sign-off) makes the call; it is never silently defaulted to one of the five.

Shape: ``session-state/<unit>.json``, one entry per attribute. Produced by the web-app target
readers (``struts-reader.py``, ``spring-mvc-jsp-reader.py``, ``jsp-servlet-reader.py``); consumed by
``strangler-planner.py`` (a flow's cutover unit is exactly the routes that share a classified-or-not
attribute) and ``overseer-gate.py``'s ``session-state`` subcommand (a flow can't be marked migrated
while any of its attributes is unclassified or still read from ``HttpSession`` by the new code).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

HTTP_SESSION_GET_RE = re.compile(r'\bsession\s*\.\s*getAttribute\s*\(\s*"(?P<name>[^"]+)"')
HTTP_SESSION_SET_RE = re.compile(r'\bsession\s*\.\s*setAttribute\s*\(\s*"(?P<name>[^"]+)"')

DESTINATIONS = (
    "derivable-per-request",
    "identity-claim",
    "client-held-ui-state",
    "server-side-durable",
    "workflow-state",
)
UNCLASSIFIED = "unclassified"


class SessionStateError(Exception):
    """A session-state ledger file is malformed. Printed without a traceback."""


@dataclass
class SessionAttribute:
    name: str
    type: str
    writtenBy: list[str] = field(default_factory=list)   # file:line citations
    readBy: list[str] = field(default_factory=list)       # file:line citations
    lifetime: str = ""                                     # free text: request | login-session | flow | ...
    flows: list[str] = field(default_factory=list)         # route/screen-flow ids that depend on it
    destination: str = UNCLASSIFIED
    rationale: str = ""

    def __post_init__(self) -> None:
        if self.destination != UNCLASSIFIED and self.destination not in DESTINATIONS:
            raise SessionStateError(
                f"session attribute {self.name}: destination must be one of "
                f"{', '.join(DESTINATIONS)}, or {UNCLASSIFIED!r}, got {self.destination!r}")


def read_session_ledger(path: Path) -> tuple[str | None, list[SessionAttribute]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SessionStateError(f"can't read session-state ledger {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SessionStateError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or "attributes" not in data:
        raise SessionStateError(f"{path} must be a JSON object with an 'attributes' list")
    attrs: list[SessionAttribute] = []
    seen: set[str] = set()
    for i, row in enumerate(data["attributes"]):
        if not isinstance(row, dict):
            raise SessionStateError(f"{path}: attributes[{i}] must be an object")
        try:
            attr = SessionAttribute(
                name=str(row["name"]), type=str(row["type"]),
                writtenBy=list(row.get("writtenBy", [])), readBy=list(row.get("readBy", [])),
                lifetime=str(row.get("lifetime", "")), flows=list(row.get("flows", [])),
                destination=str(row.get("destination", UNCLASSIFIED)),
                rationale=str(row.get("rationale", "")),
            )
        except KeyError as exc:
            raise SessionStateError(f"{path}: attributes[{i}] missing required field {exc}") from exc
        if attr.name in seen:
            raise SessionStateError(f"{path}: duplicate session attribute name {attr.name!r}")
        seen.add(attr.name)
        attrs.append(attr)
    return data.get("unit"), attrs


def write_session_ledger(path: Path, unit: str, attrs: list[SessionAttribute]) -> None:
    body = {"unit": unit, "attributes": [
        {"name": a.name, "type": a.type, "writtenBy": a.writtenBy, "readBy": a.readBy,
         "lifetime": a.lifetime, "flows": a.flows, "destination": a.destination,
         "rationale": a.rationale} for a in attrs
    ]}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(body, fh, indent=2)
        fh.write("\n")


def unclassified(attrs: list[SessionAttribute]) -> list[SessionAttribute]:
    return [a for a in attrs if a.destination == UNCLASSIFIED]


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def scan_http_session_usage(text: str, display: str) -> list[SessionAttribute]:
    """Raw ``session.getAttribute("x")`` / ``session.setAttribute("x", ...)`` calls, found by
    name so a legacy JSP scriptlet, servlet, Struts Action or Spring controller is read the same
    way — this is the one construct that isn't specific to any one framework. Merges a read and a
    write of the same name in one file into a single row with both citations."""
    found: dict[str, SessionAttribute] = {}
    for m in HTTP_SESSION_GET_RE.finditer(text):
        name = m.group("name")
        where = f"{display}:{line_of(text, m.start())}"
        found.setdefault(name, SessionAttribute(name=name, type="", lifetime="request-scan"))
        found[name].readBy.append(where)
    for m in HTTP_SESSION_SET_RE.finditer(text):
        name = m.group("name")
        where = f"{display}:{line_of(text, m.start())}"
        found.setdefault(name, SessionAttribute(name=name, type="", lifetime="request-scan"))
        found[name].writtenBy.append(where)
    return list(found.values())


def still_reads_http_session(text: str, names: set[str]) -> list[str]:
    """Session-attribute names, from ``names``, that ``text`` (meant to be *new*, modernized
    source) still reads via ``session.getAttribute`` — the overseer's session-state gate uses this
    to refuse a flow marked migrated while its new code still touches ``HttpSession``."""
    return sorted({m.group("name") for m in HTTP_SESSION_GET_RE.finditer(text)} & names)


def flows_sharing_state(attrs: list[SessionAttribute]) -> dict[str, set[str]]:
    """``flow id -> attribute names it depends on``, for the strangler planner's grouping rule:
    two routes/flows that depend on any of the same attribute names share session state."""
    out: dict[str, set[str]] = {}
    for attr in attrs:
        for flow in attr.flows:
            out.setdefault(flow, set()).add(attr.name)
    return out
