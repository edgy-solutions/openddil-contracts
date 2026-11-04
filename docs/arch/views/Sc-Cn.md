# Security-Connectivity (Sc-Cn)

What is asserted across each boundary, and who stands behind it.

| Boundary | Crossing | Asserted | Enforced by | Fails |
|---|---|---|---|---|
| Person to tier | A read | Entitlements, from {{slot:idp-issuer}} | Read-path enforcement point | Closed |
| Tier to destination | A released record | The destination's nations and accepted kinds, from the registry: {{slot:destinations}} | Egress gate, per route: {{slot:routes}} | Closed, and logged |
| Destination to tier | A taken-in record | Label equality and entitled approvers: {{slot:approval-authorities}} | Egress intake | Closed, and logged |
| Child tier to parent tier | A bridged topic | Labels stamped at ingress travel with the record | Nothing yet: slice 3 is fenced | Not enforced |
| Tier to tier | A person's session | Trust between realms; a revocation is bounded by the link | Designed, not built | Not built |

The child-to-parent row is the plain gap. Labels cross an uplink carried on the record, and no enforcement point sits on the hop.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| Entitlements are asserted | [ADR-0029](../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Built |
| Label first, enforce second | [ADR-0029](../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Built |
| Egress enforcement at the gate; fails closed and loud | [ADR-0043](../../../decisions/ADR-0043-egress-gate-one-predicate-two-subjects.md) | Proposed | Measured under compose |
| Destination registry | [ADR-0046](../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Declared |
| Intake checks | [ADR-0046](../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Not stated |
| Bridge enforcement | [ADR-0029](../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Fenced |
| Revocation bounded by link; brokering parent | [ADR-0045](../../../decisions/ADR-0045-per-tier-identity-realm-replicas.md) | Accepted | Design only |
