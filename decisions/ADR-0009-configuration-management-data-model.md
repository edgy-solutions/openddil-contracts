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

## Addendum (2026-05-13) — Manual discrepancies are a separate list

Inside the `cm-service` persistence model, `AsMaintainedRecord` carries
**two** discrepancy lists rather than one:

- `discrepancies` — analyzer-computed entries, rebuilt from scratch on
  every reanalysis cycle (`_reanalyze` clears and re-populates from the
  current `installed`/`mod_status` state against the baseline).
- `manual_discrepancies` — entries raised by humans or external systems
  via `CmEvent.ManualDiscrepancyRaised`. These persist across reanalysis
  cycles because the analyzer has no way to re-derive them (they reflect
  human judgment, not baseline-vs-installed math).

The two lists are merged into the protobuf `ConfigurationDiscrepancy[]`
field at the serialization boundary (`store.record_to_proto`). On the
wire and to downstream consumers, there is one unified list keyed by
`discrepancy_id`. Manual entries are still identifiable by their
`discrepancy_id` (`uuid5` over a seed beginning with `"manual|"`), so
consumers that want to distinguish source can — but most don't need to.

**Why this matters for future engineers**: it is tempting to "simplify"
by collapsing `manual_discrepancies` back into `discrepancies`. **Do not.**
Reanalysis would clobber every manual entry. The separation is deliberate
and is verified by `test_manual_discrepancy_survives_reanalysis`,
`test_critical_manual_discrepancy_escalates_overall_status`, and
`test_manual_discrepancy_appears_in_wire_form` in
`openddil-cm-service/src/tests/test_asset_cm.py`. A future
`clear_manual_discrepancy(discrepancy_id)` handler (planned for
Phase 3.5) is the right way to remove manual entries — not by letting
the analyzer wipe them on the next observation.

## Alignment declared (ADR-0038 C1 intake), 2026-10-14

**By concept name only.** No schema text, element names or code lists from either specification are copied into the
contracts.

| field (contracts) | aligned to | concept named |
|---|---|---|
| `AsMaintainedConfiguration` (`installed`, `mod_status`, `discrepancies`, `overall_status`, `baseline_id`, `lifecycle`), `ConfigurationStatus`, `ModComplianceState` | EIA-649; NATO ACMP-2000 | configuration status accounting |
| `ConfigurationBaseline`, `AuthorizedCi`, `ModificationRequirement`, `ConfigurationItem` | EIA-649; NATO ACMP-2000 | configuration status accounting |
| `ConfigurationDiscrepancy`, `CmEvent` and its event types | EIA-649; NATO ACMP-2000 | configuration status accounting |
| `AssetIdentity.configuration_baseline`, `AssetLogisticsStatus.cm_baseline_id`, the asset-cm-state driver of `RegionFleetSummary` | EIA-649; NATO ACMP-2000 | configuration status accounting |

**The reference is the as-maintained baseline.** Every status is a statement about one asset's as-maintained
configuration against the baseline it is assigned. An asset with no baseline is not assessed; an asset with a baseline and
no assessment has not reported. The two are different facts and are shown differently.

**The display words are status accounting words.** The surface says *conforms* or *deviates* (*deviates: critical* for a
critical discrepancy). It never says *mission capable*: CM status and operational severity are separate axes
(ADR-0035, class 6). The stored `CONFIG_STATUS_*` tokens are unchanged. The pipeline reads them by name, so a rename is a
migration and is not part of this declaration.

The field names are OpenDDIL-local, with a declared alignment intent. Binding them to named elements is owed before any
field is frozen. The intent declarations already made elsewhere stay as they are: ADR-0046 (ASD S5000F, MIMOSA OSA-CBM)
and ADR-0044 (ASD S5000F).
