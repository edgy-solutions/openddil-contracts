# ADR-0024: Multi-Cluster Faust Aggregator Pattern

## Status

Accepted — 2026-05-17 — **Implementation pattern.** Captures the empirical
findings from Phase 6b §B's faust-regional build. ADR-0023 was the
topology decision (one new image, two instances, per-region rollups);
this ADR is the implementation pattern that emerged when §B's spike and
live-stack diagnosis turned over rocks the topology decision didn't
specify.

## Context

ADR-0023 §B specified the regional aggregator tier: one `faust-regional`
container per region, consuming its assigned edges' brokers, producing
three rolled-up topics. The recipe assumed Faust would handle multi-
cluster consumption natively because the topology required it.

It does not. Three empirical findings, captured here rather than
re-discovered every time a future regional-tier service is built:

**(1) `faust.App(broker=[url1, url2])` does NOT multi-cluster.** Faust's
broker argument is forwarded to aiokafka's `bootstrap_servers`, which
treats the list as multiple bootstrap addresses for **one** cluster —
whichever broker wins the bootstrap MetadataRequest defines "the
cluster," and the other cluster's topics are invisible. §B spike
verified this empirically: a fixture topic `spike-cross-cluster`
populated independently on `redpanda-edge-01` and `redpanda-edge-02`
returned exactly one message (whichever cluster Faust elected) under
`broker=["kafka://edge-01:9092", "kafka://edge-02:9092"]`. The other
cluster's marker was silently dropped.

**(2) `faust.Worker(primary_app, *secondary_apps)` DOES compose multiple
Apps in one process.** Each App carries its own broker, consumer group,
RocksDB Tables, changelog topic namespace. Naive `asyncio.gather(
app_east.start(), app_west.start())` does NOT work — Faust's underlying
Mode framework requires one Worker owning the event loop. Worker-with-
secondaries is the idiomatic Faust composition; the spike verified it
delivers both clusters' events into one process.

**(3) The PartitionsMismatch from a partition-count-heterogeneous Table
source-set is non-obvious until live.** §B's first compose-up crashed
the aggregator immediately with `PartitionsMismatch`: the aggregator
subscribed to the per-region fan-in topic (partitions=1, set per the §B
recipe to match the Tables partition invariant) AND to `asset-cm-state`
on hq directly (partitions=8, existing topic with per-asset key
distribution). Faust requires all source topics that update a given
Table to share partition count. The same-process composition is fine;
the multi-source-partition-count is not. Live-stack diagnosis (not code
review) caught this — the Phase-5 partition-count invariant did the
catch, exactly as it caught the prognostics_accumulators bug.

Underneath finding (3) is the load-bearing rule: **when source data is
heterogeneous (some on edge brokers, some on hq), the fan-in topology
must be applied uniformly — a source App per source cluster, even when
some happen to be on the same broker as the aggregator.** The recipe's
Option A framing treated edge-broker inputs as the only cross-cluster
case; the hq-produced inputs (`asset-cm-state` per §A,
`asset-logistics-status` per §A) needed the same wrap-and-republish
treatment, not the originally-attempted direct subscription on the
aggregator App.

This pattern is not in Faust's documentation. Future regional-tier
services (Phase 6d candidates: customer-overlay AMQP routing,
echelon-aware egress bridges) will reach for it and find no idiom; an
ADR makes it findable.

## Decision

**The multi-cluster Faust aggregator pattern is: Worker composition of
one Aggregator App + N Source Apps + per-region fan-in topic + uniform
source-App treatment for all source clusters, regardless of broker
co-location with the aggregator.**

### Composition (mandatory)

- ONE container per region.
- ONE Python process per container.
- `faust.Worker(aggregator_app, *source_apps_and_their_sidecars)` —
  primary App + secondary Services, all in the same event loop. Process-
  level coupling is intentional: a crash in any App takes the region
  down; Kafka durability handles restart; restart is one observability
  surface rather than three.

### Source/aggregator split (mandatory)

- Source Apps are **stateless wrap-and-forward.** No RocksDB Tables. No
  per-asset memory. Faust agent consumes each event, wraps in a
  fan-in envelope (proto `RegionalAggregatorInput`-style oneof), produces
  to the per-region fan-in topic.
- Aggregator App owns ALL state. RocksDB Tables, changelog topics,
  emit timers, output topics — all on the aggregator. Pre-aggregating
  at the source App was rejected for the same reason ADR-0023 rejected
  passthrough-with-attribution (constraint 3 unverified, real
  aggregation collapsed).
- Source Apps and Aggregator MUST be in the same Worker (same process,
  same container). Separate containers would multiply the deployment
  surface and lose the single-restart story.

### Per-region fan-in topic (mandatory)

- One fan-in topic per region. Named `region-<region_id>-fan-in`.
- `cleanup.policy=delete`, `retention.ms=3600000` (1h), `partitions=1`,
  `replication.factor=1` (demo; production sizes per cluster). Fan-in
  topics are pipeline internals, NOT persistent state — short retention
  keeps replay bounded while surviving restart-and-catch-up.
- `partitions=1` matches the aggregator Tables partition invariant;
  changing this requires changing the aggregator's Table partitions in
  lockstep AND changing every source App's produce-key strategy.
- NOT one global fan-in topic keyed by `region_id`. Per-region topics
  give clean per-region partition ownership and avoid cross-region
  partition coupling.

### Heterogeneous-source-cluster rule (load-bearing)

**A source App per source cluster, even when some source clusters happen
to coincide with the aggregator's own broker.** If asset-cm-state lives
on hq and the aggregator also lives on hq, the aggregator MUST still
consume asset-cm-state via a wrap-and-republish hq source App rather
than subscribing directly. The PartitionsMismatch problem is general:
any time an aggregator Table is updated by agents from sources with
different partition counts, Faust will crash the agent on the first
event. Uniform wrap-and-republish through the fan-in keeps the
aggregator's source-set partition-count-homogeneous (everything is
partitions=1 fan-in).

The same-broker case (no aiokafka sidecar producer needed, Faust's
native producer handles the produce) is an implementation detail — the
RULE is "source App per source cluster," regardless of whether the
produce side needs a sidecar.

### Source-side filtering by region (mandatory for shared topics)

Source Apps that consume topics shared across regions (asset-cm-state,
asset-logistics-status — single hq topics carrying all regions' events)
MUST filter by `region_id` at the source App, dropping mismatched
events before they reach the fan-in. The aggregator's Table tracks
only its region's assets; cross-region events poisoning the Table
would silently corrupt the rollups.

The filter happens on the message's own `region_id` field
(Provenance.region_id for proto sources, JSON envelope top-level
region_id for cm-state). A defensive cross-check at the aggregator
(envelope.region_id != my_region_id → drop with WARN) is cheap insurance
against a misconfigured source App but is not load-bearing.

## Consequences

**Pros**

- Multi-cluster consumption works in one process, one container — the
  shape ADR-0023 implicitly required is achievable in Faust without
  reaching for non-Faust hybrids or MirrorMaker-style infra.
- The pattern is uniformly applied — there are no special cases for
  "this source is on the same broker so we can subscribe directly."
  Special cases are exactly the failure mode that led to the
  PartitionsMismatch crash.
- State ownership is unambiguous: aggregator owns Tables, source Apps
  don't. Cross-cluster Table writes (which Faust doesn't support
  anyway) are structurally impossible.
- Per-region fan-in topics give clean partition ownership and make
  per-region severability testable in isolation.
- Restart story is one Worker, one container, Kafka durability handles
  the rest — same observability surface as faust-edge.

**Cons**

- One extra topic per region (the fan-in). At 2 regions this is
  bounded; at scale see follow-up #12 (multi-region scaling).
- Source-side filter on shared topics means **each region's source App
  consumes every message on the shared topic**. At 2-3 regions this is
  fine; at 10+ regions the duplicate-reads cost becomes meaningful.
  Follow-up #12 names this explicitly.
- The aiokafka sidecar in per-edge source Apps is a small bounded
  hybrid (Faust on consume side, aiokafka on cross-cluster produce
  side). It's the cleanest pattern available but it is NOT pure Faust;
  future readers will see one extra dependency they wouldn't expect.
- Worker composition couples all Apps' lifecycles — a crash in any App
  takes the whole region down. Documented as intentional in the
  regional/README.md; this is a trade we accept.

## Related

- **ADR-0014 — Restate vs Faust Placement.** This ADR is the
  implementation pattern for the regional-tier Faust placement decision
  ADR-0014 set (cumulative/windowed aggregations belong in Faust).
- **ADR-0023 — Hierarchy Restoration Topology and Phase Plan.** The
  topology decision this ADR implements. ADR-0023 §B specified two
  faust-regional instances; this ADR specifies how each one is built
  internally.
- **Phase 6b §B commits:** `openddil-tactical-agents` 4a3ffa6 (new
  regional package with the pattern), d48ff6a (the live-stack
  PartitionsMismatch diagnosis and the heterogeneous-source-cluster
  rule landing); `openddil-projector` 2872b78 + c9a1d76 (handler
  registration + decoder registry); `openddil-contracts` c12106b (the
  RegionalAggregatorInput envelope proto).

## Notes for future maintainers

- **`faust.App(broker=[url1, url2])` is a trap.** Faust accepts the
  syntax silently; the broker selection is opaque; one cluster's data
  is dropped without error. If you find yourself reaching for it,
  reach for Worker composition instead.
- **The hq source App pattern (uniform wrap-and-republish for
  same-broker sources) feels redundant when you first see it.** It
  isn't. The PartitionsMismatch crash is what redundant looks like in
  retrospect — the source App is the insurance, not the
  inefficiency.
- **Tables partition count is the load-bearing invariant.** Every
  source App for a Table-updating agent must produce to a topic with
  partition count matching the Table's. The fan-in topic has
  partitions=1 because the Tables have partitions=1; change one,
  change both.
- **Single-edge regions still use the same shape.** ADR-0023 chose
  asymmetric region sizes deliberately (region-east has 2 edges,
  region-west has 1) so the degenerate-but-correct single-source case
  is exercised. Don't special-case it.
