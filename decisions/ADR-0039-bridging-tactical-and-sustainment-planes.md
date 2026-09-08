# ADR-0039: The bridging thesis — tactical and sustainment planes

## Status

Accepted — 2026-08-15. **Positioning. Nothing built.** States what
OpenDDIL is *for* in terms of the two system families it sits between.
Supersedes ADR-0011's positioning as the primary statement; that ADR
remains valid on its narrower question (adjacency to strategic
sustainment modelling tools) and is amended to point here.

## Context

Two families of system exist in this domain, built by different
communities, decades apart, for different questions.

**Tactical systems model the fight.** Entities, tracks, engagements,
posture. They are real-time, they are pushed, they tolerate loss, and
their identifiers are about *what is happening right now* — a track
number, an entity id, an emitter designation.

**Materiel systems model the stock.** Parts, serial numbers, stock
records, work orders, requisitions, configuration baselines. They are
transactional, queried rather than pushed, authoritative about *what is
owned and what state it is recorded in*, and their identifiers are about
custody — a stock number, a serial, a work-order reference.

**A track number and a stock record can describe the same rounds and
share no vocabulary.** Neither model is wrong. Each is well-suited to the
question its community asks. The gap is not a defect in either; it is
that **nobody owns the correlation**.

The observable consequence is mundane and widespread: the logistics
picture in an operations centre is frequently maintained by hand.
Somebody reads one screen, reads another, and reconciles them in a
spreadsheet or in their head. That reconciliation is where readiness
actually lives, and it is the least durable artifact in the room.

A second structural characteristic compounds it. **Materiel management
systems in this domain are increasingly cloud-resident**, which is
excellent for a garrison and poor for a forward site: reaching them
requires the connectivity that a forward site is defined by not reliably
having. Systems in that class commonly replicate by **row state** rather
than by operation, which resolves collisions by value precedence without
reference to what either side was trying to do. The practical effect is
that offline operation against them is fragile, and that genuine business
conflicts surface as row collisions requiring **manual reconciliation at
the database layer** — often by someone with no view of the intent behind
either write.

This is a characterization of a class, not of any product. It is stated
because it is the environment OpenDDIL deploys into, and because two of
this ADR's three consequences follow from it directly.

## Decision

**OpenDDIL is the correlation layer between the tactical plane and the
sustainment plane. It owns neither, speaks both, and preserves each
side's provenance.**

The value proposition is precise: **readiness lives in the intersection
of the two planes and is fully represented in neither.** A tactical
system knows an asset is deployed and firing. A materiel system knows the
asset's authorized configuration, its stock on record, and its
outstanding work orders. *"Can this unit sustain this operation"* is a
question about both, and today it is answered by a human holding two
screens.

Three commitments follow.

### 1. Correlate, do not transact

**OpenDDIL correlates and advises. Systems of record transact.**

This is the `work_order_ref` precedent (ADR-0011 as amended, ADR-0038 §3)
generalized from maintenance to supply: OpenDDIL carries a *reference* to
an authoritative record created elsewhere, and stamps its own derived
view alongside it. It does not create the work order, adjust the stock
balance, or close the requisition.

The reason is not modesty. A correlation layer that also transacts
becomes a **second system of record for the same objects**, which is the
condition that produces the reconciliation problem this ADR exists to
relieve.

### 2. Preserve both provenances, never merge them into one

A correlated value carries **where each side's contribution came from**,
not a fused number whose lineage has been averaged away. Two authorities
means two timestamps, two identifiers, and two claims — and the
correlation is a *third* artifact that cites both rather than replacing
either.

This is the provenance discipline (ADR-0034, ADR-0035, ADR-0020) applied
at the portfolio seam. A correlation that discards its inputs' lineage is
exactly as unexplainable as a derived number with no stamp, and for the
same reason.

### 3. The boundary against evaluation is principled, not scope-avoidance

ADR-0038 §2 fences operational course-of-action generation and analysis
permanently. This ADR supplies the *structural* argument that fence was
missing.

**Correlation and evaluation are different acts.** A neutral join
between two communities' models is adoptable by both precisely because it
asserts nothing either would dispute — it says *these records describe
the same physical thing* and shows its work. The moment that layer begins
scoring
options, it becomes **a third opinion** competing with the staff process
on one side and the materiel authority on the other, and it is
unadoptable by both. The neutrality is the product.

So the COA fence is not "we are too small for that." It is: *the thing
that makes a bridge useful is that it does not take sides, and
evaluation is taking sides.*

## Prior instances of this seam, and what is actually there

Two enterprise integrations were scoped early in this project and are
referenced in ADR-0014, ADR-0022 and the demo material. **They were the
first instances of the seam this ADR describes, scoped before the framing
existed to explain them** — which is precisely why they read as customer
plumbing and were deprioritized. Recording that rationale is half of what
this ADR is for.

**What exists was read rather than assumed** (2026-08-15):

- **One code site.** A demo Restate saga step that POSTs a hardcoded
  payload (`device_id`, `issue`, `action_taken`, `priority`) to a
  work-orders endpoint on a service hostname that appears in **no compose
  file and no chart**. The project's own test documentation records the
  endpoint as dead and never exercised by the demo flow.
- **Egress-only, one-shot, fire-and-forget.** A single POST inside a
  saga, retried by Restate on failure. No read path, no query, no
  reconciliation, no cadence.
- **Everything else is naming and intent** — a proto comment marking
  `work_order_ref` as an external reference, two UI panels whose titles
  were *removed* under ADR-0017 because they overclaimed a connection
  that does not exist, and an aggregation constraint (ADR-0022 §4)
  reserving that any future bridge must carry echelon context.

The honest summary: **the earlier scoping was an aspiration with a stub,
not an integration pattern.** That is a better starting position than a
half-built bidirectional coupling, because nothing has to be undone — but
it means no claim about how those systems actually behave can be made
from this repository, and none is made here.

## Consequences

**Pros**

- The project acquires a one-sentence answer to *what is this for* that
  is neither a feature list nor a competitive claim, and that explains
  the existing boundary decisions rather than restating them.
- ADR-0038 §2's fence gains a structural justification, which makes it
  durable under pressure from a customer who would like scoring.
- The two early integrations stop being unexplained plumbing and become
  the first instances of a named seam, which is what makes them
  schedulable.

**Cons**

- "Correlation layer" is a harder sell than a feature, because its value
  is only legible to someone who has felt the two-screens problem. This
  is a real adoption cost and is accepted deliberately: the alternative
  positioning (do more, own more) is what makes a bridge unadoptable.
- Committing to *never transact* forecloses a capability some deployments
  will ask for. The escape hatch is a deployment-side integration that
  transacts against its own system of record using OpenDDIL's advisory as
  input — which keeps the boundary intact and is ADR-0038 §3's shape.

**Rejected alternatives**

- *Position OpenDDIL as a materiel system with tactical inputs.*
  Rejected: it puts the project in competition with authoritative
  systems of record on their own ground, where it has neither the data
  nor the mandate, and it recreates the second-system-of-record problem.
- *Position it as a tactical system with logistics overlays.* Rejected
  for the mirror reason, and because the logistics questions are the ones
  currently unanswered.
- *Leave positioning in ADR-0011.* Rejected: that ADR answers a narrower
  question (adjacency to strategic modelling tools) and had a capability
  claim retracted in 2026-08-12. Stretching it to carry the primary
  thesis would repeat the mistake that produced the retraction.

## The bridge's argument, in one number — service life (added 2026-09-06)

The clearest case for this ADR turned up while diagnosing something else,
and it is a single missing number rather than an architectural claim.

**Engine wear on this deployment is computed from WALL-CLOCK TIME SINCE
OPENDDIL FIRST SAW THE ASSET.** ADR-0020 records why: DIS Entity State PDUs
carry no engine-on signal, so observed time is the closest available proxy.
The consequence, measured on the lab, is that all 14 assets report an
*identical* 647.3 hours in service.

That number is not merely imprecise. It is **structurally incapable of
varying between assets**, because every asset's life starts at zero the
moment the tactical plane notices it. So:

> **The engine wear axis cannot show a distribution at any coefficient.**
> Not with better tuning, not with a longer run. A real fleet has airframes
> at different points in their service life; this model has none, because
> the tactical plane does not know what happened before the exercise
> started.

**The thing that knows an airframe's actual hours is the materiel system.**
As-maintained state — installed configuration, accumulated service life,
overhaul history — is a **Contract B supply read** (see
`DESIGN-2026-09-06-interface-contracts.md` §2, read side). Until that read
is wired, prognostics is deriving a quantity whose true value already
exists in a system OpenDDIL is not yet talking to, and the derived number
can only ever be "time since we started watching".

*Why this is the better argument:* it is not "the planes should be
bridged because integration is good". It is that a specific number on a
specific screen is wrong in a specific, unfixable-from-this-side way, and
the fix is a read the bridge already specifies. **Prior service life is a
source fact, and the source is on the other side of the bridge.**

*A note on what NOT to do meanwhile:* seeding synthetic prior hours in the
sim would produce a convincing distribution and would be authored fiction
in a physical unit — the same error as picking wear coefficients to taste
(GD-14). If a demo needs varied service life before the bridge exists, it
must be declared as scenario data by whoever owns the scenario, exactly as
DIS enumerations are.

## What this ADR did not establish

Per ADR-0037 §6.

- **How the two named enterprise systems actually behave.** Their real
  interaction pattern, cadence, identifier scheme, and whether the
  earlier scoping was ever intended as egress-only or bidirectional are
  **unverified from this repository**. What is recorded above is what the
  code and documents contain, which is one dead POST. Anything further is
  a conversation with the people who operate them, and must precede
  planning rather than follow it.
- **Whether the row-state and cloud-residency characterization applies to
  the specific systems in scope.** It is stated as an industry class
  because that is the level at which it is verifiable here. Confirming it
  per-system is an integration task.
- **No identifier-correlation design.** Which identifiers actually join,
  and whether the join is deterministic or probabilistic, is unexamined.
  ADR-0041 records why that is an ontology problem rather than a
  matching-heuristic problem, and equally does not solve it.
- **No cost, sequencing or dependency analysis.** This is positioning.

## Related

- **ADR-0011** — strategic sustainment tool positioning; narrower
  question, amended to point here.
- **ADR-0038 §2 / §3** — the COA fence this ADR supplies the structural
  argument for, and the propose/dispose boundary §1 generalizes.
- **ADR-0040** — offline sustainment operation; what the sustainment side
  of this bridge must do when the link is down.
- **ADR-0041** — ontology convergence; why the correlation is an ontology
  problem, and the declared-model precondition for doing it declaratively.
- **ADR-0022 §4** — the standing constraint that any enterprise egress
  bridge carries echelon context.
- **ADR-0034 / ADR-0035 / ADR-0020** — the provenance disciplines that
  commitment 2 applies at the portfolio seam.

---

## Addendum 2026-09-08 — the end-to-end chain, stated once

```
detection
  -> fault code + candidate components
    -> TM fault-isolation procedure        (reasoning plane, ADR-0031)
      -> corrective procedure
        -> parts
          -> NSN
            -> requisition intent          (Contract B)
              -> MMIS
```

**The IETM is the middle of the bridge.** Everything left of it is this
system's own derivation; everything right of it is somebody else's system of
record. The bridge was described as tactical-to-sustainment; this names what
sits between the two halves and why neither half can reach the other without
it — a detection cannot become a requisition without a procedure that says
which part.

**The loop closes into supply.** ADR-0040's offline reconciliation is the
last link's failure mode: when the MMIS is unreachable the intent queues and
is rendered as unapplied, and everything upstream of it still worked.

**Second meeting point with the reasoning plane.** The returned procedure is
a natural workflow for the process plane — steps, tools, hazards, parts, in
order. Noted rather than designed: it is the shape of the next seam, not a
commitment to build it.
