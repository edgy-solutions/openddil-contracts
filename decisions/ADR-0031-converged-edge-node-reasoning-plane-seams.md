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

**Open question — two policy corpora must be reconciled.** Both projects
independently selected Topaz, which is what makes a shared PDP realistic
rather than aspirational. But both also already carry their own
git-managed policy content: ADR-0029 specifies an OpenDDIL
`users.yaml` of asserted nation entitlements, while the Invincible Agent
project already has a policy directory (`users.yaml`, `groups.yaml`,
`domains.yaml`, `personas.yaml`, `trust_table.yaml`, plus asset,
capability, task and ontology-compartment grants) with its own sync
tooling.

"One policy manifest" is therefore a **target state, not a current
one**. Reconciling them is a required deliverable of Phase 2, and it is
a design question rather than a merge: whether OpenDDIL's releasability
attributes become an additional resource-attribute source consumed by
the existing grant model, or the two remain distinct policy *modules*
sharing one authorizer instance and one decision log. What is not
acceptable is shipping both corpora as independent deciders over the
same rows and calling that a shared PDP.

**The narrower sync-tooling tension is resolved.** ADR-0029 takes an
explicit "asserted, never inferred — no directory sync" stance, and the
agent-side policy directory ships sync tooling under `policy/sync/`,
which reads as a contradiction. It is not: that stance *originated* on
the agent side, where the doctrine is that the hand-authored git file
**is** the assertion — a directory may seed a *draft*, but the human's
PR approval is what makes it an entitlement. The sync tooling is
therefore the deployment pipe that transports asserted content into the
running authorizer, not a derivation path.

Both projects carry this sentence so the boundary is stated rather than
assumed:

> **Sync tooling transports asserted, PR-reviewed policy content into
> the authorizer; it never derives entitlements from a directory or any
> other source.**

With that stated in both repositories, the accreditation-facing property
of ADR-0029 — every entitlement has a named author, a reviewer, and a
date — survives contact with the agent-side tooling intact.

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

Three deliverables, in dependency order. §2.1 is **the first job** —
everything else in the read seam is contingent on its answer.

#### 2.1 — The edge read substrate (FIRST JOB)

**Investigated 2026-08-06 against the deployed chart. Answer: there is
no edge-local queryable relational store today.**

The finding, from `openddil-helm/openddil-demo/templates/edge.yaml` and
`values.yaml`:

- `postgresHq` is the **only** relational store in the chart. No
  per-edge Postgres exists.
- There are four projectors — `projector-edge-01/02/03` plus
  `projector-hq`. The per-edge projectors are edge-local **consumers**
  but HQ **writers**: each subscribes to `KAFKA_BROKERS = <its own edge
  broker>` and writes to `POSTGRES_DSN = postgres://…@<release>-postgres-hq`.

So per-edge projection genuinely exists — but it projects *into HQ*.
A reasoning plane "reading local rows" via SQL today would in fact be
reading HQ Postgres across the tier boundary: the reachback dependency
this ADR named, arriving as the default outcome rather than as a tail
risk. It would fail precisely during severance, which is the condition
that motivates edge co-location at all.

**What is genuinely edge-local:** the truth exists at the edge, in
Kafka form. Every broker — each edge and HQ — carries its own copy of
every topic (the topic-init pattern), including the compacted
`telemetry-latest-state`. The edge holds current per-asset state
locally; it simply has no relational surface over it.

That reframes the question from *"is there a substrate?"* (yes) to
*"what is the minimal edge-local read surface over it?"* Three
candidate shapes, to be decided in this phase:

| Option | Shape | Trade |
|---|---|---|
| **(a) Edge-local Postgres** | Add a per-edge store; edge projector writes local (dual-write, or a second instance) | Heaviest footprint. **But** the read-seam contract becomes tier-independent — identical SQL surface at edge and HQ — and the edge projector already consumes the local broker, so only its write target changes. |
| **(b) Read the local broker directly** | Reasoning plane consumes the edge's compacted topics | No new store, smallest footprint. No SQL; the agent must materialize and maintain its own view, and the ADR-0029 releasability columns exist only in the projected relational form. |
| **(c) Minimal edge-local materialization** | Small purpose-built store fed from local compacted topics | Middle ground; risks becoming a second projector with a different schema — i.e. a second truth. |

Option (a) is the current lean precisely because it keeps **one read
contract across tiers**, which is what makes §2.2 writable once rather
than per-tier. It is a lean, not a decision — this phase decides, with
edge footprint (ADR-0021, ADR-0030 §engine policy) as the counterweight.

#### 2.2 — The read surface contract

Define and document the **stable read surface** a co-located agent
consumes.

- **Which relations:** `telemetry_latest_state`,
  `asset_logistics_status`, `asset_capability_state`, and the
  releasability-classified view from ADR-0029.
- **Which mechanism:** follows directly from §2.1.
- **Precondition:** the releasability columns from ADR-0029 Phase 1 must
  be present, so the agent's Topaz checks have resource attributes to
  decide over. Without them the shared-policy element (b) is not
  expressible.

#### 2.3 — Policy reconciliation: modules, not merge

Resolving the open question raised in element (b). The shape:

**Distinct policy modules, one authorizer instance, one decision log.
Do not merge the grant models.**

The two corpora answer *different questions about the same request*,
which is why they compose rather than collide:

- The **capability module** (agent-side) answers: which persona×domain
  cells is this subject entitled to, which verbs/engines/tools may run,
  which ontology compartments are reachable.
- The **releasability module** (ADR-0029) answers: may this subject see
  this row, given nations/clearance against the row's labels.

When the reasoning plane grounds on an OpenDDIL row, the request passes
both: the capability module governs *whether this kind of retrieval may
run at all*; the releasability module governs *which rows may ground
it*. **Only the releasability module ever decides row access.** That
satisfies the no-second-decider-over-the-same-rows rule by
decomposition rather than by merge — a stronger result than merging,
because neither corpus has to absorb the other's model.

**The real reconciliation deliverable is therefore the subject
namespace, not the policy content.** Composition only works if both
modules recognise the same subject. If the two `users.yaml` files name
the same human differently, decisions cannot compose and the shared
decision log cannot correlate — producing two-truths drift at the
*identity* layer, which is worse than at the policy layer because it is
invisible: both modules answer confidently, about different people.

Concretely:

> **One subject identity namespace. One subject record per human,
> carrying both attribute families — the persona×domain matrix
> (agent-side) and nations + clearance (ADR-0029). Merge the subjects,
> federate the policies, share the log.**

If the agent-side grant model resists this shape somewhere concrete,
that resistance is itself a finding: record it here rather than
bending the subject model around it silently.

**Deliverable for all three: a documented contract, not code.**

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
- Both projects arrive with an existing, non-trivial policy corpus.
  Converging them is real design work with a real chance of friction,
  and until Phase 2 settles it, the "one authorization truth" property
  is asserted rather than achieved.

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
