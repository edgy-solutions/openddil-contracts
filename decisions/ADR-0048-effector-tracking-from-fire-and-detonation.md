# ADR-0048 — Effectors are tracked from DIS Fire and Detonation events, as child tracks of the launcher, never as assets

## Status

**ACCEPTED — 2026-10-06.** Un-parks munitions Phase 6 for the DIS path only (PLAN-munitions-taxonomy-phases.md,
"Phase 6's blocker"). The upstream feed path is unchanged.

## Decision

1. **Fire and Detonation are decoded at ingress.**
   - sensor-ingest publishes both PDU types as JSON records with:
     - `pdu_type` (`fire` or `detonation`);
     - `event_urn`, `launcher_urn`, `target_urn`, `munition_urn`;
     - the munition type, quantity, warhead and fuse;
     - the raw `detonation_result`.
   - `event_urn` uses the prefix `dis-event:`, never `dis:`, so an event id cannot be mistaken for an asset id
     (ADR-0047).
   - The site filter is `firingEntityID.site` for both types. A Detonation carries the firing entity too, so both
     records are keyed by launcher.
   - The ingestor stamps the edge as provenance. Connect does not default it.
2. **Gate order on the edge Connect is fixed: diverts, then kind, then force.**
   - Diverts run ahead of both gates: `event_report` goes to CM intake, and `fire`/`detonation` go to topic
     `effector-events`. Neither is Entity State, so neither gate judges them.
   - The kind gate (`dis_ingress_kind_dropped{kind}`, default admits kind 1) runs before the force gate
     (`dis_ingress_force_dropped{force}`, default admits force 1).
   - A record both gates would refuse, such as a munition's own Entity State from an opposing force, is counted
     **once, by kind**. The sum of the two counters is therefore the number of refused Entity State records, with no
     double count.
   - Reordering the gates changes what both counters mean. **That is a contract change, not a refactor.**
   - Remove Entity passes both gates. The gates are stateless, and a removal for an id that was never admitted
     creates nothing downstream.
3. **One row per launch, in `effector_launch`, labelled from the launcher.**
   - The projector writes one row per `event_urn` and copies `originator_nation` and `releasable_to` from the
     launcher, the same way `tactical_events` is labelled.
   - A Fire whose launcher is not an admitted asset is refused (`effector_refused_total{reason="unknown_launcher"}`).
     An unadmitted launcher's fires stop there.
   - A Detonation with no matching Fire is refused (`reason="no_fire"`).
4. **Terminal states are a small vocabulary, and "miss" is not one of them.**
   - The DIS `detonationResult` maps as follows:
     - 1 → `entity_impact`;
     - 3 → `ground_impact`;
     - 2, 4 and 5 → `detonated`;
     - 6 → `dud`;
     - anything else → `other`.
   - A Fire with no Detonation within `effectors.terminalTimeoutSeconds` becomes `unresolved`
     (`effector_unresolved_total`). If a Detonation arrives later, it replaces `unresolved` and sets `late_terminal`
     (`effector_late_terminal_total`).
   - **The absence of a Detonation is never an outcome.** That is the reason Phase 6 was parked, and it still holds
     for any path that only sees a track disappear.
5. **A replay is not a refusal.**
   - Where two projectors write one store, every record is projected twice.
   - A Detonation that finds its row already terminal with the **same** result is a replay: there is no write, and
     it is counted in `effector_replayed_total`.
   - Only a **different** result is refused (`reason="conflicting_detonation"`).
   - Refusals are counted per projector instance, so in such a topology one bad event counts once for each projector
     that sees it.
6. **Declared load comes from the deployment, with no default.**
   - The chart's `effectors.declaredLoad` maps an exact asset id or a platform variant to a load per munition type.
     The chart ships these maps empty.
   - Without a declared load, "remaining" is **unknown**, not zero, and no readiness factor is emitted.
   - A declared-load change rolls every pod that mounts it, because a pod-template checksum covers the load.
7. **Readiness: both witnesses evaluate, and the worst wins.**
   - Fusion counts launches from its own subscription to `effector-events`. It does not read the projector's table.
   - It emits a supply factor per munition type that has a declared load, using the ammunition thresholds already in
     use.
   - The telemetry-consumables evaluation keeps running alongside it. A disagreement between the two witnesses
     surfaces as the worse of them, which is the point of keeping both.
8. **Launches are child tracks of the launcher, never assets.**
   - The launcher's detail view lists launches newest first, with expended, in-flight and unresolved counts.
   - The card renders nothing for an asset that has fired nothing.
   - Launches never appear in a fleet list, an asset count or an asset map layer.
9. **Only the labelled table is served.**
   - `effector_launch` is in the Electric publication and in `releasability.labeledTables`.
   - The declared-load table and the per-launcher counts view carry no labels. They are not published, so the PEP
     refuses them as unlabelable.
   - How "remaining of declared" reaches the browser is still open; see Named limits.

## Why

- **Disappearance is not an outcome, but a Detonation PDU is.** Phase 6 was parked because the upstream feed has no
  termination event: a track that disappears might have been intercepted, missed, self-destructed or simply been lost
  in transit. DIS carries `detonationResult`, which is an actual termination, so that reason does not apply to the
  DIS path.
- **Munitions are not assets.**
  - An in-flight munition counted as an asset inflates fleet counts and puts transient objects on asset layers.
  - Keying a launch by event, and labelling it from its launcher, keeps it out of every asset surface. It is still
    governed by the launcher's releasability.
- **Two independent witnesses are worth more than one reconciled number.**
  - Telemetry consumables report what the platform says it has.
  - Declared load minus launches is arithmetic from the exercise's own events.
  - Merging them would hide exactly the disagreement an operator should see.

## Consequences

- **Phase 6 runs on the DIS path.** Its failure counter is the `unresolved` terminal state, named for what it is:
  no termination seen. It is never counted as a failure.
- **The upstream feed path is unchanged.** It still models in-flight munitions as assets. Converging it onto child
  tracks is a separate change, recorded as a follow-up.
- **Predictions sum across projector instances** wherever two projectors share a store.
- **The reset clears launch counts with the rest of fusion's per-asset state.** No separate reset path is needed.

## Named limits

- **Remaining of declared is not shown yet.** The declared-load table carries no labels, so it cannot be served
  under the partition rule. Three ways to reach the browser are open:
  - a labelled per-launcher supply table, written by the projector;
  - serving the declared-load table by role;
  - fusion writing the remaining count into the launcher's logistics status.
- **There is no expected-empty entry for `effector_launch`.** A sparse entry needs proof that the producer is
  alive, and the existing liveness probe measures fusion, not the projector. A quiet exercise therefore cannot yet
  show an empty table as truthfully empty.
- **Compose cannot check the serving gate.**
  - The compose frontend reads Electric directly, with no PEP in front of it.
  - Electric keeps serving a table after it is dropped from the publication.
  - So the labelled-table gate is verified only on a deployment that runs the PEP.

## Related

- PLAN-munitions-taxonomy-phases.md, "Phase 6's blocker": parked 2026-07-14, un-parked here for the DIS path.
- ADR-0035: information honesty. Unknown is not red, and no outcome is invented from absence.
- ADR-0047: `asset_id` is opaque. An event id carries its own prefix so that it is never read as an asset id.
