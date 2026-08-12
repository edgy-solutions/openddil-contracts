# Design — asset class is declared, not inferred

**Date:** 2026-08-11. **Status: DESIGN ONLY — nothing built, nothing
scheduled.** Recorded so the correction is not lost between now and whenever
the work is taken up.

---

## The correction

Asset class is currently **inferred** by the frontend/view layer from a
behavioural asymmetry: *an asset with a row in `asset_capability_state` is a
LAUNCHER; a munition-candidate variant without one is a MUNITION.*

The rule works, requires no producer to assert anything, and shipped with no
schema change. That combination reads as elegance. **It is the tell.**

**A classification that requires nobody to assert anything is deriving from
behaviour, and behaviour is deployment.** The rule does not encode a fact
about the world — it encodes a fact about how one feed publishes: *things
that report loadouts are launchers.* That correlates with a real physical
asymmetry (launchers have magazines; rounds in flight do not), which is
precisely why it feels principled. The correlation belongs to the source, not
to the domain.

### How it fails — all three are ordinary, none are exotic

| situation | classified as | why it is wrong |
|---|---|---|
| launcher whose feed has not emitted a snapshot yet (first boot, feed gap) | **MUNITION** | absence of evidence read as evidence of absence |
| producer that publishes stores for *all* platforms (several sim frameworks do) | **everything LAUNCHER** | the asymmetry the rule depends on simply is not there |
| dismounted / reloadable / externally-magazined systems | varies | the physical premise does not hold uniformly |

Every failure is **silent and plausible** — the classification is always
*some* class, never "unknown". That is the silent-absence family, arriving in
the ontology layer.

### It is the same finding as the capability-item vacuum, one layer up

Two weeks apart, two instances of one disease:

- **GD-10** — no canonical *item structure* existed, so the source's payload
  shape filled it de facto.
- **here** — no canonical *class property* exists, so the source's publishing
  behaviour fills it de facto.

Absent a declared canonical property, the source's behaviour becomes the
model by default. Nobody decides this; it simply happens, and it looks like
cleverness on the way in.

---

## The correct model

**`asset_class` is a declared Silver field.** OpenDDIL defines the taxonomy
from domain and open-standard vocabulary — per the schema-provenance policy,
the canonical shape derives from standards, and a feed's fields are input to
the *mapping*, never sources for the *model*.

Values: `SENSOR`, `LAUNCHER`, `MUNITION`, `PLATFORM`, `FACILITY`,
**`UNKNOWN`**. `UNKNOWN` is load-bearing, not a placeholder.

### The assignment ladder — overlay responsibility, in order of preference

1. **Producer declares it.** Best case; the feed carries a type that maps
   cleanly.
2. **Overlay maps it from *declared* source attributes.** Reading what the
   source *states*, not what it *does*. For DIS this is a lookup against an
   open standard — see below; this is the normal case, not the exception.
3. **Overlay applies a deployment-specific stated rule** — including,
   legitimately, *"in this deployment, capability-emitters are launchers."*
   Same rule as today. The difference is that it is a **declared local
   mapping with an author**, not a canonical inference, and no other
   deployment inherits it.
4. **`UNKNOWN`** — unmapped assets are *visibly* unknown. Never silently
   reclassified.

**The core never infers.** If the overlay did not say, OpenDDIL does not
know. Same discipline as deny-unlabelled and self-identifying mocks: absence
stays absence.

---

## Finding 1 — DIS already declares this (checked, not assumed)

**The DIS entity-type tuple's first field is the entity-kind discriminator.**
The ontology annotates it in its own comments — `kind=1 (Platform)` appears
three times in `ontology/dis_entity_types.yaml`.

Per SISO-REF-010 the kind axis separates Platform (1) from Munition (2) at
the top level — *[standard-derived; verify against the current SISO-REF-010
publication before relying on it, per that file's own curation rule].*

**So for DIS, class is a one-field lookup on a value the source declares.**
Not an inference. Ladder step 2 is available and authoritative, which makes
the capability-emitter rule a *proprietary-feed exception* rather than the
general mechanism.

**But the ontology currently recognises no munitions.** All 11 entries are
`kind=1`; there are **zero `kind=2`** entries. Verified:

```
kinds present in dis_entity_types.yaml: 1
```

Consequence: a fired round arriving as `kind=2` matches no entry, falls to
`_default`, and becomes `UNKNOWN` platform metadata — the failure mode §1 of
the provenance audit describes. **The DIS path cannot classify munitions
today because the ontology has never been asked to.**

That is good news for the fix: extending the ontology with munition-kind
entries is an ontology PR, which is exactly where ADR-0016 says variant
resolution changes belong.

**Note what this gap has meant in practice:** the DIS path has never been
*able* to classify a round. Every DIS-sourced munition to date has resolved
to `_default` and landed somewhere it should not have — silently, because
`_default` produces a value rather than a refusal.

**The gap is testable today, before it is closed.** The overlay's DIS
generator sets entity kind as the first element of a freely-specified tuple,
and the wire field is `uint32`, so a `kind=2` entity is a one-line addition.
That yields two guards for the price of one:

- **now** — a munition entity proves the unrecognised path is *visible*
  (resolves to UNKNOWN) rather than absorbed into a plausible class;
- **after the ontology extension** — the same entity proves the new entries
  actually resolve, on the day they land.

A golden-file case built from that entity would guard the coverage gap in
both directions. Worth doing when this is scheduled; not done here.

---

## Finding 2 — the mapping layer can already express this

No extension needed. `AssetIdentity` carries `platform_variant` (field 7),
documented as *"populated by the DIS ontology lookup in Bloblang"* — a
declared canonical value assigned by the mapping from an ontology lookup.
**`asset_class` is the identical shape**: same layer, same mechanism, same
ontology-PR discipline.

The proto change is purely additive: fields 1–5 are marked stable, "new
fields start at 6", and 6–10 are taken. `asset_class` is **field 11**. No
renumbering, no breaking change.

*If a future source needs class to depend on something the mapping layer
cannot express (a joined lookup rather than a field), that is a
**mapping-layer extension** — not a core compensation. The core's job is to
carry what was declared, not to make up for what the mapping could not say.*

---

## Finding 3 — migration sketch, preserving today's behaviour

Force Posture must not break. The sequence keeps it working throughout:

1. **Add the field.** `AssetIdentity.asset_class = 11`, plus the enum with
   `UNKNOWN` as zero-value. Nothing reads it yet. Purely additive.
2. **Extend the DIS ontology** with munition-kind entries so `kind=2` assets
   resolve rather than falling to `_default`. Ontology PR, domain reviewer,
   SISO-REF-010 citation per that file's curation rules.
3. **Overlays assign class.** The DIS overlay maps from entity kind (ladder
   step 2). The proprietary-feed overlay carries the **existing join rule,
   moved verbatim**, recorded as that deployment's stated assumption —
   naming the sim's publishing asymmetry it rests on, with an author and a
   date.
4. **Core reads the field.** The classifier view changes from *computing* a
   class to *reading* one, with `UNKNOWN` passed through visibly rather than
   defaulted into a class.
5. **Retire the inference.** Only once every live feed assigns class. Until
   then step 3's rule keeps behaviour identical — the same logic, relocated
   to where it is true.

**Nothing is deleted before its replacement carries the load**, and at no
point does Force Posture see a different answer than it does today.

### The one behaviour change that is the point

Today an unclassifiable asset becomes `MUNITION`. Afterwards it becomes
`UNKNOWN` and looks it. **That will surface assets nobody knew were being
mis-filed** — which is the fix working, not the fix breaking.

> **A count that rises when an instrument is fixed was always that high.**
>
> This is the **third** time a correctness fix here has made a
> previously-silent population visible: sensors with null positions, the
> buffer counter reading a consumer group that never existed, and now
> mis-filed asset classes. Each time the honest reading was identical — the
> system did not get worse, the instrument got truthful.
>
> Say this to whoever watches the UNKNOWN count jump, **before** they see it.
> Absent the sentence, a number going up reads as a regression, and the
> reasonable response to an apparent regression is to revert the fix that
> revealed it. That is the failure mode this note exists to prevent.

---

## Adjacency and the bundled ask

**Track with GD-10.** Same message family, same declared-vs-observed
question. The capability-item schema and the asset-class field are one
conversation about one feed; sequencing them together avoids negotiating
twice with the same people.

### A related defect found while checking this — `_default` that confabulates

The sting in the coverage gap is not that `_default` exists; it is that
**`_default` produces a value rather than a refusal.** A fallback yielding
`UNKNOWN` is honest. A fallback yielding a real-looking answer is a
confabulation mechanism with a config file.

Swept the DIS ontology's `_default` on 2026-08-11. Six of its seven fields
are honest — `platform_variant: UNKNOWN`, `platform_family: UNKNOWN`, a
nomenclature that literally says *"Unrecognized DIS entity type — requires
ontology curation"*, and three explicit `null`s. **One field breaks the
pattern:**

```yaml
cm_schema: "generic-v1"     # in the _default entry
```

`generic-v1` occurs in **exactly one place in the entire workspace** — that
line. Every other `cm_schema` value belongs to a recognised entry
(`ground-combat-vehicle-v1`, `rotary-wing-v1`, …). Nothing defines it,
nothing resolves it. An unrecognised entity is stamped with a CM schema that
does not exist, in a field whose six siblings correctly declare ignorance.

**Blast radius was zero** — `cm_schema` is declared but unconsumed, verified.
Latent, not live.

**FIXED 2026-08-11** (same session, deliberate exception to design-only): set
to `null`, like its siblings. The exception was taken because a *latent*
confabulation is worse than a live one — an active wrong value gets found
when something downstream misbehaves, whereas this one waits, and the first
person to wire CM-schema resolution inherits a field that reads as though it
was populated deliberately for years. The fix was smaller than the record of
the fix, and could not break anything, since nothing read the field.

**The follow-up sweep was also done** — see
`AUDIT-2026-08-11-fallback-honesty.md`. It found the population: **four
confabulating fallbacks across nine surfaces**, and two of them outrank this
one. The most consequential is live: a mapping fills absent fuel with `0.0`
*and always sets the unit*, which defeats fusion's own absence check and
presents an asset with no fuel telemetry as an asset with an empty tank.

---

**The upstream wire-contract ask should carry three questions, not two:**

1. Does the feed carry a durable **stockpile / capacity** figure? *(the
   Phase-3 blocker — there is no capacity today, only an absolute count)*
2. Does the feed emit **termination events** (HIT / MISS / FAILED)? *(the
   Phase-6 blocker)* — and frame it as the strong version: end of life is
   currently inferred from a track disappearing, which cannot distinguish
   success from miss, dud or self-destruct **and also fires on dropped
   packets, sim restarts and network gaps**. The ask is therefore not for
   better outcome attribution; it is for **the only signal that separates
   "an event occurred" from "the feed hiccuped"** — a request producers
   usually recognise as legitimate immediately.
3. Does the feed **declare asset class**, or an attribute from which class is
   derivable *by declaration*? *(this document)*

All three are the same question wearing different clothes: **what does the
source declare, versus what are we inferring from its behaviour?**

---

## Related

- `GENERALIZATION-DEBT.md` **GD-10** — the capability-item vacuum; sibling.
- `AUDIT-2026-08-09-schema-provenance.md` — discovery-is-not-derivation, the
  governing rule this design obeys.
- `PLAN-munitions-taxonomy-phases.md` — where the inferred classifier is
  currently recorded as the taxonomy's load-bearing idea; that entry needs
  amending when this lands.
- ADR-0016 — platform-variant resolution via ontology PR; the precedent this
  follows.
