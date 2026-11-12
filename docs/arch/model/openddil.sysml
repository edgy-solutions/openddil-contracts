// The structural model behind the architecture views, in SysML v2 textual
// notation. Views pull a package in with a marker comment, so each statement
// lives here once. Decision and evidence marks live in the views, because they
// change with the decision records and the model does not.

package OpenDDIL {

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

    package OperationalNodes {
        doc /* ADR-0033: root, intermediate and leaf are positions in a tree, not kinds of tier. Names come from the deployment. */

        abstract part def OperationalPerformer;

        part def TierNode :> OperationalPerformer {
            ref part parent : TierNode[0..1];
            ref part children : TierNode[0..*];
            ref part lateralPeers : TierNode[0..*] {
                doc /* ADR-0033 amendment: lateral links are deployment configuration. */
            }
        }

        part def Operator :> OperationalPerformer;
        part def FeedSource :> OperationalPerformer;
        part def C2Consumer :> OperationalPerformer;
        part def SustainmentRecordHolder :> OperationalPerformer;
        part def ExternalDestination :> OperationalPerformer;
    }

    package ResourceKit {
        doc /* ADR-0033 node kit. Every member but the aggregator is optional, under the dependency rules below. */

        abstract part def KitMember;
        part def Broker :> KitMember;
        part def Aggregator :> KitMember;
        part def Projector :> KitMember;
        part def Store :> KitMember;
        part def Presentation :> KitMember;
        part def PolicySidecar :> KitMember;

        part def Uplink {
            doc /* ADR-0021: one bridge, one consumer group and one severable proxy per child. */
            part bridge : KitMember;
            part proxy : KitMember;
        }

        part def Node {
            part broker : Broker[0..1];
            part aggregator : Aggregator[1];
            part projector : Projector[0..1];
            part store : Store[0..1];
            part presentation : Presentation[0..1];
            part policySidecar : PolicySidecar[0..1];
            part uplink : Uplink[0..1];

            doc /* Dependency rules, ADR-0033: a store needs a projector, presentation needs a store, and presentation that has to survive severance needs its own broker. */
        }

        part def EgressGate;
        part def EgressAssembler;
        part def EgressForwarder;
        part def EgressIntake;

        part def EgressChain {
            doc /* ADR-0046: at the hub in this pass; per tier is roadmap increment 2. */
            part assembler : EgressAssembler[0..1];
            part gate : EgressGate[1];
            part forwarder : EgressForwarder[1];
            part intake : EgressIntake[0..1];
        }
    }

    package Information {
        doc /* Logical entities only. Field names are local to this architecture; the wire shape is in the proto contracts. */

        item def Asset {
            doc /* ADR-0047: the id is opaque inside the system; every boundary has a mapper. */
            attribute operationalStatus;
            attribute reportingStatus;
            attribute postureStatus;
        }
        item def Provenance {
            attribute originatorNation;
            attribute releasableTo[0..*];
            attribute originNode;
        }
        item def OperationalState {
            doc /* ADR-0026: orthogonal axes. */
            attribute powerState;
            attribute functionalMode;
            attribute healthState;
            attribute activelyReceiving;
            attribute activelyTransmitting;
        }
        item def ConfigurationItem;
        item def DiscrepancyEpisode;
        item def ArrivalDeclaration;
        item def FieldingRecord;
        item def EffectorTrack;
        item def Intent;

        item def Kind {
            doc /* ADR-0046: a kind is a schema in the deployment overlay, with pointers that say where its key and label live. */
        }
        item def Destination {
            attribute nations[0..*];
            attribute accepts[0..*];
        }
        item def DecisionRecord {
            doc /* ADR-0043 section 7: one line per record, carrying the reason. */
        }
    }

    package SecurityStructure {
        doc /* ADR-0029 and ADR-0043: one decision point, many enforcement points, and one predicate with two subjects. */

        part def PolicyDecisionPoint;
        abstract part def PolicyEnforcementPoint;
        part def ReadPathPEP :> PolicyEnforcementPoint;
        part def GatePEP :> PolicyEnforcementPoint;
        part def IntakeCheck :> PolicyEnforcementPoint;
        part def IdentityRealm {
            doc /* ADR-0045: design only. Each tier has its own issuer and keys, and the home tier holds credentials. */
        }

        abstract part def Subject;
        part def PersonSubject :> Subject;
        part def DestinationSubject :> Subject;
    }
}
