# ADR-0053 — Logistics cyber detection as surfaced disagreement

## Status

**PROPOSED — 2026-10-29.** Design only. Nothing here is built or deployed.
- It adds detectors over records the stack already keeps, plus one outbound kind.
- It adds no new enforcement point. Enforcement stays where `openddil:ADR-0029` (the PDP and PEP),
  `openddil:ADR-0043` (the egress gate) and `openddil:ADR-0046` (intake) put it.

## Findings first: six premises that are not true today

1. **An undeclared application id is published, not counted.**
   - Only *declared* non-asset sources are filtered: `_non_asset_source` → `dis_pdus_filtered_total{reason="non_asset_source"}`
     (`openddil:openddil-sensor-ingest/dis_ingestor.py:1150-1175`).
   - An unknown (site, application) pair flows on, and its only effect is skipped appearance decoding
     (`appearance.py:13-16`). No counter and no reason label exist for it.
2. **The gate counters are not per source, and are not metrics.**
   - The egress gate, intake, forwarder and assembler each keep an in-process dict and write it to JSON log lines:
     - egress gate: by reason and by `class:<c>` (`openddil:openddil-demo/egress/gate.py:608, 694-695`);
     - forwarder: every 60 s (`forwarder.py:110, 1017`).
   - They count decisions about records, not traffic from sources.
   - The only per-type ingest counter is `dis_pdus_received_total{pdu_type}`, which has no source label.
   - "Per-source rate anomalies from the gate counters" has no input today.
3. **Nothing checks time order or kinematics at run time.**
   - `telemetry_latest_state` upserts are last-write-wins with no newer-sample guard
     (`openddil:openddil-projector/src/persistence/postgres.py:270-300`).
   - `Provenance.source_sequence` is on the wire, documented as "helps detect drops", and consumed by nothing.
   - Order and duplicate rules exist only offline, in the Contract-B validator (`conflicting_duplicate`,
     `order_regression`, `timestamp_invalid`;
     `openddil:openddil-customer-bundle-example/conformance/contract-b/validate.py:101, 284-299, 689-708`).
   - No speed or kinematic plausibility check exists.
4. **Duplicate ids are caught at render, not at run time.** `check-entity-assignment.sh` fails a render that admits one
   id in two sidecars. Two live sources claiming one id are not compared.
5. **"Configuration tamper from the as-maintained baseline" has no observed side.**
   - The CM analyzer compares the as-maintained record, built from *declared* CmEvents, against the authorized baseline
     (`openddil:openddil-cm-service/src/discrepancy/analyzer.py:144-175`).
   - It catches a declared unauthorized change. It cannot catch an undeclared one, because no configuration is
     observed from the asset.
   - `AssetIdentity.configuration_baseline` on the wire is filled from the ontology default, not from the asset
     (`openddil:openddil-demo/dynamic-mappings/sim-dis-mapping.yaml:160`).
   - Tamper detection needs an observed configuration source first.
6. **The writer and consumer census runs only during a reset.** It is phase 3b of `reset-scenario.sh`
   (`openddil:openddil-helm/scripts/reset-scenario.sh:2400-2456`; `--writer-census-only` at :2631-2649), which prints
   `UNDECLARED` / `UNDECLARED CONSUMER`. There is no runtime census.

Also not found:
- a label change made without a declaration, as a detector;
- NIST SP 800-82, ATT&CK for ICS, STIX or CJCSM 6510, in either repo.

## Context

A logistics picture is a target because people act on it. The attacks that matter here are not the ones that take the
picture down. They are the ones that make it lie:
- a phantom asset;
- a duplicated id;
- a replayed "operational";
- an unlabelled record relabelled in passing;
- a readiness claim that no observation supports.

The stack's design already refuses to collapse sources: every record names its producing tier, and labels move only on
a declaration. Detection is the same rule turned outward. **When two things that should agree do not, say so, with
provenance, and do not pick a winner.**

## What exists today

### Hardening (done)

| control | where |
|---|---|
| per-tier PEP in front of Electric, asking the tier's own PDP; `TOPAZ AUTHZ DENIED` lines | `openddil:openddil-demo/gateway/pep.py:2-27, 265`; `openddil:ADR-0029` "Per-tier PDP" |
| releasability policy (OPA via Topaz) | `openddil:openddil-demo/policy/releasability.rego` |
| labels stamped at ingress; completeness gate | `openddil:ADR-0029` §3, §7 |
| egress gate with named refusals; fail closed | `openddil:ADR-0043` §7-9; `egress/gate.py:82-124` |
| intake gate with named refusals; `intake_records` ledger | `openddil:ADR-0046` §5; `egress/intake.py:94-101`; `schema.hcl:1416` |
| egress ledger, never downgraded | `egress_delivered_events` (`schema.hcl:1935`); `forwarder.py:520-545` |
| ingress TLS with https redirect; TAK mTLS (ghostunnel, `--allow-cn`, digest-pinned) | `openddil:openddil-helm/openddil-demo/values.yaml:1281-1314, 1509-1529` |
| NetworkPolicies limiting Electric, panes, cm-intake and exercise control to their PEP | `templates/{egress,releasability,tier-node,hub,exercise-control}.yaml`; `_helpers.tpl:2778` |
| non-root and read-only root in egress | `templates/egress.yaml:959, 1040-1041` |
| image digest check (run by hand) | `openddil:openddil-helm/scripts/check-image-pins.sh` |
| declared writers and consumers, checked at render and at reset | `check-produces-declarations.py`, `check_consumer_declarations.py`; reset phase 3b |

### Hardening (on rows or not present)

| gap | state |
|---|---|
| per-tier identity | `openddil:ADR-0045`, PROPOSED |
| digest check in CI | not wired into `chart-checks.yml` |
| non-root chart-wide | egress only |
| service-to-service mTLS | not present |
| SBOM and image signing | not present |

### Detector inputs

| detector | input today |
|---|---|
| undeclared app id | none (finding 1) |
| duplicate id across sources | render-time check only |
| impossible kinematics | `telemetry_latest_state.kinematics`, `last_sample_at`; no check |
| replayed timestamps | `Provenance.sample_time`, `source_sequence`; no check |
| per-source rate | none (finding 2) |
| configuration tamper | declared side only (finding 5) |
| label change without declaration | `asset_declaration{originator_nation, releasable_to, declared_by, declared_at, source, owning_tier}` (`openddil:ADR-0050`); the intake's `label_mismatch` |
| census | reset phase 3b only (finding 6) |
| false readiness | observed `telemetry_latest_state` (`operational_status`, `health_state`, `reporting_status`, `provenance`); declared `asset_cm_state.overall_status`, `asset_declaration`, `asset_fielding`; derived `asset_logistics_status{overall_severity, constraining_factors, computed_at}` |
| audit | `egress_delivered_events`; `intake_records`; gate decision lines `{decision_id, outcome, reason, policy_version, ts}` |

## Decision

### 1. Every detector is a disagreement between two named records

A detector never infers intent. It names two records that should agree, shows that they do not, and attaches both
provenances. One output shape serves every detector: an **indicator**.

```
indicator: { indicator_id, detector, asset_id?, source?, owning_tier,
             left:  {record, columns, value, provenance},
             right: {record, columns, value, provenance},
             opened_at, closed_at?, count }
```

It opens and closes like an episode (`openddil:ADR-0051` §1), and its history is kept. Each side's `provenance`
names its source class (observed, declared or derived). An indicator never merges two sides into one entry.

| detector | left | right | new work |
|---|---|---|---|
| `undeclared_source` | (site, app) seen at ingest | the declared sources and admit list | a counter with a source label at ingest, plus a bounded table of first and last seen |
| `duplicate_id` | id from source A | the same id from source B within a window | a per-id (producer_id) last-seen map at ingest |
| `implausible_motion` | position at t₁ | position at t₂ | a speed bound per variant (overlay; the `movement.standards` home) |
| `time_regression` | stored `last_sample_at` / `source_sequence` | the incoming sample | a newer-sample guard that counts, rather than silently overwrites |
| `source_rate` | per-source received rate | that source's declared or learned band | the source label from the first row; the band as overlay data |
| `config_drift` | observed configuration (software version, CI serial) | the as-maintained record | **an observed configuration source** (finding 5); until one exists, this detector is declared and absent |
| `undeclared_relabel` | the label on record n | the label on record n-1, with no `asset_declaration` between them | a per-asset last-label read at the projector |
| `undeclared_writer` | a writer or consumer seen on a topic | `produces.yaml` and the consumer declarations | the reset census, run on a schedule, read only |
| `readiness_disagreement` | one of observed, declared or derived | another of the three | a read; no new store (§2) |

### 2. False readiness: three sources side by side, never collapsed

Readiness has three sources at a tier:
- **observed:** what the asset reports (`telemetry_latest_state`, with its `provenance`);
- **declared:** what people have stated (`asset_cm_state.overall_status`, `asset_declaration`, `asset_fielding`);
- **derived:** what fusion computed (`asset_logistics_status.overall_severity`, `constraining_factors`).

The view shows all three for one asset. Each shows its value, its producing tier, its source and its time.

The system never computes a single "true readiness". When two sources fall into different readiness bands, the view
marks the pair as disagreeing and opens a `readiness_disagreement` indicator. The FMC/PMC/NMC vocabulary stays where it
is today, at egress only (`openddil:openddil-customer-bundle-example/dynamic-mappings/egress/system-b-egress-fmc.yaml`).
The band mapping per variant is overlay data.

False readiness looks like:
- observed `destroyed` while derived is green;
- declared in compliance while observed `health_state = failed`;
- derived green while the asset has been silent past its window.

Every one of them is a disagreement the view can show **without** knowing which source is lying.

When a `readiness_disagreement` leaves (§3), it carries **all three sources**, not only the disagreeing pair. Each
source is its own provenance entry, with its class, value, producing tier and time. On iagent's side the three arrive
as **three provenance entries, never one** (`iagent:ADR-0063`). The no-single-readiness rule therefore holds past the
seam as well as on our screen.

### 3. Indicators leave as a kind and as STIX, through the same gate

- **To iagent:** a new overlay kind, `CyberIndicator`, released through the existing gate (`openddil:ADR-0046` §4).
  Key `/indicator_id`; episode `(/detector, /asset_id or /source, /opened_at)`.
  - iagent reserves the content kind **`cyber_indicator`** at its door. `iagent:ADR-0063` is the receiving half. The
    destination sends `CyberIndicator` as `content_kind: cyber_indicator`.
  - It arrives as an event carrying `on_behalf_of`, our `episode_id` and our `asset_id` (or the source, for a
    source-keyed detector). `on_behalf_of` is declared per kind in the overlay, and which subject it names is
    confirmed against `iagent:ADR-0063` before the kind is frozen.
  - The left and right sides travel as separate `provenance[]` entries, each keeping its source class. iagent passes
    them through unmerged (`iagent:ADR-0063`).
- **To a SOC:** the same indicator rendered as a STIX indicator plus an observed-data pair, to a declared destination.
  - Same gate, same labels, same refusals. An indicator about a coalition asset is releasable only where the asset is.
  - The detector vocabulary maps to ATT&CK for ICS technique names by concept, in an overlay table, so a SOC reads
    familiar terms.
- **Reporting:** an incident report under CJCSM 6510 is a person's act. OpenDDIL provides the indicator and the audit
  trail (egress ledger, intake records, gate decision lines). It does not file the report.

### 4. Detection never enforces

A detector opens an indicator and does nothing else:
- it never drops, quarantines or relabels a record;
- it never refuses a release.

Enforcement stays at the PEP, the gates and the declarations. A detector that acted would let an attacker who can
trigger it switch off the picture, and that is the attack this ADR exists to surface.

## What is new

- An `indicator` record with open/closed history (§1).
- Nine detector declarations, five of which need new ingest or projector counting (§1 table).
- The readiness view (§2) and its band mapping per variant (overlay).
- The `CyberIndicator` kind (sent as `content_kind: cyber_indicator`, reserved on iagent's side), a STIX rendering
  for a declared SOC destination, and an ATT&CK-for-ICS concept table (§3).
- A source label on ingest counters, and a newer-sample guard that counts.
- Unchanged: the PEP, the gates, the labels, the declarations and the egress ledger.

## Alignment declared (ADR-0038 C1 intake)

**By concept name only.** No schema text, element names or code lists are copied here or into the kinds.

| OpenDDIL | aligned to | concepts named |
|---|---|---|
| hardening table, detectors at the logistics layer | NIST SP 800-82 | ICS security architecture, monitoring, defense in depth, boundary protection |
| detector vocabulary (§1) | MITRE ATT&CK for ICS | spoof reporting message, rogue master, manipulation of view, modify parameter (by technique concept, not id) |
| indicator out (§3) | STIX 2.1 | indicator, observed-data, sighting, relationship |
| reporting and audit (§3) | CJCSM 6510.01 | incident, event, reportable incident, reporting chain |

The field names are OpenDDIL-local, with a declared alignment intent. Binding them to named elements is owed before any
field is frozen.

## First demo-able slice

**"Three sources, one asset, no collapse." About 3 days.**

Scope:
1. **A read, 1 d.** A PEP-mediated endpoint returns, for one asset:
   - observed: `operational_status`, `health_state`, `reporting_status`, `last_sample_at`, `provenance.edge_id`,
     `provenance.producer_id`;
   - declared: `asset_cm_state.overall_status`, `as_of`, and the latest `asset_declaration` `declared_by` /
     `declared_at`;
   - derived: `asset_logistics_status.overall_severity`, `constraining_factors`, `computed_at`.

   The same labels and the same PDP apply, with no new table.
2. **One pane, 1 d.** Three columns. Each shows its value, its tier, its source and its time. A pair is marked when
   its bands differ. There is no rolled-up "readiness" anywhere.
3. **The band mapping, 0.5 d.** One overlay file for the lab's two variants, mapping each source's values to
   ready / limited / not-ready.
4. **Run, 0.5 d.** On edgy-lab:
   - one asset where the three agree;
   - 1010 with an open CM discrepancy (declared red, observed operational): marked;
   - one asset silent past its window (derived from stale input): marked.

   For each claim, assert the mark's state and the cell text, and take a screenshot.

Out of the slice:
- the indicator record;
- every other detector;
- the kind and STIX;
- the ATT&CK table.

The slice sends nothing.

**Demo line:** "The asset reports operational, the CM record says not compliant, and fusion says limited. Here is who
said each, from which tier, and when. We don't pick one."

## Generalization debt

**GD-17** (`GENERALIZATION-DEBT.md`): the slice's disagreement mark compares sources through one three-band mapping
(ready / limited / not-ready), rather than a vocabulary each variant declares. A variant whose readiness does not fit
three bands is forced into them. Status `open`.

## Consequences

### Positive
- Every detector is explainable as "these two records disagree". An operator can check it against the record without
  trusting a model.
- Indicators ride the existing gate, so a coalition indicator is released only where its asset is.
- Detection never enforces, so a triggered detector cannot be used to blind the picture.

### Negative
- Five detectors need new counting at ingest or the projector, on the hottest path.
- `config_drift` stays absent until an observed configuration source exists. The ADR declares a detector it cannot yet
  run.
- Learned rate bands would be the first learned threshold in the stack. Declared bands come first.

### Neutral
- The census already exists. Running it on a schedule changes when it runs, not what it checks.

## Related
- `openddil:ADR-0029`: labels, the PDP and PEP, and the completeness gate.
- `openddil:ADR-0043`: the egress gate, named refusals, fail closed.
- `openddil:ADR-0045`: per-tier identity (on the hardening rows).
- `openddil:ADR-0046`: kinds, the gate and intake.
- `openddil:ADR-0050`: declarations as a label source.
- `openddil:ADR-0051`: the open/closed episode shape.
- `openddil:ADR-0052`: hazard findings, the sibling finding shape.
- `iagent:ADR-0063`: the receiving half; reserves `cyber_indicator`, keeps source classes unmerged, and receives the
  false-readiness view's three sources as three provenance entries.
