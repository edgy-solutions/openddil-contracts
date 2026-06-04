# ADR-0027 — Runtime-configurable tunables via shared settings table

## Status

Proposed (2026-06-04). Implementation deferred until cross-tunable
demand surfaces — see "Deferral rationale" below.

## Context

Several services in the OpenDDIL pipeline hold numeric tunables that an
operator might reasonably want to change at runtime without redeploying
or restarting a pod. The first concrete case surfaced in field debug
on 2026-06-04:

- `logistics-fusion-service`'s `thresholds.ammo_low_count` (default 5)
  decides when `inventory.ammo_low` factors fire. The customer sim
  publishes static `ammo: 200` per launcher, so no factors ever fire
  with the default. Operators wanted to bump the threshold mid-demo to
  see the EngagementWatchlist populate, without rebuilding the bundle
  or restarting the deployment.

The same shape will recur. Other tunables already in
`logistics-fusion-service/src/fusion/thresholds.py`:

- `ammo_pct_critical`, `ammo_pct_degraded` — telemetry-percentage bands
- `fuel_*` (eventual), `engine_hours_*`, `rul_*` — sustainment-driven
  thresholds

`faust-regional` aggregator has analogous polling intervals, top-N
caps, and emission cadences that might want runtime tuning.

The current adjustment path for `ammo_low_count`:

```bash
kubectl set env deploy/openddil-logistics-fusion-service AMMO_LOW_COUNT=20
# pod restarts, picks up new value
```

Works, but: requires kubectl access, restarts a pod (drops in-flight
events), and is not discoverable from the SPA. For a demo or operator
workflow, the friction is real.

## Decision

Adopt a shared `runtime_settings` table on the HQ postgres as the
canonical store for operator-tunable scalars. Each tunable is one row
keyed by a hierarchical string key:

```sql
CREATE TABLE runtime_settings (
    key         text PRIMARY KEY,
    value       jsonb NOT NULL,
    description text,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    updated_by  text
);

-- seed examples
INSERT INTO runtime_settings VALUES
  ('logistics-fusion.ammo_low_count',    '5',    'Below this round count, fire inventory.ammo_low'),
  ('logistics-fusion.ammo_pct_critical', '10.0', 'Below this percent of capacity, fire ammo.pct_critical'),
  ('logistics-fusion.ammo_pct_degraded', '25.0', 'Below this percent of capacity, fire ammo.pct_degraded');
```

Services that consume tunables:

- **Read on a short interval** (5–30s) from the table, refreshing an
  in-memory cache. Polling chosen over Restate signals because the
  read pattern is single-table-fits-in-memory and the cadence
  acceptable; no need for change-notification fan-out at this scale.
- **Fall back to env-var default** if the row is missing — keeps
  bootstrapping safe and lets services run before the table is
  populated.
- **Never block on the DB query** — if postgres is unreachable, the
  service keeps using its last cached value (or env-var fallback).

The SPA gets a `useRuntimeSetting(key)` Electric hook that subscribes
to the row, and a small "Tunables" panel (or per-card inline editor)
that writes to it. Writes can go through a thin admin HTTP API on
either logistics-fusion or a new admin service — TBD at implementation
time, not material to this ADR.

## Deferral rationale

Today there is exactly **one** tunable anyone has asked to change at
runtime (`ammo_low_count`). The env-var override path is acceptable
for that single case; building a settings table + cache + UI for one
knob would be premature abstraction.

This ADR is recorded now so:

1. The design space is captured durably while the context is fresh.
2. When the second or third tunable demands runtime tuning, the
   implementer doesn't re-derive the design — they pick this up.
3. Service authors adding new env-var-tuned thresholds can write the
   constant such that it's easy to swap to a settings-table read
   later (i.e., wrap in a `get_threshold(key, default)` helper now,
   even if `get_threshold` just calls `os.environ` for v1).

Trigger to revisit and implement:

- A second tunable surfaces with runtime-tuning need, OR
- An operator workflow requires changing a tunable from the SPA, OR
- A specific demo scenario needs threshold variation without pod
  restarts.

## Consequences

### Positive

- Single pattern for any tunable that wants runtime adjustment.
- Audit (`updated_at`, `updated_by`) baked in from row schema.
- Survives pod restarts (persistent in postgres).
- SPA-discoverable — operator doesn't need kubectl.

### Negative

- Adds one more table + one more polling loop per consumer service.
- Cache staleness window (5–30s) means SPA writes don't reflect
  instantly in service behavior. Acceptable for thresholds; not
  acceptable for hot-path config like routing rules.
- Doesn't help for cross-service atomic changes (e.g., bump two
  thresholds simultaneously and have both consumers see the new
  values at the same instant).

### Neutral

- Pairs with [[ADR-0028]] (asset registry centralization) as a class
  of "shared runtime state, written by an admin path, read by every
  consumer" patterns.

## Related

- [[ADR-0028]] — Centralized asset_registry for edge/region lineage
  (separate concern, same architectural pattern)
- `openddil-logistics-fusion-service/src/fusion/thresholds.py` — the
  current env-var-only tunables that would migrate first
