# Audit — do our fallbacks refuse, or do they answer?

**Date:** 2026-08-11 · **Method:** reading only, plus one one-line fix noted
below · **Anchor:** every finding cited to file and line as of this date.

## The question

A lookup or mapping that meets an input it does not recognise has two honest
options and one dishonest one:

- **refuse** — `UNKNOWN`, `null`, absent
- **pass through** — carry the source value unchanged and let a downstream
  drift check flag it
- **answer** — emit a plausible, real-looking value ✗

The third is the dangerous one, and it is dangerous in a specific way: **a
fallback that manufactures a value is indistinguishable from a successful
lookup.** Nothing downstream can tell "we recognised this" from "we made
something up", because both arrive as data of the same shape.

Prompted by finding one instance while checking the DIS coverage gap. This
pass converts *"we found one"* into *"we know the population"*.

## Scope

Every lookup table and every mapping fallback in the mapping layer, in both
the OSS defaults and the sample overlay:

- 4 ontology tables in `openddil-contracts/ontology/`
- 2 ontology tables in the sample overlay
- 3 Bloblang mappings (`sim-dis`, `sample-sensor`, `sim-a`)

Not covered: private overlays (not visible here), egress mappings, and the
projector/fusion layers — see *Did not establish*.

---

## Findings

| # | site | fallback | verdict |
|---|---|---|---|
| **F1** | `sim-a-mapping.yaml:105-106` | absent fuel → `0.0` **with unit always set** | ✗ answered — **FIXED `efef7a6`** |
| **F2** | `sim-a-mapping.yaml:114-115` | absent rounds → `0` | ✗ answered — **FIXED `efef7a6`**, and narrower than stated below |
| **F3** | `sample-sensor-mapping.yaml:99,114,121` | unrecognised mode → `POWER_STATE_ON` / `FUNCTIONAL_MODE_ACTIVE` / `HEALTH_STATE_NOMINAL` | ✗ answered — **FIXED `90cbaf6`** |
| **F4** | `dis_entity_types.yaml` `_default` | `cm_schema: "generic-v1"` | ✗ answered — **FIXED, this commit** |
| F5 | `dis_entity_types.yaml` `_default` | `platform_variant`/`platform_family`: `UNKNOWN`; nomenclature says "Unrecognized"; 3 × `null` | ✓ refuses |
| F6 | `platform_variant_aliases.yaml` | no `_default`; unaliased variants pass through unchanged | ✓ passes through |
| F7 | `asset_identity_aliases.yaml`, `platform_reference.yaml` | no fallback branch at all | ✓ n/a |
| F8 | `sim-dis-mapping.yaml:36` | unmapped force id → `FORCE_UNKNOWN` | ✓ refuses |
| F9 | `sample-sensor-mapping.yaml:151` | unparseable nation → `"UNKNOWN"` | ✓ refuses |

**Base rate: 4 confabulating of 9 surfaces** — revised to **5 of 10** once the
F3 fix surfaced the activity booleans, which this sweep had passed over. The
DIS `_default` alone was six-sevenths honest, which is exactly why its one
dishonest field read as deliberate.

*Note the revision's provenance: the fifth surface was found by **fixing**,
not by **looking**.* Reading the block to change it forced attention onto
every branch; reading it to audit it did not. A sweep is a weaker instrument
than a rewrite, and a base rate produced by sweeping should be quoted as a
floor.

---

## F1 — the one that matters, and it is live

```yaml
root.sustainment.fluids.fuel_remaining.value = $src.fuel.main_tank.or(0.0)
root.sustainment.fluids.fuel_remaining.unit  = "gal_us"      # unconditional
```

Fusion implements an absence check, correctly:

```python
if not fuel.unit and fuel.value == 0.0:
    return None  # field unset
```

It requires **both** an empty unit and a zero value. The mapping sets the
unit unconditionally, so the check can never fire for this source.

**Net effect: an asset whose feed omits fuel data is presented as an asset
with an empty tank**, and fusion evaluates it as a real constraining factor
rather than declining to judge.

**The mapping's absence-filling defeats the downstream's absence-respecting.**
Fusion did the right thing and the mapping made it unreachable — which is
worse than neither doing it, because the code reads as though absence is
handled.

F2 is the same construction on rounds and capacity.

**Not fixed here.** Changing `.or(0.0)` to leave the field unset changes
fusion's output for real assets — a behaviour change in a mapping, not a
comment fix, and it belongs to whoever owns the deployment. The
recommendation is: **omit the field rather than defaulting it**, and let
fusion's existing check do the job it was written for.

*A private overlay derived from this specimen very likely carries the same
construction. Worth checking there first — this file is the public twin.*

### Fixed 2026-08-12 (`efef7a6`) — and F2 above is overstated

Authorised and landed. Two things the fix established that this audit had
wrong or had not looked at:

**F2 is not "the same construction" as F1.** The two `.or(0)` one line apart
looked identical and were not:

- `quantity_capacity` — `.or(0)` is **correct and load-bearing**. Fusion's
  `_eval_ammo` skips any slot with `quantity_capacity == 0`, so zero is
  already this field's declared *not-evaluable* sentinel. Kept deliberately.
- `quantity_remaining` — `.or(0)` was the confabulation, and only in the
  case the audit did not separate: **with a capacity present**, a missing
  round count gives `0/N = 0%`, which fusion bands `CRITICAL`. A slot with
  *no* ammunition telemetry was reported as a slot that is *out* of
  ammunition, at the evaluator's highest severity.

Reading the two calls as one finding would have produced the wrong fix —
removing the capacity default would have *disabled* the sentinel that makes
absence work. **The population-audit rule cuts both ways: the surrounding
instances are where the worst case hides, and also where the false positive
does.**

**proto3 optionality constrains the fix.** Neither `Quantity` nor
`ConsumableState` declares `optional`, so absent and zero are identical on
the wire. Omitting a `uint32` therefore *cannot* express absence — it decodes
as `0`, the value at issue. The fix had to find the level that can:

- **fuel** — deleting the whole `Quantity` decodes as `unit="" value=0.0`,
  which is exactly the pair fusion already tests. The check simply becomes
  reachable; no downstream change.
- **rounds** — map-key absence *is* expressible, so a slot with no round
  count is dropped from the map entirely.

**Verified by execution, not by reading.** Both expressions were run over six
inputs. Absent fuel omits the Quantity; absent round count drops the slot.
Critically, a **genuine `0.0` tank keeps its unit** and a **genuine `0` round
count is retained** — real empty states still raise factors. The change
separates *absent* from *zero*; it does not suppress zeros. That distinction
is the entire fix, and it is the one thing worth re-checking if anyone
revisits this.

## F3 — a residual class is not the same as an unrecognised input

```
power_state:     match this.mode { … _ => "POWER_STATE_ON" }
functional_mode: match this.mode { … _ => "FUNCTIONAL_MODE_ACTIVE" }
health_state:    match this.mode { … _ => "HEALTH_STATE_NOMINAL" }
```

A catch-all is legitimate when it names a **residual class** — "everything
not explicitly off/starting/stopping is on" is a real modelling decision, and
the mapping documents it well.

It stops being legitimate when the input is one the mapping has **never
seen**. A source that adds a mode string, or sends a typo, yields *powered
on, active, and nominal* — a healthy asset, asserted. `HEALTH_STATE_NOMINAL`
for an unknown state is a **safety-relevant false negative**: the system
claims health it has no basis for.

This is the specimen ADR-0030 designates as the reference for adapter
authors, so the construction propagates to every mapping written from it.
**Recommended shape:** enumerate the known-good values explicitly and let
anything else fall to `UNSPECIFIED` / `UNKNOWN` on the health axis in
particular. Not changed here — it alters fixture behaviour and the golden
files that pin it.

### Fixed 2026-08-12 (`90cbaf6`) — and the feared golden churn did not happen

The catch-alls were not removed, they were **emptied**: all ten modes the
source schema declares are now enumerated explicitly, so only genuinely
unrecognised input reaches the final branch.

**The concern that deferred this fix turned out to be unfounded, and
measurably so.** Re-blessing all seven cases left the six pre-existing
goldens **byte-identical** — `git status` reported only the new case
directory. Behaviour for every declared mode is provably unchanged, which
converts "this will change what we see" from an argument into a settled
question. *Worth generalising: the cost of a fix and the cost of the fix's
worst imaginable form are different numbers, and only one of them was
measured before deferring.*

A **fifth surface** the original sweep missed: the two activity booleans
carried the same `_ => true` construction, so an unrecognised mode also
asserted the sensor was actively receiving *and* transmitting. A bool has no
`UNSPECIFIED`, and `false` is not a refusal — it asserts *"not receiving"*,
equally unfounded. Those now **delete the field**; absent means not claimed.
The sweep found this only because the fix required reading every branch in
the block, not because the audit looked for it.

New golden case `unrecognised-mode` pins the honest failure, and was
**verified as a guard rather than assumed to be one**: reintroducing a single
catch-all leaves all six declared-mode cases passing and fails only that one.
A future "simplification" back to `_ =>` is caught by exactly one test, which
is the reason it exists.

*Harness portability note, incidental:* `run.sh` maps `uname -s` for
linux/darwin only, so it fetches a nonexistent binary under Git Bash on
Windows (`mingw64_nt-…`). CI is unaffected (ubuntu) and the suite runs under
WSL. Not fixed — recorded so the next person does not debug it twice.

---

## The rule this suggests

**A fallback answers only where it can name the class it is answering for.**

- A *residual class* fallback is fine: it says "everything else is X" and X is
  a real category, chosen deliberately.
- An *unrecognised input* fallback must refuse: `UNKNOWN`, `null`, or absent.

The two are easy to conflate because they are the same syntax — `_ =>` and
`.or(…)` serve both. The distinguishing question is whether the author could
**name what falls into the branch**. If the answer is "anything, including
things that do not exist yet", it is not a residual class.

Corollary, from F1: **filling an absence upstream destroys a downstream's
ability to detect it.** A mapping that defaults is making a judgement on
behalf of every consumer that will ever read the field, including consumers
that had explicitly handled the absent case.

---

## What this audit did not establish

- **Private overlays were not read** — not visible from here. Given F1/F2 live
  in the public twin they were derived from, that is the first place to look.
  **Carried to the exchange list** rather than left as a remark, because a
  finding whose only home is a *did-not-establish* bullet is a finding that
  expires. The public fixes do **not** propagate on their own: an overlay
  authored by copying this file holds its own copy of the construction, and
  nothing in this repository can reach it.

  *The check is one question, not a review:* does any mapping there set a
  `Quantity.unit` unconditionally, or `.or(0)` a count that a capacity is
  paired with? Both are greppable.
- **Egress mappings were not swept** (`dynamic-mappings/egress/`).
- **Projector and fusion handlers were not swept** for their own defaults —
  only fusion's fuel and inventory absence checks were read, and only far
  enough to establish F1.
- **No claim about runtime frequency.** Whether any live asset currently omits
  fuel data is a deployment question; this is a source reading.
- **F3's blast radius is unmeasured** — how often an unrecognised mode string
  actually arrives is unknown.

### The follow-up this audit earned but did not perform

**Enumerate fusion's absence conventions, then verify each mapping can
satisfy them.** F1 was found from the mapping side — *this default looks
wrong* — and the fusion check was read only far enough to confirm it. That
ordering is backwards, and it is why F2's capacity default was nearly
mis-fixed.

The correct direction: for every evaluator, ask **what does this code treat
as "do not judge", and can every mapping feeding it actually produce that
value?** Two conventions are already known and they are not the same shape —
`not unit and value == 0.0` for `Quantity`, `quantity_capacity == 0` for
`ConsumableState` — and neither is written down anywhere but in the
evaluator's own body.

**An absence convention known only to the consumer is a contract with one
signatory.** Every producer has to rediscover it, and rediscovering it by
reading Python is how it gets defeated by a mapping author who never saw the
check. The output of that sweep should be a *stated* convention per field
type, not a per-mapping fix list.

## Related

- `PRINCIPLES.md` §*A probe must fail distinguishably from its own zero* —
  the same rule at the instrument layer; F1 is its mapping-layer twin.
- `DESIGN-2026-08-11-declared-asset-class.md` — where F4 was found.
- ADR-0037 — verification evidence as deliverable; this is a finding
  document under clause 1.
- ADR-0030 — designates `sample-sensor-mapping.yaml` as the reference
  specimen, which is why F3 propagates.
