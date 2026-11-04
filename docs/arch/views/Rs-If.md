# Resources-Information (Rs-If)

The information as it exists on the wire: proto contracts, ontology files, and the kinds, routes and destinations a deployment declares. Which workload writes and reads each topic is in [Resources-Connectivity](Rs-Cn.md).

## Contracts

| Artefact | Where | What it fixes |
|---|---|---|
| Proto contracts | `openddil-contracts/proto/`, 16 files and 68 messages | The tiers' wire shape. Provenance carries `originator_nation` and `releasable_to`. |
| Ontology files | `openddil-contracts/ontology/` | Identity aliases, DIS appearance and condition, entity types, platform reference and variants. {{slot:platform-variants}} |
| Contract B schema | `openddil-customer-bundle-example/conformance/contract-b/` | The catalog shape, with its validator and fixtures |
| Kinds | `<Kind>.schema.json`, in the deployment overlay | One schema per kind. `x-openddil` points at its key, label, owning tier, trigger, episode, observed-at, sources and picture. {{slot:kinds}} |
| Routes | Deployment overlay | Source topic, destination, sink topic and kind. {{slot:routes}} |
| Destinations | Deployment overlay | Display name, nations, accepts, asserted by and on. {{slot:destinations}} |

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| Labels are carried on provenance | [ADR-0029](../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Built |
| Kinds, routes and destinations live in the overlay | [ADR-0046](../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Declared |
| Contract B's catalog shape | [Interface contracts](../../../decisions/DESIGN-2026-09-06-interface-contracts.md) | Design note | Not stated |
