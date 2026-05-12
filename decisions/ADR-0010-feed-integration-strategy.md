# ADR-0010: Feed Integration Strategy

## Status
Proposed

## Context
OpenDDIL must integrate with multiple external feeds: 
- DIS/IEEE-1278.1 (well-specified but legacy)
- A proprietary JSON/Python feed (archaic, badly-implemented, customer-mandated)
- Future protocols (MAVLink, STANAG 4586, MIL-STD-1553 captures, OBD-II/CANbus)

A unified integration strategy is required to ensure the core mesh is not polluted by the idiosyncratic behaviors of edge protocols.

## Decision
**External protocols do not shape internal contracts.** 
Each external feed will live as an independent ingestion sidecar deployed in `openddil-sensor-ingest/`, producing to its own Bronze topic (e.g., `ingress-dis-raw`, `ingress-proprietary-raw`). All sidecars must conform to a common Silver schema produced by Redpanda Connect Bloblang transforms. The Silver schema is the authoritative internal contract. External protocol quirks are absorbed entirely in the sidecar layer and never leak inward.

## Adapter Pattern Specification
Each sidecar must adhere to the following adapter pattern:
1. **Decode**: Decode its native protocol locally.
2. **Emit JSON**: Emit structured JSON to its dedicated Bronze topic.
3. **Provenance**: Populate a provenance block containing:
   - `source_protocol`
   - `producer_id`
   - `source_sequence`
   - `ingest_timestamp`
4. **Malformed Input**: Handle malformed input via local metrics/counters, *not* by pushing garbage to the global DLQ.
5. **Backpressure**: Handle backpressure via standard Kafka producer configuration (buffer limits, timeouts), *not* by failing silently or dropping packets without metrics.

## Identity Reconciliation
When the same physical asset appears in multiple feeds with different identifiers, reconciliation happens downstream of Bronze in a dedicated `asset-identity-resolver` service, **not** in the sidecars.
- Sidecars emit raw native identifiers.
- The resolver maps them to the canonical OpenDDIL `asset_id` via a curated YAML lookup (`openddil-contracts/ontology/asset_identity_aliases.yaml`).

## Anti-Patterns Explicitly Rejected
- **Protocol Leakage**: Do not let the proprietary feed's quirks (sentinel values, missing units, inconsistent timestamps) leak into the Silver schema.
- **Canonical Identity Bleed**: Do not let any single feed's identity scheme become the canonical OpenDDIL identity scheme.
- **Shared Sidecars**: Do not collapse multiple feeds into a shared sidecar.

## Future Protocols
The next three anticipated feeds will plug in following this exact pattern:
- **MAVLink**: Will plug in as an independent sidecar producing to `ingress-mavlink-raw`.
- **STANAG 4586**: Will plug in as an independent sidecar producing to `ingress-stanag4586-raw`.
- **OBD-II**: Will plug in as an independent sidecar producing to `ingress-obd2-raw`.
