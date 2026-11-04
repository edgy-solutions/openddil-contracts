# Sample Fleet System: Resources-Connectivity (Rs-Cn)

built on OpenDDIL 0.1.161

Which resource talks to which, and across what boundary. The row-by-row flows are generated from a bundle, under Data exchange below. Link figures: {{slot:link-characteristics}}. Severance results: {{slot:severance-test-results}}.

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

## Data exchange

Generated from a bundle by [`tools/data_exchange.py`](../../tools/data_exchange.py), which reads a chart render. A tier, kind or route with no row fails the generator's check. Every row is declared and none was measured; where a declaration is missing, the Exceptions section of the output names it.

Chart: openddil-demo 0.1.161
Values: tier-node-values.yaml
Values: egress-values.yaml
Declared, not measured: this table reads a render; nothing here was observed running.

### Tiers

| Tier | Broker | Exchange rows |
|---|---|---|
| edge-north | edge-north | 34 |
| edge-south | edge-south | 34 |
| hq | hq | 54 |
| region-north | none rendered | 7 |
| region-south | none rendered | 7 |

### Kinds

| Kind | Key | Label | Owning tier | Exchange rows | Destinations |
|---|---|---|---|---|---|
| FaultEvent | /picture/event_id | /picture/label | /picture/owning_tier | 2 | system:depot-ledger |
| RepairOrder | /order_id | /label | /owning_tier | 2 | system:c2-stand-in-atl |

### Destinations

| Destination | Display name | Nations | Accepts | Asserted by | Asserted on | Routes |
|---|---|---|---|---|---|---|
| system:c2-stand-in-atl | C2 stand-in (Atlantis) | ATL | RepairOrder | sample-registry | 2026-01-01 | c2, repair-orders |
| system:depot-ledger | Depot ledger | ATL, BDR | FaultEvent | sample-registry | 2026-01-01 | depot-faults |

### Exchanges

| Tier | Broker | Topic | Writer | Declared by | Consumers | Kind | Destination | Labels |
|---|---|---|---|---|---|---|---|---|
| edge-north | edge-north | asset-capability-snapshot | none declared | - | edge-hq-bridge-edge-north, tier-projector-edge-north | - | - | table asset_capability_state |
| edge-north | edge-north | asset-cm-state | tier-cm-edge-north | annotation | edge-hq-bridge-edge-north, tier-projector-edge-north | - | - | table asset_cm_state |
| edge-north | edge-north | asset-declarations | tier-declaration-intake-edge-north | annotation | edge-hq-bridge-edge-north, tier-projector-edge-north | - | - | table asset_correlation; table asset_declaration |
| edge-north | edge-north | asset-element-inventory | none declared | - | edge-hq-bridge-edge-north, tier-projector-edge-north | - | - | table inventory_items |
| edge-north | edge-north | asset-fielding | none declared | - | edge-hq-bridge-edge-north, tier-projector-edge-north | - | - | table asset_fielding |
| edge-north | edge-north | asset-logistics-status | tier-fusion-edge-north | annotation | edge-hq-bridge-edge-north, tier-projector-edge-north | - | - | table asset_logistics_status |
| edge-north | edge-north | asset-telemetry-windows | faust-edge-edge-north | annotation | edge-hq-bridge-edge-north, tier-projector-edge-north | - | - | table asset_telemetry_windows |
| edge-north | edge-north | derived-sustainment | faust-edge-edge-north | annotation | edge-hq-bridge-edge-north | - | - | not declared |
| edge-north | edge-north | effector-events | redpanda-connect-edge-north | annotation | edge-hq-bridge-edge-north, tier-projector-edge-north | - | - | table effector_launch |
| edge-north | edge-north | ingress-dis-raw | sensor-ingest-edge-north | annotation | none declared | - | - | not declared |
| edge-north | edge-north | ingress-dlq | redpanda-connect-edge-north | annotation | none declared | - | - | not declared |
| edge-north | edge-north | link-heartbeat | tier-projector-edge-north | annotation | edge-hq-bridge-edge-north | - | - | not declared |
| edge-north | edge-north | munition-tracks | redpanda-connect-edge-north | annotation | edge-hq-bridge-edge-north, tier-projector-edge-north | - | - | table munition_track |
| edge-north | edge-north | openddil-edge-north-asset_state-changelog | faust-edge-edge-north | annotation | none declared | - | - | not declared |
| edge-north | edge-north | openddil-edge-north-prognostics_accumulators-changelog | faust-edge-edge-north | annotation | none declared | - | - | not declared |
| edge-north | edge-north | raw-sensor-stream | redpanda-connect-edge-north | annotation | none declared | - | - | not declared |
| edge-north | edge-north | tactical-events | faust-edge-edge-north | annotation | edge-hq-bridge-edge-north, tier-projector-edge-north | - | - | table tactical_events |
| edge-north | edge-north | tactical-events | tier-cm-edge-north | annotation | edge-hq-bridge-edge-north, tier-projector-edge-north | - | - | table tactical_events |
| edge-north | edge-north | tactical-events | tier-fusion-edge-north | annotation | edge-hq-bridge-edge-north, tier-projector-edge-north | - | - | table tactical_events |
| edge-north | edge-north | telemetry-latest-state | faust-edge-edge-north | annotation | asset-registry-service, edge-hq-bridge-edge-north, logistics-sim, tier-projector-edge-north | - | - | table telemetry_latest_state |
| edge-north | hq | asset-capability-snapshot | edge-hq-bridge-edge-north | connect.yaml | none declared | - | - | table asset_capability_state |
| edge-north | hq | asset-cm-state | edge-hq-bridge-edge-north | connect.yaml | egress-assembler | - | - | table asset_cm_state |
| edge-north | hq | asset-declarations | edge-hq-bridge-edge-north | connect.yaml | none declared | - | - | table asset_correlation; table asset_declaration |
| edge-north | hq | asset-element-inventory | edge-hq-bridge-edge-north | connect.yaml | none declared | - | - | table inventory_items |
| edge-north | hq | asset-fielding | edge-hq-bridge-edge-north | connect.yaml | none declared | - | - | table asset_fielding |
| edge-north | hq | asset-logistics-status | edge-hq-bridge-edge-north | connect.yaml | egress-gate-c2 | - | system:c2-stand-in-atl | table asset_logistics_status |
| edge-north | hq | asset-telemetry-windows | edge-hq-bridge-edge-north | connect.yaml | none declared | - | - | table asset_telemetry_windows |
| edge-north | hq | derived-sustainment | edge-hq-bridge-edge-north | connect.yaml | none declared | - | - | not declared |
| edge-north | hq | effector-events | edge-hq-bridge-edge-north | connect.yaml | none declared | - | - | table effector_launch |
| edge-north | hq | link-heartbeat | edge-hq-bridge-edge-north | connect.yaml | none declared | - | - | not declared |
| edge-north | hq | munition-tracks | edge-hq-bridge-edge-north | connect.yaml | none declared | - | - | table munition_track |
| edge-north | hq | tactical-events | edge-hq-bridge-edge-north | connect.yaml | none declared | - | - | table tactical_events |
| edge-north | hq | telemetry-latest-state | edge-hq-bridge-edge-north | connect.yaml | none declared | - | - | table telemetry_latest_state |
| edge-south | edge-south | asset-capability-snapshot | none declared | - | edge-hq-bridge-edge-south, tier-projector-edge-south | - | - | table asset_capability_state |
| edge-south | edge-south | asset-cm-state | tier-cm-edge-south | annotation | edge-hq-bridge-edge-south, tier-projector-edge-south | - | - | table asset_cm_state |
| edge-south | edge-south | asset-declarations | tier-declaration-intake-edge-south | annotation | edge-hq-bridge-edge-south, tier-projector-edge-south | - | - | table asset_correlation; table asset_declaration |
| edge-south | edge-south | asset-element-inventory | none declared | - | edge-hq-bridge-edge-south, tier-projector-edge-south | - | - | table inventory_items |
| edge-south | edge-south | asset-fielding | none declared | - | edge-hq-bridge-edge-south, tier-projector-edge-south | - | - | table asset_fielding |
| edge-south | edge-south | asset-logistics-status | tier-fusion-edge-south | annotation | edge-hq-bridge-edge-south, tier-projector-edge-south | - | - | table asset_logistics_status |
| edge-south | edge-south | asset-telemetry-windows | faust-edge-edge-south | annotation | edge-hq-bridge-edge-south, tier-projector-edge-south | - | - | table asset_telemetry_windows |
| edge-south | edge-south | derived-sustainment | faust-edge-edge-south | annotation | edge-hq-bridge-edge-south | - | - | not declared |
| edge-south | edge-south | effector-events | redpanda-connect-edge-south | annotation | edge-hq-bridge-edge-south, tier-projector-edge-south | - | - | table effector_launch |
| edge-south | edge-south | ingress-dis-raw | sensor-ingest-edge-south | annotation | none declared | - | - | not declared |
| edge-south | edge-south | ingress-dlq | redpanda-connect-edge-south | annotation | none declared | - | - | not declared |
| edge-south | edge-south | link-heartbeat | tier-projector-edge-south | annotation | edge-hq-bridge-edge-south | - | - | not declared |
| edge-south | edge-south | munition-tracks | redpanda-connect-edge-south | annotation | edge-hq-bridge-edge-south, tier-projector-edge-south | - | - | table munition_track |
| edge-south | edge-south | openddil-edge-south-asset_state-changelog | faust-edge-edge-south | annotation | none declared | - | - | not declared |
| edge-south | edge-south | openddil-edge-south-prognostics_accumulators-changelog | faust-edge-edge-south | annotation | none declared | - | - | not declared |
| edge-south | edge-south | raw-sensor-stream | redpanda-connect-edge-south | annotation | none declared | - | - | not declared |
| edge-south | edge-south | tactical-events | faust-edge-edge-south | annotation | edge-hq-bridge-edge-south, tier-projector-edge-south | - | - | table tactical_events |
| edge-south | edge-south | tactical-events | tier-cm-edge-south | annotation | edge-hq-bridge-edge-south, tier-projector-edge-south | - | - | table tactical_events |
| edge-south | edge-south | tactical-events | tier-fusion-edge-south | annotation | edge-hq-bridge-edge-south, tier-projector-edge-south | - | - | table tactical_events |
| edge-south | edge-south | telemetry-latest-state | faust-edge-edge-south | annotation | asset-registry-service, edge-hq-bridge-edge-south, logistics-sim, tier-projector-edge-south | - | - | table telemetry_latest_state |
| edge-south | hq | asset-capability-snapshot | edge-hq-bridge-edge-south | connect.yaml | none declared | - | - | table asset_capability_state |
| edge-south | hq | asset-cm-state | edge-hq-bridge-edge-south | connect.yaml | egress-assembler | - | - | table asset_cm_state |
| edge-south | hq | asset-declarations | edge-hq-bridge-edge-south | connect.yaml | none declared | - | - | table asset_correlation; table asset_declaration |
| edge-south | hq | asset-element-inventory | edge-hq-bridge-edge-south | connect.yaml | none declared | - | - | table inventory_items |
| edge-south | hq | asset-fielding | edge-hq-bridge-edge-south | connect.yaml | none declared | - | - | table asset_fielding |
| edge-south | hq | asset-logistics-status | edge-hq-bridge-edge-south | connect.yaml | egress-gate-c2 | - | system:c2-stand-in-atl | table asset_logistics_status |
| edge-south | hq | asset-telemetry-windows | edge-hq-bridge-edge-south | connect.yaml | none declared | - | - | table asset_telemetry_windows |
| edge-south | hq | derived-sustainment | edge-hq-bridge-edge-south | connect.yaml | none declared | - | - | not declared |
| edge-south | hq | effector-events | edge-hq-bridge-edge-south | connect.yaml | none declared | - | - | table effector_launch |
| edge-south | hq | link-heartbeat | edge-hq-bridge-edge-south | connect.yaml | none declared | - | - | not declared |
| edge-south | hq | munition-tracks | edge-hq-bridge-edge-south | connect.yaml | none declared | - | - | table munition_track |
| edge-south | hq | tactical-events | edge-hq-bridge-edge-south | connect.yaml | none declared | - | - | table tactical_events |
| edge-south | hq | telemetry-latest-state | edge-hq-bridge-edge-south | connect.yaml | none declared | - | - | table telemetry_latest_state |
| hq | edge-north | asset-element-telemetry | logistics-sim | annotation | tier-projector-edge-north | - | - | table asset_element_telemetry |
| hq | edge-south | asset-element-telemetry | logistics-sim | annotation | tier-projector-edge-south | - | - | table asset_element_telemetry |
| hq | hq | asset-cm-state | cm-service | annotation | egress-assembler | - | - | table asset_cm_state |
| hq | hq | asset-element-inventory | logistics-sim | annotation | none declared | - | - | table inventory_items |
| hq | hq | asset-logistics-status | logistics-fusion-service | annotation | egress-gate-c2 | - | system:c2-stand-in-atl | table asset_logistics_status |
| hq | hq | asset-registry-events | asset-registry-service | annotation | none declared | - | - | not declared |
| hq | hq | egress-c2-repair-sink | egress-gate-c2 | annotation | egress-forwarder | RepairOrder | system:c2-stand-in-atl | kind label /label |
| hq | hq | egress-c2-status | egress-gate-c2 | annotation | none declared | - | system:c2-stand-in-atl | not declared |
| hq | hq | egress-depot-faults | egress-assembler | annotation | egress-gate-c2 | FaultEvent | system:depot-ledger | kind label /picture/label |
| hq | hq | egress-depot-sink | egress-gate-c2 | annotation | egress-forwarder | FaultEvent | system:depot-ledger | kind label /picture/label |
| hq | hq | egress-repair-orders | egress-intake | annotation | egress-gate-c2 | RepairOrder | system:c2-stand-in-atl | kind label /label |
| hq | hq | parts-availability | logistics-sim | annotation | none declared | - | - | not declared |
| hq | hq | tactical-events | cm-service | annotation | none declared | - | - | table tactical_events |
| hq | hq | tactical-events | logistics-fusion-service | annotation | none declared | - | - | table tactical_events |
| region-north | hq | region-fleet-summary | faust-regional-region-north | annotation | none declared | - | - | not declared |
| region-north | hq | region-north-fan-in | faust-regional-region-north | annotation | none declared | - | - | not declared |
| region-north | hq | region-region-north-aggregator-region_region_north_assets_latest-changelog | faust-regional-region-north | annotation | none declared | - | - | not declared |
| region-north | hq | region-region-north-aggregator-region_region_north_emitted_partials-changelog | faust-regional-region-north | annotation | none declared | - | - | not declared |
| region-north | hq | region-region-north-aggregator-sweep-tick | faust-regional-region-north | annotation | none declared | - | - | not declared |
| region-north | hq | region-top-factors | faust-regional-region-north | annotation | none declared | - | - | not declared |
| region-north | hq | region-wear-trends | faust-regional-region-north | annotation | none declared | - | - | not declared |
| region-south | hq | region-fleet-summary | faust-regional-region-south | annotation | none declared | - | - | not declared |
| region-south | hq | region-region-south-aggregator-region_region_south_assets_latest-changelog | faust-regional-region-south | annotation | none declared | - | - | not declared |
| region-south | hq | region-region-south-aggregator-region_region_south_emitted_partials-changelog | faust-regional-region-south | annotation | none declared | - | - | not declared |
| region-south | hq | region-region-south-aggregator-sweep-tick | faust-regional-region-south | annotation | none declared | - | - | not declared |
| region-south | hq | region-south-fan-in | faust-regional-region-south | annotation | none declared | - | - | not declared |
| region-south | hq | region-top-factors | faust-regional-region-south | annotation | none declared | - | - | not declared |
| region-south | hq | region-wear-trends | faust-regional-region-south | annotation | none declared | - | - | not declared |

### Exceptions

| Exception | Count | Items | Meaning |
|---|---|---|---|
| consumer-without-writer | 12 | edge-north/asset-capability-snapshot (edge-hq-bridge-edge-north); edge-north/asset-capability-snapshot (tier-projector-edge-north); edge-north/asset-element-inventory (edge-hq-bridge-edge-north); edge-north/asset-element-inventory (tier-projector-edge-north); edge-north/asset-fielding (edge-hq-bridge-edge-north); edge-north/asset-fielding (tier-projector-edge-north); edge-south/asset-capability-snapshot (edge-hq-bridge-edge-south); edge-south/asset-capability-snapshot (tier-projector-edge-south); edge-south/asset-element-inventory (edge-hq-bridge-edge-south); edge-south/asset-element-inventory (tier-projector-edge-south); edge-south/asset-fielding (edge-hq-bridge-edge-south); edge-south/asset-fielding (tier-projector-edge-south) | A consumer is bound to this topic; no workload declares writing it. |
| group-without-topic | 27 | edge-north/connect-dis-mapper (redpanda-connect-edge-north); edge-north/openddil-edge-north (faust-edge-edge-north); edge-north/region-region-north-source-edge-north (faust-regional-region-north); edge-south/connect-dis-mapper (redpanda-connect-edge-south); edge-south/openddil-edge-south (faust-edge-edge-south); edge-south/region-region-south-source-edge-south (faust-regional-region-south); hq/projector-asset-correlation (projector-hq); hq/projector-asset-declaration (projector-hq); hq/projector-asset-element-inventory (projector-hq); hq/projector-asset-element-telemetry (projector-hq); hq/projector-asset-fielding (projector-hq); hq/projector-capability-state (projector-hq); hq/projector-cm-state (projector-hq); hq/projector-effector-launch (projector-hq); hq/projector-logistics-status (projector-hq); hq/projector-munition-track (projector-hq); hq/projector-parts-availability (projector-hq); hq/projector-region-fleet-summary (projector-hq); hq/projector-region-top-factors (projector-hq); hq/projector-region-wear-trends (projector-hq); hq/projector-tactical-events (projector-hq); hq/projector-telemetry-latest (projector-hq); hq/projector-telemetry-windows (projector-hq); hq/region-region-north-aggregator (faust-regional-region-north); hq/region-region-north-hq-source (faust-regional-region-north); hq/region-region-south-aggregator (faust-regional-region-south); hq/region-region-south-hq-source (faust-regional-region-south) | A consumer group is declared; no mounted config or env binds it to a topic. No topic is inferred. |
| labels-not-declared | 35 | 35 rows | No kind label and no labelled table is declared for this topic. Absence is not defaulted. |
| workload-no-declaration | 24 | egress-pane-api; egress-stub-sink; electric-sync; frontend; pep; postgres-hq; redpanda-edge-north; redpanda-edge-south; redpanda-hq; restate-hub; restate-server; tier-electric-edge-north; tier-electric-edge-south; tier-frontend-edge-north; tier-frontend-edge-south; tier-pep-edge-north; tier-pep-edge-south; tier-pg-edge-north; tier-pg-edge-south; tier-restate-edge-north; tier-restate-edge-south; tier-topaz-edge-north; tier-topaz-edge-south; topaz-hq | Information: a Deployment or StatefulSet declares neither annotation. |
| writer-not-annotated | 26 | hq/asset-capability-snapshot (edge-hq-bridge-edge-north); hq/asset-capability-snapshot (edge-hq-bridge-edge-south); hq/asset-cm-state (edge-hq-bridge-edge-north); hq/asset-cm-state (edge-hq-bridge-edge-south); hq/asset-declarations (edge-hq-bridge-edge-north); hq/asset-declarations (edge-hq-bridge-edge-south); hq/asset-element-inventory (edge-hq-bridge-edge-north); hq/asset-element-inventory (edge-hq-bridge-edge-south); hq/asset-fielding (edge-hq-bridge-edge-north); hq/asset-fielding (edge-hq-bridge-edge-south); hq/asset-logistics-status (edge-hq-bridge-edge-north); hq/asset-logistics-status (edge-hq-bridge-edge-south); hq/asset-telemetry-windows (edge-hq-bridge-edge-north); hq/asset-telemetry-windows (edge-hq-bridge-edge-south); hq/derived-sustainment (edge-hq-bridge-edge-north); hq/derived-sustainment (edge-hq-bridge-edge-south); hq/effector-events (edge-hq-bridge-edge-north); hq/effector-events (edge-hq-bridge-edge-south); hq/link-heartbeat (edge-hq-bridge-edge-north); hq/link-heartbeat (edge-hq-bridge-edge-south); hq/munition-tracks (edge-hq-bridge-edge-north); hq/munition-tracks (edge-hq-bridge-edge-south); hq/tactical-events (edge-hq-bridge-edge-north); hq/tactical-events (edge-hq-bridge-edge-south); hq/telemetry-latest-state (edge-hq-bridge-edge-north); hq/telemetry-latest-state (edge-hq-bridge-edge-south) | The writer is known from config; no produces-topics annotation names it. |
| writer-without-consumer | 52 | edge-north/ingress-dis-raw (sensor-ingest-edge-north); edge-north/ingress-dlq (redpanda-connect-edge-north); edge-north/openddil-edge-north-asset_state-changelog (faust-edge-edge-north); edge-north/openddil-edge-north-prognostics_accumulators-changelog (faust-edge-edge-north); edge-north/raw-sensor-stream (redpanda-connect-edge-north); edge-south/ingress-dis-raw (sensor-ingest-edge-south); edge-south/ingress-dlq (redpanda-connect-edge-south); edge-south/openddil-edge-south-asset_state-changelog (faust-edge-edge-south); edge-south/openddil-edge-south-prognostics_accumulators-changelog (faust-edge-edge-south); edge-south/raw-sensor-stream (redpanda-connect-edge-south); hq/asset-capability-snapshot (edge-hq-bridge-edge-north); hq/asset-capability-snapshot (edge-hq-bridge-edge-south); hq/asset-declarations (edge-hq-bridge-edge-north); hq/asset-declarations (edge-hq-bridge-edge-south); hq/asset-element-inventory (edge-hq-bridge-edge-north); hq/asset-element-inventory (edge-hq-bridge-edge-south); hq/asset-element-inventory (logistics-sim); hq/asset-fielding (edge-hq-bridge-edge-north); hq/asset-fielding (edge-hq-bridge-edge-south); hq/asset-registry-events (asset-registry-service); hq/asset-telemetry-windows (edge-hq-bridge-edge-north); hq/asset-telemetry-windows (edge-hq-bridge-edge-south); hq/derived-sustainment (edge-hq-bridge-edge-north); hq/derived-sustainment (edge-hq-bridge-edge-south); hq/effector-events (edge-hq-bridge-edge-north); hq/effector-events (edge-hq-bridge-edge-south); hq/egress-c2-status (egress-gate-c2); hq/link-heartbeat (edge-hq-bridge-edge-north); hq/link-heartbeat (edge-hq-bridge-edge-south); hq/munition-tracks (edge-hq-bridge-edge-north); hq/munition-tracks (edge-hq-bridge-edge-south); hq/parts-availability (logistics-sim); hq/region-fleet-summary (faust-regional-region-north); hq/region-fleet-summary (faust-regional-region-south); hq/region-north-fan-in (faust-regional-region-north); hq/region-region-north-aggregator-region_region_north_assets_latest-changelog (faust-regional-region-north); hq/region-region-north-aggregator-region_region_north_emitted_partials-changelog (faust-regional-region-north); hq/region-region-north-aggregator-sweep-tick (faust-regional-region-north); hq/region-region-south-aggregator-region_region_south_assets_latest-changelog (faust-regional-region-south); hq/region-region-south-aggregator-region_region_south_emitted_partials-changelog (faust-regional-region-south); hq/region-region-south-aggregator-sweep-tick (faust-regional-region-south); hq/region-south-fan-in (faust-regional-region-south); hq/region-top-factors (faust-regional-region-north); hq/region-top-factors (faust-regional-region-south); hq/region-wear-trends (faust-regional-region-north); hq/region-wear-trends (faust-regional-region-south); hq/tactical-events (cm-service); hq/tactical-events (edge-hq-bridge-edge-north); hq/tactical-events (edge-hq-bridge-edge-south); hq/tactical-events (logistics-fusion-service); hq/telemetry-latest-state (edge-hq-bridge-edge-north); hq/telemetry-latest-state (edge-hq-bridge-edge-south) | A workload declares writing this topic; no consumer is bound to it. |

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| Ingress classes and definition files | [ADR-0030](../../../../decisions/ADR-0030-two-stage-configurable-ingress.md) | Accepted | Not stated |
| Uplink through a severable proxy; severing it really stops data | [ADR-0021](../../../../decisions/ADR-0021-edge-hq-topology-is-load-bearing.md) | Accepted | Built |
| Contract A | [Interface contracts](../../../../decisions/DESIGN-2026-09-06-interface-contracts.md) | Design note | Not stated |
| Contract B | [Interface contracts](../../../../decisions/DESIGN-2026-09-06-interface-contracts.md) | Design note | Not stated |
| Release and intake at the hub | [ADR-0046](../../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Not stated |
| Cursor-on-target bridge | [CoT bridge design](../../../../decisions/DESIGN-2026-10-01-cot-bridge.md) | Design note | Not stated |
| Member-to-member flows in the matrix | [ADR-0033](../../../../decisions/ADR-0033-recursive-tier-hierarchy-framework-invariant.md) | Accepted | Declared |
| Writers and consumers, per topic, from workload annotations | [ADR-0054](../../../../decisions/ADR-0054-workload-annotations-declare-broker-use.md) | Accepted | Declared |
