# Operational-Constraints (Op-Ct)

The rules this architecture keeps. The first table holds rules about what the running system may do. The second and third hold rules about how present work is written, so that it does not harden something a later capability needs. Each restates its record's rule, and the Sources table cites the record.

## Rules the running system keeps

| Rule | Statement |
|---|---|
| R1 | No status change is ever expressed as a delete. Withdrawal cannot be inferred from silence: an asset that goes on being quiet never becomes prunable. |
| R2 | Labels are stamped at ingress and carried. No later stage re-derives one. |
| R3 | Nothing crosses a boundary ungated, and nothing that crosses is described as integrated until a conformance suite says so. |
| R4 | Nothing in the analytics or process plane asserts that a course of action is supportable, advisable or executable. It may compute sufficiency against a stated demand and report the margin and the binding constraint. |
| R5 | An arrival is never matched automatically. A person ends every arrival state. |

## Rules for work on the tier hierarchy

These bind until the generalisation backlog is worked. They constrain how work is written, not whether it ships.

| Rule | Statement |
|---|---|
| H1 | Do not state tier-kind laws. Which tiers get a component is deployment configuration, and the framework rule is stated apart from the instantiation. |
| H2 | Do not add new named-tier components. New work extends the node kit or is parameterised by tier. |
| H3 | Do not deepen the `edge_id`/`region_id` assumption. New schema, contracts or code that needs a position in the hierarchy is reviewed against hierarchy-path addressing. |
| H4 | Do not assume leaf-stream inputs in a new aggregation. A rollup composes over child rollups. |
| H5 | Do not assume strictly-tree data flow. The mechanisms are direction-agnostic, and only their configuration is tree-shaped today. |

## Rules for work toward the anticipated capabilities

The capabilities are anticipated and not committed. These constraints are what is accepted. The record states each one's cost today.

| Rule | Statement | Cost today, per the record |
|---|---|---|
| C1 | The detection-event envelope is not finalised in a shape that cannot carry a recommendation, a horizon or an uncertainty band. | Zero |
| C2 | The analytics registry's output-type vocabulary is open. | Zero |
| C3 | Analytics inputs are not typed as observed state only. | Zero |
| C4 | Advisory provenance does not inherit the detection stamp's shape by default. | Overdue, not pending. A unit that generates recommended actions shipped before the constraint was written, so the fix is now a change against live consumers. |
| C5 | The process plane's workflow subject is not assumed to be an asset. | Zero |
| C6 | Feasibility over rollups is rollup-of-rollups, so the composability gate binds it. | Zero, already tracked |
| C7 | R4 above. | Zero |

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| R1 | [ADR-0044](../../../decisions/ADR-0044-lifecycle-two-columns-no-deletes.md) | Proposed | Pending |
| R2 | [ADR-0029](../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Not stated |
| R3 | [Interface contracts](../../../decisions/DESIGN-2026-09-06-interface-contracts.md) | Design note | Nothing built |
| R4, and C1 to C7 | [ADR-0038](../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Not stated |
| R5 | [ADR-0050](../../../decisions/ADR-0050-asset-arrivals-declare-and-expect.md) | Proposed | Not stated |
| H1 to H5 | [ADR-0033](../../../decisions/ADR-0033-recursive-tier-hierarchy-framework-invariant.md) | Accepted | Pending |
