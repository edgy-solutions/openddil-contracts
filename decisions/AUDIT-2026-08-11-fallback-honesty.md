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
| **F1** | `sim-a-mapping.yaml:105-106` | absent fuel → `0.0` **with unit always set** | ✗ **answers — LIVE, highest consequence** |
| **F2** | `sim-a-mapping.yaml:114-115` | absent rounds/capacity → `0` | ✗ answers — same shape as F1 |
| **F3** | `sample-sensor-mapping.yaml:99,114,121` | unrecognised mode → `POWER_STATE_ON` / `FUNCTIONAL_MODE_ACTIVE` / `HEALTH_STATE_NOMINAL` | ✗ answers — reference specimen, so it propagates |
| **F4** | `dis_entity_types.yaml` `_default` | `cm_schema: "generic-v1"` | ✗ answered — **fixed in this commit** |
| F5 | `dis_entity_types.yaml` `_default` | `platform_variant`/`platform_family`: `UNKNOWN`; nomenclature says "Unrecognized"; 3 × `null` | ✓ refuses |
| F6 | `platform_variant_aliases.yaml` | no `_default`; unaliased variants pass through unchanged | ✓ passes through |
| F7 | `asset_identity_aliases.yaml`, `platform_reference.yaml` | no fallback branch at all | ✓ n/a |
| F8 | `sim-dis-mapping.yaml:36` | unmapped force id → `FORCE_UNKNOWN` | ✓ refuses |
| F9 | `sample-sensor-mapping.yaml:151` | unparseable nation → `"UNKNOWN"` | ✓ refuses |

**Base rate: 4 confabulating of 9 surfaces.** The DIS `_default` alone was
six-sevenths honest, which is exactly why its one dishonest field read as
deliberate.

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
- **Egress mappings were not swept** (`dynamic-mappings/egress/`).
- **Projector and fusion handlers were not swept** for their own defaults —
  only fusion's fuel and inventory absence checks were read, and only far
  enough to establish F1.
- **No claim about runtime frequency.** Whether any live asset currently omits
  fuel data is a deployment question; this is a source reading.
- **F3's blast radius is unmeasured** — how often an unrecognised mode string
  actually arrives is unknown.

## Related

- `PRINCIPLES.md` §*A probe must fail distinguishably from its own zero* —
  the same rule at the instrument layer; F1 is its mapping-layer twin.
- `DESIGN-2026-08-11-declared-asset-class.md` — where F4 was found.
- ADR-0037 — verification evidence as deliverable; this is a finding
  document under clause 1.
- ADR-0030 — designates `sample-sensor-mapping.yaml` as the reference
  specimen, which is why F3 propagates.
