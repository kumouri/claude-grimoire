# CLAUDE.md — claude-grimoire

## What this repo is

A personal collection ("grimoire") of standalone **Claude Code** artifacts — skills, hooks,
slash commands, and subagents — that don't belong to any other project. It exists to showcase
this work on Ceryce's portfolio, so each artifact should be self-contained, documented, and
presentable.

## Where things go

| Directory | Contents |
| --- | --- |
| `skills/` | One folder per skill, each containing a `SKILL.md` plus any supporting files. |
| `hooks/` | One folder per hook: the `settings.json` snippet and the script(s) it invokes. |
| `commands/` | Custom slash command files. |
| `agents/` | Custom subagent definition files. |
| `zethus/` | GitHub Copilot process kit: one enforcing agent, ten skills, templates, stdlib scripts, installer. Own `README.md`. |
| `docs/` | Cross-cutting architecture docs + mermaid diagrams (e.g. `docs/grimoire/`). |
| `tests/` | Python `unittest` suite (gated by CI). Run: `python -m unittest discover -s tests -t .`. |
| `scripts/` | Repo-maintenance scripts + their tests (e.g. the CI identifier guard). |
| `mnemosyne/` | Self-contained reflexion-memory engine (package · CLI · MCP server · plugin). Own `README.md`. |
| `morpheus/` | Self-contained session-dreaming/consolidation engine (package · CLI · MCP server · plugin). Own `README.md`. |
| `grimoire/` | Umbrella: unified MCP server + plugin composing mnemosyne + morpheus. Own `README.md`. |
| `amphion/` | Spec-to-PR implementation pipeline: seven skills + one plugin, config-driven, no runtime. Own `README.md`. |

When adding a new artifact, drop it in the matching directory and give it a short README or
header comment explaining what it does and how to install/use it.

`zethus/` targets **GitHub Copilot**, not Claude Code — it installs into a consuming repo's `.github/`.
Keep it org-neutral and its scripts stdlib-only; maintenance rules are in
[`zethus/README.md`](zethus/README.md#maintaining-this-kit), coverage in `tests/test_zethus.py`.

## Featured — Grimoire (Mnemosyne + Morpheus)

`grimoire/` is the umbrella: one MCP server (`grimoire.mcp_server`, all ten tools) and one plugin
(a single `grimoire_hook.py` dispatcher) composing two independent engines — **mnemosyne** (memory)
and **morpheus** (dreams). Each engine also ships standalone four ways (package · CLI · MCP server ·
plugin). Design: [`docs/grimoire/architecture.md`](docs/grimoire/architecture.md).

`morpheus/` is automatic session **memory consolidation**: `PreCompact`/`SessionEnd` hooks enqueue a
durable job, a detached worker reflects over the transcript delta via one of three engines
(`headless`/`hybrid`/`deterministic`), writes durable facts into the per-project two-tier store
(`memory/<type>-<slug>.md` + `MEMORY.md`) plus a `memory/dreams/` log; `SessionStart` injects a
recall digest. Pure Python 3 stdlib. Install: `morpheus install` or the plugin. Design:
[`morpheus/docs/architecture.md`](morpheus/docs/architecture.md).

When extending morpheus, keep `dispatch.py` non-blocking and error-swallowing, preserve the triple
recursion guard (`--bare` + `CLAUDE_MORPHEUS` + `CLAUDE_CODE_CHILD_SESSION`), and keep all three
engines emitting the same `DreamResult` contract. When extending grimoire, keep it a thin composer —
new capability belongs in an engine, surfaced through the umbrella. Add/adjust tests in `tests/`.

## Featured — Amphion

`amphion/` is a spec-to-PR implementation pipeline shipped as seven composable skills under one
plugin (`amphion/plugin/`): `load-context` → implement (`flag-or-fix` / `resume-interrupted-phase`)
→ `initialize-ci` → `pr-description` → `sync-claude-md` → `log-friction`. Pure markdown, no
runtime. Every project-specific fact — document set and read order, ledger path, gate commands,
mandated checks, integration branch, friction sink, doc-to-code map — lives in the consuming
project's `.claude/amphion.config.json` (example: `amphion/amphion.config.example.json`). Pipeline:
[`amphion/docs/pipeline.md`](amphion/docs/pipeline.md).

When extending amphion, keep the skills **config-driven and org-neutral** — no client names, no
private paths, no hardcoded document titles; a new project-specific fact becomes a config key, not
a literal. Keep the resolution order (config → repo evidence → ask the user; never guess silently).
**Do not widen `sync-claude-md`** — it may only rewrite in place, never append, and only for a doc
whose described code changed in the same diff; the rationale is in the skill and must stay there.

## Featured artifact — Mnemosyne

`mnemosyne/` is a generic, git-backed **reflexion memory** for agent pipelines: recall durable
lessons into new work, reflect real failures into new lessons, and govern promotion of local
lessons to a shared, PR-reviewed tier. The engine is stdlib-only Python and **config-driven** —
recall axes, stages, and vocabulary live in `mnemosyne.config.json`, so the scorer is
domain-agnostic. It ships three ways over one engine: a PyPI package/CLI (`src/mnemosyne/`,
console script `mnemosyne`), a Claude Code plugin (`mnemosyne/plugin/`), and an MCP server
(`src/mnemosyne/mcp_server.py`). Design: [`mnemosyne/docs/design.md`](mnemosyne/docs/design.md).

Beyond its own local+shared tiers, a repo can **federate** with additional shared stores (broader
`team`/`enterprise` tiers) declared in `config.stores` — each a separate memory repo addressed by a
git URL (auto-cloned into `$MNEMOSYNE_CACHE`) or a path, with a distinct id prefix so federated ids
never collide. `recall` reads the union best-effort (an unreachable store is skipped, never fatal);
`promote --to <tier>` / `export` copies chosen local lessons up to a store, and `sync` pulls stores
and retires a local original once its exported copy is approved upstream. Federation lives in
`src/mnemosyne/stores.py`; keep clone/pull best-effort (never fail a recall) and keep prefixes
distinct.

When extending it, keep the engine dependency-free (the `mcp` package is an optional extra),
drive new recall dimensions through config axes rather than hardcoding them, and keep
`mnemosyne selftest` green (it's wired into the CI `tests/` suite).

## This repo is public — the identifier guard

Every byte committed here is published. `scripts/check_identifiers.py` is a **blocking** CI
step (in the `Python tests` job) that rejects machine-specific identifiers in tracked files:
Windows user-profile paths, other drive-absolute paths, POSIX home directories, WSL drive
mounts, this project's GitHub URL under an org other than `kumouri`, and email addresses
outside a small justified allowlist.

```bash
python scripts/check_identifiers.py
python -m unittest discover -s scripts -p "test_check_identifiers.py" -t scripts
```

Rules for extending it:

- **Match by shape, never by secret string.** A denylist of the private terms would have to
  contain them, and committing it here would publish exactly what it protects. Before adding
  any literal, ask: *would I be comfortable seeing this on the repo's GitHub page?*
- **Use the sanctioned placeholders** (`<user>`, `alice`, `%USERNAME%`, `/home/runner`, …) when
  docs need to show the shape of a path; add new ones to `PLACEHOLDER_NAMES`, documented.
- **Keep the author.** Ceryce's name, her `@kumouri` handle and her contact address in package
  author metadata are deliberate attribution — never "fix" them. The rule is *scrub the
  machine, keep the author*. Allowlist entries need a comment saying why they are safe.
- **Keep it green.** A check that lands red is a check someone disables.

**What it cannot see:** it has no knowledge of any private denylist, and it scans only the
working tree, never history. A green run means "no identifier of a *known shape* was found" —
not "safe to publish". The pre-release gate is still a private `pii_sweep.py --repo … --history`
run against that denylist; this is a cheap always-on subset of it.

## Branching — Git Flow

- `main` — stable, tagged releases only.
- `develop` — integration branch; default branch, PRs target here.
- `feature/*`, `bugfix/*`, `release/*`, `hotfix/*`, `support/*` — short-lived branches.
- Release tags are prefixed with `v`.

Use `git flow feature start <name>` / `git flow feature finish <name>` for routine work.

## Conventions

- **Merge PRs with merge commits** (`gh pr merge --merge`) — never squash or rebase.
- **Never merge a PR with red or pending CI.**
- Markdown is the canonical source for any document deliverable.
