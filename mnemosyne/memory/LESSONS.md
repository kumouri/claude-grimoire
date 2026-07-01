# Reflexion Lessons (generated — do not edit by hand)

Source of truth is `memory/lessons.jsonl` (+ local `memory/local.jsonl`). Regenerate with `mnemosyne render`. Baseline `96ca934`. Config `software-eng`.

**5 active lesson(s)** across 5 categories. Authored only via the mnemosyne engine.

## mistake (1)

### L-0001 — Pin idempotency for every new write endpoint

- **Apply:** For any new or migrated endpoint that writes, decide the idempotency contract (key, dedup window, replay behavior) up front and record it as an acceptance criterion.
- **Why:** A write endpoint whose idempotency is unspecified accumulates or double-posts on replay, and the gap is only found late.
- **When:** `stages=intake,implement` · `tags=idempotency,replay,dedup,transaction` · `work_types=new-feature,migration` · `source_systems=monolith` · `endpoint_patterns=POST *,PUT *`
- **Source:** reflection-of: A new POST double-posted on replay because idempotency was never specified.
- _confidence=high · tier=shared · memory=episodic · review=approved · learned-in=plan_

## decision (1)

### L-0003 — Ship risky changes behind a feature flag

- **Apply:** Wrap a risky or hard-to-reverse change behind a feature flag and roll it out gradually, so it can be disabled without a redeploy.
- **Why:** Gradual rollout with a kill switch turns a risky change into a reversible one and shortens incident recovery.
- **When:** `stages=plan,implement` · `tags=feature-flag,rollback,cutover` · `work_types=new-feature,enhancement`
- **Source:** —
- _confidence=high · tier=shared · memory=semantic · review=approved_

## convention (1)

### L-0002 — Default list endpoints to a page size of 50

- **Apply:** List/collection endpoints paginate with a default page size of 50 unless there's a reason otherwise; propose it and confirm rather than returning unbounded results.
- **Why:** Unbounded list responses are a recurring latency and memory cost; a shared default avoids re-debating it each time.
- **When:** `stages=plan,implement` · `tags=pagination,validation` · `endpoint_patterns=GET *`
- **Source:** —
- _confidence=medium · tier=shared · memory=semantic · review=approved_

## security (1)

### L-0005 — Write an audit record for every PII mutation

- **Apply:** Any create/update/delete that touches personal data must write an audit record (who, what, when, before/after) in the same transaction as the change.
- **Why:** Audit gaps on PII are found during compliance review, not development; tying the audit write to the same transaction makes it impossible to skip.
- **When:** `stages=intake,implement` · `tags=pii,audit,security,compliance,transaction`
- **Source:** —
- _confidence=high · tier=shared · memory=semantic · review=approved_

## process (1)

### L-0004 — Sequence cross-service dependencies into the final phase

- **Apply:** When planning phased work, order phases so anything depending on another service's endpoint lands last; don't front-load a cross-service dependency.
- **Why:** A plan that front-loads a cross-service dependency stalls waiting on the other team; sequencing it last keeps earlier phases unblocked.
- **When:** `stages=plan` · `tags=sequencing,cross-service,state-machine` · `work_types=migration`
- **Source:** reflection-of: A plan front-loaded a cross-service dependency and the phase stalled.
- _confidence=high · tier=shared · memory=procedural · review=approved · learned-in=plan_
