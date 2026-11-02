# Resources-Connectivity (Rs-Cn)

Which resource talks to which, and across what boundary. The row-by-row flows are generated from a bundle and live in [Resources-Information](Rs-If.md). Link figures: {{slot:link-characteristics}}. Severance results: {{slot:severance-test-results}}.

| | Broker | Aggregator | Projector | Store | Presentation | Bridge | Gate |
|---|---|---|---|---|---|---|---|
| **Ingress** | writes | | | | | | |
| **Broker** | | feeds | feeds | | | feeds | feeds |
| **Aggregator** | writes | | | | | | |
| **Projector** | | | | writes | | | |
| **Store** | | | | | feeds, through the read path | | |
| **Bridge** | writes parent's, across the proxy | | | | | | |
| **Gate** | writes sink topic | | | | | | |

## Boundary interfaces

| Interface | Direction | Peer | Transport | Contract |
|---|---|---|---|---|
| Ingress | In | {{slot:feeds}} | {{slot:ingest-formats}} | Definition file for each format |
| Uplink | Child to parent | Parent tier | Kafka protocol through a proxy | The bridge's topic list |
| Contract A | Out | {{slot:c2-system}} | Thin egress connector | Open status vocabulary |
| Contract B read | In | {{slot:sustainment-system-of-record}} | Extraction from a readable SQL source | Catalog shape, with a conformance suite |
| Contract B write | Out | {{slot:sustainment-system-of-record}} | Intents | Propose only: the system of record disposes |
| Release | Out | {{slot:destinations}} | HTTP POST by the forwarder | A kind's schema |
| Intake | In | {{slot:destinations}} | Polled over HTTP; callback later | A kind's schema |

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| Ingress classes and definition files | [ADR-0030](../../../decisions/ADR-0030-two-stage-configurable-ingress.md) | Accepted | Not stated |
| Uplink through a severable proxy; severing it really stops data | [ADR-0021](../../../decisions/ADR-0021-edge-hq-topology-is-load-bearing.md) | Accepted | Built |
| Contract A | [Interface contracts](../../../decisions/DESIGN-2026-09-06-interface-contracts.md) | Design note | Not stated |
| Contract B | [Interface contracts](../../../decisions/DESIGN-2026-09-06-interface-contracts.md) | Design note | Not stated |
| Release and intake at the hub | [ADR-0046](../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Not stated |
| Cursor-on-target bridge | [CoT bridge design](../../../decisions/DESIGN-2026-10-01-cot-bridge.md) | Design note | Not stated |
| Member-to-member flows in the matrix | [ADR-0033](../../../decisions/ADR-0033-recursive-tier-hierarchy-framework-invariant.md) | Accepted | Declared |
