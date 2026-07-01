# Mnemosyne — design

## Problem

An agent (or a team) is good at not wasting effort on what the current materials already answer.
It is **bad at not repeating itself across runs**. Every run starts cold: a gap hit last week (an
unspecified idempotency contract, a state transition nobody pinned, a soft-delete that looked like
a hard delete) is re-discovered the hard way, and a decision already settled (the house
persistence pattern, the audit-on-PII rule) is re-debated. The agent has no memory of its own
mistakes or the team's accumulated rulings.

## Goal

Give the agent a **reflexion memory**: durable *lessons* it **recalls** at the start of a task and
**applies**, plus a **reflect-and-capture** step that turns feedback (a review catch, a broken
assumption, an implementation landmine) into a lesson so the same miss never happens twice. It
must distribute to everyone using it, **announce itself** (no silent memory), and stay small and
portable — stdlib only, git for storage and distribution.

## The Reflexion loop

This implements [Reflexion (Shinn et al., 2023)](https://arxiv.org/abs/2303.11366): an agent that
improves not by retraining but by **verbally reflecting on feedback and storing those reflections
in an episodic buffer it consults on the next attempt**.

| Reflexion component | Here |
|---|---|
| **Actor** (produces a trajectory) | a stage's run → its artifact |
| **Evaluator** (scores it) | downstream reality: a reviewer, a test, the next stage |
| **Self-reflection** (verbal lesson from feedback) | `mnemosyne reflect` — "what should we have done?" |
| **Episodic memory buffer** | the git store (`memory/lessons.jsonl`) |
| **Recall on next trial** | `mnemosyne recall --stage` at the start of each stage |

Modern agent-memory practice frames the same store along three axes — **episodic** (a reflection
tied to a specific past event), **semantic** (a consolidated standing fact/decision), and
**procedural** (a rule that changes how the work is run). A lesson carries both a topical
`category` (mistake / decision / convention / security / architecture / process) and a
`memory_type` along that axis.

A lesson also carries a lifecycle **stage** — orthogonal to both — so the loop learns across a
whole `intake → plan → implement → review` trail rather than only at the front. `recall --stage
plan` boosts planning lessons; a lesson captured downstream defaults to recalling in *its* stage
**and** the front stage, so the build feeds the next round of work. `source.stage` records where a
lesson was learned; `trigger.stages` controls where it fires (empty = everywhere).

## Domain-agnostic by construction: config-driven axes

Nothing about a specific pipeline is hardcoded. A `mnemosyne.config.json` defines:

- the **lifecycle stages** and which one is the "front" stage lessons feed back into;
- the **recall axes** — the dimensions a lesson's `trigger` is scored on — each with a `weight`
  and a `match` strategy: `set` (case-insensitive overlap, e.g. tags, components), `glob`
  (bidirectional fnmatch, e.g. service names), or `glob_scalar` (a scalar context value vs a list
  of patterns, e.g. an HTTP endpoint vs `POST *`);
- a **controlled vocabulary** and **stopwords** used to auto-extract context from a free-text
  brief;
- the **enums** (categories, memory types, confidence multipliers) and **thresholds** (dedup,
  prune age, active cap).

The engine's scorer loops over `config.axes`; adding a `components` axis to the config gives you
`--components` on the CLI and a scored `trigger.components` with no code change. Two example
configs ship: a minimal `default` (tags + stages + free-text) and `software-eng` (tags,
components, work-types, source-systems, services, endpoint-patterns).

## The core decision: git, not a new service

The store and the distribution channel are the **same git repo**, chosen over standing up a
dedicated service.

| | **Git (chosen)** | Dedicated service |
|---|---|---|
| New infra | none | a service, its store, its on-call |
| Distribution | native (`git pull`) | every client calls an endpoint |
| Review / audit of new lessons | native (PR + `CODEOWNERS`) | build a review path |
| Recall quality | lexical + metadata (great for procedural/semantic rules) | can add vector recall |
| Operational cost | ~zero | real |

Two findings make git-first principled rather than a workaround. Hybrid retrieval — embedding
similarity *plus* metadata filters — is what real agents need, and structured key lookup already
works well for procedural rules and profiles; our lessons are exactly procedural/semantic rules
with strong metadata, so lexical+metadata recall fits the data. And file-based memory is
competitive in practice (Letta's filesystem memory scored 74% on LoCoMo, beating several
specialized memory libraries). Files in git are the right default, with a clean upgrade path
(the MCP server, or a vector index) if recall ever outgrows them.

## Architecture

**Two tiers.** A captured lesson lands in the **local** tier (`memory/local.jsonl`, gitignored)
instantly — zero friction. It shapes only *your* work until you **promote** it: `mnemosyne
promote` moves it to the **shared** tier (`memory/lessons.jsonl`, committed) on a branch and
stages a PR. A reviewer approves before it becomes team-wide, so one bad lesson can't silently
poison everyone — the cost of a wrong shared lesson is high (it steers every future run), so it
gets a human gate. Agent proposes, human disposes.

**Source of truth = the JSONL.** `memory/lessons.jsonl` is authoritative; `memory/LESSONS.md` is a
**generated** human view, regenerated on every write and committed so PR diffs are readable.
Lessons are authored **only through the engine** — never hand-edited — which keeps ids, stamps,
dedup, supersession, and the rendered view consistent. `mnemosyne validate` enforces the schema
and spine consistency.

**Thin by design.** The agent never reads the store. It runs one command and relays the one-line
result. All scanning, ranking, writing, git work, and validation live in the engine, keeping the
per-run token cost near zero.

## Recall algorithm

`recall` takes context — extracted from a brief (`--from-brief`) or given explicitly per axis —
and scores every active lesson by weighted overlap against its `trigger`: each axis contributes
`weight × matches`, a `--stage` match adds `stage_weight`, and free-text query keywords found in
the title/lesson add a small capped bump. An empty trigger gets a small floor so "always worth a
glance" lessons still surface. The sum is scaled by **confidence** (high 1.0 / medium 0.85 /
low 0.6). Top-N above a minimum score are returned, each with its **matched reasons** shown, and
the output capped to a character **budget** so the paste stays small. Deliberately transparent and
debuggable — no opaque similarity score.

## Hygiene — keeping signal above noise

A reflexion store's failure mode is the opposite of forgetting: it **accretes**. Five mechanisms
keep signal above noise.

1. **Don't bank missing-deliverable / transient failures.** Reflecting on "the build produced no
   output" or "a re-run fixed it" is a *process retry*, not a lesson. A guard refuses these
   (exit 3 / `LowValueError`) unless forced; a genuine domain failure (a trigger that didn't fire)
   is not matched and saves normally.
2. **Dedup by reinforcement.** On capture, the engine finds the best same-category near-duplicate
   (title+lesson Jaccard blended with tag Jaccard) and, at/above the threshold, **reinforces** it
   — bumping a counter (and eventually confidence) instead of adding a record.
3. **Track real usage without churning the store.** `recall` writes usage to a **gitignored
   sidecar** (`memory/usage.local.json`); prune/stats merge it with the authored baseline. Reads
   never produce noisy diffs that would fight the PR gate.
4. **Collapse at recall.** Even with dedup, seeds and edits can leave near-identical twins; recall
   drops the lower-scored one so a digest never spends its budget twice.
5. **Prune and cap.** `prune` retires — never deletes — aged, never-recalled, low/medium-confidence
   lessons and enforces an active cap (retiring lowest-value lessons over it; high-confidence and
   ever-recalled lessons are protected). Dry-run by default; `--apply` writes `status=retired` + a
   reason, keeping the record for audit.

## Transparency contract

Every command prints a quotable line the surfaces relay verbatim:

- **recall** → `RECALL: N reflexion lesson(s) applied … (L-…, L-…). Source: …` — the user sees what
  prior knowledge is steering the work and can veto any of it.
- **capture / reflect** → `SAVED: L-00NN captured to LOCAL reflexion memory — "…"` + the promote hint.
- **promote** → `PROMOTED: L-00NN … staged for team review …`.

Memory is never applied behind the user's back, and never shared unreviewed.

## Governance

Lessons are **superseded, never silently deleted** (`--supersede` marks the old one and links the
replacement), so the history of what was learned — and later corrected — stays auditable. When the
memory lives in its own git repo, use `docs/lesson-review-checklist.md` as the pull-request
template and `CODEOWNERS` to route shared-store changes to the right reviewers.

## Packaging

One engine, three delivery layers (see the [README](../README.md)):

- **CLI / library** — `mnemosyne …` or `import mnemosyne`; the stdlib foundation.
- **Claude Code plugin** — a skill + hooks (recall on prompt, sync on session start) + `/recall`,
  `/reflect`, `/promote` commands.
- **MCP server** — the same operations as MCP tools for any MCP client.

## References

- Shinn et al., *Reflexion: Language Agents with Verbal Reinforcement Learning*, NeurIPS 2023 — <https://arxiv.org/abs/2303.11366>
- *Types of AI Agent Memory (episodic/semantic/procedural)* — <https://atlan.com/know/types-of-ai-agent-memory/>
- *What Is AI Agent Memory?* (hybrid retrieval) — <https://www.ibm.com/think/topics/ai-agent-memory>
- *7 Steps to Mastering Memory in Agentic AI* (Letta filesystem / LoCoMo) — <https://machinelearningmastery.com/7-steps-to-mastering-memory-in-agentic-ai-systems/>
