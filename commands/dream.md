---
description: Consolidate the current session into long-term memory now (manual dream)
argument-hint: "[optional focus, e.g. 'just the auth decisions']"
---

Run a **dreaming** consolidation on the conversation so far, on demand (the same thing that
happens automatically before compaction and at session end).

Use the `dreaming` skill to do this: reflect over everything in the current session, distill the
durable signal, and write it into this project's two-tier memory store (`memory/<type>-<slug>.md`
files + the `MEMORY.md` index), merging/deduping/linking against what's already there. Then do a
bounded association pass and record speculative connections in the dream log only.

If the user supplied a focus after the command ($ARGUMENTS), bias the consolidation toward it;
otherwise consolidate the whole session.

Keep it tight: quality over quantity, never store secrets or anything derivable from the repo,
and respect the memory format exactly.
