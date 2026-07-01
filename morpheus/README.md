# Morpheus 🌙

Automatic session **memory consolidation** ("dreaming") for Claude Code. Before context is
compacted and when a session ends, a background "dreamer" reflects over the transcript and
distils the durable signal into your long-term memory — no manual note-taking. Named for the
Greek god of dreams; the dreaming counterpart to [mnemosyne](../mnemosyne/) (memory).

One stdlib-only engine, shipped four ways: a **package**, a **CLI**, an **MCP server**, and a
Claude Code **plugin**. Design + diagrams: [`docs/architecture.md`](docs/architecture.md).

## What it does

- **Dreams** at `PreCompact` and `SessionEnd`: consolidates the session's durable facts into
  `memory/<type>-<slug>.md` + `MEMORY.md` under `~/.claude/projects/<slug>/memory/`, merging and
  deduping, and logs speculative *associations* into `memory/dreams/`.
- **Wakes** at `SessionStart`: injects a recall digest so a new session starts already remembering.
- On demand via the `dream` MCP tool, the `morpheus dream` CLI, or the `/dream` command.

Three engines by token budget: `headless` (default, background `claude -p`), `hybrid`
(deterministic prefilter + a small model), `deterministic` (no LLM).

## Install

**Plugin (recommended):** install the Morpheus (or Grimoire) plugin — its `hooks.json` wires the
lifecycle hooks and its `.mcp.json` auto-registers the MCP server. The plugin still needs the
Python package importable, so `pip install "morpheus-dreaming[mcp]"` first (Claude Code doesn't
auto-install server dependencies).

**Package / CLI:**

```bash
pip install "morpheus-dreaming[mcp]"     # [mcp] extra only needed for the MCP server
morpheus install                          # merge hooks into ~/.claude/settings.json (idempotent)
```

**MCP server:** `claude mcp add morpheus -- python -m morpheus.mcp_server` (tools: `dream`,
`wake`, `dreams`).

**Standalone hooks (no plugin):** `morpheus install` (`--project DIR` / `--uninstall` / `--dry-run`).

> Don't install the standalone Morpheus plugin *and* the Grimoire plugin at once — their hooks
> would both fire. Pick one.

## CLI

```
morpheus dream --cwd DIR --transcript FILE [--session ID] [--mode MODE]
morpheus wake  --cwd DIR [--light]
morpheus dreams --cwd DIR [-n N]
morpheus worker [--once|--watch]
morpheus reconcile [--no-drain]
morpheus install [--project DIR] [--uninstall] [--dry-run]
morpheus selftest
```

## Configure

`~/.claude/morpheus/config.json` (seeded from `data/config.example.json`): `mode`, `model`,
`min_delta_records`, `max_new_memories`, `dream_timeout_sec`, `redact_secrets`,
`auto_commit_memory`, `digest_dreams`, `enabled`. See [`docs/usage.md`](docs/usage.md) for the
full table and troubleshooting.

## Tests

Repo-root suite: `python -m unittest discover -s tests -t .` (plus `morpheus selftest`).
