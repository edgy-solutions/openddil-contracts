# ADR-0026 — OperationalState: orthogonal-axis posture model for any entity source

## Status

Accepted (2026-05-27).

## Context

Through Phase 6, OpenDDIL's Silver `EntityTelemetryEvent` had one
state-bearing block on the asset axis: `SustainmentMetrics`. That works
well for mobile platforms with consumables — fuel, oil, ammunition,
component wear — because every interesting state question collapses to
"does this entity have the margin to keep operating?"

Phase 7's expansion to cover stationary infrastructure — sensors,
facilities, fixed launchers — broke that assumption. A SHORAD radar has
no fuel level. An air-defense site has no main-gun ammunition count. But
a radar absolutely has operational state worth surfacing in a logistics
COP: is it powered on, what mode is it in, is it healthy? The
maintainer responsible for that radar cares about exactly that data.

Two adjacent observations forced the question into design space:

1. The customer sim ships a `stateData.subsystem_state` string per
   sensor. Eight values: `OFF`, `MAINTENANCE`, `STANDBY`, `OPERATE`,
   `OPERATE_RX_ONLY`, `OPERATE_TX_ONLY`, `SHUTDOWN`, `DEGRADED`.

2. The existing OpenDDIL stance (`proprietary-mapping.yaml` header,
   pre-Phase 7) was to drop Sensor messages at Bronze under the
   rationale: *"OpenDDIL is a logistics COP, sensor coverage isn't
   logistics-domain."* That stance conflated **sensor coverage geometry**
   (innerRange/outerRange/azimuth/FOV — correctly out of scope for
   logistics) with **sensor operational state** (subsystem health and
   activity — first-class logistics-domain data). Coverage geometry stays
   at Bronze; operational state becomes Silver.

A naive first pass added a single `SubsystemState` enum to the proto
mirroring the customer's eight values. That worked for the customer but
locked the canonical Silver model to one source's combined-state
vocabulary — actively hostile to DIS, AFSim, VRForces, or any future
adapter whose state encoding looks different. The first commit went out;
the rework went in before deployment.

## Decision

### Canonical: 3 orthogonal axes + 2 discrete activity cues

`EntityTelemetryEvent.operational_state` (proto field 6) carries:

```protobuf
message OperationalState {
  PowerState      power_state      = 1;  // is the entity functional?
  FunctionalMode  functional_mode  = 2;  // what is it doing right now?
  HealthState     health_state     = 3;  // is it nominal or impaired?
  bool actively_receiving    = 4;        // discrete RX path active
  bool actively_transmitting = 5;        // discrete TX path active
}
```

Each axis has its own enum (`POWER_STATE_*`, `FUNCTIONAL_MODE_*`,
`HEALTH_STATE_*`) with `UNSPECIFIED = 0` so consumers tolerate any axis
being absent. Producers populate whichever axes their wire shape
carries.

The three axes are **orthogonal**, not a precedence hierarchy: an
entity may be `POWER_ON + MODE_ACTIVE + HEALTH_DEGRADED` simultaneously
(operating with caveats — the most common non-nominal state in
practice). The earlier 8-value enum was a cross-product flattening that
mixed dimensions into one slot, losing the ability to distinguish
"powered on, in maintenance window, health-nominal" from "powered off,
unknown health" from "powered on, active, degraded."

### Adapters decompose source vocabularies into the canonical model

The customer-overlay bundle's `proprietary-mapping.yaml` Bloblang decomposes
its single `subsystem_state` string via match blocks:

| Customer wire value | power_state | functional_mode | health_state |
|---|---|---|---|
| `OFF` | OFF | UNSPECIFIED | UNSPECIFIED |
| `MAINTENANCE` | MAINTENANCE | UNSPECIFIED | UNSPECIFIED |
| `STANDBY` | STANDBY | IDLE | NOMINAL |
| `OPERATE` | ON | ACTIVE | NOMINAL |
| `OPERATE_RX_ONLY` | ON | RECEIVE_ONLY | NOMINAL |
| `OPERATE_TX_ONLY` | ON | TRANSMIT_ONLY | NOMINAL |
| `SHUTDOWN` | SHUTTING_DOWN | UNSPECIFIED | UNSPECIFIED |
| `DEGRADED` | ON | ACTIVE | DEGRADED |

Other adapters follow the same shape with different source-field
mappings:

- **DIS (IEEE 1278)**: `EntityState.appearance.power_plant_on` →
  `power_state`; `appearance.damage` / `firepower_kill` →
  `health_state`; `EmissionSystem.system_status.OPERATING` →
  `power_state` + `actively_transmitting`; `EmitterBeam` activity →
  `functional_mode` SCAN/TRACK.

- **AFSim**: `platform.is_on()` → `power_state`; `sensor.mode()`
  (passive/active/scan/track) → `functional_mode`; `damage_state` →
  `health_state`.

- **VRForces**: entity damage states (none/slight/destroyed) →
  `health_state`; behavior activity → `functional_mode`.

- **Any future source**: populates whichever axes it carries;
  UNSPECIFIED stays valid for the rest.

### Logistics-fusion emits one ConstrainingFactor per non-nominal axis

`_eval_operational_state` in
[openddil-logistics-fusion-service/src/fusion/rules.py] returns
`list[ConstrainingFactor]`. Per-axis mapping:

| Axis value | Severity | factor_id |
|---|---|---|
| `power_state == OFF` | CRITICAL | `operational.offline` |
| `power_state == SHUTTING_DOWN` | CRITICAL | `operational.shutdown` |
| `power_state == MAINTENANCE` | DEGRADED | `operational.maintenance` |
| `health_state == FAILED` | CRITICAL | `operational.failed` |
| `health_state == FAULT` | CRITICAL | `operational.fault` |
| `health_state == DEGRADED` | DEGRADED | `operational.degraded` |
| `functional_mode == *` | — | informational only (no factor) |

An entity in `POWER_STATE_MAINTENANCE + HEALTH_STATE_DEGRADED` emits
**both** `operational.maintenance` and `operational.degraded`. That is
the correct corollary of axes being independent — if the underlying
reality has multiple non-nominal axes, the COP shows multiple factors.
Collapsing to a single severity would be lossy.

`FunctionalMode` does not drive severity. An operator commanding
`MODE_RECEIVE_ONLY` is a posture choice, not a fault. The mode is
visible to consumers (maintainer-view detail panel surfaces it) but
the COP doesn't alarm on it.

The factor_id namespace `operational.*` stays semantically distinct
from `subsystem.<NAME>` (the existing namespace `_eval_subsystems` uses
for per-component BIT codes from `sustainment.health.active_fault_codes`).
Two different scopes: whole-entity operational mode vs named-component
fault.

### Coverage geometry stays out of scope

Sensor wire-shape fields `innerRange`, `outerRange`, `azimuth`,
`azimuthFOV`, `elevation`, `elevationFOV` are sensor-coverage geometry.
They are preserved at Bronze (the `ingress-proprietary-raw` topic) but
NOT mapped to Silver. OpenDDIL's logistics-COP domain doesn't surface
coverage today; a future `EntitySensorCoverage` Silver type can be
defined if a downstream consumer materializes.

### Stationary infrastructure ride existing message shapes

Facilities (`AIR_DEFENSE_SITE`, `HEADQUARTER_COMPLEX`,
`INSTALLATION_FACILITY_CIVILIAN`) flow through the Unit message path,
not via a separate FacilityMessage. The customer sim's `Node.type` ==
`definitionName` for facility nodes serves as the `platform_variant`
discriminator; the Unit-message Bloblang branch handles them
unchanged. Facility-specific operational state arrives via the same
3-axis OperationalState block when the source populates it.

## Consequences

### Positive

1. **Adapter independence.** A new source — DIS gateway, AFSim
   integration, VRForces feed — adds an adapter that decomposes its
   source vocabulary into the canonical 3 axes. Fusion rules don't
   change. SPA cascade doesn't change. Same architectural shape that
   `projector/edge_assignment` strategies and `platform_variant_aliases`
   established: separate canonical Silver from source-specific quirks.

2. **Honest multi-factor severity.** An entity with multiple non-nominal
   axes emits multiple ConstrainingFactor entries. Maintainer sees both
   "in maintenance window" AND "degraded subsystem" simultaneously
   rather than one collapsed value that hides the other.

3. **Stationary infrastructure becomes first-class.** Sensors,
   facilities, fixed launchers gain a logistics-COP presence proportional
   to their operational state. Previously they were either invisible
   (dropped at Bronze) or rendered with no severity information.

4. **Wire-shape changes localized to adapters.** The Silver model is
   stable; per-source mapping changes stay in per-source mapping files.
   `proprietary-mapping.yaml` evolution doesn't ripple to
   `dis-mapping.yaml` or future adapters.

### Negative

1. **Decomposition overhead in every adapter.** Sources with single
   combined-state enums (like customer-overlay) need explicit match blocks to
   split into 3 axes. The Bloblang gets more verbose than a 1:1 string
   passthrough would have been. Trade-off accepted: canonical-model
   discipline beats per-source coupling.

2. **Bigger proto surface.** Three enums + one message instead of one
   enum + the existing scaffolding. The proto file grew ~140 lines.
   Acceptable; the entropy goes into clearer ontology, not noise.

3. **Test surface multiplies.** Fusion now has matrix testing concerns:
   power × mode × health combinations. Practical mitigation: test only
   the axes that drive severity (power + health). FunctionalMode is
   informational and exercised at the producer/consumer boundary.

### Neutral / acknowledged

- **Customer-overlay wire-shape provenance.** The Sensor message schema is
  documented as an LLM-reconstructed inference, not a customer ICD. The
  `stateData` block was wire-confirmed by visual inspection of captured
  payloads (2026-05-27); the 8-value vocabulary was provided by the
  customer's documentation. Future adapter authors should not assume
  this schema is authoritative.

- **schema_revision bump.** Producers that populate `operational_state`
  set `schema_revision = 2`. Consumers shouldn't gate on it (proto3
  default for the new field is UNSPECIFIED everywhere); it's a
  human-readable marker for producer self-documentation.

## Architectural family

This decision belongs to the project's established pattern of separating
canonical Silver from source-specific quirks via dispatch tables /
registries / strategy resolvers:

| Layer | Canonical | Source-specific decomposition |
|---|---|---|
| Edge assignment | `EdgeAssignment` (edge_id + region_id + derivation_basis) | `nearest_fob`, `asset_id_prefix`, `static`, `chain` strategies, configured per-deployment |
| Platform variant | Canonical strings in `platform_variant_aliases.yaml` `canonical:` column | Per-source `native -> canonical` alias tables (sim_a, dis, proprietary) |
| Asset identity | Canonical asset_id (URN form) | Per-source `native_id -> canonical_asset_id` alias tables |
| **Operational state** | **3-axis `OperationalState`** | **Per-source decomposition in each adapter's mapping** |

Future adapter authors look at any of these patterns and follow the
same shape. New canonical-model additions should follow the same
discipline: define the canonical Silver shape first, then write
per-source decompositions.

## References

- Bloblang worked example: `openddil-customer-bundle-customer-overlay/dynamic-mappings/proprietary-mapping.yaml`
- Fusion rule: `openddil-logistics-fusion-service/src/fusion/rules.py :: _eval_operational_state`
- Proto: `proto/openddil/telemetry/v1/telemetry.proto :: OperationalState`
- ADR-0010 (feed integration strategy) — establishes per-source adapter pattern
- ADR-0017 (UI mock components self-identify) — the COP-honesty discipline that motivated rejecting silent collapsing
- ADR-0023 (hierarchy restoration topology) — established the canonical-vs-quirks separation pattern for edge_id/region_id

## Open items (tracked as follow-ups, NOT blocking)

- **Maintainer GROUND DIAGNOSTICS sensor panel** displays the three axes
  separately. Requires projector to store `operational_state` in
  `telemetry_latest_state` (postgres column migration). Tracked as
  Phase 5 work.
- **Coverage-geometry Silver type** if a downstream consumer of sensor
  field-of-view materializes. Not blocking.
- **DIS adapter** for EntityState + EmissionSystem when the DIS feed
  formally returns. The canonical model is ready; the adapter is
  per-source mapping work.
- **Whitelist refactor** for `platform_variant_aliases.yaml`'s
  proprietary section. The 12 entries added in this work are identity
  passthroughs (`native == canonical`) — that's whitelisting via
  alias-table abuse. Refactor to an explicit whitelist YAML structure
  when next touching the bundle. (Follow-up #27.)
