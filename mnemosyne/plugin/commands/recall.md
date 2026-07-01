---
description: Recall relevant reflexion lessons for the current work and apply them
argument-hint: [query / what you're about to do]
---

Recall durable lessons from the Mnemosyne reflexion memory that are relevant to: **$ARGUMENTS**
(if that's empty, infer the context from the current task and recent conversation).

1. Run the engine with the Bash tool (it reads `$MNEMOSYNE_REPO`, or pass `--repo`):

   ```
   mnemosyne recall --query "$ARGUMENTS"
   ```

   Add `--stage <stage>` if you know the current lifecycle stage, `--tags a,b` for known tags,
   or `--from-brief <path>` to extract context from a plan/ticket/brief. If `mnemosyne` isn't on
   PATH, use `python -m mnemosyne …`.

2. **Relay the `RECALL:` line verbatim** to the user (the transparency contract).
3. **Apply** the returned lessons to the work — as defaults, checks, or questions. Confirm any
   lesson flagged LOW-CONFIDENCE before relying on it.
4. State plainly which lessons you applied and how.
