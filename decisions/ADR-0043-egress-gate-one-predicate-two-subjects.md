# ADR-0043: The egress gate — one predicate, two subjects

## Status

Proposed — 2026-09-23. **Built, measured and red-checked under compose.
Not deployed anywhere.** It cannot be more accepted than its premises:
every admit/refuse rule it implements comes from
`PLAN-arc2-slice2-opening-package.md`, which is itself **PROPOSED** and
whose five rules are the user's to confirm.

What that means concretely: the code exists, the numbers below were
measured rather than predicted-and-assumed, and the central claim has a
test that fails when the claim is broken. None of that makes the rules
right — it makes them **arguable against something that runs**.

## Context

ADR-0029 named two gates and two adversaries:

- the **read gate** protects against the wrong *person* at the read
  surface. Slice 1 shipped it: a PDP answering `allow`, `allowed_nations`,
  `policy_version` and `corpus_version`, a PEP that renders those into a
  SQL predicate, and a decision log carrying every allow and every deny.
- the **egress gate** protects against the wrong *destination* at the
  outbound boundary. Nothing was built.

The ADR also recorded the asymmetry that makes the second one the harder
half: a read denial is recoverable — the operator sees less than they
wanted and says so — while an egress leak is durable and has no human in
the loop. By the time anyone could look, it has already happened.

`DESIGN-2026-09-06-interface-contracts.md` §5 closed with *"Nothing
crosses ungated, and the gate is Slice 2's own opening package — this one
assumes it rather than specifying it."* That package did not exist, so
Slice 2 could not start: the corpus held a fence, two adversaries and
three forward notes, and **no admit/refuse rule at all**. It was written
first (`PLAN-arc2-slice2-opening-package.md`) and this ADR is what was
built against it.

## Decision

### 1. ONE predicate, evaluated with two different subjects

Egress is not a second release rule. It is **the read rule with the
destination in the subject slot**.

```
(originator_nation IS NOT NULL AND originator_nation IN (:nations))
  OR
(releasable_to IS NOT NULL AND releasable_to && ARRAY[:nations])
```

For the read path `:nations` is the person's entitlement. For the egress
path it is the destination's. Nothing else differs.

The alternative — a stricter, separately authored egress rule — was
rejected because it is a **second implementation of the release rule**,
and two implementations of one rule diverge in the direction nobody is
looking. An ATL C2 seeing what an ATL person sees, including
ATL-authored readings, is the correct consequence and not a leak: the
contrary position says a nation may not hand its own data to its own
command system.

The consequence worth stating out loud, because it looks alarming in a
count: **the ATL stand-in admits most of the fleet.** That is the
prediction being confirmed, not the gate failing.

### 2. A destination is a subject, not a fourth category

The policy corpus already holds subjects with `nations`. A system
principal with `nations` is the same object without a person behind it,
so the C2 stand-in is `system:c2-stand-in-atl` with `nations: [ATL]` —
one nation, because a single nation is the **discriminating** case
against this fleet's labels. A two-nation stand-in would admit
everything and measure nothing.

This keeps `destination_unknown` a real and distinct outcome: a
destination absent from the corpus is refused under its own reason, never
silently treated as entitled to nothing.

### 3. Enforcement is a compiled in-process predicate, asked once

The gate asks the PDP **once**, at startup, for its one destination, and
compiles `allowed_nations` into a record predicate it then evaluates
in-process for every record.

This is a compile step, **not a cache**. The difference is the failure
mode: a cache serves a stale answer when the PDP goes away, and a stale
entitlement is exactly what an entitlement revocation exists to stop. The
gate instead stops forwarding and exits.

`policy_version` and `corpus_version` are therefore fixed facts for the
life of the process, which is what makes them meaningful in every line of
its decision log rather than values that drift mid-stream.

### 4. The agreement test is the mechanism, not the intention

§1 is cheap to state and easy to quietly break — a clause added to the
SQL, a condition tightened in the Python, and the two disagree for months
about rows nobody looked at.

So the two are compared where they can actually disagree:
`tests/hero_scenario_v3/test_51_egress_read_agreement.py` runs the read
path's SQL **in Postgres** and the gate's compiled predicate **in
process** over one fixture, for every entitlement in the corpus, and
fails on any row where the verdicts differ.

The fixture is deliberately **not** the fleet. The fleet has no
aggregates, no NULL-authored rows and no empty-array rows, so a fixture
drawn from it would exercise one clause of a two-clause predicate and
pass. The fixture carries the composed-empty aggregate, the both-NULL
row, the empty-string author that proto3 materialises, and a third
nation. The interesting disagreements are about `NULL` versus `[]`, about
`&&` on an empty array, and about the entitled-to-nothing subject — and
those only have answers when a real database gives them.

It also refuses to pass vacuously: if fewer than six fixture rows were
ever admitted by anything, the test fails rather than reporting perfect
agreement between two predicates that both said no to everything.

### 5. A process at the boundary, not a filter inside a connector

Contract A is explicit that the thin per-consumer connector **translates,
it does not decide**. A release decision made inside a connector's
mapping is a decision distributed across every connector, and "the single
boundary" then has no place a reader can point at.

So the gate is its own process. Whatever carries the result onward is
downstream of it and has no policy in it.

**One destination per process**, on purpose. A gate serving several
destinations from one loop holds several compiled predicates and writes a
log in which "admitted" is ambiguous until you also read the destination
field.

### 6. Admitted records cross byte for byte

The gate decides; it does not translate, redact or re-encode. A gate that
rewrote an admitted payload would be making a **second** decision — about
what the destination sees *within* a record it was entitled to — with
nothing in the log saying it had.

### 7. Nothing is dropped silently, and the reasons are not interchangeable

Every record produces exactly one decision line, admitted or refused,
carrying the record's key, the class it fell into, the reason, the
destination, its nations, and both versions. The count of lines equals
the count of records seen; if it does not, that is a bug and not a
policy.

Four outcomes are deliberately **kept apart** rather than collapsed into
"denied":

| Outcome | Why it is its own reason |
|---|---|
| `no_nation_overlap` | an actual policy denial — the label was read and did not entitle this destination |
| `unlabelled` | deny-unlabeled, asserted **at the gate** and not inherited from the read path. On the wire, proto3 renders an unset string and an empty repeated field identically to a producer that declared nothing, so this is the floor |
| `classification_not_evaluated` | the fence, §8 |
| `undecodable` | the record was **never evaluated**. Logging it as a denial would claim the policy looked at it and said no |
| `destination_unknown` | the corpus does not know this destination. Distinct from a destination with an empty nation set |
| `authz_unavailable` | **not a deny.** A broken PDP and a policy denial must never be the same line, because the operator's entire diagnosis is the difference between them |

### 8. Classification is fenced, and the fence fails closed

Slice 2 is the **releasability** axis and nothing else. The gate declares
that it evaluates that axis only, and **refuses any record carrying a
classification field it does not evaluate**, with reason
`classification_not_evaluated`.

The fence therefore fails closed: a producer that starts marking records
on an axis this gate cannot reason about gets refused, rather than having
its markings silently ignored while the record crosses on releasability
alone. The proto has no classification field today; `reserved 11`
(`policy_label`) is where such an axis would land, and this fence is what
keeps that day from being a silent one.

### 9. Failure is closed and loud

If the PDP cannot be reached at startup the process **exits non-zero**
rather than starting with no entitlement. A gate that starts and admits
nothing looks exactly like a gate correctly refusing everything, and that
ambiguity is the operator's whole problem.

### 10. The producer labels; fusion still refuses to default

`logistics-sim` now stamps `originator_nation` from its site's declared
nation and leaves `releasable_to` empty unless a scenario says otherwise.
Both keys are **absent** when the site declares no nation — not empty
strings, not a default.

The fusion service's existing refusal to default a label stays exactly as
it is. That refusal is what makes the floor visible: if nothing upstream
declared a nation, the record is unlabelled and the gate says so by name.

## Alignment declared (ADR-0038 C1 intake)

Two new vocabularies leave this slice, and both are declared rather than
implied:

- **The decision record's fields.** `decision_id`, `outcome`, `reason`,
  `record_class`, `destination`, `destination_nations`, `key`,
  `policy_version`, `corpus_version`, `detail`. These are **OpenDDIL-local
  and aligned to nothing published.** They mirror the Slice 1 read
  decision log's shape deliberately, so that one reader can read both logs
  without a translation step; that is an internal consistency claim, not a
  standards claim.
- **The refusal reason enum** in §7. Also OpenDDIL-local. It is *not* an
  access-control vocabulary from any published standard, and naming it as
  local is the point: a reason set that looked standard while being
  invented is the shape ADR-0041 warns about.

The **labels themselves** carry their alignment from Slice 1 and it is
unchanged: `originator_nation` is ISO-3166 alpha-3, and the
`originator_nation` / `releasable_to` pair is aligned to STANAG
4774/4778 label concepts, on the wire as `Provenance` fields 9 and 10.

## What was measured, against a prediction written first

The prediction was written into the plan and into the test as **literals**
before the gate ran, because a test that computes its expectation from the
data it is checking agrees with itself no matter what the code does.

Declared fleet: 14 assets — 8 ATL, 6 BDR. One ATL asset carries
`releasable_to: [BDR]`; every other `releasable_to` is `[]`.

**Predicted**, toward the ATL destination: admit 8, refuse 6, all six
`no_nation_overlap`.

**Measured** (`test_50_egress_gate_counts.py`, against the running gate
and a running PDP): admitted **8** of 14; refusals
`{no_nation_overlap: 6, unlabelled: 1, classification_not_evaluated: 1}`.
The two extra refusals are the red-check records, which were produced on
purpose:

- a proto record with an unset nation and an empty release array —
  the shape an unlabelled record actually has on the wire — refused
  `unlabelled`;
- a record carrying `classification: "S//NF"` **and** labels that would
  have passed the releasability axis outright — refused
  `classification_not_evaluated`, which is the fence doing the only job
  that distinguishes it from an unused branch.

The agreement test passes over **6 entitlements × 12 fixture rows** with
identical verdicts from both implementations, and was red-checked by
crippling the containment clause: it then correctly named the four rows
the two sides disagreed about.

Both tests were **red-checked, not merely run green.** A test only ever
observed passing is a test whose green means nothing.

## What this ADR does not decide

- **The real ALCS adapter and the C2's inbound format.** Contract A is
  defined against published status vocabulary and never against a
  particular consumer's inbound API. Nothing here assumes one.
- **Whether the gate's decision is final.** If a receiving C2 cannot carry
  `originator_nation` / `releasable_to` through, the gate's decision
  *becomes* final at our boundary, and Contract A's "translates, does not
  decide" has to say what the gate decides on that consumer's behalf.
  This is the first thing to establish with a real consumer, and it is a
  conversation rather than a design.
- **The classification axis.** Fenced, per §8.
- **Aggregates crossing the boundary.** §7 states the rule an aggregate
  falls under, and the agreement fixture exercises it; **no aggregate is
  on the guarded topic today**, so the rule is stated and untested by live
  data.
- **Multiple destinations.** One process per destination is the decision;
  how a deployment with many C2s is composed from that is not designed.
- **Mid-stream entitlement change.** The gate asks once and exits if the
  PDP goes away. Re-asking on a schedule, or being pushed a revocation,
  is unaddressed.

## Limits

- **Everything here was proven under compose, and compose is not the
  lab.** The measurement produced records directly onto the guarded topic
  from the same declaration the ingress mapping stamps from. That makes it
  a measurement **of the gate**, which is what was asked for — and it is
  explicitly *not* evidence that the ingest chain labels anything.
- **The compose PDP is a second copy of the chart's.** Its `version`,
  `opa` and `api.services.authorizer` blocks are the chart's verbatim, for
  the reason that a compose PDP answering differently would make every
  compose measurement a statement about compose. Two copies is still two
  copies, and nothing mechanical keeps them in step.
- **The PDP build in use logs no decisions.** `plugins` and
  `decision_logger` are documented and present in the published schema but
  rejected by this build. So each PEP's own log is the audit trail, and
  there is no second independent record beside it. That is a single point
  of truth where the design would prefer two.
- **The gate has never been severed from its PDP mid-stream.** §3's
  exit-rather-than-serve-stale behaviour is written and unit-tested; it
  has not been observed against a PDP that died under load.
- **`logistics-sim` does not feed the guarded topic.** Its labels were
  built and verified in-image, but its outputs are consumed by the
  projector and never reach the gate. Contract B's producer wiring is
  therefore **recorded as the next step, not delivered.**

## Where the findings went

Five things were found while building this, none of them about the gate
itself. They are recorded in `FOLLOW-UPS.md` under 2026-09-23 rather than
here, because this document's subject is a decision and theirs is a
defect. The one worth naming in an ADR is the first: **under compose,
every record on the stack was unlabelled**, and had been for as long as
the mount existed — a state indistinguishable from a fleet nobody ever
declared, and invisible precisely because unlabelled is a legal answer.
