---
name: log-friction
description: Log a friction point or pain point encountered during a workflow to the project's configured friction log — a markdown file, a Notion page, or GitHub issues. Use when something is harder than it should be, takes unexpected effort, has no clear path, or produced a workaround worth remembering.
---

# Log friction

You are recording a friction point in the project's friction log. The goal is a structured record
of workflow problems, so they can be addressed systematically rather than re-encountered and
re-solved from scratch every time.

Friction is worth logging when it cost real time, had no clear path, or forced a workaround — not
for every small annoyance, and not as a substitute for fixing something you could fix right now.

## Step 1: Find the sink

Read `frictionLog` from `.claude/amphion.config.json`:

| Key | Meaning |
|---|---|
| `frictionLog.sink` | `markdown` (default), `notion`, or `githubIssues`. |
| `frictionLog.markdown.path` | Repo-relative file to append entries to. Default `docs/friction-log.md`. |
| `frictionLog.notion.pageId` | Target Notion page/database id. Required for the `notion` sink. |
| `frictionLog.githubIssues.repo` / `.labels` | Target repo (`owner/name`) and labels for the `githubIssues` sink. |
| `frictionLog.categories[]` | The project's category vocabulary — each entry has a `name` and an `includes` description. |

**If there is no config or no sink is set**, default to the `markdown` sink at
`docs/friction-log.md`. That needs no credentials, no external service, and no setup — a friction
log nobody can write to is a friction log nobody keeps.

**If the configured sink is unreachable** (Notion not connected, `gh` not authenticated), do not
lose the entry: write it to the markdown fallback, tell the user the configured sink failed, and
let them decide whether to re-file it.

## Step 2: Gather context

Ask only for what isn't already clear from the conversation. Confirm what you inferred rather than
asking from scratch.

1. **What were you trying to do?** — the goal, not the problem. One sentence.
2. **What was the friction?** — what was harder than expected, broke, had no clear path, or
   required a workaround.
3. **Workaround** — how you got past it, or `none — still blocking`.
4. **Severity** — ask the user to pick:
   - `blocking` — could not proceed without resolving it
   - `significant` — got through it, but it cost meaningful time or effort
   - `minor` — small annoyance, low impact

## Step 3: Assign a category

Use `frictionLog.categories[]` from the config. If the project defines none, use this default set —
it partitions *where in the delivery pipeline* the friction happened, which is what makes the log
actionable later:

| Category | What belongs here |
|---|---|
| **Environment & Tooling** | Local setup, toolchain, editor, shell, machine-specific breakage |
| **Build & CI** | Build system, pipelines, flaky or slow gates, release plumbing |
| **Code & Architecture** | Seams that fight the change, missing abstractions, load-bearing surprises |
| **Testing & Verification** | Hard-to-write tests, missing fixtures, unverifiable behaviour |
| **Docs & Knowledge** | Missing, stale, or unfindable information |
| **Process & Coordination** | Handoffs, review latency, orchestration and agent-delegation failures |
| **External Services & Dependencies** | Third-party APIs, vendor limits, upstream bugs |

If nothing fits, propose a new category and confirm it with the user before using it — then offer
to add it to `frictionLog.categories[]` so it exists next time.

## Step 4: Write the entry

Every entry, whichever sink, carries the same fields:

- **Date** — today's date, absolute (`2026-08-28`, never "today").
- **Project** — the current project or repo name.
- **Category** — from Step 3.
- **Task / goal** — what was being attempted.
- **Friction** — a clear description of the problem.
- **Workaround** — what got you past it, or `none — still blocking`.
- **Severity** — blocking / significant / minor.
- **Notes** — anything else worth preserving: tool names, verbatim error messages, links, related
  decisions.

By sink:

- **`markdown`** — append one `##`-headed entry to `frictionLog.markdown.path`, newest last.
  Create the file with a short header if it doesn't exist.
- **`notion`** — create the entry under `frictionLog.notion.pageId` using the available Notion MCP
  tools, mapping the fields above to that page's properties.
- **`githubIssues`** — open an issue on `frictionLog.githubIssues.repo` with the fields as the
  body and `frictionLog.githubIssues.labels` applied.

## Step 5: Confirm

Show the user the final entry and where it landed. Give them a chance to correct it before you
close out.

## Anti-patterns

- **Don't log instead of fixing.** If it's a five-minute fix in the repo you're already in, fix it.
- **Don't log the same friction twice** — check the existing log first and add to the existing
  entry if it recurred.
- **Don't paraphrase the error.** Paste it verbatim; the exact string is what makes the entry
  searchable later.
- **Don't block the user's work to file this.** Capture, confirm, move on.
