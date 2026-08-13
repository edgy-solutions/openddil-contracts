# ADR-0035: Information honesty in operator-facing surfaces

## Status

Accepted — 2026-08-11. **Standing engineering position.** Consolidating,
not introducing: most of what follows is already implemented behaviour
recorded across ADR-0017, ADR-0026, ADR-0032 and `PRINCIPLES.md`. This
ADR states it once, in one place, as a rule a new surface can be checked
against.

## Context

This project has enforced one rule, repeatedly, in six unrelated places,
without ever writing the rule down:

| Where it was enforced | What was almost shipped |
|---|---|
| ADR-0017 | Hardcoded fallback arrays indistinguishable from a working integration |
| `Inventory.tsx` empty state | A mock inventory that read as *"real data gone stale"* when the truth was *"feature not built"* |
| `assetTier.ts` | One silent-asset state, when there are two with different meanings |
| ADR-0032 §f | A severance banner that was the root's opinion of a site, shown at the site |
| `rules.py` CM cap | A configuration deviation rendering in mission-capability language |
| `MunitionsInventory.tsx` | A browser-session accumulator presenting as a durable stockpile record |

Each was found separately, fixed locally, and generalized (if at all)
into a one-line principle. `PRINCIPLES.md` §*Claims vs. sources* is the
closest existing statement — *"a component must claim only what its data
source supports"* — and it is one paragraph carrying six instances.

The cost of leaving it dispersed is not that any single surface is wrong
today. It is that the rule has to be **re-derived per component**. A new
panel's author has no single document to check against, so the question
*"is this label honest?"* gets asked by review, by accident, or not at
all. Five of the six rows above were caught by someone looking at the
running system with fresh eyes, which is not a repeatable control.

There is a second reason to state it plainly. Displayed state is where
this system meets a human decision. Every other honesty discipline here
— provenance stamps, schema derivation, mock markers — exists to make
that final rendering trustworthy. Naming the property they serve makes
them legible as one system rather than six habits.

## Decision

**An operator-facing surface claims only what its data supports. Where
the support differs, the rendering differs.**

Concretely: a value's *basis* is part of the value. If two readings have
the same pixels and different bases, that is a defect, not a styling
choice.

### The six claim classes

Every rendered value falls into one of these. Each has a required
distinguishing treatment.

**1 — Not from the pipeline (mock / hardcoded / synthetic).**
Self-identifies, per ADR-0017: `const DEMO_MOCK = true`, a visible
`<DemoMockBanner>`, and a file-header comment naming what it waits on.
`grep -rn DEMO_MOCK` is the authoritative inventory; `test_34` asserts
the always-visible banners render.

*Adjacent case:* data that IS from the pipeline but is **modelled rather
than measured** carries a `SYNTHESIZED` badge with a hover explaining the
producing component and the topic (`Inventory.tsx`, `TelemetryCharts`).
This is a weaker claim than "mock" and a weaker claim than "measured",
and it renders as its own third thing rather than being rounded to
either neighbour.

**2 — Never observed (absent).**
Absence renders as absence, never as a zero, and the empty state says
*why it is empty* to the extent the code can distinguish. `Inventory.tsx`
carries two distinct empty states for exactly this reason — *"this asset
has no rows yet"* vs *"the table has no rows at all"* — because the
operator's next action differs.

The instrument-side form of this rule is ADR-0036's subject; this ADR
governs the rendering. Where a probe supplies a not-a-reading sentinel,
the surface must render it as not-a-reading: the buffer tile shows `—`
when `probe_healthy` is false rather than printing the sentinel or
coercing it (`Header.tsx`).

**3 — Observed but old (stale), and *why* it is old.**
`assetTier.ts` classifies silent assets into three tiers, and the
distinction between two of them is purely epistemic:

- `STALE` — silent past threshold, link up. *"We expected to hear from
  it, we didn't."* Slate outline: mute, unexplained.
- `COMM_LOST` — silent past threshold, the asset's edge link is severed.
  *"We know why we're not hearing from this."* Amber outline.
- `LOST` — silent past the long threshold. Drops out of the 3D scene,
  stays queryable and labelled in the pulldown.

Same underlying fact (no telemetry), two different things known about
it, two different renderings. This is the class in its purest form and
it is the model for the rest.

Recovery from a silent tier is gated by hysteresis
(`applyRecoveryHysteresis`) — downgrades fire immediately, upgrades
require N samples in a window — because a momentary reconnect that
flashes an asset back to ACTIVE is a claim the single sample does not
support. **Honesty is asymmetric on purpose: we are quicker to say we
have lost something than to say we have it back.**

**4 — Derived within the viewing session, not recorded.**
A value accumulated by the browser since page load carries that
qualifier in its own label, not in a footnote. `MunitionsInventory.tsx`
renders *"Expended since this browser session started. Derived from
observed ammo drops, not a durable stockpile record — a page reload
resets this to 0."*; the per-asset card says *"fired this session"*.

The rule: **a session-scoped accumulator never wears the noun of a
durable record.** "Expended" alone is a stockpile claim. "Expended since
session start" is an observation claim, which is what the data is.

**5 — Computed elsewhere, when the operator needs to know where.**
A tier's presentation states its own tier's truth as its own, and states
another tier's assertions as that tier's. ADR-0032 §f is the load-bearing
instance: the severance indicator now reports **the tier's own uplink,
as observed by the tier**, rather than the root's centrally-computed
opinion of that site — an opinion which was, by construction,
unavailable at the site exactly when it mattered.

Generalized: any indicator whose subject is *"the state of the link
between me and someone else"* is rendered from the local side of that
link, or it is not rendered.

**6 — One axis's vocabulary never borrowed for another axis.**
ADR-0026 established that entity posture is three orthogonal axes, and
that collapsing them is lossy. The corollary at the presentation layer:
a value derived from one axis may not be rendered in another axis's
words. A configuration-management deviation is not a mission-capability
statement, so `rules.py` caps CM-derived severity at `DEGRADED` — the
factor stays visible in the drill-in, contributes to worst-of, and never
solo-drives the display into "cannot perform mission" language it has no
basis for.

### The check

One question, answerable in front of the running UI without reading code:

> **What would have to be true for this pixel to be honest — and does
> the data actually establish it?**

If the answer requires an assumption the data does not carry (*it's
probably current*, *zero probably means none*, *this is probably the
whole record*), the rendering is overclaiming and the fix is a
distinguishing treatment, not a caveat elsewhere on the page.

### What this rule is not

- **Not a mandate to render uncertainty everywhere.** A value with solid
  support renders plainly. Decorating everything defeats the purpose:
  if every tile has a badge, no badge is a signal.
- **Not a demo-suppression toggle.** ADR-0017 already settled this — a
  demo that hides which parts are mock is the failure mode the marker
  exists to prevent. If a specific engagement needs badges suppressed,
  that is a deliberate build-time decision with a named owner, not a
  default.
- **Not a substitute for fixing the data.** A well-labelled wrong number
  is still a wrong number. The label is honest about provenance, not
  about correctness.

### The check's subject is a value, not a component

*(Added 2026-08-12, after AUDIT-2026-08-12 found the second instance.)*

**A component can pass this ADR's check while carrying a dishonest field,
because the check was asked once of the component instead of once of each
value it renders.** This is a limit on the check above, stated here
rather than discovered a third time.

Two instances, and what makes them sharp is that **both components are
exemplary**:

- **IH-1** — `Header.tsx` handles its not-a-reading sentinel correctly:
  `probe_healthy` false renders `—`, never the raw `-1`, never a coerced
  number. That is class 2 done right. One line above it,
  `status?.bridge_group_lag ?? 0` renders a confident zero produced by
  having no reading at all.
- **F3 / IH-6** — `LogisticsStatusCard.tsx` carries a syncing notice that
  never falls through to empty copy, a genuinely-empty state, and a
  backfill state that renders its own rationale. Three honest states in
  one component. The *"Projected mission-capable"* row inside it renders
  a linear extrapolation on unvalidated coefficients as a bare duration.

And the sharpest form of it is at the component *boundary*:
`HqWorkOrders.tsx` was **renamed under ADR-0017** precisely because the
panel does not talk to a work-order system, with a file comment saying
so. The honesty of the **panel** was reviewed and corrected. The
**advisories rendered inside it** — machine-generated, unprovenanced —
were never in scope, because the subject of that review was the panel.

*The rule that follows:* **review the field.** Each rendered value is
asked *what would have to be true for this pixel to be honest*
separately, including values inside a component that has already passed.
A component-level verdict is a summary of per-field verdicts, never a
substitute for them.

*What it costs, stated plainly:* more review surface, roughly by the
average field count of a panel — and the cost is real, because the
components most worth reviewing are the dense ones. Two mitigations, both
partial: the six classes make each field's question fast to answer once
the habit exists, and most fields fall into "support is solid, render
plainly" in a sentence. This does not make the check cheap; it makes it
correct. **The alternative is a discipline whose pass rate is highest
exactly where it is applied most carefully**, which is what these two
instances are.

## Registered gaps

Per this project's discipline, positions the system does **not** yet
hold are registered here rather than written as if they were true.
Each is a real, currently-open divergence from the rule above.

**IH-1 — Pre-sync buffer tile renders a plausible zero.**
`Header.tsx:112` (and its `HqHeader` / `RegionalHeader` twins) computes
`const lag = status?.bridge_group_lag ?? 0`. Before the first Electric
shape sync arrives, `status` is null, `probeDown` is false, and the tile
renders **`0 MSGS`** — a confident reading produced by having no reading.
The window is short (one shape sync) and the failure is benign, but it
is precisely class 2, in the same component whose sentinel handling is
otherwise correct. *Fix shape: a third render state for "no reading
yet", distinct from both `—` (probe down) and a number.* Not fixed here.

**IH-2 — The CM-red / ops-green quadrant has no first-class rendering.**
The `DEGRADED` cap in `rules.py` (2026-07-14) is an interim measure that
keeps the CM factor from overclaiming, at the cost of collapsing
*"operating under a configuration waiver"* into plain `DEGRADED`
alongside genuinely degraded operation. The honest state exists in the
domain and has no enum value; the follow-up is an explicit
`OPERATING_WITH_CM_WAIVER` value so the quadrant is first-class at every
tier. **This ADR does not claim the four quadrants are rendered
distinctly today. Three of four are.**

**IH-3 — `tactical_events.severity` mixes two vocabularies in one
column.** `handlers/tactical_events.py::_SEVERITY_KEYS` extracts, in
priority order, `severity` → `current_status` → `overall_severity` →
`overall_status`. The third is logistics severity
(`LOGISTICS_SEVERITY_*`); the fourth is configuration status
(`CONFIG_STATUS_*`). Both land in one `severity` column with nothing
recording which axis produced the value — so a consumer filtering the
event feed by severity is filtering across two scales that do not
compare. This is class 6 at the storage layer rather than the render
layer, which is why it survived a render-layer sweep. *Fix shape: carry
the producing axis alongside the value, or normalize at extraction.*
Not fixed here.

**IH-5 — The most-derived value in the system carries the weakest
provenance.** *(AUDIT-2026-08-12 F4. Producer-side; distinct from IH-6,
which is the render.)*

`rules.py::_eval_mtbf` is the one evaluator whose output is purely
derived — a linear extrapolation of a wear-trend slope, on coefficients
ADR-0020 documents as authored placeholders. It constructs its
`ConstrainingFactor` setting neither `origin` nor `confidence`, so the
factor emits `ORIGIN_UNSPECIFIED` and `0.0`.

Both defaults are *honest* in the proto3 sense — ADR-0020 chose them
deliberately so that evaluators which had not been made provenance-aware
would claim nothing rather than claim wrongly. **The inversion is that
the discipline landed everywhere except its most load-bearing point.**
The derived-sustainment evaluator sets `ORIGIN_DERIVED` explicitly;
measured values are stamped; the one value that is a *projection built on
an extrapolation of placeholders* is the one that says nothing about
where it came from.

*Why it matters beyond tidiness:* `origin` is the field a surface would
read to apply class 1's modelled-not-measured treatment. **IH-6 cannot be
fixed properly without this** — the renderer has no signal to branch on,
so a basis marker would today have to be hardcoded per field rather than
driven by the data. Producer-side stamp first, render second.

**FIXED 2026-08-12.** `_eval_mtbf` now stamps `origin = ORIGIN_DERIVED`
and `confidence = _MTBF_ASSERTED_CONFIDENCE` (0.2), a named constant whose
comment states that it is **asserted, not computed**, and why no
computation is available: linear extrapolation of a single trend line
carries no intrinsic uncertainty estimate, and the accumulators keep
`(mean, count)` — enough to merge, not enough for dispersion. The path to
a real number, and the rule that **confidence-kind must be declared
alongside confidence-value**, are recorded in
[ADR-0020 §Confidence staircase](ADR-0020-prognostics-derivation-stage.md).

*Guard:* `test_mtbf_factor_stamps_derived_provenance`, **run red against
the unstamped evaluator before being trusted** (ADR-0037 §3) — it failed
on `origin == 0` vs `ORIGIN_DERIVED == 2`, which is precisely the state it
exists to prevent recurring. `origin` is asserted by identity rather than
truthiness, since `ORIGIN_UNSPECIFIED` is `0` and a truthiness check would
fail open on exactly the case that matters. 76 tests pass.

**IH-6 — A horizon renders as a bare duration with no basis.**
*(AUDIT-2026-08-12 F3. Render-side; the consequence of IH-5.)*
`LogisticsStatusCard.tsx` renders *"Projected mission-capable"* as a
formatted duration with no basis marker, no derived badge, and no
tooltip. The value reaches it from `_eval_mtbf` via
`projected_mission_capable_remaining` — a linear extrapolation on
unvalidated coefficients, presented as a plain fact. This is class 1's
*modelled-not-measured* case, and the `SYNTHESIZED` treatment (or an
equivalent for projections) is absent. See the review-unit note above for
why it survived: the component around it is otherwise exemplary.

**FIXED 2026-08-12, driven by IH-5's stamp.** A `DERIVED` badge in the
same amber vocabulary as `SYNTHESIZED` now sits beside the horizon, and
**no displayed value changed — only its basis became visible.**

Two properties of the implementation are the point:

- **Keyed off `origin`, not off the field.** `horizonSource()` recomputes
  the same minimum fusion's `compose_status` used, finds the factor that
  produced the horizon, and reads *its* stamp. When another evaluator
  starts projecting, or a registered analytics unit replaces the rule, the
  marker follows the data with no frontend edit. A per-field condition
  would have worked exactly once.
- **Hover text composed from provenance, not written as a sentence.**
  `lib/valueBasis.ts` renders whatever stamp fields are present, with a
  generic pass for keys it has no opinion about — so `detector`,
  `version`, `config_hash`, `model_artifact_hash` (ADR-0034) and the
  uncertainty band (ADR-0038 AE-4) appear **without a frontend change**
  once they appear in the JSON.

*Recorded because it will be asked again: the marker is permanent, not a
simulation artifact.* A remaining-life horizon is modelled **by
construction** — nobody measures *"37 hours until limit"*; it is a
projection under assumptions, and real telemetry improves its **inputs**,
never the output's nature. A validated Weibull fit on real failure history
is still a model. What evolves is the marker's *content*
(*"linear extrapolation, confidence asserted"* →
*"weibull-v3.2 · interval ±6h @80%"*), never its *presence*. Removing it
once the numbers look trustworthy would present a projection as a
measurement — the decision-assertion hazard ADR-0038 §2 fences against,
and the reason that boundary is an architectural limit rather than a
maturity stage. The note lives in `valueBasis.ts` as well, where the next
person to touch the badge will meet it.

*Also confirmed:* `constraining_factors` persists as JSONB, so the stamp
reaches the UI with **no projector or schema change** — the fix is one
producer line, one helper, one badge.

**IH-4 — "Which tier am I looking at?" is answered by the URL, not by
the surface.** With three fixed views (GD-04) and the tier-presentation
node serving a per-tier instance, the page does not itself assert which
node's truth it is rendering. Today the deployment makes this
unambiguous and the runbook's rung (iii) depends on the operator knowing
which browser tab is the pilot site. The claim becomes checkable only
when presentation is tier-parameterized; recorded now so the
parameterization work inherits the requirement rather than discovering
it.

## Consequences

**Pros**

- A new surface has one document to check against, and the check is
  runnable in front of the UI without reading the code that produced it.
- The existing markers (`DEMO_MOCK`, `SYNTHESIZED`, tier outlines, the
  `—` sentinel render, session qualifiers) stop being six local
  conventions and become one vocabulary with six members. A reviewer who
  learns one learns the set.
- The rule is falsifiable per surface, which is what makes the registered
  gaps above possible to state as gaps rather than as omissions.

**Cons**

- Distinguishing treatments cost design attention, and there is a real
  ceiling: past some number of distinct states an operator stops reading
  them. Mitigated by keeping the classes to six and by the "render
  plainly when support is solid" carve-out — but this is a genuine
  budget, not a free property.
- The rule is enforced by review and by the class-specific mechanisms
  (grep, `test_34`, the sentinel contract). There is no single automated
  check for "this label overclaims", and there is unlikely to be one.

**Rejected alternatives**

- *A single per-panel "data quality" indicator.* Rejected: it collapses
  the six classes back into one, which is the ADR-0026 mistake at the
  presentation layer. "Mock", "never observed", "stale, cause unknown",
  and "session-derived" prompt four different operator actions.
- *Documenting provenance in a data dictionary instead of on screen.*
  Rejected for ADR-0017's reason: the failure mode is a person looking
  at a screen forming a belief. A signal that does not reach that person
  at that moment is not a control.
- *Rendering the sentinel value itself (`-1`) as the honest treatment.*
  Rejected: a negative message count is a distinguishable value, which
  is why the probe writes it, but it is not a **legible** one. The
  sentinel's job is to survive the wire; the surface's job is to say
  "no reading". `—` does that; `-1` makes the operator infer it.

## Related

- **ADR-0017** — UI mock components self-identify. Class 1; the
  precedent this generalizes.
- **ADR-0026** — orthogonal-axis posture model. Class 6's origin: the
  argument against collapsing independent axes, restated for rendering.
- **ADR-0032 §f** — the severance-indicator inversion. Class 5's
  load-bearing instance.
- **ADR-0036** — failure detectability. The instrument-side companion:
  this ADR governs how a not-a-reading is *rendered*; that one governs
  how a probe *produces* one.
- **ADR-0029** — releasability. A filtered view is an honest view of
  what the viewer may see; the deny-unlabeled ordering gate exists
  because a policy-emptied screen and a genuinely empty screen are
  byte-identical to the operator.
- **`PRINCIPLES.md` §Claims vs. sources** — the one-line form. This ADR
  is its expansion; the principle stays as the portable version.
- **`PRINCIPLES.md` §A probe must fail distinguishably from its own
  zero** — the same disease one layer down.
- **GD-04** (`GENERALIZATION-DEBT.md`) — three fixed views; IH-4's
  owning row.
