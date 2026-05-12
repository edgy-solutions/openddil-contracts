# ADR-0009: Configuration Management Data Model

## Status
Proposed

## Context
OpenDDIL's customer is prioritizing Configuration Management (CM). CM in defense sustainment is distinct from CMDB/IT-CM and tracks: Configuration Items (CIs), Configuration Baselines, Modification Requirements (MWO/TCTO), As-Maintained Configuration, and Discrepancies. A robust data model is required to capture the physical state of the fleet against its authorized baseline.

## Decision
We will implement **Hardware CM and Modification CM in v1**. 
- Software/Firmware CM is deferred to v2. 
- Documentation CM and Operational CM are explicitly excluded (out of scope, owned by other program offices).

## Schema
The following Protobuf message families and supporting enums will be implemented to support the CM data model:

```protobuf
syntax = "proto3";

package openddil.configuration.v1;

// Supporting Enums
enum CiCategory {
  CI_CATEGORY_UNSPECIFIED = 0;
  CI_CATEGORY_SYSTEM = 1;
  CI_CATEGORY_SUBSYSTEM = 2;
  CI_CATEGORY_COMPONENT = 3;
}

enum ModType {
  MOD_TYPE_UNSPECIFIED = 0;
  MOD_TYPE_MWO = 1; // Modification Work Order
  MOD_TYPE_TCTO = 2; // Time Compliance Technical Order
  MOD_TYPE_ECP = 3; // Engineering Change Proposal
}

enum ComplianceCategory {
  COMPLIANCE_CATEGORY_UNSPECIFIED = 0;
  COMPLIANCE_CATEGORY_MANDATORY = 1;
  COMPLIANCE_CATEGORY_OPTIONAL = 2;
}

enum ModComplianceState {
  MOD_COMPLIANCE_STATE_UNSPECIFIED = 0;
  MOD_COMPLIANCE_STATE_NOT_APPLICABLE = 1;
  MOD_COMPLIANCE_STATE_PENDING = 2;
  MOD_COMPLIANCE_STATE_COMPLIED = 3;
  MOD_COMPLIANCE_STATE_EXEMPT = 4;
}

enum DiscrepancyType {
  DISCREPANCY_TYPE_UNSPECIFIED = 0;
  DISCREPANCY_TYPE_MISSING_CI = 1;
  DISCREPANCY_TYPE_UNAUTHORIZED_CI = 2;
  DISCREPANCY_TYPE_MOD_OVERDUE = 3;
}

enum Severity {
  SEVERITY_UNSPECIFIED = 0;
  SEVERITY_MINOR = 1;
  SEVERITY_MAJOR = 2;
  SEVERITY_CRITICAL = 3;
  SEVERITY_GROUNDING = 4;
}

enum ConfigurationStatus {
  CONFIG_STATUS_UNSPECIFIED = 0;
  CONFIG_STATUS_AUTHORIZED = 1;
  CONFIG_STATUS_DISCREPANT = 2;
}

// Core Messages
message ConfigurationItem {
  string ci_id = 1;
  string part_number = 2;
  string nsn = 3;
  string nomenclature = 4;
  CiCategory category = 5;
}

message AuthorizedCi {
  string ci_id = 1;
  int32 required_quantity = 2;
  bool is_mission_critical = 3;
}

message ConfigurationBaseline {
  string baseline_id = 1;
  string platform_type = 2;
  repeated AuthorizedCi authorized_cis = 3;
  int64 effective_date = 4;
}

message ModificationRequirement {
  string mod_id = 1;
  ModType mod_type = 2;
  string description = 3;
  ComplianceCategory compliance_category = 4;
  repeated string applicable_ci_ids = 5;
}

message InstalledCi {
  string ci_id = 1;
  string serial_number = 2;
  string parent_ci_id = 3;
  int64 install_date = 4;
}

message ModCompliance {
  string mod_id = 1;
  ModComplianceState state = 2;
  int64 compliance_date = 3;
}

message AsMaintainedConfiguration {
  string asset_id = 1;
  string baseline_id = 2;
  ConfigurationStatus status = 3;
  repeated InstalledCi installed_cis = 4;
  repeated ModCompliance mod_compliance_status = 5;
  int64 last_updated = 6;
}

message ConfigurationDiscrepancy {
  string discrepancy_id = 1;
  string asset_id = 2;
  DiscrepancyType type = 3;
  Severity severity = 4;
  string description = 5;
  string related_ci_id = 6;
  string related_mod_id = 7;
  int64 detected_at = 8;
}
```

## Storage Placement
- **`ConfigurationBaseline`**: Records live in a baseline registry. Initially, these will be YAML files stored in `openddil-contracts/baselines/`. Eventually, this will migrate to a dedicated baseline service.
- **`AsMaintainedConfiguration`**: Lives in a compacted Kafka topic named `asset-cm-state`, keyed by `asset_id`.
- **`ConfigurationItem`**: Lives in a compacted Kafka topic named `cm-items`, keyed by `ci_id`.

## Out-of-Scope Clarifications
- OpenDDIL **will not** implement IUID (Item Unique Identification) registry sync.
- OpenDDIL **will not** own the authoritative source of NSN data.
- OpenDDIL **will not** replace existing CM authorities (TACOM, AMCOM, JPO, etc.). It consumes their baselines and reports compliance against them.
