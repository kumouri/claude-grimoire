---
name: pr-description
description: Write a pull request description with evidence — what and why, linked spec and ADRs, the local gate table, tests and what they prove, what was NOT checked, deliberate deferrals, and decisions needed from the reviewer — diffed against the repo's real integration branch. Use when opening or updating a PR, or when asked to summarize a branch for review.
---

# PR description

A good description lets the reviewer read the diff already knowing what to check. It carries the
evidence the author gathered, so the reviewer doesn't have to repeat it, and it says plainly what
wasn't checked.

## Step 1: diff against the right base

Work out the integration branch. Don't assume `main`:

1. `branchModel.base` in `.github/zethus.config.json`, if set;
2. otherwise `develop`, if it exists;
3. otherwise the default branch (`git remote show origin`, the *HEAD branch* line).

Fetch first, then read `git log --oneline origin/<base>..HEAD` and `git diff origin/<base>...HEAD`.
The three-dot diff is against the merge-base, so it describes *your* changes, not everything that
landed on the base since you branched.

## Step 2: fill the template

Start from `.github/zethus/templates/pr.md`:

- **What / Why:** one sentence, then two or three lines. Link the spec, and say which phase this
  PR is.
- **Changes:** grouped by concern. Don't restate the diff line by line.
- **Evidence:** the `run-local-gates` table, pasted unedited; the tests added and what each
  proves; the mutation check; any measurement, with its source and timestamp.
- **What was not checked:** gates that were skipped or manual, environments not exercised, and
  claims verified only by reading. Never drop this heading. Write "Nothing — every gate ran" if
  that's true.
- **Not in this PR (intentional)** and **Noticed but out of scope:** deferrals and `file:line`
  observations. These headings are shared with Amphion's `flag-or-fix`, which files its deferrals
  under them.
- **Decisions needed from the reviewer:** as options, with your recommendation first and marked
  **(Recommended)**.
- **Docs updated:** from [docs-sync-check](../docs-sync-check/SKILL.md).
- **AI assistance:** name the tool, and confirm the co-author trailer is on the commits.

Delete any other heading that is empty.

## Step 3: open it — don't merge it

Push the branch and open the PR against the integration branch. **Don't merge it, even if you
can.** A person merges, and only when CI is green on the exact head commit they reviewed. If you
push again after review, say so in a comment: the approval covered the earlier commit.

## Anti-patterns

- **Diffing against `main` in a repo that integrates on `develop`.** You'd describe every commit
  since the last release.
- **"All tests pass"** without saying which ones ran, where, and on what tree.
- **Hiding a judgment call in the diff.** If you decided something the spec didn't, it belongs
  under *Decisions needed*, or in an ADR.
