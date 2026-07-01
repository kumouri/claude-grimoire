# Grimoire 📖

**The book that holds both.** Grimoire is a thin umbrella that unites two independent Claude Code
memory engines under **one MCP server** and **one plugin**:

- 🧠 **[mnemosyne](../mnemosyne/)** — reflexion *lessons* memory (recall / capture / reflect /
  promote / prune / hygiene). Deliberate, git-backed, PR-governed.
- 🌙 **[morpheus](../morpheus/)** — automatic session *dreaming* / consolidation (dream / wake /
  dreams). Background, per-project.

Grimoire itself adds no new memory model — it composes the two. Design + diagrams:
[`docs/grimoire/architecture.md`](../docs/grimoire/architecture.md).

## What you get

- **One MCP server** (`FastMCP("grimoire")`, `python -m grimoire.mcp_server`) exposing **all nine
  tools** — the six mnemosyne tools + morpheus's `dream` / `wake` / `dreams`.
- **One plugin** with a single lifecycle-hook dispatcher that runs both engines' concerns without
  double-firing: SessionStart (memory sync + dream-wake digest), UserPromptSubmit (recall
  injection), PreCompact / SessionEnd (dream), SessionEnd (reflect nudge).

## Install

Grimoire is the **recommended all-in-one**. It needs both engine packages importable:

```bash
pip install "grimoire-mcp"          # pulls mnemosyne-reflexion + morpheus-dreaming + mcp
```

Then install the **grimoire plugin** (its `.mcp.json` auto-registers the server and its
`hooks.json` wires the unified dispatcher), or register the server manually:

```bash
claude mcp add grimoire -e MNEMOSYNE_REPO=/path/to/memory-repo -- python -m grimoire.mcp_server
```

> **Pick one plugin.** Install *either* the Grimoire plugin (both engines) *or* a single engine's
> standalone plugin (`mnemosyne/plugin`, `morpheus/plugin`) — never a standalone *alongside*
> Grimoire, or their hooks double-fire.

## The two stores (by design)

Grimoire keeps the engines' stores separate ("two stores, one roof"):

| Engine | Store | Nature |
|---|---|---|
| mnemosyne | `<repo>/memory/*.jsonl` (git-backed) | curated lessons, PR-promoted |
| morpheus | `~/.claude/projects/<slug>/memory/` | auto-consolidated per-project facts |

See [`docs/grimoire/architecture.md`](../docs/grimoire/architecture.md) for the composition and
hook-dispatch diagrams.
