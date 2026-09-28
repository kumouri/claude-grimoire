# Per-channel notification preferences

**Status:** DRAFT · **Owner:** Test Owner · **Date:** 2026-09-28 · **Related:** —

> This is a synthetic example spec, used only to demonstrate `spec-to-stories`. It is not a real
> feature of any project in this repo.

## The ask

> "Let people turn off email but keep push, instead of the current all-or-nothing switch." —
> Product, 2026-09-20

- **Answers:** how notification channels become independently toggleable, and how existing users
  get a sane default when the toggle ships.
- **Does not answer:** digest scheduling, or which channels exist beyond email and push.

## What is true today

| # | Fact | Where (`file:line` @ commit) | How verified |
|---|---|---|---|
| F1 | Notification settings store a single `notifications_enabled` boolean per user | `src/notifications/settings.py:10` @ `deadbeef` | read `UserSettings` |
| F2 | The settings API has one PATCH endpoint that accepts only that boolean | `src/notifications/api.py:34` @ `deadbeef` | read the route handler |

**What this research did not cover:** the notification delivery workers themselves; only the
settings model and API were read.

## Design

Replace the single boolean with a per-channel map (`{"email": bool, "push": bool}`), exposed
through the existing PATCH endpoint with a widened payload, and backfill existing users to
`{"email": <old value>, "push": <old value>}` so nobody's behaviour changes on deploy day.

## Phases

| Phase | What | Behaviour change | Verified by |
|---|---|---|---|
| 1 | Per-channel toggle in the settings model and API | Yes, additive: old clients still see a boolean derived from `email` | unit tests on the model and the API |
| 2 | Backfill existing users' settings to the new shape | No visible change if the backfill is correct | migration test, comparing before/after per user |

## Out of scope

- **Digest scheduling** — a separate spec; this only covers on/off per channel.

## Open questions

1. **Do new channels beyond email and push get added in this change?** Options: A — no, ship these
   two only; B — leave the map open-ended now. **Recommended: A**, because the ask names only these
   two. · Decides: Product.
