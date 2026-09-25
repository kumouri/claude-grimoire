---
name: fresh-eyes-investigation
description: Investigate a failure with fresh eyes — given only the failing artifact (log, test output, stack trace, diff) and one line of intent, return a ranked list of places to look, each marked established (with what was read) or conjecture. Never a diagnosis, never a fix; an empty list is a valid answer. Use when an approach has failed twice, when a failure makes no sense, or when you're stuck and have a theory you can't shake.
---

# Fresh-eyes investigation

When you are stuck, you are usually stuck *inside a theory*. Every attempt so far tested the same
belief. This investigation is useful because it doesn't share that belief. So its inputs are
deliberately narrow, and it is forbidden to produce the thing that stuck people want most: an
answer.

## Inputs — exactly two

1. **The artifact:** the failing log, test output, stack trace, or diff. Give the thing itself, not
   a summary of it.
2. **One line of intent:** what was supposed to happen. "The nightly export should produce one
   file per tenant."

Pass nothing else. Leave out your hypothesis, what you've tried, and what you think it "probably"
is. If the request contains a hypothesis anyway, **ignore it, and say at the top of the output
that you did.**

If your environment can run a subagent, run this in one, so the investigator really has none of
your context. Otherwise, run it yourself after deliberately setting your theory aside.

## Rules

1. **Never diagnose.** Output leads, never a cause. This holds even when the cause looks obvious,
   and even when it would have been right. A confident diagnosis defeats the purpose: it replaces
   one unchecked theory with another.
2. **Read-only.** Don't re-run the failing thing, edit files, or "just try" a fix.
3. **Mark each lead** as **established** (cite exactly what you read: `file:line`, the log line) or
   **conjecture** (reasoned but unread). Established leads rank first.
4. **Compare with the nearest thing that works.** The strongest method is to diff the failure
   against the closest *succeeding* counterpart, such as yesterday's run, the sibling test, or the
   other tenant, and look where they diverge.
5. **An empty list is a valid answer.** If the artifact shows nothing anomalous, say exactly that.
   Never invent leads to fill the list. A made-up lead costs someone real time to rule out.
6. **One pass.** Return the list and stop. Don't ask follow-up questions.

## Output

```markdown
<If a hypothesis was supplied: "A hypothesis was included in the request; it was ignored.">

| Rank | Where to look | Why | Basis |
|---|---|---|---|
| 1 | `src/export/partition.py:88` | Tenant key read before the config reload at :62 | established — read both lines |
| 2 | The 02:00 cron window | Failure timestamps cluster at 02:00–02:04 | established — log lines 14, 31, 57 |
| 3 | Clock skew between hosts | Two hosts' timestamps interleave out of order | conjecture — no host clock data read |
```

Or, when nothing stands out:

```markdown
No leads: the artifact shows no anomaly relative to the stated intent.
```

## After

Whoever was stuck works through the leads in rank order. A lead that pans out becomes a fact in
the spec or the PR, with its citation. If the list was empty, the problem is probably outside the
artifact: get a better artifact before trying again.
