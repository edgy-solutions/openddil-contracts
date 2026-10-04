# ADR-0047 — `asset_id` is opaque inside the system; every boundary has a mapper

## Status

**ACCEPTED — 2026-10-03.** Supersedes ADR-0015 (identity resolution asymmetry, a proposed stub).

## Decision

1. **`asset_id` is opaque inside OpenDDIL.**
   - Interior code may compare it for equality, hash it, key by it, store it and display it.
   - It may not split it, pattern-match it, check its prefix or suffix, slice it, or `LIKE`-query it,
     for any purpose: not to learn a site, a callsign, a feed, an edge, a region, a nation or a kind.
   - The one exception is input validation at a trust boundary. Checking an id taken from a request
     against an allowed character set and length derives nothing from it. Each such check is listed
     in the CI allowlist like a mapper.
2. **Every boundary has a mapper.**
   - At ingress, a mapper turns a source's native identity into an `asset_id` *plus declared fields*:
     `dis_entity_id`, `callsign`, the site, the source feed, and whatever else the interior needs.
   - At egress, a mapper turns an `asset_id` into the destination's identity.
   - The mapper is the only code that knows any identity scheme.
3. **DIS to internal is the identity mapping today.**
   - The DIS mapper sets `asset_id` to the string it sets now.
   - That is the mapper's choice, and it can change without any interior change. The interior must
     not be able to tell.
4. **What the interior needs, it reads from a declared field.**
   - A declared field is set by the mapper, or by an authoritative table (ADR-0028), and carried
     alongside the id.
   - If no field exists for something the interior needs, the fix is to add the field at the boundary,
     not to read it out of the id.
5. **Correlation and durable-versus-session identity stay at the boundary.**
   - *Correlation* is two sources naming one asset.
   - *Durable versus session* matters because a DIS entity id is a coordinate in one exercise, not a
     hull.
   - Both are the boundary mapper's concern, handled through the mapper's tables.
   - ADR-0015's plan for an interior resolver that rewrites ids into a canonical form is withdrawn.
6. **No re-keying.** Existing `asset_id` values, Kafka keys, Restate object keys and table keys are
   unchanged. This ADR changes what code may do with the id, not the id.
7. **Enforced in CI.**
   - Each repo that handles asset ids runs a check that fails on a new parse.
   - The only allowed sites are the boundary mappers' construction of an id, each one listed by file
     in the check's allowlist with the reason.

## Why

- **The id was carrying data it was never declared to carry.**
  - Site filters, callsign derivation and prefix checks each read structure out of a string whose
    structure belongs to one source, DIS.
  - Every such read is a silent dependency on that source's scheme.
  - A second source with a different scheme fails quietly in each of those places. It shows as no
    rows, a wrong site or an empty callsign; nothing raises an error.
- **ADR-0015 recorded the symptom.** The same asset appeared under two ids. It proposed fixing that by
  rewriting ids in the interior, which is re-keying under another name.
- **The cheaper rule is to keep the interior ignorant of schemes.** Then a mapper can change its
  scheme, or a second mapper can arrive, without the interior noticing.
- **Contract B already had to take this position.** Its validator does not parse `asset_id`, and the
  site that keys the label lookup is a declared field (DESIGN-2026-09-06, amendment 2026-10-03).

## Consequences

- **Every existing parse site is replaced by a declared field.** The inventory and each replacement
  are recorded below as they land.
- **`AssetIdentity` already declares most of what the parse sites wanted:** `dis_entity_id` (site,
  application, entity), `callsign`, `platform_type`. Where a field exists, the replacement reads it.
  Where one is missing, it is added at the boundary.
- **ADR-0041 is unaffected and consistent.** The tactical and sustainment identifiers are carried side
  by side, neither derived from the other. This ADR applies the same rule within one identifier.

## Inventory and replacements

*(Filled as the replacements land.)*

## Related

- ADR-0015: superseded.
- ADR-0028: the authoritative asset → edge → region table, which is one source of declared fields.
- ADR-0041: both identifier schemes carried, never derived.
- DESIGN-2026-09-06-interface-contracts.md, amendment 2026-10-03: the Contract B kit treats
  `asset_id` as opaque.
