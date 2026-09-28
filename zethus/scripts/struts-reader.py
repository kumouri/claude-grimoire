#!/usr/bin/env python3
"""Read Struts 1.x and 2.x route/action/form/validation/session/authz constructs for the
`webapp-target-struts` reader (see `docs/webapp-modernization.md`), aimed at the FIRST REAL TARGET
SHAPE this build is built for: a Struts action wrapped in or invoked from a Spring MVC controller,
rendering JSP views, mid-migration to REST plus a new frontend. Hybrid detection below is not an
edge case here — it is the primary case.

Recovers, each as a rule-ledger-shaped row cited to `file:line`:

- **Struts 1 action mappings** (`<action path=... type=... name=... scope=... validate=...>` in a
  struts-config.xml) — route + controller class + form-bean binding + validation opt-in,
  `kind: orchestration` for the route, `kind: validation` when `validate` is true (Struts 1's own
  default, when the attribute is absent).
- **Struts 1 form-beans** (`<form-bean name=... type=...>`) — the ActionForm backing a route,
  `kind: validation`.
- **Struts 2 actions** (`<action name=... class=... method=...>` in a struts.xml) with their
  `<result>` view targets, `kind: orchestration`; `<interceptor-ref name="validation">` opts a
  Struts 2 action into framework validation, `kind: validation`.
- **`<forward>` / `<result>` view targets** — the JSP (or redirect) each route resolves to,
  `kind: orchestration`.
- **`roles="..."` on an `<action>`** — the authz rule Struts enforces before the action runs,
  `kind: validation` (no dedicated authz kind exists in the shared vocabulary; see
  `recover-business-rules`'s Kind list).
- **Session-scoped form-beans** (`<action ... scope="session">`, Struts 1's own default scope) —
  one `_session_state.py` row per session-scoped form-bean, `destination: unclassified` until a
  person (or Copilot, under sign-off) makes the stateless-destination call — see
  `docs/webapp-modernization.md`'s SESSION STATE -> STATELESS design.
- **Hybrid delegation** (`--java` sources): a Spring `@Controller`/`@RestController`-annotated
  class that references a Struts Action or ActionForm class name collected from the XML is reported
  as a hybrid-delegation finding, `kind: orchestration`, `confidence: Medium` — a structural
  inference from a co-occurring name, not a guarantee that delegation is the only path into the
  action.

Also emits a route manifest (`_routes.py`) for `strangler-planner.py`: one entry per Struts action,
with its session-attribute dependency and (for Struts 1) whether the action is already fronted by a
REST controller elsewhere is left to the Spring MVC reader — this reader only knows the Struts side.

This is line-based pattern matching over the XML/Java text, not a real XML or Java parser —
deliberately, matching every other reader in this kit (`ksh-wrapper-reader.py`,
`plsql-ddl-intake.py`): a `<forward>`/`<result>` is reported on its own line, not linked back to its
enclosing `<action>` by nesting — the constitution author cross-references by the route's own
citation, same discipline `recover-business-rules` already asks for everywhere else.

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

ATTR_RE = re.compile(r'([\w:-]+)\s*=\s*"([^"]*)"')
# lookahead, not \b: "action" is immediately followed by "-" in "<action-mappings>", which is a
# \w/\W boundary and would otherwise false-match the container element.
ACTION_TAG_RE = re.compile(r'<action(?=[\s/>])([^>]*?)/?>', re.I)
FORM_BEAN_TAG_RE = re.compile(r'<form-bean\b([^>]*?)/?>', re.I)
FORWARD_TAG_RE = re.compile(r'<forward\b([^>]*?)/?>', re.I)
RESULT_TAG_RE = re.compile(r'<result\b([^>]*?)>(?P<path>[^<]*)</result>', re.I | re.S)
INTERCEPTOR_REF_RE = re.compile(r'<interceptor-ref\s+name\s*=\s*"validation"', re.I)
CONTROLLER_ANNOTATION_RE = re.compile(r'@(?:Controller|RestController)\b')


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


def parse_attrs(raw: str) -> dict[str, str]:
    return dict(ATTR_RE.findall(raw))


def read_struts1_actions(text: str, display: str
                         ) -> tuple[list[Rule], list[SessionAttribute], list[Route], set[str]]:
    rules: list[Rule] = []
    session_attrs: list[SessionAttribute] = []
    routes: list[Route] = []
    classes: set[str] = set()
    for m in ACTION_TAG_RE.finditer(text):
        attrs = parse_attrs(m.group(1))
        if "path" not in attrs:
            continue          # a Struts 2 <action name=...> without path -- handled separately
        lineno = line_of(text, m.start())
        where = f"{display}:{lineno}"
        path = attrs.get("path", "?")
        atype = attrs.get("type", "")
        name = attrs.get("name", "")
        scope = attrs.get("scope", "session")     # Struts 1's own default is session
        validate = attrs.get("validate", "true")   # Struts 1's own default is true
        roles = attrs.get("roles", "")
        if atype:
            classes.add(atype)
        parts = [f"route {path!r}"]
        if atype:
            parts.append(f"handled by {atype}")
        if name:
            parts.append(f"form {name!r} ({scope} scope)")
        rules.append(Rule(id=f"ACTION-{lineno}", rule="; ".join(parts), kind="orchestration",
                          where=where, confidence="High", why="explicit <action> attributes"))
        if validate.lower() == "true" and name:
            rules.append(Rule(id=f"VALIDATE-{lineno}",
                              rule=f"route {path!r} runs ActionForm {name!r} validation before the "
                                   "action executes",
                              kind="validation", where=where, confidence="High",
                              why="validate attribute defaults to true and was not disabled"))
        if roles:
            rules.append(Rule(id=f"AUTHZ-{lineno}", rule=f"route {path!r} requires role(s): {roles}",
                              kind="validation", where=where, confidence="High",
                              why="explicit roles attribute"))
        session_names = []
        if name and scope.lower() == "session":
            session_attrs.append(SessionAttribute(
                name=name, type=atype or "ActionForm",
                writtenBy=[where], readBy=[where], lifetime="login-session", flows=[path],
            ))
            session_names = [name]
            rules.append(Rule(
                id=f"SESSTATE-{lineno}",
                rule=f"session attribute {name!r} ({atype or 'ActionForm'}) lives in HttpSession "
                     f"for the login session, written/read via route {path!r} — citable under the "
                     "constitution's Session / state section",
                kind="orchestration", where=where, confidence="High",
                why="Struts 1's own default scope is session; not overridden"))
        routes.append(Route(id=path, path=path, method="", where=where,
                            sessionAttributes=session_names))
    return rules, session_attrs, routes, classes


def read_form_beans(text: str, display: str) -> tuple[list[Rule], set[str]]:
    rules = []
    classes: set[str] = set()
    for m in FORM_BEAN_TAG_RE.finditer(text):
        attrs = parse_attrs(m.group(1))
        name, ftype = attrs.get("name", "?"), attrs.get("type", "")
        if ftype:
            classes.add(ftype)
        lineno = line_of(text, m.start())
        rules.append(Rule(id=f"FORM-{lineno}", rule=f"form-bean {name!r} backed by {ftype or '?'}",
                          kind="validation", where=f"{display}:{lineno}", confidence="High",
                          why="explicit <form-bean> declaration"))
    return rules, classes


def read_forwards(text: str, display: str) -> list[Rule]:
    rules = []
    for m in FORWARD_TAG_RE.finditer(text):
        attrs = parse_attrs(m.group(1))
        name, path = attrs.get("name", "?"), attrs.get("path", "?")
        lineno = line_of(text, m.start())
        rules.append(Rule(id=f"FWD-{lineno}", rule=f"forward {name!r} -> {path}",
                          kind="orchestration", where=f"{display}:{lineno}", confidence="High",
                          why="explicit <forward> declaration"))
    return rules


def read_struts2_actions(text: str, display: str) -> tuple[list[Rule], list[Route], set[str]]:
    rules = []
    routes: list[Route] = []
    classes: set[str] = set()
    for m in ACTION_TAG_RE.finditer(text):
        attrs = parse_attrs(m.group(1))
        if "path" in attrs or "name" not in attrs:
            continue           # Struts 1 style, or unrecognized -- handled elsewhere
        lineno = line_of(text, m.start())
        where = f"{display}:{lineno}"
        name = attrs.get("name", "?")
        klass, method = attrs.get("class", ""), attrs.get("method", "execute")
        if klass:
            classes.add(klass)
        rules.append(Rule(id=f"ACTION2-{lineno}",
                          rule=f"route {name!r} -> {klass or '?'}#{method}",
                          kind="orchestration", where=where, confidence="High",
                          why="explicit <action> attributes"))
        routes.append(Route(id=f"/{name}", path=f"/{name}", method="", where=where))
    for m in RESULT_TAG_RE.finditer(text):
        attrs = parse_attrs(m.group(1))
        rname = attrs.get("name", "success")
        lineno = line_of(text, m.start())
        rules.append(Rule(id=f"RESULT-{lineno}", rule=f"result {rname!r} -> {m.group('path').strip()}",
                          kind="orchestration", where=f"{display}:{lineno}", confidence="High",
                          why="explicit <result> declaration"))
    for m in INTERCEPTOR_REF_RE.finditer(text):
        lineno = line_of(text, m.start())
        rules.append(Rule(id=f"VALIDATE2-{lineno}", rule="action opts into the validation interceptor",
                          kind="validation", where=f"{display}:{lineno}", confidence="High",
                          why='explicit <interceptor-ref name="validation">'))
    return rules, routes, classes


def read_config(path: Path, display: str
                ) -> tuple[list[Rule], list[SessionAttribute], list[Route], set[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    rules: list[Rule] = []
    session_attrs: list[SessionAttribute] = []
    routes: list[Route] = []
    classes: set[str] = set()
    r1, s1, rt1, c1 = read_struts1_actions(text, display)
    rules += r1; session_attrs += s1; routes += rt1; classes |= c1
    r2, c2 = read_form_beans(text, display)
    rules += r2; classes |= c2
    rules += read_forwards(text, display)
    r3, rt3, c3 = read_struts2_actions(text, display)
    rules += r3; routes += rt3; classes |= c3
    return rules, session_attrs, routes, classes


def read_hybrid_delegation(java_paths: list[Path], repo: Path, struts_classes: set[str]) -> list[Rule]:
    """Flag a Spring @Controller/@RestController class whose source references a Struts Action or
    ActionForm class name collected from the XML -- the FIRST REAL TARGET SHAPE this reader is
    built for (docs/webapp-modernization.md): a hybrid where Spring MVC wraps or invokes Struts."""
    rules = []
    short_names = {c.rsplit(".", 1)[-1] for c in struts_classes if c}
    for path in java_paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        display = rel(path, repo)
        cm = CONTROLLER_ANNOTATION_RE.search(text)
        if not cm:
            continue
        referenced = sorted(n for n in short_names if re.search(rf'\b{re.escape(n)}\b', text))
        if referenced:
            lineno = line_of(text, cm.start())
            rules.append(Rule(
                id=f"HYBRID-{lineno}",
                rule=f"Spring controller references Struts class(es): {', '.join(referenced)} -- "
                     "hybrid: Spring MVC delegates to (or wraps) a Struts Action/ActionForm",
                kind="orchestration", where=f"{display}:{lineno}", confidence="Medium",
                why="Spring controller annotation co-occurs with a name collected from the Struts "
                    "config in the same file; a structural inference, not a guaranteed call path",
            ))
    return rules


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="struts-reader",
                                description="Recover route, form/validation, session-scope, authz "
                                            "and Spring-hybrid-delegation rules from Struts 1.x/2.x "
                                            "config, plus optional Java sources for hybrid detection.")
    p.add_argument("--repo", help="repository root, for display only (default: nearest .git "
                                  "ancestor of cwd)")
    p.add_argument("configs", nargs="+", help="struts-config.xml / struts.xml file(s)")
    p.add_argument("--java", nargs="*", default=[], help="Java source file(s) to scan for hybrid "
                                                          "Spring-controller-delegates-to-Struts "
                                                          "references")
    p.add_argument("--unit", default=None, help="unit name for the session-state ledger (default: "
                                                "the first config file's name)")
    p.add_argument("--out", help="write the rule ledger as JSON to this path")
    p.add_argument("--session-out", help="write the session-state ledger as JSON to this path")
    p.add_argument("--routes-out", help="write the route manifest as JSON to this path")
    args = p.parse_args(argv)
    try:
        repo = Path(args.repo).resolve() if args.repo else find_repo_root()
        all_rules: list[Rule] = []
        all_session: list[SessionAttribute] = []
        all_routes: list[Route] = []
        all_classes: set[str] = set()
        for c in args.configs:
            path = Path(c)
            if not path.is_file():
                raise UsageError(f"no such file: {c}")
            display = rel(path.resolve(), repo)
            rules, session_attrs, routes, classes = read_config(path, display)
            all_rules += rules
            all_session += session_attrs
            all_routes += routes
            all_classes |= classes
        java_paths = []
        for j in args.java:
            jp = Path(j)
            if not jp.is_file():
                raise UsageError(f"no such file: {j}")
            java_paths.append(jp)
        all_rules += read_hybrid_delegation(java_paths, repo, all_classes)

        print(f"{len(all_rules)} rule(s), {len(all_session)} session attribute(s), "
              f"{len(all_routes)} route(s) recovered from {len(args.configs)} config file(s) and "
              f"{len(java_paths)} Java file(s)")
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
            unit = args.unit or Path(args.configs[0]).name
            write_session_ledger(Path(args.session_out), unit, all_session)
            print(f"wrote {rel(Path(args.session_out), repo)}")
        if args.routes_out:
            write_routes(Path(args.routes_out), all_routes)
            print(f"wrote {rel(Path(args.routes_out), repo)}")
        return 0
    except UsageError as exc:
        print(f"struts-reader: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
