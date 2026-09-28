# Accept a per-channel settings payload on the notification settings endpoint

**Epic:** Phase 1 — Per-channel toggle in the settings model and API · **Traceability:**
`example/spec.md#phases`, phase 1 · **Sizing notes:** one endpoint, widened payload, no migration

> This is a technical enabler with no direct end-user-visible behaviour of its own — it's what
> story 0001 is built on. It skips the user story statement below; see Context for who benefits.

## User story

Not applicable — see the note above.

## Context

Story 0001 needs an API that accepts and returns a per-channel map instead of one boolean. This
story is that API change alone, so it can be built and tested before any client (or 0001's own
acceptance tests) depends on it. Whoever calls this endpoint — today's settings UI, or a future one
— is the beneficiary.

## Acceptance criteria

- [ ] Given a PATCH request with `{"email": false, "push": true}`, when it's sent to the settings
      endpoint, then the stored settings reflect exactly that map.
- [ ] Given an old client that still sends `{"notifications_enabled": false}`, when it's sent, then
      the endpoint accepts it and maps it to `{"email": false, "push": false}` (backward compatible).
- [ ] Given a GET on the settings endpoint, when a user has a per-channel map stored, then the
      response includes both channels.

## Out of scope

- **The backfill of existing users' stored settings** — that's story 0003, Phase 2.

## Dependencies

- None known — this can be built first, ahead of 0001's UI-facing behaviour.

## INVEST self-check

| Criterion | Pass / Flag | Note |
|---|---|---|
| Independent | Pass | Ships and is tested on its own; nothing else in this batch has to land first. |
| Negotiable | Pass | Names the contract (payload shape, backward compatibility), not the implementation. |
| Valuable | Pass | Value is stated in Context: it's what makes 0001 buildable at all. |
| Estimable | Pass | One endpoint, one payload shape change. |
| Small | Pass | Fits comfortably in one PR. |
| Testable | Pass | Each criterion names a request/response pair a tester can send and check. |

**Flagged:** none.
