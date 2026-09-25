---
name: sync-claude-md
description: Correct documentation that a code change just made wrong — in the same diff, in place. Use only when a diff has changed code that some document describes; the skill edits the specific stale lines and nothing else. It never appends, never adds sections, and does nothing at all when no documented code changed. Not a general documentation review, not a place to record what a phase did.
---

# Sync docs to the diff

Documentation that describes code should be corrected when that code changes. This skill does
exactly that much: given a diff, it finds the documentation lines that the diff made **factually
wrong** and rewrites those lines in place.

It is deliberately, aggressively narrow. **Read "Why this skill is narrow" before you decide it
should do more.**

## The two hard rules

1. **Rewrite in place. Never append.** Every edit replaces or deletes text that is already there.
   No new sections, no new bullets, no "updated as of" notes, no changelog entries. If a change
   genuinely needs a *new* piece of documentation, that is not this skill's job — **report it to
   the user and stop.**
2. **Fire only on the diff.** Touch a document only when code that *that document describes*
   changed **in this same diff**. No diff, no edits. Code changed but no document describes it, no
   edits. This is a gate, not a preference.

If you cannot satisfy both rules, make no edit and say why.

## Step 1: Establish the diff (the gate)

```
git diff --name-only <base>...HEAD     # <base> = branchModel.base, else develop, else default branch
git diff --name-only                   # plus uncommitted work, if you're syncing before committing
```

Hold that list of changed paths. It is the *entire* authority for what may be edited below.

**If the list is empty, or contains only documentation files, stop.** Report "no documented code
changed" in one sentence and do nothing else.

## Step 2: Map changed paths to candidate documents

Use `docSync.map` from `.claude/amphion.config.json` — a list of
`{ "doc": <path>, "describes": [<globs>] }`. A document is a candidate **only if** at least one
changed path from Step 1 matches one of its `describes` globs.

With no config, fall back to the narrowest defensible heuristic: for each changed file, the
`CLAUDE.md` or `README.md` in its own directory, then in the nearest ancestor directory **inside
this repo**. Stop at the repo root.

Hard limits on the candidate set, whether configured or inferred:

- **Never** a document outside this repository — no parent workspace, no sibling repo, no
  `~/`-rooted path.
- **Never** sweep for documents. If it isn't reachable from a changed path, it isn't a candidate.
- **Never** a document merely because it is stale. Staleness alone is out of scope here; that is a
  standalone documentation pass, not a step in a code change.

## Step 3: Find the lines that this diff made wrong

For each candidate document, read it and identify the specific lines whose *subject* — a path, a
filename, a command, a symbol, a route, a directory listing, a version — both:

- appears in the changed-path list or the diff hunks from Step 1, **and**
- now states something that is no longer true.

Typical hits:

| Documented thing | Diff signal | Correct action |
|---|---|---|
| A file or directory path | That path was renamed, moved, or deleted | Rewrite the path, or delete the line if the thing is gone |
| A build/test/lint command | The script or task was renamed or removed | Rewrite the command to the one that now exists |
| A described module boundary or entry point | That module's public surface changed in the diff | Rewrite the description to match |
| A structure table row | The row's file/directory was deleted or renamed in the diff | Rewrite or delete the row |
| A stated version or dependency | Changed in a manifest in this diff | Rewrite the value |

**A line that is merely awkward, verbose, or differently-phrased-than-you-would-write-it is not a
hit.** Do not rewrite for style. Do not "improve" prose. Correctness only.

## Step 4: Edit

Make targeted `Edit`-tool replacements against the lines from Step 3. Nothing else in the file may
change.

If a document needs something *added* to be accurate — a new directory now exists and has no row,
a new command has no entry — **do not add it.** Collect these as "gaps noticed" for Step 5 and let
the user decide. Adding is how this skill previously grew documents without bound; see below.

## Step 5: Report

- **Edited** — one bullet per file: what was wrong, what it now says.
- **Gaps noticed, not written** — one bullet each, so the user can choose to add them.
- **Nothing stale** — one sentence, and stop.

## Why this skill is narrow

This skill previously ran after every implementation phase, reviewed every `CLAUDE.md` in scope,
and brought each one "up to date." Two failure modes followed directly from that design, and both
rules above exist to prevent a specific one:

**It appended, so documents bloated.** "Bring it up to date" reads as "add what's missing," and
every run added. `CLAUDE.md` files grew into changelogs of everything that had ever happened — and
a long context file is a worse context file, because the signal a future session actually needs is
buried in accumulated history. Hence rule 1: **rewrite in place, never append.** Anything that
would grow the document gets reported, so a human makes that call deliberately, once, rather than
an agent making it on every run.

**It fired unconditionally, so every PR conflicted with every other PR.** Running it at the end of
every phase meant every branch touched the same few documentation files, usually near the same
lines. Independent PRs that shared no code at all still collided in `CLAUDE.md`, and the merge
conflicts cost more than the staleness ever did. Hence rule 2: **a document is touched only when
the code it describes changed in this same diff.** Two PRs that don't touch the same code no longer
touch the same documentation.

**Do not widen this back.** The instinct to make it "just also check" adjacent documents, or to
"just add" the missing row, is exactly what produced both failures. The goal is documentation that
doesn't go stale; the mechanism that failed was the unconditional sweep, and the mechanism that
works is the diff gate. If you find a real gap this narrowness leaves, raise it with the user —
don't quietly restore the sweep.

## Anti-patterns

- **Don't run this "to check."** With no code diff there is nothing to check; that's a
  documentation review, and it's a different job.
- **Don't touch a document because it looks out of date.** Only the diff can nominate a document.
- **Don't add a section, a bullet, a note, or a date stamp.** Ever.
- **Don't rewrite whole files.** Targeted edits only — a full rewrite is an append wearing a
  disguise, and it conflicts with everything.
- **Don't climb out of the repository.** A parent-workspace document is never in scope.
- **Don't restate what the phase did.** That belongs in the commit message and the PR description,
  which is where a reader looks for history.
