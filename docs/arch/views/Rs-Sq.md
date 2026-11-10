# Resources-Sequences (Rs-Sq)

The release and intake exchanges of [Operational-Sequences](Op-Sq.md), between workloads. The function numbers are those of [Resources-Processes](Rs-Pr.md). Every arrow into or out of a broker is a topic. The rendered topic names are in [Resources-Connectivity](Rs-Cn.md).

## Release

```mermaid
sequenceDiagram
    participant CM as Configuration service
    participant B as Hub broker
    participant A as Assembler F11
    participant G as Gate F12
    participant F as Forwarder F13
    participant D as Destination
    CM->>B: discrepancy, on the replicated topic
    B->>A: discrepancy
    A->>A: read the picture from the store and mint the event and episode ids
    A->>B: release request, on the route's source topic
    B->>G: release request
    G->>G: schema, then accepted kinds, then the label at the kind's pointer, then decide
    G->>B: admitted record, on the route's sink topic
    G->>G: decision line, with kind and route
    B->>F: admitted record
    F->>D: HTTP POST
```

The gate's added reasons are `kind_not_accepted` and `schema_invalid`. A record that fails either is refused and logged like any other refusal. A severed tier queues at its gate's output, as any egress does.

## Intake

```mermaid
sequenceDiagram
    participant D as Destination
    participant I as Intake F14
    participant S as Hub store
    participant B as Hub broker
    participant G as Gate F12
    I->>D: GET on the poll interval
    D-->>I: artifacts of the kind
    I->>I: validate against the kind and match the answered record's label
    I->>I: resolve each approver and check it by the read path's predicate
    I->>S: artifact and local decision, in the intake table
    I->>B: admitted artifact, as a release request
    B->>G: release request, decided as above
```

The intake table holds kind, key, label, body and decision, with the owning tier as a column. Storing it at the owning tier is the design, so that a severed tier holds its own decisions. Until that lands, it does not.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| Assembler, gate and intake steps, and the intake table at the hub | [ADR-0046](../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Declared |
| Event and episode ids, both deterministic | [ADR-0046](../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Not stated |
| Gate and forwarder: one decision line per record | [ADR-0043](../../../decisions/ADR-0043-egress-gate-one-predicate-two-subjects.md) | Proposed | Measured under compose |
| Approvers decided by the read path's predicate | [ADR-0029](../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Built |
