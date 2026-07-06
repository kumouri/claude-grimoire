"""Mnemosyne configuration wizard — build a documented `mnemosyne.config.json` interactively.

Stdlib-only and driven entirely through injectable input/output callables, so it works from a
plain terminal (no MCP, no Claude Code required) and can be tested hermetically by scripting the
inputs. It is self-documenting in two ways:

  * while you build it — every prompt explains the setting it configures, its accepted values, and
    its default (press Enter to keep the default);
  * after you build it — the file it writes carries an `_about` block documenting each field, which
    the engine ignores on load (it is an unknown key), so the config explains itself when reopened.

The wizard seeds from a bundled preset (a complete, valid config) and lets you tweak it, then
validates the result by constructing a real `Config` before it is written — so a config the wizard
produces is always loadable.
"""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

from .config import Config, ConfigError, load_named_example

# One-line docs per config field. Shown as help while prompting AND embedded in the written file's
# `_about` block, so the interactive help and the on-disk documentation never drift.
FIELD_DOCS = {
    "name": "Informational label for this config (shown by `mnemosyne config`).",
    "id_prefix": "Lesson id prefix — 'L' produces ids like L-0001. Must be unique vs any store prefix.",
    "categories": "The topical categories a lesson can be filed under (csv).",
    "failure_category": "Which category is run through the missing-deliverable / transient-failure guard.",
    "memory_types": "Cognitive-memory kinds a lesson can be: episodic / semantic / procedural.",
    "confidence": "Confidence level -> recall-score multiplier (higher confidence ranks higher).",
    "review_states": "Governance states a lesson moves through (local -> proposed -> approved).",
    "stages": "Lifecycle stages a lesson can be scoped to; `recall --stage` boosts matching lessons.",
    "recall_also_stage": "The 'front' stage a lesson captured downstream also recalls into.",
    "stage_weight": "Recall points added when a lesson's stage matches the current stage.",
    "query_weight": "Recall points per free-text keyword hit in a lesson (capped at 4).",
    "axes": "Recall dimensions: each scores weight x matches of a lesson's trigger against context.",
    "vocab": "Controlled vocabulary auto-harvested as tags from a free-text brief (csv).",
    "stopwords": "ALLCAPS tokens ignored when an axis extracts tokens from free text (csv).",
    "thresholds": "dup = near-duplicate similarity (0-1); prune_max_age_days; prune_cap = active cap.",
    "recall": "Recall digest defaults: top (max lessons), min_score, budget (max chars).",
    "stores": "Broader shared memory repos federated in as extra tiers (e.g. team / enterprise).",
}

# preset key -> (bundled config name, one-line description)
PRESETS = {
    "minimal": ("default", "tags + stages + free-text only — the smallest useful config"),
    "software-eng": ("software-eng", "rich axes: components, work-types, source-systems, services, endpoints"),
    "multi-store": ("multi-store", "minimal axes + example team/enterprise stores (federation)"),
}


# ----------------------------------------------------------------------------- io + prompts


class IO:
    """A thin, injectable console. Tests pass their own input/output callables."""

    def __init__(self, input_fn=None, output_fn=None, color=None):
        # Resolve at call time (not def time) so tests can monkeypatch builtins.input/print.
        self._in = input_fn or input
        self._out = output_fn or print
        from .color import Palette, should_color
        # Auto-enable brand colour only on the real stdout path (default print) at a TTY. A test or
        # the selftest that injects its own output_fn gets plain text.
        if color is None:
            color = should_color() if output_fn is None else False
        self.c = Palette(color)

    def ask(self, prompt: str) -> str:
        return self._in(prompt)

    def say(self, msg: str = "") -> None:
        self._out(msg)

    def section(self, title: str, desc: str = "") -> None:
        self.say("")
        self.say(self.c.title(f"== {title} =="))
        for line in _wrap(desc):
            self.say(self.c.dim(line))


def _wrap(text: str, width: int = 78):
    out = []
    for para in (text or "").split("\n"):
        out.extend(textwrap.wrap(para, width) or [""])
    return out


def _fmt_default(d) -> str:
    if d is None:
        return ""
    if isinstance(d, bool):
        return "yes" if d else "no"
    if isinstance(d, list):
        return ",".join(str(x) for x in d)
    return str(d)


def _coerce(raw: str, cast: str):
    if cast == "int":
        try:
            return int(raw)
        except ValueError:
            raise ValueError(f"'{raw}' is not a whole number")
    if cast == "float":
        try:
            return float(raw)
        except ValueError:
            raise ValueError(f"'{raw}' is not a number")
    if cast == "list":
        return [x.strip() for x in raw.split(",") if x.strip()]
    return raw


def ask(io: IO, label: str, help_text: str, default, *, cast: str = "str", choices=None):
    """Prompt for one value, documenting it. Enter keeps the default; input is cast + validated."""
    io.say("")
    for line in _wrap(help_text):
        io.say("  " + io.c.dim(line))
    if choices:
        io.say("  options: " + io.c.value(", ".join(str(c) for c in choices)))
    while True:
        raw = io.ask(f"  {io.c.label(label)} [{io.c.value(_fmt_default(default))}]: ").strip()
        if raw == "":
            return default
        try:
            val = _coerce(raw, cast)
        except ValueError as e:
            io.say(io.c.warn(f"  ! {e}"))
            continue
        if choices and val not in choices:
            io.say(io.c.warn("  ! choose one of: ") + io.c.value(", ".join(str(c) for c in choices)))
            continue
        return val


def ask_bool(io: IO, label: str, help_text: str, default: bool = False) -> bool:
    io.say("")
    for line in _wrap(help_text):
        io.say("  " + io.c.dim(line))
    hint = "Y/n" if default else "y/N"
    while True:
        raw = io.ask(f"  {io.c.label(label)} [{io.c.value(hint)}]: ").strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        io.say(io.c.warn("  ! please answer y or n"))


def _ask_unique(io: IO, label: str, help_text: str, default, taken, what: str):
    while True:
        v = ask(io, label, help_text, default)
        if v in taken:
            io.say(io.c.warn(f"  ! {what} '{v}' is already used — it must be unique"))
            continue
        return v


# ----------------------------------------------------------------------------- section editors


def _edit_axes(io: IO, axes):
    axes = [dict(a) for a in axes]
    if axes:
        io.say("")
        io.say("  current axes:")
        for a in axes:
            io.say(f"    - {io.c.value(a['name'])} (match={a.get('match', 'set')}, weight={a.get('weight', 1)})")
        if ask_bool(io, "Remove any of these axes?", "Drop axes you don't need.", default=False):
            axes = [a for a in axes
                    if ask_bool(io, f"Keep axis '{a['name']}'?", "", default=True)]
    while ask_bool(io, "Add a recall axis?",
                   "Define a new dimension lessons are scored on (e.g. components, services).",
                   default=False):
        axes.append(_build_axis(io, {a["name"] for a in axes}))
    if not axes:
        io.say(io.c.dim("  (no axes — recall will rely on stages + free-text matching only)"))
    return axes


def _build_axis(io: IO, taken):
    while True:
        name = ask(io, "Axis name",
                   "The trigger key + CLI flag, e.g. 'components'. Lowercase; spaces become '_'.",
                   "tags").strip().replace(" ", "_")
        if not name:
            io.say(io.c.warn("  ! an axis needs a name"))
            continue
        if name in taken:
            io.say(io.c.warn(f"  ! axis '{name}' already exists"))
            continue
        break
    match = ask(io, "Match strategy",
                "set = case-insensitive overlap (tags, components); "
                "glob = fnmatch both ways (service-name patterns); "
                "glob_scalar = one scalar context vs a list of trigger patterns (an endpoint vs 'POST *').",
                "set", choices=["set", "glob", "glob_scalar"])
    weight = ask(io, "Weight (points per match)",
                 "How much this axis matters in ranking — higher wins ties.", 3, cast="int")
    axis = {"name": name, "match": match, "weight": weight, "label": name}
    if match == "glob_scalar":
        axis["context"] = ask(io, "Context key",
                              "The recall-input key this axis reads (often differs from the name, e.g. 'endpoint').",
                              name)
    if ask_bool(io, "Auto-extract this axis from a free-text brief?",
                "Let `recall --from-brief` pull values for this axis out of the text automatically.",
                default=(match == "set")):
        src = ask(io, "Extract from",
                  "'vocab' matches the controlled vocabulary; 'enum' matches this axis's allowed values.",
                  "vocab", choices=["vocab", "enum"])
        axis["extract"] = {"from": src}
    return axis


def _edit_stores(io: IO, stores, id_prefix: str):
    stores = [dict(s) for s in stores]
    if stores:
        io.say("")
        io.say("  current stores:")
        for s in stores:
            io.say(f"    - {io.c.value(s['tier'])} ({s['prefix']}-) -> {s.get('url') or s.get('path')}")
    if not ask_bool(io, "Configure shared team/enterprise stores?",
                    "Federate this repo with other memory repos as broader tiers. "
                    "Skip if you just want a self-contained local repo.",
                    default=bool(stores)):
        return stores
    while ask_bool(io, "Add a shared store?",
                   "A broader tier backed by its own git repo (recall reads it; `promote --to` writes to it).",
                   default=not stores):
        taken_tiers = {"local", "shared"} | {s["tier"] for s in stores}
        taken_prefixes = {id_prefix} | {s["prefix"] for s in stores}
        tier = _ask_unique(io, "Store tier label",
                           "e.g. 'team' or 'enterprise'. Cannot be 'local' or 'shared'.",
                           "team", taken_tiers, "tier")
        prefix = _ask_unique(io, "Store id prefix",
                             "A distinct 1-2 letter prefix, e.g. 'T'. Distinct prefixes keep federated ids from colliding.",
                             "T", taken_prefixes, "prefix")
        entry = {"tier": tier, "prefix": prefix}
        kind = ask(io, "Address by",
                   "'url' — mnemosyne clones + pulls it into a cache; 'path' — an existing repo on disk.",
                   "url", choices=["url", "path"])
        if kind == "url":
            entry["url"] = ask(io, "Git URL", "e.g. git@github.com:org/team-memory.git",
                               "git@github.com:org/team-memory.git")
        else:
            entry["path"] = ask(io, "Repo path", "Path to an existing mnemosyne memory repo.",
                                "../team-memory")
        entry["readonly"] = ask_bool(io, "Read-only?",
                                     "If yes, `promote --to` refuses to write to it.", default=False)
        stores.append(entry)
    return stores


# ----------------------------------------------------------------------------- orchestration


def run_wizard(io: IO | None = None, *, input_fn=None, output_fn=None) -> dict:
    """Walk the user through building a config and return the validated config doc (a dict).

    Raises ConfigError if the assembled config fails validation (rare — inputs are constrained)."""
    io = io or IO(input_fn, output_fn)

    io.say(io.c.title("Mnemosyne configuration wizard"))
    io.say(io.c.dim("Builds a documented mnemosyne.config.json. Press Enter to accept each [default]."))

    io.section("Starting point",
               "Seed the config from a preset (a complete, valid config) and tweak it from there.")
    for key, (_name, desc) in PRESETS.items():
        io.say(f"  - {io.c.value(key)}: {desc}")
    preset = ask(io, "Preset", "Which preset to start from.", "minimal", choices=list(PRESETS))
    doc = load_named_example(PRESETS[preset][0]).as_dict()

    io.section("Identity", "How this config and its lessons are labelled.")
    doc["name"] = ask(io, "Config name", FIELD_DOCS["name"], doc["name"])
    doc["id_prefix"] = ask(io, "Lesson id prefix", FIELD_DOCS["id_prefix"], doc["id_prefix"])

    io.section("Categories", "The vocabulary a lesson is filed under.")
    doc["categories"] = ask(io, "Categories", FIELD_DOCS["categories"], doc["categories"], cast="list")
    if doc["failure_category"] not in doc["categories"]:
        doc["failure_category"] = doc["categories"][0]
    doc["failure_category"] = ask(io, "Failure category", FIELD_DOCS["failure_category"],
                                  doc["failure_category"], choices=doc["categories"])

    io.section("Lifecycle stages",
               "Stages let the loop learn across intake -> plan -> implement -> review, not just at the front.")
    doc["stages"] = ask(io, "Stages", FIELD_DOCS["stages"], doc["stages"], cast="list")
    if doc["recall_also_stage"] not in doc["stages"]:
        doc["recall_also_stage"] = doc["stages"][0]
    doc["recall_also_stage"] = ask(io, "Front stage", FIELD_DOCS["recall_also_stage"],
                                   doc["recall_also_stage"], choices=doc["stages"])
    doc["stage_weight"] = ask(io, "Stage weight", FIELD_DOCS["stage_weight"], doc["stage_weight"], cast="float")
    doc["query_weight"] = ask(io, "Query keyword weight", FIELD_DOCS["query_weight"],
                              doc["query_weight"], cast="float")

    io.section("Recall axes",
               "Axes are the heart of recall: each is a dimension a lesson's trigger is scored on. "
               "Adding an axis automatically gives it a CLI flag and makes it scored — no code change.")
    doc["axes"] = _edit_axes(io, doc["axes"])

    io.section("Vocabulary", "Optional controlled vocabulary auto-harvested as tags from a brief.")
    doc["vocab"] = ask(io, "Vocab", FIELD_DOCS["vocab"], doc["vocab"], cast="list")

    io.section("Hygiene thresholds", "Keep the store's signal above noise.")
    th = dict(doc["thresholds"])
    th["dup"] = ask(io, "Duplicate similarity threshold (0-1)",
                    "At/above this title+tag similarity, a capture reinforces the existing lesson instead of adding one.",
                    th["dup"], cast="float")
    th["prune_max_age_days"] = ask(io, "Prune max age (days)",
                                   "Never-recalled low/medium-confidence lessons older than this are prune candidates.",
                                   th["prune_max_age_days"], cast="int")
    th["prune_cap"] = ask(io, "Active lesson cap",
                          "Soft cap on active lessons; prune retires the lowest-value ones over it.",
                          th["prune_cap"], cast="int")
    doc["thresholds"] = th

    io.section("Recall defaults", "Defaults for the recall digest (overridable per call).")
    rc = dict(doc["recall"])
    rc["top"] = ask(io, "Top N", "Max lessons returned by a recall.", rc["top"], cast="int")
    rc["min_score"] = ask(io, "Min score", "Lessons scoring below this are not surfaced.", rc["min_score"], cast="float")
    rc["budget"] = ask(io, "Digest char budget", "Max characters in the text digest (0 = unlimited).", rc["budget"], cast="int")
    doc["recall"] = rc

    io.section("Shared stores (federation)",
               "Optionally federate with broader team/enterprise memory repos. See `mnemosyne stores`.")
    doc["stores"] = _edit_stores(io, doc.get("stores", []), doc["id_prefix"])

    # Validate by constructing a real Config — the same check the engine runs on load.
    try:
        Config(doc)
    except ConfigError as e:
        io.say("")
        io.say(io.c.warn(f"  ! the assembled config is not valid: {e}"))
        raise
    return doc


# ----------------------------------------------------------------------------- output


def documented_doc(doc: dict) -> dict:
    """Wrap a config doc with a self-documenting `_about` block (the engine ignores unknown keys)."""
    about = {"_": "Generated by `mnemosyne wizard`. The _about block documents each field and is "
                  "ignored by the engine. Edit fields below and re-run `mnemosyne validate`."}
    for key in doc:
        if key in FIELD_DOCS:
            about[key] = FIELD_DOCS[key]
    return {"_about": about, **doc}


def write_config(doc: dict, path: Path) -> Path:
    """Write the documented config to disk as pretty JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(documented_doc(doc), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
