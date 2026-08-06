# ADR-0031 — Converged edge node: OpenDDIL seams for a co-located reasoning plane (mini-iagent)

## Status

Accepted (2026-08-05). Scope is OpenDDIL's seams only — see §Scope
discipline.

## Context

An OpenDDIL edge already holds the thing a reasoning agent most needs
and most often lacks: **local, current, structured ground truth about a
specific set of equipment.** Telemetry, logistics status with
constraining factors, configuration state, and capability state are all
present at the edge, kept current by the pipeline, and — by ADR-0021 and
ADR-0022 — kept current *even when the link to higher tiers is severed*.

Separately, the **Invincible Agent** project (`../invincible-agent`) is
a polyglot agentic mesh: a Dagster control plane orchestrating a fleet
of FastAPI engines with BAML-typed grounding contracts. A reduced
deployment of it — **mini-iagent** — is small enough to run co-located
on an OpenDDIL edge node rather than centrally.

Putting those together gives a **converged edge node**: a data plane and
a reasoning plane on the same node, sharing one policy engine, all three
severance-tolerant. The reasoning plane answers questions about the
equipment at that site, grounded in that site's own rows, and keeps
answering them when the site is cut off — which is precisely when a
maintainer or logistician most needs answers and least has reachback.

The risk this ADR exists to manage is scope. "Agent on the edge" is an
invitation to build a product: a UI, a document corpus, retrieval
infrastructure, a multi-edge rollout. None of that belongs in OpenDDIL,
and starting it inside OpenDDIL would entangle two projects with
different release cadences and different reviewers.

### Scope discipline

**This ADR defines OpenDDIL's seams. It does not build the reasoning
agent.**

The reasoning plane is an external project with its own lifecycle. What
OpenDDIL owes it is a small number of stable, documented contracts.
What OpenDDIL must not do is grow a reasoning implementation inside
itself, or shape its data model around one consumer.

The deliverables here are mostly **documented contracts and one small
exporter** — deliberately, not code-heavy. If a phase below starts
producing agent behaviour, it has left scope.

## Decision

### The converged edge node rests on three shared elements

**(a) Data substrate.** The edge's local truth is the reasoning plane's
grounding source. Not a copy, not an export — the same rows the
maintainer view renders. Grounding on the same rows the operator sees is
what makes an answer checkable: an operator can click through to the row
that produced it.

**(b) Policy.** **One Topaz sidecar per edge serves both** OpenDDIL's
PEPs (ADR-0029) and the reasoning plane's per-source access decisions.
One policy manifest, one decision log, no second authorization truth.

This is the load-bearing element. A co-located agent with its own access
model would be an independent path to the same data with independently
maintained rules — which is how releasability enforcement gets bypassed
in practice, without anyone deciding to bypass it. ADR-0029's
single-PDP discipline extends across the plane boundary: the reasoning
plane is another PEP, not another decider.

**(c) Provenance.** Agent answers cite OpenDDIL rows **and** carry the
access decisions that gated their grounding — *decision-as-provenance*.
An answer is accompanied by what it was built from and by what the
policy engine permitted to be used.

This interoperates with OpenDDIL's existing provenance discipline
(ADR-0022/0023 origin stamping, ADR-0029 releasability labels). It also
gives the honest form of a hard question: if a user's entitlements
excluded rows, the answer says so rather than silently answering from a
subset.

All three function severed from higher tiers. That is the point of doing
this at the edge rather than centrally.

## Phasing

### Phase 1 — Architecture note (~½ day)

This ADR. The three shared elements above are the deliverable.

### Phase 2 — Read seam (~1 day)

Define and document the **stable read surface** a co-located agent
consumes.

- **Which relations:** `telemetry_latest_state`,
  `asset_logistics_status`, `asset_capability_state`, and the
  releasability-classified view from ADR-0029.
- **Which mechanism at the edge:** direct database read vs. a filtered
  subscription — **decide and document**, do not leave implicit.
- **Open question this phase must resolve, not assume:** what the edge
  tier's actual data stores are, versus HQ's. The current deployment
  concentrates the read-model database at HQ; whether an edge-local
  reasoning plane reads an edge-local store, or reads through a
  tier-appropriate mechanism, is a genuine unknown that this phase must
  settle with reference to the deployed topology rather than to the
  architecture diagram. Getting this wrong produces a "local" agent with
  a reachback dependency — i.e. one that fails exactly when it was
  supposed to help.
- **Precondition:** the releasability columns from ADR-0029 Phase 1 must
  be present, so the agent's Topaz checks have resource attributes to
  decide over. Without them the shared-policy element (b) is not
  expressible.

**Deliverable: a documented contract, not code.**

### Phase 3 — Subset packaging seam (~1 day)

Define how *"what ships to this edge"* is derived.

An edge's fleet composition — the `platform_variant`s actually present,
from the ORBAT / edge-assignment data OpenDDIL already holds
(ADR-0028) — keys which ontology, documentation, and knowledge subsets a
co-located agent needs. An edge with three radar tiers and a launcher
type does not need the whole enterprise corpus.

**Deliverable:** a small exporter or documented query producing the
edge's **equipment manifest** — `edge_id → platform_variants + asset
list` — as the subset-selection input.

This is OpenDDIL **exposing what it already knows**, not new modelling.
If this phase starts adding fields to support the agent, it has left
scope: the manifest is a projection of existing registry data.

### Phase 4 — Thin proof (~1–2 days)

**Gated on Phases 1–3 and ADR-0029 Phase 3** (Topaz deployed with
asserted entitlements).

One question, answered at one edge, grounded on local rows, gated by the
local Topaz. Worked example:

> *"Which assets at this site are degraded, and what factor is
> constraining each?"*

Answered from `asset_logistics_status` + its `ConstrainingFactor` list,
with the access decision recorded on the answer.

The question is chosen because OpenDDIL can already answer it exactly
and structurally — so the proof tests **the seams**, not the reasoning.
If the answer is wrong, the seam is wrong; there is no model-quality
ambiguity to hide in.

**Success criterion:** the three seams compose — local data grounds the
answer, the local policy engine gates it, and the answer carries both
its row citations and its access decisions.

**Explicitly not a product build.**

## Fenced — tracked, not built

Named so they are decisions rather than drift:

- Agent UI
- Document corpora
- Vector / retrieval infrastructure
- Multi-edge rollout

**The seams are the deliverable.** The reasoning plane matures in its
own project, against these contracts.

## Consequences

### Positive

- A reasoning plane can be added to an edge without OpenDDIL growing a
  reasoning implementation — the two projects stay independently
  releasable.
- One policy engine per edge means releasability enforcement cannot be
  bypassed by the reasoning path, by construction rather than by
  vigilance.
- Answers are checkable: they cite the same rows the operator can open.
- Severance-tolerant by inheritance — the reasoning plane is local
  because the data and policy it depends on are already local.
- The equipment manifest is independently useful (deployment scoping,
  documentation packaging), not solely an agent input.

### Negative

- Co-location adds compute and memory load to edge nodes whose footprint
  is already an architectural constraint (ADR-0021, ADR-0030 §engine
  policy). Whether a given edge can host mini-iagent is a per-deployment
  sizing question this ADR does not answer.
- A stable documented read surface is a commitment: changing those
  relations now has an external consumer, which is a constraint on
  future schema work.
- Two projects sharing a policy manifest requires coordinated change
  management; a policy edit for one plane affects the other.

### Neutral / acknowledged

- The read-mechanism question in Phase 2 is genuinely open. This ADR
  records it as a decision to be made against the deployed topology,
  not one made here.
- Phase 4 proves seam composition on a question OpenDDIL can already
  answer structurally. It says nothing about reasoning quality on
  questions it cannot — that evaluation belongs to the external project.
- "mini-iagent" is a reduced deployment of an external project. Its
  internals, engines, and orchestration are out of scope for OpenDDIL
  ADRs; only the contracts between the planes are in scope here.

## Related

- ADR-0021 — the edge is load-bearing and not a small copy of HQ (edge
  footprint constrains co-location).
- ADR-0022 / ADR-0023 — hierarchical aggregation and severance
  tolerance; the property the reasoning plane inherits.
- ADR-0028 — centralized asset registry; the source of the equipment
  manifest in Phase 3.
- ADR-0029 — ABAC enforcement; supplies the shared PDP and the resource
  attributes the reasoning plane's checks decide over.
- `../invincible-agent` — the external project mini-iagent is a reduced
  deployment of.
