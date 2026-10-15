# ADR-0049 — In-flight munitions are tracked from their own Entity State, keyed by munition id, never as assets

## Status

**ACCEPTED — 2026-10-15.** Amends ADR-0048 §2 (the kind gate has two exits) and §8 (track markers are a track
layer, not an asset layer). The rest of ADR-0048 stands.

## Decision

1. **The kind gate has two exits.**
   - A kind in the asset set (`DIS_ADMITTED_ENTITY_KINDS`, default `1`) continues to the force gate and the asset
     mapping, as before.
   - A kind in the track set (`DIS_TRACK_ENTITY_KINDS`, default `2`) leaves on the track path:
     - it is counted in `dis_ingress_kind_tracked{kind}`;
     - it is published to topic `munition-tracks`, keyed by the munition's entity id.
   - A kind in neither set is dropped and counted in `dis_ingress_kind_dropped{kind}`, as before.
   - The two sets are chart values per path. The render fails if they intersect.
   - **This changes what `dis_ingress_kind_dropped` counts.** A kind-2 record is now routed, not dropped. The sum of
     the dropped and force-dropped counters is still the number of refused Entity State records.
   - The track path skips the force gate. Ownership is decided by the Fire claim (2) and the launcher join (3), not
     by force.
2. **A Fire claims its munition at ingress.**
   - On an edge that admits by entity id, an Entity State whose id was named as the munition by an admitted
     launcher's Fire is admitted.
   - Any other Entity State that is not listed and is not kind 1 is filtered as `munition_unclaimed`.
   - With no entity filter, nothing changes.
   - **Ordering limit:** an Entity State that arrives before its Fire is not admitted. The first sample after the
     Fire is.
   - A Fire that names no munition (0:0:0) produces no track. Its launch row is unaffected.
3. **One row per munition, in `munition_track`, with the launcher as parent.**
   - The key is the munition's own id. It never enters `telemetry_latest_state`, a fleet list or an asset count.
   - The launcher, the launch event and the labels are copied from the `effector_launch` row whose
     `munition_asset_id` matches. Whichever record arrives second completes the join, so arrival order does not
     matter.
   - An unjoined row carries no labels. Under deny-unlabeled the PEP does not serve it.
4. **A track ends on a Detonation or on silence.**
   - **Detonation:** the record names the munition (`explodingEntityID`), or the munition is found through the
     Fire's event. Its result maps through ADR-0048's vocabulary. This applies whatever happens to the launch row.
   - **Silence:** a track this tier has not heard from for `munitionTracks.silenceSeconds` becomes `silent`.
     - The default is 12 s, the DIS default timeout (2.4 × a 5 s heartbeat).
     - Silence is judged on this tier's own arrival clock and is never compared across clocks.
   - A later Detonation replaces `silent` and sets `late_terminal`.
   - A sample for a terminal track writes nothing.
   - **`silent` is a track state, not a launch outcome.** It means "this tier stopped hearing it". ADR-0048 §4
     holds: the launch row's terminal state is set only by a Detonation or by its own timeout (`unresolved`).
5. **Markers and counts read the same rows.**
   - The map at every tier draws each non-terminal track as a small marker tied to its launcher. The marker is gone
     at terminal state.
   - The in-flight counts on the munitions cards are the same non-terminal rows, so the number and the dots agree.
   - Expended and unresolved still come from `effector_launch`.

## Why

- **A missile in flight is a child of a launch, not a fleet member.** Admitting it as an asset was the defect the
  kind gate was built to stop. Dropping it outright then removed the only position the exercise had for it.
- **The Fire is the ownership fact.** Entity id lists name platforms. A munition's id is minted at launch, so the
  only party that can vouch for it is the launcher that fired it.
- **The arrival clock keeps silence honest at every tier.** An edge sample time compared with a region clock would
  turn link latency into false silence. Each tier says only what it heard.

## Consequences

- **Rounds with no munition id** (0:0:0, e.g. gun rounds) have a launch row but no track, so they show no dot.
  - In-flight counts drop to what can be drawn.
  - Launches without a track remain visible through expended and unresolved.
- **During a link outage** an upper tier marks its tracks `silent`. That is true from where it stands. A Detonation
  that arrives later corrects the terminal state.
- **The upstream feed path is unchanged** (ADR-0048 Consequences). It still models munitions as assets.

## Related

- ADR-0048: effector tracking from Fire and Detonation. Amended here in §2 and §8.
- ADR-0035: information honesty. Silence is named as silence, not as an outcome.
- ADR-0047: `asset_id` is opaque. A munition id is never read as an asset id.
