# ADR-0020: Prognostics Derivation Engine (Phase 5)

## Status

Accepted — 2026-05-14 — **Phase 5.** Closed 2026-05-15 at step 2 — no open
rulings. Fire/Detonation + barrel-life activation is scoped as a separate
future phase (blocked on customer ammo-message inventory), not a Phase 5
tail. See `tests/hero_scenario_v3/README.md` → "Phase 5 close note" for the
close summary and follow-ups audit.

Supersedes the earlier "Proposed — stub" draft of this same ADR. That draft
asserted that "System A emits both measured sustainment and kinematics" and
that the "calibration oracle dependency [was] already satisfied." **Both
were false** — see [No oracle — by design](#no-oracle--by-design). The
decision to build the derivation engine stands and is unchanged; the oracle
and calibration framing is removed.

## Context

The Phase 4b edge view surfaced a real limitation: DIS-sourced assets (e.g.
`dis:1:1:4773` / IRON-01) show a "no sustainment telemetry" empty state in
the prognostics panel. The DIS Entity State PDU carries kinematics —
position, velocity, attitude, articulation parameters — but no thermal /
fluid / wear metrics.

As of Phase 4, **no feed anywhere in OpenDDIL carries measured
sustainment.** DIS is kinematic-only. The proprietary customer feed is
kinematic + sensor-geometry only (assessed Phase 4d — Unit and Sensor
message types, no sustainment of any kind). Sim A is fabricated — a
placeholder that was never a placeholder *for* a real feed.

That empty state is accurate about the wire format, but it should not be
read as a law of nature. A substantial amount of sustainment signal is
**derivable from kinematic history**:

- cumulative distance → track / road-wheel wear
- operating hours → time-based maintenance intervals
- speed / acceleration profile → drivetrain stress, hard-accel counts
- terrain integral from pitch / roll → suspension stress
- articulation parameters → turret / gun actuator cycle counts
- rounds-fired from DIS Fire / Detonation PDUs → ammo consumption, barrel life

None of this is computed today.

## Decision

Build a **Prognostics Derivation Engine**: a pipeline stage that turns
kinematic history into sustainment *estimates*, populating the same Silver
`sustainment.*` fields a measured CBM+ feed would populate. Per ADR-0010,
derived sustainment is feed-agnostic — the fusion engine treats derived and
measured identically at the contract level. Derivation is an additional
*source* of sustainment data, not a parallel schema.

### Module shape and seams

Per the reviewed Phase 5 recipe, the engine lives **inside `faust-edge` for
now**, as a self-contained, extractable module. "Inside faust-edge, movable
later" is a hard constraint, not an aspiration — the seams below are what
make a later extraction a *deployment* change rather than a refactor.

- **Its own module** — a `prognostics/` package (`models.py`,
  `coefficients.py`, `accumulators.py`, `agent.py`, `tests/`). Only
  `agent.py` may import `faust`; the rest is framework-free.
- **Input seam** — `agent.py` registers its *own* `@app.agent` consumer of
  `raw-sensor-stream`. It reads kinematics and nothing else; it does not
  touch faust-edge's window buffers, state Table, or any internal state.
  faust-edge changes by exactly one line (`register_prognostics(app)`) —
  that line *is* the seam.
- **Output seam** — a new `derived-sustainment` topic. That topic is the
  engine's entire downstream contract; nothing learns the producer happens
  to run inside the faust-edge process today.
- **The `rules.py` mold** — `models.py` follows `fusion/rules.py` exactly:
  a frozen `PrognosticsInputs` dataclass, independently unit-testable
  `_derive_*` functions, env-driven `coefficients.py` (the `Thresholds`
  mold), a single pure `derive_sustainment(inputs, coeffs, now_ns)` entry
  point. Per ADR-0006, no framework integration leaks into the models.
- **Durable accumulator Table** — cumulative distance and operating hours
  are lifetime accumulators, not rolling windows; the engine owns its own
  RocksDB-backed Faust Table (`prognostics_accumulators`, per-asset-keyed),
  separate from faust-edge's `asset_state`. The changelog topic travels
  with the engine on extraction.
- **ADR-0022 compliance** — every `derived-sustainment` message carries
  `edge_id` / `region_id` origin-node provenance; the accumulator Table is
  per-asset-keyed; any rollup is written as "roll up the children of this
  node," not "roll up everything."

### Initial wear-model set

Phase 5 picks a small, defensible set and explicitly defers the long tail:

**Initial set:** distance-driven track wear, operating hours,
rounds-through-tube barrel life, terrain-integral suspension stress.

**Deferred (post-Phase-5):** brake wear, filter clogging, fluid
degradation, fatigue cycling, and the rest — each added later with its own
evidence.

Rounds-fired for the barrel-life model comes from **DIS Fire / Detonation
PDU ingestion** (in scope for this stage — currently ingested by nothing).
The proprietary customer sim's Shot message was assessed in Phase 4d and
deliberately dropped from scope, so DIS is the rounds-fired source. The
ammo-model input seam is nonetheless **shaped to also accept a future
measured ammo-state source** — `PrognosticsInputs` carries an optional
`measured_ammo_state` slot and `_derive_ammo` branches on it — with the
calibration machinery itself deferred. Cheap now; avoids a model rewrite if
a measured ammo feed ever lands.

### The provenance marker and the confidence field

Every derived `sustainment.*` value carries a provenance marker
distinguishing `MEASURED` from `DERIVED`. In Phase 5, **everything the
engine emits is `DERIVED`** — there is no measured source anywhere in the
system.

**Confidence field — ruling (flagged for review per the Phase 5 brief):**
keep a `confidence` field in the contract as a **forward-looking
placeholder** — present in the shape from day one, populated trivially in
Phase 5 (a fixed placeholder value, documented as having no real meaning
yet). Rationale: the same "get the structural shape right while it is
cheap" logic as ADR-0013 (Quantity-everywhere) and ADR-0022 (provenance
columns) — when the validation phase arrives it can populate real
confidence without a contract migration under live consumers. The
alternative (drop it from Phase 5, add it later) trades a free field now
for an expensive migration later. This is a small ruling and open to
redirect; it is called out here rather than buried.

## Confidence staircase

*(Added 2026-08-12, with the ADR-0035 IH-5 stamp. Extends this ADR's
confidence ruling; no earlier decision changed.)*

The `confidence` field was carried from Phase 5 as a forward-looking
placeholder. IH-5 populated it on the mtbf projection —
`_MTBF_ASSERTED_CONFIDENCE = 0.2` — and that value needs its status
recorded, because a number in a confidence field invites the assumption
that something computed it.

**Nothing computed it. It is asserted, and asserted is the honest
status.** A computed confidence is not available today for a structural
reason rather than a scheduling one: linear extrapolation of a single
trend line carries **no intrinsic uncertainty estimate**, and the wear
accumulators retain `(mean, count)` — sufficient to merge a mean across
tiers ([AUDIT-2026-08-07](AUDIT-2026-08-07-aggregation-composability.md)
§3), insufficient for dispersion. There is no residual, no sample
variance, nothing to derive a fit quality from. A computed-looking number
here would be the confabulation shape the fallback audit named: a
real-seeming answer where an honest assertion belongs.

The value is low because the projection rests on authored placeholder
coefficients this ADR documents as unvalidated. **It is a floor on trust,
not a measurement of it.**

### The four steps, and what each unlocks

1. **Asserted placeholder — today.** A constant with a comment naming why
   it is not a computation. Honest, cheap, and carries no claim it cannot
   support.
2. **Sample retention + regression → fit-derived confidence.** Retaining
   points rather than only `(mean, count)` makes a fit quality
   computable — R², residual spread, prediction interval on the slope.
   **Still ceilinged by coefficient uncertainty:** a perfect fit to a
   trend built on unvalidated coefficients is a precise projection of an
   unvalidated model.
3. **Coefficient validation (this ADR's AFSIM / VR-Forces gate) →
   removes the ceiling.** This is the step that makes *any* computed
   confidence trustworthy rather than merely arithmetic. Step 2 without
   step 3 produces a number that is defensible about its own fit and
   silent about whether the model means anything.
4. **Failure history, or a registered ML unit (ADR-0034) → calibrated
   probability**, plus the uncertainty **band** ADR-0038 AE-4 names as
   absent. This is where *"fails at H+N, ±M"* becomes sayable.

The staircase is ordered by dependency, not by preference: step 4's
calibration needs step 3's validated coefficients, and step 2 without
step 3 is a well-measured wrong answer.

### Confidence-kind must be declared alongside confidence-value

**A confidence number is meaningless without its kind.** An asserted
floor, a regression fit quality, and a calibrated failure probability are
**different quantities on different scales**, and 0.2 means something
different in each. They must not share one field silently — a consumer
comparing across producers, or across time as the staircase is climbed,
would be comparing incomparable numbers with no way to detect it.

So when step 2 lands, `confidence` gains a declared kind beside it. This
is the same declared-vs-inferred discipline the project applies one field
over — GD-11's asset class (declared, never inferred), GD-10's capability
shape (declared, not defined de facto by the first integrator). The
failure mode is identical: absent a declaration, the meaning is set by
whoever wrote the first producer, and every later reader inherits it
without knowing.

*Not designed here.* Whether the kind is an enum on `ValueProvenance`, a
field beside `confidence` on `ConstrainingFactor`, or part of the
analytics-unit provenance stamp is a decision for the change that makes
confidence computable. Recorded now so the field cannot quietly acquire a
second meaning before then.

## No oracle — by design

The earlier draft of this ADR treated "System A" as a real, integrated
calibration oracle. It is not one. **Sim A is fabricated** — there is no
feed producing it, and the placeholder was never a placeholder *for*
something real elsewhere. Confirmed: as of Phase 5 there is **no calibration
oracle, and there never was one.**

This is not a gap to be filled — it is a **sequence**. A real
measured-sustainment asset is implemented *after* the derivation approach is
validated end-to-end against **AFSIM / VR-Forces** and its potential is
demonstrated. The oracle is deliberately downstream, gated on proving the
concept first. Building it now would be building a validator for a
mechanism nobody has yet shown is worth validating.

## What Phase 5 is — and is not

Phase 5 builds the derivation engine and demonstrates it **end-to-end on
synthetic data.** Stated plainly, so it is never overstated:

- **It is** a working demonstration of the derivation *mechanism*: the
  pipeline runs, kinematic history flows through the wear models, derived
  sustainment lands on the Silver `sustainment.*` fields and reaches the
  COP. The previously-empty prognostics panel is populated for
  kinematic-only assets.
- **It is not** a producer of validated or trustworthy sustainment numbers.
  The inputs are synthetic, the coefficients are authored placeholders, and
  there is no ground truth to check them against.

Validation against measured truth is an **explicitly deferred future
phase**, gated on AFSIM / VR-Forces. This framing is not a hedge — it is the
accurate description, and it is a legitimate thing to build: the point is
proving the *mechanism* works so the AFSIM / VR-Forces validation work can
be justified. **The engine is the work; the engine is the value.** The
oracle was only ever for validation, and validation is downstream.

## Testing

With no calibration oracle, the test story is singular and clean —
**scripted OpenDIS authored-scenario tests.** Known input, known answer,
assert the engine does the arithmetic right: e.g. "entity driven exactly
10 km, flat terrain, constant speed → derivation reports ~10 km cumulative
distance and the flat-terrain burn the coefficients specify." The authored
scenario *is* the oracle — for the *mechanism*.

This tests that the engine computes correctly **given its coefficients**.
It does **not** test whether the coefficients are *correct* — that is the
deferred AFSIM / VR-Forces validation. Two different claims; the Phase 5
tests make only the first. (The earlier draft's "System A calibration
oracle" test path is deleted — it was never real. The scripted-scenario
approach was always the cleaner one.)

## Demo narrative — stated honestly

When the prognostics demo is shown, it claims exactly this and no more —
written down here, and to be carried into the demo runbook, so the framing
is set *before* the demo rather than improvised under questioning:

- **Claims:** the derivation pipeline works end-to-end. Kinematic-only
  assets that showed an empty prognostics panel now show derived
  sustainment, computed live from kinematic history through an isolated,
  independently-testable engine.
- **Does not claim:** that the derived numbers are accurate. They are
  mechanism output on authored coefficients, with no ground-truth
  validation. The COP marks them `DERIVED` (ADR-0017's honesty principle
  applied to derived data) precisely so the distinction is never blurred.

### Methodology placeholders to name out loud

Demo-stage compromises the demo must name rather than gloss — same
discipline as how the missing oracle gets named:

- **Engine hours is observed time, not engine-on time.** DIS Entity State
  PDUs carry no engine-on signal, so the engine-hours model uses *observed
  time* (window between first and last sample for the asset) as a
  stand-in. This is a deliberate **overestimate** by design: it counts
  parked-but-visible time. Honest framing: *"derived from observation
  time, not engine-on state — placeholder methodology absent ground
  truth."* Finding or defining an engine-on signal is tracked as a
  future-work item.
- **Barrel-life is built but dormant.** The model has the shape and
  passes its unit tests, but emits nothing in practice until
  Fire/Detonation PDU ingestion lands (in scope per the *Decision*
  section above, follow-on wiring step). While dormant, derived
  sustainment carries no `wear.barrel` component — honest absence. The
  dormancy is tracked as a follow-up so it doesn't get forgotten when
  Fire/Detonation lands.
- **Logistics status for DIS-sourced assets is now driven by derived
  sustainment.** With Phase 5 step 2 (fusion-service consuming
  `derived-sustainment`), DIS-only assets — which previously had no
  sustainment data at all and therefore no wear-driven constraining
  factors — will start showing `DEGRADED` (and eventually `CRITICAL`)
  logistics status when the derived wear models cross thresholds.
  Honest framing: *"the visible severity is real — the engine ran the
  arithmetic against actual kinematics — but the underlying coefficients
  are authored placeholders, so a DEGRADED status here reflects the
  mechanism working, not a validated assessment of the asset's
  condition."* Each derived-driven `ConstrainingFactor` carries
  `origin = ORIGIN_DERIVED` structurally (see proto note below), so a
  consumer that wants to render it differently can.
- **Coefficients are compressed in the demo deployment for visibility.**
  `prognostics/coefficients.py` defaults are order-of-magnitude reasonable
  for real tracked vehicles (5000 km / 5000 h / 1000 rounds /
  100000 deg·km). With those defaults, no short scripted-OpenDIS scenario
  crosses fusion's wear thresholds and the demo would show nothing —
  every model stays at ~100% remaining. The demo therefore overrides them
  via `PROGNOSTICS_*` env vars in `docker-compose.override.yml` to much
  smaller values (10 km / 1 h / 100 rounds / 50 deg·km) so a few-km /
  few-minute scenario actually crosses thresholds and produces real
  constraining factors. Honest framing: *"the compressed values are sized
  so the demo shows the engine working — they are not estimates of real
  platform life."* The honest-authored defaults live in the engine's
  contract (`coefficients.py`); the visibility-tuning lives in the demo
  configuration (`docker-compose.override.yml`). Different artifacts for
  different purposes — the contract stays honest, the demo stays visible.

### Proto extension landed in step 2

`openddil.logistics.v1.ConstrainingFactor` gained `origin` (reusing the
same `Origin` enum as `SustainmentMetrics.value_provenance`) and
`confidence` in Phase 5 step 2. Additive, proto3 zero-default for the
8 existing fusion-rules construction sites (which become provenance-aware
later — out of step 2 scope; tracked with the COP-surface pass). This is
continuous with ADR-0020's existing direction (per-value provenance shape
applied at the next contract boundary) and does not need a separate ADR.

## Consequences

**Pros**

- DIS-sourced (and other kinematic-only) assets gain a populated
  prognostics panel instead of an empty state.
- The engine is buildable *now* — it has no blocked dependency. The oracle
  was the only thing that ever looked like a blocker, and it was never
  real.
- AFSIM / VR-Forces validation, when it comes, inherits a working,
  isolated, testable engine rather than building derivation reactively
  under its own schedule pressure.
- The isolation seams mean a later extraction into a standalone service is
  a deployment change, not a rewrite.

**Cons / risks**

- Derived estimates carry uncertainty that measured values do not, and the
  numbers are unvalidated. Mitigated by the `DERIVED` provenance marker,
  the honest demo narrative above, and ADR-0017-style COP treatment — the
  distinction must never be allowed to blur into "the system reports fuel
  at X%."
- Scope-creep risk on the wear-model set. Mitigated by the explicit
  initial-four / deferred-long-tail split.

**Rejected alternatives**

- *Wait for a measured-sustainment oracle before building.* Rejected: the
  oracle is sequenced *after* this work, gated on it. Waiting would stall
  indefinitely on a dependency that is deliberately downstream.
- *Present derived numbers as sustainment data without the marker.*
  Rejected — that is the ADR-0017 failure mode applied to derived data.

## Related

- **ADR-0010** — Feed Integration Strategy. Derived sustainment is
  feed-agnostic Silver, same as any measured feed.
- **ADR-0013** — Physical Quantity Consistency. Derived values are
  Quantity-typed, same as measured; also the precedent for the
  forward-looking `confidence` field ruling.
- **ADR-0014** — Restate vs Faust Placement. The cumulative / rate
  aggregations belong in Faust.
- **ADR-0006** — Persistence / Computation Model Separation. The wear
  models are pure-Python, framework-free, same discipline as fusion
  `rules.py`.
- **ADR-0022** — Hierarchical Aggregation Is the Architecture. The
  `derived-sustainment` output and the accumulator Table are
  provenance-shaped and per-asset-keyed.
- **ADR-0017** — UI Mock Components Self-Identify. The measured-vs-derived
  COP treatment is the same honesty principle applied to derived data.

## Notes for future maintainers

- This ADR was a "Proposed — stub" through Phase 4; Phase 5 fills it in and
  moves it to Accepted. The one substantive correction from the stub: there
  is no System A calibration oracle — see [No oracle — by
  design](#no-oracle--by-design).
- The oracle / validation phase is **AFSIM / VR-Forces-gated** and
  deliberately downstream. When it lands, the `confidence` field and the
  `MEASURED` half of the provenance marker get real meaning; until then
  they are forward-looking placeholders.
- The Phase 4b `TelemetryCharts` empty state was deliberately worded to
  describe a *current limitation* ("derived prognostics … not yet wired"),
  not a permanent fact — this stage fills that slot.
