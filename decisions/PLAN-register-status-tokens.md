# Plan — declared status tokens on register rows

**Date:** 2026-08-15 · **Status: EXECUTED 2026-08-15.** All 38 rows carry a
token; checks 3 and 4 are live in `check-decision-indexes.sh` and CI. Kept
rather than deleted — the record of why the heuristic was rejected is the
useful part, and the grammar below is the reference for every row added
from now on.

> ### Acceptance criterion, and the thing not to over-read
>
> **A green status check means the index AGREES with its home. It does not
> mean either is true.** The script prints that sentence on every clean run,
> deliberately, so the distinction survives a hurried reader.
>
> The only pass that touched reality was step 1 — reading all 38 blocks to
> determine each status from the home document rather than copying the
> index's view. That pass **re-established the home as authority**, which
> mattered because the index had already been wrong once (`IH-5`/`IH-6`).
> Nothing in CI can repeat it, and nothing in CI claims to.

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

## Steps — all executed 2026-08-15

1. ✅ **Token on all 38 rows**, each status read from its home block rather
   than copied from `FOLLOW-UPS.md`. Result: 33 `open`, 3 `fixed 2026-08-12`
   (`IH-5`, `IH-6`, `AE-1`), 1 `fixed 2026-08-08` (`GD-09`), 1 `in-arc Arc 1`
   (`GD-08`).
2. ✅ **Checks 3 and 4 in `check-decision-indexes.sh`** — exact string
   comparison over two extractors (GD table column; prose `Status:` line),
   no window, nothing to tune.
3. ✅ **Verified by making each fail**: a prose-register disagreement, a GD
   table disagreement, a deleted token, and two simultaneous disagreements.
   Each names the specific row and exits 1; the tree was restored clean
   after each.
4. ✅ Check 4 shipped with 3, not after — see the acceptance note above.

### Two things that went wrong, kept because they are the useful part

**The token's anchor was structurally wrong on the first attempt.** Inserting
*after* each bolded heading split sentences wherever prose continued on the
heading's closing line — `UD-1` and `IH-5` both broke mid-clause. Reverted
and re-anchored **above** the heading, where nothing can be split, then
confirmed by diff that the change is **purely additive**: no pre-existing
line altered anywhere in four documents. *A "mechanical" edit across 26
prose blocks is only mechanical if the anchor holds for every block shape,
and headings that wrap are a different shape.*

**`grep -P` is unavailable in this environment's locale**, so the first
implementation of checks 3–4 emitted a `-P supports only unibyte and UTF-8
locales` error **on every line** while still reporting failures — noise that
looked like the check working. Replaced with a single `awk` pass doing exact
field comparison, which is both portable and simpler than what it replaced.

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
