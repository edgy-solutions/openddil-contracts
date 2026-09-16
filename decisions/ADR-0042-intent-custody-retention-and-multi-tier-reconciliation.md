# ADR-0042: Intent custody, retention, and multi-tier reconciliation

## Status

Proposed — 2026-09-16. **Design position. Nothing built, and nothing here
has been observed under an actual sever.** Answers exactly two of the
five items ADR-0040 registered under *What this ADR did not establish* —
storage/retention/queue mechanics, and multi-tier intent — plus the
sanitization obligation ADR-0040 names and ADR-0037 registers.

**It deliberately does not touch the other three.** The action
vocabulary and the contract's verb set are excluded by ADR-0040's own
text: *"both the classes and the operations are derived from the action
vocabulary, so neither can be designed before it exists."* That
conversation has not happened. The fifth — *"nothing was prototyped"* —
is a statement about evidence rather than a design gap, and this ADR
adds to it rather than closing it.

## Context

ADR-0040 decided that a severed site raises **intent**, not state, and
that intent replays against the authority when the link returns. It then
registered what it had not settled:

> **Storage, retention and queue mechanics.** Where intent lives at a
> tier, how long it is kept, and what happens when a site is severed
> longer than retention are all unaddressed.
>
> **Multi-tier intent.** Whether intent raised at an edge reconciles via
> its parent or directly to the authority, and what happens when the
> intermediate tier is the severed one, is not designed.

Those two are this ADR's subject. Everything it decides attaches to a
line ADR-0040 already drew, because custody is a consequence of that
line rather than a new principle:

> **OpenDDIL holds intent durably and authoritatively as intent. It
> never holds the transaction.**

### The shape of the problem, from the severance audit

`AUDIT-2026-08-08` found that the reachback failure is **write-side**.
Of `projector-<edge>`, which reads a local broker and writes a root
database:

> its non-tolerance is *write-side*: the data reaches it fine during
> severance; it simply cannot store it anywhere the local tier can read.

**That is the problem custody exists to answer, stated by an audit that
was not looking for it.** Getting the fact is never the difficulty. The
difficulty is having somewhere local, durable, and readable to put it —
and a queue that drains upward is not that, because during severance it
is exactly the thing that cannot drain.

### What the intent already is, in the platform's own class system

The reasoning plane's ADR-0054 classifies every store by four fields,
and edge-authored intent is the case its worked example uses — the
combination none of that ADR's three lifecycle shapes covers:

| field | value |
|---|---|
| reproducibility | `stateful` |
| authority | `upstream` |
| sync obligation | `flush-up` |
| releasability | reserved, at ROW granularity |

**AN EARLIER DRAFT WROTE `authority: upstream, pending`, AND THAT WAS
WRONG IN A WAY WORTH RECORDING** — it was the first stress this pairing
put on the neighbouring schema, and it surfaced before either ADR was
enforced, which is the convergence working as intended.

`pending` is **not a qualifier on authority; it is the row's
reconciliation status.** The class belongs to the STORE and does not
transition: an intent row lives in the intent store as `stateful ·
authority: upstream · flush-up` from raise to outcome, and acceptance
changes the **row's status**, never the store's class. Giving the class
a lifecycle would reintroduce the per-write field `iagent:ADR-0054`
removed at its own ratification.

**This is not a borrowed vocabulary; it is the same fact from the other
side.** `authority: upstream` is §7's line as a field — local authority
over what happened here, central authority over the record — and
`flush-up` is *replicate intent, not state* as a field. The class is
useful here because it makes the wrong storage choice **unwritable
rather than reviewed**: a store declaring `authority: upstream` cannot
be written by an interface that writes records of fact.

## Decision

### 1. Custody — intent is an event on a local topic, and the tier rail carries it

**Where it lives: BOTH, and one of them alone is not custody.**

- an event on a **local** topic at the tier that raised it — durable
  transport, and the thing the rail carries;
- **and a projected row in the tier store** — which is what makes it
  legible *here*.

Not a queue awaiting drain, and not a row in a root store the tier
cannot reach.

**THE SECOND HALF IS NOT A CONVENIENCE.** ADR-0040 §3 requires a
locally-raised action to *render* as `asserted-locally-unconfirmed`, and
the maintainer's screen reads the tier store — not topics. An intent
that exists only as a topic event is durable and **invisible**, so
*"readable by that tier"* would be a claim the interface cannot honour.
Custody is the event plus the projection.

**What it is:** typed by composability per ADR-0040 §5 and carrying its
cached basis per §6, so an intent is self-describing at the moment it is
raised rather than at the moment it reconciles. The basis travels with
it because the basis is what makes it *checkable* later — and because
the tier that could have supplied it may be unreachable when the check
happens.

**How it moves:** by the **existing tier rail**, and this ADR invents no
flush mechanism. The rail is already the thing that carries events
upward; intent is an event; a second mechanism would be a second thing
to sever.

> **A queue that only drains upward is not custody.** Custody is the
> property that the fact is safe and legible *here*, for as long as it
> takes, whether or not it ever drains. The rail is how it eventually
> leaves; it is not where it lives.

#### Intent identity is the record key, and the relay invariant applies

**An intent carries a stable id — origin tier plus sequence — and that
id is the record key.** Relays preserve it; the authority deduplicates
by it.

Every mechanism in this ADR replays: two hops of relay, replay on
reconnect, and reconciliation via a parent. **All three are only safe
if the same intent arriving twice is recognisable as the same intent**,
and the id is what makes that true without the authority having to
reconstruct identity from content.

**The hazard is not hypothetical and is recent**: the null-key relay
defect is exactly the shape that would corrupt intent custody silently —
a relayed record losing its key does not fail, it duplicates, and the
duplicate is indistinguishable from a second action by the maintainer.
This rule is cited to that incident rather than argued from first
principles.

#### Keyed by intent id, and NEVER compacted by asset

**State the key and the compaction posture together**, because either
alone reads as safe. Custody topics are keyed by **intent id**, so
compaction is harmless — every intent is its own key.

**Keyed by asset id and compacted, earlier intents for the same asset
vanish** — and what vanishes is precisely the history ADR-0040's Limits
section requires be kept: *"a rejected intent's history is what makes the
next one better."* The phantom-partial incident showed what replayed
history over a changed key does; this is the same mechanism pointed at a
record that must not be superseded.

### 2. Retention — authority-pending intent does not age

**Authority-pending intent never ages out before it is accepted or
rejected.** A retention policy that expires an unreconciled intent
destroys the only record that the site acted, and does so precisely in
the case the offline path exists for: a long severance.

**Reconciliation outcomes persist permanently**, which ADR-0040's Limits
section already requires and this ADR does not re-decide:

> An intent that reconciles successfully **keeps its outcome record**;
> it is not discarded on success. Two reasons: the sequence *raised →
> accepted* is the only evidence the offline path worked, and a rejected
> intent's history is what makes the next one better.

That paragraph also names why it must be written down at all: *"it is
the default behaviour of most queue implementations, so it must be
stated."* The same sentence applies to §2's first rule — most queues age
by default, and the default is wrong here.

**Severance outlasting retention is a declared degraded mode, not a
silent policy.** ADR-0040's Limits section supplies the template, and
this ADR reuses it rather than inventing a second way to say it:

> Recorded as a degraded mode so a deployment can choose it knowingly,
> rather than as the expected case that sets the ceiling for everyone.

So: a deployment whose storage genuinely cannot hold intent for the
severance it may experience **declares that bound**, and declares what
happens at it. What it must not do is discard silently, which renders as
a site that never acted.

### 3. Multi-tier — intent reconciles via its parent, and custody is recursive

**Intent raised at an edge reconciles via its parent**, not directly to
the authority. The rail is hierarchical (ADR-0022/0023) and intent rides
it; a direct path would be the second mechanism §1 refuses, and it would
be the mechanism that only exists for the failure case, which is the one
nobody exercises.

**A severed intermediate tier holds custody for its children under the
same rule.** It is not a relay that fails when the link above it fails;
it is a tier, and §1 applies to it exactly as written. Children
reconcile to it, it holds their intent locally and durably, and it
reconciles upward when its own link returns.

> Custody is **recursive**, and it has to be, because the alternative is
> that a tier's tolerance depends on the tier above it — which is the
> property ADR-0022's invariant exists to deny.

#### Ordering at the parent, named rather than left to emerge

**The parent forwards each child's intents in that child's arrival
order, and NEVER reorders across children.**

ADR-0040 §5's order-dependent class makes this a real question the
moment two children raise intents against one resource: a parent cannot
order them by the children's clocks, because a severance is exactly when
those clocks are unreconciled and a parent that tried would be inventing
a sequence.

**Cross-child ordering conflicts surface as named exceptions at the
authority** — ADR-0040 §4's remainder, *"named business exceptions with
intent attached"* — and not as a merge the parent performed. **Left
unstated, custody quietly acquires a merge semantics ADR-0040 refused**,
which is the failure this whole design exists to avoid arriving through
an implementation detail.

**THE SCOPE OF THIS SECTION IS SMALLER THAN IT LOOKS, AND THAT IS A
MEASURED FACT.** The severance audit found that external runtime
dependencies are *"concentrated, not scattered"*: only Restate
constrains tier placement, and it constrains exactly two services. So
holding custody at an intermediate tier is *"a two-service problem, not
a stack-wide one"* — which is the sentence a reader should check this
section against.

### 4. Sanitization — the gate binds at replication

ADR-0037's **VE-7** registers the gap and states the fix shape: the
check binds *"at the moment an artifact leaves the workspace"*, and is
*"a step in the procedure that produces the artifact rather than a
separate discipline someone remembers."*

**For intent, that moment is tier replication.** An intent raised
locally and held locally has not left anything; an intent crossing a
tier boundary has. So the gate is a step in the replication path, not a
review before a release.

**THE GATE REFUSES; IT NEVER REDACTS.** A redacted intent is not the
intent the site raised, and an intent that reconciles against a
different basis than the one it was raised with is the thing §6's cached
basis exists to prevent. At replication the gate **blocks and alerts**;
it does not mutate. One sentence, and it closes a door VE-7's shape
would otherwise leave open — the apparatus that protects becoming the
thing that silently alters.

**What is OSS-visible is the rule, not the pattern list**, per VE-7's
own reasoning about the second instance of its shape — *"publishing an
enumeration of what a sanitizer matches"* is itself an exposure. This
ADR states that intent is sanitized before it crosses a tier boundary
and at which step; the patterns stay with the hygiene tooling.

VE-7's framing is worth carrying into this ADR whole, because it is why
custody makes the obligation *larger*:

> **the apparatus built to manage sensitive material becomes the
> exposure**, because attention sits on the artifact being protected
> rather than on the protecting… *the control describes what it
> protects*.

Durable local custody of operator actions creates a new sensitive
-bearing artifact class — a maintainer's actions at a named site, held
for the duration of a severance — and it is created by the mechanism
designed to make the site *more* honest. That is the shape exactly.

## Limits registered rather than assumed

**NOTHING IN THIS ADR HAS BEEN OBSERVED UNDER A SEVER**, and §3 rests on
a table that says so of itself. `AUDIT-2026-08-08` closes with:

> Live verification of any classification (no populated-cluster access).
> **This table is derived from charts and source, not observed behaviour
> under an actual sever.**

The classifications that §3 reasons from are therefore a **reading**,
not a measurement. This ADR inherits that limit rather than its
confidence: the recursive-custody rule is derived from how the
components are wired, and no tier has been watched holding its
children's intent while severed.

**The first thing that should be built here is not a mechanism but an
observation** — one tier, actually severed, with its children raising
intent — because every rule above would survive being wrong in the same
way: quietly, until a site that acted appears not to have.

**Retention bounds are not specified in time.** §2 rules that
authority-pending intent does not age and that a bound must be declared
where storage forces one; it does not say how long, because the honest
answer is per-deployment and a number here would be a guess that reads
as a requirement.

## What this ADR did not establish

Per ADR-0037 §6.

- **The action vocabulary and the verb set.** Excluded by ADR-0040's own
  text, not deferred by preference.
- **Queue mechanics below the event.** §1 rules where intent lives and
  what carries it, not the retention implementation of the local topic.
- **What a rejected intent shows an operator.** ADR-0040 §3 rules that
  it must never present as an accepted transaction; what the rejection
  itself renders as is a surface question and belongs with ADR-0035's
  classes.
- **Any measurement.** See Limits.

## A finding recorded in both corpora, and resolved in neither

The safety personas synced this week (`SAFETY_ENGINEER`, and the two
test subjects) are subjects in the **reasoning-plane corpus only**.
ADR-0031 §2.3 requires one subject record carrying both attribute
families before the converged node exists.

Recorded here and in the reasoning plane's equivalent debt register
rather than resolved in either, because resolving it in one corpus is
what would make it invisible in the other — **the subject namespaces
merge; the policy modules compose; those are different operations and
only the first is outstanding.**

**AND THE MERGE IS SMALLER THAN "ONE SUBJECT RECORD" READS.** The
natural merge point already exists: **one `sub` from the shared identity
provider, with two attribute families keyed by it.** That is a join on a
key both sides already carry, not a new record type either side has to
author — worth saying, because the phrase invites a schema where a
foreign key is what is actually required.

## Related

**CITED `repo:ADR-NNNN` FROM HERE ON, per the 2026-09-16 convention.** ADR
numbers now collide across the two corpora — 0029, 0031, 0034, 0035 and
0037 each name a different document in each — so an unqualified number
already means two things. Unqualified references below are
`openddil:` by locality.

- **`openddil:ADR-0040`** — the decision this ADR completes; §7 is the line custody
  attaches to, §5 and §6 type what is stored, and its Limits section
  supplies both the permanent-outcome rule and the degraded-mode
  template.
- **ADR-0037 VE-7** — registers the sanitization gap; §4 is that gate
  placed for this artifact class.
- **ADR-0035** — the claim classes; ADR-0040 §3 extends them with
  `asserted-locally-unconfirmed`, which is what a held intent renders
  as.
- **ADR-0031** + 2026-09-08 addendum — the converged node, and the
  subject-namespace finding above.
- **ADR-0022 / ADR-0023** — the hierarchical rail §1 and §3 ride rather
  than duplicate.
- **AUDIT-2026-08-08** — the write-side framing in Context, the
  two-service scope in §3, and the unobserved-classification limit.
- **Reasoning plane, ADR-0054** — the four-field data class; edge
  -authored intent is its worked example of a combination no lifecycle
  shape covers.
