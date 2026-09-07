# Two-hop freshness: both ages carried, not fused

**Status:** design, written before the bridge retarget moves data
**Date:** 2026-09-07
**Touches:** ADR-0033 (recursive tiers), ADR-0035 (class 2: absence rendered as
something else), ADR-0036 clause 4 (degraded mode), GD-05 (non-composable
rollups), GD-12 (absence conventions)

## The thing that breaks

HQ's view of a leaf shows exactly one age today: `latest_sample_at` in
`EdgeAttribution`, `observed_at` in `RegionFleetSummary`, both rendered by a
local `relativeAge()`. That was adequate while every leaf was one hop from
HQ, because a number that stopped advancing had two possible causes — the
edge stopped sampling, or its bridge stopped delivering — and both were the
same edge's problem, diagnosed by the same person walking to the same rack.

Put a tier-managed region in between and that stops being true. There are now
**three** independent places the number can freeze:

1. the edge stops sampling the asset,
2. the **edge → region** bridge stops delivering,
3. the **region → HQ** bridge stops delivering.

All three freeze `sample_time` at HQ. All three render as one growing number
against the leaf. So HQ would display `edge-01 — 6m ago` while edge-01 is
perfectly healthy and it is the region's uplink that is down.

That is not merely imprecise, it is **misdirecting**, and in the expensive
direction: the operator response to "the edge is quiet" is to go look at the
edge, which is the one place where nothing is wrong. The failure is at the
region, and the region is the tier whose whole purpose is to keep working
when the link above it does not.

In ADR-0035's terms this is class 2 — an absence rendered as something else.
The absence of a *relay* is being rendered as the absence of an *observation*.

## Why fusing is the wrong repair

The tempting fix is one number that accounts for both: `max(observation_age,
relay_age)`, or "the worst age in the chain". It is wrong twice.

* It is **one number again**. Which hop is responsible is precisely the
  information the second number exists to carry, and a max discards it. The
  two failures still look identical, just with a more defensible label.
* It is **non-composable**, in the GD-05 sense. An age already fused at the
  region cannot be fused again at HQ without the region's own relay latency
  being counted into the leaf's observation age. Depth-3 makes it worse.

So: carried, not fused. Two ages, side by side, each attributable.

## The design

### Wire

`Provenance` gains a relay chain. Field 11 is reserved, so this is 12:

```proto
message RelayHop {
  // The tier that performed the relay -- the PUBLISHER, not the receiver.
  string tier_id = 1;
  // When that tier handed the message upward. Absolute, not a duration:
  // durations would have to be summed, and summing is fusing.
  google.protobuf.Timestamp relayed_at = 2;
}

// Ordered leaf -> root. APPEND ONLY.
repeated RelayHop relay_chain = 12;
```

Three rules, and all three are load-bearing:

1. **Each relay appends exactly one hop.** It never rewrites an existing
   entry and never truncates the chain. A region that overwrote the edge's
   hop would be fusing by another name.
2. **The chain is ordered leaf → root**, so `len(relay_chain)` *is* the hop
   count, and `relay_chain[i]` attributes a delay to a named tier.
3. **`sample_time` is never touched by a relay.** It belongs to the leaf and
   stays the leaf's. This is the same discipline as `edge_id` / `region_id`
   and `originator_nation`: the earliest tier that knows the answer states
   it, every later tier carries it unchanged.

### View

For a leaf under a region, HQ computes and renders both:

* observation age = `now - sample_time`
* relay age, per hop = `now - relay_chain[i].relayed_at`

```
edge-01   observed 12s ago  ·  via region-east 4s ago      <- healthy
edge-01   observed 6m ago   ·  via region-east 3s ago      <- EDGE is quiet
edge-01   observed 6m ago   ·  via region-east 6m ago      <- REGION uplink down
```

Rows two and three are the pair that a single number cannot separate, and
they call for opposite responses. That is the acceptance test for this whole
design: if those two rows ever render alike, it has failed.

### Absence, per GD-12

* **No `relay_chain` at all** renders UNSPECIFIED — never `0s`, never
  "direct", never blank-so-it-reads-as-fresh. An unstamped message is not a
  fresh one.
* Distinguishing "arrived directly" from "a relay failed to stamp" therefore
  requires that **every** relay stamps, including today's single-hop
  edge → HQ bridge. This is not a region feature bolted onto a region path.
  With that in place the chain length is itself the reading: `1` = direct
  leaf, `2` = leaf under a region, `0` = unstamped or legacy → UNSPECIFIED.

### Clock skew is not freshness

These ages are differences taken across machines. So: carry absolute
timestamps and compute the age at the viewer, and treat a `relayed_at` in the
future as **skew, not freshness** — clamp to zero and mark it. A negative age
rendered as "just now" would be the cheeriest possible presentation of a
broken clock.

## Where the stamp goes, and what lands first

The bridge is a Benthos pipeline with no processors: it reads a topic list
and writes each message through unchanged. Stamping there means teaching it
the envelope.

* **(a) Stamp at the bridge.** The correct place — it is the component that
  performs the relay, and it covers everything the relay carries. Costs the
  bridge protobuf awareness.
* **(b) Stamp at the tier's producers.** Cheaper, and wrong: the bridge also
  carries `raw-sensor-stream` and `telemetry-latest-state`, which the tier's
  own services did not author. (b) would leave exactly those topics
  unstamped, and they are the ones the leaf view is built from.

So the design is (a).

**The honest interim, which lands first and independently.** Until (a)
exists, HQ must not present its single age as though it were the whole story.
The leaf-under-region view carries the observation age and renders the relay
age as UNSPECIFIED — visibly missing rather than silently absent. That is
worse information than the final design and better than today's, because
today's actively asserts something false about which tier is at fault.

This ordering matters for sequencing: the UI change is decoupled from the
proto and bridge changes, so it can land before the retarget while (a)
follows.

## What this does not establish

* That the relay chain is *complete*. A relay that fails to stamp produces a
  short chain, which reads as a shallower tree rather than as an error. The
  consumer census is the complement here: it enumerates who reads whose
  broker, this enumerates who relayed. Neither alone proves the topology.
* That a fresh relay age means the data is right. A bridge faithfully
  relaying a frozen upstream stamps a fresh hop over stale content — which is
  exactly why the observation age is carried alongside and never replaced.
