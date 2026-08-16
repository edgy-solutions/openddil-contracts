# Audit — how absence is expressed, and whether anyone can express it

**Date:** 2026-08-15 · **Scope:** `GD-12`. Every evaluator in
`openddil-logistics-fusion-service/src/fusion/rules.py`, every field type
they read, and the producers that feed them. **Reading only; no fixes.**

## The question

proto3 gives OpenDDIL's scalars no `optional`, so **absent and zero are
identical on the wire**. Every consumer wanting to distinguish *"no data"*
from *"a reading of zero"* must therefore invent a sentinel out of the
fields it has. Two were known going in — `Quantity` and `ConsumableState` —
and neither is written anywhere but inside the evaluator that uses it.

Three questions, per **GD-12**: what is the **full population**; can a
producer **actually satisfy** each convention; and what does proto3 permit
at all.

## The population — eight conventions, six shapes

| # | Shape | Convention | Site | Producible? |
|---|---|---|---|---|
| **C1** | `Quantity` | unset ⟺ `value == 0.0` **and** `unit == ""` | `_eval_fuel`, `_quantity_to_pint` (so also `_eval_wear`, `_eval_mtbf`) | **Now yes** — was **structurally impossible** until `efef7a6` |
| **C2** | `ConsumableState` | not evaluable ⟺ `quantity_capacity == 0` | `_eval_ammo` | Yes |
| **C3** | `Timestamp` | unset ⟺ `seconds == 0` and `nanos == 0` | `_eval_staleness` | **No producer can reach it** — see below |
| **C4** | JSONB item | absent ⟺ key missing **or** non-numeric | `_eval_inventory` | Yes (not proto) |
| **C5** | enum `LogisticsSeverity` | `UNSPECIFIED` ⇒ skip | `_eval_subsystems` | Yes |
| **C6** | enum `PowerState` / `HealthState` | **NONE** | `_eval_operational_state` | — **see F1** |
| **C7** | message presence | `is None` on `FusionInputs` | every evaluator | Python-side, pre-proto |
| **C8** | repeated / map | empty ⇒ `return []` | `_eval_inventory`, `_eval_ammo` | Yes |

Six distinct shapes, **no two using the same mechanism**, and not one of
them stated outside the function that implements it.

---

## F1 — the operational-state axes have no absence convention at all

**This is the finding.** `_eval_operational_state` branches on `POWER_STATE_
OFF / SHUTTING_DOWN / MAINTENANCE` and `HEALTH_STATE_FAILED / FAULT /
DEGRADED`. There is **no branch for `UNSPECIFIED`**, and none for `NOMINAL`
either — both fall through every condition and emit **zero factors**.

So at the factor layer:

```
HEALTH_STATE_NOMINAL      → no factor
HEALTH_STATE_UNSPECIFIED  → no factor      ← identical
```

**An asset that has told us nothing about its health is evaluated exactly
like an asset that has told us it is fine.** That is the silent-absence
family in its original form, sitting in the evaluator whose entire subject
is condition.

### It is an omission, not a decision — the codebase already knows the pattern

`_eval_subsystems`, forty lines earlier, does the right thing:

```python
sev = thresholds.subsystem_health_map.get(health.strip().upper(),
                                          ls.LOGISTICS_SEVERITY_UNSPECIFIED)
if sev in (ls.LOGISTICS_SEVERITY_UNSPECIFIED, …):
    continue
```

An unrecognised subsystem-health string resolves to `UNSPECIFIED` and is
**skipped rather than scored**. The concept is present, applied on one axis
and absent on the adjacent one.

### Staleness does not cover it, and this is the part worth being precise about

`_eval_staleness` catches an asset that **stops reporting**. It cannot catch
an asset that **reports, and says nothing** — a message with
`HEALTH_STATE_UNSPECIFIED` is a fresh message, so staleness stays silent
while the health axis contributes nothing.

> **The gap is exactly: "no telemetry" is detected; "telemetry that makes no
> claim" is not.**

### And a fix from three days ago now lands here

`90cbaf6` changed the reference mapping so an unrecognised sensor mode
yields `HEALTH_STATE_UNSPECIFIED` instead of `NOMINAL` — the point being
that the system must not assert health it has no basis for.

**That honest refusal arrives at a consumer that cannot tell it from an
assertion of health.** The Silver record is now truthful and the evaluated
outcome is unchanged.

*This is F1-of-the-earlier-audit's twin, and the more general form.* There,
a consumer's absence check existed and the producer made it
**unsatisfiable**. Here, the producer emits a correct refusal and the
consumer **has no check to satisfy**. Both end identically: *absence
presenting as nominal, with the honest half of the system fully intact.*
**Fixing a producer does not make a consumer honest**, and neither side's
correctness is visible from the other.

---

## F2 — C3 is a convention no current producer can trigger

`_eval_staleness` treats `seconds == 0 and nanos == 0` as *"producer didn't
set sample_time; can't judge staleness"* and returns `None`.

Both OSS mappings assign it **unconditionally from a source field**:

```
root.provenance.sample_time = this.reported_at     # sample-sensor
root.provenance.sample_time = $src.timestamp       # sim-a
```

If that source field is absent, the Bloblang assignment **errors and the
message goes to the DLQ** — it does not arrive with an unset timestamp. So
for every producer visible here, **C3's guard is unreachable**.

That is not a defect: it is a defensive check against producers this
repository cannot see, and it costs nothing. It is recorded because
*unreachable* and *satisfied* look identical in a coverage report, and
because C1 spent months in the same state while being **load-bearing** —
which is how F1 of `AUDIT-2026-08-11` happened.

---

## F3 — what proto3 permits, per shape

Absence is only expressible where the schema leaves room for it:

| Shape | Can absence be expressed? | Mechanism |
|---|---|---|
| `Quantity` | **Yes, by luck** | `unit` is a string; `""` is a usable discriminator that a `double` alone could not provide |
| `ConsumableState` scalars | **No** | bare `uint32`; absent decodes as `0`. Only **map-key absence** expresses "nothing said about this slot" |
| `Timestamp` | Yes | message field — `HasField` is available, though the code uses the zero-check instead |
| enums | **No** | zero value *is* `UNSPECIFIED`; distinguishable from other values, **not** from "never set" |
| repeated / map | Yes | empty is unambiguous |
| JSONB | Yes | key presence is real |

**Two of six shapes cannot express absence in the field itself**, which is
why the conventions differ: they are not stylistic variation, they are each
the best available trick for that shape. That also means **no single rule
can be stated for all of them** — the resolution has to be per-shape, which
is a stronger argument for writing them down, not a weaker one.

---

## What follows (recommended; nothing done here)

1. **State the conventions where both sides can cite them** — in the proto,
   next to the type. `Quantity` should carry, in a comment, that an empty
   unit with a zero value means *unset*; `ConsumableState` that a zero
   capacity means *not evaluable* and that a slot with nothing to say is
   **omitted from the map**. Today a producer must read Python to learn a
   wire contract.
2. **Decide the operational-state axes explicitly** (F1). Either
   `UNSPECIFIED` earns a factor — *"health not reported"*, most likely
   `DEGRADED`-or-lower with `ORIGIN_DERIVED` — or it is documented as
   deliberately unscored. **Silence is currently the answer by default, and
   nobody chose it.** ADR-0026 is the owning decision.
3. **Do not unify the conventions.** Two shapes cannot express absence at
   all; a single rule would have to be the weakest of them.

## What this audit did not establish

- **Runtime frequency.** Whether any live asset currently emits
  `HEALTH_STATE_UNSPECIFIED` is a deployment question. This is a source
  reading; the lab was not queried for it.
- **Non-OSS producers.** Private overlays were not read (**X-5**), so
  "producible?" answers cover the two public mappings and the DIS path only.
- **Consumers other than fusion.** The projector, the UI and egress make
  their own absence decisions and were **not swept**. F1 concerns the
  factor layer alone — the raw `OperationalState` block still reaches the UI,
  where ADR-0035's class-2 rules apply independently and were not checked.
- **Whether C6 has ever mattered in practice.** No claim is made that a
  mis-evaluation has occurred, only that the code cannot distinguish the
  cases.

## Related

- `GENERALIZATION-DEBT.md` **GD-12** — this audit is its survey.
- `AUDIT-2026-08-11-fallback-honesty.md` — F1 there is the producer-side
  twin of F1 here.
- ADR-0026 — owns the operational-state axes.
- ADR-0036 clause 1–2 — *absence is never rendered as nominal*, stated as an
  obligation on the producer; F1 is the same obligation unmet on the
  **consumer** side.
