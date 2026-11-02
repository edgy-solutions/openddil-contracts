# AV-1 Overview and Summary Information (DoDAF 2.02)

From UAF 1.2 Summary-Overview (Sm-Ov).

The architecture of {{slot:deployment-name}}, which supports {{slot:mission-thread}}.

OpenDDIL reads a fleet's tactical signals and its sustainment records, correlates them, and keeps doing so when a tier is cut off from the tier above it. It correlates and does not transact: both provenances are kept, and the system of record stays the system of record.

Three decisions shape every other view:

- The tiers form a hierarchy in which each tier does its own stream processing, and the depth of that hierarchy is deployment configuration.
- Each uplink exists and can be severed. Severing it stops data, and the backlog is visible as bridge-group lag.
- Nothing crosses a boundary ungated, and nothing that crosses is described as integrated until a conformance suite says so.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| Correlate between the tactical and sustainment planes, keeping both provenances | [ADR-0039](../../../../decisions/ADR-0039-bridging-tactical-and-sustainment-planes.md) | Positioning | Nothing built |
| Hierarchical aggregation is the architecture | [ADR-0022](../../../../decisions/ADR-0022-hierarchical-aggregation-is-the-architecture.md) | Accepted | Declared |
| Unbounded, recursive tier hierarchy | [ADR-0033](../../../../decisions/ADR-0033-recursive-tier-hierarchy-framework-invariant.md) | Accepted | Pending |
| One severable hop per uplink | [ADR-0021](../../../../decisions/ADR-0021-edge-hq-topology-is-load-bearing.md) | Accepted | Built |
| Nothing crosses ungated; integration claims wait for a conformance suite | [Interface contracts](../../../../decisions/DESIGN-2026-09-06-interface-contracts.md) | Design note | Not stated |
| Operator surfaces state what they do not know | [ADR-0035](../../../../decisions/ADR-0035-information-honesty-operator-surfaces.md) | Standing | Not stated |
| Verification evidence is a deliverable | [ADR-0037](../../../../decisions/ADR-0037-verification-evidence-is-a-deliverable.md) | Standing | Not stated |

## Measured results

{{slot:measured-results}}

No measured figure for a deployment appears in these views until this slot is filled.
