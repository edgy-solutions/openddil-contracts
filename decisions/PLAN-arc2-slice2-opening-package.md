# Plan — Arc 2 Slice 2 opening package

**Date:** 2026-09-23 · **Status: PROPOSED. Not accepted.** Every rule below
is recorded so that it can be argued with; none of it is settled, and the
code written against it is written against a proposal, not a decision.
· **Method:** the rules in §2 were answered by the user on 2026-09-23 as
recommendations. The findings in §4 were verified by reading and executing.

`DESIGN-2026-09-06-interface-contracts.md` §5 closes with:

> **Egress gating.** Nothing crosses ungated, and the gate is Slice 2's own
> opening package — this one assumes it rather than specifying it.

That package was never written. This is it. It exists because Slice 2 could
not start without it: the corpus recorded a fence, two adversaries and three
forward notes, and no admit/refuse rule at all.

---

## 1. What Slice 2 is

ADR-0029's second gate. Slice 1 protects against the wrong **person** at the
read surface; Slice 2 protects against the wrong **destination** at the
outbound boundary. The ADR's own table states the asymmetry that makes this
the harder half:

- a read denial is recoverable — the operator sees less than they wanted;
- an egress leak is **durable and has no human in the loop** — it has
  already happened by the time anyone could look at it.

Slice 2's subject of enforcement is a link, not a seat.

---

## 2. The five rules

Answered 2026-09-23. Each is the user's to confirm; each is implemented as
proposed so that confirming or overturning it is a diff rather than a design
session.

### 2.1 A destination is a subject

A C2 is not a fourth attribute category. The framework already has subjects
with `nations`; **a system principal with `nations` is the same thing without
a person behind it.** The stand-in destination holds one nation, **ATL**,
because a single-nation destination is the discriminating case against a
fleet labelled in two nations.

*Consequence for the code:* `policy/releasability.rego` needs no change. It
is already subject-agnostic — it answers exactly "which nations may this
subject see" and its header forbids adding row logic. The destination is a
new row in `policy/users.yaml` and nothing else.

*Honesty point, recorded rather than solved:* every existing row in
`users.yaml` is keyed on an OIDC `sub`, and a system principal has no OIDC
`sub`. Its identifier is asserted by deployment configuration. That is a
weaker rung of the provenance ladder than the human rows, and the row says
so in place.

### 2.2 Egress is the read predicate, with the destination as subject

**One predicate, not two.** An ATL C2 sees what an ATL person sees,
*including ATL-authored readings with no onward release*, because anything
else says a nation cannot hand its own data to its own C2.

Writing a stricter egress rule would be a **second implementation of the
release rule**, and a second implementation is a second thing to keep true.

*Consequence, stated in advance so it is not read as a leak:* the ATL
stand-in admits most of the fleet. That is the correct prediction. See §3.

### 2.3 Classification is fenced, and the fence fails closed

Slice 2 is the **releasability** axis. `classification` remains fenced, as it
was in Slice 1.

The gate therefore **declares the axis it evaluates and refuses any record
carrying a classification field it does not evaluate.** A fence that silently
passes marked data is not a fence. Refusing is the only honest handling of a
marking whose meaning the gate has not been taught.

### 2.4 The producer labels

`originator_nation` comes from deployment configuration at the producing
site; `releasable_to` is empty unless the scenario says otherwise.

**Fusion's refusal to default a label stays.** A derived row carries what it
received and invents nothing. That refusal is what makes the unlabelled floor
visible instead of papering it over — see §4.1, where it is exactly what
made the floor measurable.

### 2.5 Enforcement form: compiled in-process, from the same source

ADR-0029's third Slice 2 forward note says per-message Topaz calls "will not
scale, and the fix is a compile step, not a cache", and that the compile step
is "worth designing before Slice 2 starts."

The gate therefore:

1. asks Topaz **once per destination**, not once per record — the same
   `data.openddil.releasability.decision` query the read path uses;
2. **compiles** the returned `allowed_nations` into an in-process record
   predicate;
3. is held to the read path by an **agreement test**: the SQL predicate the
   read PEP builds and the in-process predicate the gate compiles must return
   the same verdict for every row of a shared fixture.

The agreement test is the mechanism that keeps 2.2 true over time. Without
it, "one predicate" is a sentence in a document and two functions in a
repository.

---

## 3. What the gate admits and refuses, by class

Restated before measuring, per the dispatch.

The predicate, from ADR-0029 §4 and its 2026-09-08 addendum:

```
(originator_nation IS NOT NULL AND originator_nation IN (:nations))
  OR
(releasable_to IS NOT NULL AND releasable_to && ARRAY[:nations])
```

with `:nations` bound to the **destination's** nations.

| Class | Example from the declared fleet | ATL destination |
|---|---|---|
| authored by the destination's nation, no onward release | `originator_nation: ATL, releasable_to: []` | **ADMIT** — authorship clause |
| authored by the destination's nation, released onward | `originator_nation: ATL, releasable_to: [BDR]` | **ADMIT** — authorship clause |
| authored elsewhere, released to the destination | `originator_nation: BDR, releasable_to: [ATL]` | **ADMIT** — containment clause |
| authored elsewhere, no onward release | `originator_nation: BDR, releasable_to: []` | **REFUSE** — `no_nation_overlap` |
| aggregate, composed audience includes the destination | `originator_nation: NULL, releasable_to: [ATL, BDR]` | **ADMIT** — containment clause only; an aggregate claims no authorship |
| aggregate, composed audience empty | `originator_nation: NULL, releasable_to: []` | **REFUSE** — `no_nation_overlap`. An aggregate whose audience composed to nothing is releasable to nobody, and that is the intended reading of `[]`, not a bug |
| unlabelled | no `originator_nation`, no `releasable_to` | **REFUSE** — `unlabelled`. Deny-unlabeled, asserted at the gate and not inherited from the read path |
| carries a classification field | any `classification` present | **REFUSE** — `classification_not_evaluated`, §2.3 |
| destination unknown to the policy corpus | — | **REFUSE** — `destination_unknown`. Distinct from an empty nation set |
| PDP unreachable | — | **REFUSE** — `authz_unavailable`, and this is *not* a deny. A broken PDP and a policy denial must never be the same record in the log |

**Nothing is dropped silently.** Every refusal is one line naming the record,
the class it fell into, and the reason. A record that crosses is one line
too. The count of lines equals the count of records the gate saw; if it does
not, the gate has a bug rather than a policy.

---

## 4. Findings — verified 2026-09-23, before any code

These are the reasons the measurement in §5 could not simply be run.

### 4.1 The declared fleet is not labelled under compose

`openddil-demo/ontology/releasability.yaml` is the deployment's declaration
of national origin, and `dynamic-mappings/sim-dis-mapping.yaml` reads it at
ingress from `/ontology/releasability.yaml`.

Under **helm**, `/ontology` is an overlay: `contracts/ontology` first, then
`demo/ontology` on top (`templates/edge.yaml` and `hub.yaml`, `"overlay"
true`). `releasability.yaml` arrives from the second layer.

Under **compose**, `/ontology` is a single mount of
`../openddil-contracts/ontology`, which does not contain
`releasability.yaml`. The three `redpanda-connect-0{1,2,3}` services
therefore read a file that is not there, and **every record on the compose
stack is unlabelled.**

The gate would have refused 100% of the fleet for a reason nobody wanted —
the floor working because nothing is labelled, which is precisely the
self-satisfying outcome that file's own header warns about one layer down.
Compose is corrected to overlay the same file. **Ledger row opened.**

### 4.2 `releasability.yaml` names a consumer that does not exist

That file's `CONSUMED BY` block — kept, in its own words, so that "a reader
added without a line here is a reader nobody can find from the file it
depends on" — lists:

```
* openddil-logistics-sim  src/logistics_sim/releasability.py
```

No such file exists, and `originator_nation` occurs nowhere in that
repository. The list records an intention as though it were a dependency.
Slice 2 writes the file the list already named. **Ledger row opened.**

### 4.3 The label source is per-asset, and §2.4 says site

§2.4 says `originator_nation` comes "from the emitting site's nation, which
is deployment config". `releasability.yaml` is deployment config, but it is
**per-asset**, and it refuses a catch-all default on purpose.

These are reconciled rather than chosen between, and the reconciliation is
the part most worth arguing with:

- the **per-asset declaration wins** wherever it names the asset. It is the
  strongest rung available and the corpus already names logistics-sim as its
  consumer (§4.2);
- the file's own `default_originator_nation` is honoured when a deployment
  sets it — the file permits this explicitly for a deployment that "genuinely
  cannot know an origin" and "should set the default and be honest that it is
  one";
- a **site nation** (`LOGISTICS_SIM_SITE_NATION`) is the deployment's way of
  being that honest, and is **unset by default**. When unset, an undeclared
  asset gets no label and the completeness gate fails with that asset named,
  which is the intended outcome.

So §2.4 is implemented literally — the producer labels, from deployment
config, never from inference — at the finest granularity the deployment has
actually declared. **If the intent was a blanket site label overriding the
per-asset map, this is the paragraph to overturn.**

### 4.4 logistics-sim does not feed the topic the gate guards

Traced, because a label is worthless if it does not reach the boundary.

`openddil-logistics-sim` emits `asset-element-telemetry` and
`asset-element-inventory`. Neither is among the inputs of
`openddil-logistics-fusion-service`, which are `asset-telemetry-windows`,
`asset-cm-state`, `raw-sensor-stream`, `derived-sustainment` and
`asset-capability-snapshot`. Both of logistics-sim's topics are consumed by
`openddil-projector` alone, into Postgres.

`asset-logistics-status` — the topic the gate guards — is produced by fusion
from the *sensor* path, whose labels are stamped by the ingress mapping in
§4.1, not by logistics-sim.

**Consequence:** labelling logistics-sim is correct and was asked for, but it
does not by itself put a label in front of the gate. It labels the element
and inventory planes. The sensor path, once §4.1 is corrected, is what
supplies the gate. Both are done here; conflating them would have produced a
measurement that appeared to prove the wrong chain.

### 4.5 A per-asset registry nation can contradict a site nation

`openddil-stack/asset-registry-service` reads `originator_nation` and
`releasable_to` from inbound event provenance per asset. A site-level default
(§4.3) can therefore disagree with a per-asset label already held by the
registry for the same asset. Nothing today detects the disagreement.
**Ledger row opened**; not resolved here, because resolving it is a policy
question about which declaration wins, not a bug.

---

## 5. Predicted counts, before measurement

Declared fleet: 14 assets — 8 ATL (`dis:1:1:1000`–`1007`), 6 BDR
(`dis:2:1:1000`–`1005`). One ATL asset, `dis:1:1:1000`, carries
`releasable_to: [BDR]`; every other `releasable_to` is `[]`.

**Toward the ATL C2 stand-in:** admit 8, refuse 6, all six
`no_nation_overlap`. The eight admitted are the ATL fleet, seven of them by
the authorship clause alone.

**The three seats, for comparison** (same predicate, subject = person):

| Subject | nations | admitted |
|---|---|---|
| `operator.atlantia` | `[ATL]` | 8 |
| `operator.borduria` | `[BDR]` | 7 — six BDR by authorship, plus `dis:1:1:1000` by containment |
| `liaison.coalition` | `[ATL, BDR]` | 14 |

`operator.borduria`'s seventh is the only live exercise the containment
clause gets. Without it, every admission would come from the authorship
clause and half the predicate would be carried, untested and
indistinguishable from broken.

**Red-check:** a record whose class the gate must refuse — a BDR-authored
record with `releasable_to: []` — presented to the ATL destination, required
to be refused with reason `no_nation_overlap`; and a record carrying a
`classification` field, required to be refused with
`classification_not_evaluated`.

---

## 6. What this package deliberately does not decide

- **The real ALCS adapter and the C2's inbound format.** Contract A is
  defined against published status vocabulary and never against a C2's
  inbound API. Nothing here assumes one.
- **Whether the gate's decision is final.** Contract A says the per-consumer
  connector "translates, it does not decide". If a receiving C2 cannot carry
  `originator_nation` / `releasable_to` through, then the gate's decision
  *becomes* final at our boundary and Contract A has to say what the gate
  decides on that C2's behalf. This is the first thing to establish with a
  real consumer.
- **The classification axis.** Fenced, per §2.3, and the fence is where the
  next slice starts if a consumer needs markings OpenDDIL does not enumerate.
  The proto's `reserved 11` (`policy_label`) is where that would land.
- **Aggregates crossing the boundary.** §3 states the rule an aggregate falls
  under; no aggregate is on the guarded topic today, so the rule is stated
  and untested by live data.
