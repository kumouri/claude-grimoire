---
name: load-context
description: Read a project's canonical planning, decision, and convention documents in the right order before starting spec-driven implementation work. Use at the start of any phase-N branch session, whenever you need to refresh context on what was decided, or when picking up spec-driven work cold. Optionally takes a phase number or component name and also reads that phase's briefing plus the specs it references. Reads the document set from .claude/amphion.config.json; discovers and confirms it when no config exists.
---

# Load implementation context

The first stage of the [Amphion](../../../README.md) pipeline. This skill loads a project's
canonical planning documents **in a deliberate order**, plus any phase-specific specs they point
at.

The order is the point. Knowing the **resolved decisions** before reading the specs prevents
re-deciding settled questions; knowing the **voice/convention rules** before reading per-unit specs
makes the specs' examples land properly. Reading the same files in a random order costs you the
same tokens and gives you less.

Invoke this at the start (or resumption) of spec-driven implementation work. For a one-off lookup,
just Read the specific file — don't load the whole stack.

## Step 0: Read the config

Read `.claude/amphion.config.json` from the repo root (see
[`amphion.config.example.json`](../../../amphion.config.example.json)). The keys this skill uses:

| Key | Meaning |
|---|---|
| `context.root` | Base directory the paths below are relative to. Defaults to the repo root. |
| `context.core[]` | The ordered core document set. Each entry: `role`, `path`, `note`. **Order in this array is the read order.** |
| `context.phase.briefing` | Path template for a phase briefing; `{phase}` is substituted. |
| `context.phase.specs[]` | Globs for the per-unit spec documents. |
| `context.phase.supporting[]` | Anything else a briefing habitually references. |
| `vocabulary.spec` | What this project calls a spec — `spec`, `audit`, `brief`, `ticket`. Use their word when you report back. |

**If there is no config**, do not guess silently. Glob for the usual homes of planning material
(`.claude/*.md`, `docs/*.md`, `CLAUDE.md`, `README.md`), propose an ordered core set to the user in
one message, and offer to write it into `.claude/amphion.config.json` so the next session doesn't
have to re-derive it. Then proceed with the confirmed set.

## Step 1: Read the core set (always)

Read every `context.core[]` entry **in array order**. A typical set, and why each role sits where
it does:

1. **`plan`** — the phased execution order, the file-modification map, and the pointers to
   per-unit specs. This tells you what the other documents are *for*.
2. **`decisions`** — the questions already resolved. Read before any spec, so you implement
   decisions rather than reopening them.
3. **`voice`** *(optional)* — tone, register, and naming rules for user-facing copy. Skip the role
   entirely on projects with no copy surface.
4. **`conventions`** — `CLAUDE.md` or equivalent: repo conventions, things to avoid, and the
   project's "when you hit something unexpected" table.

A missing optional document is not an error — note it and continue. A missing `plan` or
`decisions` document **is** worth surfacing, because the rest of the pipeline assumes decisions
exist somewhere.

If several documents match a role and they carry dates in their names, prefer the newest.

## Step 2: Read the phase-specific set (when a phase or component was named)

If the user gave a phase number, a branch name, or a component they're touching:

1. **The briefing** — substitute into `context.phase.briefing` (e.g. `{phase}` → `3`). If the
   template resolves to nothing, fall back to the un-numbered form for phase 1.
2. **The specs that briefing references** — resolve them against `context.phase.specs[]`. Read
   only the ones the briefing actually cites; the glob is a search space, not a reading list.
3. **Supporting documents** the briefing names — resolve against `context.phase.supporting[]`.

If the user named a **component** rather than a phase ("I'm working on the checkout flow"), match
it against `context.phase.specs[]` directly and read the matching spec plus the core set.

## Step 3: Confirm what you loaded

Give the user one tight paragraph:

- **Phase / scope** you're set up for (or "general context" if none was given).
- **Specs in scope** — by name.
- **Open questions** you spotted while reading: items still marked `[TBD]`, spec items marked
  deferred, and any conflict between a briefing and the spec it points at.
- **Decisions that bear on this phase** — cite them by their identifier in the decisions document.

Then ask whether to proceed with implementation or discuss anything first.

## When NOT to use this skill

- **Quick lookups** — one fact from one document: Read that document.
- **Already-loaded context** — if the files are already in this conversation, don't re-read them.
- **Work outside the plan** — a `fix/…` or `feat/…` branch unrelated to the phased work rarely
  needs the full stack. Read the conventions document, plus the voice guide if the change touches
  user-facing copy.
- **Projects with no planning documents** — there is nothing for this skill to order. Say so
  rather than manufacturing a document set.

## Next in the pipeline

Context loaded → implement. When implementation hits something the plan doesn't address, use
[`flag-or-fix`](../flag-or-fix/SKILL.md).
