# Decision brief — per-tier severity (Arc 1 Phase 3 blocker)

**Date:** 2026-08-08 · **Status:** decision reserved · **For:** a/b/c call

## The problem, restated

Fusion runs once at the root tier and produces `asset-logistics-status`
to the **root broker** (`FUSION_KAFKA_BROKERS = $hqBroker`,
`hub.yaml:573`). A tier presentation node's projector subscribes
**tier-local topics only**. Severity therefore never reaches a tier-local
store — **absent, not stale**. The UI renders ringless whether connected
or severed, and Phase 5(iii)'s recording would show live telemetry over
a dead severity layer.

Pushing severity *downward* is not a fix: during severance the root
**cannot compute** that tier's severity at all, its inputs having
stopped. The computation must move.

## Finding: what fusion actually uses Restate for

Read `workflows/asset_logistics.py` end to end. Two features, not many.

| Restate feature | In use? | What it holds / does | What breaks without it |
|---|---|---|---|
| **Per-key durable state** (`ctx.get`/`ctx.set`, keyed by `asset_id`) | Yes, heavily | 9 keys, **all latest-value-per-asset**: telemetry, derived sustainment, windows, CM state, capability snapshot + 3 scalars (`last_severity`, `revision`, `next_timer_ns`) and origin provenance | A keyed materialized view. Direct equivalent: a Kafka state store / compacted table. |
| **Durable delayed self-invocation** (`ctx.object_send(on_timer, send_delay=…)`) | Yes — the one genuinely Restate-specific capability | Per-asset self-rescheduling cadence tick, debounced via `next_timer_ns` | **Staleness and MTBF projection stop updating for quiet assets.** An asset that goes silent freezes at its last severity — the "gone quiet" detection is exactly this. |
| Cross-VO calls / orchestration | **No** | `object_send` targets `on_timer` on the *same* key only — self-send | n/a |
| Sagas / compensation / multi-step workflow | **No** | none present | n/a |
| Exactly-once & retry semantics | Implicit | handlers are latest-value writes, effectively idempotent | Low risk |

**Verifying the chart's "VO state is load-bearing" claim: it is
overstated.** The state is a cache of latest inputs, and **3 of the 5
input topics are compacted** (`telemetry-latest-state`, `asset-cm-state`,
`asset-capability-snapshot`) — fully reconstructible by replay. The other
two (`asset-telemetry-windows`, `derived-sustainment`) are retention-based
(24 h), so reconstructible within that window. Losing VO state costs a
**replay**, not data.

**Consequence for (b):** the honest cost is *state store + periodic
scan*, not a workflow-engine reimplementation. Faust already provides
both (tables + `@app.timer`). The per-key precise timer becomes a
full-keyspace scan on the cadence — at tier-scoped keyspaces (tens to
low hundreds of assets) that is trivial.

## Re-sizing (a) — the footprint objection *strengthens*, unexpectedly

I could not obtain live row counts (see Blocked below), but the
structural answer is more decisive than a count would be:

**Restate's cost is a fixed runtime baseline, not a data-proportional
cost.** It is a RocksDB-backed stateful server — `requests 512Mi`,
`limits 2Gi`, 5 Gi PVC — and that baseline does not shrink because a
tier holds fewer assets. Per-asset state is small (latest-value JSON
dicts, order KB/asset), so a tier holding 100 assets stores maybe a few
MB.

So the intuition "an edge Restate is smaller, therefore cheaper" is
**false in the way that matters**: (a) costs ~512 Mi–2 Gi **per tier
node, essentially fixed**, roughly doubling the tier presentation node
and adding a PVC + StatefulSet at the tier ADR-0021 identifies as
footprint-constrained. The 512 Mi-OOMKill note is about state growth at
root scale; it is not the binding constraint here — the baseline is.

## (c) — honest-gap treatment (spec only, no build)

Three sentences, per the CM-label discipline (claim only what the data
supports):

> The severity indicator renders in a distinct **"not computed here"**
> state — visually neutral, never green, never a severity colour — with
> the label *"Severity computed at HQ — unavailable while this site is
> severed."* It must not fall back to last-known severity styled as
> current, because a stale ring is indistinguishable from a live one.
> Position, telemetry, CM state and capability remain fully live, so the
> UI shows exactly the truth: this tier knows what it locally holds.

## Interaction with ADR-0034 — the sequencing question

ADR-0034's per-tier detection plane converges on **fusion evaluators as
registered detectors running at each tier**, which is architecturally
option (b). So (a) buys a Restate-per-tier topology that the analytics
arc is designed to replace. Whether that is waste or a legitimate bridge
depends on how far out the analytics arc sits.

## Recommendation *(labelled as such — decision reserved)*

**(c) now, (b) as the destination; (a) not recommended.**

The feature table is what moves me: with no orchestration, no sagas, no
cross-object calls, and largely-reconstructible state, (b) is a state
store plus a periodic scan — materially cheaper than it looked
yesterday, and it is where ADR-0034 lands anyway. (a) pays a fixed
per-tier runtime baseline for a topology we intend to replace.

(c) as interim keeps Phase 5(iii) honest and recordable: position and
telemetry live at a severed site is *still* the arc's proof, and the
severity gap is stated on screen rather than hidden. It does weaken the
demo, and that is the real cost of this recommendation.

**Not decided here.** If the analytics arc is far out and the demo needs
severity at a severed site soon, (a) is defensible as a bridge — the
brief's job is to price it, not to choose.

## Blocked

- **Live row counts / cardinality measurement (T3).** No access to a
  populated cluster: current context `edge` has no OpenDDIL pods;
  `edge-rancher` returns 403 unauthenticated. Both the per-tier VO-state
  count and the `factor_id` cardinality query remain parked. Structural
  analysis above does not depend on them.
