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
