#!/usr/bin/env python3
"""Read old Spring MVC + JSP route/view/session/authz constructs, including hybrid delegation to
Struts and already-migrated-to-REST detection, for the `webapp-target-spring-mvc-jsp` reader (see
`docs/webapp-modernization.md`). Built for the same FIRST REAL TARGET SHAPE as `struts-reader.py`: a
hybrid app where a Spring MVC controller wraps or invokes a Struts Action/ActionForm and renders
JSP views, already part-way migrated to REST microservices plus a new frontend (Angular is a
supported HLA-named choice, not a default -- see `webapp-hla-input-check.py`).

Recovers, each as a rule-ledger-shaped row cited to `file:line`:

- **`@RequestMapping`/`@GetMapping`/`@PostMapping`/`@PutMapping`/`@DeleteMapping`** — route + HTTP
  method, `kind: orchestration`. Class-level and method-level mappings are read the same way (a
  flat scan, not a full parser — deliberately, matching every other reader in this kit); a route is
  reported where its annotation sits, not stitched to a base class path.
- **`return "viewName";`** inside a controller file — the JSP view a route resolves to,
  `kind: orchestration`, `confidence: Medium` (a flat scan can't prove which method a given
  `return` belongs to).
- **`@SessionAttributes({...})`** — one `_session_state.py` row per named attribute,
  `destination: unclassified` until a person (or Copilot, under sign-off) makes the
  stateless-destination call.
- **`@PreAuthorize`/`@Secured`/`@RolesAllowed`** — the authz rule Spring Security enforces before
  the method runs, `kind: validation` (no dedicated authz kind; see `recover-business-rules`'s Kind
  list).
- **Hybrid delegation to Struts** — an `import org.apache.struts...` in the file is High-confidence
  evidence on its own; a reference to a class name passed via `--struts-classes` is Medium
  confidence, same discipline as `struts-reader.py`'s own hybrid check in the other direction.
- **Already migrated to REST** — a `@RestController` class, or `ResponseEntity`/`@ResponseBody`
  found within the same short window as a route's mapping annotation, marks that route
  `alreadyMigrated: true` in the route manifest (`_routes.py`) for `strangler-planner.py` to exclude
  from further cutover planning — it's already on the new side.

Exit codes: 0 read the source, findings printed (empty is a valid finding) · 2 usage error.
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
from _routes import Route, write_routes  # noqa: E402
from _session_state import SessionAttribute, write_session_ledger  # noqa: E402

MAPPING_RE = re.compile(
    r'@(?P<verb>RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)\s*'
    r'\((?P<args>[^)]*)\)', re.S)
VALUE_RE = re.compile(r'(?:value|path)?\s*=?\s*"(?P<path>/[^"]*)"')
METHOD_ARG_RE = re.compile(r'RequestMethod\.(?P<method>\w+)')
VIEW_RETURN_RE = re.compile(r'\breturn\s+"(?P<view>[A-Za-z0-9_./-]+)"\s*;')
SESSION_ATTRS_RE = re.compile(r'@SessionAttributes\s*\(\s*(?P<args>[^)]*)\)', re.S)
QUOTED_RE = re.compile(r'"([^"]+)"')
AUTHZ_RE = re.compile(
    # one level of nested parens allowed, so @PreAuthorize("hasRole('USER')") captures the whole
    # expression rather than stopping at hasRole's own closing paren.
    r'@(?P<kind>PreAuthorize|PostAuthorize|Secured|RolesAllowed)\s*'
    r'\((?P<args>(?:[^()]|\([^()]*\))*)\)', re.S)
REST_CONTROLLER_RE = re.compile(r'@RestController\b')
CONTROLLER_RE = re.compile(r'@Controller\b')
ALREADY_MIGRATED_NEARBY_RE = re.compile(r'ResponseEntity|@ResponseBody')
STRUTS_IMPORT_RE = re.compile(r'^\s*import\s+org\.apache\.struts', re.M)

NEARBY_WINDOW = 90      # chars after a mapping annotation to look for an already-migrated signal
                         # -- roughly "through this method's own return-type declaration," not into
                         # the next method's; a flat scan, so this is a proximity heuristic, not a
                         # guarantee -- see the module docstring's already-migrated-to-REST note.


@dataclass
class Rule:
    id: str
    rule: str
    kind: str
    where: str
    confidence: str
    why: str


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def read_mappings(text: str, display: str, is_rest: bool) -> tuple[list[Rule], list[Route]]:
    rules: list[Rule] = []
    routes: list[Route] = []
    for m in MAPPING_RE.finditer(text):
        args = m.group("args")
        pm = VALUE_RE.search(args)
        path = pm.group("path") if pm else "?"
        mm = METHOD_ARG_RE.search(args)
        verb = m.group("verb")
        method = mm.group("method") if mm else {
            "GetMapping": "GET", "PostMapping": "POST", "PutMapping": "PUT",
            "DeleteMapping": "DELETE", "PatchMapping": "PATCH",
        }.get(verb, "")
        lineno = line_of(text, m.start())
        where = f"{display}:{lineno}"
        rules.append(Rule(id=f"ROUTE-{lineno}", rule=f"route {path!r} ({method or 'any method'})",
                          kind="orchestration", where=where, confidence="High",
                          why=f"explicit @{verb}"))
        nearby = text[m.end():m.end() + NEARBY_WINDOW]
        already = is_rest or bool(ALREADY_MIGRATED_NEARBY_RE.search(nearby))
        routes.append(Route(id=path, path=path, method=method, where=where,
                            alreadyMigrated=already))
    return rules, routes


def read_views(text: str, display: str) -> list[Rule]:
    rules = []
    for m in VIEW_RETURN_RE.finditer(text):
        lineno = line_of(text, m.start())
        rules.append(Rule(id=f"VIEW-{lineno}", rule=f"resolves to view {m.group('view')!r}",
                          kind="orchestration", where=f"{display}:{lineno}", confidence="Medium",
                          why="a bare string return in a controller file; not stitched to a "
                              "specific method by this flat scan"))
    return rules


def read_session_attributes(text: str, display: str) -> tuple[list[Rule], list[SessionAttribute]]:
    rules = []
    session_attrs = []
    for m in SESSION_ATTRS_RE.finditer(text):
        names = QUOTED_RE.findall(m.group("args"))
        lineno = line_of(text, m.start())
        where = f"{display}:{lineno}"
        rules.append(Rule(id=f"SESSION-{lineno}",
                          rule=f"@SessionAttributes holds: {', '.join(names) or '(none named)'}",
                          kind="orchestration", where=where, confidence="High",
                          why="explicit @SessionAttributes annotation"))
        for name in names:
            session_attrs.append(SessionAttribute(
                name=name, type="model attribute", writtenBy=[where], readBy=[where],
                lifetime="controller-session", flows=[],
            ))
    return rules, session_attrs


def read_authz(text: str, display: str) -> list[Rule]:
    rules = []
    for m in AUTHZ_RE.finditer(text):
        lineno = line_of(text, m.start())
        expr = m.group("args").strip()
        rules.append(Rule(id=f"AUTHZ-{lineno}", rule=f"@{m.group('kind')}({expr})",
                          kind="validation", where=f"{display}:{lineno}", confidence="High",
                          why="explicit Spring Security method-security annotation"))
    return rules


def read_hybrid_delegation(text: str, display: str, struts_classes: list[str]) -> list[Rule]:
    rules = []
    im = STRUTS_IMPORT_RE.search(text)
    if im:
        lineno = line_of(text, im.start())
        rules.append(Rule(id=f"HYBRID-{lineno}",
                          rule="imports org.apache.struts -- hybrid: this Spring controller file "
                               "delegates to (or wraps) Struts",
                          kind="orchestration", where=f"{display}:{lineno}", confidence="High",
                          why="explicit Struts import"))
    for name in struts_classes:
        m = re.search(rf'\b{re.escape(name)}\b', text)
        if m:
            lineno = line_of(text, m.start())
            rules.append(Rule(
                id=f"HYBRID-{lineno}",
                rule=f"references Struts class {name!r} -- hybrid: Spring MVC delegates to (or "
                     "wraps) a Struts Action/ActionForm",
                kind="orchestration", where=f"{display}:{lineno}", confidence="Medium",
                why="a name passed via --struts-classes was found in this file; a structural "
                    "inference, not a guaranteed call path",
            ))
    return rules


def read_file(path: Path, display: str, struts_classes: list[str]
              ) -> tuple[list[Rule], list[SessionAttribute], list[Route]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if not (CONTROLLER_RE.search(text) or REST_CONTROLLER_RE.search(text)):
        return [], [], []
    is_rest = bool(REST_CONTROLLER_RE.search(text))
    rules: list[Rule] = []
    session_attrs: list[SessionAttribute] = []
    r1, routes = read_mappings(text, display, is_rest)
    rules += r1
    rules += read_views(text, display)
    r3, s3 = read_session_attributes(text, display)
    rules += r3; session_attrs += s3
    rules += read_authz(text, display)
    rules += read_hybrid_delegation(text, display, struts_classes)
    return rules, session_attrs, routes


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="spring-mvc-jsp-reader",
                                description="Recover route, view, session, authz, hybrid-Struts-"
                                            "delegation and already-migrated-to-REST rules from "
                                            "Spring MVC controller source.")
    p.add_argument("--repo", help="repository root, for display only (default: nearest .git "
                                  "ancestor of cwd)")
    p.add_argument("sources", nargs="+", help="Spring MVC controller Java file(s)")
    p.add_argument("--struts-classes", nargs="*", default=[],
                   help="Struts Action/ActionForm class name(s) to cross-reference for hybrid "
                        "delegation (Medium confidence when found)")
    p.add_argument("--unit", default=None, help="unit name for the session-state ledger (default: "
                                                "the first source file's name)")
    p.add_argument("--out", help="write the rule ledger as JSON to this path")
    p.add_argument("--session-out", help="write the session-state ledger as JSON to this path")
    p.add_argument("--routes-out", help="write the route manifest as JSON to this path")
    args = p.parse_args(argv)
    try:
        repo = Path(args.repo).resolve() if args.repo else find_repo_root()
        all_rules: list[Rule] = []
        all_session: list[SessionAttribute] = []
        all_routes: list[Route] = []
        for s in args.sources:
            path = Path(s)
            if not path.is_file():
                raise UsageError(f"no such file: {s}")
            display = rel(path.resolve(), repo)
            rules, session_attrs, routes = read_file(path, display, args.struts_classes)
            all_rules += rules
            all_session += session_attrs
            all_routes += routes

        print(f"{len(all_rules)} rule(s), {len(all_session)} session attribute(s), "
              f"{len(all_routes)} route(s) recovered from {len(args.sources)} source file(s)")
        for r in all_rules:
            print(f"  [{r.id}] {r.rule} ({r.where}, confidence: {r.confidence})")
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump({"rules": [asdict(r) for r in all_rules]}, fh, indent=2)
                fh.write("\n")
            print(f"wrote {rel(out_path, repo)}")
        if args.session_out and all_session:
            unit = args.unit or Path(args.sources[0]).name
            write_session_ledger(Path(args.session_out), unit, all_session)
            print(f"wrote {rel(Path(args.session_out), repo)}")
        if args.routes_out:
            write_routes(Path(args.routes_out), all_routes)
            print(f"wrote {rel(Path(args.routes_out), repo)}")
        return 0
    except UsageError as exc:
        print(f"spring-mvc-jsp-reader: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
