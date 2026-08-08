# Audit — severance-tolerance inventory (all services)

**Date:** 2026-08-08 · **Box:** half-day reading task, one table, no fixes
**Companion to:** ADR-0032 (presentation-plane reachback), ADR-0034
(detection-plane reachback), `PRINCIPLES.md` §Locality

## Why

ADR-0022 stated severance tolerance for the **data plane** and
implemented it there. Two other planes were later found non-tolerant —
**presentation** (ADR-0032) and **detection** (ADR-0034) — and both were
found *by accident*, from unrelated investigations. Three lucky finds is
not an audit methodology.

This sweep converts "planes we happened to check" into a map: every
service, where it runs, what it reads, where it writes, whether it
survives losing its uplink — plus **external runtime dependencies**,
which is where the Restate coupling that blocked Arc 1 Phase 3 came
from.

**Classification key**
`TBC` tolerant-by-construction (local inputs, local outputs) ·
`TBB` tolerant-by-buffering (degrades gracefully, catches up) ·
`NT` **non-tolerant** (needs the uplink to do its job) ·
`n/a` not applicable (root-tier or infrastructure by nature)

## Inventory

| Service | Chart | Tier | Reads | Writes | Ext. runtime dep | Class |
|---|---|---|---|---|---|---|
| `sensor-ingest` | edge | leaf | UDP/HTTP ingress (local) | edge broker | — | **TBC** |
| `redpanda-connect` | edge | leaf | local ingress | edge broker | — | **TBC** |
| `redpanda-edge` | infra | leaf | producers | local log | — | **TBC** |
| `faust-edge` | edge | leaf | edge broker | edge broker | — | **TBC** |
| `projector-<edge>` | edge | leaf | **edge broker** | **root postgres** | postgres (root) | **NT** ⚠ |
| `edge-hq-bridge` | edge | leaf | edge broker | root broker (via toxiproxy) | — | **TBB** (buffers by design — the DDIL mechanism) |
| `logistics-sim` | logistics-sim | root | root+edge brokers | edge brokers | — | n/a (synthetic producer) |
| `faust-regional` | regional | intermediate | **child brokers** | **root broker** | — | **NT** (no local broker — ADR-0032 §a) |
| `logistics-fusion-service` | hub | root | **child brokers** (via Restate subs) | **root broker** | **Restate** | **NT** ⚠ (ADR-0034 finding) |
| `cm-service` | hub | root | child brokers (via Restate subs) | root broker | **Restate** | **NT** ⚠ (same shape — see below) |
| `asset-registry-service` | hub | root | root broker | root postgres | — | n/a (root-tier registry, ADR-0028) |
| `restate-server` | hub | root | — | own PVC | — | n/a (root-only runtime) |
| `restate-hub` | hub | root | root broker | Restate | Restate | n/a |
| `projector-hq` | hub | root | root broker | root postgres | — | n/a |
| `electric-sync` | hub | root | root postgres | SSE to clients | postgres | n/a today → **becomes tier-local in Arc 1** |
| `frontend` | hub | root | Electric (root) | — | Electric | **NT** ⚠ (ADR-0032 finding; Arc 1 fixes) |
| `postgres-hq` | infra | root | — | — | — | n/a |
| `redpanda-hq` | infra | root | — | — | — | n/a |
| `toxiproxy` | infra | root | — | — | — | n/a (the sever mechanism itself) |
| `topic-init` | infra | all brokers | — | — | — | n/a (install-time Job) |

## Findings

**1. The two known gaps are confirmed and correctly classified** —
`frontend` (presentation) and `logistics-fusion-service` (detection).
Arc 1 addresses the first; the second is the open a/b/c decision.

**2. A third instance of the same shape: `cm-service`.** It is a Restate
Virtual Object (`restate.VirtualObject("AssetCM")`), deployed once at
root, consuming child brokers via Restate subscriptions, producing to
the root broker — **structurally identical to fusion.** So a severed
tier also gets **no CM state recomputed** while severed.

This is the third plane-instance found, and it is the answer to "will
the sweep surface another one": **yes, and it is fusion's twin.** It
matters for the a/b/c decision because whatever resolves fusion
resolves cm-service by the same mechanism — which *doubles the value* of
option (b) and *doubles the footprint* of option (a) (or at least
amortises one Restate per tier across two services, if (a) is chosen).

**3. `projector-<edge>` is the reachback in its purest form** — it reads
a **local** broker and writes a **root** database. It is the component
Arc 1 is already fixing, and it is worth noting that its non-tolerance
is *write-side*: the data reaches it fine during severance; it simply
cannot store it anywhere the local tier can read.

**4. `faust-regional`'s non-tolerance is structural, not incidental** —
it has no local broker to read from, per ADR-0032 §a. Consistent with
that ADR's decision not to place stores at intermediate tiers in this
deployment.

**5. External runtime dependencies are concentrated, not scattered.**
Only **Restate** appears as a coupling that constrains tier placement,
and it constrains exactly two services — both of which are the
detection-plane instances. No other service carries a comparable
dependency. That is good news for the generalisation: distributing the
analytics plane is a *two-service* problem, not a stack-wide one.

## Conclusions

- **ADR-0022's invariant is now mapped rather than repeatedly
  rediscovered.** Four `NT` entries, all explained, none surprising
  after the fact.
- **One new instance found** (`cm-service`), which is the sweep paying
  for itself.
- **Nothing here changes the a/b/c options**; it changes their *scope* —
  both fusion and cm-service ride whichever mechanism is chosen.
- Not fixed here, per the box.

## Blocked / not covered

- Live verification of any classification (no populated-cluster access —
  see `BRIEF-2026-08-08-per-tier-severity.md` §Blocked). This table is
  derived from charts and source, not observed behaviour under an actual
  sever.
- Egress connectors and customer-overlay components are deployment
  overlay, not core chart, and are out of this sweep's scope.
