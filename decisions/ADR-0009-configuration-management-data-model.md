# ADR-0009: Configuration Management Data Model

## Status
Accepted

## Context
OpenDDIL's customer is prioritizing Configuration Management (CM). CM in defense sustainment is distinct from CMDB/IT-CM and tracks: Configuration Items (CIs), Configuration Baselines, Modification Requirements (MWO/TCTO), As-Maintained Configuration, and Discrepancies. A robust data model is required to capture the physical state of the fleet against its authorized baseline.

## Decision
We will implement **Hardware CM and Modification CM in v1**. 
- Software/Firmware CM is deferred to v2. 
- Documentation CM and Operational CM are explicitly excluded (out of scope, owned by other program offices).

## Schema
The authoritative Protobuf schema is implemented in:

**`openddil-contracts/proto/openddil/configuration/v1/configuration.proto`**

Message families:
- `ConfigurationItem` — a discrete, serialized, trackable component (keyed by `ci_id`)
- `ConfigurationBaseline` — a versioned reference BOM for a platform variant, containing `AuthorizedCi` slots and `ModificationRequirement` directives
- `AsMaintainedConfiguration` — per-asset current state, containing `InstalledCi`, `ModCompliance`, `ConfigurationDiscrepancy`, and a rolled-up `ConfigurationStatus`
- `ConfigurationDiscrepancy` — a computed delta between as-maintained and authorized configuration

Supporting enums: `CiCategory`, `ModType`, `ComplianceCategory`, `ModComplianceState`, `DiscrepancyType`, `Severity`, `ConfigurationStatus`.

All 7 enums are referenced in message fields. No orphan enums. All `google.protobuf.Timestamp` fields use the well-known import.

## Storage Placement
- **`ConfigurationBaseline`**: Records live in a baseline registry. Initially, these will be YAML files stored in `openddil-contracts/baselines/`. Eventually, this will migrate to a dedicated baseline service.
- **`AsMaintainedConfiguration`**: Lives in a compacted Kafka topic named `asset-cm-state`, keyed by `asset_id`.
- **`ConfigurationItem`**: Lives in a compacted Kafka topic named `cm-items`, keyed by `ci_id`.

## Out-of-Scope Clarifications
- OpenDDIL **will not** implement IUID (Item Unique Identification) registry sync.
- OpenDDIL **will not** own the authoritative source of NSN data.
- OpenDDIL **will not** replace existing CM authorities (TACOM, AMCOM, JPO, etc.). It consumes their baselines and reports compliance against them.
