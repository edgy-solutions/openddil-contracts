# ADR-0008: CloudEvents Binding Mode

## Status
Approved

## Context
Anomaly alerts produced by the edge agents need to be consumed by various tactical interfaces and long-term stores. We have adopted the CloudEvents (v1.0) standard to ensure interoperability. We must decide between "Structured" binding (everything in the payload) and "Binary" binding (metadata in Kafka headers, data in the payload).

## Decision
We will use **Structured Mode Binding**.

- The entire CloudEvent (metadata + data) will be serialized as a single JSON blob in the Kafka record value.
- The Kafka key will remain the `asset_id` for partition affinity and compaction.

## Rationale
- **Simplicity**: Structured mode is easier to debug and "cat" from the command line without specialized header-aware tools.
- **Portability**: The event is self-contained. It can be moved from Kafka to S3 or a database without losing its CloudEvent identity.
- **Tooling**: Most standard Redpanda/Kafka clients handle JSON values natively without extra header configuration.

## Consequences
- **Pros**: Lower barrier to entry for new consumer agents.
- **Cons**: Slightly higher overhead as metadata is repeated in the body. If we reach extreme throughput (>100k events/sec), we may reconsider Binary Mode to allow routing via headers without deserializing the body.
