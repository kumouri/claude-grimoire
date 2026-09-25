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

## 🎼 Also featured — Amphion

**[Amphion](amphion/)** — a spec-to-PR implementation pipeline as seven composable skills: load
the decided context, handle what the spec didn't cover, recover from a crashed delegate, add CI,
write the PR, correct the docs the diff made wrong, and log the friction. Pure markdown,
config-driven, no runtime. Named for the twin who built Thebes' walls by playing his lyre while the
stones set themselves. Pipeline + diagram: [amphion/docs/pipeline.md](amphion/docs/pipeline.md).

## 📜 Structure

| Directory | What lives here |
| --- | --- |
| [`grimoire/`](grimoire/) | The umbrella: unified MCP server + plugin composing both engines. |
| [`mnemosyne/`](mnemosyne/) | Reflexion-lessons memory engine (package · CLI · MCP server · plugin). |
| [`morpheus/`](morpheus/) | Session dreaming / consolidation engine (package · CLI · MCP server · plugin). |
| [`amphion/`](amphion/) | Spec-to-PR implementation pipeline — seven composable skills, one plugin. |
| [`skills/`](skills/) | Standalone custom Skills not tied to an engine or package. |
| [`hooks/`](hooks/) | Standalone Claude Code hooks. |
| [`commands/`](commands/) | Standalone custom slash commands. |
| [`zethus/`](zethus/) | GitHub Copilot process kit — enforcing agent, ten skills, templates, scripts. |
| [`agents/`](agents/) | Custom subagent definitions. |
| [`docs/`](docs/) | Cross-cutting architecture docs and diagrams (e.g. `docs/grimoire/`). |
| [`scripts/`](scripts/) | Repo-maintenance scripts, including the CI identifier guard. |
| [`tests/`](tests/) | Python `unittest` suite covering the engines. |

Each directory has its own README describing conventions and what belongs there.

## 🪨 For GitHub Copilot — Zethus

**[Zethus](zethus/)** — my development process, packaged for GitHub Copilot and installable into
any repository's `.github/`, or once per user into `~/.copilot/` so it follows you into every repo
without touching any of them. One custom agent walks every change through research → spec →
sign-off → phased implementation (Phase 0 changes no behaviour) → tests → local gates → a PR with
evidence, and refuses to skip a stage; ten standalone skills, spec/ADR/PR templates, and stdlib
scripts (`run-local-gates`, `new-adr`, `new-spec`, `docs-pointer-check`) carry the procedures.

## 🧪 CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs two jobs on every PR into
`develop` or `main`:

- **Validate artifacts** — markdownlint, JSON/YAML well-formedness, shellcheck.
- **Python tests** — the identifier guard (below), the `unittest` suite, and an
  MCP-server smoke import.

Run the suite locally with:

```bash
python -m unittest discover -s tests -t .
```

### 🔒 The identifier guard

**This repository is public — every byte committed here is published.**
[`scripts/check_identifiers.py`](scripts/check_identifiers.py) is a blocking CI step that
scans every tracked text file for machine-specific identifiers: Windows user-profile paths
(`C:\Users\<name>\…`), other drive-absolute paths, POSIX home directories (`/home/<name>/`,
`/Users/<name>/`), WSL drive mounts, this project's GitHub URL under the wrong org, and
email addresses outside a small justified allowlist.

Run it and its tests locally:

```bash
python scripts/check_identifiers.py
python -m unittest discover -s scripts -p "test_check_identifiers.py" -t scripts
```

The guard matches by **shape, not by a list of secret strings** — deliberately. A denylist of
the private terms to forbid would have to *contain* those terms, and committing it to a public
repo would publish exactly what it was written to protect. Documented placeholders
(`<user>`, `alice`, `%USERNAME%`, CI's `/home/runner`, …) are accepted so docs can still show
the shape of a path. Ceryce's name, her `@kumouri` handle and her contact address in package
author metadata are **deliberate attribution** and stay: the rule is *scrub the machine, keep
the author*.

> [!IMPORTANT]
> **What this guard cannot see.** It has no knowledge of any private denylist — the real
> names of clients, businesses and workspace trees live only in a private scrub workspace
> outside this repo. A green run means "no identifier of a *known shape* was found", **not**
> "this repo is free of private information". It also scans only the current working tree, so
> it can never notice something already committed and later deleted. The pre-release gate
> remains a private `pii_sweep.py --repo … --history` run against that denylist; this check is
> a cheap always-on **subset** of it, not a replacement. Do not read a green tick here as
> clearance to publish.

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
