# Audit — Silver schema provenance

**Date:** 2026-08-09
**Scope:** the Silver (canonical) schema — `proto/openddil/**` plus the
capability-snapshot path, which turns out not to be proto-defined at all.
**Method:** reading only. No code changed, nothing built.
**Anchor:** evidence cited by file and line throughout; every claim below is
recoverable to a source read on this date.

---

## Why provenance is worth a table

A canonical schema accumulates shapes from several places, and the places
differ in what they oblige us to. A field derived from a published standard
is anchored — its meaning is checkable against a document. A field that
arrived from a source system is anchored to *that system's* modelling
choices, which we do not control and may not be able to see. A field we
invented is anchored to nothing but our own judgement, which is fine as long
as we know that is what it is.

The audit sorts the schema into those classes so the third kind can be
recognised on sight.

**Classes used:**

| class | meaning |
|---|---|
| **open-standard-derived** | shape and vocabulary follow a published standard, cited in the proto |
| **intersection-derived** | shape is the common ground of several feeds; no single source owns it |
| **organic** | OpenDDIL invented it; anchored to our own judgement |
| **sim-ancestry** | shape follows simulation-domain conventions rather than a standard document |
| **source-shaped** | shape is a source system's, carried without decomposition |

---

## 1. The live question: the capability snapshot

**Question as posed:** is the capability structure still a mirror of a source
system's field hierarchy under a generic name?

**Answer: the question is moot in the form asked, and the real state is
different — there is no OpenDDIL-defined structure at all.**

Evidence:

- **No proto exists.** Nothing under `proto/openddil/**` defines a capability
  message. The fusion service says so directly: the snapshot is
  *"a JSON dict, not a proto"*
  (`openddil-logistics-fusion-service/src/fusion/rules.py:179`).
- **The payload is stored verbatim.** The projector target declares
  `capabilities jsonb NOT NULL DEFAULT '[]'`, commented as *"the per-store
  array stored verbatim as JSONB"*
  (`openddil-stack/schema/migrations/20260520010000_phase7_asset_capability_state.sql:3-7`).
- **The projector never inspects items.** It persists the envelope and passes
  the array through untouched
  (`openddil-projector/src/handlers/capability_state.py:46`).

So the shape divides cleanly:

| part | class | note |
|---|---|---|
| envelope — `asset_id`, `schema_version`, `mode`, `observed_at`, `provenance` | **organic** | OpenDDIL-defined, consistent with the rest of Silver |
| `capabilities[]` items | **source-shaped** | not modelled; carried opaquely |

**The item contract exists only as three consumer reads.** Everything known
about an item's shape is what code happens to reach for:

| field | read at | meaning in use |
|---|---|---|
| `capability_id` | `rules.py:386` | compound token: launcher asset id + munition type, joined (`openddil-demo/frontend/src/lib/munitionType.ts:6-9`) |
| `ammo` | `rules.py:382` | absolute count |
| `store_location` | `rules.py:387` | station identifier, fallback key |

**This is not the feared shape, and it is not obviously better.** "Mirrored
under a generic name" would at least be a *declared* structure with a
recorded field hierarchy. What exists instead is an undeclared one: the
source's hierarchy survives inside the JSONB, and our contract with it is
three `.get()` calls in one evaluator. A field the source renames breaks a
consumer with no schema check in between.

### The layered verdict

The question "is the open schema free of any particular integrator's
influence?" has three answers, and only the third is interesting.

| layer | verdict |
|---|---|
| **vocabulary** | **clean, verified.** No integrator-specific naming anywhere. The three field names in use — quantity, station, type-bearing identifier — are open domain vocabulary: stores and munition counts are DIS/AFSim concepts. |
| **declared structure** | **clean, but vacuously.** The feared shape — one integrator's field hierarchy enshrined in an open proto under a generic name — does not exist, because *no declared shape exists*. Nothing is imitated because nothing is stated. This satisfies the letter of the provenance policy. |
| **de facto contract** | **not corrupted, but dependent.** The only definition of the item shape that exists anywhere is whatever one deployment's mapping emits. Our code couples to it through three consumer reads. |

**Free from corruption is not free from definition.** No intellectual
property leaks and no foreign vocabulary appears — and yet the canonical
model is a vacuum, and a vacuum gets filled by whoever integrated first. A
second deployment mapping its data tomorrow would be mapping to a shape
reverse-engineered from consumer reads of the first deployment's output.

Dependence-by-vacuum is in one respect *worse* than a declared mirror: a
mirror is visible, reviewable, and fails loudly when the source moves. This
fails silently.

**The escalation fired on the trigger's reason rather than its letter, which
is the trigger working correctly.** The danger was never "a mirror exists" —
it was "stockpile counting built on a shape that is not ours." An undeclared
shape is that danger in stealth form.

**One genuine modelling gap, already documented in code:** the feed carries
an absolute count and *no per-store capacity*, so engagement-worthiness bands
on an absolute threshold rather than percent-remaining
(`rules.py:364-368`). Percent-of-capacity is unavailable, not merely unused.

**What is already right here, and should survive any redesign:** the fusion
evaluator stamps `ORIGIN_DERIVED` and holds `confidence = 0.0`, separating
the fed measurement (the count) from the OpenDDIL conclusion drawn on it
("can this asset still engage?") — the claims-vs-sources discipline applied
correctly (`rules.py:370-374`).

### Escalation — flagged, as instructed

The trigger was "flag before munitions stockpile work builds on that shape."
**It fires.** Not because the structure is mirrored, but because the reason
behind the trigger is fully engaged: stockpile logic would be built on a
payload with no schema, no ownership, and a de-facto contract of three
consumer reads. Any counting, aggregation or projection over stores inherits
that fragility and multiplies it.

**Recommendation: model the item before building on it.** Sketch only —
nothing built, per instruction.

> **The governing rule for that modelling — discovery is not derivation.**
>
> The item's full field set is discoverable: a deployment's own overlay
> carries the source-specific mapping artifacts, and reading them would
> enumerate what the feed actually contains. That is a legitimate and
> necessary **discovery** step — you cannot map what you have not seen.
>
> It is **not** a legitimate source for the canonical shape. Deriving the
> Silver message from a particular feed's field hierarchy reproduces exactly
> the condition this section flags, one level up and with a schema file to
> make it look deliberate. The result would be source-shaped and *declared*,
> which is harder to dislodge than source-shaped and undeclared.
>
> **The canonical shape derives from open standards**; a feed's fields are an
> input to the *mapping*, never to the model. Concretely: read the overlay to
> learn that a quantity, a station and a type exist; take the *names,
> structure and semantics* from the stores/munitions vocabulary the domain
> already publishes. Any field the feed carries that no standard covers is a
> decision to make deliberately and record — not a field to inherit by
> default.
>
> This is the difference between a canonical schema and a lowest-common
> transcription of whoever integrated first.

- A `MunitionStore` message with explicit fields: store/station identifier,
  munition type, quantity, and *capacity where the feed provides it* (with
  absence represented, not defaulted — the count/percent distinction above is
  a real fork).
- Munition type as its own field rather than a substring of a compound id.
  Parsing a type out of `capability_id` by prefix-stripping
  (`munitionType.ts:35-36`) is string surgery standing in for a field.
- Vocabulary from the domain rather than invented: **stores/station**
  language is already what the code uses and matches simulation and C2
  convention — **J3.7 weapon status**, **DIS munition-supply**, **AFSim
  stores**, and **S2000M** where stockpile semantics land. The existing words
  are good; they need a schema under them.
- Keep the derived/fed split exactly as it is today.
- **When the canonical shape lands, re-derive the sample overlay's authored
  wire-schema as an instance of it.** That fiction was written into the same
  vacuum this section describes, so it is currently a *second independent
  definition* of the item shape rather than an example of one. Left as-is it
  would quietly become a competing authority — two undeclared shapes instead
  of one.

**Fenced:** design work waits until scheduled. Today's deliverables are this
sketch and the prerequisite link (GD-10), nothing built.

---

## 2. Provenance table — Silver schema

`proto/openddil/telemetry/v1/telemetry.proto` (535 lines) is the bulk of
Silver. Classification from the messages and their in-file citations
(IEEE 1278, SISO-REF, WGS84/ECEF, STANAG, AFSim all appear; see §3 for what
does **not**).

| messages | class | anchor |
|---|---|---|
| `EcefPosition`, `Wgs84Position`, `LocalEnu`, `Position`, `Velocity`, `Attitude`, `EulerAngles`, `Quaternion`, `Vector3`, `KinematicState`, `DeadReckoning` | **open-standard-derived** | WGS84 geodesy; IEEE 1278.1 kinematics and dead-reckoning |
| `DisEntityType`, `DisEntityId` | **open-standard-derived** | SISO-REF-010 enumerations; the 7-tuple carried structurally |
| `PositionQuality` | **organic** | quality banding is ours |
| `SustainmentMetrics`, `ThermalMetrics`, `PowerMetrics`, `FluidMetrics`, `ConsumablesMetrics`, `ConsumableState`, `ComponentWearMetrics`, `WearState`, `HealthFlags` | **organic** | no standard cited — see §3 |
| `OperationalState` | **organic** | the three-axis model of ADR-0026 |
| `ValueProvenance`, `Provenance` | **organic** | OpenDDIL's own provenance model; deliberate and load-bearing |
| `AssetIdentity` | **intersection-derived** | spans DIS identity and platform-variant ontology |
| `EntityTelemetryEvent` | **organic** | envelope |
| capability snapshot | **source-shaped** | §1 |

**Reading:** the kinematic and identity half of Silver is anchored to
published standards *with citations in the file*. The sustainment and health
half is entirely organic. That is not a defect — it is where §3's opportunity
sits.

---

## 3. Alignment opportunities — the organic sustainment models

**Finding: no sustainment or health-monitoring standard is referenced
anywhere in the protos.** Searched for S5000F, ISO 13374, MIMOSA/OSA-CBM and
STANAG across `proto/` — the only hits are the kinematic/identity standards
above. The health models were built from first principles.

They are also the models most likely to be compared against a standard by an
external reviewer, because mature ones exist:

| our shape | candidate alignment | why it is a fit |
|---|---|---|
| `ComponentWearMetrics`, `WearState` | **ISO 13374** (condition-monitoring data processing: data acquisition → manipulation → state detection → health assessment → prognostics) | our raw-vs-derived split already mirrors its lower blocks; adopting its vocabulary would make the pipeline legible to a CBM audience without changing behaviour |
| `SustainmentMetrics`, `ConsumablesMetrics`, `ConsumableState` | **S5000F** (in-service data feedback) | S5000F exists to carry exactly this class of usage/consumption feedback between operator and support authority |
| `HealthFlags`, `OperationalState` | **ISO 13374 health assessment** + existing FMC/MC vocabulary | the three-axis model is richer than most; the opportunity is a documented *mapping*, not a replacement |
| provenance model | **none needed** | genuinely ours, and stronger than what the standards specify — keep it |

**Framing that matters:** these are alignment *opportunities*, not gaps. The
organic models were derived from the problem and work. The value of citing a
standard is external legibility — an accreditor or partner recognising the
shape — plus a vocabulary check that occasionally reveals a missing concept.
The realistic first step is a **mapping document**, not a schema change.

---

## 4. What this audit did not establish

Stated so no one inherits a stronger claim than the reading supports:

- **The capability item's full field set is unknown *here*.** Three fields
  are known because three consumers read them. The feed carries more, and it
  is discoverable — a deployment's own overlay holds the source-specific
  mapping artifacts that enumerate it. That reading was out of scope for this
  audit, and when it happens it is a **discovery** step feeding the mapping,
  not the model (see the governing rule in §1).
- **Source-specific Bloblang mappings were not read.** The projector docstring
  notes several feeds decomposed by "their respective Bloblang"
  (`capability_state.py:4-8`). Those mappings are where any real
  decomposition would live.
- **No claim about which sources are live.** This is a schema audit, not a
  deployment audit.
- **Standards fit is a first-pass judgement**, from the shape of our messages
  against what those standards are for. Nobody has read the standards against
  our fields clause by clause.

---

## Related

- ADR-0020 — prognostics derivation, the derived/fed boundary §1 relies on.
- ADR-0026 — the three-axis `OperationalState`.
- `PRINCIPLES.md` §*Claims vs. sources* — the discipline the capability
  evaluator already applies correctly.
- `GENERALIZATION-DEBT.md` **GD-10** — the finding of §1, recorded as a hard
  prerequisite of munitions stockpile work. **No munitions phase document
  exists in any OSS repo**, so that row is currently the prerequisite's only
  durable home; it should be cited from the phase plan when one is written.
- **S2000M** — the stockpile-semantics standard named in the §1 sketch
  alongside J3.7 / DIS munition-supply / AFSim stores, for when the canonical
  item schema is scheduled.
