# ADR-0034 — Tier analytics are deployment configuration, not framework code

## Status

Accepted (2026-08-07) as a framework invariant and as constraints
binding current work. The **engine build is fenced** — see §Fenced. This
ADR is the invariant's citable home, written *before* the violation
deepens rather than after.

Sequel to ADR-0033: that ADR made the **topology** deployment
configuration. This one makes the **analytics that run on it**
deployment configuration.

## Context

### The requirement

A deployment must be able to decide, per tier, what that tier collects
from below, what it computes and emits upward, and what algorithmic
analysis it runs — without editing framework code. One deployment wants
a different rollup set at its province tier; another wants a different
detector suite at its edges. If either requires a code change, the
framework is not generic, in exactly the way a bounded tier count was
not generic.

### Current state: the invariant is violated at every layer

Stated plainly, because ADR-0033's lesson was that unrecorded intent
gets re-derived wrongly:

| Plane | Today |
|---|---|
| **Collection** | Hardcoded everywhere **except** the projector, whose topic-set axis exists once and was turned for the first time in Arc 1. The regional aggregator hardcodes its subscriptions. |
| **Aggregation** | Entirely hardcoded — the three `region_*` rollups are Python in `aggregator_app.py::_emit_rollups`. |
| **Detection** | Entirely hardcoded — the fusion evaluators (`_eval_inventory`, `_eval_operational_state`, `_eval_cm_state`, staleness, wear/MTBF) are rule functions in `fusion/rules.py`. |

### Investigated finding: detection has a reachback problem too

The hypothesis going in was that per-edge fusion subscriptions imply
edge-tier detection already exists in primitive form. **That is not what
is deployed.**

`logistics-fusion-service` is rendered **once, in `hub.yaml`** — it
appears zero times in `edge.yaml` and `regional.yaml`. It is a single
HQ-tier Deployment that **subscribes downward into all three edge
brokers** (plus the HQ broker for CM state), with edge-suffixed consumer
groups.

So detection today is **centralized at HQ with downward reach**, not
distributed to the tiers whose data it analyses. The consequence is the
same shape as ADR-0032's reachback finding, one plane over:

> **Under severance, a severed edge's assets get no logistics severity
> computed at all** — the evaluator that would compute it is at HQ, and
> the telemetry it needs stops arriving. The tier that still has the
> data, and the operator who most needs the answer, cannot produce it.

That makes per-tier configurable detection not merely a genericity
requirement but a **DDIL correctness improvement**. It is the same
argument ADR-0032 made for presentation, and it inherits the same rule:
severance-tolerant detection at tier N requires tier N's own inputs.

## Decision

### The invariant

> **Each tier configures three analytics planes: what it COLLECTS from
> below, what it AGGREGATES and emits upward, and what it DETECTS.
> All three are deployment configuration. Detection outputs are events —
> first-class data, collectable and aggregatable by the tier above.**

Detection producing events *that flow like any other data* is what makes
it a plane rather than a feature: a tier's detections become a parent
tier's inputs, recursively, exactly as ADR-0033 requires of everything
else.

### The config/code line

Restated in ADR-0030's idiom, because this project has now drawn the
same line three times (Bloblang maps but does not parse grammars; edge
assignment is a registry of strategies bound by config):

> **Config composes a small verified primitive algebra and binds
> registered units. Algorithms live in code, behind a registry, named
> and versioned — referenced from config, never expressed in it.**

The moment configuration tries to express an algorithm, the project has
built a bad programming language in YAML. That is the failure the
boundary exists to prevent.

**Primitive algebra** (config-expressible): `count`, `sum`, `min`,
`max`, `worst-of`, `distinct`, `group-by`, `filter`, `threshold`,
`mean-via-(mean,count)`, plus **window specifications** (see below).
These are exactly the operations
[AUDIT-2026-08-07](AUDIT-2026-08-07-aggregation-composability.md) worked
through, so their composition behaviour is already characterised.

**Registered units** (code): `@register_aggregation`,
`@register_detector` — following the existing `@register_strategy`
pattern from edge assignment. Windowed aggregations, detectors, and ML
models are all registered units.

### Registered units are parameterized families, not singletons

A registered unit exposes a **typed parameter surface** at registration
— window length/slide/type, thresholds, sensitivity, feature set,
hyperparameters. One registered `windowed_anomaly_detector` becomes many
instances via config.

**Instance = registration + binding config.** The registry entry is a
*family*; config binds instances of it.

This is not a convenience. Without parameterization, every threshold
tweak becomes a new registry entry, and the registry bloats into exactly
the hardcoding it replaced — one entry at a time, invisibly, because
each individual addition looks reasonable.

### Composition typing — the audit becomes a type system

Configurable aggregation changes the status of the composability audit.
A deployer who configures top-N at tier 2 and collects it at tier 3 has
**recreated the truncation bug through configuration** — silently, in
someone else's deployment, where no audit will ever run.

Therefore every algebra operation and every registered aggregation
carries a composition classification:

- **Propagating** — associative/algebraic, safe to emit upward:
  `count`, `sum`, `min`, `max`, `worst-of`, `distinct`,
  `mean-via-(mean,count)`.
- **Terminal** — lossy, valid only at the point of presentation:
  `top-N`, percentile snapshots.

> **The config schema rejects a terminal operation on any stream marked
> for upward emission.**

`top-N` becomes what it always was: a presentation-layer operation. The
truncation bug becomes **unwritable** rather than merely audited-for —
the difference between "we checked" and "the system won't let you."

The audit's classification table is the seed of this type table.

### Windows are first-class, and window compatibility is typed

Window specifications (tumbling / hopping / session; length, slide,
grace) are config-plane vocabulary.

They interact with composition typing non-trivially: **windowed
aggregates compose upward only when window boundaries are compatible
across tiers.** A parent can merge two aligned 5-minute tumbling
windows; it cannot cleanly merge a child's 5-minute against another's
7-minute, or misaligned slides.

This is the truncation lesson in temporal form — the lossy operation is
window misalignment, and it must be **rejected at config-validation
time**, not discovered later as quietly-wrong trends. Window
compatibility on upward-emitted windowed streams is therefore a
coherence-validator check.

### Serialization is first-class — ML units are three artifacts

A registered unit must be serializable. For ML this means **artifacts,
not just parameters**:

> **ML instance = registered inference wrapper (code) + versioned
> serialized artifact (ONNX-class weights) + binding config.**

This converges the analytics plane with the distribution machinery
already being built. Model artifacts travel to tiers **the same way**
policy bundles travel to Topaz sidecars (ADR-0029 §6) and registry data
travels down `registry-sync` (ADR-0032 §c). Arc 1 Phase 4's downstream
flow is therefore not a registry-specific pipe — it is the **general
artifact-distribution seam**, and models are its third passenger.

The DDIL property carries too: artifact distributed ahead of time,
inference local, **a severed tier keeps detecting**.

### Parallelism is a registration contract

Instances must scale horizontally, which in this stack means the
Faust/Kafka idiom: partition-parallel by key, windowed state in the
state store, no cross-partition shared state within an instance.

A unit **declares its keying/partitioning requirements at
registration**, and the engine **refuses bindings that cannot satisfy
them**. Same move as composition typing: make the invalid configuration
unwritable rather than audited-for.

### Provenance — analytics must explain themselves

Every configured aggregate and every emitted detection event stamps its
producer. Detection-as-provenance, sibling of the decision-as-provenance
pattern (ADR-0031 §c):

| Output | Stamp |
|---|---|
| Aggregate | `{operation, version, config_hash, tier}` |
| Detection event | `{detector, version, config_hash, tier}` |
| **ML detection event** | `{detector, version, config_hash, tier, model_artifact_hash}` |

`model_artifact_hash` is mandatory and non-negotiable for ML outputs:
*"which weights produced this alert"* is the first question any
post-incident review asks, and it is unanswerable retroactively if not
stamped at emission.

Without these stamps, a derived number at the root tier is
unexplainable — which config, at which tier, produced this?

### Wire shapes — two generic envelopes

Per-hardcoded-rollup proto messages would reintroduce the hardcoding at
the schema layer: every new configured aggregation would become a
contracts change.

- **Generic aggregate envelope** — typed measures + grouping keys +
  provenance.
- **Typed detection-event envelope** — event type, subject
  asset/stream, severity or score, window/time basis, full provenance
  stamp.

Both are needed. Events are first-class data, so they need first-class
wire shape; ad-hoc per-detector messages would recreate the
contracts-change-per-detector problem exactly where the aggregate
envelope solves it.

Whether the existing `region_*` messages become instances of the
aggregate envelope or run legacy-parallel during migration is an
assessment for the implementing arc.

### Hierarchy coherence validation

Deployment analytics config is validated **as a whole** — a lint for the
analytics topology, sibling to `helm lint`:

- every collected stream has a child emitter;
- every upward-emitted aggregate is composition-typed **propagating**;
- windowed upward-emitted streams have compatible windows;
- schemas agree across the parent/child boundary.

Named as a deliverable of the implementing arc, not of this ADR.

### ML composability: scores are terminal, events are propagating

Recorded explicitly rather than left to be discovered, because the
plausible-but-wrong version is silent.

A count composes. **A model score generally does not** — tier N cannot
merge two children's anomaly scores into a parent anomaly score by any
algebra. Averaging them produces a number that looks meaningful and
isn't.

The type system already has the vocabulary:

- **ML scores are terminal.**
- **ML *events* are propagating** — "anomaly detected on asset X" is an
  event, and events aggregate upward by counting/grouping like any event
  stream.

Stating this prevents someone configuring score-averaging across tiers
and calling it fusion — plausible-looking, meaningless, and silent: the
exact failure family this entire plane is being typed against.

## Constraints binding current work

Until the implementing arc runs, work must not deepen the hardcoding:

1. **No new hardcoded aggregations or detectors.** New analysis extends
   the future registry or is explicitly marked interim.
2. **Analytics bindings touched by in-flight work are interim.** Arc 1
   Phase 3 helm templates and Arc 3 ingress sidecars carry this note —
   what they wire today is expected to be re-expressed as registry
   entries + config.
3. **No new per-rollup proto messages** without assessing them against
   the generic aggregate envelope.
4. **Do not average scores across tiers.** Even manually, even once.

## Migration posture

The three `region_*` aggregations and the fusion evaluators become the
**first registry entries plus config** when the arc runs —
behaviour-preserving re-expression, not redesign. That they can be
expressed in the primitive algebra plus a small registry is itself
evidence the algebra is cut correctly; if one of them cannot be, that is
a finding about the algebra.

The detection plane's migration additionally has the option — not the
obligation — of moving evaluators from HQ-centralized to per-tier, which
is where the reachback finding above gets resolved.

## Fenced — explicitly not built by this ADR

- The configurable-analytics engine itself.
- Any `faust-regional` rework.
- Any fusion evaluator migration.
- The coherence validator.
- **Model training and artifact production — entirely.** This ADR
  governs *distribution, binding, execution, and provenance of
  already-produced artifacts*. MLOps upstream of the artifact is
  deliberately somebody else's pipeline.

The engine is its own arc, sequenced after Arc 1 and likely interleaved
with Arcs 2/3 by bandwidth.

## Consequences

### Positive

- A deployment composes its analytics per tier from a catalogue of
  parameterized, versioned units — the difference between "plugins
  exist" and a product surface a sustainment organisation can actually
  specify against.
- The truncation bug and the window-misalignment bug become unwritable
  rather than audited-for.
- Every derived number and every alert becomes explainable, including
  which model weights produced it.
- Detection can move to the tier that owns the data, resolving the
  reachback finding above.
- The downstream artifact seam gets a third passenger, confirming it as
  general infrastructure rather than registry-specific plumbing.

### Negative

- Substantial engine work, fenced but real: a generic aggregation engine
  is materially harder than three hardcoded rollups.
- A config language is a surface to design, document, version, and
  support — and a bad one is worse than the hardcoding.
- Artifact distribution adds weight to edge tiers already footprint-
  constrained (ADR-0021), and ML inference adds more.
- Two new wire envelopes to design and migrate onto.

### Neutral / acknowledged

- Like ADR-0033, this describes an intent the implementation does not
  yet meet. The constraints exist so the gap does not widen.
- The primitive algebra is small by design and will feel insufficient at
  some point. The correct response is a registered unit, not a bigger
  algebra — algebra growth is how config becomes a programming language.
- The framework keeps arriving at the same three-part shape at every
  layer: **a registry of verified units, config that binds them,
  provenance that explains them.** Ingestion has it (decoders +
  mappings), authorization has it (policy modules + assertions +
  decision log), analytics now has it. That recurrence is worth noticing
  as the framework's signature rather than treating each instance as
  novel.

## Related

- ADR-0033 — recursive tier hierarchy; this is its analytics sequel, and
  its do-not-harden constraint pattern is reused here.
- ADR-0024 / [AUDIT-2026-08-07](AUDIT-2026-08-07-aggregation-composability.md)
  — the aggregations being made configurable, and the classification
  that becomes this ADR's type system.
- ADR-0030 — the config/code boundary idiom this restates.
- ADR-0032 — presentation-plane reachback; the detection-plane reachback
  found here is the same shape one plane over. Its Phase 4 downstream
  flow is the artifact-distribution seam models will use.
- ADR-0029 — policy bundles as the first passenger on that seam;
  decision-as-provenance, whose sibling is detection-as-provenance.
- ADR-0031 — provenance carrying the decisions that gated an answer.
- `PRINCIPLES.md` — §Framework vs. instantiation (the invariant this
  applies), §Claims vs. sources (why provenance stamps are mandatory).
