# ADR-0059 — Condition monitoring, built-in test and usage: an alignment record, with the gaps as rows

## Status

**PROPOSED — 2026-11-11. Design only. Nothing here is built.** Ordered 2026-11-10, and extended 2026-11-11 with fault
detection and isolation and with remaining useful life. This is an alignment record. It reads what exists against the
standards named below, by concept only, and names the gaps as rows. It aligns nothing by field name, and no row here is
a conformance claim. Each standard is marked with how much of its text was read (§1). A concept from a standard that
was not read is never used to decide anything here.
**Reviewed 2026-11-11: accepted as proposed**, with four rulings:
- where closure reasons come from (§4.4), with the field list put to iagent's architect as a question;
- network state as an observed input (§7), with the alerting path added the same day;
- ADR-0038 §1 and St-Tx corrected so the analyzer sits under configuration status accounting;
- ADR-0057's output kinds open when the remaining-life kind is specified.
**Builds on:** ADR-0038 §1 (the ISO 13374 reading) and C1, C2 and C7; ADR-0051 (failure records, usage meters,
composable rollups); ADR-0057 (the declared analytic unit); ADR-0020 (derived values and the confidence staircase);
ADR-0013 (the quantity and its unit); ADR-0046 (declared kinds at the gate); ADR-0056 (one identity per thing).
**Read at:** OpenDDIL working trees of 2026-11-11. Line numbers move with them. These are reads, not runs.

## Findings first

1. **The capability names and the ISO 13374 blocks were never checked against the standard's text, and that text is
   still unread.** St-Tx names six condition-monitoring capabilities after ISO 13374's blocks, through ADR-0038 §1. The
   only block names this task could read come from a secondary source: a 2009 ISO TC 184/WG 6 slide in a MIMOSA
   presentation. They are data acquisition, data manipulation, state detection, health assessment, prognostics
   assessment and advisory generation. They agree with St-Tx's names in concept, and the model writes "Prognostic"
   where the slide writes "Prognostics". Parts 1 and 4 were read as abstracts only, and parts 2 and 3 not at all (§1).
   ADR-0038's caveat, "a reading, not a conformance claim", is exactly right, and it stays.
2. **Most of the "condition" advice is configuration advice.** The analyzer that writes `recommended_action`
   (`openddil:openddil-cm-service/src/discrepancy/analyzer.py:144`, the strings at :202-329) compares installed items
   and modifications against a baseline. That is configuration management, not condition monitoring. ADR-0038 §1 listed
   it under state detection and advisory generation. As a configuration check it belongs to ConfigurationStatusAccounting,
   and ADR-0038 §1, St-Tx and the capability record now say so (ruled 2026-11-11).
   The only condition advisory is fusion's constraining factors, which carry no advice text
   (`openddil:openddil-logistics-fusion-service/src/fusion/rules.py`). The two disciplines share the abbreviation "CM"
   in this codebase, so the glossary now writes both out (§6).
3. **There is no structured built-in test record.** Built-in test arrives as `HealthFlags.active_fault_codes`, a list
   of free strings commented "Unstructured fault codes from BIT (Built-In Test)"
   (`openddil:openddil-contracts/proto/openddil/telemetry/v1/telemetry.proto:283-284`), and as five boolean warnings
   (:278-282). The record has no test type, no structured result, no isolated unit and no confidence. The DIS fields
   that bear on condition, such as the appearance damage, mobility, firepower, power-plant and deactivated bits
   (`ontology/dis_appearance.yaml`), are an entity's reported state, not a test result.
4. **An episode has no failure-mode, mechanism or cause vocabulary.** An episode's `fault_code` is a key into the
   deployment's fault catalog (`openddil:openddil-demo/gateway/pep.py:1674-1706`, `:324-331`). It is not a failure mode
   in IEC 60812's sense, "manner in which failure occurs". The analyzer's findings carry no `fault_code` at all
   (`analyzer.py:363-395`, no call site passes one).
5. **An episode cannot yet support fault detection and isolation rates.**
   - Its detecting source is an opaque string (`DiscrepancySourceRecord.source`,
     `openddil:openddil-cm-service/src/as_maintained/persistence_model.py:72-75`), and no declared vocabulary separates
     built-in test from an operator, the analyzer or an algorithm.
   - It names one `component` (:101) and has no ambiguity group.
   - It closes with free-text `resolution` and `cleared_by` (:150-151). It has no closure reason: confirmed, no fault
     found or cannot duplicate.
   - It carries no platform variant (:82-155), so a rate per variant cannot be counted from it. ADR-0051 §2 freezes a
     baseline at open, but not a variant.
6. **Usage meters stop at ADR-0051's three.** `count:rounds`, `count:moves` and `duration:emitting`
   (`ADR-0051-failure-records-for-fracas.md:116-118`) are the only meter kinds. Hours, cycles and distance exist as
   fields or accumulators: `WearState.hours_in_service` and `cycles` (`telemetry.proto:262-266`), `power_cycles` with
   no unit (:232), and the wear unit's `cumulative_distance_m`. None of them is a declared meter. Starts and an odometer
   were not found.
7. **The remaining-life value is a percentage of an authored life, not a time.** The wear unit reports remaining useful
   life in `%` (`openddil:openddil-tactical-agents/algorithms/wear/wear.py:21`, `:128`), against life totals that are
   placeholders (`wear.py:1-15`; `algorithms/wear/unit.yaml:16-22`).
   - The trend carries a latest value, a slope and a fit quality (`windowed_telemetry.proto:33-39`, `:49-54`). It has no
     distribution, no horizon, and no derived or advisory marking of its own.
   - Fusion projects a single time point from the slope (`rules.py:614-630`, `projected_time_to_worse`).
   - ISO 13381-1 defines remaining useful life as a time (§4).
8. **The algorithm contract's output kinds are closed.** `OUTPUT_KINDS = ("sustainment", "anomaly")`
   (`openddil:openddil-tactical-agents/edge/algorithm_runtime/declaration.py:32`), and ADR-0057 §1 refuses any other.
   This is a refusal at startup, and that is correct for a slice. But ADR-0038 C2 requires the output vocabulary to be
   open, and C1 requires the envelope to carry a horizon and a band. A remaining-life output has nowhere to go today.
9. **No confirmed failure outcome returns to OpenDDIL.** Nothing records that a failure was confirmed, or that a
   reported fault was found not to exist. The ledger's `outcome` is delivery, not failure
   (`openddil:openddil-stack/schema/schema.hcl:2062`), and the intake's `decision` is an admission decision. So nothing
   can score a prediction against what happened. §4.4 names where a confirmed outcome will come from.

## 1. What was read

Read on 2026-11-11 from public pages and publisher previews. The ISO site refused every request. A name from a search
snippet does not count as read.

| Standard | Portion read | What it gives this record |
|---|---|---|
| ISO 13374-1 (2003) | Abstract | The scope sentence only |
| ISO 13374-2, -3 | **Unread** | Nothing |
| ISO 13374-4 (2015) | Abstract | Presentation of diagnostic and prognostic data, advisories and recommendations |
| ISO 13374 block names | A secondary slide (2009, ISO TC 184/WG 6, in a MIMOSA deck) | The six block names, not the standard's text |
| MIMOSA OSA-CBM | Public page | That it implements ISO 13374's functional specification; no layer or class text |
| MIMOSA OSA-EAI, CCOM | Public pages | Component names and a CCOM class list, with no definitions |
| ISO 17359 (2018) | Abstract, and the 2011 contents | The steps of a monitoring programme, as headings |
| ISO 13381-1 (2015) | Preview: scope, terms 3.1-3.10, 5.1 | Prognosis, remaining useful life, estimated time to failure, predictive horizon, confidence level. **Withdrawn in 2025**; the 2025 edition is **unread** |
| ISO 14224 (2016) | Abstract, and a draft-stage seminar deck | A "reliability language"; the names failure mode, failure mechanism, failure cause, and critical, degraded and incipient failure. **Definitions unread** |
| IEC 60812 (2018) | Preview: contents, scope, term 3.1.1 | Failure mode; identifying detection methods |
| MIL-HDBK-2165 (1995) | **Full** | Built-in test, fault coverage, fault resolution, ambiguity group, false alarm, cannot duplicate, retest okay |
| MIL-STD-1309 | **Unread** | Nothing |
| IEEE 1232 / IEC 62243 (2012) | Preview: scope, contents | That it specifies diagnostic models and reasoner interchange; the model abbreviations are not expanded in the read text |
| ARINC 624-1 (1993) | Abstract | Design guidance for an onboard maintenance system |
| MIL-HDBK-2155 (1995) | **Full** | Failure verification, and close-out with corrective action or a documented rationale |
| W3C SOSA/SSN | 100k of 238k characters, including all of §4 | Observation, sensor, feature of interest, observable property, procedure, result, platform, phenomenon time, result time |
| IOF Core, IOF Maintenance (release 202601) | Class labels only, with no definitions | Failure event, failure mode code, degraded state, failed state, maintenance work order record |
| ROMAIN | **Unread** | Nothing. Its authorship is unconfirmed |
| ISO 15926 | Part 1 abstract | The scope fragment only. Parts 2, 3, 4 and 100 are **unread** |
| QUDT, UCUM | Their own pages | A unit and quantity-kind vocabulary; UCUM's unit codes |
| PROV-O | 100k of 263k characters | Entity, activity, agent; derived from, generated by, acted on behalf of |
| PHM prognostic metrics (Saxena et al., IJPHM 2010) | **Full** | Prognostic horizon, α-λ performance, relative accuracy, cumulative relative accuracy, convergence |
| PHM metrics (Saxena et al., 2008) | **Unread** | Nothing. The 2010 paper says it adapts it |

A row that reads "Unread" stays a declared intent in Sd-Tx until it is read. A rung rises only on a read, and a read
that changes a mapping here amends this record.

## 2. The edge pipeline against ISO 13374's blocks

The block names are from the secondary slide (§1). The capability names are St-Tx's. Paths are in `openddil:`.

| Block (slide name) | Capability (St-Tx) | Where, by file |
|---|---|---|
| Data acquisition | DataAcquisition | `openddil-sensor-ingest/dis_ingestor.py` (UDP to `ingress-dis-raw`, :136; Entity State :689, :859); `appearance.py:67`; the base Connect pipeline's input (`openddil-demo/openddil-base-connect.yaml:30`) |
| Data manipulation | DataManipulation | the Connect mapping to `raw-sensor-stream` (`openddil-base-connect.yaml:153`); window buffers and regression (`openddil-tactical-agents/edge/faust_edge.py`, ~458-482, :382-425); `edge/element_rollup.py`; the quantity and its UCUM unit (`openddil-contracts/proto/openddil/common/v1/quantity.proto:17-30`) |
| State detection | StateDetection | the worst-of condition (`openddil-sensor-ingest/condition.py:310`); band crossings (`edge/element_bands.py:61-88`); the thermal unit (`algorithms/thermal/thermal.py:24`); fusion's thresholds (`openddil-logistics-fusion-service/src/fusion/thresholds.py:25-47`, `rules.py:433`, :731) |
| Health assessment | HealthAssessment | fusion's status roll-up (`rules.py:961`, `_max_severity` :188). There is no diagnosis: nothing attributes a cause, as ADR-0038 §1 found |
| Prognostics assessment | PrognosticAssessment | the wear unit (`algorithms/wear/wear.py:38`, :110-121); `ComponentWearTrend` (`windowed_telemetry.proto:49-54`); fusion's projection (`rules.py:614-630`); the regional aggregator (`regional/aggregator_app.py:284`) |
| Advisory generation | AdvisoryGeneration | **None for condition.** The analyzer's actions (`openddil-cm-service/src/discrepancy/analyzer.py:202-329`) are configuration advice (finding 2). The egress assembler's nearest spare (`openddil-demo/egress/assembler.py:471-487`) is a lookup, not advice |
| (presentation, on the slide) | InformationPresentation | the UI's cards (ADR-0058) |

The analyzer's comparison (`analyzer.py:144`) and its overall status (:345-359) are configuration status
accounting. ConfigurationStatusAccounting names them, and from 2026-11-11 the analyzer sits only there: ADR-0038 §1,
St-Tx and the capability record were corrected to match.

## 3. Records against SOSA/SSN and ISO 14224

Concepts only, named as the read text names them. ISO 14224's definitions were not read, so every ISO 14224 column
entry below is a declared intent, not an alignment.

| OpenDDIL | SOSA/SSN (read) | ISO 14224 (names only) | Note |
|---|---|---|---|
| A sample on `raw-sensor-stream`: a `Quantity` with a role or signal key, an entity and `sample_time_ns` | An observation: its result (the quantity), its observed property (the role), its feature of interest (the asset or component) and its phenomenon time | Operating and condition data | SOSA also names a class "Sample". Its definition was not in the read portion, so OpenDDIL's "sample" is mapped to observation only, and the name clash goes in the glossary |
| The DIS entity that reports, and the ingest sidecar | Sensor, platform | — | Nothing records which sensor made a sample. The entity is the platform |
| A windowed trend: latest, slope, fit quality | An observation whose procedure is the regression | — | Derived. PROV-O: derived from the samples |
| A band crossing; the thermal alert | An observation of a derived property | Degraded failure, critical failure | The bands are not failure classes. The concept names are from a draft-stage deck |
| The DIS appearance and condition fields; `HealthFlags`; `active_fault_codes` | An observation of a reported state | Detection method (the deck mentions an annex, unread) | Not a test result (finding 3) |
| An episode, open and closed (`persistence_model.py:82-155`) | — | Failure data: failure mode, mechanism, cause | None of the three is on the episode (finding 4). The nearest IOF label is "failure event" |
| `fault_code` | — | — | A catalog key. The nearest IOF label is "failure mode code", but the key is not a failure mode |
| A usage meter (ADR-0051 §3) | An observable property of the asset, with a monotonic result | Operating time (name only) | Units through UCUM. QUDT is the quantity-kind vocabulary, not verified here |
| The wear model | A procedure. Its output is an observation of remaining life | — | ISO 13381-1 governs the concept (§4). PROV-O: an activity, with the producer stamp as its agent |
| The producer stamp and `ORIGIN_DERIVED` | — | — | PROV-O: generated by, attributed to |

## 4. Fault detection and isolation, and remaining useful life

### 4.1 Detection and isolation rates

MIL-HDBK-2165 was read in full. Its concepts used here, quoted:
- **Fault coverage, fault detection:** "The ratio of failures detected (by a test program or test procedure) to
  failure population; expressed as a percentage."
- **Fault resolution, fault isolation:** "the percent of the cases for which the isolation procedure results in a
  given ambiguity group size."
- **False alarm:** "A fault indicated by BIT or other monitoring circuitry where no fault exists."
- **Cannot duplicate:** "A fault indicated by BIT or other monitoring circuitry which cannot be confirmed at the first
  level of maintenance."

"No fault found" is not a term in the handbook. It is used here as a closure value name, aligned to MIL-HDBK-2155's
failure verification: a reported failure is "verified as actual or an explanation provided for lack of verification".

**The four rates are measured per variant from episodes, as sums.** This extends ADR-0051 §4's rollup. Each tier keeps
counts. Counts compose up the tiers, and rates do not. HQ divides at read time.

| Count, per (region, variant, component) | Read from the episode |
|---|---|
| Confirmed failures | Closure reason `confirmed` |
| Confirmed failures detected by built-in test | Confirmed, with detecting source `bit` |
| Confirmed failures isolated to a group of at most k | Confirmed, detected by built-in test, with the confirmed component in an ambiguity group of size at most k, for each declared k |
| Built-in test indications not confirmed | Detecting source `bit`, closed `no_fault_found` or `cannot_duplicate` |
| Closures, by reason | Every closed episode |
| The variant's meter delta | ADR-0051 §3, so a false alarm can be stated per unit of use |

- **Detection rate:** confirmed and detected by built-in test, over confirmed.
- **Isolation rate to a group of size k:** confirmed and isolated within k, over confirmed and detected by built-in test.
- **False-alarm rate:** indications not confirmed, over built-in test indications, or per unit of the meter.
- **No-fault-found rate:** `no_fault_found` closures, over closures.

These are this record's working counts, aligned to the handbook's concepts. They do not restate a definition the
handbook does not give. The tier states the counts, and it never states that a test is adequate (ADR-0038 C7).

**What the episode needs, and does not have** (finding 5):
- a detecting source, from a declared vocabulary: `bit`, `operator`, `analyzer`, `algorithm`, open to a deployment's
  additions;
- an ambiguity group: the ordered candidate components that the indication named, each an identity under ADR-0056;
- at close, the confirmed component and a closure reason: `confirmed`, `no_fault_found` or `cannot_duplicate`.
  MIL-HDBK-2165's "retest okay" is a candidate fourth value, for a deployment that repairs at two levels;
- the variant, frozen at open beside the baseline (ADR-0051 §2).

### 4.2 Remaining useful life

From ISO 13381-1:2015, as previewed. That edition is withdrawn; the 2025 edition is unread, and this section is checked
against it before any field freezes.
- **Remaining useful life:** "remaining time before system health falls below a defined failure threshold".
- **Predictive horizon:** "threshold for prediction of lead time to failure as desired by the user".
- **Confidence level:** "figure of merit (e.g. percentage) that indicates the degree of certainty that the
  diagnosis/prognosis is correct".
- §5.1: prognostics predicts remaining useful life "with a satisfactory level of confidence".

**Proposed: remaining useful life is an output kind of the algorithm contract** (ADR-0057). A unit that declares it
emits, per component:
- the meter it is stated in, a declared usage meter (ADR-0051 §3), with its UCUM unit. A percentage of an authored life
  is not one;
- a distribution over the remaining use, never a point alone. Its form (quantiles, or a named parametric family) is
  declared, so a reader knows what the numbers are;
- the horizon, in the same unit;
- the failure threshold it was computed against, by reference;
- the meter reading and the time it was computed at, and the identity of the component;
- `ORIGIN_DERIVED`, the producer stamp, and a confidence with its kind (ADR-0020). It is marked **advisory**: it
  informs a person and starts nothing by itself (ADR-0038 C7).

This answers ADR-0038 C1 for prognosis: a future time basis and a band. It needs ADR-0057's closed set of kinds opened,
as C2 requires (finding 8). ADR-0057's status now says the set opens when this kind is specified (ruled 2026-11-11). The kind's field names are not proposed here. They are bound when the kind is specified.

### 4.3 Scoring against what happened

**Proposed: a scoring harness over recorded failures.**
- **The join:** each remaining-life output, at its meter reading, is joined to the component's confirmed failure. That
  failure is an episode closed `confirmed` (§4.1), with the meter reading at failure. The actual remaining use is the
  difference.
- **The source:** failure outcomes come from the failure reporting loop, MIL-HDBK-2155's verification and close-out, as
  ADR-0051 §6 carries it. Confirmed outcomes are the completed work orders of §4.4. Today none returns (finding 9).
- **The metrics:** by concept, from Saxena et al., IJPHM 2010, read in full: prognostic horizon, α-λ performance,
  relative accuracy, cumulative relative accuracy, and convergence. This record asserts no definition of its own for
  any of them. The harness implements the paper's text and cites it.
- **Where it runs:** offline, over recordings, like ADR-0057 §9's replay harness. It never writes to a live store.
- **What its scores mean today:** the wear unit's life totals are placeholders (finding 7), so a score today measures a
  placeholder. The harness is built so that the first calibrated unit is scored on the day it ships, not so that today's
  numbers mean something.

### 4.4 Where a closure reason comes from

**Ruled 2026-11-11.** A confirmed component and a closure reason come from one place: the maintenance management
information system's completed work order. It returns through iagent as the outcome of its maintenance action record,
the workflow's registered output artifact. iagent's ruling R-114 (2026-10-02) has the completed record cross back to
OpenDDIL as the plain wire response, not as an ingest kind.
- **Confirmed:** a closure carried by that outcome is a confirmed closure. Only these closures count in §4.1's
  confirmed counts and in §4.3's join.
- **Declared at the tier:** a closure recorded at a tier, by a person or a workflow step, is declared-local and
  unconfirmed. It is kept and shown, and it counts under its own reason, never as `confirmed`. A later outcome from the
  work order confirms it or replaces it.
- **A release never closes an episode.** Releasing a record through the egress gate (ADR-0046) reports the fault. It
  says nothing about the repair.

**A question for iagent's architect:** which fields the maintenance action record's outcome carries. At least the
confirmed component, the closure reason from §4.1's vocabulary, the work order reference, and the time of completion.
Until it is answered, no outcome field is bound here.

## 5. The built-in test kind: a proposed seam

A built-in test result enters as a declared record, not as free strings. It enters at the tier that observes it, and
it becomes an episode's detection.

| Field (concept) | What it holds |
|---|---|
| Test type | From a vocabulary declared per variant. Names are not taken from a standard here, because MIL-STD-1309 is unread |
| Result | Pass, fail or not run, from a declared vocabulary |
| Fault code | A key in the deployment's fault catalog, as an episode carries it today |
| Isolated unit | The ambiguity group: one or more candidate components, ordered, each an identity (ADR-0056) |
| Confidence | A value with its kind (ADR-0020), or absent. Never a default |

It also carries the time observed, the source entity, `ORIGIN_MEASURED`, and the labels of its source.

- **Where it comes from:** a deployment's ingest maps its source's built-in test into this record. DIS appearance bits
  are not mapped into it, because they report state, not a test.
- **What it opens:** a `fail` opens or joins an episode, with detecting source `bit` and the ambiguity group from the
  isolated units.
- **What is not decided:** the kind's field names, its topic, and whether `active_fault_codes` is kept beside it. They
  are bound when the kind is specified.
- **Standards:** MIL-HDBK-2165 gives its concepts. IEEE 1232's models are a candidate interchange, and are unread past
  the preview.

## 6. Configuration management and condition monitoring

Both are written out in full in decisions and views from this record on. "CM" stays only inside an identifier that
already has it, such as `cm-service` or `asset_cm_state`, and there it always means configuration management.
- **Configuration management:** what an item is built to and what has been done to it. That covers baselines,
  modifications and their compliance, and status accounting (EIA-649, concept aligned).
- **Condition monitoring:** what state an item is in, from what it reports and what is measured. That covers detection,
  health, prognosis and advice (ISO 17359's programme; ISO 13374's blocks, as read in §1).

The Information-Dictionary view gains a short terms section that says this, with the other terms this record uses.

## 7. Network state as an observed input

Ordered 2026-11-11 with the review, and extended the same day with the alerting path. Design only.

### 7.1 The rule

OpenDDIL treats network state as an input with provenance. It never manages the network. It never reconfigures a
route, radio, terminal or switch.

The sever-and-heal tooling is test equipment, not a feature:
- the network screen's link toggles and toxics reach the link proxy only when `linkControl.enabled` is set
  (`openddil:openddil-helm/openddil-demo/values.yaml:280-281`, default `false`;
  `openddil-demo/templates/tier-node.yaml:1304-1310`). Unset, their routes answer 404
  (`openddil:openddil-demo/gateway/pep.py:3158-3163`);
- the scripts that cut and heal a tier (`openddil:openddil-helm/scripts/sever-tier.sh`,
  `check-severance-acceptance.sh`) are rehearsal tools.

Nothing in a deployment depends on either. A commanded link state never feeds a figure. The maintainer screen already
holds this: it takes no link state, because a flipped toggle once turned a silent asset into a COMM_LOST with no data
behind it (`openddil:openddil-demo/frontend/src/MaintainerApp.tsx:231-237`).

### 7.2 What OpenDDIL measures today

- **Heartbeats.** Each tier's projector sends a heartbeat every 2 s on `link-heartbeat`, keyed by link id
  (`openddil:openddil-projector/src/edge_buffer_monitor.py:377`, `:459`). The contract calls it "per-tier proof that the
  path toward HQ is reachable" (`openddil:openddil-contracts/proto/openddil/link/v1/link_heartbeat.proto:7-20`).
- **Link status.** `link_monitor.py` derives `link_status` and `link_state` rows (`schema.hcl:933`, `:943`). A link is
  down after 15 s without a heartbeat, and is restored after 3 arrivals, with a 10 s traffic hold
  (`openddil:openddil-projector/src/link_monitor.py:50`, `:51`, `:60`).
- **A tier's own uplink.** `LinkReachability` writes `edge_buffer_status.hq_link_severed` (`edge_buffer_monitor.py:196`;
  `schema.hcl:879`, `:899`). It reads severed after twice the sum of its exchange and hold periods
  (`edge_buffer_monitor.py:100`).
- **Figures.** The screens show data age (`openddil:openddil-demo/frontend/src/lib/linkStatus.ts:78`, `:84`). An asset
  reads COMM_LOST, STALE or LOST by its own sample age and its edge link (`lib/assetTier.ts`). Link staleness enters at
  30 s and exits at 10 s (`lib/linkIndicator.ts:57-58`).
- **No network management input.** Nothing reads a network management system, SNMP or an alert. Nothing scrapes
  OpenDDIL's exporters: the chart has no scrape configuration. It deploys no Prometheus and no Alertmanager.

### 7.3 In: a network management system as an observed source

Where a deployment has a network management system (NMS), its link and device state arrive as an **observed** source.
Each arrival carries its provenance: which NMS, which probe or rule, and when. It sits beside OpenDDIL's
heartbeat-derived link state. It does not replace that state.

- **A disagreement is shown, not resolved.** When the NMS and the heartbeats disagree about a link, that is an ADR-0053
  disagreement. The left side is the heartbeat-derived `link_status` or `hq_link_severed`, which is derived. The right
  side is the NMS observation, which is observed. Detection never enforces (ADR-0053 §4).
- **Without an NMS,** the heartbeats are the source, as today.
- **At a severed edge, the screen shows both.** The NMS says why the link is down: a local terminal fault, or the far
  end. OpenDDIL says what the cut is costing:
  - the age of what each tier last heard;
  - the releases queued behind the cut. These are the bridge's lag in the broker (`bridge_group_lag`,
    `schema.hcl:891`) and the egress forwarder's retries. The forwarder retries for up to
    `OPENDDIL_FORWARD_RETRY_MAX_S` (default one day, `openddil:openddil-demo/egress/forwarder.py:105`), then holds;
  - the steps delegated to the severed tier. None are built. The local authorizer decides while severed
    (`openddil-demo/templates/tier-node.yaml:2033-2036`). ADR-0033's lateral peers and ADR-0036 §4 are design only.

**An Alertmanager-compatible webhook is one supported input format.** It is a format, not a product requirement. As
the receiver's documentation describes it, each notification carries:
- alerts that are firing or resolved;
- each alert's labels and annotations;
- its start and end times;
- a link to what generated it;
- a fingerprint.

The payload is versioned. A receiver turns each alert into the observed link-state kind (§7.6). No field is bound here.

**Alerts are operational signals.** A receiver converts them into the observed NMS-input kind, and only that. An alert
never opens an episode, a disagreement or any other finding directly. Findings come only from OpenDDIL's own detectors,
which read the observed record like any other source.

### 7.4 Use: what link quality feeds

Link quality feeds what OpenDDIL already does with it. The NMS input is one more input to these, beside the
heartbeats:
- **Debounce.** Three layers exist: the projector's restore arrivals and traffic hold, the screens' stale enter and
  exit, and the link row's own staleness.
- **Per-destination priority.** None was found. Today a release has no per-destination priority. That is a gap, and
  not part of this section.
- **Queueing.** The bridge, the egress forwarder and the ingest spool queue on their own. None is gated by link state.
- **Delegation.** Not built (§7.3).
- **Staleness on figures,** as in §7.2.

### 7.5 Out: OpenDDIL's own health for a deployment's monitoring

A deployment's NMS monitors OpenDDIL as a service through OpenDDIL's existing exporters. The outbound format is
Prometheus exposition, by concept. The format's documentation names a text format (`text/plain; version=0.0.4`) and
OpenMetrics as the effort built from it. Read 2026-11-11.

| Service | Endpoint | Metrics | Source |
|---|---|---|---|
| Projector | `:8084` (the chart sets it) | messages consumed and upserts; decode and database errors; topic lag; rows pruned; link heartbeats produced, received and rejected; element changes, evictions, refusals and restamps; effector and track counters | `openddil:openddil-projector/src/metrics.py:8-172`, served `:181` |
| Configuration management service | `:9464` by default | unknown-asset removals dropped | `openddil:openddil-cm-service/src/metrics.py:22` |
| Fusion | `:9464` by default | unknown-asset removals dropped; effector refusals, replays and detonations seen; publishes suppressed | `openddil:openddil-logistics-fusion-service/src/metrics.py:17-54` |
| DIS ingest | `:8080` `/metrics`, `/healthz/live`, `/healthz/ready` | PDUs received, decoded, filtered and dropped; decode errors; publish errors and latency; spool depth, oldest age and drops; condition claims; sidecar readiness | `openddil:openddil-sensor-ingest/dis_ingestor.py:157`, `:363-432`, `:1376-1396`; `spool.py:43`; `condition.py:58-69`; `ready.py:54` |
| Gateway (PEP) | `:9464` `/metrics` | viewer shape refusals, element views and their deletes; deliveries per destination and class; merges | `openddil:openddil-demo/gateway/pep.py:495`, `:625-676` |
| Edge stream processor | `:4196`, the processor's defaults | defaults, plus routed, dropped and forwarded counters on the DIS mappings | `openddil:openddil-demo/openddil-base-connect.yaml:6-8` |
| Regional stream processor | `:4195` | defaults | `openddil:openddil-regional-stack/connect/redpanda-connect.yaml:98-103` |

- The chart sets no metrics port for the configuration management service or fusion. They listen on their default.
- The broker, the durable-execution server, the sync service, the authorizer, the identity provider and the database
  declare no metrics in the chart. Their upstream endpoints were not read.
- Today only exercise control reads any of these, as rate sources
  (`openddil-demo/templates/exercise-control.yaml:266-281`).
- No document publishes this list. Publishing it is a row.

### 7.6 Alerting across tiers, by concept

These describe how a deployment's alerting should sit across DDIL links. OpenDDIL deploys none of it (§7.2).
- **Each tier alerts on its own.** Alertmanager can form a high-availability cluster whose peers share silence and
  notification state. Such a cluster is never stretched across a DDIL link: a cut would split it. Each tier runs and
  evaluates its own alerting, so a severed tier still alerts.
- **Upward catch-up by remote write.** Prometheus Remote-Write 1.0 is for propagating samples "reliably ... without
  loss". Its senders must retry with backoff, should buffer persistently through a receiver's outage, and must send each
  series in timestamp order. A tier writes upward. After a cut, it catches up from its buffer.
- **A link-severed alert inhibits the symptoms below it.** Inhibition mutes target alerts while a source alert exists,
  where the labels named as equal match. A link-severed alert for a tier mutes that tier's downstream staleness and
  queue alerts at its parent. The cause pages once.
- **Alerts stay signals** (§7.3).

**Rows** (in `FOLLOW-UPS.md`):
- the observed link-state kind for NMS input: observed, provenance, link or device, state, cause if given, `observed_at`.
  Its receiver takes the webhook format first;
- the exporter list in the operator documentation;
- the link-state entry in the disagreement view.

**Alignment, by concept.** FCAPS is the frame: fault, configuration, accounting, performance and security management.
OpenDDIL touches fault and performance only, and only as inputs. FCAPS's text (ITU-T M.3400) was not read. No product
is named as required.

## Decision

1. This record is the alignment of condition monitoring, built-in test and usage, by concept only, with every standard
   marked by how much was read (§1). Sd-Tx carries one row per standard at the rung its read supports.
2. ISO 13374 stays a reading. The block names are recorded as coming from a secondary source until parts 1 to 3 are
   read.
3. The gaps are rows in `FOLLOW-UPS.md`, each closed by its own increment:
   - the built-in test kind (§5);
   - the episode's detection and closure fields (§4.1);
   - the failure-mode vocabulary on the episode;
   - usage meters beyond ADR-0051's three;
   - remaining useful life as an output kind (§4.2);
   - the scoring harness (§4.3).
4. Configuration management and condition monitoring are written out in full (§6).
5. A closure is confirmed only by the completed work order's outcome, through iagent (§4.4). A closure recorded at a tier
   is declared-local and unconfirmed. A release never closes an episode. The outcome's fields are a question for iagent's
   architect.
6. The analyzer is configuration status accounting. It is not state detection, and its advice is not condition advice.
7. ADR-0057's output kinds open when the remaining-life kind is specified (§4.2).
8. Network state is an observed input with provenance, never managed (§7). An NMS disagreement with the heartbeats is
   shown, not resolved. Alerts become the observed link-state kind through a receiver, never findings. OpenDDIL's
   health goes out by its exporters. The rows are the link-state kind, the exporter list and the disagreement entry.

## Consequences

- **Positive:** a reader can tell which standard was read and which was only named. The rates and the scoring have a
  defined shape before any field is added. Each gap has an owner row.
- **Negative:** six rows, and two of them need records from the maintenance side (a confirmed failure, a closure
  reason) that only the consumer can confirm. ADR-0057's closed kinds must be opened, which is a change to a slice
  record.
- **Neutral:** no code changes. St-Tx's names stay, because they agree with the slide in concept.

## What this does not establish

- Nothing is built, run or measured.
- No conformance to any standard. No field is named from a standard.
- The definitions of ISO 14224's terms, ISO 13374's blocks, and anything in MIL-STD-1309, ROMAIN or ISO 15926: all
  unread.
- That ISO 13381-1:2025 keeps the 2015 terms.
- Which fields the maintenance action record's outcome carries, and whether every work order returns a closure reason
  and a confirmed component. That is the question to iagent's architect (§4.4).
- What any network management system reports, or how often. None was read, and FCAPS's text was not read (§7).
- The upstream metrics of the third-party services (§7.5).

## Related

- [ADR-0038](ADR-0038-anticipated-capability-envelope.md): §1, C1, C2, C7.
- [ADR-0051](ADR-0051-failure-records-for-fracas.md): episodes, meters, rollups, the seam.
- [ADR-0057](ADR-0057-declared-analytic-units-adr0034-first-engine-slice.md): the declared unit and its kinds.
- [ADR-0020](ADR-0020-prognostics-derivation-stage.md): derived values, confidence and its kind.
- [ADR-0053](ADR-0053-logistics-cyber-detection-as-surfaced-disagreement.md): the disagreement shape (§7.3).
- [ADR-0056](ADR-0056-one-identity-per-thing-every-other-id-is-an-alias.md): identities for components.
- [Citations note](CITATIONS-2026-09-08-standard-ontologies.md): the earlier verification of the ontologies.
