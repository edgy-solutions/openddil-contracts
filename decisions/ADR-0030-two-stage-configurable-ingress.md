# ADR-0030 — Two-stage configurable ingress: structure vs. semantics

## Status

Accepted (2026-08-05).

## Context

ADR-0010 established the feed-integration strategy: multiple sources
land on a common Silver ontology, with per-source mapping expressed
declaratively in Bloblang rather than in bespoke per-source services.
That has held well for sources that arrive as structured data — JSON
over AMQP/HTTP, where the mapping problem is purely one of *meaning*
(this field is fuel level, that field is a platform type, this string
needs alias resolution).

Binary wire formats break the assumption underneath it. A DIS PDU, an
ASTERIX record, or a tactical datalink message is not structured data
that needs re-interpretation — it is a **packed binary grammar** that
must first be parsed into fields at all. Bloblang is a mapping language.
It is a poor bit-field parser and an actively bad place to encode a wire
grammar: the resulting mapping is unreadable, untestable in isolation,
and silently wrong at the edges (variable-length fields, conditional
field presence, FSPEC-driven layouts).

The existing DIS path already resolved this correctly but implicitly: a
decoder sidecar (`dis_ingestor.py`) parses PDUs and publishes JSON to
`ingress-dis-raw`, and Bloblang maps *that* to Silver. The pattern
works. It has never been written down, so each new format is at risk of
re-litigating it — and the pressure at integration time is always to
"just add a bit of parsing to the mapping" because a sidecar feels like
more work.

Two further pressures make writing it down urgent now:

1. **Formats are arriving faster than engineering capacity.** ASTERIX
   (surveillance radar) is next, tactical datalink is visible behind it.
   If each format costs a bespoke service, the integration rate is
   bounded by engineering headcount rather than by configuration.

2. **Some formats are controlled specifications.** The OSS core cannot
   ship a decoder for a spec it may not redistribute. The architecture
   has to be able to accept such a format without the OSS repository
   ever containing the specification.

## Decision

### The boundary statement

> **Bloblang maps structured data to the Silver ontology; it does not
> decode binary grammars. Binary wire formats are decoded by
> format-decoder sidecars driven by declarative format definitions.
> Adding an ingestion format requires zero engine code: one format
> definition + one Bloblang mapping.**

That is the rule. The rest of this ADR is its implications.

### Stage division

**Stage 1 — structure / grammar.**
Binary wire → decoder sidecar + definition file → raw JSON on
`ingress-<format>-raw`.

The sidecar's engine is **generic**. All per-format knowledge lives in
definition files, which are configuration — mounted, versioned, and
changeable without touching engine code.

**Stage 2 — semantics.**
Raw JSON → Bloblang → Silver ontology: identity aliasing,
`platform_variant` resolution, kinematics, `OperationalState`
decomposition, provenance stamping.

This is the existing discipline, unchanged. ADR-0015 (identity
resolution), ADR-0016 (platform-variant reconciliation), ADR-0026
(operational-state axes) and ADR-0029 (label stamping) all continue to
apply here and only here.

The seam between the stages is a Kafka topic carrying raw JSON. That
placement is deliberate: it makes Stage 1 output independently
inspectable, replayable, and testable against sample captures without
running Stage 2 at all.

### Engine policy

Engines are chosen per format against the definition-driven test, not
by preference:

**Formats with an existing definition-driven open decoder use it.**
ASTERIX is the worked case: category definitions are XML, runtime
hot-loadable, and open implementations already consume them. Adding a
new ASTERIX category is dropping in an XML file — no rebuild.

**Formats without one use [Kaitai Struct](https://kaitai.io/).** A
`.ksy` declarative format definition is compiled in CI to a Python
parser. The licensing split is load-bearing and deliberate:

- the **runtime** is permissively licensed and ships in the image;
- the **compiler** is GPL and stays in the build toolchain, never in a
  shipped artifact.

Adding a format is: new `.ksy` + CI regeneration + image rebuild. That
is the same operational rhythm as any configuration-overlay change that
requires a redeploy — a known, rehearsed motion, not a new one.

**Heavier JVM-based decoding engines are excluded from tactical-tier
sidecars.** This is a deliberate edge-footprint design decision, not a
technical judgement about those engines: small-footprint deployability
on constrained forward infrastructure is an architectural requirement
for OpenDDIL's edge tier (ADR-0021 — the edge is not a small copy of
HQ). A decoder that doubles the edge node's memory floor is
disqualified at the edge regardless of merit.

The definition-in / JSON-out interface keeps engines **swappable per
format**. If a program requires a specific engine at a higher tier —
where footprint is not the binding constraint — that substitution
changes one sidecar and no downstream contract.

### Controlled-spec formats follow the customer-bundle pattern

For formats whose specifications are controlled (tactical datalink
J-series being the motivating case), the split mirrors the existing
OSS-core / private-overlay separation already used for deployment
mappings:

- **The OSS core ships:** the sidecar *seat* (the deployment slot, the
  topic, the wiring, the framing listener where framing is itself
  unrestricted) and a **generic datalink-track Silver shape** — the
  canonical target the mapping produces.
- **A customer bundle ships:** the format definition and the mapping,
  authored by parties with legitimate access to the specification.

The OSS repository therefore never contains the controlled
specification, and the capability is still architecturally present and
demonstrable. This is the same structure as existing deployment mapping
overlays: the core defines the contract and the seat, the private bundle
supplies the deployment-specific content.

## Phasing

### Phase 1 — This ADR (~½ day)

The boundary statement is the deliverable. It is what prevents the next
integration from quietly putting a bit-parser in a mapping.

### Phase 2 — ASTERIX sidecar (~2–3 days)

Wrap an existing open, definition-driven ASTERIX decoder as a sidecar:

```
UDP listener (multicast-capable)
  → decoder + category-definition directory
  → JSON per record
  → ingress-asterix-raw
```

Category definitions mount as configuration (hot-addable). Same
deployment seat as the existing DIS mapper — this is a second tenant of
a proven pattern, not new infrastructure.

### Phase 3 — Bloblang mappings (~1–2 days)

- **CAT048 / CAT062** (target reports, system tracks) →
  `EntityTelemetryEvent`: track position → `kinematics.position.wgs84`,
  track identifiers through identity aliasing, position-source per
  source, provenance including `originator_nation` where derivable
  (ADR-0029).
- **CAT034** (radar service messages) → `OperationalState`. A
  surveillance radar's status decomposes into power / functional-mode /
  health exactly as the existing sensor feed did. This is the **third
  independent worked example** of the ADR-0026 decomposition, from a
  source that has never seen OpenDDIL — which is the strongest available
  evidence that the axis model is a genuine intersection rather than one
  source's vocabulary in disguise.

### Phase 4 — Verification (~½ day)

Replay **publicly available ASTERIX sample captures** through the
pipeline. Verify decoded tracks land in `telemetry_latest_state` with
correct positions and render through the existing visual cascade.

Falsifiable and specific: *known sample coordinates appear at known map
positions.* Not "ingestion works" — a coordinate from the capture
appears where that coordinate should be.

### Phase 5 — Fenced / deferred

- **Kaitai CI toolchain** stood up against a second concrete format,
  when one materializes. Standing it up speculatively would be building
  a toolchain against an imagined format.
- **Datalink framing listener** as the sidecar seat — framing only, no
  message-internals decode in the OSS core.

## Consequences

### Positive

- New format = one definition file + one mapping. Integration rate stops
  being bounded by engineering headcount.
- Wire grammars become testable in isolation, against sample captures,
  without the semantic layer running.
- Controlled-spec formats are architecturally supportable without the
  OSS repository ever holding the specification.
- The raw-JSON seam gives every format the same debugging surface: read
  `ingress-<format>-raw` and see exactly what the decoder produced.
- Engine choice is reversible per format; no downstream contract depends
  on which engine parsed the bits.

### Negative

- One sidecar per format is more moving parts than a single fat ingest
  service, and each is a deployment object to operate and monitor.
- The Kaitai path requires CI regeneration and an image rebuild per
  format change — genuinely less agile than hot-loaded definitions, and
  the two-tier story ("some formats hot-load, some need a rebuild") is a
  wrinkle operators must know.
- Excluding JVM engines at the tactical tier forecloses some
  best-in-class decoders there. Accepted deliberately; mitigated by
  per-format swappability at higher tiers.
- The two-stage split means a per-format failure can occur in two
  places, and "no data" requires checking both.

### Neutral / acknowledged

- The DIS path already follows this pattern. This ADR ratifies and names
  existing practice as much as it introduces anything.
- Sample-capture replay verifies the decode and the mapping, not
  real-world radar behaviour. Live-feed validation is a separate,
  program-gated activity — the same honesty ADR-0020 applies to
  prognostics.
- "Zero engine code" is a claim about the common case. A format with
  genuinely novel transport (not just novel payload grammar) still needs
  listener work; the claim covers the grammar, not the plumbing.

## Related

- ADR-0010 — feed integration strategy (the declarative-mapping
  discipline this refines).
- ADR-0015 / ADR-0016 — identity resolution and platform-variant
  reconciliation, both Stage 2 concerns.
- ADR-0021 — edge topology is load-bearing (why edge footprint
  constrains engine choice).
- ADR-0026 — OperationalState axes; CAT034 is the third worked example.
- ADR-0029 — provenance labelling stamped during Stage 2 mapping.
