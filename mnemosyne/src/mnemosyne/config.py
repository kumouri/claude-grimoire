"""Mnemosyne configuration — the knobs that make the engine domain-agnostic.

Everything that used to be hardcoded for one pipeline (the recall axes, their
weights, the controlled vocabulary, the lifecycle stages) lives in a JSON config
file. The engine reads a `Config` object and never hardcodes a domain concept.

Resolution order (first that exists wins):
  explicit path arg  |  $MNEMOSYNE_CONFIG  |  <repo>/mnemosyne.config.json  |  bundled default

A config is a JSON object with these keys (all optional except where noted; missing
keys fall back to the bundled default):

  name                 label for this config (informational)
  id_prefix            lesson id prefix, e.g. "L" -> L-0001
  categories           topical category enum
  memory_types         cognitive-memory enum (episodic/semantic/procedural)
  confidence           {level: multiplier} map, e.g. {"high":1.0,"medium":0.85,"low":0.6}
  review_states        governance state enum (local/proposed/approved)
  stages               lifecycle stage enum (e.g. intake/plan/implement/review)
  recall_also_stage    when a lesson is captured in stage X, also recall it here (the "front" stage)
  stage_weight         recall points for a stage match
  query_weight         recall points per free-text keyword hit (capped at 4)
  axes                 the recall dimensions (see below)
  vocab                controlled vocabulary harvested as tags from free text
  stopwords            ALLCAPS tokens to ignore when a "set/allcaps" axis extracts tokens
  thresholds           {dup, prune_max_age_days, prune_cap}
  recall               {top, min_score, budget} defaults for the recall digest

Each entry in `axes` is a dimension recall scores a lesson on:

  name        the trigger key inside a lesson (lesson.trigger[name]) and the CLI flag
  weight      points per match
  match       "set"         list-vs-list case-insensitive overlap (weight * hits)
              "glob"        list-vs-list bidirectional fnmatch (weight * hits)
              "glob_scalar" a scalar context value vs a list of trigger patterns (weight once)
  context     the recall-context key this axis reads (defaults to `name`; glob_scalar
              axes usually differ, e.g. name=endpoint_patterns, context=endpoint)
  label       short reason label shown in the digest ("why it matched")
  enum        optional allowed values (validated; also used by extract from="enum")
  extract     optional auto-extraction rule for `recall --from-brief`/`--query`:
                {"from": "vocab"}                  match config.vocab entries
                {"from": "enum", "aliases": {...}}  match enum values + alias phrases
                {"regex": ["...", "..."]}          capture via regex(es)
                {"allcaps": true}                  ALLCAPS tokens minus stopwords
"""
from __future__ import annotations

import json
import os
from pathlib import Path

BUNDLED_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_CONFIG_PATH = BUNDLED_DIR / "default.config.json"
CONFIG_FILENAME = "mnemosyne.config.json"


class ConfigError(Exception):
    """Raised when a config file is present but malformed."""


class Config:
    """A validated, engine-facing view of a mnemosyne config document."""

    def __init__(self, doc: dict, source: str = "<default>"):
        d = _merge_defaults(doc)
        self.source = source
        self.name = d["name"]
        self.id_prefix = d["id_prefix"]
        self.categories = list(d["categories"])
        # the category whose captures are run through the missing-deliverable / transient-failure guard
        self.failure_category = d.get("failure_category", "mistake")
        self.memory_types = list(d["memory_types"])
        self.confidence = dict(d["confidence"])
        self.confidence_levels = list(self.confidence.keys())
        self.review_states = list(d["review_states"])
        self.stages = list(d["stages"])
        self.recall_also_stage = d.get("recall_also_stage") or (self.stages[0] if self.stages else None)
        self.stage_weight = float(d["stage_weight"])
        self.query_weight = float(d["query_weight"])
        self.axes = [_norm_axis(a) for a in d["axes"]]
        self.axis_names = [a["name"] for a in self.axes]
        self.vocab = list(d.get("vocab", []))
        self.stopwords = set(x.upper() for x in d.get("stopwords", []))
        th = d.get("thresholds", {})
        self.dup_threshold = float(th.get("dup", 0.6))
        self.prune_max_age_days = int(th.get("prune_max_age_days", 180))
        self.prune_cap = int(th.get("prune_cap", 200))
        rc = d.get("recall", {})
        self.recall_top = int(rc.get("top", 6))
        self.recall_min_score = float(rc.get("min_score", 0.5))
        self.recall_budget = int(rc.get("budget", 1800))
        _validate(self)

    def axis(self, name: str):
        for a in self.axes:
            if a["name"] == name:
                return a
        return None

    # id helpers -------------------------------------------------------------
    @property
    def id_pattern(self) -> str:
        return rf"^{self.id_prefix}-\d{{4}}$"

    def format_id(self, n: int) -> str:
        return f"{self.id_prefix}-{n:04d}"

    def as_dict(self) -> dict:
        return {
            "name": self.name, "id_prefix": self.id_prefix, "categories": self.categories,
            "failure_category": self.failure_category,
            "memory_types": self.memory_types, "confidence": self.confidence,
            "review_states": self.review_states, "stages": self.stages,
            "recall_also_stage": self.recall_also_stage, "stage_weight": self.stage_weight,
            "query_weight": self.query_weight, "axes": self.axes, "vocab": self.vocab,
            "stopwords": sorted(self.stopwords),
            "thresholds": {"dup": self.dup_threshold, "prune_max_age_days": self.prune_max_age_days,
                           "prune_cap": self.prune_cap},
            "recall": {"top": self.recall_top, "min_score": self.recall_min_score, "budget": self.recall_budget},
        }


def _norm_axis(a: dict) -> dict:
    if "name" not in a:
        raise ConfigError(f"axis missing 'name': {a}")
    out = dict(a)
    out.setdefault("match", "set")
    out.setdefault("weight", 1)
    out.setdefault("context", out["name"])
    out.setdefault("label", out["name"])
    if out["match"] not in ("set", "glob", "glob_scalar"):
        raise ConfigError(f"axis '{out['name']}': unknown match '{out['match']}'")
    return out


def _load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ConfigError(f"cannot read config {p}: {e}") from e


_DEFAULT_CACHE: dict | None = None


def _default_doc() -> dict:
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is None:
        _DEFAULT_CACHE = _load_json(DEFAULT_CONFIG_PATH)
    return dict(_DEFAULT_CACHE)


def _merge_defaults(doc: dict) -> dict:
    """Shallow-merge over the bundled default so a partial config is still complete."""
    base = _default_doc()
    base.update({k: v for k, v in (doc or {}).items() if v is not None})
    return base


def _validate(cfg: "Config") -> None:
    if not cfg.stages:
        raise ConfigError("config.stages must be non-empty")
    if cfg.recall_also_stage and cfg.recall_also_stage not in cfg.stages:
        raise ConfigError(f"recall_also_stage '{cfg.recall_also_stage}' not in stages")
    if not cfg.confidence:
        raise ConfigError("config.confidence must map at least one level to a multiplier")
    names = [a["name"] for a in cfg.axes]
    if len(names) != len(set(names)):
        raise ConfigError("duplicate axis name in config.axes")


def resolve_config_path(config_arg: str | None = None, repo: Path | None = None) -> Path | None:
    """Return the config file to use, or None to fall back to the bundled default."""
    if config_arg:
        return Path(config_arg).expanduser().resolve()
    env = os.environ.get("MNEMOSYNE_CONFIG")
    if env:
        return Path(env).expanduser().resolve()
    if repo:
        cand = Path(repo) / CONFIG_FILENAME
        if cand.exists():
            return cand
    return None


def load_config(config_arg: str | None = None, repo: Path | None = None) -> Config:
    """Load a Config from the first source that exists, else the bundled default."""
    p = resolve_config_path(config_arg, repo)
    if p is None:
        return Config(_default_doc(), source=str(DEFAULT_CONFIG_PATH))
    return Config(_load_json(p), source=str(p))


def load_named_example(name: str) -> Config:
    """Load one of the bundled example configs (e.g. 'default', 'software-eng')."""
    p = BUNDLED_DIR / f"{name}.config.json"
    if not p.exists():
        raise ConfigError(f"no bundled config named '{name}' ({p})")
    return Config(_load_json(p), source=str(p))
