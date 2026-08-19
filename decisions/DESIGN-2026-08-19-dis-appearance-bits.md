# Design — DIS entity appearance: the health source that was already there

**Date:** 2026-08-19 · **Read and design only; nothing built.** Commissioned
to settle whether the DIS path has any source for the operational-state
health axis, because the answer gates the logistics-sim tactical-damage
constraint set.

## The answer, and it corrects a registered gap

**A source exists, on Bronze, today — and the mapping discards it.**

| stage | file | behaviour |
|---|---|---|
| Stage 1 | `dis_ingestor.py:230` | `appearance_bits` extracted from `entityAppearance` and **published** |
| Stage 2 | `sim-dis-mapping.yaml` | **zero references.** Not read, not mapped, not commented |

ADR-0026's amendment registered this as *"no DIS source for the health
axis."* That was wrong in a specific and useful way: the correct statement
is **"a partial source has been arriving on `ingress-dis-raw` since the
sidecar was written, and Stage 2 never learned to read it."**

**And it is sharper than "unmapped": ADR-0026 SPECIFIED this mapping.** Its
adapter list, written 2026-05-27, says *`EntityState.appearance.power_plant_on`
→ `power_state`; `appearance.damage` / `firepower_kill` → `health_state`.*
The decision existed, the sidecar carried the data, and Stage 2 was never
written.

**A specified mapping that nobody built is indistinguishable, from the
outside, from a source that does not exist.** ADR-0026 then registered it as
the latter — citing its own unbuilt design as a missing feed. Nobody
contradicted anything: the ADR described intent, the gap described
observation, and neither could see that the difference between them was
implementation.

*Why the distinction matters more than a wording fix:* "no source" implies
an upstream ask — a producer must start sending something. "Present and
unmapped" is a change we can make alone, against data already in the topic,
with no producer conversation and no wire change. The work is smaller than
the gap it closes, and it has been available the whole time.

It also explains a measurement that looked like a producer problem: 14 of 14
lab assets carry `health_state IS NULL`. That is not the feed being silent.
**The feed has been speaking and the mapping has not been listening.**

## What the bits carry

DIS `entityAppearance` is a 32-bit field on the Entity State PDU. **Its
meaning is not global — it is interpreted per entity kind AND domain**, so
the same bit means different things for a land platform and an air platform.
That single fact drives the whole design below.

*Evidence class, stated per this corpus's convention:* the layout below is
**standard-derived and MUST be verified against the current SISO-REF-010 /
IEEE 1278.1 publication before it is relied on** — the same rule
`dis_entity_types.yaml` already imposes on itself. It is written here to
size the work, not to be copied into code unchecked.

For **Platform** entities (`kind = 1`), the only kind the ontology
recognises today, the fields relevant to the health axis:

| bits | field | values | axis relevance |
|---|---|---|---|
| 3-4 | **Damage** | 0 none, 1 slight, 2 moderate, 3 destroyed | **the primary health signal** |
| 1 | **Mobility kill** (land) / **Propulsion kill** (air, surface, subsurface) | 0 no, 1 yes | subsystem-specific impairment |
| 2 | **Firepower kill** | 0 no, 1 yes | **land only** — the bit is reused in other domains |
| 21 | **Power plant status** | 0 off, 1 on | maps to the *power* axis, not health |
| 22 | **State** | 0 active, 1 deactivated | entity has left play |

**The ontology covers `kind=1` only, across domains 1 (land) and 2 (air)** —
5 land entries and 6 air. So a first mapping needs exactly two domain
interpretations, not the full matrix.

**Note bit 2.** Firepower kill is land-specific, and other domains reuse that
position for an unrelated meaning. A mapping that decodes bit 2 without
branching on domain will assert firepower kills on aircraft. That is the
kind of defect that renders plausibly and is discovered late.

## Why this belongs in the ontology, not in Bloblang

The decode requires the entity's **kind and domain** to know what a bit
means. The mapping already resolves `platform_variant` through
`dis_entity_types.yaml` keyed by the entity-type tuple — **the same key
already carries kind and domain in its first two positions.**

So appearance decoding is the *same shape* as variant resolution: a lookup
against a curated, PR-reviewed, standards-cited table, changed by an
ontology PR rather than a code change (ADR-0016's discipline). Hardcoding a
bit layout in Bloblang would put a wire grammar in a mapping language, which
ADR-0030 exists to forbid; silently mis-decode every domain the layout does
not match; and require a mapping edit per domain, which is the coupling
ADR-0016 removed for variants and would reintroduce here.

**Sketch — an `appearance` block per kind/domain, not per entry.** The
existing table is keyed by the full 7-tuple, but appearance semantics vary
by `kind_domain` only, so repeating them per entry would be 11 copies of two
facts. A sibling map keyed by `kind_domain` is the honest shape:

```yaml
# ontology/dis_appearance.yaml  (SKETCH — not written)
appearance:
  "1_1":             # Platform / Land
    damage:          { bits: [3, 4], values: {0: NONE, 1: SLIGHT, 2: MODERATE, 3: DESTROYED} }
    mobility_kill:   { bit: 1 }
    firepower_kill:  { bit: 2 }
    power_plant:     { bit: 21 }
    deactivated:     { bit: 22 }
  "1_2":             # Platform / Air
    damage:          { bits: [3, 4], values: {0: NONE, 1: SLIGHT, 2: MODERATE, 3: DESTROYED} }
    propulsion_kill: { bit: 1 }
    # bit 2 is NOT firepower kill in this domain — deliberately absent
    power_plant:     { bit: 21 }
    deactivated:     { bit: 22 }
```

**Absence in that table is meaningful and must stay meaningful:** a domain
that does not declare `firepower_kill` has no such bit, and the mapping must
emit nothing rather than defaulting — clause 3 of the ADR-0026 convention,
applied to a lookup instead of an enum.

## Mapping sketch — damage to the axes

Bit extraction is arithmetic, and ADR-0013 bars arithmetic from the mapping.
Two placements are possible and the choice is a real decision:

| placement | for | against |
|---|---|---|
| **Stage 1** (sidecar decodes bits into named fields) | keeps math out of Bloblang; the sidecar already parses a wire grammar | sidecar must read the ontology, which it does not today |
| **Stage 2** (Bloblang masks bits via ontology table) | ontology stays the single source of interpretation | bit masking in a mapping is what ADR-0030 forbids |

**Recommendation: Stage 1.** The sidecar is already the component whose job
is "turn a wire grammar into named fields," and a bit-field is a wire
grammar. It publishes `damage: "MODERATE"`, `mobility_kill: true` alongside
the raw `appearance_bits` — raw retained, so Stage 1 does not become the
only place the truth exists.

The axis mapping is then pure selection, and it is **not** a free choice —
it is constrained by the ADR-0026 convention just ratified:

```
damage == DESTROYED   -> health_state = HEALTH_STATE_FAILED
damage == MODERATE    -> health_state = HEALTH_STATE_FAULT
damage == SLIGHT      -> health_state = HEALTH_STATE_DEGRADED
damage == NONE        -> health_state = HEALTH_STATE_NOMINAL   (a POSITIVE assertion, clause 4)
appearance absent, or domain unmapped -> health_state UNSET     (clauses 1-3)
power_plant == 0      -> power_state  = POWER_STATE_OFF
power_plant == 1      -> power_state  = POWER_STATE_ON
```

**`NONE -> NOMINAL` is the load-bearing line.** It would be the first place
in the system where `NOMINAL` is a *positive assertion derived from a source
that actually said so*, rather than a value reached by falling through every
other branch. Clause 4 asks for exactly that; this is what satisfying it
looks like.

## What this unblocks, and what it does not

**Unblocks:** the logistics-sim tactical-damage constraint set. The sim
already consumes `telemetry-latest-state` and constrains synthesis from
reported health — but DIS never populated health, so that correlation has
been **inert for every DIS asset**, and demo consistency has come from two
sims sharing a scenario rather than one constraining the other. Mapping
appearance converts that coincidence into a mechanism: *destroyed means not
healthy* stops being a rule someone must write into the sim and becomes a
fact arriving on the wire.

**Does not unblock, and must not be assumed:** whether the simulator in use
populates appearance at all. The bits are in the PDU spec; a given producer
may leave them zero. **Zero is indistinguishable from "no damage"** — bits
3-4 of `0` read as `NONE`, which is a positive claim of health. So a
producer that never sets appearance would, under the mapping above, assert
every entity healthy. That is absence-answering-as-nominal arriving in a new
place, and it is why the next step is a measurement rather than a build.

**The measurement that gates implementation:** count distinct
`appearance_bits` values on `ingress-dis-raw`. All-zero means the field is
unpopulated and the mapping would manufacture health out of silence. Any
variation means the producer is really setting it.

### MEASURED 2026-08-19 — the gate fires. Do not build the mapping yet.

**Source side.** `dis_sim.py:171` sets `pdu.entityAppearance = 0` as a
literal. The lab's only DIS producer never populates the field.

**Wire side**, sampled from `ingress-dis-raw` on the lab:

```
records sampled   : 3000
distinct entities : 8   (both edges: NORTHPO, CAPEVER, ATLAS, BEDROCK, SYLVAN)
appearance values : {0: 3000}
```

**Zero, universally.** So under the mapping designed above, bits 3-4 of `0`
decode as damage `NONE`, which maps to `HEALTH_STATE_NOMINAL` — a positive
assertion of health. **Every synthetic asset in the lab would be declared
healthy on the strength of a field its generator never sets.**

That is the defect the ADR-0026 amendment forbids, and building this mapping
today would commit it *while citing the amendment as authority*. The gate
existed for exactly this outcome and it fired on the first run.

**What must come first: a damage-emission control in `dis-sim`**, the
sibling of `AssetState.as_unclaimed()` just added to logistics-sim. Until
the generator can set appearance deliberately, the lab cannot exercise the
mapping *or* its guard — a red-check would be impossible, because no input
distinguishes "no damage" from "no claim".

**And the guard that must ship with the mapping, whenever it does:** an
all-zero appearance field is treated as **unpopulated, not as undamaged**.
The two are indistinguishable in the bits and must be distinguished by
something else — a producer allow-list, an explicit "this feed populates
appearance" declaration, or a non-zero sentinel bit. Choosing that mechanism
is part of the work and is **not** decided here.

### The zero-sentinel is valid only for DECLARED sources — required before build

**Recorded 2026-08-19; one paragraph, no build.** The power-plant sentinel
above (a claim-making entity is never all-zero) works for `dis-sim` **only
because we control the generator**. It does not generalise, and the reason
matters:

**The sentinel discriminates among entities that made *some* claim. It
cannot detect a feed-wide silence.** A third-party DIS producer that
legitimately never populates appearance is indistinguishable, on the wire,
from one that set every bit to zero — every entity reads *powered off,
undamaged*, and nothing in the bits says which situation you are in.

So the mapping requires a **per-source declaration**: *"this feed populates
appearance."* It is **overlay configuration**, and the asset-class ladder
applies verbatim:

1. the feed declares it (rare);
2. the overlay states it as a **deployment assumption with an author and a
   date** (the normal case);
3. otherwise the mapping **does not read the bits at all**, and the axis
   stays honestly `UNSPECIFIED`.

**Absent the declaration, the bits are not read.** That is the gate made
permanent rather than a one-time measurement — the measurement answered
*today's* question about *our* generator; the declaration answers it for
every source, including ones nobody has integrated yet.

*Note the shape.* This is `GD-12` again, one layer out: the wire cannot
express the difference between "damage: none" and "field not set", so the
distinction has to be **declared** somewhere rather than inferred from the
value. Fourth field type to need that, after `Quantity`, `ConsumableState`
and the operational-state enums. **The fourth instance is where a pattern
stops being a coincidence** — in all four, a wire that cannot distinguish
*absent* from *a legitimate value* forced the distinction to be declared
somewhere else, and in all four the cheap local answer was to read the value
and hope.

*Note what that gate protects against.* Without it, this design would close
a gap by introducing the exact defect the ADR-0026 amendment was written to
prevent — and it would do so while citing that amendment approvingly.

## What this did not establish

- **Bit layout is unverified against the publication.** Standard-derived,
  written to size the work; the ontology's curation rule requires a cited
  source before an entry lands.
- **Only `kind=1` was considered.** The ontology recognises no other kind
  (zero `kind=2` munition entries), so no munition appearance semantics were
  examined.
- **No producer behaviour was observed.** The gating measurement was not
  run; this is a source reading.
- **Non-platform domains** (surface, subsurface, space) were not detailed,
  since the ontology covers none.

## Related

- **ADR-0026 §Amendment** — the convention this mapping must obey; its
  registered gap is corrected above.
- ADR-0016 — variant resolution by ontology PR; the precedent for putting
  appearance semantics in a curated table.
- ADR-0030 — Stage 1 decodes grammars, Stage 2 maps structure; the argument
  for the sidecar placement.
- ADR-0013 — no arithmetic in mappings; why bit masking cannot live in
  Bloblang.
- **GD-12** — absence conventions; the all-zero hazard is its newest
  instance.
