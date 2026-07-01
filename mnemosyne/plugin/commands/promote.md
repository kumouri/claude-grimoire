---
description: Promote a local reflexion lesson to the shared, PR-reviewed team store
argument-hint: [lesson id, e.g. L-0009]
---

Promote lesson **$ARGUMENTS** from the local tier to the shared team store for review.

1. Run the engine with the Bash tool (reads `$MNEMOSYNE_REPO`, or pass `--repo`; use
   `python -m mnemosyne …` if needed):

   ```
   mnemosyne promote $ARGUMENTS
   ```

2. **Relay the `PROMOTED:` line and the git/PR steps it prints verbatim.** This moves the lesson
   local → shared and marks it `proposed`; a human reviewer must approve the PR before it becomes
   team-wide truth (agent proposes, human disposes).
3. If the user asks, run the printed git/PR commands to open the review PR — but do not merge it
   yourself; that's the reviewer's call.
