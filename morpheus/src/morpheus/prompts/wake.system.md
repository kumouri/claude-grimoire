# Waking — recall priming (optional)

This prompt is a reference for the "wake" step. In practice the SessionStart hook builds the
digest deterministically from `MEMORY.md` + recent dream logs (see `lib/digest.py`) and injects
it as `additionalContext`, so no model call is required on wake.

If you ever drive waking through a model instead, the task is: read `memory/MEMORY.md` and the
most recent `memory/dreams/*.md` entries, then produce a concise digest (≤ 12 lines) of the
most relevant long-term memories and any open hypotheses from recent dreams — so the new
session starts already "remembering." Do not restate everything; surface what is most likely to
matter now.
