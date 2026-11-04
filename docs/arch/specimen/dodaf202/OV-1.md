# Sample Fleet System: OV-1 High Level Operational Concept Graphic (DoDAF 2.02)

built on OpenDDIL 0.1.161

From UAF 1.2 Operational-Taxonomy (Op-Tx).

The kinds of performer, and the concept in one picture: {{slot:mission-thread}}, among {{slot:coalition-nations}}.

```mermaid
flowchart TB
    feeds["Feed sources<br/>{{slot:ingest-formats}}"] --> leaf["Leaf tiers<br/>{{slot:edge-sites}}"]
    leaf -- "severable uplink" --> mid["Intermediate tiers<br/>{{slot:regional-nodes}}"]
    mid -- "severable uplink" --> root["Root tier<br/>{{slot:root-node}}"]
    leaf -- "severable uplink" --> root
    ops["Operators<br/>{{slot:operator-roles}}"] --- leaf
    ops --- mid
    ops --- root
    root -- "status, gated" --> c2["C2 picture<br/>{{slot:c2-system}}"]
    root -- "records, gated" --> maint["Maintenance system<br/>{{slot:maintenance-system}}"]
    maint -- "actions, gated intake" --> root
    sor["Sustainment system of record<br/>{{slot:sustainment-system-of-record}}"] -- "records read" --> root
    root -- "intents, not writes" --> sor
```

Root, intermediate and leaf are positions in a tree and not kinds of tier: a tier is the same kit wherever it sits.

```sysml
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
```

Model: [OperationalNodes](../../model/openddil.sysml)

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| Root, intermediate and leaf are positions | [ADR-0033](../../../../decisions/ADR-0033-recursive-tier-hierarchy-framework-invariant.md) | Accepted | Pending |
| Three tiers aggregate in the chart today | [ADR-0023](../../../../decisions/ADR-0023-hierarchy-restoration-topology-and-phase-plan.md) | Accepted | Declared |
| A consumer takes status derived from open vocabulary (Contract A) | [Interface contracts](../../../../decisions/DESIGN-2026-09-06-interface-contracts.md) | Design note | Not stated |
| The system of record is read, and receives intents (Contract B) | [Interface contracts](../../../../decisions/DESIGN-2026-09-06-interface-contracts.md) | Design note | Not stated |
| Records go out and actions come in through one gate | [ADR-0046](../../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Not stated |
