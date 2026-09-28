# Stories from `example/spec.md`

One row per story. Grouped under an epic heading because the spec has phases. A story whose
self-check flagged a criterion is marked in the Flagged column, not hidden.

## Phase 1 — Per-channel toggle in the settings model and API

| # | Story | Traceability | Flagged |
|---|---|---|---|
| [0001-toggle-email-independently-of-push.md](0001-toggle-email-independently-of-push.md) | Let a user turn off email notifications while keeping push on | `example/spec.md#phases`, phase 1 | — |
| [0002-expose-per-channel-setting-in-the-api.md](0002-expose-per-channel-setting-in-the-api.md) | Accept a per-channel settings payload on the notification settings endpoint | `example/spec.md#phases`, phase 1 | — |

## Phase 2 — Backfill existing users' settings to the new shape

| # | Story | Traceability | Flagged |
|---|---|---|---|
| [0003-backfill-existing-users-settings.md](0003-backfill-existing-users-settings.md) | Backfill existing users to the new per-channel settings shape | `example/spec.md#phases`, phase 2 | Independent |
