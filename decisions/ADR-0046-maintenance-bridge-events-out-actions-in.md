# ADR-0046 — The maintenance bridge: events out through the gate, actions in as local decisions

## Status

**PROPOSED — 2026-10-02. Awaiting approval; nothing here is built.** Extends
`openddil:ADR-0031` (the reasoning-plane seams). It adds a second seam:
ADR-0031 lets an agent read the tier, and this ADR sends a maintenance event
out to the workflow plane and takes an approved action back in.

### Decisions taken for this pass, recorded as such

These are inputs to this ADR, not conclusions it argues for:

1. **The workflow runs in iagent. OpenDDIL holds no workflow state.** Approval
   routing, pending tasks, escalation and timers live in the iagent workflow
   definition (`iagent:ADR-0039`) and its decision records (`iagent:ADR-0034`).
   OpenDDIL holds the event it sent, the action it received, and the local
   decision it made about that action. Nothing in OpenDDIL says "awaiting
   approval".
2. **Per-tier iagent is the design; a single instance is this pass.** Each tier
   would eventually reach its own reasoning plane, as in ADR-0031. In this pass
   one iagent instance (the hub's) serves every tier.
3. **The maintenance beat is shown connected**, separate from the severance
   rehearsals. `sever-tier.sh` is not changed to exempt anything. A severed tier
   queues events at its gate's output, like every other egress.
4. **Action-record vocabulary:** work orders aligned to ASD S5000F concepts,
   faults to MIMOSA CBM concepts, declared under `ADR-0038` C1 (§Alignment
   declared below). The alignment is by concept name only. The field
   definitions are ours.
5. **The first asset is a medium-range air defense radar (MRAD).** It joins the
   lab fleet as one pinned id with a SISO radar entity type, declared in
   `releasability.yaml`. The failure is a discrete fault in one **array
   module**. A maintainer reports it through the UI as a CM discrepancy, and a
   BIT-style telemetry fault is a second source. It is not a wear path.

## Context

OpenDDIL already sends state out through one gate: the C2 egress gate
(`openddil:ADR-0043`) reads a source topic and decides each record against one
destination subject's nations. It writes the admitted records to a sink topic
and logs every decision, admitted or refused, as one JSON line. The gate is
generic: source topic, sink topic, and destination are configuration
(`egress/main.py`).

Maintenance needs the same gate in both directions:
- **Out:** a fault on an asset needs a decision from people who are not at the
  tier: what to do, with which parts, and who approves.
- **In:** that decision has to come back to the tier that owns the asset. It
  is recorded there as that tier's own decision, and then sent on to whatever
  system tracks the work.

ADR-0031's addendum already drew the division this ADR depends on:
- **OpenDDIL holds STATE**: what is wrong with this asset now.
- **The reasoning plane holds KNOWLEDGE**: what the manual says to do about it.

The workflow (who must approve) is a third thing. Decision 1 puts it in iagent.

## Decision

### 1. Event out: a fault, with the asset's current picture

One `MaintenanceEvent` per **fault episode**, minted at the owning tier.

| field | meaning |
|---|---|
| `event_id` | minted by the owning tier; stable for the episode |
| `kind` | `cm_discrepancy` or `lifecycle_transition` |
| `asset_id`, `owning_tier` | the subject asset and the tier that owns it (ADR-0028's static assignment) |
| `fault` | `item` (generic item name, e.g. "array module", plus position), `fault_code`, `observed_at` |
| `sources[]` | one entry per independent report: `source` = `maintainer_report` or `bit_telemetry`; `reported_by` (a subject `sub` or a sensor id); `observed_at`; the row it came from |
| `picture.readiness` | the asset's current operational and reporting status (ADR-0044's two columns) |
| `picture.factors` | the asset's current constraining factors, as the tier computes them |
| `picture.lifecycle` | the lifecycle state, as ADR-0044 stores it |
| `picture.spare` | for the faulted item: `on_hand_here`, `nearest_site_with_stock`, `as_of` (from the spare-parts stand-in) |
| `picture.battle_condition` | from the readiness rollup at the owning tier |
| `label` | `originator_nation`, `releasable_to`, from the asset's declaration in `releasability.yaml` |
| `provenance` | the rows the picture was read from, each with its key and timestamp |

**One fault, one event, however many sources.** The episode key is
`(asset_id, fault.item, fault.fault_code)` while the episode is open. A second
source inside an open episode is appended to `sources[]` and published as a
revision of the same `event_id`. Events are counted by distinct `event_id`, and
sources are counted separately. A BIT fault and a maintainer report of the same
fault are one event with two sources.

### 2. Every event goes out through the gate

A second instance of the egress gate, configured for maintenance:
- source `maint-events`
- sink `egress-maint-events`
- destination `system:maint-iagent`

The gate decides each event exactly as it decides a C2 record: on the record's
label against the destination subject's nations. It applies the same
deny-unlabelled floor and logs one decision line per event. iagent's starter
reads the sink topic. The transport binding beyond the sink topic is not
decided here: no iagent instance is reachable from a deployed tier yet, so the
binding is settled when one is.

**Red-check**, carried by the build: an event about a BDR-originated asset,
offered to a destination entitled to ATL only (`system:c2-stand-in-atl`, the
existing ATL-only subject), is refused, and the refusal is logged.

### 3. Destinations are subjects in the registry

There is no `destinations.yaml`. A destination is a **system principal** in
`policy/users.yaml` (`openddil:ADR-0043`). The header comment of that section
records that such an identifier is asserted by deployment configuration. This
ADR adds two such principals:

| subject | nations | receives |
|---|---|---|
| `system:maint-iagent` | `[ATL, BDR]` | maintenance events (the workflow plane) |
| `system:mmis-stand-in` | `[ATL, BDR]` | released maintenance actions (the stand-in maintenance-management system) |

Both carry the existing caveat of that section: link authentication (mTLS or a
service identity) is out of scope, and the identifier is asserted by deployment
configuration.

### 4. Action in: a work order with its approval chain embedded

iagent returns one `MaintenanceAction` per decided work order.

| field | meaning |
|---|---|
| `action_id`, `event_id` | the action, and the event it answers |
| `asset_id`, `owning_tier`, `label` | copied from the event; the tier refuses an action whose label differs from its event's |
| `work_order.task` | what is to be done (e.g. remove and replace the array module at a position) |
| `work_order.task_refs[]` | the manual nodes the task cites: the graph URI (the identifier, per ADR-0031's addendum), plus the data-module code as display provenance |
| `work_order.parts[]` | `item`, `part_ref`, `quantity`, `source_site` |
| `work_order.outcome` | `approved` or `rejected`. These are final values only: there is no pending state in OpenDDIL |
| `approval_chain[]` | ordered steps: `step`, `role`, `approver_sub`, `decision`, `decided_at`, and a reference to iagent's decision record for that step |
| `provenance` | iagent workflow definition id and version, instance id, the manual nodes consulted |

**Approvers are resolved from the subject registry.** Every `approver_sub` must
resolve to a row in `policy/users.yaml`, and that subject must be entitled to
the action's label by the same predicate the read path uses. If any approver
fails to resolve or is not entitled, the action is refused at the tier, and the
refusal is logged.

### 5. Every action is a local decision at the owning tier

The owning tier decides each arriving action and logs one decision line. The
line has the same shape as the gate's (`decision_id`, `allowed`, `reason`, the
record key) and adds the approver chain's subjects. The decision is stored
locally at that tier, so the record of what was approved survives severance of
the tier.

An action the tier admits is then **released through the gate toward
`system:mmis-stand-in`**:
- a third gate instance, source `maint-actions-decided`, sink
  `egress-mmis-actions`;
- the maintenance pane on the hub reads what that gate released, filtered by
  viewer nations like the C2 pane, with withheld shown as a count of
  unlabelled records only.

### 6. The fleet addition keeps both partitions

The MRAD gets one pinned id in edge-01's entity range and is declared
ATL-originated in `releasability.yaml`:
- **No asset belongs to two edges** (`test_49`): the id is in edge-01's range
  only.
- **The nation partition** (`demos/releasability-partition.sh`) still splits
  into a non-empty ATL side and a non-empty BDR side.
- `dis:1:1:1099` stays undeclared.

Adding the asset changes the measured baseline (the fleet counts at hq, edge-01
and region-east, the C2 pane, and the TAK picture). Those changes are predicted
at the build, not assumed unchanged.

### Noted for later, not built

For a radar, battle condition should include **the coverage lost if a section
is taken down for the repair**. That is a future input to `picture` and to the
approval workflow, and it is not in this pass.

## Alignment declared (ADR-0038 C1 intake)

Two vocabularies are declared, by concept name only. **No schema text, element
names or code lists from either specification are copied here.** I do not have
either specification in hand. Writing plausible element names would produce
the artefact this corpus keeps catching: something that reads as a standards
citation and is a reconstruction.

| our record | aligned to | concepts named |
|---|---|---|
| `MaintenanceAction.work_order` | ASD S5000F (in-service data feedback) | maintenance task, the event that triggered it, the parts it consumed, who authorised it |
| `MaintenanceEvent.fault` and `sources[]` | MIMOSA CBM (OSA-CBM) | state detection (the BIT source), health assessment (the fault on an item), advisory (the returned work order) |

The field names in §1 and §4 are **OpenDDIL-local names with a declared
alignment intent**. Binding them to named S5000F and MIMOSA elements is owed
before any field is frozen, the same rung ADR-0044 stands on for JC3IEDM.

## Consequences

### Positive
- The gate stays the only way out, in both directions. No new egress path has
  its own authorisation logic.
- The owning tier's decision log names who approved the work, as that tier's
  own record, and it survives severance.
- OpenDDIL keeps no workflow engine. Changing the approval process is an edit
  to iagent's workflow definition, not an OpenDDIL release.

### Negative
- A single iagent instance means a severed tier cannot raise a work order until
  it is reconnected. Events queue at the tier's gate output. That is this pass's
  instantiation, not the design.
- System principals remain asserted by configuration (§3).
- Approver resolution couples the action path to the subject registry being
  current at the owning tier. A tier with a stale registry refuses
  newly-onboarded approvers, which is the safe failure.

### Neutral
- The C2 pane and the maintenance pane are the same mechanism with different
  destinations. A third destination is configuration, not code.

## Related
- `openddil:ADR-0031`: the reasoning-plane seams, and its 2026-09-08 addendum (state vs knowledge, graph URIs)
- `openddil:ADR-0043`: one predicate, two subjects (the egress gate)
- `openddil:ADR-0044`: lifecycle columns (readiness and lifecycle in `picture`)
- `openddil:ADR-0028`: asset registry lineage (`owning_tier`)
- `openddil:ADR-0038`: C1 intake (§Alignment declared)
- `iagent:ADR-0034`: decision records (the approval chain's references)
- `iagent:ADR-0039`: workflow definitions (where the approval process lives)
- `iagent:ADR-0035`: the process plane and the data plane
