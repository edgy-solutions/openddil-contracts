# DESIGN — the regional tier node (opening package)

**Status: PLAN ONLY. Nothing built. Go-signal reserved.**
Written 2026-09-05, after edge-01's tier node and its UD-10/UD-11 cutover.

The regional node is the **first intermediate**. Everything so far has been
leaves and a root, and the two ends of a tree are the easy cases: a leaf has
no children to compose and a root has no parent to be cut from. An
intermediate has both, and every section below is some consequence of that
one fact.

The closest precedent is edge-01, and the honest summary of edge-01 is
**"mostly the cutover, not the scaffolding."** That is expected to hold here
too — the per-tier PEP, Topaz, ingress, realm client and store all derive
from helpers now, and the fourth-tier check already proved the template
renders an intermediate. What it does *not* mean is that this is small. The
cutover was the hard part at edge-01 and it is harder here, for reasons §1
and §3 set out.

---

## §0 — What is already true, so the package does not re-buy it

* The chart renders an intermediate. `check-tier-config.sh` renders a
  fourth tier "intermediate under region-east" and asserts its shape; the
  presentation resolves it by shape (`has_children` + `parent`) with no
  code change.
* `region_id` exists in the read model, so a regional node has a column to
  be scoped by. **GD-01 does not block this** — that row is about a
  hierarchy PATH, and a one-level-deep region is addressable without one.
* Per-tier PEP, Topaz, NetworkPolicy, nginx upstream, ingress host, OIDC
  client and cookie-scheme all derive from `openddil.isTierManaged`,
  `openddil.tierClientId` and friends. A second tier is configuration.
* `prune_subscriptions` retires what a tier stops consuming, so a cutover
  no longer leaves its predecessor running.

---

## §1 — The cutover, one level up: what must move, and what the root eats instead

**This is the largest piece and it is bigger than edge-01's, because there
are more downward paths and one of them is already known to be wrong.**

### What reaches into a region's edges today

`openddil-faust-regional-region-east` runs **at the root** and carries:

```
REGIONAL_EDGES=edge-01=openddil-redpanda-edge-01:9092,edge-02=...
REGIONAL_HQ_BROKERS=openddil-redpanda-hq:19092
REGIONAL_FAN_IN_TOPIC=region-east-fan-in
```

It consumes each edge's broker **directly** and produces
`region-fleet-summary`, `region-top-factors` and `region-wear-trends` onto
the HQ broker, where `projector-hq` writes them into `region_fleet_summary`,
`region_top_factors`, `region_wear_trends`.

**Two live root-owned consumer groups still sit on edge-01's broker — an
edge that is already tier-managed:**

| group | owner | state |
|---|---|---|
| `region-region-east-source-edge-01` | `faust-regional-region-east` | `Stable` |
| `asset-registry-edge-01` | `asset-registry-service` | `Stable` |

Neither is gated on `isTierManaged`. **This is UD-11 unfinished, not new
work discovered here**: the projector was retired, and these two were not.
They were invisible to the severance acceptance because that check measures
`telemetry_latest_state`, which neither of them writes — *a cut proves
something about the paths that feed what you measured and nothing about the
paths that feed what you did not.*

**They should be fixed as part of §1 and not left to wait for the regional
node**, because a tier-managed edge with two root-owned consumers on its
broker is the exact condition UD-10 describes, and the reason it is not
currently causing UD-10's symptom is only that these two use their own
consumer groups.

### What moves

* **Regional aggregation moves into the regional node**, computing from the
  region's own store rather than from its edges' raw streams.
* **Edge→region bridges are retargeted**: an edge currently bridges to HQ.
  A tier-managed edge under a tier-managed region bridges to the REGION,
  and the region bridges its derived state to HQ. That is a change to
  `edge.yaml`'s bridge output address, driven by "does this edge's parent
  have a tier node?" — a predicate that does not exist yet and is the one
  new helper this work needs.
* **The root stops consuming edges under a tier-managed region entirely.**
  Its input for that whole subtree becomes the region's derived topics.

### The ordering hazard

Retarget the bridge before the region can consume, and the edge's data goes
nowhere. Retire the root's regional aggregation before the region produces,
and HQ's regional tables go **empty** rather than stale — the same trap
UD-11 hit, where gating the projector without bridging
`telemetry-latest-state` would have emptied HQ's fleet view. The guard
written there (`check-tier-config.sh`, "the root stopped computing AND the
bridge carries nothing") generalises and should be extended rather than
re-invented.

---

## §2 — The two-source store, and where honesty about approximation goes

An intermediate's store is fed by **two sources at once**: derived state
arriving upward from its children's bridges, and whatever the region ingests
directly. Leaves have one source; roots have one source. This is the first
node with two, and it is ADR-0034's rollup-of-rollups arriving as deployment
reality rather than as a note.

**GD-05 is the gate and it is explicit about it:** *"resolve before any
fourth tier or any rollup-consuming-rollup."* This work is a
rollup-consuming-rollup. The 2026-08-07 audit found:

* two of the three regional aggregations are **plumbing away from
  composing** — they can be made to compose over child rollups;
* **`region_top_factors` is genuinely non-composable.** Top-N truncation is
  lossy and the loss compounds per tier: a region's top-10 computed from
  each edge's top-10 is not the region's top-10, and HQ's top-10 computed
  from regions' top-10s is further off again.

**The decision this package must force rather than default:** a
non-composable rollup at an intermediate has exactly three honest options,
and the wrong move is to compute it anyway and say nothing.

1. **Compute from full child state.** The region keeps enough of its
   children's detail to compute top-N correctly. Correct, and it makes the
   regional store much larger — it is no longer only derived state.
2. **Mark it approximate, in the data.** The row carries a flag saying it
   was composed from truncated inputs, and every consumer that displays it
   must display that. Cheap to compute, and only honest if the marking
   survives to the screen — an approximation flag nobody renders is worse
   than not computing it.
3. **Do not compute it at a region at all.** `region_top_factors` becomes a
   thing only a node with full leaf detail produces. Fewest lies, least
   capability.

Recommendation: **(2) for the pilot with the flag rendered, (1) as the
endpoint** — but this is a decision for the go-signal, not an
implementation detail to be chosen at a keyboard.

---

## §3 — Severance in two dimensions

Edge-01 gave one severance case. A region gives at least three, and the
second is the new one:

| cut | what must hold |
|---|---|
| **edge ↔ region** | the edge serves locally; the region's view of that edge goes stale-with-indicator; heal converges |
| **region ↔ HQ** | *the region serves locally **for its edges**, which are still attached to it*; HQ's region view goes stale; heal converges |
| both | the edge is alone, the region is alone, and neither claims the other's state is current |

The middle row is what makes an intermediate different. **A severed region
is not an isolated node — it is a node with dependants**, and it must keep
computing, presenting and *deciding* (its own Topaz, its own realm client,
its own PEP) for edges that are still reaching it while its own uplink is
down.

`sever-tier.sh` extends by one level, and it gets harder in a specific way:
site membership is currently "pods whose component label contains the tier
id." A region's site must include the region's own pods **but not its
edges'**, because the edges must stay reachable *from* the region while the
region is cut *from* HQ. That is a different shape of policy — not
isolate-a-set, but cut-one-edge-of-the-tree — and the non-vacuity floor has
to change with it.

Two hazards already paid for, which must carry forward:

* **Established connections survive a NetworkPolicy.** The sever must
  restart the site so every flow re-establishes, or it measures nothing.
* **The component whose job is crossing the boundary must be allowed to
  fail.** The region's uplink bridge will crashloop while cut, exactly as
  the edge's does, and a readiness gate that forbids that contradicts the
  test.

Acceptance is the same four-part shape, extended: (a) region serves fresh
locally-computed data while cut, (b) **its edges still reach it**, (c) HQ's
region view goes stale-not-empty with a peer-region control, (d) heal
converges non-vacuously.

---

## §4 — Label propagation through aggregation: the mixed-nation rollup rule

**This is the first place partitioning and aggregation meet, and it is a
policy decision, not a plumbing one.**

Releasability labels currently propagate along a chain of per-asset
transforms — ingress stamps, fusion and cm-service carry, the projector
writes. Every hop maps one asset's labels to the same asset's labels. **A
rollup does not.** A regional summary row is derived from many assets, which
may carry different `originator_nation` and different `releasable_to`.

The candidate rule is **intersection**: a rollup row is releasable to
exactly those parties entitled to *every* contributing input. It is the
conservative reading and almost certainly right, and the package should
state its consequences rather than let them be discovered:

* A region with one ATL-only asset makes **every** rollup row ATL-only.
  One restrictive input dominates the whole aggregate, and the more
  coalition partners a region has, the emptier its shared rollups get.
* **A hidden row still moved the number.** A viewer sees an aggregate whose
  inputs they may not see. Whether that is a leak depends on the
  aggregate — a count over 40 assets reveals little; a "top factor" naming
  a failure mode observed on exactly one partner's asset can reveal a great
  deal. *`region_top_factors` is the dangerous one again*, for a second
  independent reason.
* **Empty-because-filtered must not render as empty-because-nothing.**
  ADR-0035 class 2, in the aggregation layer.

Alternatives to weigh at the go-signal: union (wrong — leaks), per-nation
rollups computed separately (correct, N× the work, and it makes the
releasability decision an *input* to aggregation rather than a label on its
output), and intersection-with-suppression (compute the intersection, then
refuse to emit rows whose contributing set is small enough to be
identifying — a k-anonymity threshold, which is a real design in its own
right).

**Recommendation: decide this before building, because the choice changes
what the regional node computes, not merely what it labels.**

### THE FLOOR, stated now so nobody defaults to union

Deciding the full rule under recording pressure is how a deployment
shortcut becomes a design, so the rule waits for the block. **The floor does
not:**

> **Minimum releasability of a rollup = the INTERSECTION of its
> contributing inputs' `releasable_to`.** Per-nation rollups are an
> ADDITIVE refinement on top of that, never a relaxation of it.

Anything more permissive than the intersection leaks: a row visible to a
party not entitled to every input is a row that tells them something about
an input they may not see. Union is the tempting error and it is simply
wrong. Recording the floor separately from the rule means an implementer
who reaches this before the decision has a safe answer rather than a blank.

### What the read path already does with an unlabelled rollup, and why it is right

Discovered 2026-09-06, and it settles the interim: the gateway's filter
names `originator_nation` and `releasable_to`, so a table without those
columns **cannot be partitioned and is therefore not served to anyone** —
the fully entitled subject included.

That behaviour was arriving *by accident*, as a SQL error surfacing three
components away as a 502 that panels rendered as "awaiting first emission".
It is now a stated refusal with cause `unlabelable`, and the wording matters:
**not "not releasable"**, which would imply a decision went against the
viewer. Nothing was decided about them. Unpartitionable data has no question
to answer, so everyone gets the same answer.

**Measured on the lab: five of fourteen served tables are labelable and nine
are not** — `asset_registry`, `asset_telemetry_windows`, `audit_log`,
`edge_buffer_status`, `inventory_items`, `tactical_events` and all three
`region_*` rollups. The regional rollups are therefore not a special case;
they are three of nine, and this package's §4 rule is the general answer for
a whole class of tables rather than a regional detail.

---

## §5 — The demo shell's deprecation trigger

The shell is now reachable only at `/demo`, labelled `DEPRECATED`, and no
longer occupies a node's endpoint. **Its retirement trigger, named so it
cannot linger indefinitely:**

> The demo shell is deleted when the three tier instances — edge, region,
> HQ — cover every beat the shell is used to demonstrate.

Concretely that means: the DDIL controller tab has a home (it is not a tier
instance and its ownership is explicitly undecided — opening package §7),
and no demonstration requires seeing two tiers in one pane. Until then it
stays, honestly labelled. **After the regional node lands, the only beat
plausibly still needing it is the controller**, so the trigger is close.

---

## §6 — Honest sizing against edge-01

| | edge-01 | region-east |
|---|---|---|
| scaffolding (PEP, Topaz, ingress, client, store, projector) | built once | **configuration** |
| cutover | detection + projection, found in two passes | **larger**: aggregation moves, bridges retarget, two known reachbacks to retire |
| store | one source | **two sources** |
| composability | not applicable | **GD-05 is a hard gate**, one aggregation genuinely non-composable |
| severance | one dimension | **two**, and the new one has dependants |
| labels | per-asset propagation | **a rollup rule that does not exist yet** |

**Sized as: comparable to the whole of Arc 2's substrate work, not to a
flag.** The two pieces with genuine unknowns are §2 (what a non-composable
rollup does at an intermediate) and §4 (the mixed-nation rollup rule);
both are decisions that change what gets built, which is why they are
surfaced here rather than defaulted.

The two reachbacks in §1 are the exception: they are **UD-11 unfinished**,
they affect a tier-managed edge today, and they should not wait for this
package's go-signal.
