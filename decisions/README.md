# OpenDDIL Architectural Decision Records (ADRs)

This directory contains the Architectural Decision Records for the OpenDDIL project.

## Index

- [ADR-0009: Configuration Management Data Model](ADR-0009-configuration-management-data-model.md)
- [ADR-0010: Feed Integration Strategy](ADR-0010-feed-integration-strategy.md)
- [ADR-0011: Strategic Sustainment Tool Positioning](ADR-0011-strategic-sustainment-tool-positioning.md)
- [ADR-0013: Physical Quantity Consistency](ADR-0013-physical-quantity-consistency.md) — extends ADR-0007 across the whole Silver schema (2026-05-12, clean-break migration)
- [ADR-0014: Restate vs Faust Placement](ADR-0014-restate-vs-faust-placement.md) — when to use each stream engine, and why (2026-05-12)
- [ADR-0015: Identity Resolution Asymmetry](ADR-0015-identity-resolution-asymmetry.md) — stub for the DIS-bypasses-alias-rewrite issue, to be revisited when the resolver service is built (2026-05-13, Status: Proposed)
- [ADR-0016: Platform Variant Reconciliation](ADR-0016-platform-variant-reconciliation.md) — Phase 3.5: ADR-0010 generalized to platform_variant identifiers (2026-05-13)
- [ADR-0018: asset-cm-state Wire Format Inconsistency](ADR-0018-asset-cm-state-wire-format-inconsistency.md) — Phase 4a: asset-cm-state is JSON while all other internal topics are protobuf; deliberately deferred (2026-05-14, Status: Accepted)
- [ADR-0019: Single Kafka→Postgres Projector](ADR-0019-single-kafka-postgres-projector.md) — Phase 4a: one generic config-driven projector, not per-topic services (2026-05-14)

## Phase status

Phase 4a complete (2026-05-14): single-region Postgres read-model tables +
`openddil-projector` (Kafka→Postgres) + ElectricSQL wiring, verified live.
Phase 3.5 complete (2026-05-13): Sim-A RabbitMQ ingest + logistics fusion +
System B AMQP egress, all verified live. See
[openddil-demo/docs/walkthrough.md](../../openddil-demo/docs/walkthrough.md)
for the end-to-end architecture.
