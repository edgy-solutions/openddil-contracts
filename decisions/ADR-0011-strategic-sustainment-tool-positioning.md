# ADR-0011: Strategic Sustainment Tool Positioning

## Status
Accepted, **narrowed**. **Amended 2026-08-12** — one capability claim
corrected; the positioning decision is unchanged. See
[Amendment](#amendment-2026-08-12).

**Superseded as the primary positioning statement 2026-08-15 by
[ADR-0039](ADR-0039-bridging-tactical-and-sustainment-planes.md).** This
ADR remains valid and in force on its own narrower question — *how does
OpenDDIL relate to commercial strategic sustainment modelling tools* —
and its answer (Position B, adjacent/complementary) is unchanged. It is
no longer the document that answers *what is OpenDDIL for*. Read ADR-0039
first; this one for the strategic-tools question specifically.

*Why the split rather than an expansion:* this ADR was written to settle
a competitive-positioning question against one class of tool. Stretching
it to carry the project's primary thesis is what produced the capability
claim retracted above — a positioning document accumulating assertions it
was never scoped to support.

## Context
The customer is currently using or evaluating commercial off-the-shelf (COTS) strategic sustainment modeling tools for long-term strategic analysis. A clear positioning strategy is needed to define how OpenDDIL relates to these classes of tools in the commercial portfolio, both competitively and architecturally.

## Decision
We officially adopt **Position B (Adjacent / Complementary)** as our positioning strategy.
- OpenDDIL handles the **operational sustainment loop**: real-time anomaly detection, configuration discrepancy alerting, work-order *correlation* against an external maintenance system of record, and sub-second decision cycles. (Amended 2026-08-12 — this bullet previously read "dynamic work order generation". See [Amendment](#amendment-2026-08-12).)
- Commercial strategic tools handle **strategic sustainment analysis**: life cycle cost modeling, sparing optimization, Level of Repair Analysis (LORA), and multi-decade availability simulation.

They operate on fundamentally different time horizons and inform different decision types.

## What OpenDDIL Does NOT Attempt to Replace
We will explicitly state that OpenDDIL does not replace:
- Life cycle cost modeling.
- Parametric availability simulation.
- Sparing level optimization at the program-of-record level.
- Level of Repair Analysis (LORA).
- Design-time supportability analysis.

## What OpenDDIL Provides that Strategic Tools Do Not
- Real-time edge ingestion.
- Streaming anomaly detection.
- Sub-minute decision loops.
- Configuration-aware operational alerts.
- Empirical reliability data feedback loops.

## Future Evolution
As OpenDDIL accumulates empirical reliability data from the field, that data can be fed into strategic modeling analyses as ground truth, replacing parametric estimates. This is a complementary integration vector, not a replacement vector.
- **Data Shape required for Tool Integration**: A periodic export of MTBF (Mean Time Between Failures) and MTTR (Mean Time To Repair) observations categorized per CI (Configuration Item) category.

## Sales & Positioning Guidance
- **Lead Statement**: "OpenDDIL complements your existing investments in strategic sustainment modeling."
- **Directive**: Do not initiate feature comparisons between OpenDDIL and specific commercial strategic tools.
- **Handling Dissatisfaction**: If the customer raises dissatisfaction with the outputs of their existing strategic tools, listen and document their pain points, but do not commit to replacing capabilities we do not currently possess in the core platform.

## Amendment 2026-08-12

**What changed:** the Decision section listed *"dynamic work order
generation"* among what OpenDDIL handles in the operational sustainment
loop. **Nothing in the system generates work orders**, and the contract
shape encodes the opposite relationship — `CmEvent.work_order_ref` and
`AsMaintainedState.applied_by_work_order` are both **foreign references
to orders created in an external system**. OpenDDIL records that a
maintenance action happened elsewhere and correlates its own
configuration state against it. It does not originate the action.

**Why it mattered enough to amend rather than annotate.** In ISO 13374
terms the claim describes **advisory generation** — block 6 — and this
system implements condition monitoring through health assessment with no
advisory generation at all (ADR-0038 §1). A positioning document is read
by people deciding what the system is, and this was the only place in the
corpus asserting a capability class the system does not have. The rest of
the positioning is unaffected: adjacency to strategic tools, the
time-horizon argument, and the empirical-reliability feedback vector all
stand.

**Where the claim went.** Not deleted — **relocated to its honest
status.** ADR-0038 §3 carries maintenance advisory generation as an
*anticipated* capability, with its boundary stated (OpenDDIL may propose;
the external system of record disposes and remains authoritative) and the
constraints that keep it buildable. Found and recorded as ADR-0038 AE-1,
which is where the correction's own provenance lives.

*This is the first claims-vs-sources finding in this corpus at the ADR
layer rather than in code or a display — the same rule
(`PRINCIPLES.md` §Claims vs. sources) applied one level up, to a document
asserting more than the artifacts it describes support.*
