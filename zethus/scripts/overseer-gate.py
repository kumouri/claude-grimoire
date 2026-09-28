#!/usr/bin/env python3
"""The modernization extension's overseer: deterministic stage-gate checks, not a second agent.

**Decided (2026-09-28, `docs/modernization-shared.md`):** "script-gates now, agent later." This is
the script, built the same way ``base-freshness.py`` already gates Stage 0: one purpose per
subcommand, an unambiguous exit code, invoked by the ``zethus`` agent at the stage boundary it
guards. The extension point for a future agent-based reviewer is that every subcommand already
produces the same contract an agent reviewer would consume: a plain exit code plus a gap list.
Nothing here reads like a judgment call; the day a real run needs one, that gap is the spec for the
second ``.agent.md``, not a reason to make this script fuzzier.

Three subcommands, one per overseer row in the shared spec's table:

``constitution``
    Before Stage 3 (Implement) opens: every required constitution section has a rule citation or an
    explicit "no rule found"; no ``Low``-confidence citation lacks a recorded waiver (an ADR id).
    Exit 0 clear · 1 gaps found · 2 usage error.

``golden-master``
    Before Stage 4 (Tests) reports done: every rule id cited anywhere in the constitution has at
    least one fixture in the manifest whose ``source`` is ``"legacy-run"`` — captured by running the
    *legacy* system, never hand-authored. Exit 0 covered · 1 uncovered rows found · 2 usage error.

``credential``
    Any stage, on tool setup: a credential visible in the environment or a configured file resolves
    to an environment above the one this run is configured for. This is a standing safety check, not
    a stage boundary — v1's job stops at detection: flag it loudly and refuse to use it. Reporting to
    security and rotating the credential are manual steps for the human running the pipeline.
    Exit 0 clean · 1 a higher-environment credential was found · 2 usage error.

Values that came from git blobs, config files, or fixture manifests are treated as adversarial input
for the credential subcommand: it prints the *name* of a flagged variable or key, never its value.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import UsageError, cfg, find_repo_root, load_config, rel  # noqa: E402
from _ledger import LedgerError, REQUIRED_SECTIONS, parse_constitution  # noqa: E402

DEFAULT_ENVIRONMENTS = ("dev", "test", "staging", "prod")
DEFAULT_KEY_PATTERN = r"(?i)(password|secret|token|api[_-]?key|credential|conn(ection)?string)"


# --------------------------------------------------------------------------- constitution


def constitution_gaps(path: Path, repo: Path) -> list[str]:
    cons = parse_constitution(path)
    gaps = [f"section {s!r} has no rule citation and no 'No rule found' line" for s in cons.missing_sections()]
    for citation in cons.all_citations():
        if citation.confidence == "Low" and not citation.waiver:
            gaps.append(f"{rel(path, repo)}:{citation.line}: [{citation.id}] is Low confidence "
                       "with no recorded waiver (add '(waiver: <adr-id>)')")
    return gaps


def cmd_constitution(args, repo: Path) -> int:
    path = Path(args.constitution) if Path(args.constitution).is_absolute() else repo / args.constitution
    if not path.is_file():
        raise UsageError(f"constitution not found: {args.constitution}")
    try:
        gaps = constitution_gaps(path, repo)
    except LedgerError as exc:
        raise UsageError(str(exc)) from exc
    if gaps:
        print(f"overseer constitution-gate: {len(gaps)} gap(s) in {rel(path, repo)} — refuse to "
              "open Stage 3 (Implement):")
        for g in gaps:
            print(f"  - {g}")
        return 1
    print(f"overseer constitution-gate: clear — every required section of {rel(path, repo)} is "
          "sourced or explicitly empty, no unwaived Low-confidence row. Proceed.")
    return 0


# --------------------------------------------------------------------------- golden-master


def fixture_coverage(manifest: dict) -> dict[str, list[dict]]:
    coverage: dict[str, list[dict]] = {}
    for fixture in manifest.get("fixtures", []) or []:
        for rule_id in fixture.get("ruleIds", []) or []:
            coverage.setdefault(rule_id, []).append(fixture)
    return coverage


def golden_master_gaps(constitution_path: Path, manifest_path: Path, repo: Path) -> list[str]:
    cons = parse_constitution(constitution_path)
    rule_ids = sorted({c.id for c in cons.all_citations()})
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LedgerError(f"can't read fixture manifest {manifest_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(f"{manifest_path} is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise LedgerError(f"{manifest_path} must be a JSON object with a 'fixtures' list")
    coverage = fixture_coverage(manifest)
    gaps = []
    for rule_id in rule_ids:
        fixtures = coverage.get(rule_id, [])
        legacy_run = [f for f in fixtures if f.get("source") == "legacy-run"]
        if not fixtures:
            gaps.append(f"[{rule_id}] has no fixture in {rel(manifest_path, repo)}")
        elif not legacy_run:
            gaps.append(f"[{rule_id}] only has authored fixture(s), none captured from a "
                       f"legacy run: {', '.join(f.get('id', '?') for f in fixtures)}")
    return gaps


def cmd_golden_master(args, repo: Path) -> int:
    cpath = Path(args.constitution) if Path(args.constitution).is_absolute() else repo / args.constitution
    if not cpath.is_file():
        raise UsageError(f"constitution not found: {args.constitution}")
    if args.fixtures:
        mpath = Path(args.fixtures) if Path(args.fixtures).is_absolute() else repo / args.fixtures
    else:
        cons = parse_constitution(cpath)
        found = cons.fixture_manifest_path(repo)
        if found is None:
            raise UsageError("no --fixtures given and the constitution's 'Fixture manifest' "
                             "field is empty")
        mpath = found
    if not mpath.is_file():
        raise UsageError(f"fixture manifest not found: {rel(mpath, repo)}")
    try:
        gaps = golden_master_gaps(cpath, mpath, repo)
    except LedgerError as exc:
        raise UsageError(str(exc)) from exc
    if gaps:
        print(f"overseer golden-master-gate: {len(gaps)} constitution row(s) not covered by a "
              "legacy-run fixture — refuse to report Stage 4 (Tests) done:")
        for g in gaps:
            print(f"  - {g}")
        return 1
    print("overseer golden-master-gate: clear — every constitution row has a fixture captured "
          "from the legacy system. Proceed.")
    return 0


# --------------------------------------------------------------------------- credential


def _environments(config: dict) -> tuple[str, ...]:
    envs = cfg(config, "overseer.environments", list(DEFAULT_ENVIRONMENTS))
    if not isinstance(envs, list) or not envs or not all(isinstance(e, str) and e for e in envs):
        raise UsageError("overseer.environments must be a non-empty list of environment names")
    return tuple(envs)


def _current_environment(config: dict, environments: tuple[str, ...], override: str | None) -> str:
    current = override or cfg(config, "overseer.currentEnvironment")
    if not current:
        raise UsageError("no environment configured: set overseer.currentEnvironment, or pass "
                         "--environment")
    if current not in environments:
        raise UsageError(f"overseer.currentEnvironment {current!r} is not in overseer.environments "
                         f"({', '.join(environments)})")
    return current


WORD_RE = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+")


def _tokens(name: str) -> list[str]:
    """Split an env var (``PROD_DB_PASSWORD``) or a config key (``prodApiToken``) into lowercase
    words, so an environment name is found whether the naming style is snake, kebab or camelCase.
    """
    parts = re.split(r"[_\-.\[\]/]+", name)
    return [w.lower() for part in parts for w in WORD_RE.findall(part)]


def _match_environment(name: str, environments: tuple[str, ...], override: re.Pattern[str] | None
                       ) -> str | None:
    if override is not None:
        m = override.search(name)
        return m.group(1).lower() if m else None
    tokens = _tokens(name)
    return next((e for e in environments if e.lower() in tokens), None)


@dataclass
class Flag:
    name: str            # env var or "file:key", never the value
    environment: str
    where: str            # "environment" or a config file path


def scan_environment(environments: tuple[str, ...], current: str, override: re.Pattern[str] | None,
                     environ: dict[str, str]) -> list[Flag]:
    rank = {e: i for i, e in enumerate(environments)}
    flags = []
    for name, value in environ.items():
        if not value:
            continue
        env = _match_environment(name, environments, override)
        if env is not None and rank[env] > rank[current]:
            flags.append(Flag(name=name, environment=env, where="environment"))
    return flags


def scan_config_files(paths: list[Path], environments: tuple[str, ...], current: str,
                      override: re.Pattern[str] | None, key_pattern: re.Pattern[str],
                      repo: Path) -> list[Flag]:
    rank = {e: i for i, e in enumerate(environments)}
    flags = []
    for path in paths:
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key, value in _flatten(data):
            if not value or not key_pattern.search(key):
                continue
            env = _match_environment(key, environments, override)
            if env is not None and rank[env] > rank[current]:
                flags.append(Flag(name=f"{rel(path, repo)}:{key}", environment=env, where=str(path)))
    return flags


def _flatten(data, prefix: str = "") -> list[tuple[str, str]]:
    """``(dotted.key, str(value))`` pairs from nested JSON, so a credential nested under any
    depth of config structure is still found; only scalar leaves count as a value to check."""
    out: list[tuple[str, str]] = []
    if isinstance(data, dict):
        for k, v in data.items():
            out.extend(_flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            out.extend(_flatten(v, f"{prefix}[{i}]"))
    elif isinstance(data, (str, int, float)) and str(data):
        out.append((prefix, str(data)))
    return out


def cmd_credential(args, repo: Path, config: dict) -> int:
    environments = _environments(config)
    current = _current_environment(config, environments, args.environment)
    override_raw = args.env_pattern or cfg(config, "overseer.credentialCheck.envVarPattern")
    override = re.compile(override_raw) if override_raw else None
    key_pattern = re.compile(args.key_pattern
                             or cfg(config, "overseer.credentialCheck.keyPattern", DEFAULT_KEY_PATTERN))
    config_files = [repo / p for p in
                    (args.config_file or cfg(config, "overseer.credentialCheck.configFiles", []) or [])]

    env_flags = scan_environment(environments, current, override, dict(os.environ))
    file_flags = scan_config_files(config_files, environments, current, override, key_pattern, repo)
    flags = env_flags + file_flags
    if flags:
        print(f"overseer credential-gate: {len(flags)} credential(s) for an environment above "
              f"{current!r} found — FLAGGED, refusing to use them:")
        for f in flags:
            print(f"  - {f.name} (looks like {f.environment})")
        print("This is detection only: report to security and rotate the credential manually. "
              "The run does not proceed with it.")
        return 1
    print(f"overseer credential-gate: clean — no credential above {current!r} found in the "
          "environment or configured files.")
    return 0


# --------------------------------------------------------------------------- cli


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="overseer-gate",
                                description="Deterministic modernization stage gates.")
    p.add_argument("--repo", help="repository root (default: nearest .git ancestor of cwd)")
    p.add_argument("--config", help="config file")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("constitution", help="gate before Stage 3 (Implement)")
    c.add_argument("--constitution", required=True, help="path to the constitution Markdown file")

    g = sub.add_parser("golden-master", help="gate before Stage 4 (Tests) reports done")
    g.add_argument("--constitution", required=True, help="path to the constitution Markdown file")
    g.add_argument("--fixtures", help="path to the fixture manifest JSON (default: the "
                                      "constitution's 'Fixture manifest' field)")

    cr = sub.add_parser("credential", help="standing check: any stage, on tool setup")
    cr.add_argument("--environment", help="override overseer.currentEnvironment")
    cr.add_argument("--env-pattern", help="override the environment-name regex (group 1 is the name)")
    cr.add_argument("--key-pattern", help="override the credential-shaped-key regex")
    cr.add_argument("--config-file", action="append",
                    help="repo-relative JSON file to scan for credentials (repeatable)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo = Path(args.repo).resolve() if args.repo else find_repo_root()
        config, _ = load_config(repo, args.config)
        if args.command == "constitution":
            return cmd_constitution(args, repo)
        if args.command == "golden-master":
            return cmd_golden_master(args, repo)
        if args.command == "credential":
            return cmd_credential(args, repo, config)
        raise UsageError(f"unknown command: {args.command}")
    except UsageError as exc:
        print(f"overseer-gate: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
