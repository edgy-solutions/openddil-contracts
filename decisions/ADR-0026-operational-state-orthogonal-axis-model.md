# ADR-0026 — OperationalState: orthogonal-axis posture model for any entity source

## Status

Accepted (2026-05-27). **Amended 2026-08-18 — absence is not a factor;
see §Amendment.** The axes' unspecified value now has a stated
convention, earned by a field failure and by two components arriving at
the same wrong default independently.

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

## Amendment 2026-08-18 — what an axis means when it says nothing

**The convention, stated once so both consumers can cite it rather than
re-derive it:**

> **`UNSPECIFIED` on any axis means the source made no claim. It is not a
> value on that axis — it is the absence of one.**
>
> 1. **It never becomes a `ConstrainingFactor`.** Absence does not
>    constrain the asset; it constrains our knowledge of the asset.
> 2. **It never folds into an operational category** — not `NOMINAL`, not
>    `FAULT`, not `DEGRADED`, not any future member. Every one of those is
>    a claim about the equipment, and there is no claim to make.
> 3. **A consumer that cannot express "no claim" must not invent one.** It
>    passes the absence through and lets the layer that *can* express it do
>    so — today, presentation (clause 4 below).
> 4. **`NOMINAL` is a positive assertion and must be reached deliberately**,
>    never by falling through every other branch. A code path where absence
>    and health share an exit is the defect this amendment names.

### Why clause 1 is settled and not a preference

`_eval_operational_state` emitting **no factor** for `UNSPECIFIED` is
correct, and the reason is a field failure with a date rather than an
argument.

`logistics-sim`'s `element_gen.severity_tier()` once treated
`UNSPECIFIED` health together with `tx_off`/`rx_off` as `FAULT`. On
**2026-06-24, on the work cluster**, a live feed left `operational_state`
absent — proto3 gives an unset enum the zero value and unset bools
`false`, so *every* asset matched — and **every MRAD lit up yellow**. The
rule was gated on an explicit `NOMINAL` and the behaviour backed out. Its
docstring still carries the account.

So the question *"what happens if absence is scored as impairment?"* has
been answered empirically, at scale, in front of an operator: **a
false-positive wave across the entire fleet**, produced not by a wrong
threshold but by the wire's inability to distinguish *unset* from *false*.

**What failed was conflation, not distinction.** Absence was routed into
`FAULT` — an existing operational meaning that an operator correctly reads
as *"this equipment is impaired."* The experiment says nothing against a
treatment no operator would read that way, which is why clause 2 forbids
folding rather than forbidding expression, and why the open question below
survives it.

### The argument for stating it at all — two independent re-derivations

The convention exists because **two components reached the same wrong
default without consulting each other**:

| component | site | behaviour |
|---|---|---|
| `logistics-fusion` | `_eval_operational_state` | no branch for `UNSPECIFIED`, none for `NOMINAL`; both fall through, `_max_severity` returns `OK` |
| `logistics-sim` | `element_gen.severity_tier()` rule 7 | *"anything else (NOMINAL, UNSPECIFIED, ON, …) → NOMINAL"*, with a test whose comment reads **"UNSPECIFIED is treated as healthy"** |

Two authors, two files, two repositories, one identical collapse — and in
the sim's case written down approvingly, as though it were the decision.

That is what an **uncited convention** looks like from the inside. Nobody
was careless: *"treat silence as fine"* is the locally cheapest branch
every time, because the alternative requires knowing something the local
file cannot see. **A convention that is not stated somewhere both
consumers cite does not govern them** — it gets re-derived, and it gets
re-derived the same wrong way, because the wrong way is the one the
language makes free. (**GD-12**, now with its cross-component instance.)

### The one question left open, stated precisely

**Is observed-ness a fourth thing the axis model expresses?**

The three axes answer *what posture is this asset in*. Whether the source
*said anything at all* is a different question, and it currently has no
home: it is neither an axis value nor a provenance field. The options, and
what each would cost:

| | says | cost |
|---|---|---|
| a fourth expression (coverage / observed-axes) | *this axis was never observed* — true | a declared field with no consumer today |
| provenance carries it | *this producer reports these axes* | provenance is per-event; observed-ness is per-axis |
| presentation only | *render the unknown distinctly* | rollups and counts still read `OK` |

**Deferred to demand, deliberately.** A declared field nothing reads is the
`cm_schema: "generic-v1"` shape this corpus closed in August — honest-looking,
unresolvable, and inherited by the next reader as intentional. **When it is
taken up, the consumer is named in the same change or it is not taken up.**

*What is no longer open:* whether absence may be scored as impairment. It
may not (clauses 1–2), and that half needed the evidence above rather than
a preference.

### Scheduled: presentation treatment

**When the frontend is next touched in this area**, *not reported* renders
distinguishably from *nominal*, per ADR-0035 class 2 (never observed). The
raw `OperationalState` block already reaches the UI, so this needs no
contract change and no producer change.

Stated honestly: this addresses the **pixel**, not the **aggregate**.
`overall_severity` continues to read `OK` for an unobserved axis, so
rollups, counts and tier aggregates still treat it as fine. That is a known
and accepted gap until the open question above is answered — recorded so
nobody mistakes the render fix for a complete one.

### Measured blast radius, so the amendment is not read as urgent

Queried on 2026-08-16: **14 of 14** lab assets carry unspecified axes, and
**14 of 14** are already `CRITICAL` from other factors, so **zero would
change today**. The defect is latent in this deployment and live in a
healthy one — a quiet fleet with unspecified health reads `OK`.

Two consequences worth carrying: nothing on screen moves when this is
implemented, and **this deployment cannot demonstrate the fix**, so a test
is the entire verification story (ADR-0037 clause 3).

### Follow-up work this creates — scoped, not scheduled

- **`logistics-sim` rule 7** collapses `UNSPECIFIED → NOMINAL` and must be
  fixed **in line with clause 4** rather than locally patched — the local
  patch is what produced two divergent answers in the first place. Its test
  comment (*"UNSPECIFIED is treated as healthy"*) is part of the change.
- **A deliberate `UNSPECIFIED`-emission control in the sim.** Unspecified
  health is the *normal* state for DIS-sourced assets, so the sim must be
  able to reproduce it on purpose; a generator that always emits a definite
  value cannot exercise the honest-absence path this amendment schedules.
- **The tactical-damage constraint set** (destroyed → not healthy,
  mobility-kill → propulsion, firepower-kill → weapons, fire events →
  stockpile decrement). ~~**Gated on an open question:** whether the DIS
  mapping reads entity-appearance damage bits at all.~~

  **ANSWERED 2026-08-19, and this ADR was wrong about its own gap in a way
  worth recording.** The DIS sidecar has extracted `appearance_bits` and
  published them to `ingress-dis-raw` since it was written;
  `sim-dis-mapping.yaml` has **zero** references to the field. So the
  condition is not *"no DIS source for the health axis"* — it is **a
  partial source arriving on Bronze that Stage 2 never learned to read.**

  That changes the size of the work: "no source" implies an upstream ask,
  "present and unmapped" is a change we can make alone, against data
  already in the topic, with no producer conversation and no wire change.

  **Sharper still: this ADR SPECIFIED the mapping.** Its own adapter list
  above says *`EntityState.appearance.power_plant_on` → `power_state`;
  `appearance.damage` / `firepower_kill` → `health_state`.* The decision
  was made on 2026-05-27, the sidecar carried the data, and Stage 2 was
  never written. **A specified mapping that nobody built is
  indistinguishable, from the outside, from a source that does not exist** —
  and this ADR then registered it as the latter, citing its own unbuilt
  design as a missing feed.

  Design, bit layout and the gating measurement:
  `DESIGN-2026-08-19-dis-appearance-bits.md`. That measurement is
  load-bearing — an all-zero appearance field would let the mapping
  manufacture `NOMINAL` out of silence, which is the defect this amendment
  exists to prevent.

  *Why that gate matters more than it looks.* The sim already consumes
  `telemetry-latest-state` and constrains its synthesis from reported
  health — the correlation mechanism exists. But **DIS never populates
  health** (the 14-of-14 measurement above), so for every DIS-sourced asset
  that correlation is **inert**: consistency in the demo has come from the
  two sims sharing a scenario, not from one constraining the other.
  Consistency by shared input and consistency by constraint look identical
  until the inputs diverge. The damage constraints are what convert the
  first into the second.

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

- Bloblang worked example:
  `openddil-customer-bundle-example/dynamic-mappings/sample-sensor-mapping.yaml`
  — the combined-enum → three-axis decomposition, publicly readable.

  **Amended 2026-08-08 (pointer only; no decision changed).** This
  reference previously pointed into a private deployment overlay. Two
  problems, and the second is the load-bearing one:

  1. The worked example is pedagogy for adapter authors, and its
     audience can only open public repositories — so a private path is
     a **broken reference by construction**, not merely inconvenient.
  2. Naming a private overlay's path in a public ADR asserts that
     overlay's existence, which the sovereignty discipline forbids.

  The pointer now targets the public sample overlay, whose specimen was
  written for this purpose: fictional content, identical structure, with
  the three match blocks annotated as three independent questions asked
  of one input. Repointed in the same change that made the destination
  exist, so the reference was never aspirational.
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
