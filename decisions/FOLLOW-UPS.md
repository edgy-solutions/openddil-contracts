# Follow-up index

**Reconciled:** 2026-08-12. **This file is a POINTER, never a source.**
Every row's authority is its home document; if they disagree, the home wins
and this file is the thing that is wrong.

## OPEN 2026-09-23 — the DIS fixture reaches PyPI at container start

**Opened, not scheduled.** Noticed while closing the mirror-coverage gap in
openddil-helm; recorded because the fixture sits just outside what that
check can see.

`tools/dis-sim/k8s/dis-sim.yaml` runs both simulator containers as
`python:3.11-slim` with `pip install --quiet --no-cache-dir opendis==1.0`
in the start-up command, then execs the generator from its ConfigMap mount.
So each restart needs egress to docker.io for the base image and to PyPI
for the wheel.

That was a deliberate trade when it was written: no image to build, no
registry to maintain for a test fixture, and the version pin kept where a
reader can see it must match what sensor-ingest decodes with.

**What changed around it.** openddil-helm now has
`scripts/check-mirror-coverage.sh`, which renders the chart with every
optional stack on and refuses any image the mirror inventory does not carry
or that does not resolve by digest. The fixture is not part of the chart,
so nothing in that check reaches it — but it is part of what a lab
deployment pulls. An air-gapped site that mirrors everything the check
demands still cannot start the simulator.

**Why the cost is low where it matters most.** A site that already runs its
own computer-generated-forces application takes DIS from that application
instead, and deletes this Deployment entirely; the fixture exists so that a
site without one still has wire-compatible traffic. The gap therefore bites
exactly the case the fixture is for: a disconnected lab with no CGF.

**To close, in the order that costs least:**
1. Mirror `python:3.11-slim` — already done, chart-side, as part of the
   releasability PEP's base image.
2. Vendor the wheel alongside the generator's ConfigMap, or bake generator
   and dependency into one small image published with the other
   OpenDDIL-owned images, which also removes the per-restart delay.
3. Either way, keep the version where the pin and the decoder's expectation
   stay visible to the same reader.

## OPEN 2026-09-23 — the per-site entity count and the pin map state the same fact twice

**Not now.** Recorded when it was noticed, in the dispatch that introduced
the overlap. No work is scheduled.

Since openddil-customer-bundle-example 29beeb6, dis-sim gets the platform
for an entity id from `DEFAULT_ENTITY_PLATFORMS` (or
`DIS_ENTITY_PLATFORMS_PATH`). How many entities it builds is still a
separate number: `--entities` / `DIS_ENTITIES`, set per site in
`tools/dis-sim/k8s/dis-sim.yaml` (8 at northpoint, 6 at capeverdant). The
map already says which ids exist at each site. The count repeats it.

**The count should derive from the map**: for the site and app dis-sim is
running as, build exactly the ids the map pins, and keep `--entities` only
as an explicit override that must be a subset.

**Which way each direction of drift fails.**
- *Count above the map:* refused. `platform_for` raises `SystemExit` for an
  unpinned id, so the sim stops at start-up rather than emitting an asset
  whose platform nothing declared. Verified with `--entities 9` at site 1.
- *Count below the map:* silent. The pins for the missing ids are simply
  never used, and the fleet is quietly smaller than the map says. Nothing
  reports it. This is the direction that would mislead a reader who takes
  the map as the fleet, which is the reading the map invites.

The manifest is also the only place a second site's id range is declared. A
site whose map has ids but whose deployment sets a lower count looks, from
the map alone, like a fleet that is not emitting.

**Not doing it now costs little:** the two lab edges are the only
deployments, their counts match their pins, and
`tests/test_dis_entity_platforms.py` pins the map to the deployed snapshot.
The cost arrives with a third site, or with the first scenario that supplies
`DIS_ENTITY_PLATFORMS_PATH` without also setting a matching count.

**To close:** derive the count in `main()` from the pins for
`--site-id`/`--app-id`, make `--entities` an override that is refused when
it exceeds the pinned ids, and delete `DIS_ENTITIES` from both containers in
`k8s/dis-sim.yaml`. Then a test that a site's entity count equals its pin
count. See "the next deploy relabels two simulated assets" for the map
itself.

## OPEN 2026-09-21 — the next deploy relabels two simulated assets

A **prediction from reading code, not a measurement.** Nothing is deployed.
It covers the next rollout of openddil-customer-bundle-example 29beeb6
(dis-sim pins each entity id to one platform) together with 77d8657
(SISO-REF-010-v37 tuples) and the ontology.

**Why the prediction changed.** dis-sim used to derive an id's platform from
its position in the type list, `types[index % len(types)]`, so shortening
the list moved six ids to other platforms. Each id is now pinned in
`DEFAULT_ENTITY_PLATFORMS`, and the type list's order means nothing. The
map keeps every id on the platform it reports at revision 50, except the
two RCV-M ids. `tests/test_dis_entity_platforms.py` holds the map to that
snapshot and checks that reordering the list relabels nothing.

**Fleet: 14 before, 14 after.** Per variant: RCV-M 2 → 0, AH-64E-V6 2 → 4.
Every other variant and every other id is unchanged.

| asset | before | after |
|---|---|---|
| dis:1:1:1004 | RCV-M | AH-64E-V6 |
| dis:2:1:1004 | RCV-M | AH-64E-V6 |

Every one of the 14 ids changes its **tuple** (77d8657), and the ontology
resolves each new tuple to the variant it had before. So on the variant axis
only the two rows above move.

**Predicted delta:**
- **Relabels: 2.** The two rows above. The upsert tables, each keyed on
  `asset_id`, overwrite the variant in place on the first record. Both ids
  keep emitting, so no row goes stale.
- **CM baseline mismatches: 0.** The three assets with a baseline,
  dis:1:1:1001, dis:1:1:1006 and dis:2:1:1001, keep their platforms (M1A2-SEPv3,
  UH-60M and M1A2-SEPv3). The two relabelled ids have no baseline.
- **Wear clears: 1.** At revision 50, dis:1:1:1004 was one of the two assets
  the region rollup counted CRITICAL, because its RCV-M track was fully
  consumed. The AH-64E-V6 wear manifest declares `[engine, barrel]` and no
  track, so that CRITICAL clears and the region critical count goes from 2 to 1.
  The one way this fails is if 1004's engine is itself critical; if 1004 is
  still CRITICAL, read which factor drives it before narrating it.
  dis:2:1:1004 was not CRITICAL, and there is nothing for it to clear.
- *Unchanged:* releasability, which is declared per id. Display: both ids
  showed the Unknown badge as RCV-M and still show it as AH-64E-V6, because
  the schematic registry keys `AH-64E`, not `AH-64E-V6`. No fixed-wing asset is
  emitted, and the F-35A-Block4, F-16C-Block50 and MQ-9A-Block5 keys all
  stay unemitted.

**Doc lines that cite the count or the affected assets.**

| line | status |
|---|---|
| openddil-helm `PILOT-RUNBOOK.md:472` | aligned in 6118266: "11 keys for 10 platforms" |
| openddil-customer-bundle-example `tools/dis-sim/dis_sim.py`, the type-list comment and the `--list-types` heading | aligned in 29beeb6: each tuple is a key in the ontology, one tuple per platform |
| openddil-contracts `DESIGN-2026-08-11-declared-asset-class.md:99`, "All 11 entries are `kind=1`" | a dated record, left as written |
| openddil-helm `scripts/RECORDING-READINESS.md:384-385` | a revision-50 measurement. After the deploy, `1001`, `1006` and `1002` still name the same platforms and `1004` is an AH-64E |
| openddil-contracts `GENERALIZATION-DEBT.md:77`, "14/14" | fleet size, unchanged |

**To close:** after the deploy, run `SELECT asset_id, platform_variant FROM
telemetry_latest_state` and compare it with the tables above: exactly two
ids should differ from revision 50. Then read the region critical count
(expect 1) and each baseline holder's `baseline_id` against its variant
(expect 0 mismatches). Any other difference is a finding.

## SUPERSEDED 2026-09-21 — the next deploy relabels six simulated assets

**Superseded the same day** by "the next deploy relabels two simulated
assets". openddil-customer-bundle-example 29beeb6 pins each dis-sim id to
one platform, so the six-id relabel below describes code that no longer
ships. It is kept because the mechanism it found, platform by list
position, is why the pinning exists.

A **prediction from reading code, not a measurement.** Nothing is deployed.
It covers the next rollout of openddil-customer-bundle-example 77d8657
(dis-sim's list, 11 → 10 types) together with the ontology.

**The fleet count does not change: 14 before, 14 after.** dis-sim creates
`DIS_ENTITIES` entities (8 at northpoint, 6 at capeverdant, per dis-sim's
`k8s/dis-sim.yaml`) and assigns types round-robin,
`types[index % len(types)]`. The number of entities is
set by that variable, not by the length of the list. With 8 and 6 entities
the list never reached its last three entries, so shortening it moves
assignments instead of removing an asset. The distinct variants on the wire
are also 8 before and 8 after.

| asset | before | after |
|---|---|---|
| dis:1:1:1004 | RCV-M | AH-64E-V6 |
| dis:1:1:1005 | AH-64E-V6 | UH-60M |
| dis:1:1:1006 | UH-60M | CH-47F-BlockII |
| dis:1:1:1007 | CH-47F-BlockII | F-35A-Block4 |
| dis:2:1:1004 | RCV-M | AH-64E-V6 |
| dis:2:1:1005 | AH-64E-V6 | UH-60M |

Per variant: RCV-M 2 → 0, UH-60M 1 → 2, F-35A-Block4 0 → 1. Every other
variant keeps its count, though AH-64E and CH-47F move to different ids.
The other eight assets are unchanged.

**What follows, per store.**
- *Upsert tables* (`telemetry_latest_state`, `asset_logistics_status`,
  `asset_telemetry_windows`, `asset_element_telemetry`, each keyed on
  `asset_id`) overwrite the variant in place on the asset's first record.
  No row goes stale, because all six keep emitting. **This corrects the
  RCV-M paragraph of "before the SISO-aligned tuples deploy"**: the RCV-M
  ids do not go quiet; they come back as AH-64Es.
- *Wear.* At revision 50, dis:1:1:1004 was one of the two assets the region
  rollup counted as logistics CRITICAL: the RCV-M with fully consumed
  track. An AH-64E has no track component in the wear manifest. Expected:
  that CRITICAL clears, and the region critical count goes from 2 to 1
  unless some AH-64E component is itself critical. If 1004 stays CRITICAL,
  read which factor drives it before narrating it.
- *CM.* dis:1:1:1006 is one of the three assets that carry a CM baseline.
  Baselines attach to an asset through `baseline_assigned` events, are
  replayed from `cm-events` (compact+delete, 30 days), and are **not
  re-derived from the variant**. So 1006 keeps the baseline it was given as
  a UH-60M while it reports as a CH-47F. Its CM discrepancies would then
  be one platform's configuration judged against another's: the mislabel
  class again, one layer down. dis:1:1:1001 and dis:2:1:1001 are unchanged.
- *Releasability* (`openddil-demo/ontology/releasability.yaml`) is declared
  per id without a variant, so labels carry over unchanged.
- *Display.* dis:1:1:1007 becomes the first fixed-wing asset in the
  simulated fleet. F-35A-Block4 has a CM baseline file and an ontology
  entry, but no wear-manifest entry (fixed wing is exempt), so it shows no
  wear factors. Among DIS variants only M1A2-SEPv3 has a schematic, so the
  F-35A renders as the Unknown badge, as the RCV-M did.
- The F-16C-Block50 and MQ-9A-Block5 keys are still never emitted.

**Doc lines that cite the count or the affected assets.**

| line | says | status |
|---|---|---|
| openddil-helm `PILOT-RUNBOOK.md:472` | "currently **11 entries**" | aligned in 6118266: "11 keys for 10 platforms" |
| openddil-contracts `DESIGN-2026-08-11-declared-asset-class.md:99` | "All 11 entries are `kind=1`" | dated record, left as written; true again by coincidence (11 keys since 90b8ee9) |
| openddil-customer-bundle-example `tools/dis-sim/dis_sim.py:84-91`, `:524` | list "transcribed from" the ontology; `--list-types` titled "from ontology/dis_entity_types.yaml" | no count, but now claims equality that no longer holds (10 tuples vs 11 keys); not edited |
| openddil-helm `scripts/RECORDING-READINESS.md:384-385` | CM for `1001`, `1006`; logistics CRITICAL for `1002`, `1004` | a revision-50 measurement, correct as history; those ids mean different platforms after the deploy |
| openddil-contracts `GENERALIZATION-DEBT.md:77` | "14/14" | fleet size, unchanged |
| openddil-contracts `ontology-siso.yml:6`, `PRINCIPLES.md` §*A reference table is looked up* | "eleven" | the history of the first set, correct |

**To close:** after the deploy, run `SELECT asset_id, platform_variant FROM
telemetry_latest_state` and compare it with the table above. Read the
region critical count, and read 1006's `baseline_id` from cm-service. If
1006 still carries a UH-60M baseline, that is a decision: reassign it, or
pin dis-sim's order so ids keep their platforms. It is not a fix to
improvise.

---

## RESOLVED 2026-09-21 — RCV-M stays unmapped

**Decision (user, 2026-09-21).** RCV-M has no SISO-REF-010-v37 entry at any
level, so the shared ontology gives it no key. The key is not invented, and
no local range is chosen here.

**The mechanism for local tuples is the overlay.** A deployment that needs
a locally defined type declares it as deployment data, in two halves:

- **Emitting side:** the dis-sim enumeration overlay
  (`DIS_ENTITY_TYPES_PATH`; template, example, validator and runbook in
  openddil-customer-bundle-example `tools/dis-sim/enumeration/`). Its
  validator reports a non-SISO row as a WARN and counts it in
  `NOT_IN_SISO`, which is the right shape for a deliberate local type.
- **Resolving side:** the deployment's ontology overlay (ADR-0029 §3,
  `openddil-demo/ontology/` → `/bundle/demo/ontology/`). The chart's
  bundleInit copies it over `contracts/ontology`.

**What the resolving side does not do yet.**

- bundleInit's overlay is `cp -r src/. dst/`, so on a filename collision
  the later copy wins. A deployment that ships `dis_entity_types.yaml`
  therefore **replaces the whole shared file**. It must carry every shared
  key as well as its own, and it drifts from openddil-contracts on every
  change there.
- The SISO check (`ontology-siso.yml`) sees only the contracts file. It
  never sees an overlaid one, and it would refuse a local key if it did.

So the overlay is the right place for local tuples, but on the resolving
side it is currently a whole-file override, not a merge of added keys.
Making local keys additive (a separate overlay file merged at lookup
time, with a check that its keys are **absent** from SISO) is the step that
would turn the overlay into the mechanism this row names. No deployment
needs it today.

**Where RCV-M still appears.** Its wear-component entry in openddil-demo
`ontology/wear_component_manifest.yaml` is kept. It is keyed by variant
name, is harmless when unused, and is what a deployment that emits RCV-M
through the overlay would need. The simulated RCV-M assets become
AH-64Es; see "the next deploy relabels two simulated assets".

---

## OPEN 2026-09-21 — before the SISO-aligned tuples deploy: which stored rows carry the earlier tuples

A **prediction from reading code, not a measurement.** Nothing here has been
deployed or queried. It is recorded so the deploy is checked against it,
not reasoned about afterwards.

**Where a tuple or its resolution is stored.** Resolution happens once, at
ingress (`openddil-demo/dynamic-mappings/sim-dis-mapping.yaml:54-96`), and
the raw 7-tuple travels on beside the result in `AssetIdentity.dis_entity_type`
(`telemetry.proto:317-325`).

| store | carries | shape | prediction after deploy |
|---|---|---|---|
| `ingress-dis-raw` | raw tuple | delete, 24h | ages out within a day; until then a replay resolves the earlier tuples to `_default` → UNKNOWN |
| `asset-logistics-status` | tuple + variant | **compact, retention -1** | the last record per asset keeps the earlier tuple **indefinitely**, until that asset emits again |
| `asset-telemetry-windows` | variant | delete, 24h | ages out |
| `telemetry_latest_state`, `asset_logistics_status`, `asset_telemetry_windows`, `asset_element_telemetry` (`platform_variant`) | variant only | upsert per asset_id | re-resolved on the asset's next record; stale only for assets that stop emitting |
| Restate `AssetLogistics.latest_telemetry_dict` | tuple + variant | per-asset durable state | discarded only where `ephemeralOnUpgrade` actually wipes that tier |
| `tactical_events` | neither | append | unaffected |
| `region_fleet_summary` | no variant grouping found | — | unaffected |

**The part that is not a re-resolve.** In the lab, the *variant names* in
stored rows are right: the ontology and dis-sim were wrong together, so every
asset resolved to its intended name, and the names do not change. What is
wrong is the **raw tuple stored beside the name**. The earlier tuples are
real SISO keys for other platforms — the stored M1A2-SEPv3 carries SISO's
M551A1 key. Any consumer that reads `dis_entity_type` and looks it up in SISO
gets a different platform from the one displayed. Upsert and compaction fix
that only for assets that emit again; an asset that never re-emits keeps the
earlier tuple indefinitely in the compacted topic.

**RCV-M.** It is no longer mapped or emitted. Its upsert rows and its last
compacted record stay, labelled RCV-M, with a tuple SISO does not define,
until they are flushed. That is a stale asset, not a mislabelled one.
*Correction 2026-09-21: wrong for the lab. dis-sim assigns types by index,
so the two RCV-M ids keep emitting, as AH-64Es, and their rows are
overwritten in place. This holds only for an RCV-M that stops emitting. See
"the next deploy relabels six simulated assets".*

**What append-only means here.** ADR-0019 splits projection into upsert for
compacted state and append for event streams, and the provenance chain is
append-only by rule. No record is rewritten in place. A correction is a
**new record that supersedes**: by key where the store is compacted or
upserted, and never where it is a stream. So the earlier tuples are not
wrong history to be edited. They are what was emitted, under the ontology in
force then. The correction is complete when every live asset has emitted
under the new ontology, and when anything that never will has been flushed
deliberately (`flush-assets.sh`), not waited out.

**To close:** after the deploy, count the `asset-logistics-status` records
and `telemetry_latest_state` rows whose tuple is not in the current ontology,
and confirm the count reaches 0 once every asset has emitted again, or once
the leftovers are flushed. Update the four places listed in the RESOLVED row
below first, or the demo tests will fail against the new ontology. *(Done
2026-09-21; the per-asset consequence is in "the next deploy relabels six
simulated assets".)*

---

## RESOLVED 2026-09-21 — the ontology's DIS tuples are aligned to SISO-REF-010-v37

**In repo, not deployed.** openddil-contracts be97329 (ontology + CI) and
openddil-customer-bundle-example 77d8657 (dis-sim's built-in list), pushed
together. The two live in different repos, so "one commit" is two paired
commits that cite each other.

**Finding.** Checked against SISO-REF-010-v37 (2026-05-25, the XML in
open-dis/opendis7-source-generator at 604a0ee9, sha256 eaafe0b8…), **0 of 11**
ontology keys named the platform they were mapped to. Seven existed in SISO
as a different platform; four did not exist. The header's country codes were
wrong as well (USA is 225, UK 224, Canada 39). dis-sim emitted the same
tuples, so the lab resolved every entity and nothing could notice. A stock
CGF would have been mislabelled, not merely unresolved.

| platform_variant | was | SISO name at old key | now | SISO name at new key |
|---|---|---|---|---|
| M1A1 | 1_1_225_1_1_1_0 | M1 Abrams | 1_1_225_1_1_2_0 | M1A1 Abrams |
| M1A2-SEPv3 | 1_1_225_1_3_1_0 | M551A1 | 1_1_225_1_1_18_0 | M1A2 SEP V3 (M1A2C) |
| M2A3-Bradley | 1_1_225_2_1_1_0 | M2A2 Bradley Infantry Fighting Vehicle (IFV) | 1_1_225_2_1_9_0 | M2A3 Bradley IFV |
| HMMWV-M1151A1 | 1_1_225_3_1_1_0 | M88A1 | 1_1_225_6_1_32_1 | M1151A1 Integrated Armor Protection (IAP) |
| AH-64E-V6 | 1_2_225_20_1_3_0 | AH-64C | 1_2_225_20_1_7_0 | AH-64E Guardian with Longbow Radar |
| UH-60M | 1_2_225_21_1_2_0 | UH-1B | 1_2_225_21_2_26_0 | UH-60M |
| CH-47F-BlockII | 1_2_225_22_1_1_0 | SH-2 | 1_2_225_23_1_9_0 | CH-47F |
| F-35A-Block4 | 1_2_225_40_1_5_0 | *absent* | 1_2_225_1_12_1_0 | F-35A CTOL |
| F-16C-Block50 | 1_2_225_41_1_1_0 | *absent* | 1_2_225_1_3_3_4 | F-16C Block 50/52 |
| MQ-9A-Block5 | 1_2_225_50_1_1_0 | *absent* | 1_2_225_50_34_1_0 | MQ-9A Reaper |
| RCV-M | 1_1_225_80_1_1_0 | *absent* | **not mapped** | no SISO entry at any level |

**Granularity.** SISO does not enumerate V6 (AH-64E), Block II (CH-47F),
Block 4 (F-35A) or Block 5 (MQ-9A); those keys name the nearest SISO entry,
and the variant suffix is ours. F-16C maps to SISO's combined "Block 50/52"
extra.

**Choices a reviewer may overturn.**
- RCV-M is dropped, not given an invented key. It still exists by variant
  name in openddil-demo's wear-component manifest. A locally defined tuple
  would need a decision on which range to use.
- MQ-9A: SISO has two entries for the airframe — "MQ-9A Reaper"
  (1.2.225.50.34.1.0, chosen) and "Predator B" (1.2.225.50.4.4.0). A CGF may
  emit either; only the first resolves. *Update 2026-09-21: both are now
  mapped (90b8ee9).*
- AH-64E: chosen with Longbow (.7); without Longbow is .8. F-16C: the CJ is a
  separate specific (1.2.225.1.3.10.0), not mapped.

**Mechanism.** `.github/workflows/ontology-siso.yml` runs
`scripts/check-ontology-siso.py`: fetch v37 at the pinned commit, verify the
hash, index the Entity Types table (uid 30) only, and fail on any key absent
or whose SISO name differs from the entry's `siso_description`. A permanent
red-check step plants one mislabelled key (SISO's M551A1 in place of the
M1A2 SEP V3) and requires the check to refuse it. The same workflow runs
`tests/test_ontology.py`, which previously ran in no CI.

**Not changed here** — these still carry the earlier tuples and will
disagree with the ontology once it deploys: openddil-demo
`tests/hero_scenario_v3` (test_04, 09, 10 and ~15 tests passing
`category=1, subcategory=3` kwargs), openddil-sensor-ingest
`fixtures/generate_fixtures.py` and its README, openddil-helm
`PILOT-RUNBOOK.md` (the tuple table), and a comment in openddil-demo
`dynamic-mappings/sim-dis-mapping.yaml`. Stored history: see the OPEN row
above. *Update 2026-09-21: all four aligned — openddil-demo 420b6dc,
openddil-sensor-ingest ec99387, openddil-helm 6118266. RCV-M: see "RCV-M
stays unmapped".*

---

## OPEN 2026-09-19 — a human-raised CRITICAL discrepancy is accepted and surfaces nowhere

Found by a mis-aimed emit-path probe, which is the only reason anyone looked.

`cli/submit_cm_event.py --manual-discrepancy 'CRITICAL|...'` against an asset
with no CM baseline is accepted at every layer and produces nothing:

  CLI            prints "Published dis:1:1:1000: manual_discrepancy (event_id=...)"
  Kafka          cm-events partition 1, high-watermark 0 -> 1
  Restate        group cm-service-cm-events-edge-01, offset 1, LAG 0
  handler        POST /invoke/AssetCM/apply_cm_event -> 200
  result         no status change, no tactical event, NO LOG LINE AT ALL

The cause is one early return in `_reanalyze`:

    if not record.baseline_id:
        record.manual_discrepancies = preserved_manual
        return record  # registered but no baseline assigned

`_apply_event_to_record` has already appended the CRITICAL discrepancy, so it
IS stored. `_reanalyze` then returns before recomputing `overall_status`, so
the asset stays at its prior value, `_persist_and_emit_transitions` sees no
transition, and the alert gate never opens. Every layer reports success and
the finding is invisible.

SCOPE: 12 of 14 assets. Only dis:1:1:1001, dis:1:1:1006 and dis:2:1:1001 carry
a baseline (GD-14 records the coverage as 3 of 14).

WHY THIS IS WORSE THAN A DROPPED EVENT. The handler ALREADY HAS the
drop-with-a-reason shape for the adjacent case -- an event for an unknown
asset logs "Dropping CM event for unknown asset" and returns. A known asset
with no baseline gets no such line. The distinction the code draws is between
"I have never heard of this asset" and "I have heard of it and cannot judge
it", and only the first is spoken. ADR-0035 is about surfaces refusing to
show what they cannot support; this is the same rule one layer down, in a
handler that accepts an input it cannot act on and says so to nobody.

It is also the reverse of the usual shape in this corpus. GD-11 and GD-12 are
about a value being INFERRED where it was not declared. Here a value was
DECLARED, by a human, explicitly, at the highest severity the vocabulary has
-- and the system dropped it on the floor because a different, unrelated field
was absent. An inference failure produces a wrong answer; this produces no
answer while reporting success.

NOT FIXED. Three shapes, none obviously right:
  (a) log and count the swallow, so it is at least visible -- smallest, and
      leaves the discrepancy unactioned.
  (b) let a MANUAL discrepancy set overall_status even with no baseline. A
      human assertion does not need a baseline to be true, and the analyzer's
      early return is about ANALYZER-derived findings. Probably correct, and
      it changes what overall_status means for baseline-less assets.
  (c) refuse the event at intake with a reason, the way the unknown-asset
      path already does.
(b) with (a)'s counter is the likely answer. Deliberately not picked.

RESIDUE, disclosed: dis:1:1:1000 currently holds one such swallowed CRITICAL
from the probe. It is inert and invisible while that asset has no baseline,
it WOULD activate if one were ever assigned, and it is cleared by the next
helm upgrade, since the wipe hook discards Restate Virtual-Object state.

Related: GD-14 (baseline coverage), ADR-0035, and the derive-stage row below
-- both are a mechanism returning success for a question it did not answer.

---

## OPEN 2026-09-19 — check-derive-stage counts an ARRIVAL as a COMPLETION at region-east

Found while verifying a fresh session's pre-flight against the cluster rather
than against this corpus.

check-derive-stage.sh carries a hardcoded matrix that applies the same two
"OUTPUT TOPIC" terms to all three tiers:

  edge-01|...|asset-cm-state asset-logistics-status
  edge-02|...|asset-cm-state asset-logistics-status
  region-east|...|asset-cm-state asset-logistics-status

At region-east, asset-cm-state is NOT an output. Nothing there produces it.
The tier bootstrap says so in its own log, deliberately:

  [tier region-east] NO DIRECT INGEST -- detection not bound to relayed raw
  topics ['cm-events', 'raw-sensor-stream']; keeping 4 of 7 subscriptions

All four of region-east's live subscriptions sink to AssetLogistics. There is
no AssetCM subscription at that tier, and openddil-tier-cm-region-east has
served ZERO invocations since it started (11h, one log line in 30 minutes,
against 3926 and 4318 lines per 30 minutes at the two edges). The topic
advances because edge-01 and edge-02 bridge their derived state up.

MEASURED, twice, 60s each:

  sample A   edge-01 +99   edge-02 +75   sum 174   region-east +174
  sample B   edge-01 +99   edge-02 +75   sum 174   region-east +175

The identity holds to one message of cross-broker sampling skew. The contrast
is the proof: asset-logistics-status over the same windows was +17/+14 at the
edges against +60 at the region -- NOT a sum, because the region genuinely
derives that one locally over 14 assets. One row is pass-through, the other is
real work, and the check reports them identically.

WHY IT MATTERS, stated no higher than it goes. This does not create a false
green for the region's derive stage: asset-logistics-status is a genuine
AssetLogistics output, it is measured, and the check requires every row
advancing, so a region fusion stall is still caught. Three narrower things are
true instead:

  * The script's own term 2 is "the handler's OUTPUT topic advances." That row
    re-measures term 1 -- arrival -- under term 2's name. CONSUMED IS NOT
    COMPLETED is this script's founding sentence, and the substitution it was
    written to delete has reappeared at the one tier whose wiring differs.
  * "6 advancing" reads as three tiers completing two derive stages each. It
    is five completion terms and one arrival term.
  * A reader who sets "region-east asset-cm-state +174 advancing" beside a
    deployed openddil-tier-cm-region-east pod concludes the region's CM
    service is working. It has never been invoked.

The failure direction is mislocated attribution, not a missed failure: if both
edges stopped, that row goes frozen AT REGION-EAST and accuses the region of a
fault belonging to its children.

NOT FIXED, and the choice is real rather than a typo. THREE options, for the
user to pick; none implemented here.

  (a) DROP THE ROW. region-east has one derive stage, not two. Smallest
      change, and it discards a real signal -- nothing else currently asserts
      that child state is arriving at the parent.

  (b) KEEP IT, RELABEL IT. Measure the same topic under a term that says it
      is ARRIVAL, not completion. Changes what the script claims rather than
      what it reads, and keeps the bridge-liveness signal.

  (c) DERIVE THE TERMS FROM EACH TIER'S DECLARED OUTPUTS, rather than keeping
      a matrix by hand. The wiring is already declared and already correct:
      the tier bootstrap computes exactly this when it logs "NO DIRECT INGEST
      -- detection not bound to relayed raw topics; keeping 4 of 7
      subscriptions," and Restate will list a tier's live subscriptions on
      request. A tier's completion terms are the OUTPUT topics of the
      handlers it actually has subscriptions for; its arrival terms are the
      rest. Derived that way, region-east's asset-cm-state classifies itself
      correctly with no one remembering to, AND A FOURTH TIER GETS RIGHT
      TERMS WITH NO EDIT -- which the hand-kept matrix cannot do, and which
      is the same forcing function GD-04 applies to presentation.

      This is the one that removes the defect's CAUSE rather than its
      instance. The matrix is a second, hand-maintained statement of wiring
      the deployment already declares -- PRINCIPLES.md "A second
      implementation of a rule is a second rule," and the two disagreed the
      moment a tier's wiring stopped matching the others'. It is also the
      most work, and it makes a pre-flight check depend on the admin API of
      the thing it is checking, which is a coupling worth weighing rather
      than assuming: an instrument that reads its subject's own account of
      itself cannot catch that account being wrong.

(b) is the cheapest honest fix and (c) is the one that stops this recurring.
Deliberately not picked here.

Same shape as hq_link_severed below: a mechanism behaving correctly for its
own definition and wrongly for the one a reader assumes. Related:
PRINCIPLES.md §A column that answers a different question, §A mechanism that
covers one of N is an absent mechanism with a reassuring name.

NOT A BLOCKER for the recording. The pre-flight's five checks are green on
their own terms, and every number in RECORDING-READINESS §C re-measured
correct on 2026-09-19.

---

## OPEN 2026-09-19 — hq_link_severed tracks the simulator, not reachability

Found by the severance rehearsal. edge-01 severed with sever-tier.sh (a
NetworkPolicy), and its edge_buffer_status row reported truthfully on two
fields and misleadingly on the third:

  bridge_group_lag   2713 -> 3020   climbing, correct
  probe_healthy      false          correct
  hq_link_severed    false          WRONG for this mechanism

edge_buffer_monitor._probe_hq_link_severed() probes toxiproxy hq-link -- the
frontend WAN toggle. sever-tier.sh cuts with a NetworkPolicy, which toxiproxy
knows nothing about, so the flag answers a question nobody asked during a
script-driven cut.

The screens render a LINK UP / LINK DOWN indicator from that field. In the
severance beat -- the beat whose entire subject is a screen refusing to show
what it cannot support -- the indicator will read LINK UP while the data
visibly stops.

NOT FIXED, deliberately. Whether the flag should track reachability rather
than the simulator is a semantics decision with two defensible answers, and
picking one silently to make a demo tidy is the move this corpus exists to
refuse. Recorded, and flagged in RECORDING-SCRIPT before BEAT 3 with two
honest ways to handle it on camera.

Related: the relay that cannot buffer (below) -- both are cases where a
mechanism behaves correctly for its own definition and wrongly for the one a
reader assumes.

---

## 2026-09-19 — severance rehearsed against revision 50

Predicted by classification before either cut; ended connected; pre-flight
5 of 5 after. 15 of 16 predictions held.

Dimension 1 (region from HQ), all eight: HQ held 14 rows at 403s stale --
not fresh (no path crosses the boundary), not gone (no absence rendered as
deletion). Heal 420s -> 0s in 45s.

Dimension 2 (edge-01), six of seven, including the beat: edge-01 398s stale
beside edge-02 0s fresh on one screen; at HQ edge-01 418s while the region own
rollup was 14s. Heal 635s -> 0s in 45s.

### 2.6 WAS WRONG: the relay that cannot buffer

Predicted 0 bridge restarts on the reasoning that buffering is the designed
degraded mode. It crash-looped 6 times, and the log gives the cause:
redpanda-connect exits at STARTUP unable to init its Kafka output. It never
runs long enough to be probed, so the stall probe destination-reachable clause
is not falsified -- it never ran. What is falsified is the assumption that
this relay buffers in place. It cannot; it cannot start.

It cost nothing, and that was verified rather than assumed:
bridge-group-edge-01 reached TOTAL-LAG 3020 while severed and drained to 3 on
heal, group Stable. THE KAFKA TOPIC IS THE BUFFER, which is why a relay that
holds no state is still safe to lose -- and why a relay that DID buffer in
memory would be the design worth worrying about.

---

## 2026-09-19 — the dispatch finished, and UD-14 narrowed

Pre-flight **5 of 5 across every tier**, gate green on all four stores, run
before and after a deliberate rollout at helm revision 50.

| # | check | result |
|---|---|---|
| 1 | advancing, nine stages | every stage moved |
| 2 | derive stage | COMPLETING — edge-01 +101/+16, edge-02 +75/+12, region-east +177/+56 |
| 3 | tier feed | 45 consumers clean |
| 4 | shape sizes | 81 / 45 / 83 KiB per client load |
| 5 | completeness gate | ALL 4 STORES PASS |

Deletes, predicted then confirmed: region 18,562 → 11 remaining; region
unlabelled 3 → 8 labelled; edge-01 13 → 8; edge-02 7 → 2. Every prediction
matched exactly.

### UD-14 — ROLLOUT TESTED, NOT REPRODUCED

The trigger had never been tested. Broker restart was exonerated by two
deliberate tests; the helm rollout that actually preceded the 3.5-hour wedge
was never watched, because rollouts kept happening with nobody looking at the
right thing.

`snapshot-consumers.sh` now takes that reading: every consumer group's state,
committed offset and lag on every broker, diffed across a rollout. At
revision 50, over 92 group-on-broker rows, sampled every 10 minutes for
**1h43m** after the rollout completed — eight consecutive clean samples:
**0 wedged, 0 state changes, 0 groups disappeared**, 0 containers terminated
in the window, pre-flight 5 of 5 afterwards.

The termination check is against `lastState.terminated.finishedAt`, not the
RESTARTS column — that column counts LIFETIME restarts and reported nine pods
whose last restart was five days earlier. A first pass called those "restarts
since the rollout", which would have manufactured a finding out of a column
that was answering a different question.

**Narrowed, not closed.** One clean rollout is not proof against an
intermittent wedge, and the original took 3.5 hours to be noticed. The
instrument exists now, so the next occurrence is caught in the act rather
than inferred. `RECORDING-SCRIPT` keeps its no-upgrade rule.

**THE DETECTOR NEEDED A THIRD TERM, and its first run proved it.** `Stable
AND committed frozen` matched **44 groups**, nearly all stuck at 0 on a
declared-idle tier and on known-empty topics. A signature that matches 44
healthy things would bury the one real case — the exact failure mode it was
built to catch, arriving in the detector. The condition is now

    wedged == Stable AND committed did not move AND lag > 0

the same three-term shape as the relay stall probe's destination-reachable
clause. An absence is only a finding when something else proves there was
work to do.

### `sparse`, and the parser that nearly defeated it

`tactical_events` is empty at the root whenever the fleet is stable, because
events fire on TRANSITIONS. Declaring it plainly empty would have explained
away a stopped producer, which `expected-empty.yaml`'s own header forbids.

The table cannot be its own evidence — if it is empty there is no newest row
to age against retention — so the condition is **the producer is
demonstrably completing**, taken from `check-derive-stage`, which now
publishes a timestamped verdict the gate refuses when stale.

    empty AND completing       -> sparse   (green, with the reason)
    empty AND not completing   -> stopped  (a finding)
    empty AND no fresh verdict -> unexplained (a finding)

All four branches red-checked. **The third is load-bearing**: absence of
evidence buys nothing, so it fails closed to the prior behaviour.

**A DEFECT FOUND BY THAT RED-CHECK.** The declared-empty parser emitted every
entry lacking a `stores:` key, so the sparse entry landed in BOTH lists,
`is_declared_empty` won, and a CONDITIONAL declaration silently became an
unconditional one — precisely the failure the category was added to prevent,
arriving inside its own parser.

### THE RETENTION GRADIENT WAS INVERTED

Leaves 168h, intermediates 72h, root 24h: the tier with the most storage and
the archival role retaining the *least*. Not a decision — the root's 24h was
a pre-existing default in another repo and the tiers had no value at all, so
nothing ever compared them. Now **root 720h > intermediates 168h > leaves
72h**, sized by role. A second effect: at 24h the root's alert feed emptied
within a day, so `sparse` was the steady state there rather than the
exception, and a category that always fires stops carrying information.

### THE CONFIG THAT RENDERED, APPLIED, AND NEVER ARRIVED

Adding `retention_hours` updated the live ConfigMap and changed nothing in the
pod template, because the tier projector deployment had **no checksum
annotation at all**. Kubernetes correctly rolled nothing, helm reported
success, and the projector kept the mapping set it had loaded at startup.

The bridge-retarget shape in a document that had never been given the bridge's
rule. The body is now extracted into `openddil.tierProjectorConfig` and hashed
— the rendered document, not a hand-listed tuple. Verified as a pure refactor
(render byte-identical, 628,728 both sides) and red-checked as a live hash
(changing a retention value moves it).

### NINE DAYS OF RED CI, and what it did and did not break

`openddil-demo`'s Docker Build had failed since 2026-09-09 on a frontend type
error: `RegionalApp` read `.map` off the fleet hook result rather than its
`.data`. One missed `.data` collapsed the inference into a second error
downstream; fixing the first resolved both.

So the published frontend image stayed **nine days behind the committed
source** while nothing reported it — ADR-0025's rule broken on the regional
screen, which is in the recording. The running frontend was an older image
that worked; the committed source did not compile.

**The PEP was unaffected and that was verified, not assumed**: it reaches the
cluster through the runtime-bundle, a different path, and `sha256sum` of
`/app/pep.py` in the running pod is byte-identical to `gateway/pep.py`.

### Still open

1. **UD-14** at lower priority — rollout tested, not reproduced.
2. **§E severance NOT re-run** against the current build. The substrate
   changed underneath those measurements (Restate wiped three times,
   retention declared, PEPs replaced), so the severance beats should be
   rehearsed once before recording rather than trusted from a week-old run.
3. **Restate subtree-scaling** still a design row, not a helper.
4. **One place should declare all three retention values.** The root's still
   lives in the projector repo; unifying it needs a retention override on the
   root projector.

---

## 2026-09-18 — the read path had never carried real data

Every tier PEP `OOMKilled` in a loop; every panel on every screen read FEED
UNAVAILABLE. The write path was perfect throughout: nine advancing stages, the
derive stage completing at all three tiers, 45 consumers clean.

**The banner is the part worth keeping.** *"The request failed; the panels
below are not reporting an absence of data."* ADR-0036 clause 1 and ADR-0035
class 2 on one screen, refusing to let a read failure be read as an empty
fleet. The session opened on the suspicion that traffic had stopped; the
screen had already said it had not.

### The chain — three fixed things and one never-exercised path

1. A null-keyed relay (**fixed weeks ago**) →
2. a projector fallback, `decoded.get("subject") or key or ""`, that **answered
   where it should have refused** → 18,562 rows with an empty subject and a
   fresh uuid each, so `ON CONFLICT (id)` deduped nothing — one burst,
   2026-09-08 →
3. nobody saw them for ten days because **the read path had never carried real
   data** →
4. the first day the derive stage worked, a PEP had to buffer 10 MiB × 9 shapes
   × reconnect retries in unbounded threads against 256 MiB.

Nothing new accumulated after the relay fix. **The repair made the residue
visible** — the same shape as a dead pipeline concealing everything downstream.

### Fixed

* **`pep.py` streams, bounds, and measures.** `payload = resp.read()` removed;
  a `BoundedSemaphore` caps in-flight shapes; per-shape bytes logged with a
  ceiling that WARNS rather than refuses. Streaming alone would not have been a
  bound — an unbounded thread per connection still multiplies whatever each
  thread holds, and raising 256 MiB only changes how many concurrent shapes the
  process survives. *A cap is a sizing only if something bounds what runs
  beneath it* — the RocksDB lesson, one day later, in a different component.
  Chunked framing is written by hand: `BaseHTTPRequestHandler` does not encode
  it, and the first draft sent the header without doing the work. Red-checked
  by removing the framing — the client then **hangs**, which is the browser
  symptom, not an error anyone can name.
* **The projector refuses an empty subject and counts refusals.** A refusal
  nobody counts is a silent drop. Counted rather than only logged: a log line
  is evidence for whoever is tailing at the time, a counter is evidence for
  whoever asks afterwards. Red-checked by reverting ONLY the handler — the
  first attempt reverted `base.py` too and "failed" on `ImportError`, which
  proves the import is missing, not that the fallback writes the row.
* **Retention declared per tier kind**, edges 168h / intermediates 72h.
  Intermediates keep a *shorter* window: the region accumulates its whole
  subtree's events and is where the shape is read from.
* **`check-shape-sizes.sh`** — per-tier, per-table shape bytes against a
  ceiling, measured from inside the PEP. The read-path dimension that did not
  exist, the way consumed-vs-completed did not exist two days ago.
* **Gate declarations can be scoped per store class.** `asset_registry` is
  root-side (ADR-0028) and structurally empty at tiers; declaring it unscoped
  would have excused the root too — so the day the root's registry emptied, the
  gate that exists to notice would be the thing explaining it away.

### THE ASYMMETRY THAT LET IT GROW

The projector has always had a retention pruner and a `retention_hours` field.
The **root** declares `retention_hours: 24` in
`openddil-projector/src/config/projector_config.yaml`. The **tiers declared
nothing**, so the field was None and the pruner skipped the table — while the
handler's docstring says "a background pruner deletes rows older than
retention_hours", true and vacuous at once.

Both halves read the same field name from configs that live in **different
repos**, and only one filled it in. Nothing anywhere disagreed.

### A CORRECTION worth more than the cleanup

**2026-09-17's "GATE PASSES" was a single-store run, and it was recorded as
readiness.** `--all-tiers` already existed; the checklist invoked the root-only
form, and the gate's own footer said so — *"a statement about the root store
AND NOTHING ELSE"*. The first `--all-tiers` run found unlabelled rows in two
tier stores and two undeclared-empty tables. **The mechanism existed; the
checklist did not use it.** That is the covers-one-of-N shape one level up
from the code, in the procedure.

### STILL OPEN

1. **Edge residue deletes.** edge-01 has 13 unlabelled rows, edge-02 has 7, all
   predating the cm-service labelling fix (newest unlabelled 12:02; every row
   after 18:15 is labelled). Blocked pending authorization. Predicted: 13 → 8
   remain, 7 → 2 remain.
2. **The root's `tactical_events` is empty for a reason the gate has no
   category for.** Root retention is 24h; the newest tactical event is 33h old
   because events fire on TRANSITIONS and the fleet has been stable. So the
   table is legitimately empty *most of the time*, and the gate will fail every
   time.
   **Do not simply declare it.** A declaration would also explain away a
   genuinely stopped producer, which is exactly what `expected-empty.yaml`'s
   own header forbids. The missing category is **sparse**: empty is expected
   when no qualifying event occurred within the retention window, which the
   gate can only decide by looking at the producer's last-event time rather
   than at the table alone. That is a real design row, not a config edit.
3. **Retention is committed but not applied** — it needs a `helm upgrade`,
   which fires the Restate wipe hook.
4. `openddil-demo`'s Docker Build is failing — **pre-existing** (the
   2026-09-09 run failed the same way), not from this batch.

---

## OPEN 2026-09-17 — Restate memory scales with SUBTREE, not with tier kind

The 90-minute sizing measurement recorded that the regional tier runs ~3x an
edge. That ratio is not a property of *being a region*. region-east consumes
**two children plus its own ingest**; an edge consumes its own ingest only.
The 3x is arithmetic about subtree size that happens to coincide with tier
kind in the current topology, and the lab has exactly one shape.

**A region with four edges will not be 3x. HQ over several regions is a
different number again.** Written as a per-tier constant, the first
deployment with a second region inherits a limit measured on a fleet that
never had one -- and the failure mode is the one this week already cost eight
hours: an OOM whose cause looks like data growth and is actually a budget
that was sized for a different topology.

### The change

Derive the Restate memory limit from the **tier list**, not from a constant:

* subtree size is already computable -- `openddil.tierList` resolves parent
  for every tier and `hasChildren` is already used to switch relay kind,
  projector mappings and subscription sets;
* per-kind overheads stay explicit (a root carries the registry and the
  aggregation fan-in an edge does not);
* the RocksDB budget already derives from the limit via
  `openddil.halfMemoryBytes`, so fixing the limit fixes the budget and the
  two still cannot drift. The helper composes rather than being replaced.

Same move as every other per-tier value landed this month: **declared from
topology, not inferred from the lab.** The ingest set, the subscription set,
the relay kind and the bridge target are all derived from the declared
hierarchy; memory is the last per-tier number still measured once by hand and
copied forward.

### Sizing inputs available today

| tier | children | own ingest | observed peak | budget |
|---|---|---|---|---|
| root | 2 regions (relayed) | registry + HQ | 407 Mi | 1 GiB |
| edge | 0 | DIS + CM + logistics | 374 Mi | 1 GiB |
| region-east | 2 edges | own | 1192 Mi | 1 GiB |

One data point per shape and only one region shape, so this is enough to fit
an intercept and a per-child slope and nothing more. **Do not fit a curve to
three points and call it a model.** The honest next step is the helper plus a
declared per-child increment that is easy to revise, not a formula that looks
authoritative.

**Bites at:** the first deployment with a second region, or any region with
more than two edges. Not urgent on the lab; it is a correctness problem the
moment the topology stops matching the one the constant was measured on.

*Related:* the closed sizing record in the RESOLVED section below, and the
`openddil.halfMemoryBytes` helper it would compose with.

---

## RESOLVED 2026-09-17 — the derive stage completes, for the first time

Five defects, stacked so each one's fix was blocked by the next, and the whole
stack invisible because every instrument was green. Full operator account in
`openddil-helm/scripts/RUNBOOK-2026-09-17-unwedge.md`.

| # | defect | state |
|---|---|---|
| 1 | Restate OOMKilled at 1Gi (~1600 restarts) | fixed, 2Gi, 0 restarts |
| 2 | zstd on Restate-subscribed topics | fixed, `lz4` applied and confirmed |
| 3 | comment inside a line continuation → whole `topic-init` script unparseable | fixed + guard 4 |
| 4 | release wedged `pending-upgrade` 8h behind the failed hook | cleared |
| 5 | `hook-restate-wipe` covered 1 Restate of 4 | fixed, `wipe_one` over all |

**The measurement that had never once been non-zero** (`check-derive-stage.sh`,
90s window, after the repair):

| tier | asset-cm-state | asset-logistics-status |
|---|---|---|
| edge-01 | +148 | +24 |
| edge-02 | +112 | +18 |
| region-east | +262 | +51 |

Registrations restored: 2 deployments / 7 subscriptions at each edge, 2 / 4 at
region-east. Zero restarts across all four Restates.

### NEW, and only visible because the pipeline now runs

**`tactical_events` produces unlabelled rows.** The table was empty for the
whole period the gate was green, so this branch had never executed against
real data. Two producers, two different wrong behaviours:

* `cm-service` (3 rows): stamps **neither** `originator_nation` nor
  `releasable_to` — the 6 unlabelled values the gate now names;
* `logistics-fusion` (2 rows): stamps `originator_nation` but leaves
  `releasable_to` an **empty array**, which under the ADR-0029 §4 disjunction
  is not a denial but a silent narrowing to the originator alone.

Gate FAILS, correctly, and now names the subjects. **This is the next code
fix.** It is a labelling gap in the producers, not in the gate.

**The gate could not name what it failed on.** It deduplicated by `asset_id`;
`tactical_events` keys on `subject` and the rollups on `region_id`, and an
earlier fix had SKIPPED those tables to stop psql errors printing into the
findings section. Result: `GATE FAILS: 6 unlabelled value(s)` followed by an
empty list. Fixed — key column resolved per table, subjects table-qualified.

And the first version of that fix **accused the three `region_*` rollups**,
because its predicate was a second implementation of the counting rule and
disagreed with it: an aggregate with a NULL originator is *correct*. The
predicate is now derived from the same `is_aggregate()` the counter uses.
*A second implementation of a rule is a second rule.*

### ROOT CAUSE of the OOMs — Restate budgets RocksDB at 100% of the limit

The memory limit was never the variable. Restate reads the cgroup limit, sets
`rocksdb-total-memory-size` to ALL of it, and **prints an ERROR about itself at
every startup**:

    'rocksdb-total-memory-size' parameter is set to 2.0 GiB, more than 90% of
    the process memory limit of 2.0 GiB. This risks an OOM under load; keep it
    under 50% of process memory

At the old 1Gi limit that is a 1 GiB budget inside a 1 GiB cap — not a tuning
problem, an arithmetic one. **That is what drove the ~1600 kills on edge-01 and
1124 on region-east**, and it was in the logs at every one of those starts.

**Raising the limit to 2Gi did not fix it, it re-scaled it.** The budget became
2 GiB of a 2 GiB cap; region-east then peaked at **1656 Mi of 2048** (81%) —
still climbing toward the same wall, just more slowly. 2Gi bought time and
looked like a fix because the restart counter stopped.

FIXED: `RESTATE_ROCKSDB_TOTAL_MEMORY_SIZE` set to 50% of the container limit,
computed by `openddil.halfMemoryBytes` from the SAME value that sets the limit
so the two cannot drift. Applied to the root and all five tiers (6 render
sites). Emitted in bytes because the env override rejects unit strings the TOML
field accepts, and a rejected value is silently ignored.

Verified on region-east 2026-09-17: startup ERROR gone, partition budget
810.3 MiB -> 405.2 MiB, peak 1656 Mi -> steady ~1014 Mi, zero restarts, derive
stage still completing at the same rates.

| node | pre-fix peak | post-fix | limit |
|---|---|---|---|
| root `restate-server` | 510 Mi | 517 Mi | 2Gi |
| `tier-restate-edge-01` | 638 Mi | 558 Mi | 2Gi |
| `tier-restate-edge-02` | 337 Mi | 342 Mi | 2Gi |
| `tier-restate-region-east` | **1656 Mi** | 1014 Mi | 2Gi |

**ACCIDENTAL CONTROLLED COMPARISON, and it is the strongest evidence here.**
The fix was applied to region-east alone at 12:24 while a memory watch was
already running. That left three unfixed nodes under identical load for the
next 52 minutes:

| node | budget | 12:18 -> 13:10 |
|---|---|---|
| region-east | **1 GiB (fixed)** | 1656 peak -> oscillates **1087-1185, no trend** |
| edge-01 | 2 GiB (= cap) | 589 -> 638, sawtooth to 288, then 288 -> 614 climbing |
| edge-02 | 2 GiB (= cap) | **279 -> 617 monotonic**, ~6.5 MiB/min |
| root | 2 GiB (= cap) | 466 -> 642, climbing |

The only node that went flat is the only node that was fixed. edge-02's slope
put it at the 2Gi cap in roughly 3.5 hours; the sawtooth on edge-01 is RocksDB
releasing on compaction and refilling toward the same ceiling. So "2Gi is
stable" was an artefact of not having watched long enough -- the restart
counter stopping is not the same measurement as the memory plateauing.

Applied to the remaining three at 13:14 by `kubectl set env` rather than a
helm upgrade, deliberately: an upgrade fires the wipe hook on all four
Restates, and discarding the state that had just started working to deliver a
memory fix would have been a poor trade. The chart renders the identical value,
so the next upgrade reconciles rather than reverts. After the restarts: zero
warnings on all four, partition budget 810.3 -> 405.2 MiB everywhere, derive
stage completing at unchanged rates, zero restarts.

**The 167 MiB baseline is retired as a sizing input.** It was measured on an
idle Restate and it measured the PARTITION budget, which is a different number
from the one that kills the process. The sizing record should be written
against the RocksDB budget, not against observed RSS.

*The lesson, and it is the batch's theme again:* the component was reporting
its own misconfiguration, in its own logs, as an ERROR, roughly 1600 times.
Every instrument outside it was green, so nobody read the one instrument that
was not. **A component's self-report is an instrument too, and the cheapest one
in the system.** Read the logs of the thing that is restarting before tuning
the thing it is restarting against.

### Reliability finding, independent of what caused the kills

**~1600 OOM kills corrupted a single-node Restate's cluster metadata past
self-recovery.** `POST /query` answered `node N1:1645 was shut down or
removed`; the node could neither create nor enumerate an invocation, while
every pod read `1/1 Running`. Not "invocations failing", not "invocations
absent" — a third state in which the substrate cannot answer questions about
itself, and which no liveness or readiness probe in the system detects.
Recovery was a wipe. Worth a durability row on its own merits.

### Guards landed

* **guard 4** in `check-chart-render.sh` — parses every rendered shell script
  with `sh -n`, across **three variants** (`default` 35, `tiernode` 62,
  `releasability` 38). The first version rendered defaults only and so never
  parsed any of the 27 scripts in `tier-node.yaml`; it also missed
  ConfigMap-shipped shell (`relay-stall-probe.sh`, 4.6 KB). Both were the same
  covers-one-of-N shape as defect 5, arriving inside the fix for defect 3.
* **`check-derive-stage.sh`** — dispatch item (2). Three terms: consumed,
  completed, deployment reachable. Its first draft reported `0` for eight
  watermarks including one known to be 1,436,481, because it did not export
  `KUBECONFIG`, `2>/dev/null` ate the error and `s+0` manufactured a zero. It
  now refuses to report a number it did not read, and asserts the cluster.

### Next, in order

1. Fix `cm-service` / `logistics-fusion` tactical-event labelling; gate to zero.
2. ~~Sizing record~~ **CLOSED 2026-09-17.** Written into values.yaml against
   the RocksDB budget. 90-minute watch, all four nodes under a 1 GiB budget
   with the derive stage running: root 265-407Mi, edge-01 165-374Mi, edge-02
   148-375Mi, region-east 989-1192Mi -- all sawtoothing, no trend, peak 58%
   of 2Gi. region-east runs ~3x an edge (two children plus own ingest); size
   the regional tier from that ratio, not from an edge measurement.
3. Parsers for the other embedded languages — Bloblang in the three
   `connect.yaml` ConfigMaps (`rpk connect lint`, binary already in the
   redpanda image), TOML and JSON (stdlib, free). Survey done; none checked.
4. Nightly cron for `check-advancing` + `check-derive-stage` + the gate.
5. `ADR-0042` custody: `wipe_one` must refuse to wipe a Restate holding intent
   custody. Constraint recorded in the hook's design note while it is still
   safe; the refusal lands with custody.

---

## CLOSED 2026-09-17 (was OPEN) — Restate consumes, the services never produce

> **CLOSED the same night** — see "RESOLVED 2026-09-17: the derive stage
> completes, for the first time" above. Kept for the diagnosis chain.

Two defects found tonight. The first is fixed and the second is not, and they
were stacked so the first hid the second.

### FIXED — Restate OOMKilled at 1Gi

`tier-restate-edge-01` at **1600 restarts**, `region-east` at **1124**, all
`OOMKilled` (exit 137) roughly every 17 seconds: start, catch up partitions in
~16s, die. Restate drives fusion, so nothing downstream could run. Raised to
2Gi; all three now stable with zero restarts.

**Do not record 2Gi as SIZING yet.** The 2026-08-08 note measured 167 MiB RSS
idle and concluded "the cost is BASELINE, not data". A consumer task dying and
restarting every 17 seconds for eight days is a plausible driver of the
975 MiB the survivor showed. Measure against the baseline once the pipeline
is healthy; the note may still be right and 2Gi merely margin.

### FIXED — zstd on Restate-subscribed topics

Restate's Kafka ingress is built on a librdkafka **without zstd**. One zstd
batch kills the consumer task (`Decompression (codec 0x4) ... Not
implemented`); Restate restarts it from its stored position, hits the same
batch, dies again, forever.

**The obvious suspect was wrong.** The chart does set `compression.type=zstd`
— on four `ingress-*-raw` topics, and **Restate subscribes to none of them**.
The real cause is `compression.type=producer`, the default the subscribed
topics carried, which means *store whatever codec the CLIENT chose* — and one
client chooses zstd. Evidence came from HQ's broker, never altered by hand,
showing `producer (DEFAULT_CONFIG)` rather than zstd.

Chart now sets explicit `lz4` on all six subscribed topics. **This reaches the
work cluster on upgrade: P0.1 gate.** Also worth checking whether a current
Restate image ships zstd, which would retire the constraint instead of
documenting it.

### OPEN — the services are invoked by nothing

After both fixes, at edge-01:

* `raw-sensor-stream` advancing (+98/60s) — input present
* `cm-service-silver-edge-01` **Stable, lag 7** — Restate IS consuming
* zstd errors **0**
* all seven subscriptions registered, sinks correct
* `asset-cm-state` **+0** and `asset-logistics-status` **+0** — the services
  produce nothing
* fusion's log shows only `GET /discover` — **zero invocations**, ever

Restarting both services changed nothing. So Restate consumes the messages
and the invocation does not reach the service, or reaches it and produces no
output and no log line.

**Next, in order:** query Restate's invocation status via the admin API
(`/invocations`) to see whether invocations exist and are failing, rather than
inferring from the absence of output; check whether the registered service
DEPLOYMENT in Restate points at the current pod revision; and check whether
the services' own Kafka publisher can connect — fusion logs "Kafka publisher
installed" at startup but nothing proves it produced since.

**Instrument gap this exposes.** `check-advancing` watches BROKER topics and
was green throughout, because ingest and the mapper were fine. It does not
watch the derive stage's OUTPUT relative to its input. The feed check watches
consumer groups, which were Stable. Neither instrument asks the question that
would have caught this: *this service consumed N and emitted 0.*


## CLOSED 2026-09-19 (was OPEN 2026-09-16) — tactical_events: HQ prunes, the tiers never do

> **CLOSED by the retention gradient work of 2026-09-19.** The tiers now
> declare retention_hours per kind (root 720h > intermediates 168h > leaves
> 72h) and the pruner has a target at every tier. The row below is kept for
> the diagnosis, not as outstanding work.

The completeness gate refused `tactical_events` as empty-and-undeclared at
HQ. It is right to refuse, and the cause turned out to be two facts that only
look like a fault together:

* **HQ's mapping carries `retention_hours: 24`** and a background pruner
  drops rows older than that. **The tier projector mappings carry no
  retention at all.**
* **Every tactical event in the system is 8 days 21-22 hours old.** Fusion
  emits only on an UPWARD transition into an alerting severity, and the fleet
  has been stable since. So nothing new has been produced for eight days.

HQ's zero is therefore **correct behaviour**, not a stalled producer — and
the region's 18,562 rows are the same events that HQ correctly aged out.

### Do NOT declare tactical_events expected-empty

`expected-empty.yaml` wants *"a dated claim that a named producer is absent
for a named reason."* The producer here is not absent; it is **quiescent**. A
declaration would suppress exactly the signal the gate exists to raise: a
genuinely broken fusion looks identical to a stable fleet from the table, and
the difference is the whole reason the check asks.

**The resolution before a recording is to GENERATE an event, not to declare
the table empty** — which the demo's injection beat does anyway, and which
also proves the path rather than excusing it.

### The asymmetry is the real finding

**The tier stores have unbounded tactical-event retention.** region-east holds
18,562 rows nine days old and will hold them indefinitely; HQ holds 24 hours.
Nothing decided that — HQ's mapping was configured and the tier mappings were
copied without the field.

Two things to settle:

* **Which way should it go?** An edge is the tier with the least storage and
  the most reason to keep local history through a long severance; HQ has the
  most storage and the least need for raw event history. The current
  configuration is the opposite of that argument in both directions, which
  suggests it was inherited rather than chosen.
* **Unbounded growth at a tier store is a DDIL hazard**, not just untidiness:
  the store that must survive a severance is the one with no bound on this
  table.

Recorded rather than fixed, because picking a retention is a deployment
decision and a number invented here would read as a requirement.


## RETRACTED 2026-09-09 — "a broker restart wedges its clients" is not true

I reported that as the night's root pattern. It does not reproduce.

**Two deliberate reproductions on edge-01's broker:** a 6-second pod delete,
and a 150-second full scale-to-zero. In both, every client — sensor-ingest,
the DIS mapper, faust-edge, the bridge, the tier projector — reconnected on
its own, and the advancing pre-flight read green within 100 seconds. Nothing
wedged.

So the 21:29–21:44 event that killed four clients **remains unexplained.**
The correlation with a broker roll was real; the causation was mine.

**And it strengthens the case for the mechanisms rather than weakening it.**
A known trigger could be fixed at the trigger. An unexplained wedge can only
be defended against where it shows: a component that cannot do its job must
die, and a component whose output has stopped must go unready. Those convert
an unknown cause into a visible restart, which is the property that matters
when the cause is unknown.

### And a second retraction, from the same block

I wrote that `kafka_errors` counts produce ATTEMPTS rather than deliveries,
citing edge-02 reporting zero errors while its topic was frozen. **Reading the
code shows the delivery callback does increment on error**, and re-measuring
shows edge-02's ingest was never broken: its output topic `ingress-dis-raw`
was advancing normally. The frozen topic I compared against was
`raw-sensor-stream`, which is the DIS MAPPER's output, not the ingest's.

**I diagnosed a component by watching a topic it does not write.** That is the
same mislabelling the pre-flight's own probe carried until it was corrected,
committed twice in one session — once in the tool, once in the reasoning.

What survives from that block, verified: edge-01's ingest DID enter a fatal
producer state and log at WARNING forever, and that is now fixed by exiting
non-zero.


## OPEN 2026-09-09 — two components that wedge at 1/1 Running, found before a severance

Pre-cut baseline for the two-dimension severance found the pipeline **dead
for three and a half hours**, in two unrelated ways, both invisible to every
liveness probe:

**1. Both edge bridges stopped consuming at 21:29-21:31.** edge-01 logged
`kafka: error while consuming telemetry-latest-state/1: the provided member
is not known in the current generation` — a consumer-group rebalance error —
then went silent. edge-02 logged "Input type kafka is now active" and then
nothing. Both pods stayed `1/1 Running`; lag climbed to **106,249** and
**79,726** and neither restarted.

**2. edge-01's sensor-ingest entered a FATAL librdkafka producer state at
00:51:04** — `KafkaError{code=_FATAL, val=-150, "Unable to produce message:
Local: Fatal error"}`. A fatal producer state is unrecoverable by design: the
client will never produce again without being recreated. The pod stayed
`1/1 Running, restarts=0` and kept RECEIVING and DECODING (460,181 decoded,
21,264 kafka_errors and climbing) — so every counter except the one that
mattered looked healthy.

Both are the same shape this corpus keeps recording, now on the WRITE and
RELAY sides rather than the read side: **a process that is up, probed
healthy, and doing nothing.** The read-side instances were the reachback, the
unfed consumer and the wedged Faust table; these are their producers.

**What would have caught them, and did not.** The edge buffer monitor tracks
exactly this — `bridge_group_lag` climbing to 106k is the signal — and it was
recording it. Nothing ESCALATED it. The number was on a panel nobody was
looking at, which is the difference between an instrument and an alarm.

**Why it matters beyond the outage:** severing a tier whose inbound is
already frozen measures nothing, exactly as severing a tier whose link probe
is already down measures nothing. The pre-cut baseline is what caught it, and
it caught it because the baseline asked whether numbers ADVANCE rather than
whether they exist.

**Restart cleared both.** Region inbound resumed (frozen at 199,883, moved on
restart) and ingest re-bound its UDP socket.

**To decide:**

* A liveness or readiness probe that fails on a fatal producer state, rather
  than one that only checks the process is alive. The ingest knows: it counts
  `kafka_errors`, and a nonzero-and-climbing rate with a fatal code is
  self-diagnosing.
* A bridge probe on consumer progress, not process liveness — committed
  offset advancing, not "the container is up".
* An escalation path for `bridge_group_lag` beyond rendering it. A threshold
  that turns the existing instrument into an alarm.
* **For the recording:** these two wedge. Check `bridge_group_lag` and the
  ingest's `kafka_errors` immediately before recording, because both fail
  silently and the demo would show a frozen fleet with every pod green.


## OPEN 2026-09-08 — a new consumer group replays history into a schema that has since changed

Giving region-east its own `region_*` projectors created three NEW consumer
groups, which started at offset 0 and replayed the topic's whole history —
including messages emitted BEFORE the rollups were partitioned by
releasability class.

A pre-partition message carried no `releasable_to`, so it decodes as the
**empty class**, and it carried the WHOLE region's counts. The result was a
phantom partial: `class='' assets=14 releasable_to={}` sitting alongside the
three real ones.

**It cannot be fixed by decoding.** A pre-partition message and a legitimate
empty-audience partial — a class whose contributors are releasable to nobody
— are byte-identical. There is no field that distinguishes "this producer
predates the concept" from "this producer computed an empty set".

**Why it was not visible.** `releasable_to={}` denies everyone under the §4
predicate, so the phantom row renders on no screen. It is wrong data that no
subject can see, which is the most patient kind.

**Cleaned by hand this once** (three rows at the region, plus a stale
`id='edge'` buffer row left behind when the buffer key became the tier id —
same shape: *a key change does not delete the old key's row*).

**What to decide, before the next tier is added:**

* Whether new tier consumer groups should start at `latest` rather than
  `earliest`. That avoids the replay and loses legitimate history — a real
  trade, not an obvious win.
* Or whether the aggregate handler should reject a message whose provenance
  carries no `releasable_to` KEY at all, distinct from one carrying an empty
  list. proto3 erases that distinction on the wire (recorded already), so
  this would need a producer-side marker — which is the same conclusion the
  composed-vs-uncomposed branch reached, and was abandoned for the same
  reason.
* Or accept the phantom and have the completeness gate name it: a partial
  whose class is empty AND whose asset_count equals the region total is a
  legacy row, and that conjunction is checkable even though neither half is.

The third is the cheapest and the most honest: it does not pretend the wire
carries something it does not, and it turns an invisible wrong row into a
named finding.


## PROMOTED 2026-09-08 — asset-registry-service must stamp its own writes

**Was:** deferred, behind the bridge. **Now:** behind the region, before any
recording.

**Why the cost changed.** The service still does not stamp releasability on
rows it writes; 20260906010000 backfilled what existed, so the gate reads
zero unlabelled today. That was survivable when an unstamped row hid ONE
asset.

Regional rollups are now labelled by **intersection**, and an unlabelled
contributor takes the intersection to empty. So a single row the service adds
after the backfill no longer hides an asset — **it blanks the regional
screen, for everyone, including the fully-entitled liaison.**

That is deny-unlabeled propagating correctly through aggregation, and it is
the right behaviour. The blast radius is what changed, not the correctness:
one unstamped write now costs a region's whole rollup rather than one row.

**Test when it lands:** add an asset through the service and confirm the
regional rollups keep their composed audience rather than going empty.


## Why this exists, and why it is shaped this way

Open follow-ups live in **six separate registers** across five documents.
Nobody could answer *"what is outstanding?"* without opening all of them,
and the corpus had already drifted — see §Reconciliation.

ADR-0037 **rejects a traceability matrix as a primary mechanism**, for a
good reason: *a document parallel to the work drifts from it*. That
rejection applies to this file, so it is built to be checkable rather than
trusted:

- rows carry an **ID, a short subject, a home, and a status — never content**.
  Restating a finding here would create a second version to keep in sync,
  which is the failure ADR-0037 names;
- **drift is mechanically detectable** (§How to check), so this file cannot
  silently fall behind the way `README.md` just did;
- it indexes **IDs only**. Follow-ups recorded as prose in audits and plans
  are deliberately out of scope — see §What this index does not cover.

## How to check this index is current

```bash
./scripts/check-decision-indexes.sh      # exit 0 = clean
```

**Run in CI** on every change to `decisions/` — `.github/workflows/
decision-indexes.yml`. **44 IDs as of 2026-09-05.**

*The commands are not repeated here on purpose.* A copy in this file and a
copy in the workflow are two things to keep in sync, and keeping two copies
of a drift-detector in sync is the drift it was written to detect. The
script is the single copy; this section points at it.

It runs **four** checks:

1. every register ID has a row here, and every row is a real ID;
2. every document in `decisions/` is referenced by `README.md`;
3. every row's status **matches its home document's declared token**, by
   exact string;
4. every row's home **has** a token — so a missing one fails loudly instead
   of dropping out of check 3.

Failure prints the specific IDs or filenames. A mismatch means the corpus
moved and this file did not, which is information, not an error.

*All four were verified by being made to fail* — a deleted row, an unindexed
document, a phantom ID, a disagreeing status in each register shape, and a
deleted token each produce the expected message and exit 1. A check never
seen red proves nothing about what it would catch.

> **The script's `grep -v FOLLOW-UPS.md` is load-bearing, not tidiness.**
> The obvious form scans `*.md`, which includes *this file* — so every ID
> written here would appear in its own "corpus", every row would vouch for
> itself, and the phantom-row direction **could never fail**. A renamed or
> deleted ID would pass silently. The first draft had exactly that flaw.
>
> *A verification that includes its own subject in its evidence is not a
> verification* — the same shape as a guard that has never been seen to
> fail, arriving in the checker written to prevent drift.

*This check is why the file is worth having.* It cannot verify a status is
still accurate — only a human reading the home document can — but it makes
the *cheap* failure (a row that never got added) mechanical, and leaves only
the expensive one to judgement.

### The second check exists because the first is blind to it

An entire document can go unlisted without affecting any ID. When first run
on 2026-08-12 that check found **eleven**, including **`PRINCIPLES.md` and
`GENERALIZATION-DEBT.md`** — the two most-cited documents in the corpus —
and three of five audits. All are now listed.

**Both are in CI, which was the actual conclusion.** Neither requires
judgement, both run in under a second, and both failed silently for weeks
under a team that is demonstrably careful about exactly this class of error.
See `PRINCIPLES.md` §*Indexes drift where the work is not*.

### Checks 3 and 4 — status, and why they took a detour

**Status drift is now checked exactly**, because status is **declared**
rather than inferred. Every row carries a token — the Status *column* in the
`GD` table, a `` `Status: …` `` line above the heading in the prose registers
— and the script compares index against home by exact string. Check 4 exists
so a row with **no** token cannot drop out of that comparison silently;
absence answering as agreement is the disease this tooling exists to fight,
and it would have been an ignominious way to reintroduce it.

**A green status check means the index AGREES with the home. It does not
mean either is true.** The script prints that line itself, every run, so the
distinction survives being read by someone in a hurry.

The route here is the part worth keeping, because the first two attempts
both *looked* like they worked:

This file shipped 2026-08-12 marking `IH-5` and `IH-6` **open**. Both had
been **fixed the same day**, in a parallel session, and the index was built
from a snapshot that predated it. The limitation documented below —
*"a row marked open that was quietly fixed will not be caught by any command
in this file"* — fired **within three days of being written**, which is the
strongest possible argument that it was not a theoretical caveat.

A heuristic was attempted and **deliberately not shipped**, because it does
not work:

- windowing from *any mention* of an ID gave **false positives** — `README`'s
  dense summaries mention `AE-2` and `VE-7` within a few lines of an
  unrelated *"RESOLVED 2026-08-12"* belonging to `AE-1`;
- tightening to definition sites with a 16-line window then gave a **false
  negative** — it caught `IH-6` and missed `IH-5`, whose `FIXED` marker sits
  25 lines under its heading.

**There was no correct window**, because register blocks vary in length. A
check tuned until it passes is a check whose green means nothing — the
decorative-guard failure, arriving in the third checker in three days. So
the heuristic was **rejected rather than improved**, and the property it was
trying to reconstruct was declared instead.

*Note what the detour was:* inferring status by pattern-matching prose is
the **same disease as inferring asset class from publishing behaviour**
(**GD-11**) or absence from a zero (**GD-12**) — a property nothing
declares, reconstructed downstream from a correlate that mostly works. It is
the family's fourth instance and its first inside this project's own
tooling. The fix is the one those rows also demand: **declare the property.**

*One implementation note that nearly went wrong.* The tokens were first
inserted *after* each row's bolded heading, which split sentences wherever
prose continued on the heading's closing line — the anchor was structurally
wrong, not merely misplaced. They now sit on their own line **above** the
heading, where nothing can be split. Verified by diffing: the change is
**purely additive**, no existing line altered.

---

## Registers

### GD — generalization debt (`GENERALIZATION-DEBT.md`)

| ID | Subject | Status |
|---|---|---|
| GD-01 | `edge_id`/`region_id` encode a two-level hierarchy | open |
| GD-02 | Named-tier components encode three tier kinds | open |
| GD-03 | Intermediate tier has no broker (Phase-6 shortcut) | open |
| GD-04 | Three fixed views rather than a tier-generic view | open |
| GD-05 | `region_top_factors` is non-composable (top-N truncation) | open |
| GD-06 | Tree-only data flow; no lateral peer links | open |
| GD-07 | All three analytics planes hardcoded | open |
| GD-08 | Detection centralized at root, reaching downward | in-arc Arc 1 |
| GD-09 | Bare-name alias Services | fixed 2026-08-08 |
| GD-10 | Capability-item shape undeclared | open |
| GD-11 | Asset class inferred from one feed's behaviour | open |
| GD-12 | Absence conventions declared only in the consumer | open |
| GD-13 | Generated protos are not a package; every consumer invents a path | open |
| GD-14 | Wear axis applicability: type-level manifest FIXED; asset-level as-maintained state open | narrowed — type-level fixed, asset-level open |

### UD — undetected failure modes (`ADR-0036`)

| ID | Subject | Status |
|---|---|---|
| UD-1 | Severance detector depends on the uplink it detects | open |
| UD-2 | No tolerance classification observed under a real sever | open |
| UD-3 | Egress + overlay components outside every sweep | open |
| UD-4 | Pre-sync zero, instrument-side *(see IH-1)* | open |
| UD-5 | Middleware-participation health has no observable | open |
| UD-6 | **The register itself is unaudited** | open |
| UD-7 | Resource failure manifests on a component that did not cause it | open |
| UD-8 | Field-by-field message copy drops what it was not told to carry | open |
| UD-9 | A configuration setting whose consumer does not exist fails silently | open |
| UD-10 | Tier and root share consumer groups; the tier goes silent looking healthy | open |
| UD-11 | The detection cutover retired the subscription and left the projector reaching down | fixed 2026-09-05 |
| UD-12 | Subscription bootstrap creates and never reconciles; a wipe hook hid it at the root | fixed 2026-09-05 |
| UD-13 | Fusion skipped DIS telemetry on an expired premise — guard deleted, admission by content | fixed 2026-09-07 |
| UD-14 | Four clients wedged at 1/1 Running for 3.5h — broker restart exonerated by test, helm rollout untested | remedy landed, cause OPEN |

### VE — verification-evidence gaps (`ADR-0037`)

| ID | Subject | Status |
|---|---|---|
| VE-1 | No index of evidence | open |
| VE-2 | Suite exits 0/1 — "the suite passed" cites nothing | open |
| VE-3 | Recording retention is "whoever has the file" | open |
| VE-4 | Chart self-description checked by hand | open |
| VE-5 | Single-site evidence behind fleet-shaped claims | open |
| VE-6 | No supersession rule | open |
| VE-7 | Evidence artifacts have no sanitization gate | open |
| VE-8 | No CI job runs any Python test suite | open |
| VE-9 | A deploy reports success while running the previous artifact | open |

### IH — information-honesty divergences (`ADR-0035`)

| ID | Subject | Status |
|---|---|---|
| IH-1 | Pre-sync `?? 0` renders a confident zero *(see UD-4)* | open |
| IH-2 | Three of four CM/ops quadrants rendered distinctly | open |
| IH-3 | `tactical_events.severity` mixes two vocabularies | open |
| IH-4 | Tier identity answered by URL, not asserted | open |
| IH-5 | Most-derived value carries weakest provenance | fixed 2026-08-12 |
| IH-6 | Horizon renders as a bare duration, no basis | fixed 2026-08-12 |

### AE — capability-envelope gaps (`ADR-0038`)

| ID | Subject | Status |
|---|---|---|
| AE-1 | ADR-0011 claimed work-order generation | fixed 2026-08-12 |
| AE-2 | Machine advisories ship with no provenance | open |
| AE-3 | Supply-only — no demand model | open |
| AE-4 | Horizon exists; uncertainty band does not | open |
| AE-5 | GD-10 is a prerequisite here too | open |
| AE-6 | Diagnosis absent, deliberately not listed | open |

### C — do-not-harden constraints (`ADR-0038` §6)

Not follow-ups: **standing constraints on present work**. Listed so they are
not mistaken for optional. `C4` is the only one with a clock, and it is
**overdue** — its trigger was *"before the first advisory-producing unit"*
and AUDIT-2026-08-12 F1 found advisories already shipping.

---

## Reconciliation — what this pass found

**The corpus is in better shape than expected in one place and worse in
another, and the difference is instructive.**

- **ADR-0038 was already reconciled.** AUDIT-2026-08-12 falsified two of its
  claims, and `AE-2`/`AE-4` had already been rewritten and `C4` already
  moved to overdue. The *findings* propagated correctly.
- **`README.md` had not.** Its ADR-0035 entry still said *"Four divergences
  registered"* and listed IH-1..IH-4; `IH-5` and `IH-6` were added the same
  day from that audit and never reached the index. **Corrected in this
  commit.**

*Both halves of one lesson:* the propagation that happened was into the
**document that owns the finding**, where the author was already reading.
The propagation that failed was into a **summary maintained elsewhere**.
Indexes drift where the work is not; that is the argument for the
mechanical check above, and the reason this file does not restate content.

- **`UD-4` and `IH-1` are the same defect** — the pre-sync `?? 0` — recorded
  independently in two registers, instrument-side and render-side. Not a
  duplicate to merge: the two-layer split is the point, and AUDIT-2026-08-12
  found the same pairing again in `IH-5`/`IH-6`. **The pattern is worth
  naming: a producer-side gap and its render-side consequence get found
  separately, at different times, by different sweeps.** Cross-linked here
  so the pair is visible.
- **AUDIT-2026-08-11 (fallback honesty) is fully closed** — F1–F4 all fixed
  (`ead7903`, `90cbaf6`, `efef7a6`). F5–F9 were clean on inspection. Its one
  surviving item was promoted to `GD-12` rather than left in the audit.
- **AUDIT-2026-08-12 (capability foreclosure) F1–F4 remain open** and are
  the reason `AE-2`, `AE-4`, `IH-5`, `IH-6` and `C4` read as they do.

## Reconciliation — 2026-08-19

A week of closures, checked against the registers rather than recalled.

**Statuses that moved**, all verified in their home documents:

| row | now | by |
|---|---|---|
| `IH-5`, `IH-6` | fixed 2026-08-12 | caught by *this file being wrong*, three days after the caveat was written |
| `AE-1` | fixed 2026-08-12 | ADR-0011 amended |
| `GD-09` | fixed 2026-08-08 | chart 0.1.40 |

**New rows this week:** `UD-7` (resource failure manifests away from its
cause), `GD-12` (absence conventions undeclared), `GD-13` (generated protos
are not a package), `VE-8` (no CI ran any Python suite), `IH-5`/`IH-6`.
**Six rows added, three closed** — the register grew, which is what a week
of looking produces and not a sign of decay.

**Rows whose scope changed without their status changing:**

- **`VE-4`** — split. The rendered-object half is **built and in CI**
  (`openddil-helm` `2ceee1b`); the header self-description half is **closed
  as unbuildable in its stated form**, with the structural alternative
  recorded. The row is smaller than it was, not closer to done.
- **`GD-12`** — surveyed (`AUDIT-2026-08-15`), and its fourth instance found
  in our own tooling. Still open; the *convention* is now stated in
  `telemetry.proto` for the operational axes only.
- **`GD-13`** — design landed (`DESIGN-2026-08-19-gen-python-packaging`),
  and the survey found **five** mechanisms rather than the three the row
  claims. Row text is now an undercount.

**What did not move, and should be read as deliberate:** `VE-1` (no index of
evidence), `VE-2`, `VE-3`, `VE-5`, `VE-6`, `VE-7`, `UD-1`..`UD-6`,
`GD-01`..`GD-08`, `GD-10`, `GD-11`, `IH-1`..`IH-4`, `AE-2`..`AE-6`. None was
worked; none is blocked on anything a night can fix.

*One honest note about this pass:* it reconciles **statuses and scope**, not
**truth**. Check 3 proves the index agrees with each home document; nobody
re-derived whether the homes are still right. A row that quietly became
irrelevant would survive this reconciliation intact.

## What this index does not cover

- **Prose follow-ups in audits and plans** — deliberately. Only ID'd rows
  are indexed, because only they can be checked mechanically. Anything
  worth tracking should therefore *earn an ID in a register*, and this
  boundary is the incentive to give it one.
- **Statuses are not verified here.** The checks prove a row exists, not
  that `open` is still true. A row marked open that was quietly fixed will
  not be caught by any command in this file — **and this has already
  happened once, to `IH-5`/`IH-6`, three days after the caveat was
  written.** See §*The third check does not exist*.
- **`PLAN-*` documents' open steps** — they carry their own sequencing and
  are not follow-ups in the register sense.
- **Anything outside `openddil-contracts/decisions/`.** Follow-ups recorded
  in other repositories' code comments or runbooks are not visible here,
  and no claim is made that this is the complete set of outstanding work.
