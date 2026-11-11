# ADR-0060 — Observability: a collector per tier, one trace per journey, opaque ids only

## Status

**PROPOSED — 2026-11-11. Design only. Nothing here is built.** Ordered 2026-11-11. Aligns by concept only: no
configuration, attribute or field is named from a specification as binding.
**Builds on:** ADR-0059 §7 (the exporters, per-tier alerting, remote write upward); ADR-0053 (provenance on every
side of a disagreement); ADR-0029 (the releasability label); ADR-0046 (the maintenance doors, events out and actions
in).
**Read at:** OpenDDIL working trees of 2026-11-11. Line numbers move with them. These are reads, not runs.

## Findings first

1. **Nothing emits OpenTelemetry.** No service imports it. Nothing sets an OTLP endpoint, and no collector is deployed.
   No `traceparent` or `tracestate` is read or written anywhere, and no stream processor has a tracer.
2. **Seven services expose Prometheus metrics, and nothing scrapes them** (ADR-0059 §7.5). The chart deploys no
   Prometheus and no Alertmanager.
3. **No correlation id crosses either door as a header.** The forwarder sends a content type and a bearer token only
   (`openddil:openddil-demo/egress/forwarder.py:875-878`). The ids that cross are in bodies:
   - the envelope's key and event id;
   - the destination's case id, read back from a 2xx answer and checked against the expected id;
   - the discrepancy door's 202, which returns the event id, and its 4xx, which returns the decision id as a reference.
4. **What each door logs per record.**

   | Door | Per-record line | Ids | Content or labels |
   |---|---|---|---|
   | Egress forwarder | one JSON line per outcome (`forwarder.py:578-587`) | key, kind, status, outcome, case id | none |
   | Egress forwarder, refused | a warning per 4xx (`forwarder.py:935-938`) | route | **up to 300 bytes of the destination's response body** (`:111`) |
   | Egress gate | one `DECISION` line per decision, admit and refuse (`openddil:openddil-demo/egress/gate.py:699-701`) | decision id, key, destination | **the releasability label**: originator nation, releasable-to, destination nations (`gate.py:219-236`) |
   | Egress gate, refused | the decision's `detail` | — | a schema refusal's detail is the validator's first message (`gate.py:666-668`, `kinds.py:35-37`), which can quote a value from the record; a classification refusal names the marking (`gate.py:670-673`) |
   | Egress intake | one `INTAKE_DECISION` line (`openddil:openddil-demo/egress/intake.py:810`) | decision id, key, kind, answered id | approvers and on-behalf-of by subject name; free-text `detail` (`intake.py:407-423`) |
   | Discrepancy door (gateway) | one `DECISION` line (`openddil:openddil-demo/gateway/pep.py:402-416`), and a refusal warning (`pep.py:2108-2109`) | decision id, event id, asset id, fault code | subject name |

5. **Decision records ride the log stream.** The gate's and intake's decision records are log lines. A collector that
   forwarded logs upward would carry the labels and details in the table with them.

## Decision

1. **OpenTelemetry, by concept, is the instrumentation and per-tier collection layer.** Its Collector is "a
   vendor-agnostic way to receive, process and export telemetry data", built from receivers, processors and exporters
   (the Collector's documentation, read 2026-11-11).
2. **A collector per tier.** It exports locally: metrics to the tier's own Prometheus, and logs and traces to the
   tier's own stores. It forwards upward over OTLP through a persistent queue. The exporter helper's documentation
   (read 2026-11-11) describes a queue kept in a storage extension, picked up again after a restart. A cut tier keeps
   its own telemetry, and forwards what queued when the link returns. The queue has a bound. When it is full, data is
   dropped, and the drop is counted.
3. **Alertmanager is unchanged.** Alerting stays per tier, as ADR-0059 §7.6 sets it out, with link-severed inhibition.
   No collector replaces it.
   - **Open: one upward path for metrics.** ADR-0059 §7.6 sends metrics up by remote write, and this record forwards
     telemetry up over OTLP. This record proposes remote write for metrics, and OTLP for traces and logs, and asks for
     the ruling.
4. **One trace per journey, by W3C Trace Context.** That is a W3C Recommendation of 2021-11-23, read. It defines two
   headers: `traceparent`, the request's position in its trace, and `tracestate`, vendor data beside it.
   - A filing at the discrepancy door continues as one trace through to its release at the egress gate. Across the
     broker the context rides in the record's headers, not its body.
   - The forwarder sends the context on every forward. Intake continues the trace when the answer comes back.
   - iagent is asked to propagate it through its workflow and back on the completed record (a packet to iagent's
     architect).
5. **Spans and logs carry opaque ids only.** They never carry record content or labels. The specification itself bars
   personally identifiable information from `tracestate`, and confines both headers to correlation.
   - **Redaction processor.** Each collector keeps attributes on an allow list of id fields and drops the rest before
     any exporter.
   - **The test.** It plants a releasability label, a classification marking and a free-text record value in spans
     and logs, and fails if any of them reaches an exporter.
   - **Today's lines that break the rule** (finding 4) are rows:
     - the forwarder's rejection body;
     - the gate's label and detail;
     - intake's detail and subject names.
   - **Open:** whether a subject name is an opaque id, or must be the token's subject identifier.
6. **Decision records stay records.** A decision record keeps its label and detail. It is the audit, and moves off
   the log stream to its own sink. The log line names the decision id only.
7. **Trace ids are correlated from decision records, and are never provenance.** A decision record may carry the trace
   id, so a reader can open the trace from the decision. Nothing decides from a trace. A trace can be sampled, dropped
   or arrive late. Provenance stays on the record: its producing tier, and observed, declared or derived (ADR-0053).

## Rows

In `FOLLOW-UPS.md`:
- a collector per tier with a persistent upward queue, and the ruling on metrics' upward path;
- trace context through the doors and the broker, with iagent's propagation;
- the opaque-ids rule: the redaction processor, its test, and the three lines that break it;
- decision records off the log stream, carrying the trace id.

## Consequences

- **Positive:** a filing can be followed to its release across tiers and into iagent, without the trace carrying what
  was released. Each tier keeps its telemetry when cut.
- **Negative:** a collector per tier, and a queue to size. Four doors change what they log. iagent must propagate the
  context, or the trace stops at the door.
- **Neutral:** the exporters and Alertmanager stay as they are.

## What this does not establish

- Nothing is built, run or measured.
- No collector configuration, sampling rate or queue size.
- Whether every jsonschema refusal message quotes a value. It was not run here.
- The OTLP specification and the semantic conventions: not read.

## Related

- [ADR-0059](ADR-0059-condition-monitoring-bit-and-usage-alignment.md) §7: exporters, alerting and remote write.
- [ADR-0053](ADR-0053-logistics-cyber-detection-as-surfaced-disagreement.md): provenance.
- [ADR-0029](ADR-0029-coalition-releasability-abac-enforcement.md): the releasability label.
- [ADR-0046](ADR-0046-maintenance-bridge-events-out-actions-in.md): the maintenance doors.
