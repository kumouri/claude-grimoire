# 🔮 claude-grimoire

[![made by kumouri](https://img.shields.io/badge/made%20by-kumouri-8e00ff?style=flat-square)](https://github.com/kumouri)
[![license: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-00ff0f?style=flat-square)](LICENSE)
[![Git Flow](https://img.shields.io/badge/workflow-git--flow-8e00ff?style=flat-square)](#-git-flow)

> A grimoire of Claude Code creations — the skills, hooks, slash commands, and agents I
> conjure up that don't belong to any other project.

This is a curated showcase of the [Claude Code](https://claude.com/claude-code) extensions I
build for myself: reusable **skills**, automation **hooks**, custom **slash commands**, and
purpose-built **subagents**. Each one is a small, self-contained artifact — collected here so
they're easy to share, reuse, and point at from my portfolio.

## ✨ Featured — Grimoire

**📖 [Grimoire](grimoire/)** — the book that holds both. A thin umbrella (one MCP server + one
plugin) uniting two memory engines:

- 🧠 **[Mnemosyne](mnemosyne/)** — reflexion *lessons* memory (recall / reflect / promote);
  git-backed, PR-governed, deliberate.
- 🌙 **[Morpheus](morpheus/)** — automatic session *dreaming* / consolidation (dream / wake);
  background, per-project, crash-safe.

Each engine ships four ways — **package · CLI · MCP server · plugin** — and stands alone; Grimoire
composes both and exposes all nine tools on one server. Architecture + diagrams:
[docs/grimoire/architecture.md](docs/grimoire/architecture.md).

## 📜 Structure

| Directory | What lives here |
| --- | --- |
| [`grimoire/`](grimoire/) | The umbrella: unified MCP server + plugin composing both engines. |
| [`mnemosyne/`](mnemosyne/) | Reflexion-lessons memory engine (package · CLI · MCP server · plugin). |
| [`morpheus/`](morpheus/) | Session dreaming / consolidation engine (package · CLI · MCP server · plugin). |
| [`skills/`](skills/) | Standalone custom Skills not tied to an engine. |
| [`hooks/`](hooks/) | Standalone Claude Code hooks. |
| [`commands/`](commands/) | Standalone custom slash commands. |
| [`agents/`](agents/) | Custom subagent definitions. |
| [`docs/`](docs/) | Cross-cutting architecture docs and diagrams (e.g. `docs/grimoire/`). |

Each directory has its own README describing conventions and what belongs there.

## 🌿 Git Flow

This repo follows the [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/)
branching model:

- **`main`** — stable, tagged releases.
- **`develop`** — integration branch; day-to-day work lands here first.
- **`feature/*`**, **`bugfix/*`**, **`release/*`**, **`hotfix/*`**, **`support/*`** — short-lived working branches.

Release tags are prefixed with `v` (e.g. `v1.0.0`).

## 🪪 License

[Apache-2.0](LICENSE) © 2026 Ceryce Armstrong

---

<sub>Built with care by **Ceryce** ([@kumouri](https://github.com/kumouri)) · brand purple `#8e00ff`</sub>
