# ADR-0019: Single Kafka→Postgres Projector

## Status

Accepted — 2026-05-14

## Context

Phase 4 makes the OpenDDIL pipeline visible: the COP UI needs to read
per-asset CM state, logistics severity, latest telemetry, tactical events,
and windowed aggregations. The UI's read path is **ElectricSQL**, which
exposes Postgres tables as HTTP Shapes. Something has to move data from the
pipeline's Kafka topics into those Postgres tables.

The Phase 4 pre-flight inventory found there was **no such component**.
None of `asset-cm-state`, `asset-logistics-status`, `telemetry-latest-state`,
or `tactical-events` reached Postgres. The frontend's `App.tsx` instead
polled two HTTP endpoints (`/api/telemetry`, `/api/alerts`) that `faust-edge`
never actually served — the UI received zero live data.

Two shapes of solution were on the table:

1. **One projector service per topic** — `cm-state-projector`,
   `logistics-projector`, etc. The earlier `openddil-hq` work sketched a
   per-topic Restate Virtual Object (`InventoryProcessor`) in this style.
2. **One generic projector** — a single service with a config-driven
   topic→table mapping and one handler per topic.

## Decision

**Build one generic Kafka→Postgres projector: `openddil-projector`.**

- A single service consumes all UI-bound pipeline topics.
- The topic→table mapping is **config-driven**
  (`src/config/projector_config.yaml`, SIGHUP-reloadable). Each entry binds
  one topic to one handler, one table, one consumer group, one decoder, and
  one mode (`upsert` for compacted topics, `append` for event streams).
- Adding a topic to the UI is a **config entry + a handler + a table**, not
  a new service, a new Dockerfile, a new compose block, and a new CI
  pipeline.
- The projector is a **dumb pipe**: decode → map fields → UPSERT. It holds
  no business logic. Severity computation, discrepancy analysis, and fusion
  all stay upstream in `cm-service` / `logistics-fusion-service` /
  `faust-edge`.

This is the Phase 4 architectural principle "single generic projector,
configured via YAML mapping" made normative.

### Why not per-topic projectors

- **Operational multiplication.** Five topics today would mean five
  services, five images, five compose blocks, five CI pipelines, five
  on-call surfaces — for five functions that are byte-identical except for
  the decoder and the field map.
- **The work genuinely is uniform.** Every projection is "consume → decode
  → map → UPSERT." That uniformity is exactly what a config-driven
  dispatcher captures. Per-topic services would copy-paste the consumer
  loop, the retry logic, the offset-after-write discipline, and the metrics
  five times.
- **Restate is the wrong tool here** (ADR-0014). A projection has no
  per-key durable workflow and no per-entity schedule — it is a continuous
  "consume → project → emit-to-table" firehose. ADR-0014's placement guide
  points that at Faust or a plain Kafka consumer, not at a Virtual Object.
  The projector is a plain `confluent-kafka` consumer.

### Boundary discipline

The projector imports the generated proto stubs to decode messages, and it
imports nothing else from the pipeline services. Handlers and decoders are
pure functions — unit-testable with no live Kafka or Postgres. The decoder
layer (`protobuf`, `cloudevents.json`, `json`) is the only place wire
formats are known; handlers see dicts.

## Consequences

**Pros**

- One service to deploy, monitor, and reason about. One metrics surface
  (`projector_*` on `:8084`), one consumer-lag dashboard.
- New UI data is cheap: a YAML entry + a pure-function handler + a table.
- At-least-once delivery, backpressure/retry, batch coalescing, and
  schema-drift tolerance are written once and apply to every topic.

**Cons**

- A single service consuming five topics is a single failure domain. A bug
  in the consumer loop stops all five projections, where per-topic services
  would fail in isolation. Mitigated by: handlers/decoders are pure and
  independently tested; a bad *message* is logged-and-skipped per-topic
  without affecting others; only a bug in the shared loop is global.
- One process's resource budget covers all topics. Fine at current
  pipeline volumes; if one topic becomes a true firehose, that consumer can
  be split out later — the config-driven design makes extraction
  mechanical.

**Rejected alternatives**

- *Per-topic projector services.* Rejected for operational multiplication
  of byte-identical plumbing — see "Why not per-topic projectors."
- *Restate Virtual Object per topic* (the `InventoryProcessor` sketch
  style). Rejected per ADR-0014: a stateless table projection has no
  per-key durable workflow and no schedule; durable-execution overhead is
  wrong for it.
- *Revive the Faust HTTP endpoints the UI used to poll.* Rejected: polling
  is not the Phase 4 read architecture. ElectricSQL Shapes are push-based
  and give the UI offline-first caching for free; a parallel Faust HTTP
  path would be a second, redundant read surface.

## Related

- ADR-0014 — Restate vs Faust placement. Its placement guide is why the
  projector is a plain Kafka consumer, not a Restate Virtual Object.
- ADR-0018 — asset-cm-state wire format inconsistency. The projector's
  `json` decoder mode absorbs that inconsistency; the projector is the
  service that surfaced it.
- ADR-0006 — Persistence/Computation Model Separation. The "dumb pipe, no
  business logic" discipline is this boundary applied to the projector.

## Notes for future maintainers

- The projector lives at `openddil-projector/`. Topic→table mapping:
  `src/config/projector_config.yaml`. Handlers: `src/handlers/`. Decoders:
  `src/decoders/`.
- SIGHUP currently re-reads the config and logs the delta but does not
  hot-add/remove consumers — adding or removing a mapping at runtime needs
  a process restart. If runtime mapping changes become a real need, that
  is the place to extend.
- If a single topic outgrows the shared process, extraction is mechanical:
  the same image, the same config file with a one-entry `mappings:` list,
  a separate compose service. The config-driven design was chosen partly
  to keep that escape hatch cheap.
