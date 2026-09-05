"""
test_prune_subscriptions.py — the deleting half of the bootstrap (UD-12).

These tests exist because `prune_subscriptions` is the only part of the
bootstrap that DESTROYS state, and it was added in response to a defect
that nothing had reported for as long as it had existed. The cases below
are chosen for the two ways a prune goes wrong, which are opposite:

  * it deletes too little  — the stray survives and UD-10 returns
  * it deletes too much    — a live subscription disappears and a tier
                              or an edge silently stops being consumed

The second is worse and quieter, so most of these assert what must SURVIVE.
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from bootstrap.restate_subscriptions import (  # noqa: E402
    Subscription,
    group_prefix_owner,
    prune_subscriptions,
)
import bootstrap.restate_subscriptions as rs  # noqa: E402


def _sub(cluster: str, topic: str, handler: str, group: str, sid: str) -> dict:
    return {"id": sid,
            "source": f"kafka://{cluster}/{topic}",
            "sink": f"service://{handler}",
            "options": {"group.id": group, "auto.offset.reset": "earliest"}}


class _Fake:
    """Stands in for Restate's admin API; records DELETEs."""

    def __init__(self, existing):
        self.existing = existing
        self.deleted: list[str] = []

    def __call__(self, method, url, body=None, timeout=10):
        if method == "GET" and url.endswith("/subscriptions"):
            import json
            return 200, json.dumps({"subscriptions": self.existing}).encode()
        if method == "DELETE":
            self.deleted.append(url.rsplit("/", 1)[-1])
            return 204, b""
        raise AssertionError(f"unexpected {method} {url}")


def _run(monkeypatch, existing, desired, owns):
    fake = _Fake(existing)
    monkeypatch.setattr(rs, "_http_request", fake)
    n = prune_subscriptions(restate_admin_url="http://x",
                             desired=desired, owns=owns, scope_label="test")
    return fake, n


CM = "cm-service-"
CM_OBSERVE = ("raw-sensor-stream", "AssetCM/observe")


def test_duplicates_collapse_to_one(monkeypatch):
    """The observed defect: same triple twice, one copy must remain.

    Deleting BOTH would stop consumption entirely, which is why this
    asserts the survivor and not merely the deletion.
    """
    a = _sub("openddil-edge-01", *CM_OBSERVE, f"{CM}silver-edge-01", "id-a")
    b = _sub("openddil-edge-01", *CM_OBSERVE, f"{CM}silver-edge-01", "id-b")
    desired = [("openddil-edge-01",
                 Subscription(*CM_OBSERVE, f"{CM}silver-edge-01"))]
    fake, n = _run(monkeypatch, [a, b], desired, group_prefix_owner(CM))
    assert n == 1
    assert fake.deleted == ["id-b"], "must keep the first, delete the extra"


def test_retired_edge_is_pruned(monkeypatch):
    """UD-10's retirement made real: edge-01 gained a tier node and left
    the desired set, so the root's subscription for it must go."""
    keep = _sub("openddil-edge-02", *CM_OBSERVE, f"{CM}silver-edge-02", "keep")
    gone = _sub("openddil-edge-01", *CM_OBSERVE, f"{CM}silver-edge-01", "gone")
    desired = [("openddil-edge-02",
                 Subscription(*CM_OBSERVE, f"{CM}silver-edge-02"))]
    fake, n = _run(monkeypatch, [keep, gone], desired, group_prefix_owner(CM))
    assert fake.deleted == ["gone"]


def test_other_services_subscriptions_are_untouched(monkeypatch):
    """cm-service and fusion bootstrap independently against one Restate.

    An owner of "everything present" would have them delete each other's
    subscriptions on alternating upgrades -- a self-inflicted outage that
    would look like flapping, not like a bug in a bootstrap.
    """
    mine = _sub("openddil-edge-01", *CM_OBSERVE, f"{CM}silver-edge-01", "mine")
    theirs = _sub("openddil-edge-01", "raw-sensor-stream",
                   "AssetLogistics/on_proprietary_update",
                   "fusion-service-silver-edge-01", "theirs")
    desired = [("openddil-edge-01",
                 Subscription(*CM_OBSERVE, f"{CM}silver-edge-01"))]
    fake, n = _run(monkeypatch, [mine, theirs], desired, group_prefix_owner(CM))
    assert fake.deleted == [], "fusion's subscription is not cm-service's to delete"
    assert n == 0


def test_steady_state_deletes_nothing(monkeypatch):
    """Non-vacuity in the other direction: on an already-correct store the
    prune must be a no-op. A prune that deletes on every run would churn
    consumer groups on every upgrade."""
    existing = [
        _sub("openddil-edge-02", *CM_OBSERVE, f"{CM}silver-edge-02", "a"),
        _sub("openddil-edge-03", *CM_OBSERVE, f"{CM}silver-edge-03", "b"),
    ]
    desired = [("openddil-edge-02", Subscription(*CM_OBSERVE, f"{CM}silver-edge-02")),
               ("openddil-edge-03", Subscription(*CM_OBSERVE, f"{CM}silver-edge-03"))]
    fake, n = _run(monkeypatch, existing, desired, group_prefix_owner(CM))
    assert fake.deleted == [] and n == 0


def test_unreadable_list_prunes_nothing(monkeypatch):
    """`list_existing_subscriptions` warns and returns [] when the admin
    API is unreachable. Pruning must then do NOTHING -- an empty read is
    not evidence of an empty store, and treating it as one would delete
    every subscription exactly when Restate is unhealthy."""
    class _Broken(_Fake):
        def __call__(self, method, url, body=None, timeout=10):
            if method == "GET":
                return 503, b"unavailable"
            return super().__call__(method, url, body, timeout)

    fake = _Broken([])
    monkeypatch.setattr(rs, "_http_request", fake)
    n = prune_subscriptions(restate_admin_url="http://x",
                             desired=[("openddil-edge-02",
                                        Subscription(*CM_OBSERVE, f"{CM}silver-edge-02"))],
                             owns=group_prefix_owner(CM), scope_label="test")
    assert n == 0 and fake.deleted == []


def test_empty_desired_set_deletes_everything_owned(monkeypatch):
    """Documents the sharp edge rather than defending against it: the
    desired list is authoritative, so an incomplete list is a deletion.
    This is why fusion's HQ subscriptions are explicitly appended to its
    desired set -- omitting them would silently cut the root off from
    every tier-managed edge's CM state."""
    existing = [_sub("openddil-edge-02", *CM_OBSERVE, f"{CM}silver-edge-02", "x")]
    fake, n = _run(monkeypatch, existing, [], group_prefix_owner(CM))
    assert fake.deleted == ["x"] and n == 1
