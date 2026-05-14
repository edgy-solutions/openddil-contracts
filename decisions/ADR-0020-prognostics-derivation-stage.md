# ADR-0020: Prognostics Derivation Stage

## Status

Proposed — 2026-05-14 — **Phase 5 candidate.** This is a stub: it records
the decision shape and scope boundaries so the work is well-formed when
Phase 5 picks it up. No derivation work has started.

## Context

The Phase 4b edge view surfaced a real limitation: DIS-sourced assets
(e.g. `dis:1:1:4773` / IRON-01) show a "no sustainment telemetry" empty
state in the prognostics panel. The DIS Entity State PDU carries
kinematics — position, velocity, attitude, articulation parameters — but
no thermal / fluid / wear metrics. Measured sustainment reaches OpenDDIL
only via the sim-a and proprietary (CBM+) feeds.

That empty state is accurate about the *wire format* but it should not be
read as a law of nature. A substantial amount of sustainment and
prognostics signal is **derivable from kinematic history**:

- cumulative distance → track / road-wheel wear
- operating hours → time-based maintenance intervals
- speed / acceleration profile → drivetrain stress, hard-accel counts
- terrain integral from pitch / roll → suspension stress
- articulation parameters (if the feed populates them) → turret / gun
  actuator cycle counts
- rounds-fired from Fire / Detonation PDUs → ammo consumption, barrel life

None of this is computed today. The DIS feed's articulation and
Fire/Detonation PDUs are currently unused.

## Decision

Introduce a **Prognostics Derivation Stage**: a pipeline stage that turns
kinematic history into sustainment *estimates*, populating the **same
Silver `sustainment.*` fields** a measured CBM+ feed would populate.

The derivation output is **feed-agnostic per ADR-0010**. The fusion engine
(`logistics-fusion-service`) treats derived and measured sustainment
identically at the contract level — a derived `fuel_remaining` Quantity
and a measured one are the same proto field. Derivation is an additional
*source* of sustainment data, not a parallel schema.

### Design points

- **Pure-Python derivation logic**, same boundary discipline as the
  fusion engine's `rules.py` (ADR-0006): the wear models are framework-free
  functions; Faust/Kafka plumbing wraps them, never leaks into them.
- **Faust windows are the natural home** for the cumulative / rate
  aggregations the models need — cumulative distance, operating-hours
  accrual, traverse-cycle counts, hard-acceleration counts. ADR-0014's
  placement guide puts continuous windowed aggregation in Faust.
- **A provenance / confidence marker on each sustainment value**
  distinguishes `MEASURED` from `DERIVED`. This is a contract addition
  (a field on the sustainment proto, or a parallel provenance map) — its
  exact shape is a Phase 5 design task. Downstream consumers and the COP
  must be able to tell the two apart.
- **Fire / Detonation PDU ingestion is in scope.** Rounds-fired is a
  high-value sustainment signal (ammo consumption, barrel life) and is
  currently ingested by nothing. The derivation stage is the natural
  consumer.

### Calibration and the built-in test oracle

System A emits **both** measured sustainment (fuel, ammo) **and**
kinematics for the same assets. That makes it a built-in calibration
oracle: the derivation engine can compute derived estimates from the
kinematic stream, compare them against System A's measured ground truth
for the same asset, and **calibrate its coefficients** where ground truth
exists. The calibrated coefficients then apply to pure-kinematic feeds
(DIS) that have no measured ground truth.

Crucially, this dependency is **already satisfied**: System A was
integrated in Phase 3.5. The derivation stage does **not** depend on
VR-Forces or any future constructive-sim milestone — it can begin as soon
as Phase 4 closes.

### Testing

- **System A calibration oracle** (above) — validates derived estimates
  against measured ground truth for assets that have both.
- **Scripted OpenDIS-based PDU generator** — provides
  authored-ground-truth scenarios for the pure-kinematic path, where there
  is no measured oracle. Example: "entity driven exactly 10 km, flat
  terrain, constant speed → derivation must report ~10 km cumulative
  distance and flat-terrain fuel burn." The authored scenario *is* the
  oracle.
- Evaluating a full DIS-compatible constructive sim (for richer demo
  scenarios and VR-Forces rehearsal) is **separate, lower-priority**, and
  should be preceded by a survey of currently-maintained open-source
  options. It is not a dependency of this stage.

### Scope discipline

Phase 5 picks a **small, defensible initial wear-model set**, calibrates
those against System A ground truth, and explicitly defers the long tail.

**Initial set (Phase 5):**
- distance-driven track wear
- operating hours
- rounds-through-tube barrel life
- terrain-integral suspension stress

**Explicitly deferred (post-Phase-5):**
- brake wear
- filter clogging
- fluid degradation
- fatigue cycling
- (and the rest of the long tail — added incrementally, each with its own
  calibration evidence)

## Open questions

- **Exact COP treatment of the measured-vs-derived distinction.** A
  derived sustainment value is an estimate; a measured one is an
  observation. The COP must surface that honestly — the same spirit as
  the ADR-0017 DEMO_MOCK banner, applied to derived data rather than mock
  data. Whether that is a badge, a confidence bar, a color treatment, or
  a filter is a Phase 5 (or Phase 5 COP-pass) design question.
- The exact shape of the provenance / confidence marker on the
  sustainment contract (proto field vs parallel map vs envelope).

## Consequences (anticipated — this is a stub)

**Pros**

- DIS-sourced assets gain prognostics instead of an empty panel.
- The dependency (System A) is already satisfied; the work is unblocked
  the moment Phase 4 closes.
- The calibration oracle is built in — derived estimates are validated
  against measured ground truth, not asserted.
- A later VR-Forces milestone inherits a working, calibrated derivation
  engine rather than building one reactively.

**Cons / risks**

- Derived estimates carry uncertainty that measured values do not.
  Mitigated by the provenance marker and honest COP treatment — but the
  distinction must not be allowed to blur.
- Scope creep risk on the wear-model set. Mitigated by the explicit
  initial-set / deferred-long-tail split above.

## Sequencing

**Proposed as Phase 5, immediately after Phase 4.** Rationale:

1. The dependency (System A measured sustainment + kinematics) is already
   integrated as of Phase 3.5 — no new feed integration blocks it.
2. It has a built-in test oracle (System A ground truth + scripted
   OpenDIS authored scenarios) — it can be built test-first.
3. It gives the later VR-Forces / constructive-sim milestone a working,
   calibrated derivation engine to inherit, rather than forcing that
   milestone to build derivation reactively under its own time pressure.

## Related

- ADR-0010 — Feed Integration Strategy. Derived sustainment is
  feed-agnostic Silver, same as any measured feed.
- ADR-0013 — Physical Quantity Consistency. Derived sustainment values
  are Quantity-typed, same as measured.
- ADR-0014 — Restate vs Faust Placement. The cumulative / rate
  aggregations belong in Faust windows.
- ADR-0006 — Persistence / Computation Model Separation. The wear models
  are pure-Python, framework-free, same discipline as fusion `rules.py`.
- ADR-0017 — UI Mock Components Self-Identify. The measured-vs-derived COP
  treatment is the same honesty principle applied to derived data.

## Notes for future maintainers

- This ADR is a **stub**. When Phase 5 picks it up, the Decision section's
  design points become real design tasks (the provenance-marker shape,
  the Faust window topology, the wear-model coefficient calibration
  procedure) and this ADR moves to `Accepted` with those decisions filled
  in — or is superseded by per-area ADRs if the design fragments.
- The Phase 4b `TelemetryCharts` empty state was deliberately worded to
  describe a *current limitation* ("derived prognostics ... not yet
  wired"), not a permanent fact, precisely so this stage has a clean
  narrative slot to fill when it lands.
