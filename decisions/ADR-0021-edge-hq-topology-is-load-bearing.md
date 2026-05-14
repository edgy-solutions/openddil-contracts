# ADR-0021: The Edge→HQ Topology Is Load-Bearing

## Status

Accepted — 2026-05-14

## Context

OpenDDIL's central value proposition is DDIL operation: the edge node
keeps working when the link to higher echelon is degraded or severed, and
data queued at the edge flows through when the link is restored. The
edge→HQ split — an edge tier that produces and buffers, a transport hop
that can be cut, an HQ tier that consumes — is not an implementation
detail. **It is the architecture the product exists to demonstrate.**

During Phase 4a/4b this split was quietly collapsed. The Phase 4a backend
wiring stood up a single `postgres-hq` and a single `openddil-projector`
that consumes `redpanda-edge` and writes `postgres-hq` directly, in the
same compose, with no transport hop between them. The Phase 4b UI read
everything from that one Postgres via ElectricSQL. This was an
implementation convenience — it made the read-path wiring simpler — and
it was never a deliberate decision. It was a side effect of building the
projector the shortest way.

The cost surfaced in Phase 4c. The "REDPANDA EDGE BUFFER" counter read 0
after the stack had been up for hours. Investigation found the whole DDIL
sever/buffer/restore mechanic was unwired: the edge→HQ Kafka bridge config
existed as a file but no service ran it, `redpanda-hq` was an orphaned
broker nothing produced to, and toxiproxy started without `-config` so
the `hq-link` proxy did not exist at runtime. The buffer counters were
client-side simulations. There was no topology to buffer across, because
4a/4b had collapsed it.

Phase 4c.5 restored it: the `edge-hq-bridge` service runs the bridge
config, toxiproxy loads its config so `hq-link` is real, and — the
non-obvious fix — `redpanda-hq` now advertises `toxiproxy:8474` as its
broker address so produce traffic actually routes through the proxy.

## Decision

**The edge→HQ topology is load-bearing architecture. It must remain
wired: an edge tier, a transport hop that can be severed, an HQ tier.
Any future simplification that collapses it is a deliberate architectural
decision, recorded as an ADR — never a side effect of building something
else the short way.**

Concretely, the following must stay true (or be changed by explicit
decision):

- An edge→HQ transport hop exists and is severable. Today: the
  `edge-hq-bridge` service consuming `redpanda-edge` under the
  `bridge-group` consumer group and forwarding through the toxiproxy
  `hq-link` proxy to `redpanda-hq`.
- The real edge-buffer depth is observable. Today: `bridge-group`
  consumer-group lag, surfaced via `edge_buffer_status` and ElectricSQL.
- Severing the hop genuinely stops data — it is not a no-op or a delay.
  Today: disabling the `hq-link` proxy (a total sever), not a downstream
  timeout toxic (which only delays the ack and lets the produce land).

### The runtime-verification lesson

Wiring the components is not the same as the components doing the thing.
If Phase 4c.5 had fixed only the two visible issues — the missing
toxiproxy `-config` and the orphaned bridge service — the link toggle
would have hit a real proxy API, the proxy state would have really
changed, and the buffer counter would still have stayed at zero: every
Kafka produce was routing **direct to `redpanda-hq:19092`**, ignoring the
proxy, because a Kafka client bootstraps through a broker and then
connects directly to whatever address that broker *advertises*. That
would have been a more convincing fake than the client-side simulation,
because the API calls would have been real.

It was caught only by running the sever and checking whether records
still landed at `redpanda-hq` while the proxy was "severed" — they did,
all of them. The same discipline distinguished a `downstream` timeout
toxic (delays the ack, the produce still lands) from disabling the proxy
(a total sever). **Topology claims are verified by running the sever and
confirming data actually stops — not by confirming the wiring exists.**

## Known simplification: single-hop topology

The current topology models **one** edge→HQ hop. There is no distinct
regional tier in the compose — `redpanda-edge` → `edge-hq-bridge` →
`redpanda-hq` is the whole transport path. Consequently **all three
header buffer widgets (maintainer, regional, HQ) view the same
`bridge-group` lag, relabeled per role.** The regional and HQ buffer
numbers move in lockstep because they are the same number.

A real multi-echelon topology (edge → regional → HQ) would have distinct
per-hop buffers — an edge→regional bridge and a regional→HQ bridge, each
with its own consumer-group lag — and the three views would show
genuinely different numbers. That is a deliberate future decision, not a
bug. This note exists so no one later mistakes the lockstep regional/HQ
numbers for a wiring error.

## Consequences

**Pros**

- The DDIL mechanic — OpenDDIL's whole reason to exist — is demonstrable
  as a live behavior: sever the hop, watch the real buffer climb; restore
  it, watch it drain.
- The topology is now explicit and protected. A future "let's just have
  one Postgres" simplification has to argue with this ADR first.

**Cons**

- More moving parts in the compose: the `edge-hq-bridge` service, the
  `redpanda-hq` broker, the toxiproxy `hq-link` proxy, and the
  `edge_buffer_status` table + projector monitor all exist specifically
  to keep the topology real and observable. They are load-bearing, not
  optional.
- The `redpanda-hq` broker advertising `toxiproxy:8474` is a non-obvious
  configuration. It is commented at the compose site, but it is the kind
  of thing that looks wrong to someone who does not know why.

**Rejected alternatives**

- *Leave the collapsed single-tier topology and simulate the buffer in
  the UI.* Rejected: it makes the product's central value proposition a
  lie on screen. ADR-0017's "no orphan mocks" principle applied to the
  one mechanic that most needs to be real.
- *Wire the bridge + toxiproxy but skip the broker-advertised-address
  fix.* Rejected because it does not work — it is the convincing-fake
  failure mode described above.

## Related

- ADR-0019 — Single Kafka→Postgres Projector. The projector is per-tier;
  this ADR is about the tiers existing in the first place.
- ADR-0017 — UI Mock Components Self-Identify. The buffer counter was the
  one mechanic that most needed to be real rather than a marked mock.
- ADR-0014 — Restate vs Faust placement. Same spirit: write the
  architectural rule down so it is not relitigated or eroded by
  convenience.

## Notes for future maintainers

- The topology lives in `openddil-demo/docker-compose.yml`:
  `edge-hq-bridge` (runs `redpanda-connect.yaml`), `redpanda-hq` (note
  its `--advertise-kafka-addr`), `toxiproxy` (note its `-config` flag).
- The buffer readout: `openddil-projector/src/edge_buffer_monitor.py`
  writes `edge_buffer_status`; the UI reads it via `useEdgeBuffer`.
- Phase 4d's Playwright disconnect/reconnect tests (32/33) depend on this
  mechanic being real — they cannot be written against a simulated
  buffer. If they ever fail, check the topology is still wired before
  assuming a UI regression.
