---
name: morpheus
description: >-
  Consolidate a Claude Code session into the persistent two-tier memory store —
  reflect over the conversation, distill durable facts into memory/<type>-<slug>.md
  files and the MEMORY.md index (merge, dedupe, link, prune), then do a bounded
  association pass into the dream log. Use when the user runs /dream, asks to
  "consolidate this session / remember this / dream now", or to consolidate the
  current conversation into long-term memory on demand.
---

# Morpheus — session memory consolidation

This skill performs the same consolidation the automatic morpheus hooks do, but in-context (you
already have the conversation, so no transcript parsing is needed). Work in two passes.

## Pass 1 — Consolidate (durable core)

Review the session and extract only what is **durable and worth recalling next time**. For each
fact, write or update `memory/<type>-<slug>.md` in this project's memory directory and refresh its
one-line pointer in `memory/MEMORY.md`.

Types (`metadata.type`): `user`, `feedback` (+ `**Why:**` / `**How to apply:**`), `project`
(absolute dates), `reference`. File format:

```
---
name: <type>-<short-kebab-slug>
description: <one-line summary used for recall>
metadata:
  node_type: memory
  type: <user|feedback|project|reference>
  originSessionId: <session id if known>
---

<the fact. Link related memories with [[their-name]].>
```

Index line in `MEMORY.md`: `- [Title](file.md) — short hook`.

Discipline:

- Update existing memories instead of creating near-duplicates; merge and dedupe.
- Correct or delete memories this session proved stale/wrong.
- Link related memories liberally with `[[name]]`.
- **Never** store secrets/credentials, anything derivable from the repo/code/git, or facts that
  only mattered to this one conversation.
- Quality over quantity.

## Pass 2 — Associate (bounded creative pass)

Surface non-obvious connections between memories and hypotheses worth checking next session. Only
promote one into `memory/` if you're highly confident it's a real, durable fact; otherwise note it
as speculative in your summary to the user (and, for the automatic path, the dream log). Never
fabricate.

## Finish

Give the user a 1–3 line recap: what you consolidated, which memories changed, and any speculative
associations. See [`morpheus/docs/architecture.md`](../../../docs/architecture.md) for how the
automatic pipeline uses this same two-pass model.
