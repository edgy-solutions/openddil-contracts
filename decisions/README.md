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
- [ADR-0024: Multi-Cluster Faust Aggregator Pattern](ADR-0024-multi-cluster-faust-aggregator-pattern.md) — Phase 6b §B implementation pattern: Worker-composition of one aggregator App + N stateless source Apps + per-region fan-in topic + the heterogeneous-source-cluster rule (uniform wrap-and-republish for ALL source clusters, including same-broker ones, to keep the Tables partition invariant trivially satisfied). Captures the empirical findings — `faust.App(broker=[...])` doesn't multi-cluster, `faust.Worker(primary, *secondaries)` does, PartitionsMismatch from a partition-count-heterogeneous Table source-set is non-obvious until live (2026-05-17, Status: Accepted)
- [ADR-0025: Build-Pass Deployment Verification Discipline](ADR-0025-build-pass-deployment-verification-discipline.md) — Phase 6c.1 build-pass methodology lesson: observable-end-state verification must include BOTH (a) automated tests passing AND (b) confirmation the live deployment is running the new code. Hot-reload bind-mount services pick up source on restart; static-build services (frontend) require explicit `build` + `up -d --force-recreate` + grep the served artifact. Caught live: test_47/test_48 PASSED against the Shape API while the user's browser still showed the pre-§C.1 frontend because the image wasn't rebuilt. Generalizes the eye-candy lesson one layer down — automated tests prove the code path, not the deployment (2026-05-17, Status: Accepted)
- [ADR-0026: OperationalState — orthogonal-axis posture model](ADR-0026-operational-state-orthogonal-axis-model.md) — `EntityTelemetryEvent.operational_state` decomposes into three independent axes (PowerState × FunctionalMode × HealthState) plus discrete activity cues, replacing per-source combined-state enums. Lets DIS / AFSim / VRForces / customer adapters map each source's native vocabulary onto the same canonical Silver shape; downstream rendering doesn't care which adapter produced the event (2026-05-27, Status: Accepted)
- [ADR-0027: Runtime-configurable tunables via shared settings table](ADR-0027-runtime-configurable-tunables-via-settings-table.md) — design captured for an HQ-postgres `runtime_settings` table that lets operators adjust logistics-fusion thresholds + similar scalars without pod restarts. Implementation deferred until a second tunable demands it — currently only `ammo_low_count` has surfaced as a runtime-change request, and the env-var override path covers it. Pairs with ADR-0028 as a "small shared registry, pub/sub invalidation, every consumer caches" pattern (2026-06-04, Status: Proposed, deferred)
- [ADR-0028: Centralized asset_registry for edge/region lineage](ADR-0028-centralized-asset-registry-edge-region-lineage.md) — single source of truth for asset→edge_id→region_id mapping on HQ postgres, written by one `asset-registry-service`, read by all consumers (cm-service, logistics-fusion, faust-regional source-app, projector). Static warfighter assignment wins over derived position/connection-based; divergence between assignment and observation is surfaced as a `cm.edge_divergent` constraining factor instead of silently overridden. Replaces the three-different-derivation-paths-across-three-services state that silently dropped 100% of cm-service + logistics-fusion events at the source-app's positive-region filter (2026-06-04, Status: Proposed)

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
