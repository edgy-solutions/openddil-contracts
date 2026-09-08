# The region's input contract: feed it or don't render it

**Status:** design, written before the cutover relocates faust-regional
**Date:** 2026-09-07
**Touches:** ADR-0032 (§d tier node, §e each serves its own), ADR-0033
(recursive tiers), ADR-0035 (class 2: absence rendered as something else),
GD-05 (non-composable rollups), UD-10/UD-11 (reachbacks)

## Why this exists

The retarget deployed region-east's tier node, which rendered **16 consumers**
and attached **8**. The eight are exactly the ones whose input topic the
bridge carries. The other eight are running processes, `1/1 Running`, healthy
by every probe, subscribed to topics that do not exist on their broker.

That is UD-10 wearing a different costume. A tier that looks staffed and
reads nothing is worse than one that is visibly absent, because nothing
distinguishes it from working.

So the contract is not a topic list for its own sake. It is a rule:

> **Every consumer a tier renders must have a fed topic, or it must not be
> rendered.** No third option.

## Measured: what a region renders, and what feeds it

The region's consumers and the topic each reads, taken from the rendered
`tier-projector-config` and `register_tier_subscriptions.py`:

| consumer | reads | fed today |
|---|---|---|
| tier-projector-telemetry-latest | `telemetry-latest-state` | yes |
| tier-projector-cm-state | `asset-cm-state` | yes |
| tier-projector-logistics-status | `asset-logistics-status` | yes |
| tier-projector-tactical-events | `tactical-events` | yes |
| cm-service-silver | `raw-sensor-stream` | yes |
| fusion-service-silver | `raw-sensor-stream` | yes |
| fusion-service-cm-state | `asset-cm-state` | yes |
| uplink-group | (its four inputs) | yes |
| tier-projector-capability | `asset-capability-snapshot` | **no** |
| tier-projector-windows | `asset-telemetry-windows` | **no** |
| tier-projector-element-telemetry | `asset-element-telemetry` | **no** |
| tier-projector-element-inventory | `asset-element-inventory` | **no** |
| cm-service-cm-events | `cm-events` | **no** |
| fusion-service-windows | `asset-telemetry-windows` | **no** |
| fusion-service-derived | `derived-sustainment` | **no** |
| fusion-service-capability | `asset-capability-snapshot` | **no** |

Eight fed, eight not. The census reported eight groups; the model accounts
for the number exactly, which is why it is trustworthy rather than plausible.

## The cutover's minimum, measured rather than assumed

`faust-regional` for region-east consumes, right now:

* from the **HQ** broker: `asset-cm-state`, `asset-logistics-status`,
  `asset-registry-events`
* from **each edge** broker directly: `asset-telemetry-windows`,
  `derived-sustainment`

Those last two **are** the reachback. faust-regional reaches down into
edge-01 and edge-02 for exactly the two topics nothing carries up. So
retiring the six reachbacks and feeding the relocated aggregator are the same
act, and the minimum is three topics added to the edge -> region bridge:

    asset-registry-events
    asset-telemetry-windows
    derived-sustainment

Bridge those and `region-region-east-source-edge-0N` has no reason to exist.
(`asset-registry-edge-0N` and `logistics-sim-edge-0N` are separate root-side
components and retire on their own terms.)

## The declared sets

**Region input set — edge bridges to its region (12):**

    raw-sensor-stream          telemetry-latest-state
    tactical-events            asset-cm-state
    asset-logistics-status     asset-registry-events
    asset-telemetry-windows    derived-sustainment
    asset-capability-snapshot  cm-events
    asset-element-telemetry    asset-element-inventory

Twelve rather than the three the cutover strictly needs, because of the rule
above: the other nine consumers are rendered, so leaving them unfed means a
region UI whose Capability, Windows and Element views are empty — and empty
is not the same claim as "not served here". That is precisely ADR-0035
class 2, one tier up.

Trimming this set is legitimate; trimming it **silently** is not. Anything
removed here must also stop being rendered at a region, which makes the tier
node role-aware rather than one shape for every tier.

**Region output set — region bridges to HQ (7):**

    asset-logistics-status     asset-cm-state
    telemetry-latest-state     tactical-events
    region-fleet-summary       region-top-factors
    region-wear-trends

The first four are what the uplink carries today: leaf state relayed onward,
which HQ's projectors already read. The last three are what a relocated
faust-regional *produces* — HQ runs `projector-region-fleet-summary`,
`-top-factors` and `-wear-trends` against them, so if the aggregator moves
into the region and the uplink does not carry its outputs, HQ's regional
views go empty on the day of the cutover.

`raw-sensor-stream` is deliberately **not** in the output set. It terminates
at the region; zero HQ consumer groups read it (all 16 enumerated and
described, 2026-09-07).

**Every hop stamps `relay_chain`** — edge on the edge -> region publish,
region on the region -> HQ publish. Append only, leaf to root, `sample_time`
untouched. Without it HQ cannot tell a quiet edge from a downed region
uplink; see DESIGN-2026-09-07-two-hop-freshness.md.

## A finding this surfaced, which is not about topics

`cm-service-silver-region-east` and `fusion-service-silver-region-east` are
attached to `raw-sensor-stream` **at the region**, and their edge
counterparts are attached to the same topic at the edge. The region is
recomputing silver state its child already computed, from a copy of the same
raw input.

It is not currently harmful — the region's own Postgres is separate, and the
uplink carries the leaf's derived state rather than the region's re-derivation
— but two tiers deriving the same asset's state from the same input, with no
rule about which one wins, is how a fleet ends up with two answers. Under
GD-05 the rollups are not composable, so "they will agree" is an assumption,
not a property.

**The contract therefore has a second clause, and it is the harder one:**
declaring which topics flow is not sufficient without declaring **which tier
computes what**. A region that relays its children's derived state should not
also derive it; a region that derives should not relay the children's. Today
it does both, in parallel, and nothing chooses.

That is scoped as the next question rather than answered here, because
answering it changes what the tier node renders and the cutover does not
depend on it. Recording it now so it is a decision rather than a discovery.

## Acceptance

A census extension asserts the rule directly: for each tier, every consumer
the tier RENDERS is checked against the topics its broker actually holds, and
an unfed consumer is a finding. The existing census cannot do this — it sees
only groups that attached, and an unfed consumer never forms one, so it is
invisible in exactly the data the census reads. It needs the rendered config
as a second source.

---

## Amendment, 2026-09-08: two directions, and the raw rule

The cutover deployed the 12-topic set and measured **8 fed of 12**. Working
out why produced two corrections to the contract itself, not to the deploy.

### A tier's inputs have TWO directions

`asset-registry-events` was in the upward list and should never have been.
The asset registry is **root-owned**: its events are distributed DOWN to
tiers, not gathered UP from them. Putting it on the edge → region bridge
asked edges to supply reference data they do not author, which is exactly why
it sat at watermark 0 on every edge broker — the bridge was faithfully
carrying nothing, forever.

So the contract splits:

* **Upward — derived state from children.** What a subtree computed about
  itself. This is the bridge, and it is what the input set enumerates.
* **Downward — reference data from the root.** The asset registry, CM
  baselines, releasability policy. A distribution seam, not a bridge, because
  the shape is one authority fanning out to many tiers rather than many tiers
  converging on one parent.

`asset-registry-events` moves to the downward half, and faust-regional's
registry source waits on that seam rather than on the bridge. **Naming the
direction is the fix**; leaving it on the bridge would have kept a topic
"configured, created, subscribed and permanently empty" and called the contract
satisfied.

### Raw crosses a link only to where derivation happens

The detection gate made region-east stop deriving from `raw-sensor-stream`,
and the only groups touching it there became the two Empty retired ones. Zero
groups on the HQ broker read it either (all 16 enumerated and described). So
**3.78M messages on edge-01 alone were crossing a DDIL link to feed nobody.**

The rule, which the detection gate already implies:

> Raw crosses a link only to where derivation happens, or to a **declared**
> consumer — archival, replay, an ADR-0034 training unit.

Applied: the bridge's topic list is conditional on tier-managed-ness. An
untier-ed edge still sends raw upward, because the ROOT derives its state
directly and that is the derivation happening at the other end. A tier-managed
edge sends its derived state plus `telemetry-latest-state` for presentation,
and no raw at all.

Measured after: region-east's `raw-sensor-stream` froze at 13,915 across two
samples while edge-01 advanced 3,789,365 → 3,789,381. edge-03's path is
unchanged and needs its own verification before anything touches it.

### And the check grew a fourth rung

`configured → created → subscribed → FLOWING`. The check had printed a caveat
about itself — *a topic that exists at high-watermark 0 passes here and
starves the consumer just the same* — one run before that caveat mattered,
which is the tell that it belonged in a classification rather than in prose.

An empty topic must now carry a **declared idle reason**
(`scripts/declared-idle-topics.yaml`), with three statuses: `declared`
(expected for this deployment), `held` (a known defect, deferred by decision,
named so it cannot become "expected" through familiarity), and `investigate`
(nobody knows, and it is meant to be uncomfortable). Undeclared and empty is a
finding.

**Its first run found one.** `cm-events` sat at watermark 0 on both edges —
tiers the three-rung check had been reporting as 15 of 15 fed. No cm-ingest
workload exists and `cm-items` is empty too, so nothing in this deployment
authors configuration-change events. Declared, with the evidence, rather than
discovered later as a silent gap.
