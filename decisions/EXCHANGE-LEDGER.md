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
