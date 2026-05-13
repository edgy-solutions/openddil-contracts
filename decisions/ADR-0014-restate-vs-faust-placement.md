# ADR-0014: Restate vs Faust — Where Each Engine Lives

## Status

Accepted — 2026-05-12

## Context

OpenDDIL now has two stream-processing engines in production: **Faust**
(used by `faust-edge` for anomaly detection on `raw-sensor-stream`) and
**Restate** (introduced in Phase 3 to host the Configuration Management
service via Virtual Objects).

Without a clear placement rule, every new feature provokes the same
question — "Faust or Restate?" — which invites either inconsistent
ad-hoc decisions or a slow drift toward whichever engine the most recent
engineer touched. The transition cache in Phase 3's first Restate
implementation made the answer obvious for that case, but the broader
principle deserves to be written down so Phase 3.5 and beyond don't have
to relitigate it.

This ADR documents the placement rule. It is normative for new work and
explicitly **non-retroactive** for existing services.

## Decision

### Use Faust for

- **Streaming aggregation.** Rolling z-scores, EWMAs, sliding windows,
  count-by-key over a time window. The aggregation logic *is* the
  computation; per-record latency matters; throughput is high (~100s of
  events/sec sustained or higher).
- **Table-based current-state materialization** derived from a stream
  where the table is itself the artifact (e.g., the `telemetry-latest-state`
  compacted topic projection).
- **High-throughput firehose consumers** where the workload is
  "consume → project → emit" with no per-key durable workflow.
- **The existing `faust-edge` service** stays in Faust. It works, it's
  audited (Phase 2), and the firehose shape fits the engine.

### Use Restate for

- **Per-asset (or per-entity) durable workflows.** State is durable across
  restarts. The Virtual Object instance is the natural unit of state.
  Examples: `AssetCM` per `asset_id`, future `WorkOrder` per work-order-id,
  future `ConfigurationBaseline` lifecycle per `baseline_id`.
- **Scheduled per-object timers.** "Re-check this asset's compliance when
  the soonest pending mod's due_date passes" — Restate's
  `ctx.object_send(handler, send_delay=...)` is the natural primitive.
- **Durable side effects with retry semantics.** Publishing to Kafka,
  calling enterprise APIs (ALCS, EAGLE), sending notifications — wrapping
  those calls in `ctx.run()` makes them journaled and at-least-once with
  idempotency by handler invocation.
- **Lifecycle / registration flows.** `LifecycleState` transitions, an
  asset moving through `REGISTERED → ACTIVE → STALE → DECOMMISSIONED` are
  state-machine work, not stream work.

### Anti-patterns explicitly rejected

- **Refactoring `faust-edge` to Restate "for consistency."** No. Refactor
  only on concrete operational pain (cannot meet a latency target, cannot
  scale, has a real bug that the other engine would obviously avoid) or
  on genuine fit for new requirements (the workload truly changed shape).
  Consistency for its own sake is a tax, not a virtue.
- **Building a per-asset CM service in Faust.** The transition cache
  experience showed that "in-memory dict with TTL" reinvents what Virtual
  Objects give for free. Phase 3 fixed this by switching CM to Restate;
  do not relitigate.
- **Using Restate as a general-purpose stream processor.** Restate's
  durable-execution overhead is wrong for the firehose path. If you're
  about to write `@virtual_object` for a workload that has no per-key
  state and no schedule, you probably want Faust (or a plain Kafka
  consumer).
- **Letting either engine's types leak past its boundary.**
  `algorithms.py` (faust-edge) accepts `EventView`, not `faust.Record`.
  `analyzer.py` (cm-service) accepts protobuf, not the Restate dict-form
  state. The translation happens in `_build_view` / `store.py` and
  nowhere else.

## Practical placement guide

If the answer to any of the first three is "yes," **use Restate:**

1. Does the work need to remember something about a specific entity
   across restarts?
2. Does the work need to fire on a schedule that's specific to one
   entity (not a global clock tick)?
3. Does the work involve idempotent side effects that must execute
   exactly once per logical event?

If the answer to any of the next two is "yes," **use Faust:**

4. Is the work a continuous projection / aggregation over a high-rate
   topic with no per-key durable schedule?
5. Is the result itself a stream / compacted-topic materialization that
   other services subscribe to?

Workloads that fit both lists exist. When that happens, prefer the
engine whose **primary** characteristic dominates the workload. Phase 3's
CM service had both shapes — telemetry firehose AND per-asset durable
state — and went with Restate because the durable per-asset workflow was
the harder problem and the firehose volume was modest. A future CM-derived
service that just emits a continuous fleet-health summary would belong
in Faust.

## Consequences

**Pros**

- New work has a default answer. Engineers don't relitigate.
- The two engines stay specialized; neither tries to do the other's job.
- The boundary discipline (no engine types past the service boundary)
  keeps the placement decision reversible — if a service grows in a
  direction that fits the other engine better, it can move without
  rewriting `analyzer.py` or `algorithms.py`.

**Cons**

- Two engines means two operational surfaces. Faust + RocksDB
  troubleshooting AND Restate + journal troubleshooting both have to be
  on the on-call runbook.
- Engineers need to know both. Mitigated by the boundary discipline:
  the framework layer is thin in both services; most logic lives in
  pure-Python modules that don't care which engine wraps them.

**Rejected alternatives**

- *One-engine consolidation (Faust everywhere or Restate everywhere).*
  Either choice loses the strength of the other. Faust-only forces an
  in-memory transition cache in CM; Restate-only adds journal overhead
  to a firehose that doesn't need it.
- *Letting the placement remain implicit.* Tried during the Phase 3
  draft; the first proposal collapsed the in-memory transition cache and
  the rolling EWMA into the same engine despite their opposite shapes.
  Writing the rule down prevented that.

## Related

- ADR-0006 — Persistence/Computation Model Separation. The boundary
  discipline this ADR depends on.
- ADR-0009 — Configuration Management data model. The first Restate
  workload.
- ADR-0010 — Feed integration strategy. External feeds land in their own
  sidecar; whether *that* sidecar is Faust or Restate is governed by
  this ADR.

## Notes for future maintainers

- A "phase 3 limitation" tracked previously — manual discrepancies
  surviving reanalysis — was resolved in Phase 3 via the
  `manual_discrepancies` dataclass field on `AsMaintainedRecord`. No
  separate stub needed.
- If a future Phase introduces a third engine (e.g., a Flink job for
  cross-asset windowed analytics), this ADR should be extended with a
  third section rather than rewritten — the existing placement rules
  for Faust and Restate stay valid.
