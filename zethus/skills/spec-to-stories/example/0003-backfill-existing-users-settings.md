# Backfill existing users to the new per-channel settings shape

**Epic:** Phase 2 — Backfill existing users' settings to the new shape · **Traceability:**
`example/spec.md#phases`, phase 2 · **Sizing notes:** one migration, verified per-user

> This is a technical enabler with no direct end-user-visible behaviour when it's correct — it
> skips the user story statement below; see Context for who benefits and how.

## User story

Not applicable — see the note above.

## Context

Once the per-channel API from story 0002 exists, every existing user's old single boolean has to
become a per-channel map with no visible change in what they receive. Whoever already relies on the
current notification behaviour is the beneficiary: this story is what keeps that behaviour intact
across the deploy.

## Acceptance criteria

- [ ] Given a user whose old setting was `true`, when the backfill runs, then their new setting is
      `{"email": true, "push": true}`.
- [ ] Given a user whose old setting was `false`, when the backfill runs, then their new setting is
      `{"email": false, "push": false}`.
- [ ] Given the backfill has run once, when it's run again, then no user's settings change
      (idempotent).

## Out of scope

- **Any new default that differs from the user's prior setting** — the spec requires no visible
  change on deploy day.

## Dependencies

- **Depends on story 0002** (the per-channel API and storage shape must exist before there is
  anything to backfill into).

## INVEST self-check

| Criterion | Pass / Flag | Note |
|---|---|---|
| Independent | Flag | Cannot run, or even be meaningfully tested, until story 0002's storage shape exists — named under Dependencies rather than hidden. Splitting further wouldn't remove this dependency, only relabel it, so it ships flagged. |
| Negotiable | Pass | States the required outcome (no visible change), not the migration mechanism. |
| Valuable | Pass | Value is stated in Context: it's what protects existing users from a silent behaviour change. |
| Estimable | Pass | One migration, bounded by the two old values. |
| Small | Pass | One migration script and its verification. |
| Testable | Pass | Each criterion is a concrete before/after a tester can check per user. |

**Flagged:** Independent — depends on story 0002 shipping first; see the note above and
*Dependencies*.
