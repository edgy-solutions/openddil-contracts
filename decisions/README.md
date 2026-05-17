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
- [ADR-0017: UI Mock Components Must Self-Identify](ADR-0017-ui-mock-components-self-identify.md) — Phase 4b: no orphan mocks — DEMO_MOCK const + banner + comment (2026-05-14, Status: Accepted)
- [ADR-0018: asset-cm-state Wire Format Inconsistency](ADR-0018-asset-cm-state-wire-format-inconsistency.md) — Phase 4a: asset-cm-state is JSON while all other internal topics are protobuf; deliberately deferred (2026-05-14, Status: Accepted)
- [ADR-0019: Single Kafka→Postgres Projector](ADR-0019-single-kafka-postgres-projector.md) — Phase 4a: one generic config-driven projector, not per-topic services (2026-05-14)
- [ADR-0020: Prognostics Derivation Engine](ADR-0020-prognostics-derivation-stage.md) — Phase 5: derive sustainment estimates from kinematic history. No calibration oracle (Sim A is fabricated; the earlier stub's oracle claim was false) — Phase 5 demonstrates the *mechanism* on synthetic data; validation is an AFSIM/VR-Forces-gated future phase (2026-05-14, Status: Accepted)
- [ADR-0021: The Edge→HQ Topology Is Load-Bearing](ADR-0021-edge-hq-topology-is-load-bearing.md) — Phase 4c.5: the edge/HQ split is the architecture, not an implementation detail; collapsed in 4a/4b, restored in 4c.5; future simplifications must be explicit decisions (2026-05-14, Status: Accepted)
- [ADR-0022: Hierarchical Aggregation Is the Architecture](ADR-0022-hierarchical-aggregation-is-the-architecture.md) — Phase 4d: edge→regional→HQ aggregation is the architecture (and the reason for Redpanda); the current flat single-tier topology is a recorded expedient; four "do not harden the flat assumption" constraints bind all work until hierarchical restoration (2026-05-14, Status: Accepted)
- [ADR-0023: Hierarchy Restoration — Topology and Phase Plan](ADR-0023-hierarchy-restoration-topology-and-phase-plan.md) — Phase 6 plan implementing ADR-0022: 3 edges across 2 regions + new `faust-regional` aggregator + three rolled-up topics (severity counts, top-N factors, wear trends); single edge-aware projector at HQ; 6a/6b/6c/(6d) sub-phase split with an observable checkpoint per sub-phase; per-region brokers explicitly noted as a demo simplification; maintainer view becomes per-edge-scoped at 6c with a switcher and animated transition (2026-05-16, Status: Accepted)

## Phase status

Phase 4c.5 (2026-05-14): real DDIL edge→HQ topology — edge-hq-bridge,
toxiproxy hq-link, real bridge-group-lag buffer readout. Pending live
sever/restore verification.
Phase 4c (2026-05-14): three role-aware views (maintainer / regional /
HQ) wired to real pipeline shapes.
Phase 4b complete (2026-05-14): edge-view repair — simulator removed,
ElectricSQL shape hooks, App.tsx rewired to real pipeline data.
Phase 4a complete (2026-05-14): single-region Postgres read-model tables +
`openddil-projector` (Kafka→Postgres) + ElectricSQL wiring, verified live.
Phase 3.5 complete (2026-05-13): Sim-A RabbitMQ ingest + logistics fusion +
System B AMQP egress, all verified live. See
[openddil-demo/docs/walkthrough.md](../../openddil-demo/docs/walkthrough.md)
for the end-to-end architecture.
