# Resources-Taxonomy (Rs-Tx)

The resource types, what each one specialises, and where each is a part. The table is generated from package ResourceKit in [the model](../model/openddil.sysml) when the view is rendered, so it cannot drift from the model. A type the model does not define fails the render. [Resources-Structure](Rs-Sr.md) shows the same package as a structure, and [Resources-Constraints](Rs-Ct.md) holds the rules a deployment's choice of members keeps.

<!-- generated: resource-taxonomy -->

A multiplicity of `[0..1]` is a member a deployment may leave out of a tier. `[1]` is one it may not. A row that reads "multiplicity not stated" is one where the model gives none. Which members each tier carries is deployment configuration: {{slot:tier-tree}}.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| The table | [ResourceKit](../model/openddil.sysml) | Generated | Generated |
| The node kit: optional members, the aggregator universal | [ADR-0033](../../../decisions/ADR-0033-recursive-tier-hierarchy-framework-invariant.md) | Accepted | Pending |
| The egress chain: at the hub in this pass, per tier later | [ADR-0046](../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Declared |
