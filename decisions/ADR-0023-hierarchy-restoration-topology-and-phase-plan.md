# ADR-0023: Hierarchy Restoration — Topology and Phase Plan (Phase 6)

## Status

Accepted — 2026-05-16 — **Phase 6 plan.** Implements ADR-0022. No recipe;
the topology and phase structure are the decision. Per-sub-phase recipes
are separate deliverables reviewed at the start of each sub-phase.

## Context

ADR-0022 set the architectural invariant — OpenDDIL is edge → regional →
HQ hierarchical streaming aggregation — and named four "do not harden the
flat assumption" constraints. Phase 4d shipped constraints 1 and 2:
per-asset schema carries `edge_id` / `region_id`, projector writes them
explicitly via `origin_provenance()`. Constraints 3 (aggregation logic =
"children of this node," not "everything") and 4 (egress bridges carry
echelon context) are unimplemented; today every UI rollup is a SQL
group-by over the flat pool, and no egress bridges have been built yet.

ADR-0021 set the single edge↔HQ transport hop and named the single-hop
simplification explicitly so the lockstep regional/HQ buffer numbers
could not be mistaken for a wiring bug. ADR-0019 chose a single
Kafka→Postgres projector at HQ rather than per-tier projectors.

A scope assessment ahead of this ADR put the lift at **5–8× the size of
Phase 4c.5**, across 5–6 repos, with one new container image. That size
makes hierarchy restoration the largest remaining phase and rules it out
of pre-stakeholder-demo scope. The stakeholder demo will land on the
flat topology with hierarchy framed as committed near-future
architecture — that decision is acknowledged here so the topology can be
designed for correctness rather than speed.

The assessment also surfaced that constraint 3 cannot be verified by
schema or projector alone; it requires (a) a real regional aggregator
tier that does cross-asset rollups streaming-style, and (b) UI rewiring
to consume those rollups instead of the flat per-asset pool. Both are
new code, not retrofits.

## Decision

**Hierarchy restoration is Phase 6, designed and built as the topology
ADR-0022 named. Three edges across two regions, one HQ, one new
streaming-aggregator tier (`faust-regional`), single edge-aware
projector at HQ with provenance sourced from the message stream, and a
four-sub-phase split with an observable checkpoint at the end of each
sub-phase.**

### Topology

- **3 edges across 2 regions, 1 HQ.** Minimum non-degenerate.
  Suggested layout: `region-east` carries `edge-01` + `edge-02`,
  `region-west` carries `edge-03`. A 2-edge / 1-region setup makes the
  regional→HQ hop a passthrough — visible but uninteresting — and would
  silently leave constraint 3 unverified at one of its two tiers.
  Don't compromise the topology down for effort.

- **Per-edge stack.** Each edge gets its own broker (`redpanda-edge-N`)
  plus its own per-asset pipeline: one `openddil-sensor-ingest` on a
  distinct UDP port (62040 / 62041 / 62042), one `redpanda-connect`
  DIS-mapper instance, one `faust-edge` instance with
  `OPENDDIL_EDGE_ID=edge-N` and `OPENDDIL_REGION_ID=region-east|west`.
  All same images as today — new **instances**, not new images.

- **Per-region aggregator.** Each region runs one `faust-regional`
  instance — a **new container image** — that consumes its assigned
  edges' topics and emits rolled-up topics. This is the only new image
  to scan in Phase 6; everything else is more instances of already-
  approved images.

- **Single HQ tier.** One `redpanda-hq`, one `postgres-hq`, one
  `openddil-projector`. No per-tier Postgres; the projector consumes
  edge-attributed per-asset events AND regional-rolled-up events and
  writes both into the same HQ Postgres. The per-asset tables already
  carry `edge_id` / `region_id` from Phase 4d; the new regional-aggregate
  tables get their own DDL.

**Source of truth for `edge_id` / `region_id` values.** Values are
assigned by the deployer in deployment configuration — compose env-vars
(`OPENDDIL_EDGE_ID`, `OPENDDIL_REGION_ID`) in the demo, per-customer
deployment manifests in production. OpenDDIL imposes no namespace; the
deployer chooses customer-meaningful identifiers reflecting their
organizational or physical edge structure (e.g. `FOB-ALPHA`,
`1HBCT-MMC`, `edge-01`, or any value meaningful to the customer's
fleet). The defaults `edge-01` / `region-01` baked into
`origin_provenance()` exist for the current single-tier deployment and
the test harness; multi-tier deployments override them on every edge
and regional container.

**Configuration-consistency contract.** The deployer is responsible for
three properties of the assigned values:

- (a) each edge stack has a distinct `OPENDDIL_EDGE_ID`;
- (b) each edge's `OPENDDIL_REGION_ID` matches the `region_id` of
  exactly one running `faust-regional` instance;
- (c) each `faust-regional` consumes the brokers of all and only the
  edges claiming its region.

Violations are detectable in monitoring — an edge with a duplicate ID
would show 2× expected throughput on its per-asset topics; an edge
with an orphan `region_id` would produce events that never roll up
through any `faust-regional`; a `faust-regional` consuming an
unintended edge would show its rollups counting assets that "shouldn't
be there." But none of these are enforced automatically at runtime.
This is a **deployment-time contract**, the same pattern as Kubernetes
node labels or Kafka cluster IDs: the runtime trusts the assignment,
operations verifies it.

### Projector

**Single edge-aware projector at HQ, value source switches from
env-constant to message-field. ADR-0019 stands.**

Phase 4d's `origin_provenance()` returns env-constant defaults today.
The Phase 6 change is mechanical: the per-asset handlers read
`edge_id` / `region_id` from the inbound message (stamped at the edge
or regional aggregator) instead of the projector's environment. The
row schema does not change. The handler signature does not change.
ADR-0022 constraint 2 was written with this transition in mind — the
"or a field on the inbound message" parenthetical.

For the regional rolled-up topics, the projector grows three **new
handler modules** — additive, not a refactor — that write into three
new per-region aggregate tables. The existing 5 per-asset handlers are
unchanged.

### Regional aggregation — real streaming, three named topics

**Real streaming aggregation, not passthrough-with-attribution.**

Passthrough-with-attribution (regional just forwards events to HQ
tagged with `region_id`, all aggregation in SQL group-by) was rejected
in the assessment for one reason: it leaves constraint 3 unverified.
The whole point of the hierarchy is that each tier *does* its tier's
work as a stream processor; SQL-grouping the flat pool at HQ proves
nothing about the streaming architecture. The 5–8× lift is accepted
specifically to avoid this paper-tag failure.

The regional aggregator emits **three rolled-up topics**, scoped as the
bounded minimum that exercises real aggregation without becoming a
fusion-of-fusions:

1. **`region-fleet-summary`** — per-region severity counts. Per emit:
   `{region_id, nominal: int, degraded: int, critical: int,
   comm_lost: int, asset_count: int, observed_at}`. Computed from
   `asset-logistics-status` + `asset-cm-state` streams keyed by
   asset_id, rolled up by region_id.

2. **`region-top-factors`** — per-region top-N constraining factors by
   frequency. Per emit: `{region_id, factors: [{factor_id, count,
   severity_breakdown}], observed_at}`. Computed from the
   `constraining_factors` of `asset-logistics-status` events.

3. **`region-wear-trends`** — per-region aggregate wear trend. Per emit:
   `{region_id, components: [{component_id, mean_rul_remaining,
   asset_count, observed_at}]}`. Computed from `derived-sustainment` +
   measured-sustainment streams.

Each topic is keyed by `region_id`; each region's `faust-regional`
maintains durable per-region Tables (RocksDB-backed, changelog-
replicated — same partition-count invariant discipline as
`prognostics_accumulators`).

These three were chosen because:
- Severity counts is the headline rollup every commander wants.
- Top-N factors is the rollup that surfaces *what's actually wrong* in
  the region (not just *how bad*).
- Wear trends is the only one that pulls from derived sustainment —
  proves the Phase 5 prognostics output participates in the hierarchy.

### Phase split — 6a / 6b / 6c / 6d, observable checkpoint per sub-phase

Each sub-phase ends with a runnable verification of its own claim,
matching the Phase 5 step 1 / step 2 discipline (test_35 verified the
engine; test_39 verified the integration). No sub-phase ships with a
"trust me, the bytes are right" debt to the next.

- **Phase 6a — Multi-edge infrastructure + DIS partitioning.**
  Stand up 3× `redpanda-edge`, 3× `faust-edge`, 3× `openddil-sensor-
  ingest` on distinct UDP ports, 3× `redpanda-connect` DIS-mappers.
  Edge-tier bridges produce to HQ tagged with `edge_id`. Projector
  starts reading `edge_id` from message-field rather than env. Hero
  scenario test split into 3 non-overlapping entity ID ranges per edge.

  **Observable checkpoint:** a small debug HQ panel that shows per-edge
  attribution — for each asset, which `edge_id` it came in on, sourced
  from the now-message-field provenance. *Not a polished view; a
  one-glance verification that edge attribution flows through the
  pipeline end-to-end.* Equivalent in scope to test_35 + a single
  visible panel.

- **Phase 6b — `faust-regional` aggregator + three rolled-up topics.**
  Build the new `faust-regional` image, run 2 instances (one per
  region), each consuming its assigned edges' topics. Emit the three
  rolled-up topics. Projector grows 3 new handler modules; 3 new
  per-region aggregate tables via Atlas migration. Constraint 3 starts
  being exercised on the wire.

  **Observable checkpoint:** a debug shape against ONE rolled-up topic
  (suggest `region-fleet-summary` — simplest) — a single panel showing
  the per-region severity counts live, updating as the test scenarios
  flip asset states. Verifies the streaming aggregator does real work,
  not the architectural polish of 6c.

- **Phase 6c — UI rewiring + maintainer-view per-edge scope.**
  Regional UI panel reads `region-fleet-summary` / `region-top-factors` /
  `region-wear-trends` via new hooks. HQ panel rolls up the regionals.
  Constraint 3 fully exercised at the UI tier. **Maintainer view gains
  per-edge scope** (see *Maintainer-view per-edge scope* below).

  **Observable checkpoint:** stakeholder-demo-ready hierarchy walk.
  Regional and HQ panels show genuine aggregated values; maintainer
  view scoped to a selected edge with an animated transition when the
  edge is switched.

- **Phase 6d (optional / scope-permitting) — cleanup and forward
  preparation.** Customer-overlay per-edge AMQP routing
  (`openddil-customer-bundle` + customer-overlay overlay); ADR-0019
  re-examination if Phase 6 surfaced reasons; ALCS/EAGLE constraint 4
  prep work (egress bridges with echelon context). Each item is
  individually scope-checked.

### Maintainer-view per-edge scope (6c deliverable)

The maintainer view today shows the global fleet — a slice of a flat
dataset. In a real deployment, a maintainer at edge-01's FOB sees
edge-01's assets only; they cannot see assets at FOB Bravo's edge-02.
The hierarchy renders correctly only if each edge has its own local
view, regional aggregates across its edges, HQ aggregates across
regionals.

**The maintainer view becomes per-edge-scoped in 6c.** Production
scope is fixed by where the maintainer physically is. Dev/demo scope
is a **pulldown switcher control in the MAINTAINER header** that
selects which edge the view is scoped to; the underlying mechanism is a
URL parameter (`?edge=edge-N`) so links and reloads are stable. The
pulldown scopes every ElectricSQL Shape subscription on the maintainer
page to `where edge_id = 'edge-N'`.

**Switching edges animates a transport-like transition** — visual
language of "you are physically moving to a different FOB," not a
plain refresh. This is the demo-narrative payoff: stakeholders watch
the maintainer view *travel* from FOB Alpha to FOB Bravo to FOB
Charlie, and the switching is the demonstration that the hierarchy is
real — each edge is its own scope rather than a slice of a flat
dataset.

The pulldown and animation are 6c spec, not 6c stretch. They are why
6c exists as a distinct sub-phase rather than being folded into 6b.

## Known simplification: per-region brokers

The decided topology runs three brokers total — `redpanda-edge-01`,
`-02`, `-03` plus `redpanda-hq`. **There is no per-region broker.**
Regional aggregators consume their assigned edges' brokers and produce
their rolled-up topics directly to `redpanda-hq` over per-region
severable bridges (each via toxiproxy).

A cleaner architecture would give each tier its own bus —
`redpanda-region-east`, `redpanda-region-west` between the edges and
HQ — with each hop independently severable at the broker level. That
**is** the eventual production target. The demo skips it because:
- It multiplies infra (3 → 5 brokers, 1 → 3 bridges per region pair).
- The per-region severability the demo needs is already achievable via
  per-region toxiproxy-mediated bridges to `redpanda-hq`.
- One simplification is easier to mark and lift than several.

**Same pattern as ADR-0021's single-hop note:** this paragraph exists
so no one later mistakes the absent regional brokers for a wiring
oversight, and so the production-target shape is captured before it
quietly becomes "the way it is." When the eventual production
deployment is scoped, the regional brokers go in by deliberate decision
referenced back to this paragraph — not by a side-effect realization
mid-build.

## Consequences

**Pros**

- ADR-0022 constraints 3 and 4 become *demonstrable*, not paper-tagged.
  Streaming aggregation does real work in `faust-regional`; UI rolls
  up children-of-this-node, not the whole pool.
- The schema, projector signature, and provenance dimensions are
  already in place from Phase 4d. No retrofit migration under live
  consumers.
- One new image (`faust-regional`) to scan; everything else is more
  instances of approved images. Scan-pipeline friendly.
- ADR-0019 stands. The projector grows additively; it doesn't fork
  per-tier.
- The maintainer-view per-edge scope makes the hierarchy a *narrative*
  the stakeholder can walk through, not just a table column.

**Cons**

- 5–8× the size of Phase 4c.5, across 5–6 repos. The largest remaining
  phase, accepted at honest cost rather than negotiated down.
- Cannot ship before the stakeholder demo on any reasonable timeline.
  The stakeholder demo lands on the flat topology with hierarchy
  framed as committed near-future architecture. Acknowledged
  trade-off; not a regret.
- The per-region-brokers simplification is a real architectural
  shortcut, deliberately taken and explicitly marked. If left
  unattended past the production-deployment scoping conversation it
  becomes the same hardening risk ADR-0022 was written to prevent —
  applied one tier up.
- Constraint 3 is fully verified only at the end of 6c. 6a and 6b each
  carry a partial verification (observable checkpoint per sub-phase),
  but the full "children of this node" guarantee lands with the UI
  rewiring.

**Rejected alternatives**

- **Passthrough-with-attribution** (regional just forwards events
  tagged with `region_id`; aggregation as SQL group-by at HQ).
  Rejected: leaves constraint 3 paper-tagged, doesn't exercise
  Redpanda's streaming-aggregation role, makes the hierarchy a schema
  detail rather than a runtime behavior. Same failure spirit as ADR-
  0017's "no orphan mocks" — the architecture would be real in the
  database and a slogan everywhere else.
- **2 edges across 1 region.** Rejected as degenerate: the regional→HQ
  hop becomes a passthrough, constraint 3 verified at one tier only.
  Save 1 edge instance worth of infra, lose half the architectural
  demonstration.
- **Per-tier projectors with per-tier Postgres.** Rejected: contradicts
  ADR-0019 without a corresponding benefit, multiplies the read-model
  surface, forces cross-tier UI queries. The 4d-shipped provenance
  columns are the cheaper path.
- **Restore the hierarchy in one monolithic phase** rather than 6a/6b/
  6c split. Rejected: no observable checkpoint between "stood up
  multi-edge infra" and "streaming aggregator produces rollups," which
  is the exact "trust me, the bytes are right" gap the project's
  verification discipline has been built against. The Phase 5 step 1 /
  step 2 split was the precedent.
- **Defer the maintainer-view per-edge scope to a follow-on.**
  Rejected: in production deployment, the maintainer view is per-edge-
  scoped by physical location — making it scoped only at follow-on
  time leaves the demo telling a story (global maintainer view) that
  is not how the product works. 6c is the right home.

## Related

- **ADR-0022 — Hierarchical Aggregation Is the Architecture.** The
  parent ADR; this one is its implementation. The four constraints
  defined there are the rules this topology delivers against —
  specifically, constraints 3 and 4 are the work this phase exists to
  do.
- **ADR-0021 — The Edge→HQ Topology Is Load-Bearing.** Set the
  precedent for the "known simplification" note pattern used here for
  per-region brokers. ADR-0021's single-hop simplification gets
  *resolved* by this ADR (the single hop becomes per-region hops).
- **ADR-0019 — Single Kafka→Postgres Projector.** Stands; the projector
  grows additively (3 new handler modules for the rolled-up topics)
  but does not fork per-tier.
- **ADR-0014 — Restate vs Faust Placement.** Cumulative / windowed
  aggregations belong in Faust — both the per-asset windows at the
  edge (`faust-edge`) and the per-region rollups at the regional tier
  (`faust-regional`). The new `faust-regional` is the same placement
  decision applied one tier up.
- **ADR-0024 — Multi-Cluster Faust Aggregator Pattern.** This ADR set
  the topology decision (one `faust-regional` instance per region,
  consuming its assigned edges' brokers); ADR-0024 captures the
  implementation pattern that emerged from §B's spike and live-stack
  diagnosis — Worker-composition of one aggregator App + N stateless
  source Apps + per-region fan-in topic, with uniform wrap-and-
  republish for ALL source clusters (including same-broker ones, per
  the heterogeneous-source-cluster rule). Read ADR-0024 before
  building any future regional-tier service.
- **ADR-0017 — UI Mock Components Self-Identify.** Same spirit: the
  hierarchy must be real, not a UI illusion. Rejected-alternative
  passthrough-with-attribution would have been an ADR-0017 failure
  applied to the architecture rather than to a panel.
- **ADR-0020 — Prognostics Derivation Engine (Phase 5).** Phase 5's
  `derived-sustainment` topic is one of the inputs to
  `region-wear-trends`. Phase 5 follow-up #7 (GLB asset rendering)
  slots after Phase 6 because per-platform 3D rendering written
  against the flat topology would have to be refactored for echelon-
  aware data anyway — defer is structural protection.

## Notes for future maintainers

- **The maintainer-view per-edge scope is 6c spec, not 6c stretch.**
  Pulldown control in the maintainer header, `?edge=edge-N` URL
  parameter, animated transport-like transition between edges. Scoping
  is by `where edge_id = 'edge-N'` on every ElectricSQL Shape
  subscription on the maintainer page. The animation is the demo
  payoff — make it deliberate, not perfunctory.
- **The per-region-brokers simplification is on a leash.** When the
  production-deployment scoping conversation happens, that paragraph
  is the entry point. Don't let it quietly become permanent.
- **One new image: `faust-regional`.** Add to the scan pipeline at 6b,
  not before — there's nothing to scan until the codebase exists.
- **Hero-scenario tests get a per-edge entity-ID partitioning.** Today
  the tests use a single entity range (e.g., 9994 in test_39). 6a
  splits that into per-edge non-overlapping ranges (e.g., edge-01:
  1000–1999, edge-02: 2000–2999, edge-03: 3000–3999) so each edge
  carries distinct assets and the regional aggregator has real
  cross-edge work.
- **`edge_id` / `region_id` go from dead columns to live columns at 6a.**
  Phase 4d wrote them; nothing read them. 6a is the first phase where
  reading them matters — the debug HQ panel for the 6a checkpoint, and
  the maintainer view scope at 6c.
- **Stakeholder demo lands on flat topology.** This ADR documents the
  hierarchy as committed near-future architecture. The demo narrative
  reflects this — not a deferred-with-no-plan stub.
