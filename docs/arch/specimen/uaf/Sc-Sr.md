# Sample Fleet System: Security-Structure (Sc-Sr)

built on OpenDDIL 0.1.161

One decision point per tier, and enforcement wherever data leaves a tier's custody. Labels come from {{slot:coalition-nations}}. Classification: {{slot:classification-scheme}}. Issuers: {{slot:idp-issuer}}.

```sysml
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
```

Model: [SecurityStructure](../../model/openddil.sysml)

```mermaid
flowchart TB
    subgraph tier["Each tier"]
        pdp["Policy decision point<br/>local authorizer, policy as bundles"]
        read["Read-path enforcement point"]
        realm["Identity realm<br/>own issuer and keys (design only)"]
        read --> pdp
        realm -. "asserts entitlements" .-> read
    end
    subgraph hub["Hub, this pass"]
        gate["Egress gate"]
        intake["Egress intake"]
        hpdp["Policy decision point"]
        gate --> hpdp
        intake --> hpdp
    end
    person["Person subject"] --> read
    dest["Destination subject<br/>{{slot:destinations}}"] --> gate
    bridge["Tier bridge enforcement<br/>fenced, not built"] -.-> pdp
```

The same predicate serves both subjects. A severed tier still decides and enforces, because its decision point is its own.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| One decision point, many enforcement points | [ADR-0029](../../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Built |
| A decision point at each tier | [Roadmap note](../../../../decisions/ROADMAP-2026-10-29-isolation-increments.md) | Roadmap note | Built |
| Read-path enforcement (slice 1) | [ADR-0029](../../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Built |
| Tier-bridge enforcement (slice 3) | [ADR-0029](../../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Fenced |
| One predicate with the destination as a second subject | [ADR-0043](../../../../decisions/ADR-0043-egress-gate-one-predicate-two-subjects.md) | Proposed | Measured under compose |
| A tier realm with its own issuer and keys, credentials at the home tier | [ADR-0045](../../../../decisions/ADR-0045-per-tier-identity-realm-replicas.md) | Accepted | Design only |
| Classification is fenced from the gate's decision | [ADR-0043](../../../../decisions/ADR-0043-egress-gate-one-predicate-two-subjects.md) | Proposed | Fenced |
