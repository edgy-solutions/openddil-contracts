# DESIGN — interface contracts A and B (opening package)

**Status: PLAN ONLY. Nothing built. Go-signal reserved.**
Written 2026-09-06. Records the addendum decisions taken the same day.

Two contracts, in opposite directions, and the reason they are one package
is that they share an identifier problem (ADR-0041) and a single honesty
rule:

> **Nothing crosses a boundary ungated, and nothing that crosses is
> described as integrated until a conformance suite says so.**

| | direction | consumer | shape |
|---|---|---|---|
| **Contract A** | OpenDDIL → C2 | a command-and-control picture | status/readiness of assets |
| **Contract B** | OpenDDIL ↔ sustainment system of record | a materiel management system | read of record state, write of *intents* |

---

## §1 — Contract A derives from open vocabulary, not from a C2

**The decision, and it is the load-bearing one: Contract A is defined
against PUBLISHED status vocabulary, never against a particular C2's
inbound interface.** A contract shaped to one consumer's current API is
that consumer's API with a new name; the next consumer gets a second
contract, and the "standard" was never one.

### The candidate vocabularies

These are the open sources Contract A's status semantics derive from. The
package's first task is choosing among them, not inventing beside them.

* **MIL-STD-2525 / APP-6** (symbology). Carries operational-condition and
  status amplifiers — present/anticipated, and a condition axis
  (fully-capable / damaged / destroyed / full-to-capacity). Closest thing
  to a universal *display* vocabulary for asset condition, and what a C2
  operator is already reading.
* **JC3IEDM (STANAG 5525)**. Object-item status and operational-status
  enumerations, designed exactly for cross-system exchange of what a thing
  is and how it is doing. The most semantically complete candidate and the
  heaviest.
* **Cursor-on-Target (CoT)**. Event schema with a `detail` extension
  point; the de-facto exchange format wherever TAK is present. Weakest
  status vocabulary of the three, strongest adoption.
* **Link 16 / MIL-STD-6016 J-series** where an asset's status already has
  a J-message home (the corpus already anchors weapons-capability
  vocabulary this way).
* **Materiel readiness vocabulary — FMC / PMC / NMC.** Already the
  corpus's egress vocabulary for opted-in consumers, and the one a
  sustainment audience reads without translation.

**Expected shape of the answer:** CoT or 2525/APP-6 as the *carriage* a
C2 already accepts, with JC3IEDM-derived enumerations as the *semantics*,
and FMC/PMC/NMC as the readiness projection. Recorded as an expectation,
not a decision.

### The thin egress connector is a sanctioned fallback, not a workaround

A C2 that has not adopted Contract A is the normal case, not the failure
case. **The sanctioned answer is a thin egress connector: a small,
per-consumer translation from Contract A into whatever that C2 accepts
today.**

Two properties make it a fallback rather than a fork:

1. **It translates, it does not decide.** Every releasability, severity and
   identity decision has already happened upstream of it. A connector that
   filters, re-labels, or infers is a second authorization point nobody
   reviewed (ADR-0029 §1), and that is the line it may not cross.
2. **It is per-consumer and disposable.** A connector's existence is
   evidence of one C2's adoption gap, and it retires when that gap closes.
   Connectors that accumulate permanently are the signal that Contract A
   chose the wrong vocabulary — which is a finding about the contract, not
   about the connectors.

---

## §2 — Contract B reflects the two source modes an integrator actually faces

An integrator facing a sustainment system of record has **two different
problems in the two directions**, and a contract that treats them
symmetrically will be wrong in one of them.

### Read side — record extraction

**Records are extracted, not subscribed to.** The realistic source is a
SQL database the integrator can read, and the sanctioned mechanism is
**`dlt` against that SQL source, publishing into the catalog shape** —
incremental extraction with an explicit cursor, landing in the declared
catalog form rather than in whatever the source's tables happen to look
like.

Three constraints on this path:

* **Read-only, and structurally so.** The extraction path holds no write
  capability. Not "does not write" by convention — cannot, because the
  credential it uses grants nothing else.
* **The catalog shape is the contract, not the source schema.** A
  consumer binds to the published shape; the source's columns are an
  implementation detail of one integrator's overlay. This is the same rule
  GD-10 exists to enforce one layer down: *discovery is not derivation.*
* **Extraction lag is data, not a footnote.** Every extracted record
  carries the cursor position and the extraction time, because a warehouse
  read is not a stream and a consumer that treats it as one will present
  stale rows as current ones.

### Write side — strictly the target's transactional operations

**OpenDDIL never writes to a system of record's tables.** Writes go
through the target's own transactional operations — the APIs, services or
transactions by which that system maintains its own invariants.

This is not fastidiousness. A materiel system's tables encode invariants
its transactions enforce: balances, reservations, custody, audit. A direct
write satisfies the schema and violates the system, and the damage
surfaces later, elsewhere, as a discrepancy nobody can trace to us.

**Contract B therefore carries INTENTS, not row updates.** The verbs
propose; the system of record disposes. A rejected intent is a normal
outcome that must be represented, not an error.

### The degraded mode, named because it is the common case

**Where a target exposes no transactional write operations at all**, the
honest position is:

> **Intents are emitted to an advisory queue for operator mediation, are
> explicitly non-authoritative, and are never auto-applied. The UI must
> show that an intent is unapplied — an intent that looks executed and is
> not is worse than no write path at all.**

Two rules keep this from decaying:

* **A degraded write path is labelled in the data**, not only in the
  documentation, so a consumer of the intent stream can tell mediated
  from transacted without knowing which target it came from.
* **Direct table writes are not the escalation.** If the queue is
  insufficient, the answer is a transactional operation on the target
  side — a conversation with its owner — not a credential with `INSERT`.

---

## §3 — The reference adapter skeleton, and what it may not know

**Deliverable: an OSS adapter skeleton an integrator copies into their
private overlay.** Two halves, mirroring §2:

```
adapter/
  reader/        dlt source: incremental SQL extraction -> catalog shape
                 cursor + extraction time stamped on every record
  client/        intent-verb client: propose / acknowledge / cancel
                 transport-agnostic; a Driver protocol the overlay implements
  identity/      BOTH identifier schemes carried, never collapsed
  conformance/   the suite the adapter must pass (see §4)
```

### Both identifier schemes are carried, always

Every record and every intent carries **the tactical identifier and the
sustainment identifier side by side**, neither derived from the other.
ADR-0041's whole argument is that these schemes were designed
independently for different questions and no heuristic join between them
is explainable when it is wrong. The adapter's job is to *carry* the pair
that some authority asserted; it is never to *infer* one from the other.

An adapter that can produce a sustainment identifier from a tactical one
by rule has either been given a real mapping — in which case it should
carry it as data — or has invented one.

### What the skeleton may not contain

**No target-system knowledge whatsoever.** No table names, no endpoint
paths, no vendor terminology, no field mappings, no credentials, no
site-specific enumerations. The skeleton defines the *shape* of a reader
and the *verbs* of a client; the overlay supplies the driver.

This is the same split the customer-bundle work already runs on, and the
reason to restate it: a skeleton that acquires one target's specifics is
no longer scaffolding, it is that integration, and the second integrator
inherits assumptions nobody wrote down.

---

## §4 — The conformance suite is the adapter's acceptance

**An adapter is integrated when it passes the conformance suite. Not when
it compiles, not when a demo runs, and not when a document says so.**

This is written flatly because the corpus already records the failure it
prevents: artifacts have carried words like *contract*, *ICD*, *real* and
*integrated* while being reconstructions or placeholders, and the label
was believed instead of the wire. **Wire outranks schema; a suite that
runs outranks both.**

The suite must:

* **Run against the adapter, not against a mock of it.** A conformance
  suite that exercises a stub proves the stub conforms.
* **Fail distinguishably from not running.** The existing bundle
  conformance stage is the pattern: a summary line with a count, anchored
  in CI so an empty run cannot read as a pass.
* **Cover the degraded write path explicitly**, because it is the path
  most likely to be present and least likely to be exercised — including
  the assertion that an unapplied intent is *rendered* as unapplied.
* **Assert both identifiers survive** every hop, since a collapsed pair is
  the failure ADR-0041 predicts and it is silent.

*Sequencing note:* the suite is written with the contracts and before the
first adapter, so the first integrator's implementation is measured
against it rather than becoming it.

---

## §5 — What this package deliberately does not decide

* **Which vocabulary Contract A lands on.** §1 names the candidates and an
  expectation; the choice is the package's first task.
* **The verb set for Contract B**, beyond propose/acknowledge/cancel as
  the minimum. The concrete verb list is the substance of the first
  conversation with a system-of-record owner, and inventing it here would
  pre-empt that conversation with a guess.
* **Egress gating.** Nothing crosses ungated, and the gate is Slice 2's
  own opening package — this one assumes it rather than specifying it.
