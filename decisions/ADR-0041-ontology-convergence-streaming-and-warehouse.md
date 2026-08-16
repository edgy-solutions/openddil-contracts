# ADR-0041: Ontology convergence across streaming and warehouse ecosystems

## Status

Accepted — 2026-08-15. **Design position. Nothing built.** Records why
ADR-0039's correlation is an ontology problem rather than a matching
problem, the convergence shape that makes it declarative, and two
asymmetries that are currently unsolved.

## Context

ADR-0039 commits OpenDDIL to correlating the tactical and sustainment
planes. It deliberately does not say *how*, because the honest answer is
that **the correlation is not a matching problem and cannot be solved by
better matching.**

Two authoritative sources describe the same physical things using
identifier schemes designed independently for different questions. A
heuristic join — fuzzy names, position proximity, timing — would produce
a correlation that is *probably* right, unexplainable when wrong, and
impossible to defend to either community. Both sides would be correct to
reject it.

What makes a join defensible is a **declared model both sides map onto**.
That is an ontology problem, and it is one this project has already met
three times at smaller scale: GD-10 (the capability payload with no
declared shape), GD-11 (asset class inferred from publishing behaviour),
GD-12 (absence conventions known only to consumers). Each is the same
disease — **absent a declaration, meaning is set de facto by whoever
integrated first.** Correlation across two ecosystems is that disease at
portfolio scale.

## Decision

### 1. The convergence shape

Four layers, each doing one thing:

1. **A metadata catalog names the lowest-layer shapes** — the physical
   tables, topics and message types that actually exist, with their
   fields and types, published and versioned.
2. **Standard maintenance and materiel ontologies map onto those
   shapes** — the domain vocabulary is adopted rather than invented,
   because the correlation's credibility comes from both communities
   recognising the terms.
3. **Each ecosystem translates with the mechanism native to its medium** —
   stream mapping for wire formats (the ADR-0030 Bloblang path),
   extraction and warehouse-transform tooling for record systems.
4. **The correlation is expressed against the declared model**, not
   against either source's native shape.

**The load-bearing property is one declared model with many
transport-appropriate mappings — not one transformation language forced
across every medium.** A stream mapping language applied to a warehouse
is as wrong as SQL applied to a wire format. Forcing uniformity at the
transformation layer is the mistake that makes people abandon the
canonical model; forcing it at the *model* layer is the whole point.

This is ADR-0030's structure-versus-semantics split, restated one level
up: there, binary grammars were decoded by format-appropriate decoders
and semantics were mapped uniformly onto Silver. Here, ecosystems are
translated by medium-appropriate tooling and semantics land uniformly on
a declared model. **That the same seam works at two scales is evidence it
is cut at the right joint.**

### 2. OpenDDIL's Silver model becomes a published shape in that catalog

Alongside the record systems' shapes, versioned, with the same status as
any other participant.

**This is the precondition for correlation being declarative rather than
bespoke.** Today Silver is authoritative inside this project and
invisible outside it, so any correlation against it would be written by
reading source — the GD-10 pattern exactly, one layer up. Publishing it
is what lets a mapping *cite* rather than *reverse-engineer*.

The sibling projects' roles, stated generically because the technical
relationship is what matters: **a data-engineering framework that
publishes both streaming and database shapes into the catalog**, and **an
ontology-overlay project that builds the cross-ecosystem mappings.**
Neither the organisational relationship nor any product identity is
asserted here.

### 3. Two asymmetries, both unsolved, both design constraints

These are the reasons correlation is not merely plumbing. Neither is
solved by this ADR and neither may be papered over.

**(a) Cadence — the two sides age differently.**

| | Streaming state | Record-system state |
|---|---|---|
| Shape | continuous, latest-wins | transactional, point-in-time |
| Locality | tier-local, severance-tolerant | reachable only when connected |
| Freshness | seconds | hours, or as-of-last-sync |

**Every correlated value therefore carries two timestamps and two
authorities.** A naive join — treat both as current, emit one row —
produces a value whose freshness is silently that of its stalest input
while presenting as current. That is ADR-0035 class 3 at the join layer,
and it is the failure this constraint exists to prevent.

**Join semantics for sources that age differently is new work.** Not
attempted here. The requirement recorded is negative and firm: *a
correlation must not present a fused freshness.*

**(b) Direction — streams push, record systems are queried.**

The correlation layer must decide **when to ask**, cache the answer, and
**be honest about the cache's age at every tier, including severed
ones.**

The shape that solves this already exists: `registry-sync` (ADR-0032 §c)
is a compacted, HQ→edge channel carrying reference data that enriches but
never gates local operation. Cached record-system state is the same
pattern with a different payload — which is ADR-0040 §1's observation
arriving from the other direction, and the second reason to think that
seam is correctly placed.

What remains open is the **when**: polling cadence, invalidation, and
what a tier does when its cache is older than the question being asked.

## Portability requirement — the honesty rules travel with the framework

**Cross-cutting, and stated here because ADR-0041 is where the
configuration surface multiplies.**

A configurable mapping ecosystem — many shapes, many mappings, many
authors, several media — **multiplies the surfaces where cheap inference
fills a vacuum.** Every one of this project's ontology findings arose in
a *single* codebase with *one* team. The same vacuum across ecosystems,
with mappings authored by people who will never read this repository,
produces the same failures at a rate proportional to the surface.

So these must travel **with the framework**, not remain in one project's
`PRINCIPLES.md`:

- **Declared, not inferred.** A model states its shape; a consumer never
  derives it from what a producer happens to emit. *(GD-10, GD-11.)*
- **Absence must be expressible.** Every canonical field states how it
  says *"no data"*, distinguishably from a zero, and states it next to
  the type rather than inside its readers. *(GD-12.)*
- **Fallbacks refuse rather than answer.** A mapping's default branch
  answers only where it can *name* the class it answers for; an
  unrecognised input yields `UNKNOWN`, never a plausible value.
  *(AUDIT-2026-08-11.)*
- **Provenance on every derived value.** A correlated value cites both
  contributing sources, their timestamps and their authorities.
  *(ADR-0039 §2.)*

These are not stylistic preferences carried along for consistency. Each
one was earned by a specific failure in which the absence of the rule
produced a plausible wrong answer that nothing detected.

## Consequences

**Pros**

- Correlation becomes *citable*: a mapping references a published,
  versioned shape rather than someone's reading of a source system.
- Publishing Silver into a shared catalog is useful independently of
  whether the correlation is ever built — it is the documentation
  external integrators need regardless.
- The medium-appropriate-mapping rule prevents the most common failure of
  canonical-model programmes: a single transformation language imposed
  everywhere, which practitioners route around, which decanonicalises the
  model.

**Cons**

- A shared catalog is a coordination dependency across projects, and it
  is the kind that stalls when one participant's priorities move.
  Publishing Silver's shape is the part OpenDDIL controls and should not
  be gated on the rest.
- Two timestamps and two authorities on every correlated value is real
  payload and real UI surface. The alternative is a fused value that
  lies, so the cost is accepted — but it is not free, and §3(a) is
  unsolved, so the cost is currently unbounded.

**Rejected alternatives**

- *Heuristic correlation now, ontology later.* Rejected: a probabilistic
  join is unexplainable when wrong, and both communities are right to
  reject a correlation that cannot show its work. It would also become
  the de facto model — GD-10's disease, self-inflicted.
- *One transformation language across all media.* Rejected in §1.
- *Extend Silver to absorb the record-system model.* Rejected: it makes
  OpenDDIL a second system of record for materiel data (ADR-0039 §1) and
  guarantees drift against an authority that will not consult it.

## What this ADR did not establish

Per ADR-0037 §6.

- **Which standard ontologies.** *"Standard maintenance and materiel
  ontologies"* is a class, not a selection. Choosing them requires domain
  authority this repository does not have, and choosing wrong is
  expensive — the model is the most permanent layer.
- **Which identifiers actually correlate.** The central practical
  question is untouched. Whether a defensible deterministic join exists
  at all, for any identifier pair, is unknown here.
- **The catalog's technology, governance and versioning.** Named as a
  role, not a product or a design.
- **Nothing about the sibling projects' current state** was read or
  verified. Their roles are described as capability classes; whether
  either publishes anything today is not established.
- **§3(a) and §3(b) are stated, not solved.** Join semantics across
  differing cadences, and the polling/invalidation policy, are both open.
- **The portability requirement has no mechanism.** *How* the honesty
  rules travel — documentation, lint, schema constraints, review — is
  unaddressed, and a rule with no mechanism is a hope.

## Related

- **ADR-0039** — the bridging thesis; this ADR explains why its
  correlation is an ontology problem.
- **ADR-0040 §1** — cached materiel state on the distribution seam; §3(b)
  is the same observation from the ontology side.
- **ADR-0030** — structure-versus-semantics; §1 is that split one level
  up.
- **ADR-0032 §c** — `registry-sync`, the shape §3(b) points at.
- **ADR-0013 / ADR-0026** — canonical-Silver-plus-per-source-mapping, the
  pattern §1 generalizes across ecosystems.
- **GD-10 / GD-11 / GD-12** — the three declared-versus-inferred findings
  the portability requirement generalizes; this is the sixth instance of
  that family and the first at portfolio scale.
- **AUDIT-2026-08-11** — the fallback-refusal rule.
