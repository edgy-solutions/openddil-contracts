# DESIGN 2026-11-11 — The remaining-life output kind, its ADR-0057 amendment, and the scoring harness

**Status:** accepted as proposed, 2026-11-12, with two rulings: the kind is `terminal` under ADR-0034's composition
typing (§4), and a repair starts a new life only when declared a renewal (§5.2). The §4 amendment is applied to
ADR-0057. Still a design: nothing built, nothing run, nothing measured. Ordered 2026-11-11 as a spec under ADR-0059 §4.2
and §4.3. ADR-0059 is PROPOSED, reviewed 2026-11-11 and accepted as proposed; its ruling on ADR-0057 opens the output
kinds when this kind is specified. This record specifies the kind by concept. Field names, the wire message and the
topic are bound when it is built, not here.
**Builds on:** ADR-0059 §4.2-§4.4 and findings 7-9; ADR-0057 §1, §5 and §9 (the declaration, provenance and the replay
harness); ADR-0051 §2, §3 and §6 (the frozen context, declared usage meters, the failure report); ADR-0020's confidence
staircase and its declared confidence kind; ADR-0056 (one identity per thing); ADR-0038 C1, C2 and C7.
**Read at:** OpenDDIL working trees of 2026-11-11. These are reads, not runs.

## What this is

- **A third output kind for a declared analytic unit.** A unit that declares it emits, per component, a statement of
  how much use remains before a declared failure threshold, as a distribution in a declared usage meter's unit.
- **An amendment to ADR-0057, drafted below (§4).** It is applied to ADR-0057 when this design is accepted, not before.
  Until then ADR-0057's validator refuses the kind, as its status says.
- **A scoring harness (§5).** It joins recorded remaining-life outputs to confirmed failures, offline, and scores them
  with the metrics of Saxena et al. (IJPHM 2010).

**Not in it:** a unit that emits the kind, a calibrated life model, a field name, a topic, a contracts message, or a
change to the wear unit. The wear unit's `%` output stays a sustainment output (finding 7).

## Findings that shape it

1. **Today's remaining-life value is a percentage of an authored life.** The wear unit reports it in `%`
   (`openddil:openddil-tactical-agents/algorithms/wear/wear.py:21`, `:128`), against placeholder life totals
   (`wear.py:1-15`; `algorithms/wear/unit.yaml:16-22`). ISO 13381-1:2015's preview defines remaining useful life as a
   time before health falls below a defined failure threshold (ADR-0059 §4.2).
2. **The output kinds are closed.** `OUTPUT_KINDS = ("sustainment", "anomaly")`
   (`openddil:openddil-tactical-agents/edge/algorithm_runtime/declaration.py:32`), and ADR-0057 §1 refuses any other.
3. **A derived output carries confidence 0.0.** ADR-0057 §5: "a number above zero would claim one". ADR-0020 requires a
   confidence number to declare its kind, because an asserted floor, a fit quality and a calibrated probability are
   different quantities.
4. **Usage meters are declared per variant, and only three kinds exist.** `count:rounds`, `count:moves` and
   `duration:emitting` (ADR-0051 §3). The last needs an accumulator. Hours, cycles and distance exist as fields but are
   not declared meters (ADR-0059 finding 6).
5. **No confirmed failure outcome returns to OpenDDIL** (ADR-0059 finding 9). Confirmed closures will come from the
   completed work order, through iagent (ADR-0059 §4.4, ruled 2026-11-11). Which fields that outcome carries is a
   question to iagent's architect, sent 2026-11-11 and unanswered.

## 1. The output, by concept

One output per component per computation. Each row is a concept. Its field name is bound when built.

| Concept | What it holds | Rule |
|---|---|---|
| Component | The component's identity (ADR-0056), and the asset it is fitted to | An identity, never an alias alone |
| Meter | A declared usage meter for the asset's variant (ADR-0051 §3), by meter kind | Must be declared for the variant. A percentage of an authored life is not a meter |
| Unit of use | The meter's unit, in UCUM | Taken from the meter's declaration, never from the unit |
| Meter reading at computation | The component's meter value when the output was computed | In the meter's unit |
| Computed at | The time of computation | The sample time the unit stepped on, not the wall clock |
| Remaining use | A distribution over the use remaining before the threshold | Never a point alone (§2) |
| Distribution form | How to read the numbers: a quantile set, or a named parametric family with its parameters | Declared per output in the unit's declaration |
| Horizon | The predictive horizon: how far ahead, in the meter's unit, the output claims to apply | Declared. Beyond it, the output says nothing |
| Failure threshold | The threshold the output was computed against, by reference and version | A reference, never an inline number |
| Confidence | A value with its declared kind (ADR-0020), or absent | Never a default (§3) |
| Advisory | Always set. The output informs a person and starts nothing (ADR-0038 C7) | A unit cannot unset it |
| Composition | `terminal` under ADR-0034 (ruled 2026-11-12) | Never `upward`; a fleet figure is its own derived record |
| Provenance | `ORIGIN_DERIVED` and the producer stamp (ADR-0057 §5) | As every derived output |
| Labels | As ADR-0057 §5 sets them: copy-source today, high-water after ADR-0055 | Unchanged by this kind |

Terms from ISO 13381-1:2015 (remaining useful life, predictive horizon, confidence level) are used as the preview
quotes them in ADR-0059 §4.2. That edition is withdrawn. The 2025 edition is unread. This table is checked against it
before any field freezes.

## 2. A distribution, never a point alone

- **The form is declared, not inferred.** A reader of a quantile set knows which quantiles. A reader of a parametric
  family knows the family's name and what each parameter means. Neither is guessed from the numbers.
- **A unit that can only produce a point does not emit this kind.** It keeps a sustainment output. A point with a
  made-up spread would be the confabulation ADR-0020 names.
- **Censoring is stated, not hidden.** When the remaining use exceeds the horizon, the output says so, rather than
  stating a number past the horizon.

## 3. Confidence, and whose number it is

ADR-0057 §5 stamps every derived output with confidence 0.0, and that stays true of the provenance. The remaining-life
output adds a second confidence beside the distribution, about the prediction. It is present only with a declared kind:
- **Asserted** (ADR-0020's first step): the number is the declaration's, stated with its reason. The unit never writes
  it.
- **Fit-derived** (the second step): the unit computes it from retained samples. The runner checks it is in range.
- **Calibrated** (the fourth step): only after a scoring run (§5) on confirmed failures.

With no declared kind, the confidence is absent. A reader never sees a number without its kind.

## 4. The ADR-0057 amendment, drafted

Applied to ADR-0057 on acceptance (2026-11-12), with the composition refusal the terminal ruling adds. Text, by
section:

> **Status.** Amended (date of acceptance): the output kinds admit `remaining_life`, specified in
> DESIGN-2026-11-11-remaining-life-output-kind. The set stays open (ADR-0038 C2): a further kind is added the same
> way, by a specification and an amendment.
>
> **§1, the `outputs` row.** Each output's `kind`, topic, `direction`, `producer_id`, `source_protocol` and `labels`.
> An anomaly output also has `event_type` and `severity`. A remaining-life output also declares its meter kind, its
> distribution form, its horizon, its failure threshold reference, and its confidence kind or none.
>
> **§1, the refusals.** The validator refuses:
> - an output kind other than `sustainment`, `anomaly` or `remaining_life`;
> - a remaining-life output with no meter kind, no distribution form, no horizon or no threshold reference;
> - a remaining-life output whose confidence kind is not one of ADR-0020's declared kinds;
> - a remaining-life output that is not marked advisory;
> - a remaining-life output in a unit whose `composition` is not `terminal` (ruled 2026-11-12). A distribution over
>   one component's remaining use does not compose into a fleet figure, so by the composition gate it is never
>   `upward`. A fleet-level prognosis is a separate derived record with its own rule.
>
> The render check (§4) refuses a remaining-life output whose meter kind is not declared for the variants the unit is
> deployed to.
>
> **§5, provenance.** A remaining-life output is stamped `ORIGIN_DERIVED` with confidence 0.0, like every output. Its
> prediction confidence is a separate value with a declared kind. An asserted confidence comes from the declaration,
> never from the unit. A payload that sets an asserted confidence, or sets advisory to false, is refused
> (`output_refused`).
>
> **§9, the replay harness.** A remaining-life output is compared like a sustainment output: exactly, unless a
> tolerance is declared in advance with its reason. A distribution is compared parameter by parameter, or quantile by
> quantile.

The token `remaining_life` is bound with the amendment (2026-11-12).

What the amendment does not change: the runner, the roles, the composition gate, the labels rule, the stamp's shape,
and the refusal of `dependencies`.

## 5. The scoring harness

Offline, over recordings, like ADR-0057 §9's replay harness. It never writes to a live store. It implements the
metrics of Saxena et al., IJPHM 2010 (read in full, ADR-0059 §1) from the paper's text and cites it: prognostic
horizon, α-λ performance, relative accuracy, cumulative relative accuracy, and convergence. This design states no
definition of its own for any of them. The paper's parameters are declared per run, in the run's input file.

### 5.1 Inputs

| Input | From | Carries |
|---|---|---|
| Remaining-life outputs | A recording of the kind's topic, in ADR-0057 §9's file format | Component, meter kind, meter reading at computation, computed at, distribution and its form, horizon, threshold reference, producer stamp |
| Confirmed failures | Episodes closed with reason `confirmed` (ADR-0059 §4.1), from the completed work order (§4.4) | Confirmed component, the work order reference, the time of completion, the episode's open time |
| Meter at failure | The episode's frozen context at open (ADR-0051 §2), with the meter's value (§3) | The meter reading when the failure was first observed |
| Other closures | Episodes closed `no_fault_found`, `cannot_duplicate`, or declared at the tier and unconfirmed (§4.4) | Kept to show what was excluded, never scored as a failure |
| Run declaration | A file per run | The unit versions in scope, the metric parameters, the window of recordings |

### 5.2 The join

- **Key:** the component's identity (ADR-0056), and the meter kind. An output is joined only to failures of the same
  component, measured on the same meter.
- **Which failure:** the first confirmed failure of that component whose episode opened after the output was computed.
- **Actual remaining use:** the meter reading at failure minus the meter reading at computation, in the meter's unit.
- **Time of failure:** the episode's open time, when the failure was first observed. The work order's completion time
  confirms it, and is later. It is not the end of life.
- **Unmatched outputs are censored.** A component with no confirmed failure in the window has an output whose actual
  remaining use is unknown. It is counted as censored and never scored as wrong.
- **Not a failure:** a `no_fault_found` or `cannot_duplicate` closure does not end a life. A closure declared at the
  tier counts only when a work order outcome confirms it.
- **A repair in place (ruled 2026-11-12).** A repair starts a new life only when that repair type is declared a
  renewal for that component. The declaration is per variant and names its owner, like the movement deadbands. With
  nothing declared, the life continues, and the repair is an event recorded on it. A declared renewal ends a life
  without being a failure: an output computed before it, with no confirmed failure between, is censored at the
  renewal.
- **Grouping:** scores are grouped by the producer stamp (unit, version, configuration hash), so two versions are never
  averaged together.

### 5.3 What a run reports

- Per group: the joined count, the censored count, the excluded closures by reason, and each metric with its cited
  source.
- Whether the unit's declared parameters are placeholders. The wear unit's are (finding 1), so a score of it measures
  a placeholder. The harness is built so the first calibrated unit is scored the day it ships.

### 5.4 What it waits for

- **The outcome's fields.** iagent's answer to the twelve questions and the outcome-fields packet (2026-11-11). Until
  then no outcome field is bound here.
- **The episode's closure reason, confirmed component and frozen variant** (ADR-0059 §4.1). Not built.
- **A meter that is not a placeholder.** `duration:emitting` needs its accumulator (ADR-0051 §3).
- **Renewal declarations.** Until a repair type is declared a renewal for a component and variant, every repair
  continues the life (§5.2).

## 6. Rows

In `FOLLOW-UPS.md`: the kind specified, not built, with the amendment waiting for acceptance and the harness waiting
for confirmed outcomes.

## What this does not establish

- Nothing is built, run or measured. No unit emits the kind.
- No field name, topic or wire message.
- ISO 13381-1:2025: unread. The 2015 preview's terms are used, and are checked against 2025 before any field freezes.
- Saxena et al. 2008: unread. Only the 2010 paper's metrics are named.
- Which repair types are renewals for which components. §5.2 rules that only a declaration makes one; no
  declaration exists yet.
- A fleet-level prognosis. The kind is `terminal` (§4), so it never goes upward; a fleet figure is a separate derived
  record with its own rule.

## Related

- [ADR-0059](ADR-0059-condition-monitoring-bit-and-usage-alignment.md) §4.2-§4.4, the record this specifies under.
- [ADR-0057](ADR-0057-declared-analytic-units-adr0034-first-engine-slice.md), amended by §4 when accepted.
- [ADR-0051](ADR-0051-failure-records-for-fracas.md) §2, §3, §6.
- [ADR-0020](ADR-0020-prognostics-derivation-stage.md), the confidence staircase.
- [ADR-0056](ADR-0056-one-identity-per-thing-every-other-id-is-an-alias.md).
- [ADR-0038](ADR-0038-anticipated-capability-envelope.md) C1, C2, C7.
- The BIT kind specification, stacked after this one: `DESIGN-2026-11-11-bit-record-kind.md`.
