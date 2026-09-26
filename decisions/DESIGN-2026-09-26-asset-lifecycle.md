# Asset lifecycle: a fleet needs a word for *leaving*

**Status:** design, written after the lab measurements; nothing built
**Date:** 2026-09-26
**Touches:** ADR-0014 (per-asset Virtual Objects), ADR-0029 §3 (labels
propagate, never default), ADR-0035 (class 2: absence rendered as something
else), ADR-0043 §4 (the aggregate completeness inversion), GD-05
(non-composable rollups), GD-11 (declared, not inferred), GD-12 (absence
conventions)
**Sibling:** `DESIGN-2026-08-16-operational-state-absence.md` settled what an
axis says when it knows nothing. This settles what the *fleet* says when a
member stops existing. Same disease, different subject.

## The thing that breaks

The pipeline has two verbs. It can **create** an asset and it can **update**
one. It has no verb for **withdrawing** one, at any tier, in any store.

Measured on `edgy-lab` at revision 51, not read off code
(`openddil-helm/scripts/FINDING-2026-09-26-no-asset-eviction.md`): deleting one
injected asset's rows held for four tables and failed for the fifth, because
`AssetLogistics.on_timer` at `asset_logistics.py:477` calls
`_recompute_and_maybe_emit(..., force_emit=True)` and then
`_schedule_next_timer(...)` **unconditionally**. One 144-byte PDU creates a
self-sustaining emitter. The row was back in 60 seconds and kept advancing
while the asset's own telemetry had been frozen for twenty minutes.

Clearing it took an operator, three Restate servers, six admin-API calls in a
specific order, and a pod with a shell in it. That is the cost of a
`DELETE FROM` the system has no vocabulary for.

### Why this is urgent rather than tidy

It composes. `FINDING-2026-09-26-kind2-munition-resolution.md` measures that a
munition entity arriving as `kind=2` is neither rejected nor recognised: it
resolves to `_default`, becomes `platform_variant = UNKNOWN`, and enters the
fleet as an asset with no warning anywhere. Put that beside permanence and
`restate.ephemeralOnUpgrade: false` on the work cluster, and **every round a
simulator tracks in flight is a candidate permanent UNKNOWN fleet member**,
inflating every rollup for as long as the deployment lives.

## What already exists, stated first so the gap is the real one

A claim of total absence would be wrong, and the shape of what *is* there is
what the design has to fit.

1. **Staleness, and it is correct.** `stale_input_seconds` (default 300,
   `thresholds.py:112`) is a **severity** rule: past the threshold the asset
   acquires a DEGRADED `stale_inputs` constraining factor **and goes on being
   emitted**. This design does not touch that and must not be read as
   proposing to. An asset that goes quiet is the normal condition of a real
   asset behind a downed uplink, and flagging it is the right answer.
2. **Age-based pruning, for exactly one table.** `main.py:280` builds the
   pruner's table list from `m.mode == "append" and m.retention_hours`. In
   `projector_config.yaml` that is **one** table — `tactical_events`, 720
   hours. The other **eleven** are `mode: upsert` and no pruner touches them,
   deliberately: an upsert table holds *latest state*, and latest state does
   not expire. The unhandled case is not stale state. It is **latest state of
   something that no longer exists.**
3. **A supported delete, on exactly one topic class.** A tombstone on a Faust
   changelog *is* a delete, natively, and it is durable across recovery —
   proven on the lab on 2026-09-26 (`RESULT-2026-09-26-residue-cleanup.md`):
   offset 9345227, `VALUE_BYTES=0`, the key absent after two separate cold
   recoveries.

So the gap is narrow and precise: **there is no way to say "this asset is no
longer a member of this fleet" that any reader understands**, and the one
mechanism that does delete works on one topic class out of three.

## The conflation at the centre of it

Two different questions are being answered by one signal.

| question | kind of claim | answered today by |
|---|---|---|
| have we stopped hearing from this asset? | about **our knowledge** | `stale_inputs`, correctly |
| is this asset still part of this fleet? | about **membership** | nothing |

Today the second is rendered *as* the first: an asset that has left the fleet
appears as an asset we have stopped hearing from. That is ADR-0035's class 2 —
absence rendered as something else — and it is wrong in the expensive
direction, because a stale row invites someone to go find out why the uplink
is down for an asset that was transferred out three days ago.

The inverse fix is equally wrong, and naming it is half the design: **you
cannot infer withdrawal from silence.** A timeout that evicts quiet assets
deletes the real asset behind the failed uplink, and deletes it *silently* —
a fleet count that shrinks with no reason attached is strictly worse than a
count that is too large and flagged. Per GD-11, membership is a fact about the
domain and must be **declared, never inferred from one feed's publishing
behaviour.** Silence produces `stale_inputs` and nothing else, forever.

## The design: three membership states, one of them new

| state | meaning | in rollups | history |
|---|---|---|---|
| `TRACKED` | a member; emitted on cadence | counted | kept |
| `WITHDRAWN` | **declared** no longer a member — transferred, destroyed, exercise ended | excluded, **with the exclusion reported** | kept |
| `EVICTED` | should never have been a member — mistyped id, cross-exercise leak, test injection | removed | the *removal* is recorded, per item 5's durable-record row |

`WITHDRAWN` and `EVICTED` are different because they fail differently, and
collapsing them is how a mistake gets laundered into deployment data. A
withdrawal is an assertion about a real asset and belongs in the record. An
eviction is an admission that a row was never about anything, and its honest
artefact is not a fleet-history entry but an operator log line.

### Withdrawal is a record, not an absence

A withdrawal arrives as an **ordinary labelled record on the asset's own
topic**, carrying a declared membership field — not as a null, and not as the
cessation of records. Two reasons, both already paid for in this corpus:

* **GD-12.** An absence needs a per-field convention invented independently in
  every consumer. A present record with a declared value needs one convention,
  declared once. Every previous attempt to say something by *not* saying it has
  cost more than the field would have.
* **§"Three delete semantics" below.** A delete expressed as a null is a delete
  that no reader can distinguish from a decode failure — measured, not feared.

Labels propagate per ADR-0029 §3: a withdrawal inherits the asset's own
`originator_nation` and `releasable_to` from the asset it withdraws, with no
default and no else-branch. An undeclared asset's withdrawal is unlabelled,
exactly as its telemetry was.

### Eviction is an operator act with a fixed order

There is no authoritative record to write for an asset that was never real, so
eviction cannot be a data path. Its correct shape is the procedure already
executed once and written down in `FINDING-2026-09-26-no-asset-eviction.md`,
promoted from a finding to a runbook step. The load-bearing part is the
**order**: cancel the scheduled invocation *before* clearing the object's
state. Clearing first lets the next tick fire against empty state, emit "No
telemetry observed for this asset yet" as DEGRADED, and reschedule — which
re-creates everything just cleared. The measured footprint is three servers
and both `AssetLogistics` and `AssetCM`, so "clear the object" is a per-tier,
per-service act and not one call.

## Three delete semantics for one word, measured at each reader

Per the EXCHANGE-LEDGER standing check, the path is walked producer to reader.
"Produce a tombstone" is not a procedure until it says *which topic*, because
the same bytes mean three different things:

| reader | a null-valued record means | measured |
|---|---|---|
| Faust changelog → aggregator table restore | **a delete.** Durable across recovery | yes — 2026-09-26, two cold recoveries |
| the projector, on a `compact` topic | **nothing at all** — see below | yes — code path traced end to end |
| a Restate Virtual Object | **irrelevant.** State is durable; only the admin API clears it | yes — its own docstring says so |

**The projector case is the one that matters, and the earlier fear about it was
wrong.** `FINDING-2026-09-26-no-asset-eviction.md` declined to produce
tombstones onto the three ingress `compact` topics, reasoning that a null is an
untested input class whose plausible failure — a decoder erroring and blocking
a partition — is the `WEDGED` signature. Traced now:

* every decoder raises `DecodeError("message value is None (tombstone?)")` —
  `decoders/proto.py:89`, `cloudevents.py:30`, `json_raw.py:23`;
* `main.py:152` catches `DecodeError`, logs it **once per (topic, message)**,
  increments `DECODE_ERRORS`, and **returns**;
* the batch then commits its offsets normally (`main.py:230`), because the
  skip is not an exception.

So a tombstone on a projector-fed topic is **safe and ineffective**. It does
not wedge the partition — that risk was real to decline unattended and is now
measured as unfounded — and it does not delete the row. It is silently
discarded, which is the worst of the three outcomes: the delete signal exists,
travels, and is thrown away where nobody is looking.

One second-order effect worth recording because it will surprise someone.
`_persist`'s batch dedup is `by_key[msg.key()] = msg` (`main.py:140-143`),
last-wins. A tombstone arriving in the same batch as a real update for the same
key **discards the real update**, and then decodes to nothing. Harmless for a
key being deleted; a trap the day a null is used to mean anything else.

### What the projector should do instead

The decoder is the wrong place to decide. `DecodeError` currently conflates
"these bytes are corrupt" with "this is an intentional delete", and those want
opposite handling. So:

* the null check becomes a distinct sentinel the **handler** is allowed to see,
  rather than an error the consumer swallows;
* `mode: upsert` gains a delete arm keyed by the **same `key_columns` the
  upsert already declares.** This is the cheap part: a table that declares what
  it upserts on has already declared what to delete by. No new configuration,
  no new schema, no per-table decision.
* `mode: append` ignores it. Append tables have a lifetime rule already —
  `retention_hours` — and a second one would be two truths.

## The rollup side, where the count is

`_emit_rollups` in `openddil-tactical-agents/regional/aggregator_app.py:278`
is `snapshot = list(assets_latest.items())` and filters nothing. Worth stating
sharply: `last_updated_ns` is **written in three places and read in none**
(lines 216, 237, 256 — no reader). The table's own docstring says it tracks
"each asset's latest contributions", and every key it has ever seen is a
contributor forever.

The rule for this tier follows from the "silently shrinking count" problem
above: **a rollup may not exclude a member without reporting the exclusion.**
Concretely, `RegionFleetSummary` needs a withdrawn count beside its asset
count, or a withdrawal is invisible at precisely the tier that performed it,
and the fleet number changes with no explanation attached to it.

Two constraints on that, from the register:

* **GD-05 / ADR-0043 §4.** Each emission is already one partial per
  releasability class. A withdrawn count must be partitioned by the same class
  rule as the asset count, or the count itself leaks membership across
  audiences — and it must inherit the aggregate convention (`releasable_to`
  non-null, `originator_nation` NULL), because that inversion is exactly why
  the `dis:1:1:1099` residue passed every completeness gate for days.
* A withdrawal is **not** composable by summing. A parent tier counting its
  children's withdrawn counts is counting a number whose members it cannot
  enumerate, which is the GD-05 shape. Withdrawn counts stop at the tier that
  emits them until GD-05 is resolved.

## What `ephemeralOnUpgrade` is not

`restate.ephemeralOnUpgrade` clears **everything or nothing**, at **upgrade
time only**, and it is **false on the work cluster** for good reasons. It is a
lab convenience, not a lifecycle mechanism, and treating it as the remedy is
precisely how the lab hid this for as long as it did: the residue that forced
this design would have been swept away by the next upgrade without anyone
learning that there was no other way to remove it. The wipe's own
tracelessness — a hook that deletes itself on success, so no post-deploy check
can say whether it ran — is a separate row.

## Acceptance: one pair of rows

Borrowed deliberately from `DESIGN-2026-09-07-two-hop-freshness.md`, because
the test of a distinction is that it is *visible*:

* *observed 6m ago · stale_inputs · DEGRADED* — a real asset behind a quiet
  uplink. Present, counted, flagged. **Unchanged from today.**
* *withdrawn 2026-09-26 14:02 · declared by …* — absent from the fleet count,
  with the count's change explained on the same view.

**If a quiet asset and a withdrawn asset ever render alike, this failed.**

For eviction, the acceptance is the one the procedure's ordering constraint
exists to produce: zero state rows and zero non-completed invocations on every
tier that held any, **re-checked one full cadence later** to prove the object
did not re-arm. A check that runs immediately after the clear cannot see the
only failure mode that matters.

## What this does not establish

* **No rate measurement.** Nothing here says how many spurious entities a live
  DIS multicast environment actually produces. The `kind=2` composition is a
  reason this matters; it is not evidence of frequency. The cheap thing to know
  before the work deploy is the count of `kind=2` Entity State PDUs in one
  representative run.
* **The projector delete arm is untested against a live consumer group.** §"What
  the projector should do" is a code reading plus a proposal. The tombstone
  behaviour in the table above is measured; the replacement is not built.
* **Whether withdrawal belongs in the customer egress vocabulary is open.** FMC
  has no obvious word for "no longer mine", and inventing one in a connector is
  the failure DESIGN-2026-09-06 §Contract A names. Not settled here.
* **No decision on who may declare a withdrawal.** It is an authority question,
  not a plumbing question, and it belongs with the asset registry lineage rule
  (ADR-0028: the production warfighter system is authoritative for
  asset→edge→region, and OpenDDIL surfaces divergence rather than overriding
  it). A withdrawal declared by OpenDDIL against an asset that upstream still
  lists is a divergence signal, not a delete.
