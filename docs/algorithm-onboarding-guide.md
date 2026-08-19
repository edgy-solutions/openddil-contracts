# Algorithm Onboarding Guide — bringing external algorithms into the analytics planes

**Scope.** How a team with an existing algorithm implementation — typically
C, but the shape holds for Fortran, MATLAB-generated code, or a vendor
binary — lands it in OpenDDIL's analytics planes: collection, aggregation,
detection.

**Sibling document.** [`openddil-demo/docs/protocol-onboarding-guide.md`](../../openddil-demo/docs/protocol-onboarding-guide.md)
does the same job one plane over, for *ingress*. If the code in hand is a
wire-format parser rather than an analytic, that guide — and
[ADR-0030](../decisions/ADR-0030-two-stage-configurable-ingress.md) — is
the right destination, not this one.

**Status of the target.** [ADR-0034](../decisions/ADR-0034-tier-analytics-are-deployment-configuration.md)
states the invariant this guide serves — analytics are deployment
configuration, algorithms live in code behind a registry — and **fences the
engine that would enforce it**. Aggregation and detection are hardcoded
today ([GENERALIZATION-DEBT](../decisions/GENERALIZATION-DEBT.md) GD-07).
So an algorithm landed now lands *interim*, in the shape the engine will
expect. §6 says what that obliges.

---

## 1. Classify the code before choosing a seam

Two of the four common answers are not the algorithmic path at all.

| If the code is… | It belongs in | Reference |
|---|---|---|
| A binary wire-format parser (PDU / ASTERIX / datalink grammar) | Stage 1 decoder sidecar — **not** detection | [ADR-0030](../decisions/ADR-0030-two-stage-configurable-ingress.md) |
| Semantic field mapping onto Silver | Bloblang, Stage 2 — **not** detection | [ADR-0030](../decisions/ADR-0030-two-stage-configurable-ingress.md), [ADR-0010](../decisions/ADR-0010-feed-integration-strategy.md) |
| Per-sample analytics — filtering, DSP, EWMA/z-score, Kalman, thresholding, classification | **Detection plane** | §2 |
| Accumulation — wear, fatigue, duty cycle, remaining useful life | **Prognostics derivation** | [ADR-0020](../decisions/ADR-0020-prognostics-derivation-stage.md) |
| Rollup math over many assets | **Aggregation plane** — read §6 composition typing first | [AUDIT-2026-08-07](../decisions/AUDIT-2026-08-07-aggregation-composability.md) |

The distinction that matters: *decoding* turns bytes into fields, and
*mapping* turns fields into meaning. Neither is an algorithm in this
guide's sense, and both have cheaper homes.

## 2. Where the seams are

Each seam below is already a pure, framework-agnostic function boundary —
no Faust, Restate, Kafka, or protobuf type crosses it
([ADR-0014](../decisions/ADR-0014-restate-vs-faust-placement.md) §anti-patterns,
ADR-0006 persistence/computation separation). **That boundary is the plug
point.** External code goes behind it and never sees the engine.

| Seam | File | Signature | Execution class |
|---|---|---|---|
| Edge detection | `openddil-tactical-agents/edge/detection/algorithms.py` | `(EventView, AssetState) -> Anomaly \| None` | stream-parallel (faust) |
| Edge prognostics | `openddil-tactical-agents/edge/prognostics/models.py`, `accumulators.py` | derivation over accumulated state | stream-parallel |
| Fusion / durable detection | `openddil-logistics-fusion-service/src/fusion/rules.py` | `(FusionInputs, Thresholds, now_ns) -> AssetLogisticsStatus` | durable-workflow (Restate) |
| Regional aggregation | `openddil-tactical-agents/regional/aggregator_app.py::_emit_rollups` | rollup emission | stream-parallel |

**Placement has a DDIL consequence, not just a tidiness one.**
`logistics-fusion-service` renders once in `hub.yaml` and reaches *down*
into the edge brokers (ADR-0034 §Investigated finding). An algorithm landed
there computes nothing for a severed edge. If its answer matters while
disconnected, it goes at an edge seam, on the tier that owns the inputs.

## 3. Wrapping strategy

Ranked. Pick the highest one that fits; each step down buys something
specific and costs operational surface.

1. **Transliterate to Python/numpy.** Right answer more often than teams
   expect — roughly, kernels under a few hundred lines of arithmetic. No
   build chain, no ABI, no distribution problem, and the original binary
   becomes the test oracle (§5).
2. **Keep the native code, wrap it** — `cffi` (ABI mode) or
   pybind11/Cython, built as a wheel installed into the service image.
   Service base images are `python:3.11-slim` (glibc/Debian), so manylinux
   wheels install directly. **Check arch** if edge nodes are not x86-64.
3. **Sidecar with an IPC seam** — the ADR-0030 pattern one plane over. Use
   when the code is export-controlled, non-redistributable, crash-prone, or
   drags a large runtime. Costs a hop; buys isolation and a licence
   firewall.
4. **WASM (wasmtime).** One arch-neutral sandboxed artifact; makes
   distribution identical to the ONNX-class case ADR-0034 already designed
   for. Slower per call.
5. **`P/Invoke`** if the algorithm lands in the C# edge SDK
   (`openddil-edge-dotnet`) rather than a Python service.

## 4. Shape of the landing

Two files, no engine edits.

**The wrapper** — one pure function, framework-agnostic types in and out,
units converted at the boundary, native unit declared:

```python
# Native unit: Kelvin (matches the upstream kernel; see thermal_runaway)
def thermal_margin(ev: EventView, st: AssetState, *, params: Params) -> Anomaly | None:
    if ev.component_temp is None:
        return None
    k = ev.component_temp.to("kelvin").magnitude
    score = _lib.margin(k, params.tau_s, st.native_state)   # the wrapped kernel
    ...
```

**The registration** — mirror the codebase's one existing registry,
`register_strategy` in [`openddil-projector/src/edge_assignment.py`](../../openddil-projector/src/edge_assignment.py):

```python
@register_detector("thermal_margin")
def _build_thermal_margin(cfg: dict) -> Detector:
    return thermal_margin_detector(Params(**cfg))
```

Register a **parameterized family, not a singleton.** Every magic constant
lifted out of the original source becomes a typed binding parameter. The
failure mode otherwise is invisible: each new threshold becomes its own
registry entry, each addition looks reasonable, and the registry bloats
back into the hardcoding it replaced.

## 5. Verification

- **Golden vectors first.** Capture inputs → outputs from the existing
  build *before* touching anything. This is the entire safety net for both
  transliteration and wrapping, and it is cheap only while the original
  still runs.
- **Parity tests** run the vectors through the wrapper. State the float
  tolerance and why it is what it is.
- **Verify by running**, not by reading the wiring — deploy and observe the
  emitted events (`rpk`), per
  [ADR-0025](../decisions/ADR-0025-build-pass-deployment-verification-discipline.md).
- A guard is only a guard once it has been seen red for the right reason
  ([ADR-0037](../decisions/ADR-0037-verification-evidence-is-a-deliverable.md)
  clause 3).

## 6. Constraints that will bite

**Interim posture.** ADR-0034 constraint 1 forbids new hardcoded detectors
and aggregations. A unit landed before the engine exists is marked interim
in code and recorded against GD-07 — so a shortcut cannot later be read as
a design.

**Determinism, if it runs under Restate.** `asset_logistics.py` evaluates
*inline* in the handler, so the call re-runs on replay. Native code with
`static` state, RNG, wall-clock reads, or file I/O will silently diverge
between the original execution and its replay. Either purify it, or wrap
the call in `ctx.run()` so the result is journaled. The same hidden statics
break Faust's partition-parallelism, so the fix is worth making rather than
working around.

**Execution class is declared, not assumed.** Per-key durable state or
timers → durable-workflow (Restate). High-rate stateless-per-record →
stream-parallel (Faust). ADR-0014's placement guide answers this.

**Provenance is mandatory.** ADR-0034 requires `{detector, version,
config_hash, tier}` on every detection event, and `model_artifact_hash` for
ML. **A compiled kernel is the same class of object** — an opaque binary
that produced an alert — so stamp the library build hash *and* the upstream
source revision. "Which binary produced this" is the first question a
post-incident review asks, and it is unanswerable retroactively.

**Scores are terminal; events propagate.** A score may not be emitted
upward or averaged across tiers — averaging two children's scores produces
a number that looks meaningful and isn't (ADR-0034 §ML composability).
Emit a typed detection event, which aggregates upward by counting like any
event stream.

**Units.** [ADR-0013](../decisions/ADR-0013-physical-quantity-consistency.md)
— external kernels carry *implicit* units, and the mismatch is silent.
Convert at the wrapper and declare the native unit in the docstring, the
way `thermal_runaway` declares Kelvin.

**Edge footprint.** [ADR-0021](../decisions/ADR-0021-edge-hq-topology-is-load-bearing.md)
— image size, target arch, no accelerator assumptions.

**Releasability.** Code that cannot be redistributed does not enter the OSS
repositories. Ship the compiled artifact over the distribution seam
ADR-0034 names (policy bundles → registry-sync → model artifacts); a native
unit is that seam's next passenger. Same posture as the controlled-spec
formats in ADR-0030 §Context.

## 7. Suggested slicing

1. Classify (§1); pick one algorithm; capture golden vectors from the
   existing build.
2. Wrapper at the chosen seam; parity tests green.
3. Interim registry entry + binding config + execution class + provenance
   stamps.
4. Packaging (wheel or sidecar), image, helm values; verify live.
5. Record the debt against GD-07. If the landing establishes a new rule —
   e.g. *a native unit is three artifacts: wrapper + versioned binary +
   binding config* — that is an **amendment to ADR-0034**, the direct
   generalization of its ML-units section, not a new ADR.

## Related

- [ADR-0034](../decisions/ADR-0034-tier-analytics-are-deployment-configuration.md) — the invariant, the config/code line, composition typing, provenance stamps.
- [ADR-0014](../decisions/ADR-0014-restate-vs-faust-placement.md) — which engine hosts the unit, and the boundary discipline that makes this guide possible.
- [ADR-0030](../decisions/ADR-0030-two-stage-configurable-ingress.md) — the ingress equivalent; where parsers go instead.
- [ADR-0020](../decisions/ADR-0020-prognostics-derivation-stage.md) — the derivation stage.
- [ADR-0013](../decisions/ADR-0013-physical-quantity-consistency.md) / [ADR-0021](../decisions/ADR-0021-edge-hq-topology-is-load-bearing.md) / [ADR-0025](../decisions/ADR-0025-build-pass-deployment-verification-discipline.md) / [ADR-0037](../decisions/ADR-0037-verification-evidence-is-a-deliverable.md) — units, footprint, verification discipline.
- [GENERALIZATION-DEBT.md](../decisions/GENERALIZATION-DEBT.md) GD-07 — the open debt any interim landing joins.
