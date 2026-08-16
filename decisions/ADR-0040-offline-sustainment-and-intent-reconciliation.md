# ADR-0040: Offline sustainment operation and intent-based reconciliation

## Status

Accepted — 2026-08-15. **Design position. Nothing built.** The capability
is anticipated in ADR-0038's sense; what is accepted here is the shape it
must take if it is built, and one decision — *replicate intent, not
state* — that is load-bearing enough to record before anything exists to
contradict it.

## Context

ADR-0039 places OpenDDIL between the tactical and sustainment planes. The
sustainment side of that bridge has a property the tactical side does
not: **its authoritative systems are frequently unreachable from the
sites that most need them.**

The class characteristic is stated in ADR-0039 and matters here
operationally. Materiel management in this domain is increasingly
cloud-resident; a forward site is defined by intermittent connectivity;
and systems in that class commonly replicate by **row state**, resolving
collisions by value precedence rather than by what either writer was
trying to accomplish. Offline operation against such a system is
therefore fragile in a specific way: **the disconnection is survivable
and the reconnection is not.**

What a maintainer at a severed site needs is unremarkable — see what
parts are on hand, record what was done, requisition what is missing,
adjust what was consumed. What makes it hard is that every one of those
is a **write against an authority that cannot be reached.**

## Decision

### 1. The read side is already solved — cached materiel state is the sixth passenger

Cached materiel state rides the existing HQ→tier distribution seam. It
joins a list that is now long enough to be a pattern rather than a
coincidence: policy bundles (ADR-0029), `registry-sync` reference data
(ADR-0032 §c), ML artifacts (ADR-0034), workflow definitions (ADR-0034
§process plane), and CM baselines.

The rules it inherits are the seam's existing ones and need no new
thought: **stale-but-present beats absent**, the cache **never gates
local operation**, and its age is **rendered honestly at every tier**
including severed ones (ADR-0035 class 3).

*That Arc 1 Phase 4's distribution seam keeps acquiring passengers it was
not designed for is evidence the seam was cut in the right place* — the
same observation ADR-0034 made when models became its third passenger.

### 2. The write side is new, and is the first anticipated capability that does not compose existing planes

Worth stating plainly because ADR-0038 §Consequences claims the opposite
about its three entries: *"every anticipated capability composes existing
planes."*

This one does not. Substrate, aggregation, detection, presentation and
process planes all assume the local tier is either producing observations
or consuming distributed reference data. **A locally-originated write
destined for a remote authority is neither.** It needs durable local
custody, an outbound queue with reconciliation semantics, and a lifecycle
that survives restarts and severance of unknown duration.

Recording this as an exception rather than eliding it: the claim in
ADR-0038 was true of its three entries and is not a general law.

### 3. Provisional state is a first-class claim, not a pending flag

A locally-raised action is **intent the system of record has never seen
and may reject.** It renders in its own basis class per ADR-0035 —
`asserted-locally-unconfirmed`, which is neither *measured* nor
*derived* — and it **must never present as an accepted transaction.**

The distinction is the difference between *"a requisition exists"* and
*"we asked for a requisition and do not yet know."* Rendering the second
as the first is the decision-assertion hazard (ADR-0038 §2) arriving via
optimism rather than via scoring, and it is the failure an operator would
discover at the worst moment — when the parts do not arrive.

Three renderings, not two, and the third is the one usually missed:
**raised-unconfirmed**, **accepted**, and **rejected-with-reason**. A
rejected intent that silently disappears is worse than one that was never
raised, because the maintainer believes it is in flight.

### 4. Replicate intent, not state — the load-bearing decision

**The unit of replication is the operation the maintainer performed, not
the row that resulted.**

*Why row-state replication fails here specifically.* A row carries the
value and discards the reason. When two sites' rows disagree, the
conflict is resolved by precedence — later wins, or a designated side
wins — and **the meaning behind both writes is gone by the time anyone
looks.** Every genuine business disagreement therefore arrives as a
mechanical collision that a human must reconstruct intent from, at the
database layer, hours after the fact, usually without the context to do
it correctly.

*Why intent replay dissolves most of it.* An event-sourced intent
replayed against authoritative state makes the majority of apparent
conflicts **evaporate rather than resolve**: two sites each consuming
three rounds from a stock of ten are **commutative, not conflicting** —
the answer is four, and no human needs to be involved. Row replication
sees two writes claiming different balances and escalates. Intent replay
sees two decrements and applies both.

*And it improves the remainder.* What survives replay is a **named
business exception with intent attached** — *insufficient stock*,
*competing allocation against a reserved item*, *requisition for a part
superseded while offline*. Those are routable to a supply role who can
decide, rather than to whoever has database access. **The conflict rate
drops and the residue becomes addressable by the right person.**

### 5. Actions are typed by composability

Not every intent replays cleanly, and the ones that do not are knowable
in advance rather than discovered at reconnection:

| Class | Behaviour | Example shape |
|---|---|---|
| **Freely-mergeable** | Commutative; replay in any order | a consumption decrement |
| **Order-dependent** | Associative but sequence-sensitive | a state transition with prerequisites |
| **Exclusive** | At most one may win; the rest become exceptions | claiming a uniquely-serialized item |

**This is deliberately the propagating-versus-terminal pattern from
ADR-0034's analytics typing, applied to writes.** There it prevented a
lossy aggregation from being emitted upward; here it prevents an
unmergeable intent from being queued as though it will merge. Same move:
make the invalid case unrepresentable rather than audited-for.

**The taxonomy is named as real design work and is not designed here.**
Getting the classes right requires the actual action vocabulary, which
requires the conversation ADR-0039 says must precede planning.

### 6. Every intent carries its cached basis

An intent records **the age and source of the state it was computed
against** — *"requisition raised against a stock reading 6 hours old from
tier X."*

This is what makes an exception diagnosable instead of merely reported.
*"Insufficient stock"* is not actionable; *"insufficient stock; the
maintainer was working from a six-hour-old balance that showed four"* is
both actionable and exonerating. It is the provenance-pays-twice pattern
with a predictable second payment.

### 7. The boundary under stress

While severed, **OpenDDIL is the only place the intent exists.** That
resembles being the system of record, and ADR-0039 §1 forbids being one.

The line, stated precisely because it will be tested:

> **OpenDDIL holds intent durably and authoritatively as intent. It never
> holds the transaction.**

Local authority over *what happened here*; central authority over *the
record*. The maintainer's action is a real, durable, authoritative fact
about the site — and it remains a **request** with respect to the stock
balance until the authority says otherwise. Those are different objects,
and conflating them is precisely how a correlation layer becomes a second
system of record.

## Limits registered rather than assumed

**The operations intent replay requires are a declared contract that
integrators build toward — not a precondition to be discovered.**

*This was first written the other way round, and the framing was wrong.*
The original text treated "does the receiving system expose a
transactional interface?" as the open question deciding whether intent
replay is achievable per target. That assumes OpenDDIL is a passive
consumer of whatever surface happens to exist. **It is not.** An
integrator adopting OpenDDIL owns their materiel system and has a reason
to expose the operations it needs; in practice they will build an
interface *because* they are integrating, whether or not one existed
first. **The interface is a deliverable of the integration, not a
constraint on it.**

So the design question inverts. Rather than *what will they let us call*,
OpenDDIL **declares the operations intent replay requires** — *consume*,
*requisition*, *record maintenance*, and whatever else the action
vocabulary turns out to include — and that declared surface is what
integrators build toward. Same move this project keeps making: **declared,
not inferred**, and the declaring side is the one that knows what the
semantics need to be.

It is also the stronger position. A published intent-replay contract means
**the reconciliation semantics survive the integration** rather than being
lost at a boundary someone else shaped. And it is *easier* for the
integrator: building three or four operation endpoints against a
documented contract is a smaller, clearer task than being asked to
reverse-engineer what a correlation layer wants out of row semantics.

**The contract must be modest.** The fewer operations it requires, the
more systems can implement it — which argues for a small verb set
**discovered from the action vocabulary** rather than a rich API designed
up front. A large contract is a large adoption barrier, and this is the
layer where adoption is the whole point (ADR-0039).

**Degraded mode, not the default case.** Systems where an integrator
genuinely cannot expose operations do exist — sufficiently legacy, or
sufficiently locked. Where that binds, the honest fallback is to keep
intent locally for diagnosis while accepting row semantics on the wire,
**explicitly labelled as worse**: the conflict-evaporation property of §4
is lost, and collisions return. Recorded as a degraded mode so a
deployment can choose it knowingly, rather than as the expected case that
sets the ceiling for everyone.

**Reconciliation outcomes persist on the intent permanently.** An intent
that reconciles successfully **keeps its outcome record**; it is not
discarded on success. Two reasons: the sequence *raised → accepted* is
the only evidence the offline path worked, and a rejected intent's
history is what makes the next one better. Discarding on success is the
transient-evidence failure ADR-0037 exists to prevent, and it is the
default behaviour of most queue implementations, so it must be stated.

## Consequences

**Pros**

- A forward site keeps working, and the reconnection stops being the
  dangerous part.
- Most conflicts stop being conflicts. The commutativity argument is not
  a mitigation; it is a category change in how many exceptions exist.
- Exceptions arrive with intent and basis attached, routable by role.

**Cons**

- Intent replay is materially more work than row sync, and the difference
  is concentrated in the taxonomy (§5) and the per-target interface
  question. A deployment whose authority exposes only a database gets the
  cost without the benefit.
- Three-state rendering (§3) adds operator surface, and
  `raised-unconfirmed` is a state maintainers will find unsatisfying
  precisely because it is honest about uncertainty.
- Durable local custody of intent is a new persistence responsibility at
  every tier that can raise actions, with its own retention and
  sanitization obligations (ADR-0037 VE-7).

**Rejected alternatives**

- *Queue raw row writes and replay them on reconnect.* Rejected: it
  inherits the collision semantics this ADR exists to escape, and it does
  so at the moment of maximum ambiguity.
- *Block writes while severed.* Rejected: it makes the tool useless
  exactly where it is most needed, and maintainers will keep paper
  instead — which is the status quo the project is trying to replace.
- *Auto-resolve exceptions by precedence.* Rejected: it reintroduces
  resolution-without-intent one layer up, and hides business decisions
  inside a merge rule.

## What this ADR did not establish

Per ADR-0037 §6.

- **The action vocabulary.** §5's three classes are a shape, not a
  taxonomy. Which actions exist and how each classifies is unexamined and
  requires the operator conversation.
- **The contract's verb set is undefined**, pending the action vocabulary.
  This is the same dependency §5's taxonomy has, on the same conversation:
  both the classes and the operations are *derived from* the action
  vocabulary, so neither can be designed before it exists — and once it
  does, both follow. **Note what this is not:** it is no longer a
  dependency on anyone's permission or on a survey of existing
  interfaces. The intent-replay design is not waiting on a system's
  current shape.
- **Storage, retention and queue mechanics.** Where intent lives at a
  tier, how long it is kept, and what happens when a site is severed
  longer than retention are all unaddressed.
- **Multi-tier intent.** Whether intent raised at an edge reconciles via
  its parent or directly to the authority, and what happens when the
  intermediate tier is the severed one, is not designed.
- **Nothing was prototyped.** No mechanism here has been exercised.

## Related

- **ADR-0039** — the bridging thesis; §7's boundary is that ADR's §1
  under stress.
- **ADR-0038** — anticipated-capability framing; §2 records an exception
  to that ADR's composes-existing-planes claim.
- **ADR-0032 §c / ADR-0029 / ADR-0034** — the distribution seam §1 rides
  and its existing passengers.
- **ADR-0035** — the basis classes §3 extends with
  `asserted-locally-unconfirmed`.
- **ADR-0034** — propagating-vs-terminal typing, which §5 reuses for
  writes.
- **ADR-0037 VE-7** — sanitization obligations that follow durable local
  custody of operator actions.
