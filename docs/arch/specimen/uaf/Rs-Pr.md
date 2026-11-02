# Resources-Processes (Rs-Pr)

The functions the resources perform. [Resources-Traceability](../../views/Rs-Tr.md) ties them to activities.

| Function | Performed by | What it does |
|---|---|---|
| F1 Decode | Ingress sidecar with a definition file | Binary to raw JSON on `ingress-<format>-raw` |
| F2 Map | Connect pipeline | Raw JSON to the Silver schema, in Bloblang, with no engine code |
| F3 Stamp | Ingress mapping | Writes originator nation and releasable-to onto provenance |
| F4 Assess | Stream aggregator | Derives operational state, status and posture at the tier that owns the sensor |
| F5 Account | Configuration service | Reports configuration status against a baseline |
| F6 Project | Tier projector | Writes each topic to the tier's store, by a mapping |
| F7 Bridge | Connect bridge | Carries a declared topic list to the parent |
| F8 Roll up | Regional aggregator | Aggregates children in a stream |
| F9 Decide | Policy decision point | Evaluates the predicate for a subject and a label |
| F10 Enforce a read | Read-path enforcement point | Applies the decision to a shape or a request |
| F11 Assemble | Egress assembler | Builds a record of a kind from the picture on a trigger |
| F12 Gate | Egress gate | Applies one predicate per route; writes one decision line |
| F13 Forward | Egress forwarder | Sends an admitted record to its route's destination |
| F14 Take in | Egress intake | Validates by kind, checks labels and approvers, and publishes onward |
| F15 Detect | Not built | Compares two named records and surfaces the disagreement |
| F16 Keep the failure record | Not built | Freezes a closed episode's context and verifies closure |

## Read against ISO 13374

This is a reading of the functions through ISO 13374 and not a conformance claim. The last column is the ADR's; the Functions column is this view's mapping onto it.

| Block | Functions | ADR's reading |
|---|---|---|
| 1 Data acquisition | F1 | Implemented |
| 2 Data manipulation | F2 | Implemented |
| 3 State detection | F4 | Implemented |
| 4 Health assessment | F4, F5 | Partial |
| 5 Prognostics | F4 | Partial: the mechanism, not a prediction |
| 6 Advisory generation | F4 | Partial: rule-based |

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| F1, F2 | [ADR-0030](../../../../decisions/ADR-0030-two-stage-configurable-ingress.md) | Accepted | Not stated |
| F3, F9, F10 | [ADR-0029](../../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Built |
| F4: state axes | [ADR-0026](../../../../decisions/ADR-0026-operational-state-orthogonal-axis-model.md) | Accepted | Not stated |
| F4: status at the owning tier | [ADR-0044](../../../../decisions/ADR-0044-lifecycle-two-columns-no-deletes.md) | Proposed | Built, unit-tested |
| F5 | [ADR-0009](../../../../decisions/ADR-0009-configuration-management-data-model.md) | Accepted | Not stated |
| F6, F7, F8 | [ADR-0022](../../../../decisions/ADR-0022-hierarchical-aggregation-is-the-architecture.md), [ADR-0023](../../../../decisions/ADR-0023-hierarchy-restoration-topology-and-phase-plan.md) | Accepted | Declared |
| F11, F14 | [ADR-0046](../../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Declared |
| F12, F13 | [ADR-0043](../../../../decisions/ADR-0043-egress-gate-one-predicate-two-subjects.md) | Proposed | Measured under compose |
| F15 | [ADR-0053](../../../../decisions/ADR-0053-logistics-cyber-detection-as-surfaced-disagreement.md) | Accepted | Design only |
| F16 | [ADR-0051](../../../../decisions/ADR-0051-failure-records-for-fracas.md) | Accepted | Design only |
| The ISO 13374 reading | [ADR-0038](../../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Partial |
