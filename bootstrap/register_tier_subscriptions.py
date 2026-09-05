"""
tier-node bootstrap — registers a tier's Restate services and subscriptions.

WHY THIS FILE EXISTS AT ALL (UD-12)
-----------------------------------
The tier's bootstrap used to be a shell script in the Job that POSTed each
subscription with `curl`, unconditionally. It was a second implementation of
work this library already did, and it lost the part that mattered: the
dedup pre-check. Restate 1.6 answers a duplicate POST with 200, so every
helm upgrade added another copy of all seven subscriptions. Measured on the
lab tier after two upgrades: **14 subscriptions over 7 distinct
(source, sink, group) triples, every one duplicated exactly x2.**

Nothing reported it, and nothing would have. The duplicates share a consumer
group, so on a one-partition topic one member holds the partition and the
other idles; output stays correct while the set grows by one copy per
upgrade. What it silently rebuilds is UD-10's own mechanism inside the tier
-- a group with a spare member and a partition to hand over on any
membership change.

The root path never showed this because it used the library, whose
`create_subscription` pre-checks. The divergence was not a decision; it was
a reimplementation in a language with no JSON parser to hand.

*The rule this file exists to keep:* the tier is not a different kind of
node, so its bootstrap is not a different kind of program.
"""
from __future__ import annotations

import logging
import os
import sys

from openddil_bootstrap.restate_subscriptions import (
    Subscription,
    _wait_for,
    create_subscription,
    group_prefix_owner,
    list_existing_subscriptions,
    prune_subscriptions,
    register_service_deployment,
)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("openddil.tier.bootstrap")

TIER_ID          = os.getenv("TIER_ID", "")
RESTATE_ADMIN_URL = os.getenv("RESTATE_ADMIN_URL", "")
CM_ENDPOINT      = os.getenv("TIER_CM_ENDPOINT", "")
FUSION_ENDPOINT  = os.getenv("TIER_FUSION_ENDPOINT", "")
TIMEOUT_S        = int(os.getenv("TIER_BOOTSTRAP_TIMEOUT_S", "180"))

# The tier's Restate names this cluster in its own restate.toml, scoped to
# this tier's broker alone, so a subscription here cannot resolve to a
# sibling tier's cluster. Nothing to register; only to reference.
CLUSTER = f"openddil-{TIER_ID}"


def _subscriptions(tier_id: str) -> list[Subscription]:
    """The tier's COMPLETE desired set.

    Complete is load-bearing: `prune_subscriptions` deletes anything owned
    and not named here, so an omission is a deletion.
    """
    return [
        Subscription("raw-sensor-stream", "AssetCM/observe",
                      f"cm-service-silver-{tier_id}"),
        Subscription("cm-events", "AssetCM/apply_cm_event",
                      f"cm-service-cm-events-{tier_id}"),
        Subscription("raw-sensor-stream", "AssetLogistics/on_proprietary_update",
                      f"fusion-service-silver-{tier_id}"),
        Subscription("asset-telemetry-windows", "AssetLogistics/on_telemetry_window",
                      f"fusion-service-windows-{tier_id}"),
        Subscription("derived-sustainment", "AssetLogistics/on_derived_sustainment",
                      f"fusion-service-derived-{tier_id}"),
        Subscription("asset-capability-snapshot", "AssetLogistics/on_capability_snapshot",
                      f"fusion-service-capability-{tier_id}"),
        Subscription("asset-cm-state", "AssetLogistics/on_cm_state_change",
                      f"fusion-service-cm-state-{tier_id}"),
    ]


def main() -> int:
    missing = [n for n, v in (("TIER_ID", TIER_ID),
                               ("RESTATE_ADMIN_URL", RESTATE_ADMIN_URL),
                               ("TIER_CM_ENDPOINT", CM_ENDPOINT),
                               ("TIER_FUSION_ENDPOINT", FUSION_ENDPOINT)) if not v]
    if missing:
        # Fail loudly rather than bootstrapping a tier called "" against a
        # cluster called "openddil-".
        raise RuntimeError(f"tier bootstrap missing required env: {missing}")

    logger.info("[tier %s] bootstrap starting — restate=%s cluster=%s",
                TIER_ID, RESTATE_ADMIN_URL, CLUSTER)

    _wait_for(f"{RESTATE_ADMIN_URL}/deployments", f"tier {TIER_ID} restate",
                timeout_s=TIMEOUT_S)
    for label, endpoint in (("tier-fusion", FUSION_ENDPOINT),
                             ("tier-cm", CM_ENDPOINT)):
        _wait_for(f"{endpoint}/discover", f"{label}[{TIER_ID}]",
                    timeout_s=TIMEOUT_S, expected=(200, 405, 415))
        register_service_deployment(
            restate_admin_url=RESTATE_ADMIN_URL,
            service_endpoint=endpoint,
            service_label=f"{label}[{TIER_ID}]",
        )

    desired = _subscriptions(TIER_ID)
    existing = list_existing_subscriptions(restate_admin_url=RESTATE_ADMIN_URL)
    logger.info("[tier %s] %d existing subscription(s) before reconcile",
                TIER_ID, len(existing))
    for sub in desired:
        create_subscription(sub,
                             restate_admin_url=RESTATE_ADMIN_URL,
                             cluster_name=CLUSTER,
                             existing=existing)

    # Every subscription on a tier's Restate is this bootstrap's, but scope
    # by group prefix anyway: it is the same ownership rule the root uses,
    # and a tier that later hosts something else should not have it deleted
    # by a bootstrap that assumed the whole store.
    removed = prune_subscriptions(
        restate_admin_url=RESTATE_ADMIN_URL,
        desired=[(CLUSTER, s) for s in desired],
        owns=group_prefix_owner("cm-service-", "fusion-service-"),
        scope_label=f"tier {TIER_ID}",
    )

    final = list_existing_subscriptions(restate_admin_url=RESTATE_ADMIN_URL)
    logger.info("[tier %s] bootstrap complete — %d desired, %d pruned, "
                "%d present", TIER_ID, len(desired), removed, len(final))
    return 0


if __name__ == "__main__":
    sys.exit(main())
