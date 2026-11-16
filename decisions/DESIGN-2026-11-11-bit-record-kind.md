# DESIGN 2026-11-11 — The built-in test record kind, and the detection and isolation counts it feeds

**Status:** accepted as proposed, 2026-11-12, with its open item ruled: records stay at the tier, and only the episode
and the counts go up (§6). Still a design: nothing built, nothing run, nothing measured. Ordered 2026-11-11 as a spec
under ADR-0059 §5.
ADR-0059 is PROPOSED, reviewed 2026-11-11 and accepted as proposed. This record specifies the kind by concept. Field
names, the wire message and the topic are bound when it is built, not here.
**Builds on:** ADR-0059 §4.1, §4.4 and §5, and findings 3-5; ADR-0051 §2-§4 (the frozen context, usage meters, the
rollup by variant); ADR-0056 (one identity per thing); ADR-0020 (a confidence declares its kind); ADR-0053 (provenance
on every side of a disagreement); ADR-0046 (declared kinds at the gate).
**Read at:** OpenDDIL working trees of 2026-11-11. These are reads, not runs.

## What this is

- **A declared record for one built-in test result.** It enters at the tier that observes it. A failed test opens or
  joins an episode as its detection, with the candidate components named.
- **The inputs and join for ADR-0059 §4.1's counts.** Detection, isolation, false-alarm and no-fault-found counts are
  read from these records and the episodes they join.

**Not in it:** a source mapping, a vocabulary for any variant, a field name, a topic, or a change to
`HealthFlags.active_fault_codes`.

## Findings that shape it

1. **Built-in test arrives as free strings.** `HealthFlags.active_fault_codes` is commented "Unstructured fault codes
   from BIT (Built-In Test)" (`openddil:openddil-contracts/proto/openddil/telemetry/v1/telemetry.proto:283-284`), beside
   five boolean warnings (:278-282). There is no test type, result, isolated unit or confidence (ADR-0059 finding 3).
2. **An episode's detecting source is an opaque string, and it names one component** (ADR-0059 finding 5,
   `openddil:openddil-cm-service/src/as_maintained/persistence_model.py:72-75`, `:101`). It has no ambiguity group and no
   closure reason.
3. **An episode's `fault_code` is a key in the deployment's fault catalog** (`openddil:openddil-demo/gateway/pep.py:1674-1706`,
   `:324-331`). It is not a failure mode (ADR-0059 finding 4).
4. **DIS appearance bits are reported state, not a test** (ADR-0059 finding 3).

## 1. The record, by concept

| Concept | What it holds | Rule |
|---|---|---|
| Test type | Which test ran, from a vocabulary declared per variant | No names are taken from a standard: MIL-STD-1309 is unread |
| Result | `pass`, `fail` or `not_run` | From a declared vocabulary. Nothing else is admitted |
| Fault code | A key in the deployment's fault catalog, as an episode carries it | Present on `fail`. Never a free string |
| Isolated units | The ambiguity group: one or more candidate components, ordered | Each an identity (ADR-0056). Order is the source's, not re-sorted |
| Confidence | A value with its declared kind (ADR-0020), or absent | Never a default |
| Observed at | The time the source says the test ran | The source's time, not the tier's arrival time |
| Source entity | The asset the result came from | Its identity (ADR-0056) |
| Provenance | `ORIGIN_MEASURED`, and the ingest that mapped it | A mapped result is observed, not derived |
| Labels | The labels of its source | Passed through, as the source carried them |

The terms built-in test, ambiguity group, false alarm, cannot duplicate and retest okay are MIL-HDBK-2165's (read in
full), as ADR-0059 §4.1 quotes them. "No fault found" is a closure value name, aligned to MIL-HDBK-2155's failure
verification, and not a handbook term.

## 2. Where it is declared

- **Per variant, as overlay data**, next to the variant's enumeration files and its usage meters (ADR-0051 §3):
  - the test types the variant's source can report;
  - for each, the fault codes it can name, each in the fault catalog;
  - for each, the components it can isolate to, so an ambiguity group can be checked against the variant.
- **Checked at render.** A test type with a fault code outside the catalog, or a component the variant does not
  carry, is refused before the tier starts.

## 3. Where it comes from

- **A deployment's ingest maps its source's built-in test into this record.** The mapping is the deployment's. The
  record's shape is OpenDDIL's.
- **An unmapped result is kept, not guessed.** A source code with no mapping is counted and named in the ingest's own
  refusal count. It never becomes a record with an invented test type.
- **An isolated unit that names no identity yet** is carried as its alias, marked unresolved, and resolved when the
  alias binds (ADR-0056). It is never dropped, and never counted toward isolation until it resolves.
- **DIS appearance bits are not mapped into it.** They report state.

## 4. What a record does to an episode

- **`fail`** opens an episode, or joins the open one with the same asset and fault code, as an episode is keyed today.
  The episode's detecting source is `bit`. Its ambiguity group is the record's isolated units.
- **`pass`** never closes an episode. A pass is not a repair. Closure comes from the completed work order (ADR-0059
  §4.4). A pass after a `fail` is kept beside the episode, as evidence a person can read at closure.
- **`not_run`** is kept. It has no effect on an episode.
- **Repeated `fail`s** of the same test on an open episode join it. They do not open a second one, and they are not
  counted as a second indication.

## 5. The counts: inputs and join

ADR-0059 §4.1's counts, per (region, variant, component), are read here as follows.

### 5.1 Inputs

| Input | From | Carries |
|---|---|---|
| Built-in test records | This kind, at each tier | Test type, result, fault code, isolated units, observed at, source entity |
| Episodes | The tier's episode store (ADR-0051) | Detecting source, ambiguity group, frozen variant (when built), confirmed component, closure reason |
| Confirmed outcomes | The completed work order, through iagent (ADR-0059 §4.4) | Confirmed component, closure reason, work order reference, time of completion |
| Meter deltas | The variant's declared meters (ADR-0051 §3) | Use over the counting window, so a false alarm can be stated per unit of use |
| Declared group sizes | The deployment's declaration | The values of k for "isolated to a group of at most k" |

### 5.2 The join

- **Record to episode:** by the episode the record opened or joined (§4). One indication per episode, from its first
  `fail`.
- **Episode to outcome:** by the episode, through the work order reference the outcome carries. Which fields carry it
  is iagent's answer to the outcome-fields packet (2026-11-11), not yet received.
- **Isolation:** the confirmed component's identity is looked up in the episode's ambiguity group. Its group size is
  the group's length. An unresolved alias in the group is counted as not isolated.
- **Variant:** the variant frozen at the episode's open (ADR-0059 §4.1, not built). Never the asset's variant today.

### 5.3 The counts, as sums that compose

- Confirmed failures; confirmed and detected by built-in test; confirmed, detected, and isolated within each k;
  indications closed `no_fault_found` or `cannot_duplicate`; closures by reason; the meter delta.
- Each tier keeps sums. Sums compose up the tiers. Rates do not compose, and HQ divides at read time (ADR-0051 §4).
- The tier states counts. It never states that a test is adequate (ADR-0038 C7).

## 6. Ruled, and still open

- **`active_fault_codes` stays beside the kind (ruled 2026-11-11).** The ingest fills both while sources are mapped
  one by one, and the kind is authoritative where both exist. The field is retired once every source a deployment
  declares is mapped. A FOLLOW-UPS row tracks the retirement. The other option, retiring it source by source so one
  result is never two records, was not taken.
- **Records stay at the tier (ruled 2026-11-12).** A built-in test record stays at the tier where it was observed.
  Only the episode and the counts go up: HQ gets the detection source and the ambiguity group on the episode, and the
  sums of §5.3. A deployment that needs raw records upstream declares that kind explicitly, through the gate
  (ADR-0046).

Still open:
- **The topic and the wire message.** Bound when built.

## 7. Rows

In `FOLLOW-UPS.md`: the kind specified, not built, with the counts waiting for confirmed outcomes; and a second row
to retire `active_fault_codes` once every declared source is mapped.

## What this does not establish

- Nothing is built, run or measured. No source is mapped.
- No test type name. MIL-STD-1309 is unread.
- IEEE 1232's diagnostic models: a candidate interchange, unread past the preview. Nothing here aligns to them.
- ISO 14224's failure mode, mechanism and cause: definitions unread. The record carries a fault code, not a failure
  mode.
- Whether a deployment's source can report an ordered ambiguity group at all.

## Related

- [ADR-0059](ADR-0059-condition-monitoring-bit-and-usage-alignment.md) §4.1, §4.4, §5, the record this specifies under.
- [DESIGN-2026-11-11: the remaining-life output kind](DESIGN-2026-11-11-remaining-life-output-kind.md), stacked before
  this one.
- [ADR-0051](ADR-0051-failure-records-for-fracas.md) §2-§4.
- [ADR-0056](ADR-0056-one-identity-per-thing-every-other-id-is-an-alias.md).
- [ADR-0020](ADR-0020-prognostics-derivation-stage.md), declared confidence kind.
- [ADR-0046](ADR-0046-maintenance-bridge-events-out-actions-in.md).
- [ADR-0038](ADR-0038-anticipated-capability-envelope.md) C7.
