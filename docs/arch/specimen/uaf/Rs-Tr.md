# Resources-Traceability (Rs-Tr)

Each activity in [Operational-Processes](../../views/Op-Pr.md) against the functions in [Resources-Processes](../../views/Rs-Pr.md) and the kit members in [Resources-Structure](../../views/Rs-Sr.md) that perform it. A row with no function is a gap and says so.

| Activity | Function | Resource | Capability |
|---|---|---|---|
| A1.1 Decode structure | F1 | Ingress sidecar | DataAcquisition |
| A1.2 Map semantics | F2 | Connect pipeline | DataManipulation |
| A1.3 Stamp labels | F3 | Ingress mapping | LabelledReadEnforcement |
| A2.1 Declare or confirm an arrival | F10, F6 | Read-path enforcement point, Projector | ArrivalDeclaration |
| A2.2 Account for configuration | F5 | Configuration service | ConfigurationStatusAccounting |
| A2.3 Track effectors | F4 | Stream aggregator | StateDetection |
| A3.1 Derive operational state | F4 | Stream aggregator | StateDetection, HealthAssessment |
| A3.2 Keep status and reporting apart | F4, F6 | Aggregator, Projector | StateDetection |
| A3.3 Surface a disagreement | F15 | Not built | DisagreementDetection |
| A4 Aggregate up the tiers | F7, F8 | Bridge, Regional aggregator | HierarchicalAggregation |
| A5 Present to an operator | F9, F10 | Policy decision point, Read-path enforcement point, Presentation | InformationPresentation |
| A6.1 Assemble a record | F11 | Egress assembler | GatedRelease |
| A6.2 Decide against the destination | F9, F12 | Policy decision point, Egress gate | GatedRelease |
| A6.3 Forward | F13 | Egress forwarder | GatedRelease |
| A7.1 Validate and check labels | F14 | Egress intake | GatedIntake |
| A7.2 Check the approvers | F14 | Egress intake | GatedIntake |
| A7.3 Refuse on an interlock | Gap: no function yet | Not built | SafetyInterlockRefusal |
| A8 Reconcile intent with the record | Gap: no function yet | Not built | OfflineIntentReconciliation |

The Activity, Function and Capability columns use names the other views and the model define. Who approves: {{slot:approval-authorities}}.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| The matrix joins [Operational-Processes](../../views/Op-Pr.md) and [Resources-Processes](../../views/Rs-Pr.md) and adds no claim of its own; marks are in those views | [ADR-0037](../../../../decisions/ADR-0037-verification-evidence-is-a-deliverable.md) | Standing | Not stated |
| A7.3 gap | [ADR-0052](../../../../decisions/ADR-0052-safety-states-and-release-interlocks.md) | Accepted | Design only |
| A8 gap | [ADR-0040](../../../../decisions/ADR-0040-offline-sustainment-and-intent-reconciliation.md) | Accepted | Nothing built |
