# Exchange ledger

**Opened:** 2026-08-12. Items that can only be resolved **outside these
repositories** — questions for an upstream producer, checks that must run
against a private overlay or a deployment this project cannot see.

## Why these need their own ledger

A follow-up inside the corpus has a home document and an owner. **These do
not.** They are blocked on someone else answering, and that makes them
fail in a specific way: they get raised in conversation, half-answered,
and re-derived months later by whoever next hits the same wall.

Two of the entries below were **already discovered twice each**, from
different directions, by people who did not know about the first finding.
That is the cost this file exists to stop paying.

They also share a property no follow-up register handles: **an exchange has
a direction and a counterparty**, so it is subject to the egress rules that
internal work is not. See §Handling.

## Handling — binds every row

- **Generic framing only, in this file and in anything derived from it.**
  Counterparties are *"the upstream producer"*, *"a deployment operator"*,
  *"a private overlay"*. No organisation, product, site or programme names
  appear in this repository. Rows are written so the *question* is complete
  without the identity.
- **VE-7's egress gate applies to everything sent.** An artifact attached
  to one of these asks — a capture, a schema excerpt, a console dump — is
  sanitized **before it leaves**, not before it is reviewed. A recording
  cannot be redacted after delivery, and the recipient's copy is beyond
  recall by definition.
- **Answers get recorded where the substance lives**, not here. This file
  tracks that an exchange is open, not what it concluded.

---

## Open

### Outbound — questions for an upstream producer

These are one conversation, not three, and should be raised together: they
are the same question wearing different clothes — **what does the source
declare, versus what are we inferring from its behaviour?**

| ID | Ask | Blocks | Substance |
|---|---|---|---|
| **X-1** | Does the feed carry a durable **stockpile / capacity** figure? Today there is an absolute count and no capacity, so nothing can express *percent remaining* or survive a reload. | Munitions Phase 3 onward; durable stockpile accounting | `PLAN-munitions-taxonomy-phases.md`; **GD-10** |
| **X-2** | Does the feed emit **termination events** (HIT / MISS / FAILED)? | Munitions Phase 6 (**parked** pending this) | `PLAN-munitions-taxonomy-phases.md` |
| **X-3** | Does the feed **declare asset class**, or an attribute from which class is derivable *by declaration* rather than by publishing behaviour? | **GD-11**; retiring the inferred classifier | `DESIGN-2026-08-11-declared-asset-class.md` |
| **X-4** | For each producer: **what declares national origin?** Not "can we derive one" — what *states* it. | ADR-0029 Phase 0/1; the §7 gate | `PLAN-arc2-slice1-opening-package.md` §5 step 2 |

**X-4's sibling left this list entirely on 2026-08-19, and the reason is
worth keeping.** A *"does your feed carry entity health?"* question was
being drafted for the same conversation. It turned out the feed already
does — DIS entity appearance has been arriving on Bronze since the sidecar
was written, and the mapping was never built (ADR-0026 §Amendment). **The
ask would have gone to a producer already sending the data.**

*Standing check before anything joins this list:* walk the path from
producer to reader first. An absence measured at the reader localizes
nothing (ADR-0037 §Named limits), and this ledger is the most expensive
place to be wrong about where a gap lives — a question asked of a
counterparty cannot be quietly withdrawn.

**X-2 has a stronger framing than "better outcome attribution", and it is
worth using.** End of life is currently inferred from a track
disappearing, which cannot distinguish success from miss, dud or
self-destruct — **and also fires on dropped packets, restarts and network
gaps.** So the ask is not for richer outcomes; it is for *the only signal
that separates "an event occurred" from "the feed hiccuped."* Producers
generally recognise that as legitimate immediately.

**X-4 is new and is the one most likely to be skipped**, because a
plausible answer already exists (parse it from an id convention). That is
inference from a naming habit, and releasability is the worst place to
inherit one: ADR-0029 §7's gate rests entirely on telling *not labelled*
apart from *labelled by guess*.

### Inbound — checks against systems not visible here

| ID | Check | Why it matters | Substance |
|---|---|---|---|
| **X-5** | In any private overlay: does a mapping set `Quantity.unit` **unconditionally**, or `.or(0)` a count that is paired with a capacity? | The public twin carried both; **the fixes do not propagate** — an overlay authored by copying holds its own copy | `AUDIT-2026-08-11-fallback-honesty.md` F1/F2 |
| **X-6** | In any private overlay: does anything stamp releasability labels by a route the core cannot see? | Would change `PLAN-arc2-slice1` §2 materially — a non-zero labelled count falsifies the "nothing writes them" reading for *that* deployment | `PLAN-arc2-slice1-opening-package.md` §6 |
| **X-7** | On the pilot cluster: run the §7 gate. The lab shows **42 populated rows, zero labelled** — that must not be restated as a claim about another cluster. | Deployed schemas provably diverge (`inventory_items` differs lab vs schema-of-record) | ADR-0029 §7; `PLAN-arc2-slice1` §2 |
| **X-8** | On a co-located consumer project: does its data-access authorization have a **positive-decision** audit trail, or only denials? | Raised as a **verify-first question, not a finding** — read from an installed copy, so confirm against source before treating it as true. Not a dependency either way | ADR-0029 Phase 3 note |

**X-5 and X-6 are one visit to the same file set**, and X-7 is one query.
Grouping them is the whole point of writing them down together — each is
individually too small to schedule and collectively they are one sitting.

---

## Reconciliation — 2026-08-19

**Closed by work rather than by answer:**

- **The health-axis question, never asked.** See above. The source existed;
  the mapping did not.
- **X-5 / X-6 remain open but their public twin is now clean.** The
  fallback-honesty fixes (`efef7a6`) and the ASTERIX mapping both landed
  with encode verification, so a private overlay copying either specimen
  today inherits corrected constructions. The check is still needed — the
  fixes do not propagate — but its urgency dropped from *"an overlay may be
  silently defaulting fuel"* to *"an overlay may be an old copy."*

**Unchanged and still outbound:** X-1 (stockpile/capacity), X-2 (termination
events), X-3 (asset class declaration), X-4 (national origin). These are one
conversation and none moved this week.

**X-7 (the pilot-cluster §7 gate) gained a second reason to run.** The
upgrade rehearsal found the lab's images on a rolling tag with two digests
live in one release. The pilot cluster is digest-pinned, so the same query
that answers X-7 should also confirm that pinning holds — one session, two
answers.

**X-8 unchanged**, still a verify-first question.

## Reconciliation — 2026-09-05 (Arc 2 Slice 1)

**X-4 did not close, and it is worth being precise about why, because the
work that just landed could easily be mistaken for closing it.**

Arc 2 Slice 1 shipped a deployment that DECLARES national origin per asset,
in a reviewed file, attributable to a commit — the strongest rung of the
provenance ladder reachable **without a producer that states it on the
wire**. The read path now enforces against those labels end to end.

**That answers the question for one deployment's authored fiction. X-4 asks
it of real producers, and no producer was contacted.** The distinction
matters exactly as much as it did before: a declaration this project writes
about someone else's data is still this project's assertion. What changed is
that the *mechanism* is now proven and the remaining gap is purely the
provenance of the values — which is a cleaner ask than it was, not a
cancelled one.

Two things now exist that make the ask cheaper to raise:

- **A concrete shape to ask about.** `originator_nation` (ISO-3166 alpha-3)
  and `releasable_to` are on the wire as `Provenance` fields 9 and 10,
  aligned to STANAG 4774/4778 label concepts. The question is no longer
  "could you tell us nationality somehow" but "does your feed carry a field
  we can map to this one."
- **A demonstrated consequence of not having it.** The deployment overlay
  enumerates fourteen assets by hand. That does not scale, and it silently
  stops being true the moment the fleet changes — which the completeness
  gate WILL catch, but only after the fact.

**X-1, X-2, X-3 unchanged.** Still one conversation, still not raised.

**X-5 / X-6 gained weight.** The public specimen now carries a releasability
stamp that ENCODES, where before it carried one that hard-failed. An overlay
authored by copying today inherits a working construction — which is the
improvement — but it also inherits an **id-parsing derivation** that is
legitimate only as a stated local assumption. X-6's question ("does anything
stamp releasability labels by a route the core cannot see?") now has a
second half worth asking alongside it: *if something does, what does it
derive them FROM?* An overlay that quietly parses a nation out of an
identifier is producing exactly the "labelled by guess" state the §7 gate
cannot distinguish from a real declaration.

**X-7 is partially discharged, and only for the lab.** The §7 gate now
exists as a script rather than a hand-run query
(`openddil-helm/scripts/check-releasability-completeness.sh`), it enumerates
its tables from `information_schema` as ADR-0029 requires, and on `edgy-lab`
it **passes**: three populated tables, fourteen rows each, zero unlabelled.

**None of that is a claim about the pilot cluster**, and the script says so
in its own output for precisely this reason. The row stays open. What it
costs to answer has dropped from "compose a careful query" to "run one
script and read its last paragraph", and the second reason for running it —
confirming digest pinning holds there — is untouched.

**X-8 unchanged**, still a verify-first question. Worth noting that Slice 1
built the positive-decision audit trail that question was about the absence
of: every allow and every deny is recorded with subject, allowed nations,
policy version, predicate and timestamp. That is a data point for the
conversation, not an answer to it.

## What this ledger is not

- **Not a commitment that any of these will be asked.** Raising X-1..X-4
  is a relationship decision, not an engineering one, and it is not this
  file's to make.
- **Not a record of answers.** When one lands, it goes to the document that
  owns the substance; the row here closes with a pointer.
- **Not complete.** It holds what was identified while doing other work.
  No sweep for external dependencies has ever been run, so absence of a
  row is not evidence that a boundary question does not exist — the same
  limit **UD-6** states for the failure-mode register.
- **Not a substitute for the follow-up index.** `FOLLOW-UPS.md` tracks what
  this project can fix by itself. This tracks what it cannot.
