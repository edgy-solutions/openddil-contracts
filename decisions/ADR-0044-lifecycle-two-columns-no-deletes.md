# ADR-0044: An asset that stops reporting is a record, not an absence

## Status

**Proposed — 2026-09-26. Amended 2026-09-28, on §1 and Finding 3.**

Slice 1 of the decision is now built and unit-tested (the two column pairs, the
DIS-gated `destroyed` derivation, and an UPDATE-only staleness sweep). It has not
been run against a live Kafka and Postgres.

**The 2026-09-28 amendment**, prompted by measuring the code this ADR described:
§1's "no deletes, anywhere, ever" was too strong, and Finding 3's claim that the
pruner was dormant was **factually wrong** — the asset path has been pruned by
age hourly all along. Both are corrected in place. The distinction §1 now draws
is that **retention prunes by age, lifecycle changes status by event, and only a
terminal status is prunable.**

**Code change this amendment requires, not yet made:** `prune_loop`'s predicate
must gain the terminal-status condition, so that `asset_ttl_hours` can only ever
reap an asset whose `operational_status` is terminal, and never one that is
merely quiet. Until that lands, §1 describes the intended system and not the
running one — and the honest reading of the gap is that the pruner is still a
lifecycle.

This ADR amends `DESIGN-2026-09-26-asset-lifecycle.md` (same day) on one
point and keeps the rest: the design's `EVICTED` state is **withdrawn**, because
this ADR decides that no status change is expressed as a delete (§1, amended
2026-09-28: retention still prunes by age, but only a terminal status is
prunable). It extends `ADR-0026`
(OperationalState's orthogonal axes) rather than replacing it, and it changes
what `ADR-0028`'s registry lineage rule implies for an asset nobody can account
for.

---

## Context — the archaeology first, because it changes the decision

This ADR was dispatched as a restoration: the original implementation was
believed to have carried a lifecycle status that the current pipeline lost.
Both a code sweep and a pickaxe across all fifteen repositories say otherwise,
and the correction is worth more than the premise was.

**Nothing was lost.** `LifecycleState` was introduced on 2026-05-12 and
2026-05-13 (`46442ae` *"initialize ontology, baseline definitions, proto
contracts"*, `697608e` *"Phase 3 + 3.5: CM data model"*) and it is still carried
at every hop today:

| hop | where |
|---|---|
| contract | `proto/openddil/configuration/v1/as_maintained.proto:36-42` |
| service state machine | `openddil-cm-service/src/events/asset_cm.py` (`decommission()` ~`:229`) |
| store | `openddil-cm-service/src/as_maintained/store.py:45,121` |
| projection | `openddil-projector/src/handlers/cm_state.py:78` |
| schema | `openddil-stack/schema/schema.hcl:238` |
| rollup | `openddil-tactical-agents/regional/severity.py:49-92`, `aggregator_app.py:255,323` |
| UI | `openddil-demo/frontend/src/hooks/useCmState.ts:13` |

The destroyed/deactivated signal path was likewise **added**, not removed:
`1c2d801` and `08900bc` (2026-08-19) map DIS appearance bits onto the health
axis. There is no removal commit in any repository. The nearest thing found was
`AUDIT-2026-08-15-guard-mutation-review.md:126` — *"Dropped `lifecycle` from
`record_to_proto`"* — which is a **deliberate mutation test** whose verdict was
Red, i.e. the suite caught it. That is the opposite of a regression.

`decommission()` already states this ADR's central rule, in place, since May:

> State is preserved for audit; not cleared.

**So this ADR restores nothing. It has three findings instead, and they are
better than a restoration would have been, because each is a defect in
something that works rather than a gap in something absent.**

### Finding 1 — one field, two questions

`LifecycleState` answers two unrelated questions with one enum:

| value | question it actually answers |
|---|---|
| `REGISTERED` | is this asset **ours to account for** yet? — *membership* |
| `ACTIVE` | are we **hearing from it**? — *knowledge* |
| `STALE` | are we **hearing from it**? — *knowledge* |
| `DECOMMISSIONED` | is this asset **still ours**? — *membership* |

A single column cannot hold two orthogonal facts, and the cost is not
theoretical. `region_fleet_summary.proto:21-31` buckets:

```
degraded : LOGISTICS_SEVERITY_DEGRADED OR
           CONFIG_STATUS_MINOR_DISCREPANCY OR
           LIFECYCLE_STALE
```

**So an edge losing its uplink degrades the regional materiel picture.** A
knowledge gap is rendered as equipment degradation — `ADR-0035`'s class 2,
absence rendered as something else — and it is rendered at exactly the tier
where a commander reads the fleet's readiness. A quiet radio and a broken
launcher arrive in the same bucket.

### Finding 2 — three consumers, three private lifecycles

Because the field conflates, every reader that needed one axis built its own:

* **fusion** treats silence as a *severity* input: `_eval_staleness`
  (`rules.py:813-843`) adds a DEGRADED `stale_inputs` constraining factor past
  `STALE_INPUT_SECONDS` (300) and goes on emitting. This is **correct** and this
  ADR does not touch it.
* **the UI** re-derives a five-tier model of its own — `assetTier.ts`:
  `ACTIVE / DEGRADED / STALE / COMM_LOST / LOST`, computed client-side from
  sample age against `stale_after_s: 30`, `lost_after_s: 300`. It never reads
  `lifecycle`. It already makes the distinction this ADR wants — `COMM_LOST`
  is "silent **and** the edge link is severed", `STALE` is "silent and the link
  is up" — and it makes it **in a browser**, where no other tier, no rollup and
  no egress can see it.
* **the DIS mapping** collapses the strongest available lifecycle signals into
  the health and power axes: `sim-dis-mapping.yaml:205-250` sends
  `damage == DESTROYED` to `HEALTH_STATE_FAILED` and `deactivated` to
  `POWER_STATE_OFF`. A destroyed vehicle is recorded as a vehicle with a fault.

The UI case is the sharp one. **The best model of asset liveness in this system
runs in the least authoritative place**, and the greying-out an operator
remembers seeing is real but is a rendering decision, not a fact the fleet
carries.

### Finding 3 — membership genuinely does not exist

No `remove_entity`, no reporting-status field, no `is_deleted`, no soft-delete,
no JC3IEDM object-item status anywhere in code. The aggregator's table is
`store="memory://"` and upsert-only: written at `aggregator_app.py:219,246,263`,
never `del`, never expired, and `last_updated_ns` is **written in three places
and read in none**. `prune_older_than()` is the only runtime `DELETE FROM`.

> **Corrected 2026-09-28 — this paragraph was wrong, and §1 was built on it.**
> It previously read: "it is time-based retention for append-mode tables,
> disabled in practice because `retention_hours` was never set." Measured
> directly in `openddil-projector`:
>
> * `retention_hours` is the **append-mode** field. The asset path is gated by a
>   **different** field, `asset_ttl_hours`, and it **is** set — to `24` — on
>   seven per-asset upsert tables, including `telemetry_latest_state`,
>   `asset_cm_state` and `asset_logistics_status`. `projector_config.yaml` says
>   so in its own comment.
> * `prune_loop` (`src/main.py`) builds **two** target lists, append *and*
>   upsert, and deletes from both. It is created unconditionally as a task and
>   runs hourly.
>
> So the asset path has been deleted by age all along. The survey concluded the
> mechanism was dormant by checking a field name that governs a different mode —
> and the ADR then cited its own conclusion as evidence that deletion-on-silence
> does not happen here, while it was happening hourly. **§1 is amended
> accordingly**: the mechanism is not the defect, its predicate is.
>
> Filed under §*A reference table is looked up, never recalled* in
> `PRINCIPLES.md` — a field name one letter of intent away from the right one
> reads as confirmation, and an ADR is exactly the artefact nobody re-checks.

So the thing that never existed is not a lifecycle *status*. It is a way to say
**"this asset is no longer a member of this fleet"** that any reader
understands.

---

## Decision

### 1. No deletes on status change. Retention prunes by age, and only a terminal status is prunable.

**Amended 2026-09-28.** This section previously read "No deletes. Anywhere. Ever,
on the asset path." That was too strong, and being too strong is what made it
false: the system does delete by age, today, and the ADR cited that mechanism as
dormant (see Finding 3, corrected). The distinction this section failed to draw
is the one that matters.

**Retention prunes by age. Lifecycle changes status by event. These are
different mechanisms answering different questions, and reality has both** — a
destroyed vehicle is carried as destroyed, and years later it is archived. The
error was never that rows age out; it was that ageing out had become the *only*
lifecycle, so "silent for a day" meant "gone".

So, precisely:

1. **No status change is ever expressed as a delete.** A logistics system never
   drops a destroyed vehicle from the fleet; it carries it as destroyed until
   someone writes it off. A record whose status changed is the truthful
   artefact, and a shrinking count with no reason attached is strictly worse
   than a count that is complete and annotated.
2. **Retention keeps pruning by age**, on its own clock, for its own reason —
   bounding storage. It is not a lifecycle and must never be read as one.
3. **Only an asset in a terminal status is eligible for retention. An asset that
   is still reporting is never prunable, at any age.** This is the rule that
   makes (2) safe, and it is the whole content of the amendment.

This closes the inverse temptation too, and naming it is half the decision:
**withdrawal cannot be inferred from silence.** A timeout that evicts quiet
assets deletes the real asset behind the failed uplink, and deletes it silently.
Rule 3 is what forbids it: silence is not a terminal status, so a quiet asset
never becomes prunable by going on being quiet.

**What this changes in the code as it stands.** `asset_ttl_hours: 24` on the
per-asset upsert tables is currently a crude lifecycle wearing retention's
clothes — its meaning is "silent for a day means gone". The mechanism stays; its
predicate changes. Pruning an asset row requires a terminal
`operational_status`, and `reporting_status` is never a prune input. An asset
quiet for a year and still reporting nothing terminal stays in the fleet, with
`not_reporting` on its face, which is the entire point of §2.

**And it removes a trap nobody had noticed.** While age alone was the predicate,
*every* store baseline had a 24-hour shelf life: a fleet count measured on a
Friday decays over an idle weekend with no failure anywhere, and reads exactly
like a failed reset or a stalled projector. Under rule 3 a baseline of reporting
assets is stable for as long as they report.

### 2. Two columns, not one

The asset carries **two** status fields, each with its own timestamp:

| column | answers | changed by |
|---|---|---|
| **operational status** | what is true of the asset | a signal about the asset: destruction, deactivation, decommissioning, fault |
| **reporting status** | what is true of our knowledge of it | the arrival or non-arrival of records, per reader |

A destroyed vehicle counts as **destroyed**. A silent one counts as **not
reporting**. The fleet total counts both, so it stays honest.

The two are genuinely independent, and the case that proves it is the good one:
**an entity that reports its own destruction is `destroyed` and `reporting` at
the same instant**, and becomes `destroyed` + `not_reporting` a minute later
when it stops transmitting. One column cannot express that sequence at all;
today it renders as `FAILED`, then as `FAILED`-and-DEGRADED-stale, which reads
as an asset getting worse rather than an asset that is gone and quiet.

`LifecycleState` is not deleted — nothing is. Its membership values keep their
meaning, its knowledge values (`ACTIVE`, `STALE`) become derivable from the
reporting column, and the migration path is a separate decision (see §"What
this does not decide").

### 3. Rollups partition by status, and report the partition

A rollup may not exclude a member without reporting the exclusion. So
`RegionFleetSummary` gains counts per status rather than folding statuses into
severity buckets. `LIFECYCLE_STALE` stops contributing to `degraded`: a
not-reporting asset is counted in the reporting axis, where the reader can see
that the number is about the radio and not the vehicle.

Two constraints carry over unchanged from `DESIGN-2026-09-26-asset-lifecycle.md`
§"The rollup side": the new counts partition by the same releasability class
rule as `asset_count` (per `ADR-0043` §4) and inherit the aggregate label
convention; and they **do not compose by summing** across tiers while GD-05 is
open, because a parent counting its children's counts is counting members it
cannot enumerate.

### 4. Lifecycle is decided at the tier that owns the sensor; staleness at every tier, for its own view

This is the consequence worth stating loudest, because it is what makes a
severed edge legible instead of alarming:

* **Operational status is owned.** Only the tier that receives the asset's own
  signal may assert that it is destroyed or deactivated. That assertion
  propagates as an ordinary labelled record and every other tier adopts it.
* **Reporting status is local.** Each tier computes it for *its own* feed. When
  edge-01's uplink is severed, its assets are `not_reporting` **at HQ** and
  `reporting` **at edge-01**, simultaneously, and both are correct. HQ must not
  conclude anything about the asset from its own silence.

So a severed edge's assets read **stale at HQ, not dead** — and the thing HQ
learns is about the link, which is exactly what `edge_buffer_status` already
tells it and what `assetTier.ts`'s `COMM_LOST` already distinguishes in the
browser. This decision promotes that distinction out of the browser.

### 5. The UI reads the columns; it stops being the authority

`assetTier.ts` becomes a *renderer* of carried state rather than a classifier
computing it. Its five tiers survive as presentation — the grey-out, the
recessed opacity, the `LOST`-hidden-from-3D rule — but the tier is read, not
derived, so every other tier and the egress see what the operator sees.

### 6. There is no state for "should never have been a member"

`DESIGN-2026-09-26`'s `EVICTED` is withdrawn. Under §1 there is no per-asset
delete, so an asset that was never real is carried as what it honestly is: an
asset **not reporting**, of **unknown variant**. The `dis:1:1:1099` residue
therefore stops being a bug and becomes a true statement about a thing that was
seen once and never accounted for.

**The cost of this, stated plainly rather than buried:** there is now no way to
remove one spurious asset. The only real delete in the system is the scenario
reset (`reset-scenario.sh`), it operates on the **deployment** and never on an
asset, and it says so in its own header. Between resets, a mistyped entity id
from a scenario file is permanent.

And that has a second-order obligation which must not be discovered later: a
carried not-reporting asset of unknown variant is still an **undeclared** asset,
so the `ADR-0029` completeness gate stays red until it is labelled. Because no
status change may be expressed as a delete, and residue carries no terminal
status for retention to act on, §1 therefore *forces* a labelling path for
residue. Declaring a spurious asset in
`releasability.yaml` to quiet the gate would launder a mistake into deployment
data, so the label must carry the honest fact — unknown variant, unaccounted —
rather than a plausible one. **That path is not designed here and is this ADR's
largest owed item.**

---

## Alignment declared (ADR-0038 C1 intake)

Two vocabularies are declared, one for the signal and one for the state. Both
are declared **with their provenance**, because a vocabulary that looks standard
while being invented is the failure `ADR-0043`'s C1 section names, and this
corpus has already had "ICD" and "contract" labels turn out to be
reconstructions.

### The signal — DIS, IEEE 1278.1

Three signals, and what we actually have of each:

| signal | status here |
|---|---|
| **entity-state timeout** by the standard's own heartbeat rule | The rule is the standard's. Our thresholds are **local**: `stale_after_s: 30` / `lost_after_s: 300` in `assetTier.ts`, `STALE_INPUT_SECONDS: 300` in fusion. These were sized for a ~1 Hz sim cadence, not derived from the standard's heartbeat, and saying so is the point. |
| **appearance record: damage and deactivated bits** | Decoded today — `ontology/dis_appearance.yaml:59-82`, `openddil-sensor-ingest/appearance.py:90-116`. **The bit numbering in that YAML is our own artefact and is not verified against the published standard.** It is cited here as our decoder's mapping; checking it against IEEE 1278.1 is owed and cheap. |
| **Remove Entity PDU** | **Not decoded at all.** The ingest path handles Entity State PDUs; the Simulation Management family is not parsed. So the one signal in DIS that means "this entity is gone" cannot currently reach any tier. This is the largest signal-side gap and it is new work, not a fix. |

One behaviour already correct and worth not breaking: `appearance.py:90` returns
`{}` for an all-zero appearance field rather than claiming `NONE`, i.e. it
refuses to report "no damage" when what it has is no information.

### The state — JC3IEDM / MIP

The state vocabulary is aligned to JC3IEDM's object-item model, in which an
object item carries an **operational status** and a **reporting status**, each
timestamped — which is precisely the two-column split §2 decides.

**Deliberately not restated here: the exact JC3IEDM attribute names and code
list values.** I do not have the specification in hand, and writing plausible
attribute names would produce exactly the artefact this corpus keeps catching —
something that reads as a standards citation and is a reconstruction. The
alignment is declared at the level of the model; **binding it to named JC3IEDM
attributes and code values is a required step before any field name is frozen,
and it is owed.**

Until then the columns are **OpenDDIL-local names with a declared JC3IEDM
alignment intent**, which is an honest rung on the provenance ladder and is the
same one `PLAN-arc2-slice2-opening-package.md` §2.1 used for the system
principal's identifier.

JC3IEDM appears in this corpus today only as aspiration
(`DESIGN-2026-09-06-interface-contracts.md:38,53`). This is the first decision
that would make it load-bearing, which is the reason to be careful about it.

---

## Predicted counts — compose, one entity times out and one is destroyed

The compose declared fleet is **14 assets**: 8 Atlantia (`dis:1:1:1000`–`1007`)
and 6 Borduria (`dis:2:1:1000`–`1005`), per `ontology/releasability.yaml`.

The case: **`dis:1:1:1003` stops transmitting** (times out), and
**`dis:1:1:1005` transmits an Entity State PDU with `damage = DESTROYED`** and
then also stops. Both are Atlantian, so the ATL view sees both and the BDR view
sees neither except through the shared asset.

### Today — predicted, and the prediction is the defect

| reading | t0 | t0 + 60s | t0 + 20min |
|---|---|---|---|
| rows in `telemetry_latest_state` | 14 | 14 | 14 |
| `dis:1:1:1003` health | `NOMINAL` | `NOMINAL` | `NOMINAL` (last known, forever) |
| `dis:1:1:1003` logistics severity | nominal | nominal | **DEGRADED** (`stale_inputs`) |
| `dis:1:1:1003` cm `lifecycle` | `ACTIVE` | `ACTIVE` | **`STALE`** (past 900s) |
| `dis:1:1:1005` health | `NOMINAL` | **`FAILED`** | `FAILED` |
| `dis:1:1:1005` logistics severity | nominal | critical/non-op | **DEGRADED-or-worse + `stale_inputs`** |
| rollup `asset_count` | 14 | 14 | 14 |
| rollup buckets | 14 nominal | 13 nominal, 1 non-op | **12 nominal, 2 in degraded-or-worse** |

**The defect in one number:** at t0+20min the regional rollup cannot distinguish
the destroyed vehicle from the one with a quiet radio. Both are in
degraded-or-worse; nothing carried says which is which; and if the *edge* had
been severed instead, all 8 ATL assets would land in `degraded` and the region
would read a materiel crisis caused by a network cable.

### Under this ADR — predicted

| reading | t0 | t0 + 60s | t0 + 20min |
|---|---|---|---|
| fleet total | 14 | 14 | **14** |
| operational: operational | 14 | 13 | 13 |
| operational: **destroyed** | 0 | **1** (`dis:1:1:1005`) | **1** |
| reporting: reporting | 14 | **13** | 12 |
| reporting: **not_reporting** | 0 | **1** (`dis:1:1:1003`) | **2** |
| `dis:1:1:1005` pair | `operational` + `reporting` | **`destroyed` + `reporting`** | **`destroyed` + `not_reporting`** |
| `dis:1:1:1003` pair | `operational` + `reporting` | `operational` + **`not_reporting`** | `operational` + `not_reporting` |
| rollup materiel buckets | 14 nominal | 13 nominal, 1 destroyed | **13 nominal, 1 destroyed** |

The t0+60s column is the whole argument: `destroyed` + `reporting` is a state
the current model cannot represent, and it is the state an entity is in during
the second it tells you it was hit.

Note what does **not** move: `dis:1:1:1003`'s operational status stays
`operational` at every timestep. We never heard it was damaged; we stopped
hearing from it. Concluding anything else from silence is the eviction mistake.

### The severance case, same fleet

With edge-01's uplink severed and all 8 ATL assets behind it:

| reader | fleet total | not_reporting | materiel picture |
|---|---|---|---|
| **edge-01's own view** | 14 | **0** | unchanged — it is hearing from everything |
| **HQ** | 14 | **8** | **unchanged** — 14 accounted for, 8 unheard |
| HQ, today | 14 | — | **8 assets in `degraded`** |

Same cluster, same instant, two correct answers, and the one that is wrong today
is the one a commander reads.

## Acceptance, borrowed deliberately

From `DESIGN-2026-09-26-asset-lifecycle.md`, because the test of a distinction is
that it is visible:

* *observed 6m ago · `stale_inputs` · DEGRADED · **reporting: not_reporting*** —
  a real asset behind a quiet uplink. Present, counted, flagged.
* *destroyed 2026-09-26 14:02 · **operational: destroyed** · asserted by edge-01*
  — present, counted, and counted as destroyed.

**If a quiet asset and a destroyed asset ever render alike, this failed.** That
is the same acceptance sentence as the earlier design, with the word "withdrawn"
replaced by "destroyed" because there is no longer a state that means absent.

The amended §1 does not weaken this, and reading it as though it does is the
mistake to avoid. A *destroyed* asset eventually ages out of retention and then
renders as absence — that is archival, and it is intended. A *quiet* asset never
does, at any age, because silence is not a terminal status and retention's
predicate requires one. The two therefore still diverge, which is what the
acceptance sentence asks. What would break it is retention reaping on age alone,
which is what §1 now forbids and what the code still does.

## What this does not decide

* **The migration of `LifecycleState`.** Whether the existing enum gains members,
  splits, or stays as the membership column with reporting beside it. It is a
  contract change with four readers and it deserves its own decision.
* **The JC3IEDM binding.** Named attributes and code list values, per §Alignment.
  Owed before any column name is frozen.
* **Remove Entity PDU ingest.** Decoding the Simulation Management family is new
  work of unknown size and is not scoped here.
* **The residue labelling path**, per §6 — the largest owed item.
* **Who may assert `destroyed`.** §4 says "the tier that owns the sensor", which
  is a location, not an authority. Against `ADR-0028` (the production warfighter
  system is authoritative for asset→edge→region, and OpenDDIL surfaces
  divergence rather than overriding it), an OpenDDIL-asserted destruction of an
  asset upstream still lists is a **divergence signal**, not a state change to
  be applied silently. Unresolved, and inherited unchanged from the earlier
  design.
* **Whether a status belongs in the customer egress vocabulary.** FMC has no
  obvious word for "destroyed but still counted", and inventing one in a
  connector is the failure `DESIGN-2026-09-06` §Contract A names.
* **Nothing about rate.** No measurement of how many spurious entities a live DIS
  multicast environment produces. The cheap thing to know before the work deploy
  is still the count of `kind=2` Entity State PDUs in one representative run.

---

## Amendment: posture, a third column

**2026-10-06.** A launcher displaces: it stows, moves, stops, and raises again.
None of that is "did this entity stop responding" (reporting) or "does this
entity still exist and function" (operational) — a moving launcher is fully
operational and fully reporting the whole time it is moving. It is a third,
independent fact, and this amendment gives it its own column rather than
folding it into either of the two §2 already drew:
`posture_status = emplaced | march_ordered | moving | emplacing | unspecified`.

### Why a column, not a status value

§2 ("Two columns, not one") exists because collapsing two orthogonal questions
into one field forces every reader to disentangle them again downstream. Adding
posture as a value *inside* `operational_status` or `reporting_status` would
repeat exactly that mistake a third time — "emplacing" is not a degree of
reporting, and "moving" is not a degree of being operational. The column is
new; the discipline is the one §2 already decided.

### States and the transition table

Five states, one of them the explicit no-claim state:

| state | meaning |
|---|---|
| `unspecified` | No claim. Cold start with no launcher-raised signal yet, or a platform with no launcher bit on its domain at all. Never guessed from a single reading. |
| `emplaced` | Stationary, launcher raised: ready to fire. |
| `march_ordered` | Stationary, launcher stowed, not yet moving: preparing to displace. |
| `moving` | In transit between positions. |
| `emplacing` | Just stopped, launcher not yet raised: preparing to fire from the new position. |

Decided per record by a state machine with two inputs — `launcher_raised`
(`true` / `false` / absent, where absent means "this domain has no launcher bit
at all", not "unknown this tick") and `speed` (derived from
`kinematics.velocity.ecef`, never from `ground_speed`, which this pipeline never
populates) — against two configurable holds (`POSTURE_MOVE_HOLD_S`,
`POSTURE_STOP_HOLD_S`) and a speed threshold (`POSTURE_MOVE_SPEED_MPS`;
defaults 10s / 20s / 1.0 m/s, env-overridable). First matching row wins:

| From | Reading | To |
|---|---|---|
| any but moving | moving held ≥ moveHoldSeconds | moving |
| moving | stationary held ≥ stopHoldSeconds, launcher_raised false | emplacing |
| moving | stationary held ≥ stopHoldSeconds, launcher_raised true | emplaced |
| emplacing, unspecified, march_ordered | stationary, launcher_raised true | emplaced |
| emplaced | launcher_raised false | march_ordered |
| cold start (no prior state) | stationary, stowed | unspecified (never guessed) |
| any | launcher_raised absent (no launcher bit on this platform) | only `moving` or `unspecified`: moving by the speed rule; after stopHold, stationary → unspecified |
| speed absent this record | — | no motion update; hold whatever motion state was already held |

**Power plant is not a gate.** The state machine never reads
`power_state`/`power_plant_on` as a precondition for any row above. That is a
choice, not an oversight: power is already its own orthogonal axis (field 1 of
`OperationalState`), and gating posture on it would re-collapse two facts the
rest of this ADR keeps apart — a launcher could in principle report posture
while its power axis is in `STANDBY`, and the state machine
should not have an opinion about that.

### Decided at the owning tier; carried, not re-derived

Same discipline as Decision 4: posture is decided **once**, at the edge tier
that owns the sensor (`openddil-tactical-agents/edge/posture.py`, called from
`faust_edge.py`), by a per-asset state machine with history (the `asset_state`
Faust Table, extended with the posture fields — defaults so a changelog record
written before this amendment still loads, as a cold start). Every other tier
(projector, store, every bridged topic reader) stores the decided value
unchanged; none re-derives it. A reset trims the changelog, so after a reset
every asset cold-starts `unspecified` again — the same externally-visible
effect retention's age-based pruning has elsewhere in this ADR, from an
unrelated cause.

### Does not feed readiness

`posture_status` is not an input to any readiness/FMC-NMC-PMC computation at
any tier. A `moving` or `emplacing` launcher is exactly as operational and as
reporting as an `emplaced` one; readiness already has its own two columns for
those questions, and posture answering a third question is not a signal that
either of them should change.

### Alignment declared (ADR-0038 C1 intake)

By concept name only, with provenance stated the same way §Alignment above
states it for the signal and state vocabularies — no attribute names or code
list values asserted, because the specification is not in hand:

`march_ordered` and `emplacing` follow the doctrinal march-order and
emplacement phases of a displacing launcher. Against JC3IEDM's object-item
operational-status intent: `march_ordered` / `moving` / `emplacing` declare
**"temporarily not operational" intent for the weapon function**; `emplaced`
declares **"operational" intent**. This intent is for **egress mapping only**
— `operational_status` itself is never changed by posture, exactly as the
state-machine's own transition table never reads or writes it.

**Deliberately not asserted:** any JC3IEDM attribute name or code list value.
Binding this intent to named attributes is a required step still owed, the
same gap §Alignment already names for the two existing columns. Snapshots of
an asset's state at the moment of march order and at the moment of emplacement
are named here as **owed, not built** — a natural follow-on once the egress
mapping above exists to snapshot against.

## Amendment: deactivated is reversible; destroyed and removed are not

**2026-10-10.** Section 2 made `operational_status` move only on a signal, and
every implementation read that as "a terminal value is permanent". For
`destroyed` and `removed` it should be. For `deactivated` it is wrong:
deactivation is a state an entity enters and leaves (DIS sets and clears the
appearance record's deactivated bit on the same entity), so a row that can
never leave it misreports every entity that was switched off and on again.

### The rule

| status | what returns it to `operational` |
|---|---|
| `deactivated` | the asset **reappears**: a record carrying the asset's own kinematics and no terminal claim |
| `destroyed` | only a reset (which empties the stores) or an explicit restore. A destroyed entity keeps transmitting (section 2), so a later record proves nothing. No restore action exists today, so for now that means reset only |
| `removed` | only a reset. A Remove Entity has no undo on the wire: bringing the entity back would take a Create Entity, which is a new entity |

Silence still changes nothing. A record without kinematics is not an
appearance. Neither is a status-only record, nor a record that carries any
terminal claim.

### Where it is decided

The rule is the same at every reader, and it is decided from the record, not
from local history:

* **Stores** (projector, every tier). On a full-row record with no claim, the
  upsert rewrites `operational_status` from `deactivated` to `operational` and
  stamps `operational_status_at`. It leaves any other value alone. The
  condition is evaluated against the stored row in the same statement, so two
  readers can never disagree about what they last stored.
* **Regional rollup.** The edge source forwards terminal claims as before,
  and also forwards an *appearance*. It forwards one immediately after it
  has forwarded a `deactivated` claim for that asset, and otherwise at most
  once per interval per asset; the interval is what covers a source restart.
  The aggregator clears `deactivated` only for an asset it already holds. An
  appearance never creates an entry, because entries are what the rollup
  counts.

Section 1 rule 3 (only terminal rows are prunable) is unchanged. A revived row
is `operational` again, so it stops being eligible for pruning.

## Amendment: the deployment signal is per variant

**2026-10-10.** The posture amendment above gave the state machine one
deployment input, `launcher_raised`, and the decoder fed it for every land
platform whose appearance was decoded. Two things were wrong with that, both
measured on a live fleet:

- A sensor displaces too, but it has no launcher. A stationary radar never
  read `emplaced`, however long it radiated from one position.
- Any land platform whose source sends appearance at all (a damage claim is
  enough) decodes the launcher bit as `false`. A damaged tank that stopped went
  `moving → emplacing`, a deployment phase a tank does not have.

**Decision.** Each platform variant declares which deployment signal it has, if
any, in `ontology/dis_entity_types.yaml` (`deployment_signal`, curated by PR
like the variant itself):

| `deployment_signal` | input | true means | false means |
|---|---|---|---|
| `launcher_bit` | `launcher_raised` (appearance) | launcher raised | launcher stowed |
| `emission` | `emitting` (Electromagnetic Emission PDU) | radiating: at least one beam | an explicit EE with no beams: deliberately not radiating |
| absent | none | — | — |

The ingress mapper, where the variant is resolved, passes through only the
declared signal; the other is deleted, never defaulted. The state machine reads
one input, the deployment signal, through the same transition table as before
with "launcher raised / stowed" read as "deployment signal true / false". So
the rule is: **stationary with the variant's deployment signal → emplaced;
stationary without it → unspecified, as before.** A variant with no declared
signal never leaves `moving` / `unspecified`, which is the row the table
already had for "no launcher bit on this platform".

**Silence is not a signal.** `emitting` is set only from an EE PDU seen within
the emitter's baseline `silence_after_s`. No EE at all is the absence of a
claim (`emitting` unset): posture does not move, and the condition decoder
still reads it `SENSOR_FAILED` once armed. Only the explicit zero-beam EE, the
emitter's own statement that it is not radiating, is `false`; the condition
decoder reads that `NOT_EMITTING`, not `SENSOR_FAILED`. An unexplained silence
therefore never march-orders a radar, and a radar that stows deliberately is
never reported failed.

The sequence for a displacing sensor is then the launcher's, with the signal
swapped: emplaced and radiating → goes silent (zero-beam EE) → `march_ordered`
→ moves → `moving` → stops → `emplacing` → radiates → `emplaced`.

### Alignment declared (ADR-0038 C1 intake)

By concept name only, as the posture amendment's own declaration: a sensor's
`march_ordered` / `emplacing` follow the doctrinal emission-control and
emplacement phases of a displacing sensor, with radiating as its deployed
state the way a raised launcher is a launcher's. The same JC3IEDM
operational-status intent applies, for egress mapping only.

**Deliberately not asserted:** any JC3IEDM attribute name or code list value,
any DIS emitter-system enumeration as the meaning of "deployed", or a
beam-function filter (a search beam and a track beam count the same here).
Which beams make an emitter "radiating" for a given variant is owed when a
variant needs the distinction.
