# Sample Fleet System: Operational-Connectivity (Op-Cn)

built on OpenDDIL 0.1.161

Who needs what from whom. This view states the needs. The topics and workloads that carry them are in [Resources-Connectivity](../../views/Rs-Cn.md).

| Need | From | To | Carries | Condition when severed |
|---|---|---|---|---|
| N1 | {{slot:feeds}} | Leaf tier | Entity state, faults, configuration | Local; unaffected |
| N2 | Child tier | Parent tier | Asset state and rollups | Buffers at the child; backlog visible as lag |
| N3 | Tier | Its operators | Picture, arrivals, releasable records | Works when the tier has its own broker and store |
| N4 | Hub | {{slot:c2-system}} | Status and readiness, gated per destination | Not stated |
| N5 | Hub | {{slot:maintenance-system}} | Fault records of a declared kind, gated | Not stated |
| N6 | {{slot:maintenance-system}} | Hub | Actions of a declared kind, through intake | Not stated |
| N7 | {{slot:sustainment-system-of-record}} | Sample Fleet System | Record state, extracted | Not stated |
| N8 | Sample Fleet System | {{slot:sustainment-system-of-record}} | Intents, for the record holder to accept or refuse | Held with custody at the tier |
| N9 | Operator | Tier | Declaration of an arriving asset | Local |
| N10 | Peer tier | Peer tier | Whatever a lateral link is configured for | Deployment configuration |

"Not stated" means no decision record says what this need does under severance. The hub is where the chain runs in this pass. Moving it to each tier is roadmap increment 2. Link figures: {{slot:link-characteristics}}.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| N1: feeds enter at the tier that owns the sensor | [ADR-0030](../../../../decisions/ADR-0030-two-stage-configurable-ingress.md), [ADR-0044](../../../../decisions/ADR-0044-lifecycle-two-columns-no-deletes.md) | Accepted | Not stated |
| N2: the hop exists, can be severed and buffers | [ADR-0021](../../../../decisions/ADR-0021-edge-hq-topology-is-load-bearing.md) | Accepted | Built |
| N3: tier-local presentation | [ADR-0032](../../../../decisions/ADR-0032-tier-local-presentation-reachback-finding.md) | Accepted | Not stated |
| N4: release through the gate | [ADR-0043](../../../../decisions/ADR-0043-egress-gate-one-predicate-two-subjects.md) | Proposed | Measured under compose |
| N5, N6: release and intake by kind | [ADR-0046](../../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Not stated |
| N7, N8: Contract B reads records and writes intents | [Interface contracts](../../../../decisions/DESIGN-2026-09-06-interface-contracts.md) | Design note | Not stated |
| N8: custody of an intent across tiers | [ADR-0042](../../../../decisions/ADR-0042-intent-custody-retention-and-multi-tier-reconciliation.md) | Proposed | Nothing built |
| N9: an asset enters by a person's declaration | [ADR-0050](../../../../decisions/ADR-0050-asset-arrivals-declare-and-expect.md) | Proposed | Not stated |
| N10: lateral links | [ADR-0033](../../../../decisions/ADR-0033-recursive-tier-hierarchy-framework-invariant.md) | Accepted | Pending |
