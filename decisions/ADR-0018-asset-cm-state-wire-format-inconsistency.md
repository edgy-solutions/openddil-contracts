# ADR-0018: asset-cm-state Wire Format Inconsistency

## Status

Accepted — 2026-05-14

## Context

OpenDDIL's internal Kafka topics carry **Protobuf** payloads. This is the
convention across the pipeline: `raw-sensor-stream`, `telemetry-latest-state`,
`asset-telemetry-windows`, and `asset-logistics-status` all serialise their
values with `SerializeToString()` against the generated message classes in
`openddil-contracts/gen/`.

`asset-cm-state` is the exception. `openddil-cm-service` emits it as
**JSON** — `json.dumps(payload).encode("utf-8")` in
`openddil-cm-service/src/events/asset_cm.py` — with a shape that diverges
from the `openddil.configuration.v1.AsMaintainedConfiguration` proto in
three ways:

- enum fields are **integer values** (`overall_status: 4`), not the proto
  string names
- timestamps are **`*_ns` integer nanoseconds** (`as_of_ns`,
  `last_observed_at_ns`), not RFC3339 strings or proto Timestamp messages
- the payload includes `manual_discrepancies` alongside `discrepancies`,
  mirroring the cm-service `AsMaintainedRecord` dataclass rather than the
  proto message

This was **not a deliberate design decision**. It predates the Phase 4a
`openddil-projector` and surfaced only when the projector — written
contract-first to decode `asset-cm-state` as `AsMaintainedConfiguration`
protobuf — was run against the live stack and rejected every message. The
topic has carried JSON since cm-service was built; nothing downstream had
ever attempted a contract-first protobuf decode of it before, so the
inconsistency was invisible.

Two consumers currently depend on the JSON shape:

1. **`openddil-logistics-fusion-service`** — its Restate subscription
   `asset-cm-state -> AssetLogistics/on_cm_state_change` parses the JSON.
2. **`openddil-projector`** — Phase 4a added a `json` decoder mode and a
   `cm_state` handler that maps the JSON shape (integer enums → proto
   names, `*_ns` → datetime) into the `asset_cm_state` Postgres table.

## Decision

**Leave `asset-cm-state` as JSON. Do not migrate it to protobuf as part of
Phase 4.**

The Phase 4a `openddil-projector` absorbs the inconsistency: its
`projector_config.yaml` declares `decode_as: json` for this one topic, and
the `cm_state` handler owns the shape-normalisation. This was the correct
containment — handling it in the projector rather than changing cm-service
— because:

- A wire-format change to `asset-cm-state` is a **coordinated multi-service
  change**: cm-service (producer) and logistics-fusion-service (consumer)
  must change together, with a migration window. That does not belong in a
  UI-focused phase.
- Phase 4 is already the largest phase in the project. Folding a
  cross-service wire-format migration into it is scope creep.
- The inconsistency is now **observable** — the projector's `json` decoder
  mode and this ADR both make it explicit rather than silent.

This is the same pattern as ADR-0014's treatment of `faust-edge` and
ADR-0015's identity-resolution stub: **known suboptimal, deliberately
deferred, explicitly observable.** Consistency for its own sake is a tax,
not a virtue (ADR-0014). The migration happens when a future phase has a
real reason to be substantively in cm-service anyway — at which point the
producer is already open, the consumer change can be coordinated, and the
protobuf migration rides along instead of being its own disruptive effort.

### Migration trigger (when this should be revisited)

Revisit when **any** of the following becomes true:

- a future phase modifies `openddil-cm-service` substantively for its own
  reasons (the producer is already open — migrate then)
- a third consumer of `asset-cm-state` is proposed (the cost of every new
  consumer re-implementing the JSON-shape mapping starts to exceed the
  one-time migration cost)
- the cm-service `AsMaintainedRecord` dataclass and the
  `AsMaintainedConfiguration` proto drift far enough apart that the JSON
  shape can no longer be cleanly mapped to the proto's field set

## Consequences

**Pros**

- Phase 4 stays scoped. No cross-service wire-format migration mid-phase.
- The projector's `json` decoder mode is a small, well-tested, reusable
  piece — not a one-off hack. If another producer ever emits JSON, the
  mode already exists.
- The inconsistency is documented and has a defined trigger condition, so
  it cannot quietly become permanent-by-forgetting.

**Cons**

- `asset-cm-state` remains the one internal topic a new engineer cannot
  assume is protobuf. The projector config and this ADR mitigate, but the
  asymmetry is real.
- Every new consumer of `asset-cm-state` must re-implement the JSON-shape
  mapping (integer enums, `*_ns` timestamps) until the migration happens.
  Two consumers today; this cost scales linearly.

**Rejected alternatives**

- *Migrate cm-service to emit protobuf now.* Correct end state, wrong
  time. It is a coordinated cm-service + logistics-fusion-service change
  with a migration window, dropped into a UI phase that has no other
  reason to touch either service. Scope creep.
- *Make the projector tolerate both formats (sniff JSON vs protobuf per
  message).* Adds permanent complexity to absorb a temporary
  inconsistency. The `decode_as: json` config entry is explicit and
  cheaper; when the migration happens it flips to the proto message name
  and the sniffing logic would have been dead weight.

## Related deferred-consistency items

Two further consistency items surfaced during Phase 4a. Both are
**deliberately deferred** and recorded here so they remain durable rather
than living only in a phase report:

### 1. Protobuf migration of `asset-cm-state`

The subject of this ADR. Deferred per the Decision above; trigger
conditions in the "Migration trigger" section.

### 2. `openddil-regional-stack/schema.hcl` table parity

Phase 4a added five pipeline read-model tables (`asset_cm_state`,
`asset_logistics_status`, `telemetry_latest_state`, `tactical_events`,
`asset_telemetry_windows`) to the **canonical single-region** schema at
`openddil-stack/schema/schema.hcl`. The OpenDDIL workspace also contains a
**separate** schema topology at `openddil-regional-stack/schema.hcl` for
the regional-hub deployment target.

The regional-stack schema does **not** yet have these five tables. It will
need them (with whatever row-filtered publication the regional topology
requires) **when the regional hub becomes a real deployment target** — at
that point the `openddil-projector` would also need to run against, or
replicate into, the regional Postgres.

This is **not actioned now**: the Phase 4 demo compose targets only the
single-region `postgres-hq`, and the regional-stack topology is not yet a
live deployment. Recorded here so the parity requirement is not lost when
the regional hub work begins.

## Related

- ADR-0014 — Restate vs Faust placement. Source of the "known suboptimal,
  deliberately deferred, explicitly observable" pattern, and the
  "consistency for its own sake is a tax" principle this ADR applies.
- ADR-0015 — Identity Resolution Asymmetry. Same pattern: a known gap
  stubbed as an ADR rather than fixed immediately, with a defined
  revisit trigger.
- ADR-0019 — Single Kafka→Postgres Projector. The Phase 4a service that
  absorbs this inconsistency via its `json` decoder mode.

## Notes for future maintainers

- The projector's JSON-shape mapping for `asset-cm-state` lives in
  `openddil-projector/src/handlers/cm_state.py` and
  `openddil-projector/src/decoders/json_raw.py`. When the protobuf
  migration happens, the projector change is small: flip `decode_as` in
  `projector_config.yaml` from `json` to
  `openddil.configuration.v1.AsMaintainedConfiguration`, and rewrite
  `cm_state.py` to consume the proto dict shape (RFC3339 timestamps,
  string enums) instead of the JSON shape.
- The integer-enum → proto-name mapping in `cm_state.py` imports
  `as_maintained_pb2` best-effort; it is defensive against the proto
  stubs being absent. That defensiveness can be removed once the topic is
  protobuf and the proto import is unconditional.
