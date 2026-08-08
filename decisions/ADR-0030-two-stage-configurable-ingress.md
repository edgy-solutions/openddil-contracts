# ADR-0030 — Two-stage configurable ingress: structure vs. semantics

## Status

Accepted (2026-08-05).

**Amended 2026-08-07** — DDS ingress forced a distinction the original
draft did not make: not every ingress is a byte-stream to decode. Added
§Ingress classes (byte-stream decode vs. middleware participation), the
DDS engine decision, and the QoS silent-failure trap. The two-stage
division of labour and the zero-engine-code claim both survive the
addition unchanged, which is the useful part — see §Ingress classes.

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

### Ingress classes — byte-stream decode vs. middleware participation

*(Added by the 2026-08-07 amendment.)*

The original draft assumed every Stage 1 sidecar is a **decoder**: bytes
arrive, a grammar turns them into fields. That is true of ASTERIX and of
tactical datalink. It is **not** true of DDS, and forcing DDS into the
decoder shape would have produced a dishonest ADR and a confused
implementation.

DDS is a **middleware you join**, not a format you decode. The sidecar
is a *domain participant*: it performs RTPS discovery, matches
publishers on topic + type + QoS, and receives samples that are
**already typed**. The decoding is performed by the DDS stack itself,
against IDL-defined types. There is no grammar file because there is no
grammar — there is a participant configuration.

So Stage 1 has two classes, distinguished by what their *definition
artifact* is:

| Class | Examples | Stage 1 definition artifact |
|---|---|---|
| **Byte-stream decode** | ASTERIX, tactical datalink, DIS | A **grammar** — category XML, `.ksy` |
| **Middleware participation** | DDS | A **participant config** — domain id, topic list, per-topic QoS profiles, type source (IDL files or XTypes discovery) |

**What survives unchanged, and this is the point:**

- **Stage 2 is untouched.** Received DDS samples become JSON on
  `ingress-dds-raw`, and Bloblang maps them to Silver exactly as it maps
  everything else. The semantic layer cannot tell — and must not care —
  whether a grammar or a middleware stack produced the JSON.
- **The zero-engine-code claim holds**, restated for the class: a new
  DDS integration is *participant config + type source + Bloblang
  mapping*, no engine code.

The two-stage division of labour absorbing something that is not a byte
format at all is reasonable evidence the abstraction was cut at the
right joint: the seam is *structure vs. semantics*, and "structure" was
never specifically about bytes.

### QoS mismatch fails silently — the class's characteristic trap

DDS-specific and load-bearing enough to be an architectural
requirement rather than an implementation note.

A subscriber whose reliability / durability / history QoS do not match
the publisher's **simply never matches**. No error is raised. No data
arrives. Nothing appears in a log unless discovery events are
explicitly inspected. The observable signature is an empty topic — which
is indistinguishable from "the publisher is not running."

This is the silent-absence failure mode in protocol form, and this
project has been bitten by that class before (rows arriving with
positions silently absent; a partially-labelled dataset under
enforcement looking identical to correct enforcement — see
`PRINCIPLES.md` §Ordering).

**Requirement:** the DDS bridge must surface **discovery and matching
state as a first-class observable** — publishers seen, readers matched,
and QoS-incompatibility events emitted to logs and metrics. Data flow
alone is not an adequate health signal for this ingress class, because
its characteristic failure produces no data and no error.

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

**DDS engine: Eclipse Cyclone DDS in the OSS core.** *(Added by the
2026-08-07 amendment.)*

- **Licensing:** EPL-2.0 / EDL-1.0. Weak, file-level copyleft — clean to
  depend on from an MIT-licensed project **as a container dependency**,
  not vendored into OpenDDIL source. Recorded explicitly because the
  Kaitai entry above establishes that licensing posture is a decision
  criterion here, not an afterthought.
- **Footprint:** a small C library with Python bindings and no JVM. It
  passes the same tactical-tier discipline that excluded JVM-based
  decoding engines, so the DDS bridge is deployable at the edge rather
  than HQ-only.
- **Maturity:** widely deployed, including as a ROS 2 RMW
  implementation, so "obscure dependency" is not a live supply-chain
  objection.

**RTI Connext never ships in the OSS core.** It is commercial and
unshippable, exactly like the controlled-spec formats below. The
integration path for an RTI-based deployment is **wire-level interop,
not vendor software**:

- DDSI-RTPS is an OMG standard, and Cyclone participants interoperate
  with RTI participants on the same domain. The OSS Cyclone bridge can
  therefore subscribe to a deployment's RTI-published topics **without
  any RTI software present**.
- What the customer overlay carries is not RTI libraries but the
  deployment's **artifacts**: IDL, QoS XML profiles (RTI deployments are
  QoS-profile-heavy), and DDS Security material — governance and
  permissions XML plus certificates, since secured domains are the norm
  in the environments this targets, and Cyclone implements the DDS
  Security specification.

Interop caveats are real — XTypes compatibility and vendor-specific QoS
extensions being the usual suspects. They are **verification items, not
architecture blockers**: the claim OpenDDIL makes is standard RTPS
interop, and it is verified against a real deployment's domain rather
than by shipping a vendor stack to test against.

**Type handling is an open decision, deliberately not made here.** It is
the DDS-class analogue of the ASTERIX-XML-vs-Kaitai-CI split, and it
resolves the same way — by which option is genuinely definition-driven:

- **(a) IDL-compiled** — `idlc`-generated types built in CI. New topic =
  new IDL + regeneration + image rebuild. Same operational rhythm as the
  Kaitai path.
- **(b) Runtime-dynamic via XTypes discovery** — hot configuration, no
  rebuild, materially better if it is production-solid.

(b) is preferable *if* the Python binding's dynamic-type support is
mature enough to depend on. That maturity must be **verified honestly
before committing**; if it is not production-solid, (a) wins and the
reason is recorded. Choosing (b) on hope would reproduce the
"believed-capability" pattern that ADR-0032's Phase 2 gate exists to
prevent.

**Convergence worth recording:** UCI commonly rides DDS in OMS
environments. A DDS participation sidecar is plausibly the transport
seat for a future UCI story — two roadmap items that may turn out to be
one stack. Noted as a convergence, not a commitment.

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

**The overlay seam now carries five distinct kinds of closed-world
artifact** — proprietary AMQP message shapes, controlled-spec format
definitions, vendor DDS artifacts (IDL + QoS profiles), DDS Security
material, and — as of 2026-08-08 — **sovereignty workflow definitions**
(a nation's or department's maintainer process procedures; ADR-0034
§The two planes). That the same pattern keeps absorbing each new
closed-world integration without changing shape is what makes the
open-core story credible in environments where a large fraction of the
integrations cannot be named in public.

**Note on the fifth class:** a nation's maintenance procedures may
themselves be restricted material. Workflow definitions therefore carry
releasability labels and distribute under policy like anything else on
the wire (ADR-0029) — they are not merely private-by-repository, they
are labelled artifacts.

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

### DDS phasing *(2026-08-07 amendment)*

ASTERIX and DDS are **peers**, not sequential: independent sidecars
sharing nothing but the seat pattern. Order by available bandwidth.

1. **This amendment** — the ingress-class distinction.
2. **Cyclone bridge sidecar** — participant driven by a config YAML
   (domain, topics, per-topic QoS, type handling), emitting one JSON
   message per sample to `ingress-dds-raw` (topic name + payload +
   reception metadata). **Discovery/matching observability is a Phase-2
   deliverable, not a follow-up** — see §QoS mismatch fails silently.
3. **Bloblang mappings** — one or two demonstration topic types defined
   in core, from **an entity-state IDL of our own authorship**
   (position / velocity / identity / status), mapped to
   `EntityTelemetryEvent` + `OperationalState`. Authoring our own demo
   IDL keeps any third-party type definition out of the OSS core. If the
   status field decomposes cleanly onto the ADR-0026 three-axis model,
   that is the **fourth** independent worked example — and the first
   from a middleware-class source.
4. **Verification** — compose-stack Cyclone publisher at rate → bridge →
   Bronze → Silver → asset renders with correct position and severity.
   Falsifiable end-to-end. Plus a restart check: publisher stays up,
   bridge restarts, matching re-establishes, and the **discovery
   observable proves it** rather than data flow implying it.
   **RTI-interop verification is customer-side and fenced** — the claim
   is standard RTPS interop; OpenDDIL does not ship a vendor stack in
   order to test against it.
5. **Fenced:** DDS Security config plumbing (overlay-shaped; build when
   a secured domain is real), **DDS as egress** (publishing OpenDDIL
   state into a domain — a real future item, out of scope here),
   UCI-over-DDS payload handling, and the ADR-0017 3D-mock retirement.

**ADR-0017 linkage.** ADR-0017 preserved the maintainer 3D views as
deliberately-synthetic mocks "pending a future feed (RTI / … DDS)". This
amendment is that feed arriving in the architecture. The retirement
*trigger* is not the sidecar existing — it is **a real DDS feed carrying
the relevant entity types actually flowing**. Recorded so the linkage is
visible; not built here.

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
- ADR-0026 — OperationalState axes; CAT034 is the third worked example,
  and a DDS-borne status field would be the fourth (first from a
  middleware-class source).
- ADR-0029 — provenance labelling stamped during Stage 2 mapping.
- ADR-0017 — UI mocks self-identify; it names the DDS feed as the
  retirement trigger for the deliberately-preserved maintainer 3D mocks.
  This ADR's middleware class is that feed arriving architecturally.
- `PRINCIPLES.md` §Ordering / §Verification — the silent-absence failure
  family that the QoS-mismatch trap belongs to, and the
  verify-before-committing discipline the type-handling decision inherits.
