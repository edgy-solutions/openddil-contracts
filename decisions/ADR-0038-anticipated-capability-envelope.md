# ADR-0038: Anticipated capability envelope — constraints, not a roadmap

## Status

Accepted — 2026-08-12. **The capabilities in this ADR are anticipated,
not committed. The accepted position is the constraint set, not the
capabilities.**

That distinction is the whole document. A roadmap entry saying *"someday:
advisory generation"* is inert — it tells nobody what not to do. What is
binding here is the numbered constraint list in §6: properties current
work must not violate, each verified to cost nothing today or with its
cost stated. If the anticipated capabilities are never built, the
constraints were still cheap and still correct. If they are built, the
constraints are why they were buildable.

## Context

The concern this answers is not *"we might lose track of these ideas."*
Losing track is a memory problem, and this project has instruments for it
(`GENERALIZATION-DEBT.md`, follow-up rows, phase documents).

The concern is **foreclosure**: three layers of configurable machinery,
each making a locally sensible assumption, collectively making a
capability unbuildable without rework. Nobody decides to foreclose. It
happens because the assumption is invisible at the layer that makes it —
an analytics registry that types its outputs as *observations* is not
obviously ruling out advisories; it is just being specific.

The project has the right instrument for this, twice proven. ADR-0033's
five do-not-harden constraints (*nothing may assume strictly-tree data
flow*) and ADR-0034's four (*no new hardcoded detectors; bindings touched
by in-flight work are interim*) are exactly this move: record the future
property as a constraint on present work, then verify the constraint
costs nothing today. Both were recorded **pre-violation** and both have
held.

The timing is what makes this worth writing now rather than later. Arc 1
is templating tier nodes; the analytics engine (ADR-0034) is designed and
fenced; the process plane is a named future arc with a reference
implementation. That is precisely the moment when shapes get fixed — a
configurable layer, once it has users, is harder to widen than a
hardcoded one, because widening it is a contract change rather than an
edit.

## 1. Where the system sits — ISO 13374 block mapping

ISO 13374 decomposes condition monitoring into six functional blocks plus
an information-presentation layer. It is the standard vocabulary for
*"how far along the condition-based chain does this system go?"*, which
is the first structural question any reader asks, and the project has
never answered it in one place.

**This mapping is new analysis, written for this ADR.** No prior document
claims 13374 alignment, and nothing in the codebase references it. It is
a reading of what exists against a standard's vocabulary, not a
conformance claim.

| Block | State | What backs the classification |
|---|---|---|
| **1 — Data acquisition** | **Implemented** | `sensor-ingest`, the DIS sidecar, `redpanda-connect` ingress; ADR-0030's two-stage ingress makes new sources a definition file plus a mapping |
| **2 — Data manipulation** | **Implemented** | Bloblang structure→Silver semantics; `faust-edge` windowing; ADR-0013 Quantity normalization; ADR-0026's decomposition of source vocabularies onto canonical axes |
| **3 — State detection** | **Implemented** | `logistics-fusion` evaluators emitting `ConstrainingFactor` per non-nominal axis; `cm-service` compliance state; `assetTier` liveness classification |
| **4 — Health assessment** | **Partial** | Severity roll-ups (`overall_severity`, `overall_status`) and the CM/operational quadrant model give an *assessed condition*. What is absent is **diagnosis** — fault-cause attribution. The system says *what is wrong*, not *why* |
| **5 — Prognostics assessment** | **Partial — mechanism built, prediction not** | ADR-0020's derivation engine is **built and closed** (Phase 5): wear accumulators, remaining-life fractions, `ORIGIN_DERIVED` stamping. What is missing is a **time horizon with uncertainty** — the engine reports *fraction remaining against authored coefficients*, not *fails at H+N, ±M*. Coefficients are unvalidated by design (AFSIM / VR-Forces gated) and `confidence` is an acknowledged placeholder |
| **6 — Advisory generation** | **Not implemented** | No component produces a recommended action. See AE-1 and AE-2 — an existing ADR claims otherwise, and one unstructured field looks like the seat |
| **Information presentation** | **Implemented** | The COP, governed by ADR-0035's claim classes |
| **External system interfaces** | **Implemented, reference-only** | Egress connectors; `CmEvent.work_order_ref` carries a foreign reference to an **externally created** work order. The system points at maintenance actions; it does not originate them |

The honest one-line summary: **OpenDDIL implements condition-based
monitoring through health assessment, with prognostic mechanism but not
prognostic prediction, and no advisory generation.** Blocks 1–3 solid, 4
partial by absence of diagnosis, 5 partial by absence of horizon, 6
absent.

## 2. The permanent boundary — course of action

**Operational course-of-action generation and analysis are permanently
outside the system boundary. This is an architectural limit, not a
sequencing statement — not "not yet."**

The distinction that makes this tractable:

- **Operational COA analysis** — will this scheme of manoeuvre work, what
  does an adversary do, what are the risks to force and mission.
  **Never.** Out of scope permanently.
- **Sustainment feasibility analysis** — can a proposed operation be
  supported: do the required assets exist, are they mission capable, is
  there enough of what they consume, can the maintenance load be
  absorbed. **Logistics.** Anticipated (§4), inside the boundary.

Two reasons the limit is architectural rather than a matter of appetite:

**Adoptability.** A logistics system that stays a logistics system is
adoptable by the organizations that own logistics. One that begins
evaluating schemes of manoeuvre is competing with the staff process it
should be feeding, and becomes a political object rather than a tool.

**The safety bar changes class.** *Wrong readiness data leading to a bad
human decision* and *a system asserting that a course of action is
supportable* are different hazard classes, not different magnitudes. The
first is decision support with a human in the loop reading a state the
system claims only what it can support (ADR-0035). The second is
decision assertion, and it carries an obligation to be right that nothing
in this architecture currently discharges — no validated coefficients, no
demand model, no uncertainty semantics.

**Why the clause is here and not only in ADR-0011.** A configurable
analytics plane plus a configurable process plane is precisely the
machinery someone could use to drift across that line **without anyone
deciding to** — a registered detector, a workflow step, a threshold, and
the system is scoring options. ADR-0011 states positioning against
commercial strategic tools; this states a limit against a capability
class, in the document that governs the machinery capable of reaching it.
Constraint C7 is its enforceable form.

## 3. Anticipated capability — CBM completion (blocks 5 and 6)

**What it is.** Prognostic prediction (a time-to-limit horizon with an
uncertainty band, replacing the current fraction-remaining reading) and
advisory generation (a recommended action attached to an assessed
condition, with the provenance to justify it).

**What it is not.** Not automated maintenance execution. Not work-order
origination inside OpenDDIL — the external system of record keeps that,
and `work_order_ref` stays a reference. Not validated life prediction
until the AFSIM / VR-Forces gate ADR-0020 defines is passed; a horizon
computed from authored coefficients is a horizon-shaped number and must
render as one (ADR-0035 class 1's *modelled-not-measured* treatment).

**Substrate it composes.** The derivation engine and its accumulator
tables; `ORIGIN_DERIVED` and the `confidence` field already present in
`ConstrainingFactor`; the detection-event envelope; the registered-unit
mechanism with `model_artifact_hash` stamping for ML units.

**Constraints it imposes:** C1, C2, C4.

**Trigger to schedule.** Either half moves independently. Prognostic
prediction is gated on the validation phase ADR-0020 already names
(AFSIM / VR-Forces), because a horizon without validated coefficients
overclaims in a way a fraction does not. Advisory generation is gated on
a deployment asking for it — and on C4 being settled first, since
advisory provenance is the expensive thing to retrofit.

## 4. Anticipated capability — sustainment feasibility analysis

**What it is.** Given a proposed operation expressed as demand — these
units, these platforms, this duration, this tempo, these locations — an
answer to *can it be supported*, with the margin and the binding
constraint named. The useful output is rarely yes/no; it is *"supportable
with N% margin"* or *"fails at H+40 on a named consumable."*

**What it is not.** Not COA generation (§2). Not COA comparison as
operational recommendation — evaluating two demand profiles for
supportability is arithmetic over supply; ranking courses of action is
not. Not a planning tool: the demand comes from a planner, the system
does not propose it.

**Substrate it composes.** This is the point of the entry — it is
composition of existing planes rather than new science. Per-asset
readiness with constraining factors; consumable levels; configuration
compliance; wear trends; tier-scoped rollups; the asset registry's
asset→node lineage; releasability labels (a feasibility answer is
data-scoped like any other read). The registered-unit mechanism supplies
parameterization, versioning, tier placement, and provenance stamping for
free.

**The gap that defines it: there is no demand model.** Nothing in
OpenDDIL represents a proposed plan. No task-to-asset assignment, no
consumption profile, no duration. Feasibility is supply versus demand and
the system models supply only. **This ADR names that gap and does not
design it** — specifying a demand model now would be the
premature-abstraction failure this ADR series has repeatedly avoided, and
the shape should be derived from open planning vocabularies when it is
scheduled, not invented here.

**Constraints it imposes:** C3, C5, C6, and C7 as its boundary.

**Trigger to schedule.** A deployment posing the question against real
data, plus GD-10's capability-item shape being declared (AE-5) — a
feasibility answer counts munitions, and counting on an undeclared shape
inherits and multiplies its fragility.

## 5. Anticipated capability — advisory provenance

**What it is.** The provenance discipline extended to actionable output.
The moment a system says *"you should do X"*, ADR-0035's claims-vs-sources
rule needs an answer for recommendations: which model, which
configuration, which inputs, at what confidence — **and what the advisory
is not claiming.**

**What it is not.** Not a new mechanism. ADR-0034 already stamps
detections `{detector, version, config_hash, tier}` and ML detections
additionally with `model_artifact_hash`. This is that shape, with the
additional fields an actionable output needs, decided **before** the
first advisory exists.

**Why it is a separate entry rather than a footnote to §3.** It is
cross-cutting and it is the cheapest thing on this list to foreclose. If
the provenance shape is fixed around observations only, adding advice
later is a migration under live consumers — the exact cost ADR-0020
avoided by carrying `confidence` from day one as an acknowledged
placeholder. That precedent is the argument: **a forward-looking field
costs nothing while the shape is cheap and costs a migration afterwards.**

Advisories are the stricter case for a specific reason: a detection that
is wrong produces a misleading display, which ADR-0035's treatments are
designed to bound. An advisory that is wrong produces an action. The
provenance has to support after-the-fact answering of *why was this
advised*, which is the same question `model_artifact_hash` exists to
answer one layer down.

**Constraints it imposes:** C4.

**Trigger to schedule.** Before the first advisory-producing unit is
registered — not after. This is the one entry whose trigger is a
precondition rather than a demand signal.

## 6. Do-not-harden constraints — the binding part

Each constraint names what present work must not assume, and states its
cost today.

**C1 — The detection-event envelope must not be finalized in a shape
that cannot carry a recommendation, a horizon, or an uncertainty band.**
ADR-0034 §Wire shapes specifies the envelope as *event type, subject,
severity or score, window/time basis, provenance stamp*. Every field
there describes an **observation that has occurred**. A prognostic output
needs a *time basis in the future* and a *band*; an advisory needs an
*action* and a *rationale*. Not designed here — the requirement is that
the envelope be extended or explicitly assessed against these three
before it ships.
*Cost today: zero.* The envelope is designed and unbuilt.

**C2 — The analytics registry's output-type vocabulary must be open.** A
registered unit declares what it produces. If that vocabulary is fixed to
severities and scores at registration-contract time, advisory and
forecast units are unregisterable without a contract change.
*Cost today: zero.* The registry does not exist.

**C3 — Analytics inputs must not be typed as observed state only.** The
composition type system in ADR-0034 classifies *operations* as
propagating or terminal. It must not additionally encode a law that a
unit's **inputs** are streams of observations — a feasibility unit reads
a proposed plan alongside telemetry, and a unit that reads reference data
(the asset registry, a baseline) already sits awkwardly under that
reading.
*Cost today: zero, and it removes a latent restriction that would have
bitten reference-data-reading units anyway.*

**C4 — Advisory provenance must not inherit the detection stamp shape by
default.** Where a stamp shape is being fixed, the actionable-output case
is assessed explicitly rather than assumed to be the same. The existing
attractor is named in AE-2 and must not become the model.
*Cost today: near zero if decided now; a migration under live consumers
if deferred past the first advisory.* This is the constraint with a real
clock on it.

**C5 — The process plane's workflow subject must not be assumed to be an
asset.** ADR-0034's process-plane seam is described as *"when severity
goes CRITICAL on an asset of class X, open workflow Y"*. A sustainment
feasibility assessment is a workflow whose subject is a **plan**, not an
asset, and whose steps carry a planning artifact through. The
one-directional narrow seam is right and is not what this touches.
*Cost today: zero.* The process plane is a fenced future arc.

**C6 — Feasibility over rollups is rollup-of-rollups, so the composability
gate binds it.** GD-05 / AUDIT-2026-08-07 records that `region_top_factors`
is genuinely non-composable — top-N truncation is lossy and compounds per
tier, so a factor ranking sixth in every child is invisible to the parent.
A feasibility answer computed at a parent tier over child rollups is
exactly the consumer that gate was written for. This constraint adds no
new work; it names a second reason the existing gate must not be waived.
*Cost today: zero.* Already tracked.

**C7 — Nothing in the analytics or process plane may assert that a course
of action is supportable, advisable, or executable.** The plane may
compute supply-side sufficiency against a stated demand and report the
margin and the binding constraint. It may not rank options, recommend a
course, or emit an output whose semantics are *"do this one."* A
configured detector or workflow step that does so is out of boundary
regardless of who configured it.
*Cost today: zero.* Nothing does this. The constraint exists because the
machinery to do it accidentally is being built.

## 7. Registered gaps — where the architecture is already awkward

**AE-1 — ADR-0011 claims a capability the system does not have.** Its
Decision section lists *"dynamic work order generation"* among what
OpenDDIL handles in the operational sustainment loop. Nothing generates
work orders. The only work-order shape in contracts is
`CmEvent.work_order_ref` — an optional **reference to an externally
created** order — and `AsMaintainedState.applied_by_work_order`, likewise
a foreign reference. The contract shape points the opposite way from the
claim: the system records that an external action happened, it does not
originate one. This is a claims-vs-sources defect at the ADR layer, in a
document whose audience is positioning. *Fix shape: amend ADR-0011 to
state the reference relationship, or move the claim into this ADR's §3 as
anticipated. Not amended here — it is another document's text and this
ADR's job is to record the finding.*

**AE-2 — The only recommendation-shaped field is unstructured and
human-authored.** `ManualDiscrepancyRaised.recommended_action` is a bare
`string` on a manually-raised event: no producer, no version, no
confidence, no statement of what it does not claim. It is the natural
attractor for the first machine-generated advisory precisely because it
already exists and already means the right thing in English. Reusing it
would give machine advice the provenance profile of a free-text note.
This is what C4 exists to prevent, and it is a live risk rather than a
theoretical one.

**AE-3 — Supply-only.** No demand model of any kind exists, named in §4,
deliberately not designed.

**AE-4 — Prognostics report a fraction, not a horizon.** ADR-0020's
engine reports remaining-life fractions against authored coefficients
with a placeholder `confidence`. Block 5 is therefore *mechanism built,
prediction absent* — and the gap is not plumbing, it is that a horizon
implies a validity claim the unvalidated coefficients cannot support.

**AE-5 — GD-10 is a prerequisite for §4 as well as for munitions work.**
The capability-item shape is undeclared, defined de facto by whichever
deployment integrated first. A feasibility answer counts consumables;
counting on an unowned shape inherits its fragility. GD-10 already names
itself a hard prerequisite of stockpile work; this records a second
dependent.

**AE-6 — Diagnosis is absent and is not on this list.** Block 4 is partial
for want of fault-cause attribution, and no anticipated-capability entry
covers it. That is a deliberate omission rather than an oversight —
diagnosis needs failure-mode reference data the system does not carry —
but it should not be read as *"block 4 is fine."*

## What this ADR did not establish

Per ADR-0037 clause 6.

- **The 13374 mapping is a reading, not a conformance assessment.** It was
  derived from ADRs and a targeted source read, not from a clause-by-clause
  comparison against the standard text. Block boundaries are interpreted.
- **No sweep for foreclosure was run.** The constraints come from reasoning
  about three named capabilities against known designs. The codebase was
  **not** swept for existing assumptions that already violate C1–C7 — this
  is the same limit UD-6 states for ADR-0036's register, and it means the
  absence of a violation here is not evidence of none.
- **Nothing outside the core contracts and OSS services was examined.**
  Deployment overlays, egress connectors, and the reasoning-plane seams
  (ADR-0031) were not read for capability-envelope implications.
- **No cost was verified by attempting a change.** The "cost today: zero"
  claims rest on the components in question being unbuilt or unshipped,
  which is checkable, rather than on a trial edit.

## Consequences

**Pros**

- Present work gets a checkable list rather than an intention. C1–C7 are
  the kind of statement a reviewer can hold a design against, which is
  what made ADR-0033's and ADR-0034's constraint lists effective.
- The boundary clause becomes enforceable at the layer that could breach
  it. A limit stated only in positioning material does not reach the
  person configuring a detector.
- The block mapping answers a structural question in one place, with the
  partials stated as partials — which is more useful than a maturity
  claim and considerably more defensible.
- Every anticipated capability composes existing planes. That is the
  strongest available evidence that the layers being built are cut in the
  right places, and it is worth noting as a property rather than a
  coincidence.

**Cons**

- An anticipated-capability document invites being read as a commitment,
  and the more concrete the constraints the more it reads that way. The
  Status section is the mitigation and it is a weak one; the honest
  position is that this risk is accepted because the alternative —
  constraints with no stated purpose — is worse.
- Constraints written before their capabilities can be wrong about what
  the capability will need. C1 in particular guesses at three fields a
  prognostic or advisory output needs. Mitigated by the constraints being
  *don't-preclude* rather than *do-build*: being wrong about the specific
  fields costs nothing if the envelope is merely kept extensible.
- This is the first document in `decisions/` whose subject is partly
  unbuilt. The series' value comes from recording real positions, and a
  reader who mistakes §3–§5 for a plan gets a wrong picture of maturity.

**Rejected alternatives**

- *A roadmap document listing future capabilities.* Rejected as inert: it
  records intent and constrains nothing, so it cannot prevent the failure
  it would be written to prevent.
- *Designing the demand model now, since §4 depends on it.* Rejected —
  premature abstraction, and the shape should come from open planning
  vocabularies at scheduling time. Naming that it will exist, and that
  nothing may assume its absence, is a different and cheaper act than
  specifying it.
- *Folding these constraints into ADR-0034 as constraints 5–8.* Rejected:
  ADR-0034's constraints all defend one property (analytics
  configurability). These defend a capability envelope spanning the
  analytics plane, the process plane, and the contracts, and two of them
  (C4, C7) have nothing to do with configurability. A constraint list
  that mixes purposes stops being checkable.
- *Stating the COA boundary as "not currently in scope."* Rejected
  deliberately. "Not yet" invites the drift; the whole reason for a clause
  is that the machinery makes crossing the line easy and undramatic.

## Related

- **ADR-0011** — strategic sustainment positioning; §2 extends its
  boundary discipline from tool-class competition to capability class,
  and AE-1 records that its work-order claim is not backed.
- **ADR-0020** — the prognostics derivation engine; block 5's *mechanism
  built, prediction absent* state, and the `confidence`-as-forward-looking
  -placeholder precedent that §5 argues from.
- **ADR-0034** — tier analytics as configuration; the plane C1, C2, C3 and
  C7 constrain, and the process-plane seam C5 constrains.
- **ADR-0033** — the do-not-harden constraint idiom this ADR follows.
- **ADR-0035** — information honesty; an unvalidated horizon and a
  machine-generated advisory are both claims requiring a basis, and class
  1's modelled-not-measured treatment is what a horizon renders as.
- **ADR-0037** — verification evidence; this ADR's did-not-establish
  section is clause 6 applied to itself.
- **AUDIT-2026-08-07** / **GD-05** — composability; C6 names a second
  consumer of that gate.
- **GD-10** — the undeclared capability-item shape; AE-5.
- **`PRINCIPLES.md` §Framework vs. instantiation** — the tell this ADR
  works against, one tense later: reasoning from what exists to what the
  framework permits, rather than from a deployment to a law.
