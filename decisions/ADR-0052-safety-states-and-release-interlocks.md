# ADR-0052 — Safety states as declared findings, and work release refused by named live state

## Status

**PROPOSED — 2026-10-29.** Design only. Nothing here is built or deployed.
- Extends `openddil:ADR-0046`: one new intake kind, one new outbound kind, and one new refusal reason at the existing
  intake gate.
- Reads `openddil:ADR-0044` (posture), `openddil:ADR-0048` / `openddil:ADR-0049` (the effector ledger and munition
  tracks) and `openddil:ADR-0050` (arrivals).
- On the other side of the seam it meets
  `iagent:docs/adr/ADR-0051-sustainment-safety-the-mesh-drafts-a-risk-and-refuses-to-accept-it.md`. That ADR owns
  hazard tracking and risk acceptance, and this one gives it findings.

## Findings first: four premises that are not true today

1. **No action that reaches a tier today can be interlocked.**
   - The one inbound action kind, `MaintenanceAction`, reports work **already done**: `work_order.outcome` is required
     (lab overlay `kinds/MaintenanceAction.schema.json`).
   - Refusing it at the intake would refuse a record of the past, not stop a hazard.
   - The PEP's operator actions (file, resolve, arrivals) are bookkeeping and touch no hardware.
   - An interlock needs an action that **precedes** the work. This ADR adds one (§2).
2. **The states an interlock needs are on the wire but not stored.**
   - `OperationalState.emitting` (field 11) and `launcher_raised` (field 7) are decoded at ingest
     (`openddil:openddil-sensor-ingest/condition.py:273`, `appearance.py:139`).
   - They feed only the edge posture machine. `telemetry_latest_state` has no column for either
     (`openddil:openddil-projector/src/handlers/telemetry_latest.py:184-198`).
3. **"Raised in march order" cannot happen as stated, but the hazard behind it is real and already recorded.**
   - `march_ordered` means stationary with the launcher stowed. Lowering the launcher is the transition into it
     (`openddil:ADR-0044`, posture amendment, transition table).
   - The machine does, however, enter `moving` from **any** state once motion is held, `emplaced` included.
   - An `emplaced → moving` transition is a launcher that moved without stowing. That transition is a durable
     `openddil.posture.transition` record in `tactical_events.data`
     (`openddil:openddil-tactical-agents/edge/posture_event.py:33-85`).
   - So the finding is **"moved while raised"**, read from a transition that is already kept.
4. **Two of the six hazards have no column in openddil.**
   - **Deferred maintenance past interval:** deferral is held by the system of record and modelled in iagent
     (`iagent:agent_fleet/safety_agent/entities.py`, `WorkOrder.deferred`). The nearest openddil signals are
     `WearState.status` `WEAR_SERVICE_DUE` / `WEAR_CRITICAL`
     (`openddil:openddil-tactical-agents/edge/prognostics/models.py:168-177`) and the CM rule `required-mod.overdue`
     (`openddil:openddil-cm-service/src/discrepancy/analyzer.py:306-335`).
   - **Rounds on hand versus storage limits:** no storage, magazine or explosive limit is declared anywhere. There are
     only `effector_declared_load` (`openddil:openddil-stack/schema/schema.hcl:1828`) and the wire
     `ConsumableState.quantity_capacity`.

A fifth note: "MIL-STD-882", "interlock" and "hazard" in the weapons-safety sense appear nowhere in openddil. This ADR
introduces the vocabulary.

## Context

A sustainment picture holds live state that a maintainer's release should respect. Do not release a T/R module task
on a radar that is radiating. Do not release launcher work while a round from that launcher is in flight or
unresolved.

The tier also holds combinations of state that are hazards on their own, whether or not anyone acts on them.

OpenDDIL is not a weapon control system and issues no commands to equipment. Its part is procedural:
- refuse to *release* work while the record shows a conflicting state, and name the state;
- surface hazard states as findings for the safety workflow to track.

## What exists today

| input | record and columns | kept |
|---|---|---|
| emitting | `OperationalState.emitting` on the wire; `emitting()` = true/false/none from EE beam count within `silence_after_s` (`condition.py:273`) | not stored |
| launcher raised | `OperationalState.launcher_raised` on the wire, from appearance bit 16 (`openddil:openddil-contracts/ontology/dis_appearance.yaml:55-88`) | not stored |
| transmitting | `telemetry_latest_state.actively_transmitting` | latest only |
| posture | `telemetry_latest_state.posture_status`, `posture_since`; transitions in `tactical_events.data` | latest; transitions durable |
| lifecycle | `telemetry_latest_state.operational_status` (`destroyed` / `deactivated` / `removed`) and `reporting_status`, each with `_at` (`schema.hcl:532-543`) | latest only |
| round in flight | `effector_launch.terminal_state IS NULL`; `munition_track.terminal_state IS NULL` (`schema.hcl:1485-1600, 1689-1818`) | durable |
| unresolved launch | `effector_launch.terminal_state = 'unresolved'`, set by the sweep after `effectors.terminalTimeoutSeconds` (`openddil:openddil-projector/src/persistence/postgres.py:559-566`); view `effector_launcher_counts.unresolved` | durable |
| undeclared arrival | `asset_declaration`, `asset_correlation`, `asset_fielding.due_by`; per-edge `undeclared` / `expected` / `overdue` (`openddil:openddil-demo/gateway/pep.py:2178-2240`) | durable |
| wear, overdue mods | `WearState.status`; CM `required-mod.overdue` | latest only |
| rounds on hand | `effector_launcher_counts.remaining` (unclamped; negative = over-expended); `effector_declared_load` | durable |
| per-variant data | `openddil:openddil-contracts/ontology/dis_entity_types.yaml` (`platform_variant`, `deployment_signal`, `default_baseline`); `effectors.declaredLoad.{asset,variant}` and `movement.standards` (`openddil:openddil-helm/openddil-demo/values.yaml:750-790`) | overlay data |
| refusal shape | intake reasons `schema_invalid`, `label_mismatch`, `answered_record_unknown`, `approvers_*`, `on_behalf_of_untrusted` (`openddil:openddil-demo/egress/intake.py:94-100`); decisions in `intake_records` | durable |

## Decision

### 1. Hazard states are declared findings, not computed verdicts

Each hazard is a named predicate over stored columns, declared as overlay data. A finding is a record that states the
predicate, the rows that met it, and when. The tier never grades severity or probability: that is iagent's risk
matrix (`iagent:docs/adr/ADR-0051-…` §2), and C7 forbids the system asserting it.

| hazard (finding name) | predicate over stored records | today |
|---|---|---|
| `unresolved_launch` | `effector_launch.terminal_state = 'unresolved'` for the launcher | ready |
| `destroyed_still_reporting` | `operational_status = 'destroyed'` and `reporting_status = 'reporting'` | ready |
| `moved_while_raised` | a posture transition `emplaced → moving` | ready (transition record) |
| `undeclared_arrival` | an asset at a site with no `asset_declaration` | ready (arrivals summary) |
| `service_due_unreleased` | `WEAR_CRITICAL`, or `required-mod.overdue`, with no open work | **partial**: deferral is the system of record's (finding 4) |
| `over_declared_holding` | `remaining` above a declared storage limit for the site or variant | **new**: needs a declared limit |

A finding opens, stays open while the predicate holds, and closes when it stops holding. It uses the open/closed
episode shape of `openddil:ADR-0051` §1, so its history is kept.

### 2. Work release is a new intake kind, and the interlock refuses it

A new inbound kind, `WorkRelease`, sent **before** physical work begins. It carries:
- `release_id`, `asset_id`, `owning_tier`, `label`, `on_behalf_of`, `approval_chain`;
- `task_refs[]`: declared task classes. The free-text `task` string is never matched.

It passes the intake gate exactly as `MaintenanceAction` does. Then a new check runs, the interlock:

> For the asset's `platform_variant`, and for every `task_ref`, look up the conflicting states declared for that
> pair. Read each state from the tier's stored record. If any is present, refuse.

**Refusal reason: `interlock_conflict`.** The detail names each state, its value, its source column, and the time it
was last observed. For example:

```
interlock_conflict: emitting=true (telemetry_latest_state.emitting, observed 2026-…Z)
```

There is no generic deny.

**Unknown state refuses as well.** The reason is `interlock_state_unknown`, given when:
- the record is stale (`reporting_status` is not `reporting`);
- the state was never observed;
- the variant has no rules.

This follows `openddil:ADR-0043` §9 (fail closed and loud). A release on a silent asset is not a release on a safe
asset.

An admitted `WorkRelease` is recorded in `intake_records` with the states it was checked against. Admission is not
a statement that the work is safe. It states only that the record showed no declared conflict at `decided_at`.

### 3. The interlock rules are overlay data per variant, never code

```yaml
# overlay: interlocks/<platform_variant>.yaml (shape only; values are the customer's)
variant: <platform_variant>
rules:
  - task_ref: <declared task class>
    refuse_while: [emitting, launcher_raised, round_in_flight, round_unresolved]
```

- The state names are a declared vocabulary. Each maps to a stored column or view in the table above.
- An unknown state name in a rule file fails the render, as unknown entity mappings do today.
- The OSS default is empty, so no variant is interlocked until an overlay says so.

### 4. Store the two missing states

The projector writes `emitting` and `launcher_raised` to `telemetry_latest_state` as nullable booleans, with their
own `_at` timestamps.
- Null means not observed, and is never coerced to false.
- This is the minimum change to make findings 2 and 3 readable. It does not change `posture_status`, which still
  decides posture once, at the edge.

### 5. The seam: findings out, risk stays with iagent

- **Outbound:** a new overlay kind, `SafetyFinding`, released through the existing gate (`openddil:ADR-0046` §4).
  - Key `/finding_id`; episode `(/asset_id, /hazard, /opened_at)`.
  - It carries the predicate name, the rows that met it, and the open and close times.
- **The other side:** iagent reserves the content kind **`safety_finding`** at its door. `iagent:ADR-0063` is the
  receiving half. The destination sends `SafetyFinding` as `content_kind: safety_finding`. It seeds iagent's safety
  workflow, and the finding becomes a cited occurrence against a `Hazard` (`iagent:agent_fleet/safety_agent/entities.py`).
  - It arrives as an event carrying `on_behalf_of`, our `episode_id` and our `asset_id`. A finding is the system's
    reading of a declared predicate, not a person's act. `on_behalf_of` is declared per kind in the overlay, and
    which subject it names is confirmed against `iagent:ADR-0063` before the kind is frozen.
  - The rows that met the predicate travel as `provenance[]` entries, each with its source class. Emitting and
    launcher state are **observed**, work and holding records are **declared**, and the finding itself is
    **derived**. iagent passes them through unmerged (`iagent:ADR-0063`).
  - Severity, probability, mitigation and acceptance are iagent's (`iagent:docs/adr/ADR-0051-…` §2, §5).
  - The safety workflow's task kinds (`iagent:policy/overlays/sample/task_kinds/risk_acceptance_*.yaml`) decide;
    OpenDDIL never does.
- **Inbound:** `WorkRelease` (§2). An accepted risk does not lift an interlock. Lifting one is a change to the
  overlay rule file, a declaration made by a person and reviewed like any overlay change.

### 6. What this ADR does not claim

The interlock is a procedural check on a record. It must not be credited as a hazard control in a hazard analysis
until a software safety assessment has been done on it, and this ADR does not do one. The physical interlocks on the
equipment stay the controls of record.

## What is new

- The `emitting` and `launcher_raised` columns, with `_at` (§4).
- The `WorkRelease` intake kind (§2).
- The `interlock_conflict` and `interlock_state_unknown` refusal reasons (§2).
- The interlock rule files per variant, with a declared state vocabulary (§3).
- Six declared hazard predicates, and a finding record with open/closed history (§1).
- The `SafetyFinding` outbound kind, sent as `content_kind: safety_finding` (reserved on iagent's side) (§5).
- A declared storage limit, for `over_declared_holding` only.
- Unchanged: the intake gate's order, the existing kinds, the posture machine, and every lifecycle column.

## Alignment declared (ADR-0038 C1 intake)

**By concept name only.** No schema text, element names or code lists are copied here or into the kinds.

| OpenDDIL | aligned to | concepts named |
|---|---|---|
| hazard predicates and findings (§1) | MIL-STD-882E | hazard, hazard tracking, hazardous condition, mishap |
| `SafetyFinding` → iagent risk | MIL-STD-882E | risk assessment, risk acceptance by the appropriate authority (iagent's, never OpenDDIL's) |
| interlock refusal (§2, §6) | MIL-STD-882E | safety interlock as a design mitigation; software safety criticality (owed, §6) |
| `WorkRelease` | ASD S5000F | maintenance task, authorisation |

The field names are OpenDDIL-local, with a declared alignment intent. Binding them to named elements is owed before any
field is frozen.

## First demo-able slice

**"The release was refused, and the refusal said why." About 4.5 days.**

Scope:
1. **Projector and schema, 1 d.** Add `emitting`, `emitting_at`, `launcher_raised` and `launcher_raised_at` to
   `telemetry_latest_state` (Atlas migration; null means not observed). Unit tests cover true, false and absent.
2. **Interlock check in the intake, 1.5 d.**
   - Accept `WorkRelease` (an overlay kind schema).
   - Load `interlocks/*.yaml`, read the asset's stored state, and refuse with `interlock_conflict` or
     `interlock_state_unknown`, the detail naming the states.
   - Tests cover each state, stale, unobserved, no rules, and admit.
3. **Lab overlay data, 0.5 d.** Two rule files:
   - the sensor variant: `task_ref` array work refused while `emitting`;
   - the interceptor variant: launcher work refused while `launcher_raised`, `round_in_flight` or `round_unresolved`.
4. **Run, 1.5 d.** On edgy-lab, post three releases through the stand-in consumer's path:
   - 1010 while radiating: refused, `emitting=true`;
   - an interceptor with a round in flight: refused, `round_in_flight`;
   - 1010 after it goes silent: admitted.

   Read the decisions in `intake_records` and in the gate's decision lines.

Out of the slice:
- the hazard findings (§1);
- the `SafetyFinding` kind;
- the iagent registration;
- storage limits;
- the PEP pane.

The slice sends nothing to iagent.

**Demo line:** "The array task was refused because the radar was radiating, and the refusal names the column and the
second it was last seen."

## Generalization debt

**GD-16** (`GENERALIZATION-DEBT.md`): the interlock state vocabulary is a closed set of four names, each bound to a
column in code (§3), rather than predicates the overlay declares over stored columns. A variant whose conflicting
state is not one of the four cannot be interlocked without a code change. Status `open`.

## Consequences

### Positive
- The refusal names the state, the column and the time. An operator can see why, and a reviewer can check it against
  the record.
- Rules are customer data per variant. The OSS default interlocks nothing.
- Risk stays with the authority that owns it. OpenDDIL states conditions and never grades them.

### Negative
- A release on a stale asset is refused. In a long outage this blocks legitimate work until state returns or the
  rule file changes. That cost is chosen deliberately, and has to be explained.
- Two more columns on the hottest table.
- `WorkRelease` needs the sender to send releases, which iagent does not do today.

### Neutral
- `MaintenanceAction` is unchanged. Completed work is never refused by an interlock.

## Related
- `openddil:ADR-0043`: refusal by named reason; fail closed and loud.
- `openddil:ADR-0044`: posture and its transition table.
- `openddil:ADR-0046`: the intake gate and kinds.
- `openddil:ADR-0048` / `openddil:ADR-0049`: launches, munition tracks and terminal states.
- `openddil:ADR-0050`: declarations and arrivals.
- `openddil:ADR-0051`: the open/closed episode shape, reused for findings.
- `iagent:docs/adr/ADR-0051-sustainment-safety-the-mesh-drafts-a-risk-and-refuses-to-accept-it.md`: the hazard,
  risk matrix and acceptance.
- `iagent:ADR-0063`: the receiving half; reserves `safety_finding` and keeps source classes unmerged.
