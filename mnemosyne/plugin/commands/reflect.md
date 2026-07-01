---
description: Reflect a real failure (or capture a decision/convention) into reflexion memory
argument-hint: [what was learned / what went wrong]
---

Turn what was just learned into a durable lesson in the Mnemosyne reflexion memory: **$ARGUMENTS**

First decide which it is:

- A **mistake / gap surfaced by feedback** → use `reflect` (needs `--reflection-of`).
- A **reusable decision or convention** (a default, a naming rule, a settled choice) → use `capture`.

Then run the engine with the Bash tool (reads `$MNEMOSYNE_REPO`, or pass `--repo`; use
`python -m mnemosyne …` if `mnemosyne` isn't on PATH):

```
mnemosyne reflect --title "<imperative title>" \
  --lesson "<what to DO next time>" \
  --reflection-of "<what actually went wrong>" \
  --tags <comma,separated> --confidence <high|medium|low>
```

or

```
mnemosyne capture --category convention --title "<title>" --lesson "<what to do>" --tags <tags>
```

Guidance:

- Write the **lesson** as an action to take, not just a description of the failure.
- Do **not** reflect missing-deliverable or transient failures (timeouts, flakes, "a re-run fixed
  it") — the engine will refuse them, and it's right to. Don't `--force` past that unless the
  lesson is genuinely new and durable.
- If the engine says **REINFORCED**, that's success — an existing lesson got stronger; don't add a
  duplicate.

Finally, **relay the `SAVED:` / `REINFORCED:` line verbatim**, and mention it can be shared with
`/promote <id>` for team review.
