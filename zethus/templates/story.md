# Title as user value, not as a task

**Epic:** which epic this belongs to, or "—" if the spec has no phases · **Traceability:** the
spec file and section this came from, e.g. `docs/specs/some-spec.md#phases` · **Sizing notes:**
a rough size signal if one is warranted (e.g. "touches one module, no migration") — never an
invented story point

> Delete this note once filled in. A story with no natural "As a … I want … so that …" — a
> technical enabler with no direct user-facing behaviour — skips the user story statement below,
> but still says who benefits and how in Context. Never force the phrasing onto something it
> doesn't fit.

## User story

As a `<persona>`, I want `<capability>`, so that `<benefit>`.

## Context

Two to four sentences a human needs to understand why this exists and what changes once it ships.
No architecture, no implementation plan — that's the spec's job, cited below.

## Acceptance criteria

Given/When/Then, or a checklist — either way, something a tester can verify without asking the
author what "done" means.

- [ ] Given `<state>`, when `<action>`, then `<observable outcome>`.

## Out of scope

- **…** — because …

## Dependencies

- Depends on / blocks: `<other story or system>` — or "None known."

## INVEST self-check

| Criterion | Pass / Flag | Note |
|---|---|---|
| Independent | | |
| Negotiable | | |
| Valuable | | |
| Estimable | | |
| Small | | |
| Testable | | |

**Flagged:** none — or name the criterion, why it fails, and whether the story was split instead
of shipped as-is. See [`../docs/jira-skills.md`](../docs/jira-skills.md) for what each check means.
