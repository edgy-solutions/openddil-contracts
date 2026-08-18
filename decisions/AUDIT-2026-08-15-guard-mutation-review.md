# Audit — do our recent guards' red-checks model the defect?

**Date:** 2026-08-15 · **Method:** reading, plus re-running four mutations ·
**Fixes applied: none.** ADR-0037 clause 3 gained a correction on 2026-08-15:

> *a red run proves something only if the injected fault **models the
> defect**; a green run means either the guard is weak **or the mutation was
> wrong**, and those are not distinguishable without looking.*

That correction **postdates almost every guard in this table**. This pass
applies it backward. **The unknowns are the finding**, not the yeses.

## The table

| Guard | Injected fault when red-checked | Models the defect? |
|---|---|---|
| Golden case `unrecognised-mode` (`sample-sensor-mapping`) | Reinstated `_ => "HEALTH_STATE_NOMINAL"` on the health axis | **Yes** — the injection *is* the original construction, verbatim |
| Index check 1 — IDs ↔ rows | Deleted a row (`UD-7`); separately renamed a row's ID to a number no register uses | **Yes** — both real drift shapes: never-indexed, and renamed-at-home |
| Index check 2 — documents indexed | Broke `PRINCIPLES.md`'s link in `README.md` | **Yes** — models a document added and never listed, the case that found eleven |
| Index check 3 — status agreement | Flipped index status in **both** register shapes (prose `VE-8`, table `GD-08`) | **Yes** — models `IH-5`/`IH-6` exactly, the drift that actually occurred |
| Index check 4 — token presence | Deleted a `Status:` line from a home | **Yes** — models a row added without a token |
| Checker scope derivation | Added a fake `RC-1` register to `ADR-0039` | **Yes** — models the reported gap precisely: a register in a *new* ADR |
| `python-checks` summariser — red path | Broke one assertion | **Yes** — models an ordinary test failure |
| `python-checks` summariser — no-run path | Illegal identifier → collection error | **Yes** — models VE-8's actual defect (pytest aborts before any test runs) |
| `test_every_per_asset_handler_emits_origin_provenance` | **Re-checked in this pass** — see below | **Yes**, now verified |
| C4 badge test (`valueBasis.test.ts`) | Guard clause swapped for a truthiness test | **No — the mutation was wrong.** Already recorded in ADR-0037; the fault that models it is keying the lookup by string names |
| Chart acceptance checks | — | **No guard exists.** See F2 |
| Wire-shape guards (`test_persistence_model.py`, `munitionType.ts`, `edge_assignment.py`) | — | **Unknown.** See F3 |

---

## F1 — a guard I repaired today had never been checked against its own purpose

`test_every_per_asset_handler_emits_origin_provenance` was fixed earlier
today: it had been failing since the `edge_assignment` refactor, and the fix
made it green. **Green was all I established.** Its stated purpose — *"if a
handler stops emitting these, a flat-topology assumption has hardened"* — was
never re-tested against a handler that stops emitting.

Re-checked in this pass. Two attempts, and the first is the more useful:

1. **Invalid mutation.** Replacing the call expression produced a
   `SyntaxError` → collection error → red. **That red proves nothing**: the
   suite never ran. A guard that "fails" because the file will not parse has
   told you about your edit, not about the guard.
2. **Valid mutation.** `resolve_origin_or_derive` returning `{}` — a handler
   that stops emitting origin provenance — fails **exactly** that test and
   nothing else (`1 failed, 16 passed`), then restores clean at 63.

So the answer is **yes**, but it was *not known* until this pass, and a
repaired test is precisely where the assumption hides: fixing a red test to
green feels like verification, and it establishes only that the test passes
under *current* behaviour.

**The generalizable half:** *making a failing guard pass is not the same as
confirming it still guards.* The two look identical in a commit.

## F2 — "chart acceptance checks" are not a persisted guard

Searched `openddil-helm`: the only scripts are `build-bundle.sh` and
`publish-chart.sh`. Neither asserts chart content.

The checks this project remembers as chart guards were **one-off
verifications**, not artifacts:

- the *19 objects / 18 separators* arithmetic that caught the loop-boundary
  `---` defect — run once, in a session, never persisted;
- the `sizeLimit` change (0.1.46) — verified by rendering with the flags on
  and off, which is a **measured pair** for a change, not a guard against
  regression.

**Nothing would fail today if either defect were reintroduced.** That is a
gap in coverage rather than a gap in verification, and it is the more
serious of the two: an unverified guard can be checked, a non-existent one
cannot. `VE-4` already registers *chart self-description is checked by
hand*; this is the same hole, wider than that row states.

## F3 — three wire-shape guards, provenance of their red-checks unknown

`test_persistence_model.py`, `munitionType.ts` and `edge_assignment.py`
carry wire-shape assertions. **Whether any was ever run against an injected
fault is not recorded anywhere**, and the commits that introduced them were
not read in this pass.

Recorded as unknown rather than assumed either way. *Absence of a recorded
red-check is not evidence there was none* — but it is exactly the state
clause 3 says a claim may not be built on.

---

## What this pass established, and what it did not

- **Nine guards have a red-check that models its defect**, one of which was
  only established today (F1).
- **One is known not to** (C4 badge), already recorded and unfixed.
- **One does not exist** (F2) despite being remembered as a guard.
- **Three are unknown** (F3) and would each take a few minutes to settle.
- **Not swept:** every guard older than two weeks, the golden suite's other
  six cases (only `unrecognised-mode` was checked; the rest were verified
  as *unchanged*, which is a different claim), and all frontend tests other
  than `valueBasis`.
- **No fixes applied**, per the box.

**The base rate is better than expected and the distribution is the point:**
every guard written *after* the clause-3 correction has a defect-modelling
mutation, and every gap is in something written before it or remembered
rather than built.

## Related

- ADR-0037 clause 3 — the rule, and the C4 instance that earned the
  correction.
- `PRINCIPLES.md` §*A guard is not evidence until it has been seen to fail*
  and its limiting case §*a verification that includes its own subject…*
- **VE-4** — chart self-description checked by hand; F2 widens it.

---

## Update 2026-08-16 — the three unknowns are settled

Each was given a mutation modelling its own defect. **Two guard; one was
never a guard.**

| Guard | Mutation | Result |
|---|---|---|
| `test_persistence_model.py` (cm-service) | Dropped `lifecycle` from `record_to_proto` — silent field loss on the way back to the wire | **Red.** `test_round_trip_preserves_full_state` fails, and only it |
| `edge_assignment.py` (projector) | Discarded the strategy result so every lookup falls back | **Red.** `test_resolve_for_uses_strategy_then_fallback` fails, and only it |
| `munitionType.ts` (frontend) | — | **No guard exists.** See F4 |

Both reds name exactly one test and restore clean (67 / 63 passed), which is
the property that distinguishes a guard from a tripwire: it should fail *for
its own reason*, not take the suite with it.

## F4 — `munitionType.ts` has no test at all

It was carried in the original table as a *wire-shape guard whose red-check
was unknown*. That framing was wrong: **there is nothing to red-check.**
`src/lib/__tests__/` holds nine test files and none imports it, and no test
anywhere in `src/` references it.

It is not unused code. `extractMunitionType` and `displayMunitionType` are
imported by **four** components — `HqDigitalTwin`, `MunitionsInventory`,
`MunitionsLoadoutCard`, `useMunitionsStockpile` — so it is parsing
producer-supplied strings on four operator-facing surfaces with no coverage.

*Worth separating from the obvious reading:* this is not "someone forgot a
test." **The unknown was mis-typed as a verification gap when it was a
coverage gap**, and the two need different responses — one is answered by
running a mutation, the other by writing the test that the mutation would
have needed. An audit that asks *"was this red-checked?"* cannot see the
difference, because both answer "no evidence found".

**Fix shape, not applied:** the same treatment `operationalStatePills.test.ts`
already gives its enum — pin every input class the parser claims to handle,
including the unrecognised one, which is where this file's family of defects
has landed all week.

## The revised distribution

- **Eleven** guards with a defect-modelling red-check (was nine).
- **One** known-no (C4 badge), unchanged.
- **Two** that do not exist: the chart acceptance checks (**F2 — now
  built**, `check-chart-render.sh`) and `munitionType.ts` (**F4 — open**).
- **Zero** unknowns remaining.

The pattern holds and sharpens: **every gap was something remembered as a
guard rather than something built as one.** Not one guard that actually
existed turned out to be weak.
