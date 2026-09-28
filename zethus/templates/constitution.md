# Constitution: {{unit}}

| Field | Value |
|---|---|
| Status | {{status}} |
| Date | {{date}} |
| Owner | {{owner}} |
| Rule ledger(s) | {{ruleLedgers}} |
| Fixture manifest | {{fixtureManifest}} |
| HLA reference | {{hlaDoc}} |

Each row below cites a rule id from the ledger(s) above: `- [R1] <checkable statement> —
confidence: High|Medium|Low`. A `Low`-confidence row needs a recorded waiver:
`- [R7] <statement> — confidence: Low (waiver: <adr-id>)`. A section with nothing recovered says
so explicitly: `- No rule found — <reason>`, never left blank. See
[`../docs/modernization-shared.md`](../docs/modernization-shared.md#2-the-behaviour-constitution-template-templatesconstitutionmd).

Before Stage 3 (Implement): `python .github/zethus/scripts/overseer-gate.py constitution
--constitution <this file>` must exit 0. Before Stage 4 (Tests) reports done: every rule id cited
below needs a fixture in the manifest named in "Fixture manifest" above, captured by running the
*legacy* system — see [`fixture-manifest.example.json`](fixture-manifest.example.json) for the
shape — checked with `overseer-gate.py golden-master --constitution <this file>`.

## Inputs

- No rule found — not yet recovered.

## Outputs

- No rule found — not yet recovered.

## Side effects

- No rule found — not yet recovered.

## Ordering

- No rule found — not yet recovered.

## Error & restart semantics

- No rule found — not yet recovered.

## Commit / transaction boundaries

- No rule found — not yet recovered.

## File / message formats

- No rule found — not yet recovered.

## Exit / status contract

- No rule found — not yet recovered.

## Scheduling / invocation contract

- No rule found — not yet recovered.
