# Let a user turn off email notifications while keeping push on

**Epic:** Phase 1 — Per-channel toggle in the settings model and API · **Traceability:**
`example/spec.md#phases`, phase 1 · **Sizing notes:** touches one model and one endpoint, no
migration

## User story

As a user who wants fewer emails, I want to turn off email notifications without also losing push
notifications, so that I can quiet one channel without going silent everywhere.

## Context

Today, notification settings are a single on/off switch, so turning off email also turns off push.
This story replaces that switch with an independent toggle per channel, for email and push only.

## Acceptance criteria

- [ ] Given a user with both channels on, when they turn off email only, then push notifications
      keep arriving and email ones stop.
- [ ] Given a user with both channels on, when they turn off push only, then email keeps arriving
      and push stops.
- [ ] Given a user with no channels on, when a notification is triggered, then neither channel
      fires.

## Out of scope

- **Adding channels beyond email and push** — the spec's open question 1 keeps this to two channels.

## Dependencies

- None known — this is the first story in Phase 1.

## INVEST self-check

| Criterion | Pass / Flag | Note |
|---|---|---|
| Independent | Pass | Doesn't require story 0002 or 0003 to ship first; it's the API's own behaviour. |
| Negotiable | Pass | States the outcome (independent toggles); doesn't dictate the storage shape. |
| Valuable | Pass | Directly named in the ask. |
| Estimable | Pass | One model change, one endpoint, no open questions blocking it. |
| Small | Pass | One PR-sized change to one model and one endpoint. |
| Testable | Pass | Each criterion is a concrete Given/When/Then a tester can run. |

**Flagged:** none.
