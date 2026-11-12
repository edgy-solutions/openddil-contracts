# Sample Fleet System: Strategic-Taxonomy (St-Tx)

built on OpenDDIL 0.1.161

The capabilities this architecture names. The grouping is this view's; each row cites where the capability comes from. ISO 13374 is used as a reading of what exists and is not a conformance claim. In scope for this deployment: {{slot:capabilities-in-scope}}.

```sysml
package CapabilityTaxonomy {
    doc /* ADR-0038 section 1 reads the capabilities through ISO 13374, as a reading and not a conformance claim. */

    abstract occurrence def Capability;

    abstract occurrence def ConditionMonitoring :> Capability;
    occurrence def DataAcquisition :> ConditionMonitoring;
    occurrence def DataManipulation :> ConditionMonitoring;
    occurrence def StateDetection :> ConditionMonitoring;
    occurrence def HealthAssessment :> ConditionMonitoring;
    occurrence def PrognosticAssessment :> ConditionMonitoring;
    occurrence def AdvisoryGeneration :> ConditionMonitoring;
    occurrence def InformationPresentation :> ConditionMonitoring;
    occurrence def DeclaredAnalyticUnits :> ConditionMonitoring;

    occurrence def HierarchicalAggregation :> Capability;

    abstract occurrence def Isolation :> Capability;
    occurrence def TierLocalDecision :> Isolation;
    occurrence def TierLocalSignIn :> Isolation;
    occurrence def TierLocalMaintenanceChain :> Isolation;
    occurrence def TierLocalWorkflow :> Isolation;
    occurrence def OneSession :> Isolation;
    occurrence def EdgeWorkflow :> Isolation;

    abstract occurrence def Correlation :> Capability;
    occurrence def TacticalSustainmentCorrelation :> Correlation;
    occurrence def ConfigurationStatusAccounting :> Correlation;
    occurrence def ArrivalDeclaration :> Correlation;

    abstract occurrence def Releasability :> Capability;
    occurrence def LabelledReadEnforcement :> Releasability;
    occurrence def GatedRelease :> Releasability;
    occurrence def GatedIntake :> Releasability;
    occurrence def DeclaredLabelDimensions :> Releasability;

    abstract occurrence def DataManagement :> Capability;
    occurrence def OneIdentityPerThing :> DataManagement;

    abstract occurrence def OperatorInteraction :> Capability;
    occurrence def DeclaredCards :> OperatorInteraction;

    abstract occurrence def AnticipatedCapability :> Capability;
    occurrence def SustainmentFeasibility :> AnticipatedCapability;
    occurrence def AdvisoryProvenance :> AnticipatedCapability;
    occurrence def OfflineIntentReconciliation :> AnticipatedCapability;
    occurrence def FailureReporting :> AnticipatedCapability;
    occurrence def SafetyInterlockRefusal :> AnticipatedCapability;
    occurrence def DisagreementDetection :> AnticipatedCapability;
}
```

Model: [CapabilityTaxonomy](../../model/openddil.sysml)

A capability here is something a deployment can be phased on and shown working. A rule or a mechanism that every capability obeys is not one: rules are in [Operational-Constraints](../../views/Op-Ct.md), and [Architecture-Traceability](../../views/Am-Tr.md) shows where each decision record is cited. Operator interaction holds DeclaredCards, and the task stream and My reports from ADR-0058's first increment join it when they are specified. InformationPresentation stays under condition monitoring, as ISO 13374's presentation block.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| DataAcquisition, DataManipulation, StateDetection (ISO 13374 blocks 1 to 3) | [ADR-0038](../../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Built |
| DataAcquisition: each external feed is its own ingestion sidecar, onto one common schema | [ADR-0010](../../../../decisions/ADR-0010-feed-integration-strategy.md) | Accepted | Not stated |
| HealthAssessment (block 4) | [ADR-0038](../../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Partial |
| PrognosticAssessment (block 5): the mechanism, not a prediction | [ADR-0038](../../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Partial |
| AdvisoryGeneration (block 6): constraining factors only, no condition advice; the configuration analyzer is under ConfigurationStatusAccounting | [ADR-0038](../../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Partial |
| InformationPresentation | [ADR-0038](../../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Built |
| DeclaredAnalyticUnits: ADR-0034's first engine slice, a runner that loads the units a deployment declares | [ADR-0057](../../../../decisions/ADR-0057-declared-analytic-units-adr0034-first-engine-slice.md) | Proposed | Partial |
| HierarchicalAggregation | [ADR-0022](../../../../decisions/ADR-0022-hierarchical-aggregation-is-the-architecture.md) | Accepted | Declared |
| TierLocalDecision | [Roadmap note](../../../../decisions/ROADMAP-2026-10-29-isolation-increments.md), [ADR-0029](../../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Built |
| TierLocalSignIn, OneSession | [ADR-0045](../../../../decisions/ADR-0045-per-tier-identity-realm-replicas.md) | Accepted | Design only |
| TierLocalMaintenanceChain | [ADR-0046](../../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md), [Roadmap note](../../../../decisions/ROADMAP-2026-10-29-isolation-increments.md) | Roadmap note | Not stated |
| TierLocalWorkflow | [ADR-0034](../../../../decisions/ADR-0034-tier-analytics-are-deployment-configuration.md), [Roadmap note](../../../../decisions/ROADMAP-2026-10-29-isolation-increments.md) | Roadmap note | Not stated |
| EdgeWorkflow: workflows on the edge node keep working while the link is severed, grounded on the edge's own rows | [ADR-0031](../../../../decisions/ADR-0031-converged-edge-node-reasoning-plane-seams.md) | Accepted | Not stated |
| TacticalSustainmentCorrelation | [ADR-0039](../../../../decisions/ADR-0039-bridging-tactical-and-sustainment-planes.md) | Positioning | Nothing built |
| ConfigurationStatusAccounting | [ADR-0009](../../../../decisions/ADR-0009-configuration-management-data-model.md) | Accepted | Not stated |
| ConfigurationStatusAccounting holds the configuration analyzer, not StateDetection or AdvisoryGeneration | [ADR-0059](../../../../decisions/ADR-0059-condition-monitoring-bit-and-usage-alignment.md) | Proposed | Design only |
| ArrivalDeclaration | [ADR-0050](../../../../decisions/ADR-0050-asset-arrivals-declare-and-expect.md) | Proposed | Not stated |
| LabelledReadEnforcement | [ADR-0029](../../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Built |
| GatedRelease | [ADR-0043](../../../../decisions/ADR-0043-egress-gate-one-predicate-two-subjects.md) | Proposed | Measured under compose |
| GatedIntake | [ADR-0046](../../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Not stated |
| DeclaredLabelDimensions: a label is a set of declared dimensions, generalising ADR-0029's two nation fields | [ADR-0055](../../../../decisions/ADR-0055-a-label-is-a-set-of-declared-dimensions.md) | Proposed | Design only |
| OneIdentityPerThing: every thing has one identity, and every other id is an alias that resolves to it | [ADR-0056](../../../../decisions/ADR-0056-one-identity-per-thing-every-other-id-is-an-alias.md) | Proposed | Design only |
| DeclaredCards: a card is a declaration, one grammar across both UIs | [ADR-0058](../../../../decisions/ADR-0058-a-card-is-a-declaration-one-grammar-across-both-uis.md) | Proposed | Design only |
| SustainmentFeasibility, AdvisoryProvenance | [ADR-0038](../../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Anticipated | Nothing built |
| OfflineIntentReconciliation | [ADR-0040](../../../../decisions/ADR-0040-offline-sustainment-and-intent-reconciliation.md), [ADR-0042](../../../../decisions/ADR-0042-intent-custody-retention-and-multi-tier-reconciliation.md) | Accepted | Nothing built |
| FailureReporting | [ADR-0051](../../../../decisions/ADR-0051-failure-records-for-fracas.md) | Accepted | Design only |
| SafetyInterlockRefusal | [ADR-0052](../../../../decisions/ADR-0052-safety-states-and-release-interlocks.md) | Accepted | Design only |
| DisagreementDetection | [ADR-0053](../../../../decisions/ADR-0053-logistics-cyber-detection-as-surfaced-disagreement.md) | Accepted | Design only |

ADR-0042 is Proposed where ADR-0040 is Accepted. The row carries the stronger mark because ADR-0040 is the decision and ADR-0042 extends it.
