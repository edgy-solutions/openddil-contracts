# ADR-0022: OpenDDIL Is Hierarchical Aggregation; the Current Topology Is a Collapsed Expedient

## Status

Accepted — 2026-05-14

## Context

OpenDDIL is **hierarchical streaming aggregation**. Edges produce; regional
hubs combine the edges beneath them; HQ combines the regionals beneath it.
That tiered aggregation tree — edge → regional → HQ — is the architecture,
and it is the reason Redpanda was chosen over a simpler request/response
store: each tier is a stream processor that consumes its children and
produces a rolled-up view for its parent. It is a hard requirement for the
eventual demo, not a nice-to-have.

**The current topology does not implement this.** Phases 4a/4b stood up the
read path the shortest way: one edge, one `openddil-projector`, one flat
Postgres read-model. Phase 4c then built three role-aware views —
maintainer, regional, HQ — on top of that single flat dataset. Those views
*look* hierarchical but are not: "regional" filters the same single asset
pool, "HQ" regroups the same pool. **The aggregation hierarchy currently
exists only as a UI presentation layer over a non-hierarchical backend.**

ADR-0021 caught one face of this — the edge→HQ transport *hop* had been
collapsed — and restored the hop. It did not catch that the whole
*aggregation tree* had gone flat. The two are related but distinct: ADR-0021
is about a severable transport link existing; this ADR is about there being
genuine per-tier aggregation on either side of such links. The "multi-edge
teleport" capability lost somewhere in earlier phases is a *symptom* of the
flat backend, not a separate gap.

Collapsing to a single flat tier was a reasonable expedient — getting the
read path working needed a simple projector first, and a flat dataset was
the fastest route to three views on screen. The risk is not the collapse
itself. **The risk is letting the flat assumption harden into places that
are expensive to reverse**: the schema, the projector, the aggregation
logic, and — most urgently — the ALCS/EAGLE egress bridges about to be
built, which are the work most likely to bake "there is one flat pool" into
an external contract.

## Decision

**OpenDDIL's architecture is edge → regional → HQ hierarchical streaming
aggregation. The current single-flat-tier topology is a deliberately
recorded expedient, and full hierarchical restoration is a committed future
phase — not a stretch goal.**

Until that phase lands, all work is bound by the following **"do not harden
the flat assumption" constraints**. This list is the operative part of the
ADR: it turns "be careful about the hierarchy" into a checkable set of
rules that apply to every change between now and hierarchical restoration.

1. **Per-asset schema rows carry edge/region provenance.** Every per-asset
   read-model table has explicit `edge_id` / `region_id` columns. They are
   hardcoded to a single default (`edge-01` / `region-01`) for now and
   nothing reads them yet — the point is that every shape, rollup, and
   egress bridge written from here to the hierarchy phase is written
   against a schema that *already has the echelon dimension*. This is the
   Quantity-everywhere lesson from Phase 2.5: get the schema shape right
   during the build phase even when the values are trivial, because
   retrofitting a structural dimension after consumers exist is the
   expensive path. *(Done in Phase 4d — see "Implemented so far".)*

2. **The projector stays provenance-aware in shape, even while running
   single-tier.** The projector emits `edge_id` / `region_id` on every
   per-asset write *explicitly*, rather than leaning silently on a DB
   column default. When the hierarchy phase lands, only the *value source*
   changes (a per-tier deployment config, or a field on the inbound
   message) — the handler signature and the row schema do not. A projector
   that "doesn't know about echelons at all" is the hardened-flat failure
   mode this prevents.

3. **Aggregation logic is written as "roll up the children of this node,"
   not "roll up everything."** Any fleet rollup, severity summary, or
   constraining-factors aggregation — UI-side or backend — must be
   expressed as an operation over *the children of a given node*, even
   when, today, the only node is the single flat root and "its children"
   is the whole pool. Code that hardcodes "aggregate the entire asset
   list" has to be rewritten at the hierarchy phase; code that aggregates
   "this node's children" just gets a real tree handed to it.

4. **Egress bridges (ALCS/EAGLE) carry echelon context.** Any bridge that
   exports OpenDDIL data to an external system must include the originating
   echelon (edge/region, or a node path) in what it emits or in its
   addressing. An egress contract that assumes a single flat source is the
   most expensive instance of the hardened-flat assumption to reverse,
   because the cost of changing it is borne by an external consumer.

Any change that violates one of these four constraints is, by this ADR, a
deliberate architectural decision and must be recorded as its own ADR —
never slipped in as a side effect of building something else the short way
(the same rule ADR-0021 set for the transport hop).

### Implemented so far (Phase 4d)

- **Constraint 1** — `edge_id` / `region_id` (`text NOT NULL`, defaults
  `edge-01` / `region-01`) added to all five per-asset read-model tables:
  `asset_cm_state`, `asset_logistics_status`, `telemetry_latest_state`,
  `asset_telemetry_windows`, `tactical_events`. Atlas migration
  `20260514183155_phase4d_origin_node_provenance.sql`, an Expand-phase
  pure-`ADD COLUMN` change — existing rows backfill to the defaults.
- **Constraint 2** — `openddil-projector` `handlers/base.py` provides
  `origin_provenance()`; every per-asset handler spreads it into its
  `Write.row`. Env-overridable via `OPENDDIL_EDGE_ID` / `OPENDDIL_REGION_ID`
  for a future per-tier deployment.

Constraints 3 and 4 are forward-looking — they bind the aggregation work
and the ALCS/EAGLE bridge work that has not yet been built.

## Consequences

**Pros**

- The hierarchy is now a written, checkable invariant rather than an
  unstated assumption that quietly eroded across 4a–4c. ADR-0021 protected
  one hop; this ADR protects the whole tree and makes "don't harden the
  flat assumption" a four-item checklist anyone can apply to a diff.
- The schema and projector are already shaped for the hierarchy. When the
  restoration phase lands, the per-asset read model does not need a
  migration that adds a structural dimension under live consumers.
- The ALCS/EAGLE egress work — the highest-risk place to bake in the flat
  assumption — now starts with constraint 4 already on the table.

**Cons**

- `edge_id` / `region_id` are dead columns today: written, never read.
  This is intentional carrying-cost, paid now to avoid a retrofit later.
- The four constraints are partly enforced by review discipline, not by a
  test. Constraints 1 and 2 have schema/unit-test coverage; 3 and 4 rely
  on this ADR being consulted when aggregation and egress code is written.
- It names a committed future phase without scheduling it. The risk is the
  phase slipping indefinitely while the "temporary" flat topology accretes
  consumers — which is exactly the failure mode the four constraints exist
  to make survivable.

**Rejected alternatives**

- *Leave the hierarchy as a UI-only presentation layer and call it done.*
  Rejected: it makes the product's core architecture — the reason Redpanda
  is in the stack — a screen-deep illusion. Same failure ADR-0017
  ("no orphan mocks") and ADR-0021 ("topology claims are verified by
  running them") reject in their own domains.
- *Restore the full hierarchy now, before continuing Phase 4.* Rejected as
  out of scope and not required to keep the logistics demo moving. The
  four constraints let Phase 4+ proceed without hardening the flat
  assumption; the restoration itself is a deliberate later phase.
- *Add the provenance dimension later, when the hierarchy phase starts.*
  Rejected — this is the expensive path the Phase 2.5 Quantity rollout
  taught us to avoid. Retrofitting a structural column after shapes,
  rollups, and egress bridges already consume the tables means changing
  every consumer at once.

## Related

- **ADR-0021 — The Edge→HQ Topology Is Load-Bearing.** Named one face of
  this: the transport *hop* must exist and be severable. This ADR names
  the whole thing — the *aggregation tree* the hops connect — and turns
  it into a checklist. ADR-0021's single-hop topology note is a specific
  instance of constraint 3 (the regional/HQ buffer numbers move in
  lockstep because there is no real regional tier yet).
- **ADR-0019 — Single Kafka→Postgres Projector.** The projector is
  *per-tier* in the target architecture; constraint 2 keeps the one we run
  today shaped for that even though it currently runs single-tier.
- **ADR-0013 — Physical Quantity Consistency.** The precedent for
  constraint 1: get the schema shape right during the build phase even
  when the values are trivial.
- **ADR-0017 — UI Mock Components Self-Identify.** Same spirit applied to
  a different gap: the difference between a thing being real and a thing
  looking real on screen.

## Notes for future maintainers

- The provenance columns live in `openddil-stack/schema/schema.hcl` on all
  five per-asset tables; the projector writes them via `origin_provenance()`
  in `openddil-projector/src/handlers/base.py`.
- If you are writing fleet-aggregation logic (UI or backend) or an egress
  bridge, constraints 3 and 4 apply to you directly — read them before
  you start, not after.
- "The hierarchy phase" is referenced but unscheduled. If you are planning
  phases, this is the ADR that says it is committed work.
