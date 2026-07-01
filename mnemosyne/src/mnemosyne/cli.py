"""Mnemosyne CLI — argument parsing + human/JSON formatting over the engine (core.py).

Axis flags are generated from the active config, so a config that adds a `components` axis
automatically gets `--components` on recall/capture with no code change.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

from . import core
from .config import Config, ConfigError, load_config

PROG = "mnemosyne"


def _recall_flag(ax: dict) -> str:
    key = ax["context"] if ax["match"] == "glob_scalar" else ax["name"]
    return "--" + key.replace("_", "-")


def _recall_dest(ax: dict) -> str:
    key = ax["context"] if ax["match"] == "glob_scalar" else ax["name"]
    return "ax__" + key


def _capture_dest(ax: dict) -> str:
    return "tg__" + ax["name"]


# ----------------------------------------------------------------------------- parser


def build_parser(cfg: Config) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=PROG, description="Mnemosyne reflexion memory engine (stdlib, config-driven).")
    p.add_argument("--repo", help="memory repo path (else $MNEMOSYNE_REPO, else cwd)")
    p.add_argument("--config", help="config path (else $MNEMOSYNE_CONFIG, else <repo>/mnemosyne.config.json, else bundled default)")
    p.add_argument("--format", choices=["text", "json"], default="text")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("recall", help="context in -> ranked, budgeted lesson digest out (the hot path)")
    r.add_argument("--from-brief", help="path to a brief (or '-' for stdin); auto-extracts context")
    r.add_argument("--query", help="free-text context; keywords + signals are extracted")
    for ax in cfg.axes:
        r.add_argument(_recall_flag(ax), dest=_recall_dest(ax),
                       help=f"{ax['name']} context ({ax['match']}, csv)")
    r.add_argument("--stage", choices=cfg.stages, help="current lifecycle stage; boosts lessons scoped to it")
    r.add_argument("--top", type=int, default=cfg.recall_top)
    r.add_argument("--min-score", type=float, default=cfg.recall_min_score)
    r.add_argument("--budget", type=int, default=cfg.recall_budget, help="max chars in the text digest (0 = unlimited)")
    r.set_defaults(func=cmd_recall)

    def add_capture_args(cp):
        cp.add_argument("--json", help="read a full lesson JSON object from FILE or '-' (stdin)")
        cp.add_argument("--title")
        cp.add_argument("--lesson", help="the actionable guidance to apply next time")
        cp.add_argument("--category", choices=cfg.categories)
        cp.add_argument("--memory-type", dest="memory_type", choices=cfg.memory_types)
        cp.add_argument("--confidence", choices=cfg.confidence_levels)
        cp.add_argument("--rationale")
        for ax in cfg.axes:
            cp.add_argument("--" + ax["name"].replace("_", "-"), dest=_capture_dest(ax),
                            help=f"trigger.{ax['name']} (csv)")
        cp.add_argument("--stage", choices=cfg.stages, help="lifecycle stage this lesson was learned in (provenance)")
        cp.add_argument("--stages", help="lifecycle stage(s) to recall it in, csv (default: --stage + the front stage; empty = all)")
        cp.add_argument("--spec", help="originating spec/ticket id")
        cp.add_argument("--anchors", help="file:line / url anchors, csv")
        cp.add_argument("--related", help="related lesson ids, csv")
        cp.add_argument("--supersedes", help="lesson ids this replaces, csv (metadata only)")
        cp.add_argument("--supersede", help="single lesson id to mark superseded by this one")
        cp.add_argument("--shared", action="store_true", help="write straight to the shared tier (admin/seed; normally promote instead)")
        cp.add_argument("--force", action="store_true", help="bank even if it looks like a transient failure or a near-duplicate (skips hygiene guards)")

    c = sub.add_parser("capture", aliases=["add"], help="save a lesson (decision/convention/...) to the local tier")
    add_capture_args(c)
    c.set_defaults(func=cmd_capture)

    rf = sub.add_parser("reflect", help="save a reflexion lesson from feedback on a prior run (category=failure)")
    add_capture_args(rf)
    rf.add_argument("--reflection-of", dest="reflection_of", help="what went wrong (the feedback that triggered this)")
    rf.set_defaults(func=cmd_reflect)

    pr = sub.add_parser("promote", help="move a local lesson to shared + stage the review PR (the governance gate)")
    pr.add_argument("id")
    pr.add_argument("--push", action="store_true", help="also create the branch, commit, and push (needs git+remote)")
    pr.set_defaults(func=cmd_promote)

    s = sub.add_parser("sync", help="git pull the shared memory (refresh before starting work)")
    s.set_defaults(func=cmd_sync)

    rn = sub.add_parser("render", help="regenerate memory/LESSONS.md from the JSONL")
    rn.set_defaults(func=cmd_render)

    li = sub.add_parser("list", help="list lessons (filterable)")
    li.add_argument("--category", choices=cfg.categories)
    li.add_argument("--status", choices=["active", "superseded", "retired"])
    li.add_argument("--tier", choices=["shared", "local"])
    li.set_defaults(func=cmd_list)

    sh = sub.add_parser("show", help="print one lesson as JSON")
    sh.add_argument("id")
    sh.set_defaults(func=cmd_show)

    st = sub.add_parser("stats", help="counts by category/tier/status")
    st.set_defaults(func=cmd_stats)

    v = sub.add_parser("validate", help="schema + spine consistency; exit 0 ok / 1 problems")
    v.set_defaults(func=cmd_validate)

    pn = sub.add_parser("prune", help="retire (never delete) low-value lessons + enforce the cap; dry-run unless --apply")
    pn.add_argument("--apply", action="store_true", help="actually retire candidates (default: dry-run preview)")
    pn.add_argument("--cap", type=int, default=cfg.prune_cap)
    pn.add_argument("--max-age-days", dest="max_age_days", type=int, default=cfg.prune_max_age_days)
    pn.set_defaults(func=cmd_prune)

    hy = sub.add_parser("hygiene", help="health report: duplicates, never-recalled, cap headroom, prune candidates")
    hy.add_argument("--cap", type=int, default=cfg.prune_cap)
    hy.add_argument("--max-age-days", dest="max_age_days", type=int, default=cfg.prune_max_age_days)
    hy.set_defaults(func=cmd_hygiene)

    it = sub.add_parser("init", help="scaffold a memory repo (memory/ + .gitignore [+ config])")
    it.add_argument("--example", help="copy a bundled example config into the repo (e.g. software-eng)")
    it.set_defaults(func=cmd_init)

    cf = sub.add_parser("config", help="print the resolved active config (and its source)")
    cf.set_defaults(func=cmd_config)

    se = sub.add_parser("selftest", help="run the zero-dep test suite")
    se.set_defaults(func=cmd_selftest)

    return p


# ----------------------------------------------------------------------------- command handlers


def cmd_recall(cfg, repo, args):
    axes = {}
    for ax in cfg.axes:
        val = getattr(args, _recall_dest(ax), None)
        if val:
            axes[ax["name"]] = val
    from_text = None
    if args.from_brief:
        from_text = sys.stdin.read() if args.from_brief == "-" else Path(args.from_brief).read_text(encoding="utf-8")
    ctx = core.build_recall_context(cfg, from_text=from_text, query=args.query, axes=axes, stage=args.stage)
    ranked, tier = core.recall(cfg, repo, ctx, top=args.top, min_score=args.min_score)
    print(core.render_digest(cfg, ranked, repo, tier, args.format, args.budget))
    return 0


def _capture_fields(cfg, args):
    base = None
    if getattr(args, "json", None):
        raw = sys.stdin.read() if args.json == "-" else Path(args.json).read_text(encoding="utf-8")
        base = json.loads(raw)
    trigger = {}
    for ax in cfg.axes:
        v = getattr(args, _capture_dest(ax), None)
        if v:
            trigger[ax["name"]] = v
    return {
        "base": base, "title": args.title, "lesson": args.lesson, "category": args.category,
        "memory_type": args.memory_type, "confidence": args.confidence, "rationale": args.rationale,
        "trigger": trigger, "stage": args.stage, "stages": args.stages, "spec": args.spec,
        "anchors": args.anchors, "reflection_of": getattr(args, "reflection_of", None),
        "related": args.related, "supersedes": args.supersedes, "shared": args.shared,
    }


def _print_capture_result(cfg, res, fmt, kind_label=None):
    if fmt == "json":
        print(json.dumps(res, indent=2))
        return 0
    if res["action"] == "reinforced":
        print(f"REINFORCED: {res['dup_id']} (similarity {res['similarity']:.2f} >= {res['threshold']}) — not banking a "
              f"duplicate; its reinforced-count grew, and repeated reinforcement can earn higher confidence.")
        print(f"  If this is genuinely different, re-run with --force; to replace it, use --supersede {res['dup_id']}.")
        print(f"  Announce: reflexion reinforced an existing lesson ({res['dup_id']}) rather than adding a new one.")
        return 0
    where = "SHARED" if res["shared"] else "LOCAL"
    print(f"SAVED: {res['id']} captured to {where} reflexion memory — \"{res['title']}\" "
          f"[{res['category']}/{res['memory_type']}].")
    if kind_label:
        print(f"  ({kind_label})")
    if not res["shared"]:
        print(f"  Not yet shared with the team. Promote for PR review with: {PROG} promote {res['id']}")
    print(f"  Announce: a new lesson was saved to reflexion memory ({res['id']}).")
    return 0


def cmd_capture(cfg, repo, args):
    try:
        res = core.capture(cfg, repo, _capture_fields(cfg, args), force=args.force, supersede=args.supersede)
    except core.LowValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    return _print_capture_result(cfg, res, args.format)


def cmd_reflect(cfg, repo, args):
    try:
        res = core.reflect(cfg, repo, _capture_fields(cfg, args), force=args.force, supersede=args.supersede)
    except core.LowValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    return _print_capture_result(cfg, res, args.format,
                                 kind_label="reflexion: captured from feedback on a prior run")


def cmd_promote(cfg, repo, args):
    res = core.promote(cfg, repo, args.id)
    if args.format == "json":
        print(json.dumps(res, indent=2))
        return 0
    print(f"PROMOTED: {res['id']} moved local -> shared and marked review=proposed — \"{res['title']}\".")
    branch = res["branch"]
    if res["is_git"]:
        if args.push:
            core.git(repo, "checkout", "-b", branch)
            core.git(repo, "add", "memory/lessons.jsonl", "memory/local.jsonl", "memory/LESSONS.md")
            core.git(repo, "commit", "-m", f"reflexion: promote {res['id']} — {res['title']}")
            rc, _, err = core.git(repo, "push", "-u", "origin", branch)
            print(f"  pushed branch {branch}" if rc == 0 else f"  push failed: {err}")
            print(f"  open the PR: gh pr create --fill --head {branch}")
        else:
            print("  Stage the review PR (PR-reviewed promotion gate):")
            print(f"    git -C \"{repo}\" checkout -b {branch}")
            print(f"    git -C \"{repo}\" add memory/lessons.jsonl memory/local.jsonl memory/LESSONS.md")
            print(f"    git -C \"{repo}\" commit -m \"reflexion: promote {res['id']} — {res['title']}\"")
            print(f"    git -C \"{repo}\" push -u origin {branch} && gh pr create --fill --head {branch}")
            print("  (a human reviewer approves before it becomes team-wide truth)")
    else:
        print("  note: not a git repo yet — `git init` the memory repo to enable PR promotion.")
    print(f"  Announce: {res['id']} was promoted for team review.")
    return 0


def cmd_sync(cfg, repo, args):
    res = core.sync(cfg, repo)
    if not res["ok"]:
        print(f"SYNC: git pull failed: {res['error']}")
        return 1
    print(f"SYNC: shared reflexion memory up to date @ {res['sha']} — {res['out']}")
    return 0


def cmd_render(cfg, repo, args):
    p = core.render_lessons_md(cfg, repo)
    n = sum(1 for l in core.load_all(repo)[0] if l.get("status") == "active")
    print(f"RENDER: wrote {p} ({n} active lessons).")
    return 0


def cmd_list(cfg, repo, args):
    rows = core.list_lessons(cfg, repo, category=args.category, status=args.status, tier_filter=args.tier)
    if args.format == "json":
        print(json.dumps([{"id": l["id"], "category": l["category"], "tier": t, "status": l.get("status"),
                           "confidence": l["confidence"], "title": l["title"]} for l, t in rows], indent=2))
    else:
        print(f"{len(rows)} lesson(s):")
        for l, t in rows:
            print(f"  {l['id']} [{l['category']:<12} {t:<6} {l.get('status', 'active'):<10} {l['confidence']:<6}] {l['title']}")
    return 0


def cmd_show(cfg, repo, args):
    print(json.dumps(core.show(cfg, repo, args.id), indent=2))
    return 0


def cmd_stats(cfg, repo, args):
    s = core.stats(cfg, repo)
    if args.format == "json":
        print(json.dumps(s, indent=2))
        return 0
    print(f"STATS: {s['total']} lessons ({s['active']} active, {s['retired']} retired) @ {s['sha']}")
    print(f"  tiers: shared={s['shared']} local={s['local']}")
    print("  by category: " + ", ".join(f"{k}={v}" for k, v in sorted(s["by_category"].items())))
    if s["most_used"]:
        print("  most-used: " + ", ".join(f"{i}({n})" for i, n in s["most_used"]))
    if s["most_reinforced"]:
        print("  most-reinforced: " + ", ".join(f"{i}({n})" for i, n in s["most_reinforced"]))
    return 0


def cmd_validate(cfg, repo, args):
    res = core.validate(cfg, repo)
    if args.format == "json":
        print(json.dumps(res, indent=2))
    else:
        print(f"VALIDATE: {'OK' if res['ok'] else str(len(res['problems'])) + ' problem(s)'} — "
              f"{res['counts']['total']} lessons ({res['counts']['shared']} shared, "
              f"{res['counts']['local']} local) @ {res['sha']}")
        for pb in res["problems"]:
            print(f"  - {pb}")
        if res["render_stale"]:
            print("  - note: LESSONS.md is stale; run `mnemosyne render`")
    return 0 if res["ok"] else 1


def cmd_prune(cfg, repo, args):
    res = core.prune(cfg, repo, apply=args.apply, cap=args.cap, max_age_days=args.max_age_days)
    if args.format == "json":
        print(json.dumps(res, indent=2))
        return 0
    if res["count"] == 0:
        print(f"PRUNE: nothing to retire — {res['active']} active lesson(s) within cap {res['cap']}, none aged out.")
        return 0
    verb = "RETIRED" if res["applied"] else "would retire (dry-run — pass --apply to commit)"
    print(f"PRUNE: {res['count']} candidate(s) {verb}:")
    for lid, d in sorted(res["candidates"].items()):
        print(f"  {lid} [{d['category']}/{d['tier']}] \"{d['title']}\" — {d['reason']}")
    if not res["applied"]:
        print("  (retire = status->retired + reason; the record is KEPT for audit, never deleted.)")
        return 0
    print(f"  retired {res['count']} lesson(s) (kept for audit); LESSONS.md re-rendered.")
    if res["shared_touched"]:
        print("  note: shared lessons changed — commit memory/lessons.jsonl (a reviewed change, like a promotion).")
    print(f"  Announce: reflexion retired {res['count']} low-value lesson(s).")
    return 0


def cmd_hygiene(cfg, repo, args):
    h = core.hygiene(cfg, repo, cap=args.cap, max_age_days=args.max_age_days)
    if args.format == "json":
        print(json.dumps(h, indent=2))
        return 0
    print(f"HYGIENE: {h['active']} active / {h['total']} total @ {h['sha']} (cap {h['cap']}, max-age {h['max_age_days']}d)")
    over = h["over"]
    print(f"  cap: {'OVER by ' + str(over) if over > 0 else 'within (' + str(-over) + ' headroom)'}")
    never = h["never_recalled"]
    print(f"  never-recalled active: {len(never)}"
          + (f" — {', '.join(never[:8])}{'...' if len(never) > 8 else ''}" if never else ""))
    dups = h["duplicate_pairs"]
    if dups:
        print(f"  near-duplicate pairs (>={cfg.dup_threshold}): "
              + ", ".join(f"{a}~{b}({sc:.2f})" for a, b, sc in dups[:8])
              + (f" (+{len(dups) - 8} more)" if len(dups) > 8 else ""))
    else:
        print("  near-duplicate pairs: none")
    print(f"  prune candidates: {h['prune_candidates']}"
          + (" — run `mnemosyne prune` to review" if h["prune_candidates"] else ""))
    return 0


def cmd_init(cfg, repo_arg, args):
    # init doesn't require an existing memory/, so resolve loosely
    repo = Path(repo_arg or os.environ.get("MNEMOSYNE_REPO") or os.getcwd()).expanduser().resolve()
    res = core.init_repo(repo, args.example)
    print(f"INIT: memory repo ready at {res['repo']}"
          + (f" (wrote mnemosyne.config.json from '{args.example}')" if res["wrote_config"] else ""))
    print("  next: capture a lesson, then `mnemosyne recall`. `git init` to enable shared promotion.")
    return 0


def cmd_config(cfg, repo, args):
    print(json.dumps({"source": cfg.source, **cfg.as_dict()}, indent=2))
    return 0


# ----------------------------------------------------------------------------- selftest


def cmd_selftest(cfg, repo, args):
    return run_selftest()


def run_selftest() -> int:
    import tempfile
    import shutil
    from .config import load_named_example

    cfg = load_named_example("software-eng")
    fails = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            fails.append(name)

    tmp = Path(tempfile.mkdtemp(prefix="mnemosyne-selftest-"))
    try:
        (tmp / "memory").mkdir()
        seed = {"id": "L-0001", "title": "Pin idempotency for new POST", "category": "mistake",
                "memory_type": "episodic", "lesson": "Decide the idempotency contract for new POSTs.",
                "trigger": {"work_types": ["migration"], "endpoint_patterns": ["POST *"],
                            "tags": ["idempotency", "transaction"]},
                "confidence": "high", "status": "active", "review": {"state": "approved"},
                "created": core.today(), "uses": 0}
        core.write_jsonl(core.shared_path(tmp), [seed])

        ranked, _ = core.recall(cfg, tmp, core.build_recall_context(cfg, axes={"work_types": "migration", "tags": "idempotency"}))
        check("recall finds the seeded lesson by tag", [l["id"] for l, _, _ in ranked] == ["L-0001"])
        check("recall reports a source banner", "reflexion memory" in core.banner(tmp))

        res = core.capture(cfg, tmp, {"title": "Always confirm soft-delete semantics",
                                      "lesson": "deleteX usually UPDATEs STATUS; confirm before specifying.",
                                      "category": "convention", "confidence": "medium", "rationale": "names lie",
                                      "trigger": {"tags": "soft-delete"}, "spec": "TCK-9001"})
        check("capture assigns L-0002 to the local tier", res["action"] == "saved" and res["id"] == "L-0002" and res["tier"] == "local")
        local = core.read_jsonl(core.local_path(tmp))
        check("local tier now has 1 lesson", len(local) == 1 and local[0]["review"]["state"] == "local")

        v = core.validate(cfg, tmp)
        check("validate passes (no problems, not stale)", v["ok"])
        check("validate counts 1 shared + 1 local", v["counts"]["shared"] == 1 and v["counts"]["local"] == 1)

        md = (tmp / "memory" / "LESSONS.md")
        check("LESSONS.md generated", md.exists() and "L-0002" in md.read_text(encoding="utf-8"))

        core.promote(cfg, tmp, "L-0002")
        shared = core.read_jsonl(core.shared_path(tmp))
        local = core.read_jsonl(core.local_path(tmp))
        promoted = [l for l in shared if l["id"] == "L-0002"]
        check("promote moves the lesson to shared as proposed", len(promoted) == 1 and promoted[0]["review"]["state"] == "proposed")
        check("promote empties the local tier", len(local) == 0)

        d = core.capture(cfg, tmp, {"title": "Idempotency must be pinned on POST",
                                    "lesson": "Pin idempotency contract.", "category": "mistake",
                                    "confidence": "high", "trigger": {"tags": "idempotency,transaction"}})
        check("near-duplicate reinforces L-0001 instead of adding", d["action"] == "reinforced" and d["dup_id"] == "L-0001")
        allids = [l["id"] for l in core.read_jsonl(core.shared_path(tmp)) + core.read_jsonl(core.local_path(tmp))]
        check("no duplicate record (L-0003) created by the near-dupe", "L-0003" not in allids)
        check("the reinforced lesson's count incremented",
              [l for l in core.read_jsonl(core.shared_path(tmp)) if l["id"] == "L-0001"][0].get("reinforced", 0) >= 1)

        ranked2, _ = core.recall(cfg, tmp, core.build_recall_context(cfg, axes={"components": "NONEXISTENT", "tags": "zzz-nope"}), min_score=0.1)
        check("recall reports no match cleanly", len(ranked2) == 0)

        core.capture(cfg, tmp, {"title": "Sequence cross-service dependencies last",
                                "lesson": "Order phases so cross-service deps land in the final phase.",
                                "category": "process", "confidence": "high",
                                "trigger": {"tags": "sequencing,cross-service"}, "spec": "TCK-9100", "stage": "plan"})
        plan_lesson = [l for l in core.read_jsonl(core.local_path(tmp)) if l["title"].startswith("Sequence cross-service")][0]
        check("capture --stage plan records provenance + applicability",
              plan_lesson["source"]["stage"] == "plan" and "plan" in plan_lesson["trigger"]["stages"])
        rankedp, _ = core.recall(cfg, tmp, core.build_recall_context(cfg, axes={"tags": "sequencing"}, stage="plan"))
        check("recall --stage plan surfaces the planning lesson", plan_lesson["id"] in [l["id"] for l, _, _ in rankedp])
        check("planning lesson's matched reasons include the stage",
              any("stage:plan" in " ".join(why) for l, _, why in rankedp if l["id"] == plan_lesson["id"]))

        gfields = {"title": "Build produced no artifact",
                   "lesson": "The build stage left no build output behind.", "confidence": "medium",
                   "trigger": {"tags": "build"},
                   "reflection_of": "the build artifact was never created by the build stage"}
        guarded = False
        try:
            core.reflect(cfg, tmp, gfields)
        except core.LowValueError:
            guarded = True
        check("reflect refuses a missing-deliverable failure (LowValueError)", guarded)
        rf = core.reflect(cfg, tmp, gfields, force=True)
        check("reflect force overrides the failure guard", rf["action"] == "saved")
        bad, _m = core.is_low_value_failure("the AUDIT row was lost because the AFTER INSERT trigger did not fire")
        check("guard keeps a durable domain failure", not bad)

        core.recall(cfg, tmp, core.build_recall_context(cfg, axes={"tags": "idempotency"}))
        usage = core.read_usage(tmp)
        check("recall records usage in the sidecar", usage.get("L-0001", {}).get("uses", 0) >= 1)
        check("usage lives in a separate sidecar file", (tmp / "memory" / core.USAGE_SIDECAR).exists())

        old_iso = (_dt.date.today() - _dt.timedelta(days=400)).isoformat()
        aged = {"id": "L-0090", "title": "Old noisy lesson nobody recalls", "category": "process",
                "memory_type": "semantic", "lesson": "This one never gets recalled and should age out.",
                "trigger": {"tags": ["obscure-unused-xyz"]}, "confidence": "low", "status": "active",
                "review": {"state": "approved"}, "created": old_iso, "uses": 0, "reinforced": 0}
        sh = core.read_jsonl(core.shared_path(tmp))
        sh.append(aged)
        core.write_jsonl(core.shared_path(tmp), sh)
        dry = core.prune(cfg, tmp, apply=False, cap=999, max_age_days=180)
        check("prune dry-run flags the aged lesson", "L-0090" in dry["candidates"] and not dry["applied"])
        check("prune dry-run does not change status",
              [l for l in core.read_jsonl(core.shared_path(tmp)) if l["id"] == "L-0090"][0]["status"] == "active")
        core.prune(cfg, tmp, apply=True, cap=999, max_age_days=180)
        retired = [l for l in core.read_jsonl(core.shared_path(tmp)) if l["id"] == "L-0090"][0]
        check("prune --apply retires (status=retired, record kept with reason)",
              retired["status"] == "retired" and "retired_reason" in retired)

        capc = core.prune_candidates(core.read_jsonl(core.shared_path(tmp)), core.read_usage(tmp),
                                     cap=1, max_age_days=99999, today_d=_dt.date.today())
        check("cap sweep protects the high-confidence seed L-0001", "L-0001" not in capc)

        h = core.hygiene(cfg, tmp, cap=200, max_age_days=180)
        check("hygiene report returns a summary", "active" in h and h["active"] >= 1)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\nSELFTEST: {'ALL PASS' if not fails else str(len(fails)) + ' FAILURE(S): ' + ', '.join(fails)}")
    return 1 if fails else 0


# ----------------------------------------------------------------------------- entrypoint


NO_REPO_CMDS = {"init", "config", "selftest"}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--repo")
    pre.add_argument("--config")
    known, _ = pre.parse_known_args(argv)
    repo_hint = known.repo or os.environ.get("MNEMOSYNE_REPO") or os.getcwd()

    try:
        cfg = load_config(known.config, Path(repo_hint))
    except ConfigError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    parser = build_parser(cfg)
    args = parser.parse_args(argv)

    try:
        if args.cmd in NO_REPO_CMDS:
            return args.func(cfg, known.repo, args)
        repo = core.resolve_repo(known.repo)
        return args.func(cfg, repo, args)
    except core.EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return getattr(e, "code", 2)
    except BrokenPipeError:
        return 0
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
