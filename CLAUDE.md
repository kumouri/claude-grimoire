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
| `docs/` | Cross-cutting architecture docs + mermaid diagrams (e.g. `docs/grimoire/`). |
| `tests/` | Python `unittest` suite (gated by CI). Run: `python -m unittest discover -s tests -t .`. |
| `mnemosyne/` | Self-contained reflexion-memory engine (package · CLI · MCP server · plugin). Own `README.md`. |
| `morpheus/` | Self-contained session-dreaming/consolidation engine (package · CLI · MCP server · plugin). Own `README.md`. |
| `grimoire/` | Umbrella: unified MCP server + plugin composing mnemosyne + morpheus. Own `README.md`. |

When adding a new artifact, drop it in the matching directory and give it a short README or
header comment explaining what it does and how to install/use it.

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
