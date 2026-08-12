# Plan — munitions / asset-class taxonomy phases

**Recorded:** 2026-08-11. **Status of this document:** a *recording* of work
already agreed and largely executed, written down because it was the last
substantial plan in the project living only in conversation history. Nothing
here is new design.

---

## How to read the evidence classes

This project has been bitten by reconstruction presented as record, so every
claim below carries its class:

| class | meaning |
|---|---|
| **[repo]** | provable from a commit, file or migration in these repositories; cited |
| **[cited]** | named by a repo artifact but never defined in one — the reference is real, the content is not recorded |
| **[memory]** | held only in conversation/advisory history. Believed accurate, **not ratified**. Treat as a question for the author, not a fact. |

Anything marked **[memory]** needs a human confirmation pass. It is recorded
rather than omitted because the alternative — leaving it in conversation — is
how it gets lost.

---

## The phases

The phase list is **[repo]** — it appears in full in the body of
`openddil-demo 995b3b4` (2026-07-13):

| # | scope | status | evidence |
|---|---|---|---|
| **1** | `asset_class` classifier + `useClassifiedFleet` | **DONE** | `2893e71` |
| **2** | FORCE POSTURE split by class + maintainer picker filter | **DONE** | `2893e71` |
| **3** | Munitions inventory (HQ theater panel) | **DONE** | `995b3b4` |
| **4** | Per-launcher loadout card | **DONE** | `995b3b4` |
| **5** | In-flight parent-launcher linkage + tactical-map filtering | **DONE** | `c20fd4a`, `92358b3` |
| **6** | `failed` counter | **TODO — blocked** | blocker below |

Phase 5 is listed `TODO` in `995b3b4` and completed the same day in
`c20fd4a`; the table above reflects the later state. **Phase 6 is the only
open phase.**

### The taxonomy itself — [repo] `2893e71`

Five classes, derived from two signals already streaming to the client:

- `SENSOR` — platform variant suffix
- `FACILITY` — variant in a closed enum
- `LAUNCHER` — asset appears in `asset_capability_state`
- `MUNITION` — munition-candidate variant **and** no capability record
- `PLATFORM` — everything else (legacy DIS platforms)

`LAUNCHER` and `MUNITION` can share a platform variant, so variant alone
cannot separate them. The classifier resolves it by presence in the
capability table: only launcher hardware emits a capability record.

> **⚠ SUPERSEDED AS AN ARCHITECTURAL IDEA — 2026-08-11. See
> `DESIGN-2026-08-11-declared-asset-class.md` and **GD-11**.**
>
> This entry originally praised the discriminator as *wire-derivable* — it
> required no new field from any producer, which is why the taxonomy shipped
> without a schema change. That framing was wrong, and the cheapness was the
> tell.
>
> The rule infers ontology from **one feed's publishing behaviour** (*things
> that report loadouts are launchers*), not from anything the domain or the
> source declares. It fails silently in ordinary cases — a launcher that has
> not yet emitted a snapshot classifies as MUNITION — and every failure
> produces *a* class rather than `UNKNOWN`.
>
> **The phases and their status below are unaffected.** What changes is where
> the rule belongs: it becomes a *deployment-specific stated mapping* in the
> overlay, with `asset_class` declared as a Silver field the core reads
> rather than computes. Behaviour is preserved through the migration; see the
> design.

---

## Phase 6's blocker

**[cited]** — `995b3b4` and `c20fd4a` both gate phases 5 and 6 on
*"Q3: failure-model wire signal"*. The reference is real and appears twice.
**The Q-list itself is not in any repository** — no commit defines Q1, Q2 or
Q3. Searched: commit bodies, all refs.

**[ratified 2026-08-11]** — what Q3 means: the upstream feed emits **no
termination event** (no HIT / MISS / FAILED). A munition's end-of-life is
inferred only from its track disappearing.

**That inference is unsound at both levels**, which is the part worth
carrying into any upstream conversation:

- **"How did it end?"** — disappearance cannot distinguish intercept-success
  from miss, dud, self-destruct, or simply leaving the exercise volume.
- **"Did it end at all?"** — disappearance *also* fires on dropped packets,
  sim restarts and network gaps. So even the "something happened" half is
  unreliable.

A `failed` counter built on this would be counting an artifact of the
transport, not an outcome.

**[ratified 2026-08-11]** — Phase 6 was **parked 2026-07-14**, to be
revisited only if the upstream feed gains termination events.

> **No memory-class items remain in this document.** Both were confirmed by
> the roadmap holder on 2026-08-11 and are now citable to this record.

---

## Stockpile: the long pole, and a hard prerequisite

### There is no stockpile table — [repo], confirmed twice independently

This is the single most consequential fact about munitions work, and it has
been established from two directions that did not know about each other:

1. **[repo]** `openddil-demo bdc0060` — *"There is NO stockpile table --
   verified against schema.hcl, the only 'ammo' reference there is a comment
   describing a JSONB payload shape."* That commit relabels the UI honestly:
   `(N fired)` → `(N fired this session)`, `EXPD/INIT` → `EXPD*/INIT*` with
   the basis in tooltips.
2. **[repo]** `AUDIT-2026-08-09-schema-provenance` — reached the same place
   from schema archaeology: the capability payload is stored verbatim as
   JSONB with no declared item structure, its only contract three consumer
   reads.

The first found it by asking *"is this number durable?"*; the second by
asking *"where did this shape come from?"* Same answer.

### What the current numbers actually are — [repo] `995b3b4`, `bdc0060`

- **current** — verbatim from the capability feed's per-store ammo count.
- **initial** — a running max-seen per (launcher, store) held in **browser
  memory** (`useMunitionsStockpile`). A page reload re-derives it from
  whatever current happens to be at that moment.
- **expended** — `max(0, initial − current)`, and therefore **resets to zero
  on reload**.

These are session-derived display values, correctly labelled as such. They
are not stockpile accounting and were never intended to be.

### The prerequisite — [repo] `GENERALIZATION-DEBT.md` **GD-10**

**Any durable stockpile work is gated on GD-10.** Counting, aggregating or
projecting over stores would build on a payload with no schema, no owner, and
a de-facto contract of three `.get()` calls. GD-10 records the resolution
shape: an open-standards-derived capability-item schema (J3.7 weapon status,
DIS munition-supply, AFSim stores, S2000M for stockpile semantics), declared
in Silver, with deployment feeds decomposed into it by mapping.

Its governing rule — **discovery is not derivation** — applies directly here:
a deployment's feed and the sample overlay's authored fiction are inputs to
the *mapping*, never sources for the *model*.

**Two prerequisites, not one.** Durable stockpile accounting needs both a
declared item schema (GD-10) **and** a durable store — the missing table
above. GD-10 is the harder half and the one with a recorded home; the table
is straightforward once the shape it holds is decided.

---

## Adjacent tracked item

**[memory]** — a CM-waiver enum follow-up sits alongside this work: an
interim CM-degraded cap currently collapses the "CM red / operationally
green" quadrant into plain `DEGRADED`, and an explicit
`OPERATING_WITH_CM_WAIVER` state was wanted post-demo so that condition is
first-class at every tier. Recorded here because it was tracked in the same
conversations, **not** because it belongs to this plan — it is an ADR-0026
concern.

---

## What this document does not establish

- **The Q-list.** Q1 and Q2 are not referenced anywhere; only Q3 is, and only
  by name. Whether a fuller list exists is unknown.
- **Why phases were ordered as they were.** The what and the status are
  cited; the sequencing rationale is not recorded in any commit.
- **Anything about the upstream feed's roadmap.** Whether termination events
  might ever arrive is outside this repository entirely.
- **That the phase list is complete.** It is complete *as recorded in
  `995b3b4`*. A phase agreed after 2026-07-13 and never committed would not
  appear here.

---

## Related

- `GENERALIZATION-DEBT.md` **GD-10** — the Phase-3-onward hard prerequisite.
- `AUDIT-2026-08-09-schema-provenance.md` §1 — the capability item's
  provenance, and the sketch for a declared schema.
- ADR-0020 — the derived/fed boundary the engagement-worthiness evaluator
  respects (`ORIGIN_DERIVED`, `confidence = 0.0`).
- ADR-0026 — operational-state axes; home of the CM-waiver item above.
