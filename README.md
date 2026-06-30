# 🔮 claude-grimoire

[![made by kumouri](https://img.shields.io/badge/made%20by-kumouri-8e00ff?style=flat-square)](https://github.com/kumouri)
[![license: MIT](https://img.shields.io/badge/license-MIT-00ff0f?style=flat-square)](LICENSE)
[![Git Flow](https://img.shields.io/badge/workflow-git--flow-8e00ff?style=flat-square)](#-git-flow)

> A grimoire of Claude Code creations — the skills, hooks, slash commands, and agents I
> conjure up that don't belong to any other project.

This is a curated showcase of the [Claude Code](https://claude.com/claude-code) extensions I
build for myself: reusable **skills**, automation **hooks**, custom **slash commands**, and
purpose-built **subagents**. Each one is a small, self-contained artifact — collected here so
they're easy to share, reuse, and point at from my portfolio.

## 📜 Structure

| Directory | What lives here |
| --- | --- |
| [`skills/`](skills/) | Custom Skills — `SKILL.md` packages and their supporting files. |
| [`hooks/`](hooks/) | Claude Code hooks — `settings.json` snippets and their scripts. |
| [`commands/`](commands/) | Custom slash commands. |
| [`agents/`](agents/) | Custom subagent definitions. |

Each directory has its own README describing conventions and what belongs there.

## 🌿 Git Flow

This repo follows the [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/)
branching model:

- **`main`** — stable, tagged releases.
- **`develop`** — integration branch; day-to-day work lands here first.
- **`feature/*`**, **`bugfix/*`**, **`release/*`**, **`hotfix/*`**, **`support/*`** — short-lived working branches.

Release tags are prefixed with `v` (e.g. `v1.0.0`).

## 🪪 License

[MIT](LICENSE) © 2026 Ceryce Armstrong

---

<sub>Built with care by **Ceryce** ([@kumouri](https://github.com/kumouri)) · brand purple `#8e00ff`</sub>
