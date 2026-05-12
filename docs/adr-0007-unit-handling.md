# ADR-0007: Unit Handling Strategy

## Status
Approved

## Context
Tactical telemetry comes from diverse sources (DIS, Link-16, AIS) using various unit conventions (Fahrenheit vs Celsius, Knots vs m/s). Historically, ingestion pipelines performed "Eager Conversion" to a common SI standard. However, this is lossy, makes debugging harder, and wastes CPU cycles for algorithms that might naturally operate in the source units.

## Decision
We will **Carry Units and Defer Conversion**.

1. **Ingestion (Bloblang)**: The transformation layer purely reshapes data and attaches a unit label (using UCUM symbols like `[degF]` or `Cel`). It performs **zero arithmetic**.
2. **Persistence (Protobuf)**: Telemetry values are stored as `Quantity` messages containing both `value` and `unit`.
3. **Computation (Algorithms)**: Conversion is handled "Just-In-Time" at the algorithm layer using a physical quantities library (e.g., `pint`). 

## Consequences
- **Pros**: Algorithms are portable across unit conventions. The transformation layer stays simple and operator-editable without code changes. Data provenance is preserved.
- **Cons**: Every algorithm developer must adhere to the `pint` discipline. Bare-float comparisons are strictly forbidden.
- **Rejected Alternatives**: Eager SI conversion at ingest was rejected as being too inflexible and error-prone for a multi-ontology mesh.

## Verification
- **Truth Serum Test**: Sending `200 K` (cold) must not fire an anomaly that `200 F` (hot) would fire, even if the numerical value (200) is identical.

## Related
- **ADR-0013** (Physical Quantity Consistency, 2026-05-12) extends this rule
  from sustainment scalars to every primary physical quantity in the Silver
  schema (angles, positions, velocities). The `_deg`/`_m` bare-double field
  shapes were a violation of ADR-0007's intent; ADR-0013 migrates them to
  `Quantity { value, unit }` form.
