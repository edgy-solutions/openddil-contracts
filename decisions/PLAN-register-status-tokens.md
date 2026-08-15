# Plan — declared status tokens on register rows

**Date:** 2026-08-15 · **Status: SCHEDULED, boxed, not started.** Mechanical
work with a known shape and a known size. Boxed rather than left as a
register row because **it has a decay term**: every row added before the
tokens exist is another row to retrofit.

## The problem, stated once

A register row's **status** — open, fixed, parked — exists only as prose
inside its definition block. Nothing declares it, so anything that needs it
must *reconstruct* it: read the paragraph, or pattern-match for a `FIXED`
marker and hope the block is short enough.

That reconstruction was attempted and **provably does not work**. Windowing
from any mention gives false positives; tightening to definition sites gives
false negatives, because register blocks vary in length and **no context
window is correct for all of them**. Detail in `AUDIT`-adjacent notes and
`PRINCIPLES.md` §*A check tuned until it passes*.

The consequence is live, not theoretical: `FOLLOW-UPS.md` shipped marking
`IH-5`/`IH-6` open **three days after they were fixed** in a parallel
session, and no command in the repository could have caught it.

**This is the declared-vs-inferred family, fourth instance, in our own
tooling** — after `GD-11`, `GD-12` and `X-4`. The fix is the same one those
demand: *declare the property; do not derive it from a correlate that mostly
works.*

## The change

One token on each register row's definition line, immediately after the
subject:

```
**GD-12 — Absence conventions are declared only in the consumer.**
`Status: open`
```

**Grammar — deliberately minimal.** A parser that needs a spec is a second
thing to keep correct:

| token | meaning |
|---|---|
| `Status: open` | outstanding |
| `Status: fixed YYYY-MM-DD` | resolved; date required |
| `Status: parked <reason-ref>` | deliberately not being worked |
| `Status: in-arc <arc>` | being addressed by scheduled work |

Rules: exactly one per definition block, on its own line, first match wins.
`fixed` **requires** a date — a fix with no date is the same
unrecoverable-tense problem the anchor rule exists to prevent.

## Scope

**38 rows** across five registers as of 2026-08-15 — `GD-01..12`,
`UD-1..7`, `VE-1..7`, `IH-1..6`, `AE-1..6`. Homes:
`GENERALIZATION-DEBT.md`, `ADR-0036`, `ADR-0037`, `ADR-0035`, `ADR-0038`.

`GD` rows already carry a status **column** in their table; those convert
mechanically and are the easy third. The other four registers are prose
blocks and need the token added by reading each one.

**Out of scope:** the `C-1..C-7` constraints (standing constraints, not
follow-ups, and they have no status axis), and `X-1..X-8` in the exchange
ledger (already a table with a status column; revisit only if a check ever
needs to consume it).

## Steps

1. **Add the token to all 38 rows**, reading each block to determine its
   current status rather than copying `FOLLOW-UPS.md`'s view. *The index is
   a pointer and has already been wrong once; the home document is the
   authority and this is the pass that re-establishes it.*
2. **Extend `check-decision-indexes.sh`** with check 3: for every row, the
   index's status must equal the home's token. Exact string comparison — no
   window, no heuristic.
3. **Verify by making it fail** — flip one token, confirm the specific row
   is named and the exit code is 1, restore. Per ADR-0037 clause 3.
4. **Add a fourth check**: every register ID *has* a token. Without it, a
   new row with no token is invisible to check 3 — absence answering as
   agreement, which is the whole silent-absence family and would be an
   embarrassing way to reintroduce it here.

## Cost, and what makes it worth a box

**Roughly an hour**, most of it step 1's read-each-block pass. Steps 2–4 are
small because the comparison is exact once the data is declared.

Three things it buys, in order of durability:

1. **Deletes a heuristic permanently.** Nobody re-attempts the regex, or
   worse, ships a tuned one.
2. **Unblocks CI check 3**, the only drift class currently uncovered — and
   the one that has actually bitten.
3. **Removes the retrofit tax.** The cost grows with every row added; it is
   at 38 now and only goes up.

## What this does not do

- **Does not verify a status is *correct*** — only that the index agrees
  with the home. Both could be wrong together, and step 1 is the only pass
  that looks at reality. A green check 3 means *consistent*, not *true*, and
  the script should say so where it prints.
- **Does not cover prose follow-ups** in audits and plans; those still have
  no IDs by deliberate choice (`FOLLOW-UPS.md` §What this index does not
  cover).
- **Does not touch other repositories.** Registers elsewhere, if any exist,
  are unsurveyed.

## Related

- `PRINCIPLES.md` §*A check tuned until it passes is a check whose green
  means nothing* — why the heuristic was rejected rather than improved.
- `PRINCIPLES.md` §*Indexes drift where the work is not* — why the other two
  checks are in CI.
- **GD-11**, **GD-12**, **X-4** — the declared-vs-inferred siblings.
- ADR-0037 clause 3 — the guard-seen-red requirement binding step 3.
