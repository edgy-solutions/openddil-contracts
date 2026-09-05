"""
Shared Restate-subscription bootstrap.

Each Restate service in OpenDDIL (cm-service, logistics-fusion-service,
future identity-resolver, ...) has its own subscription list, but the
register-with-Restate plumbing is identical. This module centralizes that
plumbing so:

  - The Phase 3 duplicate-pre-check (Restate 1.6 returns 200 on duplicate
    POST /subscriptions) lives in ONE place.
  - The `force: True` re-discovery flag stays consistent across services.
  - Future Restate admin-API changes update once, not once-per-service.

Each service wires a thin wrapper that calls `bootstrap_restate_service`
with its own subscription list — see
`openddil-cm-service/bootstrap/register_subscriptions.py` for an example.

Mounting:
  Containers mount this directory at `/app/openddil_bootstrap` (read-only)
  and add `/app` to PYTHONPATH so wrappers can
  `from openddil_bootstrap.restate_subscriptions import ...`.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

logger = logging.getLogger("openddil.bootstrap")


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Subscription:
    """One topic-to-handler binding.

    `topic`           — Kafka topic name the service consumes from.
    `handler`         — Restate handler path, e.g. "AssetCM/observe".
    `consumer_group`  — Kafka consumer group id (chosen by the service).
    """
    topic: str
    handler: str
    consumer_group: str


# ---------------------------------------------------------------------------
# Small HTTP helpers (stdlib only — no requests)
# ---------------------------------------------------------------------------
def _http_request(method: str, url: str, body: dict | None = None,
                   timeout: int = 10) -> tuple[int, bytes]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _wait_for(url: str, label: str, *,
                timeout_s: int,
                expected: tuple[int, ...] = (200, 204)) -> None:
    """Block until URL responds with one of the expected statuses or the
    timeout expires."""
    deadline = time.monotonic() + timeout_s
    last_err: str | None = None
    while time.monotonic() < deadline:
        try:
            code, _ = _http_request("GET", url, timeout=3)
            if code in expected:
                logger.info("%s ready at %s (HTTP %d)", label, url, code)
                return
            last_err = f"HTTP {code}"
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_err = str(exc)
        time.sleep(2)
    raise TimeoutError(
        f"{label} not ready at {url} within {timeout_s}s (last: {last_err})"
    )


# ---------------------------------------------------------------------------
# Restate admin operations
# ---------------------------------------------------------------------------
def register_service_deployment(*, restate_admin_url: str,
                                  service_endpoint: str,
                                  service_label: str) -> None:
    """Register the service's handler manifest with Restate.

    `force: True` re-fetches the discovery manifest. Required when handler
    signatures change (e.g., `event: dict` -> `event: bytes`) because
    Restate caches the prior manifest on the deployment_id; without force,
    POST is a silent no-op and the cached signature continues to drive
    input deserialization.
    """
    url = f"{restate_admin_url}/deployments"
    body = {"uri": service_endpoint, "force": True}
    code, payload = _http_request("POST", url, body, timeout=10)
    if code in (200, 201):
        logger.info("Registered %s deployment at %s", service_label, service_endpoint)
        return
    if code == 409:
        logger.info("%s deployment already registered at %s",
                    service_label, service_endpoint)
        return
    raise RuntimeError(
        f"Restate refused to register {service_label} deployment "
        f"(HTTP {code}): {payload.decode(errors='replace')[:500]}"
    )


def register_kafka_cluster(*, restate_admin_url: str,
                             cluster_name: str,
                             brokers: str) -> None:
    """Register a Kafka cluster under a logical name. Idempotent."""
    url = f"{restate_admin_url}/clusters"
    body = {"name": cluster_name, "bootstrap_servers": brokers}
    code, payload = _http_request("POST", url, body, timeout=10)
    if code in (200, 201):
        logger.info("Registered Kafka cluster %s -> %s", cluster_name, brokers)
        return
    if code == 409:
        logger.info("Kafka cluster %s already registered", cluster_name)
        return
    if code == 404:
        # Older Restate releases. Subscriptions carry bootstrap_servers inline.
        logger.info(
            "Restate has no /clusters endpoint at this version; "
            "subscriptions will carry bootstrap_servers inline"
        )
        return
    raise RuntimeError(
        f"Restate refused Kafka cluster registration (HTTP {code}): "
        f"{payload.decode(errors='replace')[:500]}"
    )


def list_existing_subscriptions(*, restate_admin_url: str) -> list[dict]:
    """Fetch the current subscription list from Restate's admin API."""
    url = f"{restate_admin_url}/subscriptions"
    code, payload = _http_request("GET", url, timeout=10)
    if code != 200:
        logger.warning(
            "Unable to list existing subscriptions (HTTP %d) — proceeding "
            "without dedup; manual cleanup may be required if duplicates "
            "accumulate", code,
        )
        return []
    try:
        data = json.loads(payload.decode("utf-8"))
        return data.get("subscriptions", [])
    except json.JSONDecodeError:
        logger.warning("Restate /subscriptions returned malformed JSON; "
                        "proceeding without dedup")
        return []


def create_subscription(sub: Subscription,
                          *, restate_admin_url: str,
                          cluster_name: str,
                          existing: list[dict]) -> None:
    """Create one Kafka -> handler subscription, skipping duplicates.

    Equivalence is by (source URI, sink URI, consumer group). Restate
    1.6 returns 200 on duplicate POST, so we MUST pre-check; relying on
    the server's response would silently leak duplicates and each Kafka
    message would be delivered N times to the same handler.
    """
    source = f"kafka://{cluster_name}/{sub.topic}"
    sink   = f"service://{sub.handler}"
    group  = sub.consumer_group

    for s in existing:
        if (s.get("source") == source
                and s.get("sink") == sink
                and (s.get("options") or {}).get("group.id") == group):
            logger.info(
                "Subscription already present (id=%s): %s -> %s (group=%s) "
                "— skipping create",
                s.get("id"), sub.topic, sub.handler, group,
            )
            return

    url = f"{restate_admin_url}/subscriptions"
    body = {
        "source":  source,
        "sink":    sink,
        "options": {
            "auto.offset.reset": "earliest",
            "group.id":          group,
        },
    }
    code, payload = _http_request("POST", url, body, timeout=10)
    if code in (200, 201):
        logger.info("Subscription created: %s -> %s (group=%s)",
                    sub.topic, sub.handler, group)
        return
    if code == 409:
        # Older Restate releases. Kept for compatibility.
        logger.info("Subscription already exists (HTTP 409): %s -> %s",
                    sub.topic, sub.handler)
        return
    raise RuntimeError(
        f"Failed to create subscription {sub.topic} -> {sub.handler} "
        f"(HTTP {code}): {payload.decode(errors='replace')[:500]}"
    )


# ---------------------------------------------------------------------------
# Pruning — the half that was missing (UD-12)
# ---------------------------------------------------------------------------
# `create_subscription` above answers "what should exist that does not?".
# Nothing answered "what exists that should not?", and the two are not the
# same question. Registration alone can only ever grow the set, so a
# subscription retired from the desired list — an edge that gained a tier
# node, say — simply stayed, and kept consuming.
#
# At the root that was invisible: `hook-restate-wipe.yaml` deletes the
# Restate PVC on every upgrade when `restate.ephemeralOnUpgrade` is true, so
# the set was rebuilt from empty each time and retirement appeared to work.
# It was wipe-and-recreate doing the job, under a flag that knows nothing
# about tiers and which the chart documents as `false` for prod-like use.
# Set it false and retirement silently stops.
#
# Two distinct things get pruned, and the second was the observed defect:
#   STRAYS     — owned by this bootstrap, absent from its desired set.
#   DUPLICATES — the same (source, sink, group) present more than once.
# ---------------------------------------------------------------------------
def _existing_key(s: dict) -> tuple:
    """Identity of an existing subscription, matching create's pre-check."""
    return (s.get("source"),
            s.get("sink"),
            (s.get("options") or {}).get("group.id"))


def group_prefix_owner(*prefixes: str):
    """Ownership predicate: this bootstrap owns a subscription if its
    consumer group starts with one of `prefixes`.

    Ownership has to be NARROWER than "everything on this Restate", because
    cm-service and logistics-fusion bootstrap independently against the same
    root Restate. An owner of "everything" would have each delete the
    other's subscriptions on every upgrade, alternately.

    Group prefix is the right scope precisely because it does NOT mention
    the cluster: a subscription left behind on a retired edge cluster is
    exactly what must be prunable, and a cluster-scoped owner could never
    see it — the bootstrap no longer has that cluster in its list.
    """
    def _owns(s: dict) -> bool:
        gid = (s.get("options") or {}).get("group.id") or ""
        return any(gid.startswith(pfx) for pfx in prefixes)
    return _owns


def delete_subscription(sub_id: str, *, restate_admin_url: str) -> bool:
    url = f"{restate_admin_url}/subscriptions/{sub_id}"
    code, payload = _http_request("DELETE", url, timeout=10)
    if code in (200, 202, 204, 404):
        return True
    logger.warning("Failed to delete subscription %s (HTTP %d): %s",
                    sub_id, code, payload.decode(errors="replace")[:200])
    return False


def prune_subscriptions(*, restate_admin_url: str,
                          desired: list[tuple[str, "Subscription"]],
                          owns,
                          scope_label: str) -> int:
    """Delete owned subscriptions that are strays or duplicates.

    `desired` is the COMPLETE set for this bootstrap as (cluster_name, sub)
    pairs — complete, because anything owned and not named here is deleted.
    Call it once, after every cluster has been registered; calling it inside
    a per-cluster loop would delete the clusters not yet processed.

    Returns the number deleted. Never raises: a failed prune leaves a
    duplicate, which is the condition we are already in, whereas raising
    would fail a bootstrap whose registrations all succeeded.
    """
    want = {
        (f"kafka://{cluster}/{sub.topic}",
         f"service://{sub.handler}",
         sub.consumer_group)
        for cluster, sub in desired
    }
    existing = list_existing_subscriptions(restate_admin_url=restate_admin_url)
    if not existing:
        # Either genuinely empty or the list call failed (it warns and
        # returns []). Pruning nothing is the safe reading of both.
        logger.info("[%s] prune: nothing to examine", scope_label)
        return 0

    seen: dict[tuple, str] = {}
    strays: list[tuple[str, str, str]] = []   # (id, key-ish, reason)
    for s in existing:
        if not owns(s):
            continue
        key = _existing_key(s)
        sid = s.get("id") or ""
        if key not in want:
            strays.append((sid, str(key[0]), "retired from the desired set"))
        elif key in seen:
            strays.append((sid, str(key[0]), f"duplicate of {seen[key]}"))
        else:
            seen[key] = sid

    if not strays:
        logger.info("[%s] prune: %d owned subscription(s), all desired and "
                    "unique — nothing to remove", scope_label, len(seen))
        return 0

    deleted = 0
    for sid, source, reason in strays:
        logger.warning("[%s] prune: deleting %s (%s) — %s",
                        scope_label, sid, source, reason)
        if delete_subscription(sid, restate_admin_url=restate_admin_url):
            deleted += 1
    logger.info("[%s] prune: removed %d of %d candidate(s); %d kept",
                scope_label, deleted, len(strays), len(seen))
    return deleted


# ---------------------------------------------------------------------------
# Top-level: bootstrap one Restate service end-to-end.
# ---------------------------------------------------------------------------
def bootstrap_restate_service(
    *,
    service_label: str,
    restate_admin_url: str,
    service_endpoint: str,
    kafka_cluster_name: str,
    kafka_brokers: str,
    subscriptions: list[Subscription],
    timeout_s: int = 120,
) -> int:
    """Idempotent registration of a Restate service + its Kafka subscriptions.

    Returns 0 on success; raises on failure.

    Steps:
      1. Wait for Restate admin API.
      2. Wait for the service's HTTP /discover endpoint.
      3. Register the deployment (force=True for handler-signature changes).
      4. Register the Kafka cluster.
      5. List existing subscriptions; create each new one (dedup pre-check).
    """
    logger.info(
        "[%s] Bootstrap starting — restate_admin=%s endpoint=%s kafka=%s subs=%d",
        service_label, restate_admin_url, service_endpoint, kafka_brokers,
        len(subscriptions),
    )

    _wait_for(f"{restate_admin_url}/health", "Restate admin",
                timeout_s=timeout_s)
    _wait_for(f"{service_endpoint}/discover", f"{service_label} endpoint",
                timeout_s=timeout_s, expected=(200, 405, 415))

    register_service_deployment(
        restate_admin_url=restate_admin_url,
        service_endpoint=service_endpoint,
        service_label=service_label,
    )
    register_kafka_cluster(
        restate_admin_url=restate_admin_url,
        cluster_name=kafka_cluster_name,
        brokers=kafka_brokers,
    )

    existing = list_existing_subscriptions(restate_admin_url=restate_admin_url)
    if existing:
        logger.info("[%s] Found %d existing subscription(s); will dedupe",
                    service_label, len(existing))
    for sub in subscriptions:
        create_subscription(sub,
                             restate_admin_url=restate_admin_url,
                             cluster_name=kafka_cluster_name,
                             existing=existing)

    logger.info("[%s] Bootstrap complete (%d subscription(s) configured)",
                service_label, len(subscriptions))
    return 0
