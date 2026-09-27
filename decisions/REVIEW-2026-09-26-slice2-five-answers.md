# Review — the five answers in `PLAN-arc2-slice2-opening-package.md`

**Verdict: four accepted as written. One amended, and the amendment is a diff,
not a design session.**

The amended one is **2.1**, and only in its *registry*. Its predicate is right
and stays.

---

## 2.2 egress is the read predicate with the destination as subject — **accepted**

The load-bearing sentence is that a stricter egress rule would be a second
implementation of the release rule. Two implementations of one rule diverge, and
the direction they diverge in is the dangerous one: the copy that is *stricter
today* is the copy nobody re-tests, so the day it is looser than the read gate
it releases records the read gate would have refused, and the drift is invisible
because both sides pass their own tests.

The prediction that the ATL stand-in admits most of the fleet is also right and
is the correct thing to predict out loud. A gate that refuses almost nothing
proves it is wired but proves nothing about its discrimination; **the 6 BDR
assets minus the one declared releasable are what make the count meaningful**,
so the demonstrable number is 9 of 14 admitted to ATL (8 ATL + 1 shared), not
"most".

## 2.3 classification is fenced and fails closed — **accepted, and it is the strongest of the five**

"The gate declares the axis it evaluates and refuses any record carrying a
classification field it does not evaluate" is the only one of the five that
protects against a *future* mistake rather than a present one. The failure it
forecloses is a record arriving later with a classification the gate silently
ignores while reporting an allow — which is `ADR-0035`'s class 2 in the one place
it would matter most.

## 2.4 the producer labels — **accepted**

`originator_nation` from deployment config at the producing site, `releasable_to`
empty unless the scenario says otherwise, and fusion's refusal to default a
label stays. The third clause is the one to keep hardest: a defaulted label is
indistinguishable from an asserted one downstream, and the gate's `unlabelled`
refusal reason only exists if nothing upstream invents a label to avoid it.

## 2.5 enforcement compiled in-process from the same source — **accepted, with one check named**

Ask Topaz once per destination, compile `allowed_nations` into an in-process
predicate, hold it to the read path with an agreement test over a shared fixture.
Correct: a per-record Topaz call on an egress path is a latency budget nobody
measured and a failure mode (`authz_unavailable`) on every record instead of once.

The named check: a compiled predicate is a **cached authorization decision**, so
it has a staleness question the read path does not have. When the destination's
nations change in `users.yaml`, the read gate reflects it on the next request and
the compiled predicate does not until something recompiles. That is not an
objection — it is the one property of 2.5 that needs a stated lifetime rather
than an implied one, and the agreement test will not catch it because both sides
of the test read the same fresh fixture.

---

## 2.1 a destination is a subject — **predicate accepted, registry amended**

Accepted: a destination *is* a subject with `nations`, `releasability.rego` needs
no change, and the stand-in holds one nation (**ATL**). The plan's own honesty
note is the right one — every existing row is keyed on an OIDC `sub` and a system
principal has none, so its identifier is asserted by deployment configuration.

**Amended:** "a new row in `policy/users.yaml` and nothing else" puts a machine
destination in the read gate's own subject table, where it becomes
indistinguishable from a person. The specific failure is not hypothetical and not
about tidiness:

> A row in `users.yaml` is a row the **login** path resolves. The destination's
> key is asserted by deployment config rather than issued by the IdP, so if a
> token ever presents that `sub` — a test IdP, a reused fixture, a
> misconfiguration — it authenticates as the destination and inherits its
> nations. The destination exists precisely to have broad read scope, so the one
> principal you least want loginable is the one sitting in the login table.

The amendment:

* a separate **`policy/destinations.yaml`**, same shape, same `nations` field, so
  `releasability.rego` still needs no change — the predicate is unchanged, which
  is the point;
* **each gate loads only its own registry**: the read path loads `users.yaml`,
  the egress path loads `destinations.yaml`. Neither can resolve the other's
  principals, so the login path cannot see a destination at all;
* an explicit **disjointness check** between the two key spaces, failing the
  build if a key appears in both. A shared key is the whole failure mode above,
  and it is one set intersection to rule out permanently.

This keeps 2.2 intact: one predicate, two subject registries. What it refuses is
one *table*, not one predicate — the conflation 2.2 correctly forbids is of the
rule, and this separates the roster. **The split is by key issuer, not by kind of
thing: `users.yaml` holds subjects whose key is issued by the IdP, and
`destinations.yaml` holds subjects whose key is asserted by deployment
configuration** — which is why the disjointness check is the whole safeguard and
not a tidiness rule, since a key appearing in both files is a config-asserted
identity that the login path would then resolve.

---

## What this unblocks

The pane can be built. The only thing the amendment changes for the pane is
where the destination row is written and which file the egress gate loads; the
`allowed_nations` compile in 2.5, the refusal reason enum, and the admit/refuse
table in §3 are untouched.

## The count to carry into the pane's first prediction — **8 of 14, not 9**

An earlier draft of this section carried **9**. Reconciling it against
`RECORDING-READINESS.md` §C before predicting is what caught the error. §C's label
rows, measured in the region store on 2026-09-19 and re-measured unchanged on
2026-09-26 at revision 51:

| partition | assets |
|---|---|
| `ATL` | 7 |
| `ATL,BDR` | 1 |
| `BDR` | 6 |

and §C's own summation by subject entitlement: an ATL subject is served
`ATL` + `ATL,BDR` = **8**.

Re-measured 2026-09-27 directly against the hub registry at revision 51, which
also settles which way the one mixed row points:

| `originator_nation` | `releasable_to` | assets | ATL destination |
|---|---|---|---|
| `ATL` | `{}` | 7 | **ADMIT** — authorship clause |
| `ATL` | `{BDR}` | 1 | **ADMIT** — authorship clause |
| `BDR` | `{}` | 6 | **REFUSE** — `no_nation_overlap` |

**The error was a double count.** "8 Atlantian plus the single asset declared
releasable to Borduria" counts that asset twice: it is `ATL`-authored *and*
released onward, so it is the 8th of the 8, not a 9th beside them. There are only
7 pure-`ATL` assets. The prediction is therefore **8 admitted, 6 refused
`no_nation_overlap`** — the refusal count moves too, 5 → 6.

**This was already measured, and the 9 contradicted it.** ADR-0043's
measured-against-prediction section states the fleet in the form that makes the
double count obvious — *"14 assets — 8 ATL, 6 BDR. One ATL asset carries
`releasable_to: [BDR]`"* — and records **predicted admit 8, refuse 6, all six
`no_nation_overlap`**, then **measured admitted 8 of 14** by
`test_50_egress_gate_counts.py` against a running gate and PDP. (Its refusal
tally also carries `unlabelled: 1` and `classification_not_evaluated: 1`; those
are red-check records produced on purpose and are not among the 14.) So three
independent sources agree on 8 — §C's entitlement summation, the live registry,
and a passing test with its expectation written as a literal beforehand. The 9 was
not an open question; it was a regression against a recorded measurement.

That 8 is also the same 8 §C serves to an ATL *person*, which is the arithmetic
2.2 requires: one predicate means an ATL destination and an ATL person land on the
same number. A pane showing 9 would not be a rounding disagreement — it would be
the destination seeing one record more than the person does.

**What the corrected count still does not cover.** There is no `BDR` / `{ATL}` row
anywhere in the declared fleet, so every one of the 8 admits is granted by the
**authorship** clause and the **containment** clause admits nothing on fleet data.
A pane reading 8 therefore does not exercise containment — 8 is what a gate with a
broken containment clause would also show. Containment is covered, but somewhere
else: ADR-0043's agreement test runs 6 entitlements × 12 **fixture** rows and was
red-checked by crippling the containment clause, which then correctly named the
four disagreeing rows. That is the right division of labour and worth stating so
nobody reads the pane's 8 as covering both clauses. If containment is ever wanted
on fleet data, it needs a record authored elsewhere and released to ATL, which
this fleet does not contain; §4.5's per-asset-versus-site contradiction is the
obvious place to source one.

Three readings, kept distinct: **8** is the prediction; **9** means the count was
taken from the superseded arithmetic above; **14** means the gate is not in the
path at all.
