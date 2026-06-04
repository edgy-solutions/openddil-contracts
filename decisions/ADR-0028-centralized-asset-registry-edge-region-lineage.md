# ADR-0028 — Centralized asset_registry for edge/region lineage

## Status

Proposed (2026-06-04). Implementation pending.

## Context

Every asset in the OpenDDIL system has an edge_id and region_id
assignment. These are used across the pipeline to:

- Route per-asset events to the right regional aggregator
  (`faust-regional` source-app's positive-match filter on
  `provenance.region_id`)
- Render assets on the correct Regional / HQ map panels
- Aggregate fleet metrics by region
- Display per-edge asset attribution

**In the production warfighter context**, the edge/region assignment
is a **static administrative fact** — humans assign assets to edges
when fielding equipment. It is NOT derived from telemetry. The
warfighter sees the assignment in their existing asset-management
systems; OpenDDIL is downstream of that authoritative source.

**In the current OpenDDIL deployment, no service has visibility into
that static assignment.** Three workarounds have emerged:

1. **`edge_assignment.py` in the projector** runs a nearest-FOB
   computation against `kinematics.position.wgs84` to DERIVE
   `region_id` per asset. The result is written to
   `telemetry_latest_state.region_id`.

2. **`cm-service` and `logistics-fusion-service`** don't run
   edge-assignment. They emit events with empty `provenance.region_id`,
   relying on downstream consumers to figure it out. They never do.

3. **`faust-regional` source-app** filters on
   `provenance.region_id` (positive match). Empty values get dropped.
   100% of cm-service and logistics-fusion events fail the filter.
   `region-east-fan-in` and `region-west-fan-in` stay empty. Regional
   and HQ rollup panels stay "Awaiting first emission" forever.

The architecture has implicitly decided that "each consumer that
needs region_id will derive it itself" — but only the projector ever
got the derivation logic. The result is silent data loss at the
regional source-app filter.

Beyond this immediate bug, the deeper issue: **a single algorithm for
asset→edge/region lineage should not be duplicated across three or
five services**. The next FOB-list update or assignment-policy change
would require coordinated updates across multiple codebases.
Drift inevitable.

## Decision

Introduce a canonical **`asset_registry`** table on the HQ postgres
as the **single source of truth for asset→edge_id→region_id
mapping**. One service writes it. All other services read it.

```sql
CREATE TABLE asset_registry (
    asset_id          text PRIMARY KEY,
    edge_id           text NOT NULL,
    region_id         text NOT NULL,
    assignment_source text NOT NULL,  -- 'static' | 'connection' | 'position' | 'unspecified'
    assigned_at       timestamptz NOT NULL DEFAULT now(),
    assigned_by       text,           -- 'warfighter-ui' | 'edge_assignment.yaml' | 'first-seen' | ...
    last_observed_at  timestamptz,    -- updated on each telemetry arrival; doesn't trigger reassignment
    observed_edge_id  text,           -- what the system actually saw (may differ from edge_id)
    divergent         boolean NOT NULL DEFAULT false
);

CREATE INDEX idx_asset_registry_divergent
    ON asset_registry (divergent) WHERE divergent;
```

### Assignment-source priority order

When multiple inputs would assign the same asset, the registry
chooses by priority:

1. **`static`** (highest) — warfighter input, loaded from a config
   file or admin UI write. Represents what the warfighter's external
   asset-management system says. Authoritative for "intent."

2. **`connection`** — derived from "which edge's aggregator first
   received data for this asset." Reliable when an asset's telemetry
   only ever flows through one edge (typical for fixed sensors).

3. **`position`** — nearest-FOB lookup via `edge_assignment.yaml`.
   The current projector logic, moved to the registry service. Used
   when no static assignment exists and connection-based isn't
   determinable.

4. **`unspecified`** (lowest) — fallback when none of the above
   yields a clear answer. Asset still tracked, but assignment is
   marked as unknown.

### Real-vs-intent divergence — the load-bearing design choice

**Static assignment wins.** When the warfighter has assigned asset-X
to edge-01, the registry's `edge_id = edge-01`. This matches what the
warfighter sees in their other systems (the source of truth).

**But**: if the system observes asset-X's data flowing through
edge-02's aggregator (or its position is nowhere near edge-01's FOB),
the registry **flags this as `divergent = true`** and stores the
observed reality in `observed_edge_id`. The asset is rendered on the
SPA at its STATIC assigned edge (matching the warfighter's mental
model), but is highlighted as **CM-divergent** — "this asset is
assigned to edge-01 but we're seeing it at edge-02; either the
assignment is wrong or the asset moved without being re-assigned."

This is the right behavior for a logistics system: surface the
divergence between intent and reality so the warfighter can correct
the source of truth (their external system, not OpenDDIL). OpenDDIL
itself never overrides the assignment — it just shows that the
assignment looks wrong.

`divergent` becomes a new `cm.edge_divergent` (or similar) constraining
factor on `asset_logistics_status` so existing severity rollups +
EngagementWatchlist surface it. Maintainer view gets a divergence
banner on the affected asset.

### Re-assignment policy

The registry's `edge_id` can change when:

- **The warfighter updates the static assignment** (admin write to
  the table). New row supersedes old; full audit via `assigned_at` +
  `assigned_by`.
- **The static assignment is removed and the asset is now
  observable** (becomes a `connection` or `position` assignment).
- A connection-based assignment **must wait** N consecutive minutes
  of observation at the new edge before flipping (avoids flapping
  on transient cross-edge traffic). N defaults to 5 minutes,
  tunable via [[ADR-0027]].

Re-assignment is event-sourced — the new row replaces the old PK in
the table, but a changelog topic (`asset-registry-events`) records
every assignment change with full provenance.

### Bootstrap latency (cold-start)

When telemetry arrives for an unknown asset_id (no registry row yet):

- The consuming service emits the event with `provenance.region_id =
  ""` and `provenance.edge_id = ""`. Marked as "registry-pending"
  via an event-level annotation.
- The asset-registry-service receives the same event (or registers
  it via the telemetry topic it subscribes to), assigns, writes the
  row.
- Downstream consumers will see the assignment from the next event
  onward.
- The "first event" with empty provenance is dropped by the
  source-app's filter — accepted as a small bootstrap cost.
- **In production this is rarely an issue** because the static
  assignment table is pre-populated from the warfighter's external
  system. Sim-only quirk.

### Cache invalidation

Consumers (cm-service, logistics-fusion-service, faust-regional
source-app, projector) hold an in-memory `asset_id → (edge_id,
region_id)` cache for performance. **Cache updates flow via pub/sub,
not polling.**

- A new Kafka topic `asset-registry-events` carries one event per
  registry write (insert or update). Keyed by asset_id.
- Each consumer subscribes to this topic. On consume, it updates its
  cache and emits any side effects (e.g., re-routing in-flight
  events). No polling overhead. Sub-second propagation.
- Initial cache load is a bulk `SELECT * FROM asset_registry` on
  service startup. After that, the changelog is the only update
  source.

Rationale for pub/sub over polling: the registry table is small
(N=number of assets, ~1k for the demo, ~10k in production) but the
read frequency in each consumer is HIGH (one lookup per event,
hundreds of thousands per minute). A polling refresh introduces
latency between operator-action and system-behavior; pub/sub keeps
the consumer cache always current at a fraction of the cost.

### Audit and observability

- `assigned_at`, `assigned_by`, `assignment_source` on the row →
  who/when/how for the current assignment.
- `asset-registry-events` topic → full history with every prior
  assignment retained (Kafka retention configurable).
- Postgres views surface "divergent assets" (`SELECT * FROM
  asset_registry WHERE divergent`) and "recently re-assigned"
  (`ORDER BY assigned_at DESC LIMIT N`) for SPA panels.

## Consequences

### Positive

- Single algorithm location for asset→edge/region computation. FOB
  list changes, policy changes, new assignment sources — all land in
  one service.
- Decouples consumers (cm-service, logistics-fusion, source-app,
  projector) from the assignment LOGIC. They just read.
- Honors the production model: warfighter's static assignment wins.
- Surfaces divergence as a first-class logistics signal — turns a
  potential silent failure into an operator-actionable workflow item.
- Future warfighter-UI write path: one HTTP/Restate handler against
  one table.
- The registry is also the natural home for connection-based
  assignment that DIS-only stationary sensors should use (their
  position never tells you a region; their data ARRIVAL location
  does).

### Negative

- New service to build, deploy, monitor (`asset-registry-service`).
- New table + Atlas migration + projector update + 4 service
  modifications (cm-service, logistics-fusion, faust-regional
  source-app, projector). Coordinated rollout.
- During the rollout window, both old (each-derives) and new
  (registry-driven) paths must coexist. Plan migration carefully.
- Bootstrap latency adds a small "first event lost" window per
  unknown asset. Acceptable.

### Neutral

- Couples cm-service, logistics-fusion, source-app to the registry's
  pub/sub topic shape — versioning matters.
- Establishes "shared cached registry with pub/sub invalidation" as
  a reusable pattern for other system-global facts that consumers
  need to look up frequently. Possible follow-ons: asset platform
  variant catalog, baseline catalog.

## Implementation phasing

1. **Phase 0 — stopgap (demo unblock)**: `faust-regional` source-app
   reads `telemetry_latest_state.region_id` from postgres directly
   (cached 30s, polled). Single-service band-aid. Unblocks Regional
   panels for the demo without the full registry. Documented as
   throwaway.

2. **Phase 1 — registry table + service**: Implement the table,
   stand up `asset-registry-service` with the position-based
   assignment policy ported from `edge_assignment.py`. Publish
   `asset-registry-events` topic. Don't change consumers yet.

3. **Phase 2 — consumer migration**: cm-service, logistics-fusion,
   source-app subscribe to the registry topic, populate their
   caches, stamp `provenance.edge_id` + `provenance.region_id` on
   outgoing events. Projector reads registry instead of computing
   locally.

4. **Phase 3 — static-assignment input**: HTTP/admin API to write
   `assignment_source = 'static'` rows. Wire from the SPA's
   future warfighter-input UI. Begin enforcing static-wins
   priority + divergence flagging.

5. **Phase 4 — re-assignment + divergence UI**: Add the
   N-minutes-of-observation re-assignment rule. Add the
   `cm.edge_divergent` constraining factor. Add the Maintainer-side
   divergence banner.

## Related

- [[ADR-0027]] — Runtime settings table for tunables (different
  concern, similar pub/sub + cache pattern)
- `openddil-stack/projector/src/edge_assignment.py` — current
  position-based logic that becomes the position-source policy
- `openddil-tactical-agents/regional/source_app.py:277-279` — the
  positive-match filter that currently drops 100% of empty-region
  events
- `openddil-stack/schema/migrations/` — where the new
  asset_registry migration lands
