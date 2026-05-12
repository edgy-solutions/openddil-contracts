# ADR-0013: Physical Quantity Consistency Across the Silver Schema

## Status

Accepted — 2026-05-12

## Context

ADR-0007 ("Carry Units, Defer Conversion") established that physical quantities
in the Silver schema are tagged with their source unit and converted lazily by
algorithms. Phase 1 implemented this for temperature, voltage, pressure, fuel,
and other sustainment scalars via the `Quantity { value, unit }` message.

The rest of the schema — angles, positions, velocity-as-Vector3 — was written
quickly and never revisited against ADR-0007. Those fields use bare `double`s
with the unit baked into the field name (`yaw_deg`, `x_m`, `lat_deg`,
`east_m`). Vector3 has a `unit` string field but it's optional and inconsistently
populated.

Phase 2 surfaced the latent inconsistency as a real bug: the DIS Bloblang
mapping puts radians into `yaw_deg` because

1. DIS emits orientation in radians natively.
2. ADR-0007 forbids math in the Bloblang layer.
3. The proto field name lies about the unit.

The Silver event therefore claims degrees but carries radians. No algorithm
consumes orientation yet, so the bug is silent. **The CM service in Phase 3
will be the first heavy reader of Silver kinematics; that is the wrong time to
discover this.**

## Decision

Migrate every primary physical-quantity field in the Silver schema to use the
`Quantity` (or already-unit-tagged `Vector3`) idiom established by ADR-0007.

This is a **clean-break migration** (no deprecation window). Per explicit
direction from the project owner: no external consumers exist yet, so we are
not preserving wire-format backward compatibility. Existing topic data is
purged as part of the migration.

### Migration table

| Message         | Old fields (removed)                    | New fields                                |
| --------------- | --------------------------------------- | ----------------------------------------- |
| `EcefPosition`  | `double x_m=1, y_m=2, z_m=3`            | `Quantity x=1, y=2, z=3` (UCUM `"m"`)     |
| `Wgs84Position` | `double lat_deg=1, lon_deg=2, alt_m=3`  | `Quantity lat=1, lon=2, alt=3` (`"deg"` / `"m"`) |
| `LocalEnu`      | `double east_m=1, north_m=2, up_m=3`    | `Quantity east=1, north=2, up=3` (`"m"`)  |
| `EulerAngles`   | `double yaw_deg=1, pitch_deg=2, roll_deg=3` | `Quantity yaw=1, pitch=2, roll=3` (UCUM `"rad"` or `"deg"` per source) |

### Out of scope (deliberately left as bare doubles)

These are uncertainty/quality fields, not primary measurements, and live
alongside their primary quantities. They can graduate to `Quantity` in a
future cleanup if uncertainty algorithms ever need unit-tagging:

- `PositionQuality.horiz_std_m`, `vert_std_m` — 1-sigma uncertainties in m
- `Attitude.std_dev_deg` — Vector3 with `unit` already; just ensure populated

### Vector3 usage already-correct

`Vector3` already has a `unit` string field. The migration verifies these
usages populate `unit` correctly:

- `KinematicState.acceleration` — `"m/s2"`
- `KinematicState.angular_velocity` — `"rad/s"`
- `Velocity.ecef` / `ned` / `body` — `"m/s"`

### Unit conventions

Native unit per source feed; algorithms convert via `pint` at the consumer
boundary. DIS emits:

- ECEF position in m → `unit: "m"`
- ECEF velocity in m/s → `unit: "m/s"` (Vector3.unit)
- Euler orientation in rad → `unit: "rad"`
- WGS84 lat/lon in deg → `unit: "deg"` (when emitted)

Proprietary feeds in Phase 3+ may emit different conventions; that is
absorbed by their dedicated Bloblang mapping, not by a schema change.

## Consequences

**Pros**

- Schema and ADR-0007 are now consistent: every physical quantity carries
  its own unit.
- The radian-into-`yaw_deg` lie disappears. DIS orientation lands in Silver
  as `{value: 1.5708, unit: "rad"}`, honestly.
- Algorithms that consume kinematics can use the same `pint`-based
  `from_proto` adapter as thermal/electrical algorithms.
- The CM service in Phase 3 reads kinematic state through the same idiom
  it already uses for sustainment; no two-pattern conditional code.

**Cons**

- Clean-break migration invalidates any data already on `raw-sensor-stream`,
  `telemetry-latest-state`, and any persisted Faust state tables. These
  topics are purged as part of this phase.
- Every Bloblang mapping that touched the renamed fields must be updated.
  Currently that's `sim-dis-mapping.yaml` only; future feed adapters must
  follow the new shape.

**Rejected alternatives**

- *Additive migration with `deprecated = true`*: would have preserved old
  data but added perpetual schema clutter and a "which field do I read?"
  decision on every consumer. Owner directed clean break since no
  production consumers exist.
- *Leave the schema inconsistent and convert later*: Phase 3 (CM service)
  is the first heavy kinematic consumer; this migration is cheaper before
  Phase 3 ships than after.

## Verification

Hero Scenario v3 tests 1-8 continue to pass after migration. Two new tests:

- **Test 9 — Angle Quantity round-trip**: send DIS PDU with yaw = π/2 rad,
  verify Silver `event.kinematics.attitude.euler.yaw.value ≈ π/2` and
  `.unit == "rad"`; convert via pint to degrees, verify ≈ 90.0.
- **Test 10 — Position Quantity round-trip**: send DIS PDU with known ECEF
  coordinates, verify `event.kinematics.position.ecef.x.value` matches and
  `.unit == "m"`.

Test 11 (backward compatibility) from the original recipe is **skipped** —
clean-break migration makes it inapplicable.

## Related

- ADR-0007 (unit handling) — this ADR extends ADR-0007 from a sustainment-only
  rule to a schema-wide rule.
- ADR-0010 (feed integration) — external feeds absorb unit quirks in their
  Bloblang mapping; the Silver schema stays uniform.
