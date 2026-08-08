# Audit — aggregation composability (ADR-0024 set)

**Date:** 2026-08-07
**Scope:** ADR-0033 §Generalization backlog → "Aggregation composability audit"
**Box:** half-day, reading task. No fixes applied.
**Subject:** `openddil-tactical-agents/regional/aggregator_app.py::_emit_rollups`

## Why this audit exists

ADR-0033 states the tier hierarchy is unbounded and recursive. Unbounded
depth requires that **tier N aggregates tier N−1's rollups, not the
leaves** — an aggregation that assumes raw leaf streams works at depth 2
and silently breaks at depth 3. Silently is the operative word: no
error, no crash, just rollups that lie.

That makes this the one backlog item that is a **correctness
prerequisite** rather than a generalization convenience, and it makes
ADR-0033's unbounded-depth claim *unverified* until this runs.

## Method

Read every aggregation in `_emit_rollups`. For each, classify:

- **Composes-over-rollups** — can consume a child tier's emitted rollup
  and produce a correct parent rollup.
- **Assumes-raw-leaves** — requires per-asset input.

And separately, because the mathematics and the code disagree in
interesting ways here, note whether the aggregate function is
*composable in principle* even where the current implementation is not.

Plus one annotation column (free, harvested while the code was open):
does the aggregation's input carry the ADR-0029 releasability labels?

## Headline result

**All three aggregations are `assumes-raw-leaves` as implemented.** Every
one iterates `snapshot = list(assets_latest.items())` — a Faust table of
**per-asset** `AssetState` records. None has an input path that could
accept a child rollup.

But the three differ sharply in whether that is *fixable plumbing* or a
*genuine mathematical obstruction*, and that difference is the substance
of this audit:

| # | Aggregation | Implemented | Composable in principle | Verdict |
|---|---|---|---|---|
| 1 | `region_fleet_summary` | assumes-raw-leaves | **Yes** — counts are associative | Plumbing |
| 2 | `region_top_factors` | assumes-raw-leaves | **No** — top-N truncation is lossy | **Genuine obstruction** |
| 3 | `region_wear_trends` | assumes-raw-leaves | **Yes** — mean+count is algebraic, and the wire format already carries the count | Plumbing (wire already ready) |

---

## 1. `region_fleet_summary` — severity bucket counts

**What it does.** Per asset: derive a bucket from logistics severity and
from CM state, take the worse, increment that bucket's counter. Emits
`{nominal, degraded, critical, non_operational, asset_count}`.

**Composable in principle: YES.** Counts are associative and
commutative. A parent's counts are exactly the element-wise sum of its
children's counts. This is the textbook *distributive* aggregate.

**Why the implementation is not.** Bucketing happens per asset, from
`state.logistics_severity` + `state.cm_overall_status` — inputs that a
child rollup does not carry. A child emits *already-bucketed counts*,
not the per-asset severities needed to re-derive them.

**Fix shape (not applied).** Give the aggregator a second input path:
when the arriving envelope is a `RegionFleetSummary` (rather than a
per-asset update), element-wise add its counts into the parent's
totals. The per-asset path stays for leaf tiers. No change to the
emitted message or to the arithmetic.

**Label column:** inputs carry **no** releasability labels.

---

## 2. `region_top_factors` — top-N constraining factors

**This is the audit's real finding.**

**What it does.** Per asset, per constraining factor: increment
`factor_counts[factor_id]`, accumulate a severity breakdown. Sort by
count descending, **truncate to `_TOP_FACTORS_N`**, emit.

**Composable in principle: NO — the truncation is lossy in a way that
cannot be recovered downstream.**

Top-N is the classic non-composable aggregate. Counts compose; *top-N of
counts does not*. Concretely, at depth 3 with N=5:

> A factor that ranks **6th in every child region** is emitted by
> **none** of them. The parent, summing only what its children emitted,
> cannot see it at all — even though its true total across the theatre
> may exceed every factor that *was* emitted.

The failure is exactly the shape ADR-0033 warns about: no error, no
crash, a plausible-looking top-5 that is simply wrong. And it is
**worse** at greater depth, because each additional level truncates
again — errors compound multiplicatively with tier count, not additively.

Note this is *already* latent at depth 2 in the sense that any consumer
believing "these are the region's top factors" is correct today only
because the aggregator reads raw leaves. The bug is armed the moment a
tier consumes another tier's rollup.

**Fix shapes (not applied, recorded for the decision):**

- **(a) Propagate untruncated counts; truncate only at presentation.**
  Correct, and simple. Cost: message size grows with distinct factor
  cardinality. Factor IDs are a small controlled vocabulary
  (`cm.overall_status`, `operational.*`, `stale_inputs`, …), so the
  cardinality is plausibly bounded in the low tens — this is likely
  affordable and is the recommended default.
- **(b) Emit top-N *plus* an "other" residual** carrying the summed
  count of everything truncated. Bounds the error and makes it visible,
  but still cannot recover *which* factor was dropped.
- **(c) Approximate top-k sketch** (e.g. Space-Saving / Misra-Gries)
  with a stated error bound. Correct choice only if factor cardinality
  turns out to be genuinely large, which current evidence does not
  suggest.

**Recommendation for the eventual decision: (a),** unless factor
cardinality is measured and proves unbounded. It converts a silent
correctness bug into a size question, and size questions are the kind
this project can answer with a measurement.

**Label column:** inputs carry **no** releasability labels.

---

## 3. `region_wear_trends` — mean RUL per (component, unit)

**What it does.** Group per-asset wear entries by `(component_id,
unit)`, emit `mean_rul_remaining` and `asset_count` per group.

**Composable in principle: YES**, and better than expected — **the wire
format is already composition-ready.**

A mean does *not* compose from means alone. It *does* compose given
(mean, count) pairs:

```
parent_mean = Σ(mean_i × count_i) / Σ(count_i)
```

Those are precisely the two fields `ComponentWearTrend` already carries
(`mean_rul_remaining`, `asset_count`). So this aggregate is *algebraic*
— it emits sufficient statistics for its own recombination.

That looks accidental rather than designed (`asset_count` reads as a
"how many assets back this number" provenance field), but it is
genuinely valuable: **no wire-format change is required for this
aggregation to compose.** Only the merge path is missing.

The `(component_id, unit)` grouping key also composes cleanly — the
mixed-unit rule (ADR-0013 lineage) means groups never silently merge
across units, so a parent merging children's groups is safe.

**Fix shape (not applied).** Add a merge path that accepts child
`RegionWearTrends`, groups by the same `(component_id, unit)` key, and
combines with the count-weighted mean above. Guard `Σcount == 0`.

**Label column:** inputs carry **no** releasability labels.

---

## Label annotation — summary

**Uniform: no aggregation's inputs carry releasability labels today.**

The aggregator consumes `AssetState` (`aggregator_app.py:84`), whose
fields are severity, factors, CM status, CM lifecycle, wear, timestamps,
and source edge — no `originator_nation`, no `releasable_to`. A grep for
either field across `openddil-tactical-agents/regional/` returns
nothing.

This is expected, not a defect: the Arc 1 Phase 1 migration added the
labels to **Postgres tables**, while the proto `Provenance` additions
remain an ADR-0029 Phase 0 deliverable. Labels do not yet exist on the
wire, so they cannot reach a wire-fed aggregator.

**What this means for the deferred question** ("what is the releasability
label of an aggregate?" — the `region_*` exclusion from the Arc 1 Phase 1
migration): the input inventory is currently *empty*, which is useful to
know. Label composition cannot be designed against these aggregations
until labels are on the wire, and any design must account for all three
inputs arriving unlabelled today.

It also sharpens why that question is hard here: **label composition is
itself an aggregation-composability property**, and aggregation #2 shows
that not every aggregate composes. A union-of-`releasable_to` rule is
distributive (like counts); an intersection rule is also distributive;
but the *aggregation-sensitivity* concern — that a rollup can be less
releasable than any of its components, because the pattern reveals more
than the parts — is not expressible as either, and is closer in
character to the top-N problem: information that cannot be recovered
from the emitted artifact alone.

Recorded as inventory only. No composition rules designed here.

## Conclusions

1. **ADR-0033's unbounded-depth claim is now audited, and it is
   conditional.** Two of three aggregations are plumbing away from
   composing. One — `region_top_factors` — is **not correct at depth ≥3
   as specified**, and fails silently.
2. **No fixes were applied**, per the box. Fix shapes are recorded above
   for each.
3. **Nothing here blocks Arc 1**, which deploys presentation nodes at
   leaf and root of a three-deep topology and does not introduce a
   tier-consuming-tier rollup path.
4. **Before any deployment configures a fourth tier** — or a rollup that
   consumes another rollup at any depth — `region_top_factors` must be
   resolved. That is the gate this audit establishes.

## Related

- ADR-0024 — the aggregator pattern audited here.
- ADR-0033 — the recursive-tier invariant this verifies; §Generalization
  backlog is where this audit was tracked.
- ADR-0029 — releasability labels; the label column's context.
- ADR-0013 — physical-quantity consistency; why `(component_id, unit)`
  grouping is safe to merge across tiers.
