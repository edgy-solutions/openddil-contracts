# Sample Fleet System: Resources-Information (Rs-If)

built on OpenDDIL 0.1.161

The information as it exists on the wire: proto contracts, ontology files, and the kinds, routes and destinations a deployment declares. Which workload writes and reads each topic is in [Resources-Connectivity](../../views/Rs-Cn.md).

## Contracts

| Artefact | Where | What it fixes |
|---|---|---|
| Proto contracts | `openddil-contracts/proto/`, 16 files and 68 messages | The tiers' wire shape. Provenance carries `originator_nation` and `releasable_to`. |
| Ontology files | `openddil-contracts/ontology/` | Identity aliases, DIS appearance and condition, entity types, platform reference and variants. {{slot:platform-variants}} |
| Contract B schema | `openddil-customer-bundle-example/conformance/contract-b/` | The catalog shape, with its validator and fixtures |
| Kinds | `<Kind>.schema.json`, in the deployment overlay | One schema per kind. `x-openddil` points at its key, label, owning tier, trigger, episode, observed-at, sources and picture. {{slot:kinds}} |
| Routes | Deployment overlay | Source topic, destination, sink topic and kind. {{slot:routes}} |
| Destinations | Deployment overlay | Display name, nations, accepts, asserted by and on. {{slot:destinations}} |

One topic is not protobuf: `asset-cm-state` stays JSON on the wire, and the projector is configured to decode it as JSON.

Two changes are designed and not built. Each alias becomes a row naming its scheme, value, authority and validity, bound to one identity; the lookup key is an index, never the identity. In the store, every table that carries the two label columns also carries `label_key` and `label`, computed from them at every write. The label is not on the wire: provenance field 11 stays reserved.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| Labels are carried on provenance | [ADR-0029](../../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md) | Accepted | Built |
| Kinds, routes and destinations live in the overlay | [ADR-0046](../../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Declared |
| Aliases are rows bound to one identity; the lookup key is an index | [ADR-0056](../../../../decisions/ADR-0056-one-identity-per-thing-every-other-id-is-an-alias.md) | Proposed | Design only |
| `label_key` and `label` beside the two columns, computed in the store | [Compatibility slice](../../../../decisions/DESIGN-2026-11-06-adr0055-compatibility-slice.md) | Design note | Design only |
| `asset-cm-state` stays JSON | [ADR-0018](../../../../decisions/ADR-0018-asset-cm-state-wire-format-inconsistency.md) | Accepted | Not stated |
| Contract B's catalog shape | [Interface contracts](../../../../decisions/DESIGN-2026-09-06-interface-contracts.md) | Design note | Nothing built |
