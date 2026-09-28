"""Shared parsing for the modernization extension's two artifacts: the rule ledger and the
behaviour constitution (see ``docs/modernization-shared.md``).

Stdlib only, JSON rather than YAML for the ledger's machine-checkable companion file — the shared
spec allows either ("an optional companion YAML/JSON file"), and JSON needs no dependency beyond
the standard library, unlike a hand-rolled YAML parser.

Two shapes:

- **Rule ledger** (``rules/<unit>.json``): one entry per recovered rule, cited to ``file:line``,
  with a confidence and a kind. Produced by ``recover-business-rules`` and its per-shape readers.
- **Constitution** (``templates/constitution.md``): a field table plus nine fixed sections, each
  either a list of rule citations (``- [R1] statement — confidence: High``, optionally
  ``(waiver: <adr-id>)``) or the literal sentinel line ``- No rule found — <reason>``. Consumed by
  the overseer gates in ``overseer-gate.py``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

KINDS = ("validation", "calculation", "orchestration", "side-effect", "error-handling",
         "scheduling", "formatting")
CONFIDENCE_LEVELS = ("High", "Medium", "Low")

REQUIRED_SECTIONS = (
    "Inputs", "Outputs", "Side effects", "Ordering", "Error & restart semantics",
    "Commit / transaction boundaries", "File / message formats", "Exit / status contract",
    "Scheduling / invocation contract",
    # Added 2026-09-28 for the web-app extension (docs/webapp-modernization.md); a batch
    # engagement with no session or web-facing auth marks both "No rule found" like any other
    # section that doesn't apply -- the shared constitution template is one template, not a fork.
    "Session / state", "Auth shim",
)

NO_RULE_FOUND_RE = re.compile(r"^-\s*No rule found\b(?:\s*[—-]\s*(?P<reason>.+))?$", re.I)
CITATION_RE = re.compile(
    r"^-\s*\[(?P<id>[A-Za-z0-9][A-Za-z0-9._-]*)\]\s+(?P<statement>.*?)\s*[—-]\s*"
    r"confidence:\s*(?P<confidence>High|Medium|Low)\b"
    r"(?:.*?\bwaiver:\s*(?P<waiver>\S+))?",
    re.I,
)
FIELD_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*$")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")


class LedgerError(Exception):
    """A ledger or constitution file is malformed. Printed without a traceback."""


@dataclass
class Rule:
    id: str
    rule: str
    kind: str
    where: str
    confidence: str
    why: str

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise LedgerError(f"rule {self.id}: kind must be one of {', '.join(KINDS)}, got {self.kind!r}")
        if self.confidence not in CONFIDENCE_LEVELS:
            raise LedgerError(f"rule {self.id}: confidence must be High/Medium/Low, got {self.confidence!r}")


def read_ledger(path: Path) -> tuple[str | None, list[Rule]]:
    """``(unit, rules)`` from a ``rules/<unit>.json`` companion file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LedgerError(f"can't read ledger {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or "rules" not in data:
        raise LedgerError(f"{path} must be a JSON object with a 'rules' list")
    rules = []
    seen: set[str] = set()
    for i, row in enumerate(data["rules"]):
        if not isinstance(row, dict):
            raise LedgerError(f"{path}: rules[{i}] must be an object")
        try:
            rule = Rule(id=str(row["id"]), rule=str(row["rule"]), kind=str(row["kind"]),
                       where=str(row["where"]), confidence=str(row["confidence"]),
                       why=str(row.get("why", "")))
        except KeyError as exc:
            raise LedgerError(f"{path}: rules[{i}] missing required field {exc}") from exc
        if rule.id in seen:
            raise LedgerError(f"{path}: duplicate rule id {rule.id!r}")
        seen.add(rule.id)
        rules.append(rule)
    return data.get("unit"), rules


def write_ledger(path: Path, unit: str, rules: list[Rule]) -> None:
    body = {"unit": unit, "rules": [
        {"id": r.id, "rule": r.rule, "kind": r.kind, "where": r.where,
         "confidence": r.confidence, "why": r.why} for r in rules
    ]}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(body, fh, indent=2)
        fh.write("\n")


@dataclass
class Citation:
    id: str
    statement: str
    confidence: str
    waiver: str | None
    section: str
    line: int


@dataclass
class Constitution:
    fields: dict[str, str]
    sections: dict[str, list[Citation]] = field(default_factory=dict)
    no_rule_found: dict[str, str] = field(default_factory=dict)   # section -> reason

    def ledger_paths(self, repo: Path) -> list[Path]:
        """Paths named in the 'Rule ledger(s)' field, repo-relative like every other config path."""
        raw = self.fields.get("Rule ledger(s)", "")
        parts = re.split(r"[,\s]+", raw.strip())
        return [repo / p for p in parts if p and p != "—"]

    def fixture_manifest_path(self, repo: Path) -> Path | None:
        raw = self.fields.get("Fixture manifest", "").strip()
        if not raw or raw == "—":
            return None
        return repo / raw

    def all_citations(self) -> list[Citation]:
        return [c for rows in self.sections.values() for c in rows]

    def missing_sections(self) -> list[str]:
        """Required sections with neither a citation nor a 'no rule found' sentinel."""
        return [s for s in REQUIRED_SECTIONS
                if not self.sections.get(s) and s not in self.no_rule_found]


def parse_constitution(path: Path) -> Constitution:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LedgerError(f"can't read constitution {path}: {exc}") from exc
    fields: dict[str, str] = {}
    sections: dict[str, list[Citation]] = {}
    no_rule_found: dict[str, str] = {}
    current: str | None = None
    for lineno, line in enumerate(text.splitlines(), 1):
        heading = HEADING_RE.match(line)
        if heading:
            current = heading.group(1).strip()
            continue
        row = FIELD_ROW_RE.match(line)
        if row and current is None:
            key, value = row.group(1).strip(), row.group(2).strip()
            if key and key != "Field" and not set(key) <= {"-"}:
                fields[key] = value
            continue
        if current is None or current not in REQUIRED_SECTIONS:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        nrf = NO_RULE_FOUND_RE.match(stripped)
        if nrf:
            no_rule_found[current] = (nrf.group("reason") or "").strip()
            continue
        m = CITATION_RE.match(stripped)
        if m:
            sections.setdefault(current, []).append(Citation(
                id=m.group("id"), statement=m.group("statement"),
                confidence=m.group("confidence").title(), waiver=m.group("waiver"),
                section=current, line=lineno,
            ))
    return Constitution(fields=fields, sections=sections, no_rule_found=no_rule_found)
