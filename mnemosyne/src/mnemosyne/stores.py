"""Mnemosyne federation — additional git repos as broader, shared memory tiers.

The primary repo keeps its own `local` (gitignored) + `shared` (committed) tiers. A *store*
is a separate mnemosyne memory repo — a broader tier (e.g. `team`, `enterprise`) declared in
`config.stores`. This module resolves stores, clones/pulls them (best-effort), and folds their
committed lessons into a single federated view for recall/stats/validate. Writing up to a store
(export) is driven by `core.export`; this module only resolves paths and reads.

Design notes:
  - Each store has a distinct id `prefix`, so federated lesson ids never collide (validated in
    config._validate). That is what lets `federated_load` merge repos without shadowing.
  - Clone/pull are BEST-EFFORT and never raise into a recall — an unreachable or uncredentialed
    remote is skipped with a human-readable note (mirrors core.bump_usage's swallow-and-continue).
    Recall never pulls (read-only over already-cloned dirs); pulling is a `sync`-time action.
  - Import direction: this module imports leaf primitives from core at top level; core imports
    THIS module lazily inside functions only, so there is no import cycle.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path

from .core import git, read_jsonl, shared_path

# Never let an auto clone/pull of a store hang on a credential or host-key prompt — a store the
# user hasn't set up credentials for must fail fast (best-effort skip), not block a recall.
_BATCH_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_SSH_COMMAND": "ssh -oBatchMode=yes"}


# ----------------------------------------------------------------------------- store model


class Store:
    """A resolved store: a broader shared memory tier backed by its own git repo."""

    __slots__ = ("tier", "prefix", "url", "path", "readonly", "branch")

    def __init__(self, tier, prefix, *, url=None, path=None, readonly=False, branch=None):
        self.tier = tier
        self.prefix = prefix
        self.url = url
        self.path = path
        self.readonly = readonly
        self.branch = branch

    def __repr__(self):
        where = self.path or self.url or "?"
        return f"<Store {self.tier} ({self.prefix}) {where}>"


def resolve_stores(cfg) -> list:
    """Build Store objects from the normalized dicts in cfg.stores."""
    return [Store(s["tier"], s["prefix"], url=s.get("url"), path=s.get("path"),
                  readonly=bool(s.get("readonly")), branch=s.get("branch"))
            for s in getattr(cfg, "stores", []) or []]


def resolve_store(cfg, tier: str):
    """Return the resolved Store for a tier label, or None."""
    for st in resolve_stores(cfg):
        if st.tier == tier:
            return st
    return None


# ----------------------------------------------------------------------------- cache + clone


def cache_root() -> Path:
    base = os.environ.get("MNEMOSYNE_CACHE")
    return Path(base).expanduser() if base else Path.home() / ".mnemosyne" / "stores"


def store_dir(st: Store) -> Path:
    """Where a store's working copy lives: its explicit path, else a hashed cache dir.

    The URL is hashed so a `git@host:org/repo.git` never leaks illegal filename chars onto disk
    (also keeps two same-tier stores with different URLs from colliding). Windows-safe."""
    if st.path:
        return Path(st.path).expanduser().resolve()
    h = hashlib.sha1((st.url or "").encode("utf-8")).hexdigest()[:12]
    return cache_root() / f"{st.tier}-{h}"


def is_memory_repo(p: Path) -> bool:
    return (p / "memory").is_dir()


def ensure_cloned(st: Store) -> tuple:
    """Return (repo_path, note). Clone a url-store on first use; verify a path-store exists.

    Never raises: on any failure returns (None, "<reason>") so callers can skip the store.
    A url-store is cloned atomically (temp dir + rename) so a concurrent clone can't leave a
    half-populated cache dir behind."""
    d = store_dir(st)
    if st.path or d.exists():
        if not is_memory_repo(d):
            return None, f"store '{st.tier}': {d} is not a mnemosyne memory repo (no memory/ dir)"
        return d, None
    # url-store, not yet cloned
    if not st.url:
        return None, f"store '{st.tier}': no path and no url to clone"
    tmp = Path(tempfile.mkdtemp(prefix=f"mnemosyne-clone-{st.tier}-", dir=str(cache_root_ready())))
    try:
        dest = tmp / "repo"
        args = ["clone", "--quiet"]
        if st.branch:
            args += ["--branch", st.branch]
        code, _out, err = git(Path.cwd(), *args, st.url, str(dest), env=_BATCH_ENV)
        if code != 0:
            return None, f"store '{st.tier}': clone failed ({err or 'git error'})"
        if not is_memory_repo(dest):
            return None, f"store '{st.tier}': cloned repo has no memory/ dir — not a mnemosyne store"
        if d.exists():  # someone else won the race; use theirs
            return (d, None) if is_memory_repo(d) else (None, f"store '{st.tier}': concurrent clone left a bad dir")
        d.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(dest), str(d))
        return d, None
    except OSError as e:
        return None, f"store '{st.tier}': clone error ({e})"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def cache_root_ready() -> Path:
    root = cache_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def pull(st: Store) -> tuple:
    """Best-effort `git pull --ff-only` for a store. Return (repo_path, note). Never raises."""
    d, note = ensure_cloned(st)
    if d is None:
        return None, note
    if st.path:
        # explicit path-stores may be plain dirs (tests) — pull only if it's a git work tree
        code, _o, _e = git(d, "rev-parse", "--is-inside-work-tree")
        if code != 0:
            return d, None
    code, out, err = git(d, "pull", "--ff-only", env=_BATCH_ENV)
    if code == 127:
        return d, f"store '{st.tier}': git not found"
    if code != 0:
        return d, f"store '{st.tier}': pull failed ({err or out})"
    return d, None


# ----------------------------------------------------------------------------- id allocation


def next_store_id(st: Store, store_lessons) -> str:
    """Allocate the next `<prefix>-NNNN` id within a store's own lessons."""
    import re
    mx = 0
    pat = re.compile(rf"^{re.escape(st.prefix)}-(\d+)$")
    for l in store_lessons:
        m = pat.match(l.get("id", ""))
        if m:
            mx = max(mx, int(m.group(1)))
    return f"{st.prefix}-{mx + 1:04d}"


# ----------------------------------------------------------------------------- federated load


def federated_load(cfg, repo: Path, *, pull_remotes=False, notes=None):
    """Return (lessons, tier_by_id, origin_by_id, source_repo_by_id) across primary + all stores.

    tier_by_id       'local'/'shared' for the primary repo, else the store's tier label.
    origin_by_id     'primary' or the store tier label.
    source_repo_by_id  Path of the repo each lesson lives in (primary or a store dir).
    notes            optional list; skip messages for unreachable stores are appended here.

    With cfg.stores empty this returns exactly what core.load_all would (plus trivial maps), so
    the whole federated path degenerates to today's two-tier behavior."""
    from . import core  # lazy: avoid a top-level cycle (core imports this module lazily too)

    lessons, tier = core.load_all(repo)
    by_id = {l["id"]: l for l in lessons}
    origin = {i: "primary" for i in tier}
    src = {i: repo for i in tier}

    for st in resolve_stores(cfg):
        d, note = (pull(st) if pull_remotes else ensure_cloned(st))
        if note and notes is not None:
            notes.append(note)
        if d is None:
            continue
        for l in read_jsonl(shared_path(d)):
            lid = l.get("id")
            if not lid or lid in by_id:
                continue  # distinct prefixes should prevent collisions; first-seen wins if not
            by_id[lid] = l
            tier[lid] = st.tier
            origin[lid] = st.tier
            src[lid] = d

    return list(by_id.values()), tier, origin, src
