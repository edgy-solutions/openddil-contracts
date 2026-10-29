# ADR-0051 — The episode is the failure record: FRACAS from what the tier already observes

## Status

**PROPOSED — 2026-10-29.** Design only. Nothing here is built or deployed.
- Extends `openddil:ADR-0046`: one new outbound kind, one new inbound kind, and no new gate.
- Uses `openddil:ADR-0009` (the CM model), `openddil:ADR-0048` / `openddil:ADR-0049` (the effector ledger) and
  `openddil:ADR-0044` (posture signals).
- On the other side of the seam it meets `iagent:docs/adr/ADR-0056-fracas-phase-1-what-failed-on-this-part-across-programs.md`,
  whose phase 2 ("OpenDDIL's edge entry") is the inbound end of this ADR.

## Findings first: three premises that are not true today

1. **The episode does not survive its own closure.**
   - `ManualDiscrepancyResolved` (CmEvent field 16) removes the entry from `AsMaintainedRecord.manual_discrepancies`
     (`openddil:openddil-cm-service/src/events/asset_cm.py:617-619`).
   - `resolved_by` is logged and then dropped. The `resolution` text is never read, and no cleared time is stored.
   - The only trace is the CmEvent itself on `cm-events` (compact+delete, 30 days) and the egress ledger row.
   - So "first-observed, cleared" is half-true: first-observed is stored (`detected_at_ns`), cleared is not.
2. **No configuration is stored with the episode.**
   - The assembled record's `provenance[]` names the row key `asset_cm_state:{asset}` and `last_observed_at`
     (`openddil:openddil-demo/egress/assembler.py:269-311`). It carries no baseline id.
   - The nearest value is `asset_logistics_status.cm_baseline_id`, and that is latest-only.
3. **No rollup is keyed by variant.**
   - `region_fleet_summary`, `region_top_factors` and `region_wear_trends` are keyed by `region_id` only
     (`openddil:openddil-stack/schema/schema.hcl:1084, 1167, 1213`).
   - `platform_variant` exists only as a column on per-asset rows. "Fleet incidence from the rollups by variant"
     needs a new rollup. It cannot be read from an existing one.

A fourth premise needs a qualifier rather than a correction:
- emission state is on the wire (`OperationalState.emitting`, field 11; `launcher_raised`, field 7) but is **not
  projected** to a column (`openddil:openddil-projector/src/handlers/telemetry_latest.py:184-198`);
- `telemetry_latest_state.actively_transmitting` is persisted, but latest-only.

So "per emitting hour" has no history to integrate today.

## Context

FRACAS asks four questions of every failure:
- what failed;
- under what use;
- in what condition and configuration;
- did the corrective action stop it recurring.

A tier already holds most of the inputs. They sit in separate records, and some are kept only as latest state. The
gap is joining them at the moment of failure and keeping that join after the fault clears.

## What exists today

| FRACAS input | record and columns today | kept |
|---|---|---|
| failure, first observed | `ConfigurationDiscrepancy.detected_at`; cm-service `DiscrepancyRecord.detected_at_ns` (`openddil:openddil-cm-service/src/as_maintained/persistence_model.py:66-105`) | while open |
| detecting source and filer | `DiscrepancySource{source, reported_by, event_id, reported_at, description}` (`openddil:openddil-contracts/proto/openddil/configuration/v1/discrepancy.proto:169-174`); later reports append to `sources[]` | while open |
| item and failure code | `component`, `fault_code`; the episode key is uuid5 over asset, component, fault_code (`asset_cm.py:542-589`) | while open |
| the episode as released | `MaintenanceFaultEvent{event_id, episode_id, asset_id, owning_tier, fault{item, fault_code, observed_at}, sources[], picture{…}, label, provenance[]}` (overlay kind schema; `openddil:ADR-0046` §3 and its 2026-10-13 amendment) | in the egress ledger |
| release record | `egress_delivered_events{route, event_id, outcome, http_status, case_id, first_recorded_at, recorded_at, episode_id, asset_id, component, fault_code}` (`schema.hcl:1935-1999`) | durable |
| cleared | the `ManualDiscrepancyResolved` CmEvent (`recorded_at`, `recorded_by`, `resolution`) on `cm-events` | 30 days |
| use: rounds | `effector_launch.quantity` per `launcher_asset_id`; view `effector_launcher_counts{expended, in_flight, unresolved, declared, remaining}` (`schema.hcl:1485-1600, 1870-1925`) | durable |
| use: moves | `openddil.posture.transition` CloudEvents (`data{from, to, at, motion, …}`) in `tactical_events.data` (`openddil:openddil-tactical-agents/edge/posture_event.py:33-85`) | durable |
| use: emission | `telemetry_latest_state.actively_transmitting`; element `tx_active` in `asset_element_telemetry.elements` | latest only |
| condition | `asset_telemetry_windows{fluid_trends, consumable_trends, component_wear_trends, window_duration_seconds, computed_at}`; `telemetry_latest_state` (power, health, posture) | latest only |
| configuration | `AsMaintainedConfiguration`, `ModCompliance{mod_id, state, applied_at, applied_by_work_order}` (`openddil:openddil-contracts/proto/openddil/configuration/v1/as_maintained.proto:58-89`); `asset_logistics_status.cm_baseline_id` | latest only |
| mod events | `ModApplied{mod_id, applied_at}`, `PartReplaced`, `BaselineAssigned` (`cm_events.proto:38-82`). The handlers overwrite state in place (`asset_cm.py:454-497`). | latest state; events 30 days |
| variant | `platform_variant` on `telemetry_latest_state`, `asset_telemetry_windows`, `asset_element_telemetry` | per asset |

## Decision

### 1. A closed episode is kept, not removed

Resolving an episode stamps it and moves it to a closed set. It does not filter it out of the list.

- New fields: `cleared_at_ns`, `cleared_by` (the resolver's sub, the same field the PEP stamps today),
  `resolution` (the field-16 text, read at last).
- The closed set lives at the owning tier. It is append-only and keyed by the existing episode id, so a refile after
  closure is a new episode, as it is today.
- `manual_discrepancies` keeps its meaning: open episodes only. Existing readers see no change.
- Closure ages out with the asset under `openddil:ADR-0044`'s prune rule, as every other per-asset row does. The
  release record (`egress_delivered_events`) is unaffected.

### 2. The episode freezes its context at open

When an episode opens, the tier writes three frozen references with it. The values are never recomputed later.

| frozen at open | from |
|---|---|
| `baseline_id` and the `ModCompliance` list | `AsMaintainedConfiguration` at `detected_at` |
| `condition_ref` | the `asset_telemetry_windows` row as of `detected_at` (copied, since the row is latest-only), plus the `telemetry_latest_state` posture, power and health |
| `usage_at_open` | the counters in §3, read at `detected_at` |

This is configuration status accounting at the moment of failure: the record states what the item was, not what it
is now.

### 3. Usage is a declared meter per variant, never a fixed list

FRACAS rates need a denominator, and the right one depends on the variant: a launcher wears per round, a radar per
emitting hour, a towed item per move. This ADR does not hardcode the three. Each variant declares its usage meters as
overlay data, next to its enumeration files:

| meter kind | read from | today |
|---|---|---|
| `count:rounds` | sum of `effector_launch.quantity` for the launcher | exists |
| `count:moves` | posture transitions into `moving` in `tactical_events` | exists |
| `duration:emitting` | integrated `OperationalState.emitting` (or `actively_transmitting`) over time | **new: needs an accumulator** |

A meter is monotonic per asset. The episode stores its value at open (§2) and at close. A rate is computed at read
time from those values, and is never stored.

### 4. Fleet incidence is a composable rollup by variant

There is a new rollup keyed by `(region_id, platform_variant, component, fault_code)`. It holds only sums: the
episode count, the summed meter deltas and the asset count. Sums compose up the tiers, and rates do not. A
top-N would fail `openddil:ADR-0034`'s composability gate, as `region_top_factors` does (GD-05), so the rollup holds
none. HQ divides at read time.

### 5. Closure verification is recurrence on a partitioned fleet

A corrective action is verified when the same `(variant, component, fault_code)` stops recurring on the assets that
received the mod, against those that did not, over matched usage.

- **Partition:** `ModCompliance.state = APPLIED` with `applied_at` before the window.
- **Measure:** episodes per unit of the variant's meter, in each partition, from closed episodes (§1).
- The tier reports the two rates and their counts. It does not declare the action effective. That judgement belongs
  to the review board (`openddil:ADR-0038` C7: the system states facts, never a verdict).

### 6. The seam: a failure report out, a corrective action in

- **Outbound:** a new overlay kind, `FailureReport`, released through the existing gate (`openddil:ADR-0046` §4).
  - Its declarations reuse `MaintenanceFaultEvent`'s: key `/event_id`, `/label`, `/owning_tier`, and episode
    `(/asset_id, /fault/item, /fault/fault_code)`.
  - It adds the closed fields (§1), the frozen context (§2) and the meter values (§3).
  - It is emitted once, on close. An open episode is already released as `MaintenanceFaultEvent`.
- **The other side:** iagent reserves the content kind **`fracas_report`** at its door. `iagent:ADR-0063` is the
  receiving half. The destination sends `FailureReport` as `content_kind: fracas_report`, the way
  `MaintenanceFaultEvent` already leaves under its own content kind.
  - It enters through the existing door (`POST /ingest/events`, `iagent:src/iagent/gateway.py`).
  - It arrives as an event carrying `on_behalf_of`, our `episode_id` and our `asset_id`. `on_behalf_of` names the
    person who closed the episode (`/cleared_by`), declared in the overlay the way `MaintenanceFaultEvent` names its
    filer.
  - Its `provenance[]` entries keep their source class. The CM report and the people's declarations are
    **declared**, the telemetry at open is **observed**, and the meter values are **derived**. iagent passes them
    through its provenance unmerged (`iagent:ADR-0063`).
  - It feeds iagent's `safety:FailureRecord` (`iagent:agent_fleet/safety_agent/entities.py`) as a cited occurrence.
    The system of record it cites is the owning tier.
- **Inbound:** a FRACAS corrective action returns as an intake kind (`openddil:ADR-0046` §5) carrying a
  `ModificationRequirement` (`mod_id`, `ModType`: MWO, TCTO or SHIPALT).
  - The intake records the requirement against the variant's baseline catalog.
  - **It applies to no asset.** Application stays a person's `ModApplied` event at the tier, as today.
  - A returned corrective action is a declaration of what should change, never a side effect that changes
    configuration.
- **Write-back** to an upstream system of record is iagent's own ruling (`iagent:docs/adr/ADR-0054-data-classes-every-write-declares-what-it-is.md` §3).
  OpenDDIL sends a report and takes in a requirement. It writes to no one else's store.

## What is new

- A closed-episode set with `cleared_at_ns`, `cleared_by` and `resolution`, at the owning tier (§1).
- Frozen context at open: `baseline_id`, mod compliance, a condition copy and meter values (§2).
- Declared usage meters per variant, as overlay data (§3), plus one new accumulator, for `duration:emitting`.
- The `(region, variant, component, fault_code)` sums rollup (§4).
- The partitioned recurrence read (§5).
- Two kinds, `FailureReport` out (as `content_kind: fracas_report`, reserved on iagent's side) and `CorrectiveAction`
  in (§6).
- Unchanged: the gate, the door, the episode key, the open-episode list, and `MaintenanceFaultEvent`.

## Alignment declared (ADR-0038 C1 intake)

**By concept name only.** No schema text, element names or code lists are copied here or into the kinds.

| OpenDDIL | aligned to | concepts named |
|---|---|---|
| episode (open and closed), `sources[]` | MIL-HDBK-2155 (FRACAS) | failure report, failure occurrence, detection method, reporting individual |
| closure verification (§5) | MIL-HDBK-2155 | failure analysis, corrective action, verification of effectiveness, failure review board |
| usage meters (§3) | MIL-STD-1388-2B / ASD S5000F | operating time, cycles and events as usage; in-service usage data feedback |
| frozen `baseline_id` and mod compliance (§2) | EIA-649 | configuration status accounting; configuration as of a point in time |
| `CorrectiveAction` → `ModificationRequirement` | EIA-649 | change (engineering change, modification) and its effectivity |

The field names are OpenDDIL-local, with a declared alignment intent. Binding them to named elements is owed before any
field is frozen.

## First demo-able slice

**"The fault cleared, and the record stayed." About 4 days.**

Scope:
1. **cm-service, 1.5 d.** On field 16, move the episode to a closed set with `cleared_at_ns`, `cleared_by` and
   `resolution`, instead of filtering it out. Freeze `baseline_id` and the `ModCompliance` list at open. Unit tests
   cover open, refile after close, and resolve with no open episode.
2. **Store and projector, 1 d.** Add a `failure_episodes` table at the tier: `episode_id`, `asset_id`, `component`,
   `fault_code`, `detected_at`, `cleared_at`, `cleared_by`, `resolution`, `sources`, `baseline_id`, `mod_compliance`,
   `rounds_at_open`, `rounds_at_close`, `moves_at_open`, `moves_at_close`, plus labels. Atlas migration.
3. **One pane, 1 d.** An episode history on the asset page: first observed, cleared, filer, source, the configuration
   at open, and "N rounds / M moves since the previous episode".
4. **Run, 0.5 d.** On the lab, Ada files and resolves on one asset, then files again. The history shows two closed
   rows and one open row. Read in the database directly as well as on screen.

Out of the slice:
- emitting hours (needs the accumulator);
- the variant rollup;
- the recurrence read;
- both kinds and the iagent registration.

The slice needs no new gate route and sends nothing.

**Demo line:** "The radar's array module failed twice in 40 rounds. Both times it was on baseline B with the mod not
applied, and the record says who found it and who closed it."

## Generalization debt

**GD-15** (`GENERALIZATION-DEBT.md`): the first slice reads two usage meters, rounds and moves, by name in the
projector, instead of from the variant's declared meters (§3). The declared form is the decision; the named form is
the slice. Status `open`.

## Consequences

### Positive
- A failure keeps its who, when, configuration and use after it clears. That is the minimum a FRACAS needs from the
  field.
- Rates compose up the tiers without a top-N, so HQ incidence is exact.
- A corrective action never changes configuration by itself. Application stays a person's act.

### Negative
- The tier stores closed episodes indefinitely within the asset's life, so per-asset rows grow with failures.
- The condition copy at open duplicates a windows row. That is a deliberate cost of latest-only tables.
- `duration:emitting` needs a new accumulator on a value that is not projected today.

### Neutral
- `manual_discrepancies` keeps meaning "open now". The open-episode wire and the release of
  `MaintenanceFaultEvent` do not change.

## Related
- `openddil:ADR-0009`: the CM model, and the source of `baseline_id` and `ModCompliance`.
- `openddil:ADR-0034`: the composability gate the variant rollup must pass.
- `openddil:ADR-0038`: C1 alignment, and C7 (no verdicts).
- `openddil:ADR-0044`: posture signals and the prune rule.
- `openddil:ADR-0046`: kinds, the gate and intake, and the episode amendment of 2026-10-13.
- `openddil:ADR-0048` / `openddil:ADR-0049`: the effector ledger and its rounds.
- `iagent:docs/adr/ADR-0056-fracas-phase-1-what-failed-on-this-part-across-programs.md`: `safety:FailureRecord`.
- `iagent:docs/adr/ADR-0054-data-classes-every-write-declares-what-it-is.md` §3: write-back is its own ruling.
- `iagent:ADR-0063`: the receiving half; reserves `fracas_report`, `safety_finding` and `cyber_indicator`, and keeps
  source classes unmerged.
