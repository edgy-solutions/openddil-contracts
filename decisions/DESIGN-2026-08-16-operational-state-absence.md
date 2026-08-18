# Design — what should fusion say when an axis says nothing?

**Date:** 2026-08-16 · **Status: DESIGN. One half implemented, the other
half deliberately NOT — see §6.** Prompted by `AUDIT-2026-08-15-absence-conventions` F1.

## 1. The gap, scoped more narrowly than the audit stated

`_eval_operational_state` has no branch for `UNSPECIFIED` and none for
`NOMINAL`. Both fall through and emit no factor, and `_max_severity`
returns **`LOGISTICS_SEVERITY_OK`** for an empty factor list. So absence
does not merely fail to raise a flag — **it resolves to green.**

But the audit overstated the reach, and the correction matters for the
design:

**`_eval_staleness` already covers "we have heard nothing."** An asset with
no telemetry at all gets `stale_inputs` / `DEGRADED` — *"No telemetry
observed for this asset yet"*. It is not evaluated as OK.

So the real gap is exactly one case: **an asset that is reporting, freshly,
whose axes carry no claim.** Staleness sees a current message and stays
silent; the operational evaluator sees `UNSPECIFIED` and emits nothing.
*"No telemetry" is detected. "Telemetry that makes no claim" is not.*

## 2. Blast radius — measured, not imagined

Queried the lab on 2026-08-16:

```
power_state / health_state distribution   ->  (null) / (null) : 14 of 14
overall_severity distribution             ->  CRITICAL        : 14 of 14
assets that would change                  ->  0
```

**The entire fleet has unspecified axes, and every asset is already
CRITICAL from other factors.** Nothing on screen would move today.

Three consequences, and the third is the uncomfortable one:

1. The change is **safe** here — no count moves, no screen churn.
2. It is also **unverifiable** here. This deployment cannot demonstrate the
   fix working, because no asset's outcome depends on the axis. A test is
   the only available evidence, which makes ADR-0037 clause 3 the whole
   verification story.
3. **The defect is latent in this deployment and live in a healthy one.** A
   fleet whose other factors are quiet, with unspecified health, reads OK.
   That is the case nobody has, and the case the fix is for.

## 3. Why the obvious fix is wrong

*Emit a `ConstrainingFactor` for an unspecified axis.*

**A constraining factor asserts that something constrains the asset's
mission capability.** *"We do not know its health"* does not constrain the
asset — it constrains **our knowledge of** the asset. Putting it on the
severity axis borrows one axis's vocabulary for another, which is the
failure ADR-0026 exists to prevent, arriving at the evaluator instead of
the enum.

The practical consequence is worse than the theoretical one. DIS entity
state does not carry a health axis, so **every DIS-sourced asset would
carry a permanent factor forever**. ADR-0036 clause 1 already names what
that produces: *a permanent error emitted constantly trains readers to
filter it, exactly as a permanent zero trained them to trust it.* We would
convert a silent wrong answer into a loud ignored one and call it honesty.

## 4. Why the second option is also not obviously right

*A distinct non-factor record — a coverage or observed-axes field on
`AssetLogisticsStatus`.*

This is the shape that fits the meaning: it records what was observed
without claiming impairment. But it is a proto change whose consumers do
not exist, and this corpus has a name for that: the `cm_schema:
"generic-v1"` field that sat unread for years, honest-looking and
unresolvable. **A declared field nothing reads is the trap we most recently
closed**, and re-opening it deliberately needs a consumer named in the same
change.

## 5. The decision: STOP, and why that is the finding

**This is not unambiguous, so it is not being implemented.**

The three options are not a ranking with an obvious winner — they answer
different questions:

| option | says | cost |
|---|---|---|
| constraining factor | *this asset is impaired* — **false** | permanent noise on every DIS asset |
| coverage field | *this axis was never observed* — **true** | proto change with no consumer yet |
| presentation only | *render the unknown distinctly* | severity/rollups still count it green |

The presentation option deserves particular care: ADR-0035 class 2 already
requires "never observed" to render distinctly, and the raw
`OperationalState` block does reach the UI. But **`overall_severity` is
what rollups, counts and the tier aggregates consume**, and it would still
say OK. Fixing only the pixel leaves every aggregate wrong.

**The owning decision is ADR-0026's**, because the real question is whether
the orthogonal-axis model has a *fourth* thing to express — observed-ness —
or whether that belongs to provenance. That is an ADR, not an evaluator
patch, and the measured blast radius (§2) says there is no schedule
pressure forcing it now.

*What made this worth stopping for:* the missing branch is a two-line fix,
and two-line fixes are where a wrong model gets installed without review.

## 6. What WAS implemented — the unambiguous half

Checking `_eval_subsystems`, as instructed, found something worse and
clearer, in the evaluator the audit had praised for skipping `UNSPECIFIED`
correctly:

```python
sev = thresholds.subsystem_health_map.get(health.strip().upper(),
                                          ls.LOGISTICS_SEVERITY_UNSPECIFIED)
if sev in (ls.LOGISTICS_SEVERITY_UNSPECIFIED, ls.LOGISTICS_SEVERITY_OK):
    continue
```

**The skip is silent.** An asset that reports `POWERPLANT:THERMAL_LIMITED`
— a fault code we do not recognise — has it **discarded with no trace**:
no factor, no record, no log. The producer said something and the system
threw it away.

That is strictly worse than the operational-state case. There, nobody
claimed anything. Here, **a claim was made and destroyed.**

And the conflation is one line: `if sev in (UNSPECIFIED, OK)` buckets *"I
do not recognise this"* with *"this is fine."* The same two states this
project has spent a week separating everywhere else.

**Fix applied: a deduplicated WARNING naming the unmapped code.** Chosen
because it is the one action that cannot be wrong:

- it changes **no** factor, **no** severity, **no** count — the blast
  radius is zero by construction;
- it makes a discard **discoverable**, which is the precondition for
  deciding anything else about it;
- it is ADR-0036 clause 1's prescribed shape verbatim — *warn at WARNING,
  deduplicated, name the likely cause* — applied to a discard rather than
  a probe.

Deduplication matters here for the reason clause 1 gives: fault codes
arrive per message, so an unmapped code would otherwise log at telemetry
rate and be filtered within a day.

**This does not resolve the subsystem gap.** An unrecognised fault code is
still dropped from the factor list. It converts an invisible discard into a
visible one, so that the question *"should this be a factor?"* can be asked
against evidence — which is the same question §5 defers for the axes, now
with an instrument pointed at it.

## 7. Expectation note

Per the count-moved discipline, stated before anyone sees it:

- **No count will move.** Not today, not in this deployment. If someone
  checks whether this changed the numbers, the correct answer is *"it was
  not supposed to."*
- **A new WARNING will appear** in fusion logs wherever a producer emits a
  subsystem health string outside `subsystem_health_map`. That is **not a
  new fault** — it is a discard that was always happening, becoming
  visible. Its arrival rate is a measure of *vocabulary drift between
  producer and consumer*, and it belongs in the GD-12 conversation.
- **If the WARNING never appears**, that is information too: it means every
  producer's vocabulary is currently mapped, and the skip has been inert.

## 8. What this did not establish

- **Whether any producer actually emits unmapped codes.** Source reading
  only; the lab was not observed for the new warning.
- **Whether the UI already distinguishes unspecified axes.** ADR-0035 class
  2 requires it; not checked. IH-adjacent and unswept.
- **The `NOMINAL` question.** `NOMINAL` and `UNSPECIFIED` currently share a
  code path. If the axes gain a coverage treatment, `NOMINAL` needs to stop
  being *"fell through everything"* and become an explicit positive.
- **Any other evaluator's silent skips.** Only the two named were read.

## Related

- `AUDIT-2026-08-15-absence-conventions.md` F1 — the finding this designs
  against, and whose scope §1 narrows.
- ADR-0026 — owns the axes; §5 says the decision is its.
- ADR-0036 clauses 1-2 — absence never rendered as nominal; the dedup'd
  warning shape used in §6.
- ADR-0035 class 2 — never-observed rendering, the presentation half.
- **GD-12** — absence conventions; §7's warning is an instrument for it.
