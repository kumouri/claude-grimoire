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

When adding a new artifact, drop it in the matching directory and give it a short README or
header comment explaining what it does and how to install/use it.

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
