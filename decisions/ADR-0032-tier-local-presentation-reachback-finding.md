# ADR-0032 — Tier-local presentation: the reachback finding and the distributed read substrate

## Status

Accepted (2026-08-07). Phase 0 gate for Arc 1 — reviewed and amended.

Amended before acceptance (2026-08-07) after a framework-level
correction: the first draft read this deployment's broker-less
intermediate tier as a property of intermediate tiers. It is a Phase-6
implementation shortcut. The store decision is now stated as a
depth-independent conditional rule, the deliverable unit is named
tier-agnostically, and §Framework vs. instantiation records what is
currently hardcoded to three tiers. See ADR-0033 for the recursive tier
model itself.

## Context

### The finding

OpenDDIL's data plane is severance-tolerant by design (ADR-0021,
ADR-0022). Its **presentation plane is not**, and the gap was not
visible until the read path was traced against the deployed chart
rather than the architecture diagram:

- **All four projectors write to `postgres-hq`.** There are four —
  `projector-edge-01/02/03` and `projector-hq`. The per-edge projectors
  are edge-local *consumers* but HQ *writers*: each subscribes to
  `KAFKA_BROKERS = <its own edge broker>` and writes
  `POSTGRES_DSN = postgres://…@<release>-postgres-hq`
  (`openddil-helm/openddil-demo/templates/edge.yaml`).
- **`postgresHq` is the only relational store in the chart.** No
  per-edge Postgres exists.
- **The edge has state, but none of it is queryable.** Each edge broker
  carries its own copy of every topic (the topic-init pattern),
  including the compacted `telemetry-latest-state`, plus Faust table
  changelogs. The edge holds current per-asset truth; it has no
  relational surface over it.
- **The maintainer UI is served from HQ and reads HQ.** Under
  severance it freezes.

The consequence is an inversion the system should not have:

> **The persona closest to the equipment has the stalest view of it.**

A maintainer standing at a FOB, whose radar is emitting telemetry into
a broker fifty metres away, sees a frozen screen — because the screen is
fed from a database on the other side of the severed link. Meanwhile the
data they need is flowing, locally, into a topic they cannot query.

A second inversion follows: **today's severance indicators are HQ's view
of the edge, not the edge's view of itself.** The banner tells a
maintainer what HQ thinks about their link. It is derived from
bridge-group lag observed centrally. The maintainer's own tier has no
voice in its own status display.

### Why this is an ADR and not a bug

ADR-0022 established that hierarchical aggregation *is* the
architecture, and that tiers must keep functioning when the link above
them is cut. That invariant was stated for, and implemented in, the
**data plane**.

This ADR extends the same invariant to the **presentation plane**:

> A tier's operators must be able to see their own tier's truth using
> only that tier's resources.

That is a genuine architectural extension, not a defect fix. It changes
what a "tier" is — from *a place where data is processed* to *a place
where data is processed and presented* — and it introduces the first
HQ→edge data flow in an otherwise upward-only topology (§c). Both
warrant a recorded decision.

### Scope of Arc 1

Arc 1 delivers the substrate with **open access**. The policy sidecar
ships in the tier presentation node, healthy, and **decides nothing**; enforcement
is Arc 2 (ADR-0029). Shipping the seat now means Arc 2 adds rules to a
deployed component rather than adding a component.

This is a generic OSS capability — tier-local presentation for DDIL
environments. No deployment specifics appear here.

## Decision

### Framework vs. instantiation

OpenDDIL's design intent is an **unbounded recursive tier hierarchy**
(ADR-0033). Every tier is the same self-similar node: it manages the
tier below it (assets at the leaf, child nodes above that), rolls up its
subtree, and passes that rollup to its parent if it has one. **Tier
count and tier names are deployment configuration.** One deployment runs
edge→region→HQ; another runs edge→region→province→country; another adds
a cross-national tier above that. "HQ" is not a kind — it is the node
with no parent. "Edge" is not a kind — it is the node whose children are
assets rather than nodes.

Everything below decides for **this deployment's three-deep
instantiation**. Where a decision states a rule, the rule is
framework-level and depth-independent; where it states an outcome
(*which* tiers get what), that is configuration for this deployment.
This ADR is careful about the difference because an earlier draft was
not: it read this deployment's broker-less intermediate tier as a
property of intermediate tiers, which is a deployment artifact mistaken
for design.

**Currently hardcoded to three tiers** — named here so they are known
debt rather than assumed shape. Each is pointed at ADR-0033, not
resolved here:

| Hardcoding | Generic form |
|---|---|
| `edge_id` / `region_id` as named proto fields (ADR-0023) | Hierarchy-path addressing (node id + parent chain); `edge_id`/`region_id` is its two-level projection. Deepest and most expensive to move. |
| Named-tier components (`faust-regional`, projector tier parameters, helm's edge/region/hq structure) | One recursive node kind, instantiated per configured tier. |
| The collapsed intermediate broker | A broker-bearing middle tier wherever a deployment wants presentation or buffering there. |
| Three fixed UI views (maintainer / regional / HQ) | One presentation parameterized by "my tier + my subtree". |
| Aggregation semantics (ADR-0024) | Rollups must compose over *child-tier rollups*, not raw leaf streams — unbounded depth is rollup-of-rollups or it is nothing. Audit tracked in ADR-0033. |

### (a) Which tiers get stores — a conditional rule, not a tier-kind law

**The rule (framework-level, applies to any tier at any depth):**

> **Any tier MAY take the presentation kit. A severance-tolerant
> presentation at tier N requires tier N's own broker.**

The requirement is structural and it is the load-bearing discovery of
this ADR: a store is severance-tolerant only when a local projector
reads a *local* topic set and writes a *local* store, so that every
element survives the link being cut. A tier with no broker of its own
has no local topic set to project from — its store would be fed across
the very links whose severance it exists to survive, arriving stale
exactly when it is needed while still costing footprint and a migration
surface.

**The instantiation (this deployment only):**

| Tier | Broker today | Kit here | Why |
|---|---|---|---|
| Leaf (`edge-*`) | Yes | **Yes** | Broker present + operators physically at the site. The maintainer case is this ADR's finding. |
| Intermediate (`region-*`) | **No** | Not here | `templates/regional.yaml` renders one Deployment — `faust-regional-<region>` — consuming from **child** brokers and producing to the **parent** broker. No broker of its own, so the rule is not satisfied. |
| Root (`hq`) | Yes | Already exists | Unchanged. |

**The intermediate tier's broker-less shape is an implementation
shortcut, not a property of intermediate tiers.** The Phase-6 aggregator
was built to consume child brokers directly and produce to the parent's
broker, which was sufficient when no intermediate presentation was
required. A deployment that wants presentation or buffering at an
intermediate tier gives that tier a broker, and the rule then admits the
kit there with no framework change.

**Revisit condition:** any deployment that configures a broker at an
intermediate tier. Not "regions change kind" — the kind was never the
variable.

**What this ADR explicitly does NOT decide:** that intermediate tiers
are store-less as a category. Tier names and tier count are deployment
configuration (see §Framework vs. instantiation); a deployment running
edge→region→province→country may put brokers, stores, and operators at
any depth it chooses.

**Footprint in this deployment:** N leaf tiers × the tier presentation
node. At the current three-leaf topology that is three additional node
stacks. See (d).

### (b) Edge schema scope — identical DDL, content scoped by construction

**Every tier-local store is created with the full, identical schema.**
Not a per-tier subset.

The scoping the recipe identified is real but it operates on *content*,
not on *DDL*: an edge projector consuming only its own edge's topics
produces an edge-scoped store by construction — it can only write rows
for assets whose telemetry flowed through that edge. Region-rollup
tables (`region_fleet_summary`, `region_top_factors`,
`region_wear_trends`) exist as empty tables at an edge because their
producer (`faust-regional`) writes to HQ.

Identical DDL is chosen deliberately:

- It matches the Phase 1 rationale — every store born with final schema,
  one migration definition rather than N variants.
- It keeps the read-seam contract (ADR-0031 §2.2) **tier-independent**:
  the same query works at edge and HQ, which is what lets that contract
  be written once.
- Divergent per-tier schemas would make the migration matrix N-
  dimensional and would make "does this table exist here?" a runtime
  question for every consumer.

Empty tables cost approximately nothing. Schema variants cost
permanently.

**One table is not populated by construction and needs an explicit
flow:** `asset_registry` (ADR-0028) is written only at HQ. That is (c).

### (c) HQ→edge reference-data flow — compacted `registry-sync` topic

`asset_registry` is the canonical asset→edge_id→region_id mapping
(ADR-0028), written by one service at HQ. Edge-local reads need it —
without it an edge store cannot resolve its own assets' lineage.

**Decision: HQ publishes the registry to a compacted Kafka topic,
`registry-sync`; each edge projector consumes it and maintains the local
`asset_registry` table.**

Compacted-topic shape is chosen because:

- It is the mechanism the system already uses for
  "latest-state-per-key" reference data (`telemetry-latest-state`,
  `asset-cm-state` are all compacted); no new distribution primitive.
- Compaction means a newly-provisioned or long-severed edge replays to
  current state from the topic's retained tail, without a bespoke
  bootstrap path.
- Under severance the tier simply stops receiving updates and **retains
  last-known state**. Stale-but-present is the correct DDIL behaviour;
  absent is not.

**On the two staleness stances in this ADR** — this section accepts
stale-but-present, while (a) rejects a broker-less store *because* it
would be stale. Both are right, and the distinction is **data
velocity**: slow-moving reference data (assignment lineage) degrades
gracefully under staleness and remains useful; fast-moving operational
telemetry under staleness becomes actively misleading — an operator
acting on a frozen picture believing it live. Recorded so a future
reader does not cite one decision against the other.

Config-rhythm distribution (registry as a mounted ConfigMap, updated on
the deploy cadence) is the **fallback** if the topic path proves
problematic, and is recorded here so the fallback is a known option
rather than an improvisation.

**This is the arc's one new flow direction**, and it has turned out to
be **general infrastructure rather than registry-specific plumbing.**
The topology has been upward-only (edge→region→HQ); `registry-sync` is
the first deliberate HQ→edge flow. It is designed here, in the document,
rather than discovered during implementation.

**Passengers on this seam, in order of arrival:**

1. `asset_registry` reference data (this section).
2. **Policy bundles** — per-tier Topaz policy (ADR-0029 §6).
3. **ML model artifacts** — versioned weights for durable-workflow
   detectors (ADR-0034 §Serialization).
4. **Sovereignty workflow definitions** — per nation/department
   maintainer process procedures (ADR-0034 §The two planes).

All four share the same DDIL property, which is why one seam serves
them: **artifact distributed ahead of time, execution local, severed
tier keeps working.** Passengers 2–4 are labelled artifacts subject to
releasability policy, not merely private files.

Two constraints bind it:

1. **Reference data only.** `registry-sync` carries slow-changing
   assignment lineage. It is not a general downward channel, and
   proposals to put operational data on it are a separate decision.
2. **Downward flow must not become a dependency for local operation.**
   An edge that never receives a registry update must still serve its
   maintainer view from local telemetry. The registry enriches; it does
   not gate.

### (d) The tier presentation node — footprint owned, alternative recorded

**The deliverable unit is the *tier presentation node*** — deliberately
named without reference to any tier kind, because it is the generic
recursive node's presentation kit and helm templates and docs will
inherit whatever noun is used here:

> **tier presentation node** = postgres + schema-init job + projector
> instance + Electric + UI + Topaz sidecar (passive) + **restate-server
> + logistics-fusion + cm-service** *(added 2026-08-08 — see below)*
>
> Attachable to **any broker-bearing tier**, at any depth.

**2026-08-08 revision — the node gains a durable-workflow substrate.**

The original stack contained no analytics: projector writes latest-state,
store serves, UI presents. That was wrong, and the trace is short:
fusion produces `asset-logistics-status` to the **root** broker, a tier
projector subscribes **tier-local** topics only, so a tier store receives
**no severity at all** — absent, not stale, and the UI renders ringless
whether connected or severed. The severance-tolerance sweep
([AUDIT-2026-08-08](AUDIT-2026-08-08-severance-tolerance-inventory.md))
found `cm-service` is fusion's structural twin, so the same holds for CM
state.

Both are Restate Virtual Objects, and Restate was root-only. The node
therefore gains **restate-server + fusion + cm-service**.

**Three legs justify the substrate, not one:**

1. **Detection today** — fusion and cm-service must compute at the tier
   that presents, or a severed tier shows position without judgement.
2. **Configurable analytics** — ADR-0034's *durable-workflow* execution
   class requires a durable substrate at each tier.
3. **Sovereignty maintainer process workflows** *(decisive)* — maintainer
   operations run as customer-catered process workflows, custom per
   nation or department, executing at the maintainer's tier. A maintainer
   mid-procedure (inspection half-signed, requisition pending approval)
   must not lose workflow state to a WAN drop. `PRINCIPLES.md` §Locality
   applied to **process execution**.

**Rejected alternative, recorded:** re-expressing fusion/cm as
plain-Kafka consumers to avoid the substrate. It was recommended by
[BRIEF-2026-08-08](BRIEF-2026-08-08-per-tier-severity.md) on the finding
that fusion uses Restate thinly — a finding that is true of the
**demo-era hardcoding** and silent about the roadmap. It would have
removed, today, the exact substrate legs 2 and 3 need tomorrow. See that
brief's §Resolution for the framework-vs-instantiation error in full.

**Amortisation:** one substrate per tier serves two services today and
the whole detection-plus-workflow plane tomorrow. The baseline is paid
once per tier, not once per service.

**Footprint honesty:** the `512Mi`-OOMKill note in `values.yaml` is
**root-scale** — full-fleet Virtual Object state. A tier keyspace is
order-100 assets holding order-KB per asset, i.e. single-digit MB of
actual state; Restate's cost is dominated by its runtime baseline, not
its data. What an honest tier-profile request/limit is remains an
**open sizing question**, tracked as follow-on tasking — the cost is to
be owned with numbers, neither denied nor inflated.

It is built once and instantiated per configured tier. In this
deployment it lands at the leaf tiers and the root, because those are
the tiers configured with brokers and staffed with operators — not
because "edge" and "HQ" are special kinds.

The operational cost is real and is accepted explicitly:

The operational cost is real and is accepted explicitly:

- **Migrations × N.** Every schema change now runs at N+1 sites. The
  Atlas migration path already exists; the change is that its blast
  radius is multiplied and a partial-failure state (some tiers migrated,
  some not) becomes possible.
- **Backups × N**, if edge stores are ever treated as durable. They are
  **not**: an edge store is a *projection* and is fully rebuildable from
  its local compacted topics. This is stated so nobody later designs a
  backup regime for derived data.
- **Monitoring × N.** N more Postgres instances and projector instances
  to alert on.
- **Compute/memory at the edge**, which is the tier where footprint is
  an architectural constraint (ADR-0021; ADR-0030 §engine policy). The
  tier presentation node must be sized against the smallest realistic
  site it will be deployed to, not the cluster's most comfortable node.

**Rejected alternative — bespoke reads against Faust table state.**
The edge already holds per-asset state in Faust changelog topics, and a
reasoning or presentation component could read those directly instead of
projecting into a store. Rejected because it creates a **second
read-truth**: the same logical rows, materialized twice, by two
different code paths, with two different notions of "current". That is
the same disease as a second authorization truth (ADR-0031 §b) — two
confident answers, divergence invisible until it matters. One
projection path, one store shape, every tier.

### (e) Frontend serving — the edge serves its own UI

*(Flagged in the recipe as an embedded decision. **Kept, and decided.**)*

**Decision: a tier presentation node serves its own UI instance.**

The alternative — a centrally-served frontend that targets tier-local
Electric — fails the arc's own exit criterion. A UI asset loaded from a
parent tier cannot be loaded *during* severance. An operator whose
browser already has the app running might survive on cache; one who
reloads, opens a new tab, or arrives at a shift change during severance
gets nothing. "Works only if you loaded it before the link dropped" is
not severance tolerance; it is luck with a good story.

Since the frontend is a static nginx-served bundle, serving it per node
is inexpensive — it is the cheapest element of the tier presentation
node, and it converts the arc's central claim from conditional to
unconditional.

**Corollary:** the locally-served UI must target *its own* Electric
instance, resolved locally, with no parent-tier-hosted asset on the
critical path.

### (f) Severance UX inversion — the edge reports its own uplink

With local serving and local reads, the maintainer view **works while
severed**. The severance indicator therefore changes meaning, and the
change is the point:

- **Today:** the banner is HQ's view of the edge, derived from
  centrally-observed bridge-group lag. It describes the edge, from
  outside, and it is unavailable to the edge when the edge most needs
  it.
- **Under Arc 1:** the indicator becomes **the edge's view of its own
  uplink** — local `edge_buffer` state, observed locally, displayed
  locally. It says "my data is current; my uplink is down; N events are
  buffered," which is the true and useful statement.

Named here; **built in Phase 5**. Recorded now because it is a semantic
change to an existing indicator, not a new widget — anyone reading the
banner code later needs to know the meaning was deliberately inverted.

## Consequences

### Positive

- The maintainer's view of their own equipment survives severance —
  closing the inversion that is this ADR's finding.
- ADR-0022's severance-tolerance invariant becomes uniform across data
  and presentation planes, rather than holding in one and silently
  failing in the other.
- Severance status becomes self-reported by the tier that is severed,
  which is both more accurate and available when it matters.
- Arc 2 lands rules onto a deployed policy sidecar rather than
  deploying a new component under enforcement pressure.
- ADR-0031's edge read-seam gains a real substrate; its Phase 2 §2.1
  option (a) — edge-local Postgres, one read contract across tiers — is
  what this ADR builds.

### Negative

- N additional tier presentation nodes: N Postgres, N projectors, N
  Electric, N schema-init jobs, N Topaz sidecars. Real footprint at the
  tier least able to afford it.
- Migration blast radius multiplies, and partial-migration states become
  reachable.
- The first HQ→edge flow is introduced into a previously upward-only
  topology. Constrained in (c), but the precedent now exists and will
  attract proposals.
- More surfaces where "the UI shows something different here than there"
  is possible; parity checking becomes a standing verification concern
  (Phase 5 ladder step ii).

### Neutral / acknowledged

- Edge stores are **derived, not durable**. Rebuildable from local
  compacted topics; no backup regime.
- Arc 1 ships the Topaz sidecar deciding nothing. A deployed component
  with no function is a legitimate "why is this here?" question; the
  answer is Arc 2, and it is recorded here so the seat is not removed as
  dead weight.
- The regional no-store decision rests on regions having no broker. It
  is a decision about the current topology and is explicitly revisitable
  if that changes.
- **The projector's tier-parameterizability is believed, not proven.**
  Every phase after Phase 2 rests on it. Phase 2 exists to falsify it
  cheaply, in local compose, before helm templating multiplies any gap
  by N (ADR-0025 discipline).

## Related

- ADR-0033 — the recursive tier hierarchy as framework invariant; the
  model this ADR's §Framework vs. instantiation defers to, and the home
  of every three-tier hardcoding named there.
- ADR-0021 — the edge→HQ topology is load-bearing; edge footprint is an
  architectural constraint.
- ADR-0022 — hierarchical aggregation is the architecture; the
  severance-tolerance invariant this ADR extends to the presentation
  plane.
- ADR-0025 — build-pass deployment verification; why Phase 2 proves the
  projector claim before templating it.
- ADR-0028 — centralized `asset_registry`; the reference data requiring
  the (c) downstream flow.
- ADR-0029 — ABAC releasability; Arc 2, whose seat this arc deploys and
  whose label columns land as this arc's step zero.
- ADR-0031 — converged edge node; its §2.1 option (a) is what this ADR
  decides to build, and its read-seam contract is why (b) chooses
  identical DDL.
