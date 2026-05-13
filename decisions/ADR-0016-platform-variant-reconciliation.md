# ADR-0016: Platform Variant Reconciliation at the Feed Boundary

## Status

Accepted — 2026-05-13. Generalizes ADR-0010 to a second identifier level.

## Context

ADR-0010 established that external feeds adapt to OpenDDIL's internal
Silver schema via Bloblang at the feed boundary, with identity resolution
backed by `asset_identity_aliases.yaml`. Phase 3.5 surfaced a parallel
problem one level "up": the **platform variant string** ("M1A2-SEPv3",
"AH-64E", etc.) is the join key for ontology-driven facts like fuel
capacity, baseline rev, MTBF targets — and customer feeds emit their OWN
spelling of this string.

Phase 3 had the Sim-A Bloblang copying `$src.platform_type` directly into
`asset.platform_variant`. That works only as long as the customer happens
to use the canonical spelling. If they use `"M1A2 SEPv3"` (space) or
`"M1A2-SEPv3-Block2"` (custom suffix) or `"abrams-v3"` (internal name),
the downstream fusion service can't find the platform in
`platform_reference.yaml` and silently degrades the analysis.

## Decision

Platform variant reconciliation is a first-class step at every feed
boundary, parallel to asset identity reconciliation. Add
`openddil-contracts/ontology/platform_variant_aliases.yaml` (same
maintenance pattern as `asset_identity_aliases.yaml`): per-feed
`native → canonical` lists.

Feed Bloblang mappings MUST look up the canonical variant rather than
passing through the native string. If no match, emit `"UNKNOWN"` — the
fusion service handles UNKNOWN gracefully (no fuel-% evaluation) and the
ontology-drift check at startup logs WARN for any variant referenced from
an alias file that isn't in `platform_reference.yaml`.

## Consequences

- One additional ontology file (`platform_variant_aliases.yaml`) plus a
  startup WARN check in the fusion service.
- Customer integration cost moves from "guess what they call our M1A2"
  to "extend the alias file when their team confirms their strings".
- ADR-0010 generalizes: external protocols don't shape internal contracts
  at ANY identifier level — assets, variants, or future identifiers we
  introduce (baselines? CIs?).

## Verification

- Test 21 (`test_21_sim_a_silver.py`) asserts that a sim-a message with
  `platform_type: "M1A2-SEPv3"` produces a Silver event with
  `asset.platform_variant: "M1A2-SEPv3"` resolved through the alias file.
- The fusion service startup logs WARN for any variant referenced from
  `platform_variant_aliases.yaml` or `dis_entity_types.yaml` that lacks a
  corresponding entry in `platform_reference.yaml`. Caught at boot, not
  at first wrong status emission.

## Related

- ADR-0010 — Feed integration strategy (the parent principle).
- ADR-0015 — Identity resolution asymmetry (the asset-id-level version
  of the same problem; deferred to a future resolver service).
- `openddil-contracts/ontology/platform_variant_aliases.yaml`
- `openddil-contracts/ontology/platform_reference.yaml`
- `openddil-logistics-fusion-service/src/fusion/ontology_check.py`
