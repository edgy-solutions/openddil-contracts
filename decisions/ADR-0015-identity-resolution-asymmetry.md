# ADR-0015: Identity Resolution Asymmetry — DIS Feed Bypasses Alias Rewrite

## Status

Proposed — 2026-05-13. **Stub.** Promoted from a follow-up note in the
Phase 3 close-out. This ADR documents a known limitation, not a finalized
decision; it will be revisited when the identity-resolver service is
implemented.

## Context

Two feeds currently produce events into the `raw-sensor-stream` Silver
topic:

1. **DIS** (`openddil-sensor-ingest/dis_ingestor.py` →
   `sim-dis-mapping.yaml`) — emits Silver events with
   `asset.asset_id` set to the **URN form** `"dis:{site}:{app}:{entity}"`
   (e.g., `"dis:1:1:4773"`).
2. **Proprietary** (`openddil-sensor-ingest/proprietary_ingestor.py` →
   `proprietary-mapping.yaml`) — emits Silver events with
   `asset.asset_id` **rewritten to the canonical form** via lookup against
   `openddil-contracts/ontology/asset_identity_aliases.yaml` (e.g.,
   `"USA-ARMY-1HBCT-M1A2-4773"`).

Verified live during Phase 3: a Silver event for the same physical M1A2
SEPv3 hull appears under both `"dis:1:1:4773"` and
`"USA-ARMY-1HBCT-M1A2-4773"` simultaneously. **The two never reconcile
into a single record** — downstream consumers see two different
`asset_id`s for one asset.

## Why this exists

The asymmetry was introduced deliberately during Phase 3, not by accident:

- The proprietary feed's `parentUnitId` field is a string the customer
  controls; mapping it via a YAML alias is straightforward Bloblang.
- The DIS PDU's `entityID` triplet (site, application, entity) is a
  simulation-exercise coordinate, not a hull number. Rewriting it to a
  canonical hull ID requires the *same* lookup table as the proprietary
  case, but with a tuple key. Implementing that lookup in Bloblang is
  possible but starts to duplicate identity-resolution logic across
  every feed mapping.
- Per ADR-0010, feed-specific mappings absorb feed quirks but should not
  own cross-cutting concerns like canonical identity. Identity resolution
  is a *downstream* responsibility.

So Phase 3 shipped with the proprietary feed doing the alias lookup
inline (because the schema was simple) and the DIS feed punting the
rewrite to a future identity-resolver service that consumes Silver and
emits enriched Silver.

## Known consequences

- **Same physical asset has two `asset_id`s in Silver.** Consumers that
  reduce by `asset_id` (e.g., compacted state in CM service) see them as
  separate assets. `cm-service` currently treats `dis:1:1:4773` and
  `USA-ARMY-1HBCT-M1A2-4773` as two different Virtual Object instances
  with independent state.
- **CM events submitted with the canonical form do not affect the
  DIS-sourced state.** This is the test scenario flagged in Phase 3
  cross-feed identity verification: both events exist, but
  `apply_cm_event` for `USA-ARMY-1HBCT-M1A2-4773` does not update
  the `dis:1:1:4773` Virtual Object's state.
- **The COP UI (Phase 4) will need to know about this asymmetry** when
  joining feeds by asset. Phase 4 should either (a) defer joining until
  the identity-resolver service is in place, or (b) explicitly cross-walk
  via the alias YAML at display time.

## Resolution path (deferred to future phase)

Build an **identity-resolver service** between Bronze and Silver:

```
Bronze topics → identity-resolver → Silver (raw-sensor-stream)
                       │
                       └── reads asset_identity_aliases.yaml
                           (hot-reloadable)
```

The resolver:

1. Consumes from `ingress-dis-raw`, `ingress-proprietary-raw`, and any
   future Bronze topic.
2. For each event, extracts the feed's native identifier (DIS triplet,
   proprietary `parentUnitId`, etc.).
3. Looks up the canonical `asset_id` in the alias table.
4. Rewrites `asset.asset_id` to the canonical form before emitting to
   Silver.
5. Falls back to the URN form when no alias entry exists (so unknown
   assets still appear in Silver, just flagged for ontology curation).

When the resolver ships, both feed Bloblang mappings should stop doing
identity lookups inline and emit only the URN/native-id form. The
resolver becomes the sole place where canonical asset_id is assigned.

## Out of scope for this ADR

- Exact resolver architecture (Bloblang? Restate? Pure Python sidecar?).
  Apply ADR-0014's Faust-vs-Restate placement rules when the resolver is
  built — it's per-feed state with a YAML lookup, so probably a thin
  stateless consumer (Bloblang in another Connect pipeline, or a small
  Python service).
- Whether to retain DIS triplets and proprietary IDs as secondary
  fields on `AssetIdentity` for diagnostic traceability. Recommended:
  yes. The proto already has `dis_entity_id` for this purpose; a similar
  field for proprietary native IDs may be needed.

## Verification

When the resolver is implemented, a Hero Scenario v3.5+ test should
assert that sending the same physical asset via both feeds produces
**one** record on `raw-sensor-stream` (or, if both records still appear,
both carry the same canonical `asset_id`).

## Related

- ADR-0010 — Feed integration: external feeds adapt to Silver, not the
  reverse. The resolver is the place where this principle is enforced
  for identity.
- ADR-0014 — Faust vs Restate placement, applies to the resolver itself.
- `openddil-contracts/ontology/asset_identity_aliases.yaml` — the
  authoritative lookup table.
