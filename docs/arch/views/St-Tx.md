# Strategic-Taxonomy (St-Tx)

The capabilities this architecture names. The grouping is this view's; each row cites where the capability comes from. ISO 13374 is used as a reading of what exists and is not a conformance claim. In scope for this deployment: {{slot:capabilities-in-scope}}.

<!-- model: CapabilityTaxonomy -->

Model: [CapabilityTaxonomy](../model/openddil.sysml)

A capability here is something a deployment can be phased on and shown working. A rule or a mechanism that every capability obeys is not one: rules are in [Operational-Constraints](Op-Ct.md), and [Architecture-Traceability](Am-Tr.md) shows where each decision record is cited. Operator interaction holds DeclaredCards, and the task stream and My reports from ADR-0058's first increment join it when they are specified. InformationPresentation stays under condition monitoring, as ISO 13374's presentation block.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| DataAcquisition, DataManipulation, StateDetection (ISO 13374 blocks 1 to 3) | [ADR-0038 §1](../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Built |
| DataAcquisition: each external feed is its own ingestion sidecar, onto one common schema | [ADR-0010 §decision](../../../decisions/ADR-0010-feed-integration-strategy.md) | Accepted | Not stated |
| HealthAssessment (block 4) | [ADR-0038 §1](../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Partial |
| PrognosticAssessment (block 5): the mechanism, not a prediction | [ADR-0038 §3](../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Partial |
| AdvisoryGeneration (block 6): rule-based | [ADR-0038 §3](../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Partial |
| InformationPresentation | [ADR-0038 §1](../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Built |
| DeclaredAnalyticUnits: ADR-0034's first engine slice, a runner that loads the units a deployment declares | [ADR-0057 §1](../../../decisions/ADR-0057-declared-analytic-units-adr0034-first-engine-slice.md) | Proposed | Partial |
| HierarchicalAggregation | [ADR-0022 §decision](../../../decisions/ADR-0022-hierarchical-aggregation-is-the-architecture.md) | Accepted | Declared |
| TierLocalDecision | [Roadmap note](../../../decisions/ROADMAP-2026-10-29-isolation-increments.md), [ADR-0029 §6](../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Built |
| TierLocalSignIn, OneSession | [ADR-0045 §1](../../../decisions/ADR-0045-per-tier-identity-realm-replicas.md), [ADR-0045 §6](../../../decisions/ADR-0045-per-tier-identity-realm-replicas.md) | Accepted | Status line |
| TierLocalMaintenanceChain | [ADR-0046 §2](../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md), [Roadmap note](../../../decisions/ROADMAP-2026-10-29-isolation-increments.md) | Roadmap note | Not stated |
| TierLocalWorkflow | [ADR-0034 §decision](../../../decisions/ADR-0034-tier-analytics-are-deployment-configuration.md), [Roadmap note](../../../decisions/ROADMAP-2026-10-29-isolation-increments.md) | Roadmap note | Not stated |
| EdgeWorkflow: a reasoning plane on the edge node, grounded on the edge's own rows, keeps working while the link is severed | [ADR-0031 §decision](../../../decisions/ADR-0031-converged-edge-node-reasoning-plane-seams.md) | Accepted | Not stated |
| TacticalSustainmentCorrelation | [ADR-0039 §1](../../../decisions/ADR-0039-bridging-tactical-and-sustainment-planes.md) | Positioning | Status line |
| ConfigurationStatusAccounting | [ADR-0009 §decision](../../../decisions/ADR-0009-configuration-management-data-model.md) | Accepted | Not stated |
| ArrivalDeclaration | [ADR-0050 §1](../../../decisions/ADR-0050-asset-arrivals-declare-and-expect.md) | Proposed | Not stated |
| LabelledReadEnforcement | [ADR-0029 §1](../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Built |
| GatedRelease | [ADR-0043 §1](../../../decisions/ADR-0043-egress-gate-one-predicate-two-subjects.md) | Proposed | Measured under compose |
| GatedIntake | [ADR-0046 §5](../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Not stated |
| DeclaredLabelDimensions: a label is a set of declared dimensions, generalising ADR-0029's two nation fields | [ADR-0055 §1](../../../decisions/ADR-0055-a-label-is-a-set-of-declared-dimensions.md) | Proposed | Status line |
| OneIdentityPerThing: every thing has one identity, and every other id is an alias that resolves to it | [ADR-0056 §1](../../../decisions/ADR-0056-one-identity-per-thing-every-other-id-is-an-alias.md) | Proposed | Status line |
| DeclaredCards: a card is a declaration, one grammar across both UIs | [ADR-0058 §1](../../../decisions/ADR-0058-a-card-is-a-declaration-one-grammar-across-both-uis.md) | Proposed | Status line |
| SustainmentFeasibility, AdvisoryProvenance | [ADR-0038 §4](../../../decisions/ADR-0038-anticipated-capability-envelope.md), [ADR-0038 §5](../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Anticipated | Nothing built |
| OfflineIntentReconciliation | [ADR-0040 §4](../../../decisions/ADR-0040-offline-sustainment-and-intent-reconciliation.md), [ADR-0042 §1](../../../decisions/ADR-0042-intent-custody-retention-and-multi-tier-reconciliation.md) | Accepted | Status line |
| FailureReporting | [ADR-0051 §1](../../../decisions/ADR-0051-failure-records-for-fracas.md) | Accepted | Status line |
| SafetyInterlockRefusal | [ADR-0052 §2](../../../decisions/ADR-0052-safety-states-and-release-interlocks.md) | Accepted | Status line |
| DisagreementDetection | [ADR-0053 §1](../../../decisions/ADR-0053-logistics-cyber-detection-as-surfaced-disagreement.md) | Accepted | Status line |

ADR-0042 is Proposed where ADR-0040 is Accepted. The row carries the stronger mark because ADR-0040 is the decision and ADR-0042 extends it.
