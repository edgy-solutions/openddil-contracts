# ADR-0057 — Declared analytic units: ADR-0034's first engine slice

## Status

**PROPOSED — 2026-11-08. This records what was built. It is not a new decision.**
- **Amended 2026-11-12: the output kinds admit `remaining_life`**, specified in
  [DESIGN-2026-11-11-remaining-life-output-kind](DESIGN-2026-11-11-remaining-life-output-kind.md), which was accepted as
  proposed that day. The set stays open (ADR-0038 C2): a further kind is added the same way, by a specification and an
  amendment. A remaining-life output is terminal under ADR-0034's composition typing, so it never goes upward. The
  amendment is applied in §1, §5 and §9 below.
- **Noted 2026-11-11: the output kinds open when the remaining-life kind is specified.** `sustainment` and `anomaly` were
  this slice's set, not a closed vocabulary (ADR-0038 C2).
- **What this is.** ADR-0034 (Accepted 2026-08-07) fenced the engine. On 2026-11-07 the project owner lifted the fence for one slice:
  - one Faust runner that loads declared units from the bundle;
  - the wear unit first and the thermal unit second;
  - the producer stamp.

  Everything else in the fence stays fenced. This record is the slice record *under* ADR-0034. Where it says "decided",
  it means decided by ADR-0034 or by that ruling. This record only writes down how the slice meets them.
- **Drafted from the code, not from a plan.** The sources were read on 2026-11-08. All the commits named below are local
  and unpushed on that date. Their shas will be re-read when they are pushed, and this record will be corrected if any
  of them is rewritten.
  - `openddil-tactical-agents`, master: the runtime, the wear unit and the replay harness (06f5b2e, 9970905, 6ea3b69,
    e443722, 485102e, 8ab3148).
  - `openddil-tactical-agents`, branch `algorithms-thermal`: the thermal unit (2654d2f, d776dc3). It is not merged.
  - `openddil-helm`, master: bundle packaging (45685b1) and the chart's render guard (fb713fa). The branch commit
    5a3b62d enables thermal.
  - `openddil-contracts`, main: `Provenance.producer_stamp` in `proto/openddil/telemetry/v1/telemetry.proto` (8bd4bb1).
- **Nothing here is deployed by this record.** The acceptance evidence is offline, and so are the tests listed below.
- The number is provisional until the record is accepted.

## What the slice is, in one paragraph

An analytic is a **declared unit**: a directory holding a `unit.yaml` and one Python file. The unit ships in the
runtime bundle, and the chart enables it by name. One Faust runner in faust-edge loads every enabled unit and gives
each one its own agent, its own durable table and its own output topic. A unit is a single method, `step(sample,
state)`. Each output is stamped as derived, names the unit, version, parameters and tier that made it, and carries
the source's labels through. Parameters are validated three times: when the chart renders, when the runner starts,
and in the bundle's CI. Nothing is downloaded at run time. A unit is accepted when the recording-and-replay harness
runs it over recorded production input and its outputs and end state match what production emitted. On the wear
port they match exactly, with no tolerance.

## Decision

### 1. A unit is declared, and the declaration is the whole interface

`algorithms/<unit>/unit.yaml` is validated against `algorithms/declaration.schema.json` by
`edge/algorithm_runtime/declaration.py`. It has these fields:

| Field | Meaning |
|---|---|
| `apiVersion` | `openddil.io/algorithm/v1`. Nothing else is accepted. |
| `unit`, `version` | The name, which must equal the directory name, and a semantic version. |
| `runtime` | `stream-parallel`, ADR-0034's Faust execution class. It is the only class this runner accepts. |
| `entrypoint` | `file.py:Class`. The class must subclass `contract.Unit`. |
| `key` | `asset_id`. |
| `composition` | `propagating` or `terminal`, ADR-0034's composition typing. |
| `inputs` | One topic, and the roles the unit reads, each `required` or optional. |
| `params` | Every tunable constant: `type` (`number` or `integer`), `default`, optional `minimum`/`maximum`, `unit`. |
| `state` | The table name, its partitions, the record namespace, and the record's fields with type, nullability and default. |
| `outputs` | Each output's `kind`, topic, `direction` (`local` or `upward`), `producer_id`, `source_protocol` and `labels`. An anomaly output also has `event_type` and `severity`. A remaining-life output also declares its meter kind, its distribution form, its horizon, its failure threshold reference, and its confidence kind or none (amended 2026-11-12). |
| `resources` | `memory_mi` and `cpu_m`: the unit's envelope (see §8). |
| `dependencies` | Must be `[]` (see §7). |

The validator refuses all of these:
- an unknown key or an unknown role;
- a default outside its own bounds;
- an output kind other than `sustainment`, `anomaly` or `remaining_life`;
- non-empty `dependencies`;
- `labels` other than `copy-source` (see §5);
- a `terminal` unit with an `upward` output.

The last refusal is ADR-0034's composition gate, built: the truncation bug cannot be written into a declaration.

**Amended 2026-11-12, the remaining-life refusals.** The validator also refuses:
- a remaining-life output with no meter kind, no distribution form, no horizon or no threshold reference;
- a remaining-life output whose confidence kind is not one of ADR-0020's declared kinds;
- a remaining-life output that is not marked advisory;
- a remaining-life output in a unit whose `composition` is not `terminal`. A distribution over one component's
  remaining use does not compose into a fleet figure, so by the gate above it is never `upward`. A fleet-level
  prognosis is a separate derived record with its own rule.

The render check (§4) refuses a remaining-life output whose meter kind is not declared for the variants the unit is
deployed to.

The roles are a closed list in `edge/algorithm_runtime/contract.py`: `position_ecef_m`, `pitch_deg`, `roll_deg`,
`sample_time_ns`, `component_temp_k` and `ambient_temp_k`. Adding a role is a change to the runtime, not to a unit.
That is deliberate. A role says how a raw field is found and converted, and the unit sees only the converted value.

### 2. One Faust runner, and it refuses at startup

`edge/algorithm_runtime/runner.py` is the only module that imports Faust. `register(app)` builds one agent, one durable
table and the output topics for each enabled unit. The table is RocksDB with a changelog and is keyed by `asset_id`.
The runner's agents sit beside faust-edge's own agents and do not share state with them. That is the ADR-0020 seam.
The table's record class is generated from the declared fields under the declared namespace. Because of that, the wear
unit's existing changelog (`prognostics_accumulators`, `prognostics.agent._AccumulatorRecord`) loads unchanged.

The runner refuses to start, and names the reason, on any of these:
- `ALGORITHMS_ENABLED` is unset;
- any legacy `PROGNOSTICS_*` variable is set, because its parameter now lives in `ALGORITHM_PARAMS_JSON`;
- `ALGORITHMS_DIR` is not a directory;
- `OPENDDIL_EDGE_ID` is unset, because every output is stamped with its tier;
- the bindings lack `producer_stamp`, which means an older contracts build;
- `ALGORITHM_PARAMS_JSON` is malformed, or names a unit that is not enabled;
- a unit's directory is missing, or declares a different unit name;
- two units claim the same table.

A wrong deployment never runs with a default it did not ask for.

Each record goes through `core.process_one`, which the replay harness also uses (§9). It parses the record, maps the
roles, calls `step`, writes the state and then sends the outputs. A record that cannot be processed is skipped and
counted, never retried in a loop and never silently dropped. The counted reasons are `parse_failed`, `no_asset_id`,
`required_role_absent`, `step_failed`, a step that changed the state's keys, and `output_refused`. Two other counters,
`sample_time_fallback` and `role_unconvertible`, count records that were processed with a fallback.

### 3. `step`, and the sliding window as state

`contract.Unit` has one method: `step(sample, state) -> {kind: payload} | None`. It has no window callback, no
lifecycle hooks, and no access to the broker or the tables. A unit reads one sample and its key's state, and returns
its outputs or nothing.

A window is state, not an engine feature. `contract.SlidingWindow(window_ns, cap)` has three methods:
- `push`;
- `in_window(now_ns)`, which keeps samples with `now − window ≤ t ≤ now`, sorted and stable;
- `to_state` and `from_state`.

Its state is JSON-safe, so a window lives in the declared state record and survives a restart through the changelog.
It reproduces the edge trends' deque-and-filter behaviour.

**There is no `on_window`.** ADR-0034's typed windows (tumbling, hopping, session) and the window-compatibility check
are engine features, and the engine stays fenced (§11). A unit that needs a window carries one in its state.

### 4. Parameters are a schema, checked at render

Every tunable constant is a declared parameter with a type, a default and optional bounds. The defaults equal the
constants of the code being ported, so enabling a unit with no overrides reproduces it.

A parameter is checked in three places, and all three refuse the same things:
- **At chart render.** `openddil-demo/templates/_algorithms.tpl` (`openddil.algorithms.validate`) reads the chart's copy
  of each enabled unit's declaration. It fails the render on any of these:
  - an empty, duplicate or undeclared entry in the enabled list;
  - an apiVersion or unit-name mismatch;
  - overrides for a unit that is not enabled;
  - an undeclared parameter, a wrong type, or a value outside the declared bounds;
  - the legacy `faustEdge.prognosticsEnv`;
  - the envelope sum (§8).

  A bad override never reaches a cluster.
- **At bundle build.** `scripts/check-algorithm-declarations.sh` byte-compares the chart's copy
  (`openddil-demo/files/algorithms/<unit>/unit.yaml`) with the source in the bundle. The render check reads the copy,
  so this is what makes it read the truth. Exit 2, a check that could not run, is never a pass.
- **At startup.** `declaration.resolve_params` refuses an unknown or out-of-range override.

`config_hash` is the sha256 of the canonical JSON of `{unit, version, params}`, taken after the overrides are resolved.
Two tiers running the same unit with the same parameters stamp the same hash.

### 5. Derived provenance, the stamp, and the labels

**Provenance.** Every output is stamped `ORIGIN_DERIVED` with confidence 0.0. A unit cannot set its own provenance:
a payload that sets `value_provenance` is refused (`output_refused`).

The confidence is 0.0 because a derived value has no measured confidence, and a number above zero would claim one
(ADR-0020).

**A remaining-life output (amended 2026-11-12)** is stamped `ORIGIN_DERIVED` with confidence 0.0, like every output.
Its prediction confidence is a separate value with a declared kind. An asserted confidence comes from the declaration,
never from the unit. A payload that sets an asserted confidence, or sets advisory to false, is refused
(`output_refused`).

**The producer stamp.** Every output carries `producer_stamp {unit, version, config_hash, tier}`. The stamp is ADR-0034's
mandatory provenance stamp, in the shape the 2026-09-08 addendum fixed. `model_artifact_hash` is reserved and empty,
because no unit in this slice carries a model.

**What an anomaly may say.** An anomaly payload may carry only `summary` and `evidence`, where `evidence` maps strings
to numbers. The declaration supplies the severity, event type and envelope, so a unit cannot raise its own severity.

**Labels today: copy-source.** The labels are a pure passthrough of the source sample's `originator_nation` and
`releasable_to`, with no fallback from the environment (ADR-0029 §3). An anomaly copies them only if the source is
labelled. `copy-source` is the only value the declaration accepts.

**Labels next: high-water, as a separate change.** ADR-0055 §3b's rule for a single derived record is the high-water
of its inputs:
- a hierarchical dimension takes the highest;
- a permissive set takes the intersection of audiences;
- a restrictive or exclusionary set takes the union;
- an unlabelled input leaves the result unlabelled.

It becomes the rule for these units after ADR-0055 is accepted. It is a separate, predicted change, not part of this
slice (the project owner, 2026-11-07), for two reasons:
- The wear unit is a lifetime accumulator. Its high-water is the intersection over every sample that ever contributed,
  so the table record must carry label state. That changes the changelog's format, which is a migration and not a port.
- The record the label applies to is the tier's `telemetry_latest_state` row for the asset. Matching to that row is the
  acceptance for the change, and it has its own prediction.

When it lands, the declaration gains a second `labels` value and the validator accepts it. `copy-source` stays valid for
a unit whose output is one-to-one with its input.

### 6. Packaging: the units ride the bundle

`bundle/Dockerfile` copies `openddil-tactical-agents/algorithms` into the runtime bundle at `/bundle/agents/algorithms/`.
The chart mounts it in faust-edge at `/opt/openddil/algorithms`, which is `ALGORITHMS_DIR`. A unit is versioned with the
bundle that carries it, and it reaches a tier on the same seam as the rest of the bundle. A tier runs only units that are
in its bundle *and* named in its values.

### 7. Dependencies are pinned in the image, never fetched

A unit has no dependencies of its own. `dependencies` must be `[]`. `edge/algorithm_runtime/guard.py` checks each unit's
source statically, before it is imported:
- imports are limited to `__future__`, `math`, `dataclasses`, `typing` and `algorithm_runtime.contract`;
- these names are refused: `__import__`, `eval`, `exec`, `compile`, `open`, `globals`, `locals`, `vars`, `getattr`,
  `setattr`, `delattr`, `breakpoint` and `input`;
- every dunder attribute is refused.

A refusal names the file and line.

The guard is **a guard against accident in a bundle someone reviewed, not a sandbox.** That sentence is the docstring's
own. A unit is code the bundle's reviewers accept, and the guard makes a stray import or a file open fail loudly. It
does not make untrusted code safe, and this record does not claim that it does.

**No run-time downloads.** No unit, runner or chart path fetches anything at run time. There is no package install, no
model pull and no remote declaration. Everything a tier runs is in its image and its bundle, which is what lets a severed
tier start.

The image's own dependencies are an **open item** (see Open items). The rule is that they are pinned in the image.
Today they mostly are not.

### 8. Resource envelopes are declared and summed at render

Each unit declares `resources {memory_mi, cpu_m}`. The render guard sums the enabled units' envelopes and fails if the
sum exceeds faust-edge's `resources.limits`. It parses Mi and Gi, and m and whole cores, and refuses anything else rather
than guessing. Enabling one more unit can therefore fail the render, but it cannot silently push faust-edge past its
limit.

| Unit | Envelope | Status |
|---|---|---|
| wear | 16 Mi, 20 m | Declared for the port. |
| thermal | 8 Mi, 10 m | Declared in the file as "unmeasured; a ceiling for the render check, not a measurement". |

An envelope is a declared ceiling. It is not a measurement until a run measures it.

### 9. Acceptance is the recording-and-replay harness

`edge/algorithm_runtime/replay.py` feeds recorded raw records through `core.process_one`, the same function the runner
uses. It then diffs the unit's outputs and end state against what production emitted over the same window.
- **The recording.** Lines are `offset ts_ms key_b64 value_b64`, gzipped, in files named `<topic>.<first>-<last>.gz`.
  The changelog snapshot's state is the last value per key.
- **What it imports.** It does not import Faust, and it streams with bounded memory.
- **Count-only units.** A unit with no sustainment output has nothing to compare, so it runs COUNT-ONLY and says so in
  its report. For such a unit, "equal" means nothing, and the report does not print it.
- **Remaining-life outputs (amended 2026-11-12).** They are compared like a sustainment output: exactly, unless a
  tolerance is declared in advance with its reason. A distribution is compared parameter by parameter, or quantile by
  quantile.
- **CI.** The step "replay harness" in `tests.yml` runs `tests/test_replay.py` on synthetic recordings, with sockets
  disabled.

A port is accepted when, on the frozen oracle and then on the recording, the outputs and the end state match production.
The comparison is exact unless a tolerance is declared in advance with its reason. The wear port declared none.

### 10. The evidence as built (offline, 2026-11-08)

**Wear, old code against new unit.** Five scenarios: defaults, demo, zero-life, mid and tight-bands. Each has 2,400
seeded samples, 12,000 in all. The comparison is exact:
- the state JSON is equal;
- the events are equal once the ids, the wall-clock fields and the stamp are cleared, since those three differ by design.

There is no tolerance. The frozen oracle is `tests/oracle/prognostics_v0`.

**Thermal, old rule against new unit.** 24 cases pass with exact floats, against the frozen oracle
`tests/oracle/detection_v0`. The full suite on the thermal branch is 193 passed.

**Thermal over the recording.** A count-only run over 4,168 records gave 0 alerts. None of the 4,168 records carries a
temperature, so the test deployment has no thermal input. The run shows that the unit skips and counts correctly. It does
not show that the unit detects anything, and this record does not claim that.

**The match to production, not yet run.** The seven-day recording ends 2026-11-15 02:15Z. The wear match-to-row over it
comes after that, and this record will be amended with the result.

## Open items, stated as they are

- **The image is not pinned.** `edge/Dockerfile` pins only `pint==0.24.4`. Here is what the rest have:

  | Dependency | Constraint in the Dockerfile |
  |---|---|
  | `faust-streaming` | `>=0.10.0` |
  | `aiokafka` | `<0.12.0` |
  | `protobuf` | `>=6.30.0,<7.0.0` |
  | `python-snappy` | none |
  | `pyyaml` | none |
  | `watchdog` | none |

  A `uv.lock` exists but the Dockerfile does not install from it. "Pinned dependencies" is the rule this record sets. It
  is not a property of today's image. Closing it means installing from the lock, so that a rebuild of the same commit
  gets the same packages.
- **Nothing is pushed.** Every commit named in Status is local on 2026-11-08.
- **Thermal is on a branch.** Its unit and the chart commit that enables it are not merged.
- **`temp_ewma_k`.** The thermal state keeps an EWMA that the decision does not read, so that the state matches the
  original rule exactly. Using it or dropping it is a design change. The project owner ruled on 2026-11-08 that it comes out only
  after the match-to-row, in its own commit.
- **Celsius.** The UCUM code `Cel` is not convertible today, so a sample with it is counted as `role_unconvertible` and
  its temperatures are skipped. A fix is on a separate branch. It is not part of this slice.
- **A behaviour change, named.** Thermal alerts now carry the source's labels. The original rule's alerts carried none.
  That follows ADR-0029 §3, but it is a change, and anyone reading the old alerts should know it.
- **ADR-0055 cites a retired path.** Its finding 4 cites `edge/prognostics/agent.py:197-198` as the place where a derived
  record copies its labels. That module is retired, and the copy now lives in `edge/algorithm_runtime/outputs.py`. The
  finding still holds, because no derived record computes the high-water. Only the citation is stale. It is corrected in
  ADR-0055's own change, not here.

## What stays fenced

The 2026-11-07 ruling lifted the fence for this slice only. ADR-0034's fence otherwise stands:
- the aggregation engine and the primitive algebra;
- typed windows and `on_window`;
- any change to faust-regional;
- the fusion migration, so detection at regional and HQ tiers stays as it is;
- the hierarchy coherence validator;
- all of model training and MLOps.

`durable-workflow` (Restate) units are out of scope. The runner accepts `stream-parallel` only.

## What this does not establish

- That any unit has run on a cluster. Everything in §10 is offline.
- That the guard is a security boundary. It is not (§7).
- That an envelope is a measurement (§8).
- That the labels are correct for an accumulator. They are the passthrough, and §5 says why the high-water is a separate
  change.

## Related

- [ADR-0034](ADR-0034-tier-analytics-are-deployment-configuration.md): the decision this slice is under. That covers
  execution classes, composition typing, parallelism as a registration contract, the provenance stamp and its
  2026-09-08 addendum, and the fence.
- [ADR-0020](ADR-0020-prognostics-derivation-stage.md): the input and output seams the runner's agents keep, and the confidence field for derived
  values.
- [ADR-0029](ADR-0029-coalition-releasability-abac-enforcement.md) §3: labels are carried from the source, with no
  environment fallback.
- [ADR-0055](ADR-0055-a-label-is-a-set-of-declared-dimensions.md) §3b: the high-water rule that replaces `copy-source`
  after acceptance.
