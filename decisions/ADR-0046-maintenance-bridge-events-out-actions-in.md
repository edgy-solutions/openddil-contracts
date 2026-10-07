# ADR-0046 — Release by kind, intake by kind: one gate, destinations as registry entries

## Status

**ACCEPTED (v2) — approved 2026-10-03.** This replaces PROPOSED (2026-10-02). Extends `openddil:ADR-0031`.
**Amended 2026-10-05:** a refusal for an unknown answered record is provisional. See
[Amendment 2026-10-05](#amendment-2026-10-05-a-refusal-for-an-unknown-answered-record-is-provisional).

v1 described a maintenance bridge: two more egress gate instances, two system subjects named for maintenance, a
`maintenance_actions` table and a pane that knew about it. **v2 makes OpenDDIL's side generic.** OpenDDIL code names no
consumer, no domain and no endpoint. Maintenance is the first instantiation, and it lives entirely in a deployment
overlay. The other side of the seam has accepted the same shape:
- events enter its intake as a declared kind;
- its workflow is declarative;
- the record it decides is an artifact OpenDDIL polls or is called back with.

### Decisions taken for this pass, recorded as such

These are inputs, not conclusions:
1. **The workflow runs in the reasoning plane. OpenDDIL holds no workflow state.** Approval routing, pending tasks
   and timers live in the consumer's workflow definition and decision records. OpenDDIL holds three things: the record
   it released, the artifact it took in, and its own local decision about that artifact.
2. **One consumer instance serves every tier in this pass.** Per-tier instances are the design (ADR-0031).
3. **The beat is shown connected.** `sever-tier.sh` is unchanged. A severed tier queues at its gate output, like any
   other egress.
4. **Alignment is by concept name only, under ADR-0038 C1**, and it is declared in the overlay's kind schemas (§3).
5. **The first instantiation is a medium-range air defense radar (MRAD):**
   - one pinned id with a SISO radar entity type, declared ATL in `releasability.yaml`;
   - a discrete fault in one array module;
   - two sources for the same fault: a maintainer's report in the edge UI (a CM discrepancy) and a BIT-style
     telemetry fault.

## Context

There is one egress gate (`openddil:ADR-0043`):
- `EgressGate.for_destination(dest).decide(label, key)` decides a record's label against one destination's nations;
- it applies the deny-unlabelled floor;
- it logs one JSON decision line per record.

In v1 a new destination meant a new gate deployment with its own source and sink topics. It also meant per-destination
code in the pane API (`RECORD_SOURCE`). A third consumer would have meant a third copy. The gate's predicate was
already generic, but everything around it was not.

**What v1's build left in code, which v2 retires.** These are measured on compose and pushed, but not on any lab:
- openddil-stack: a `maintenance_actions` table;
- openddil-demo `egress/pane_api.py`: `RECORD_SOURCE = {"system:mmis-stand-in": _fetch_maintenance_actions}`;
- the `MaintenanceActionsPane` component;
- two system subjects in `policy/users.yaml`.

§7 says what each becomes.

## Decision

### 1. A destination is a registry entry

`destinations.yaml` is a new registry, the destination counterpart of `users.yaml`, which keeps people. Each entry
has:

| field | meaning |
|---|---|
| id | `system:<name>`, asserted by deployment configuration (the ADR-0043 caveat carries over: no link authentication yet) |
| `nations` | the destination's entitlement; the gate's only input from the entry |
| `accepts` | the kind names this destination may be released (§3); a release of any other kind is refused |
| `transport` | `topic: <name>` or `http: {url, auth_ref}`; `auth_ref` names a credential and never holds it |
| `intake` | optional: `{poll: {url, interval_s}}` or `{callback: {path}}`, the artifacts this destination returns (§5) |
| `trust_on_behalf_of` | optional, default false (§6) |

- **The repository ships the registry's shape and one generic entry,** `system:c2-stand-in-atl`, moved from
  `users.yaml`. Every other entry comes from the deployment overlay.
- **The overlay holds:**
  - the consumer's id and `[ATL, BDR]`;
  - its intake URL, kind names and subscription;
  - the maintenance-management stand-in.
- The chart renders the overlay's entries into topaz's data next to the shipped ones (`data.openddil.destinations`).
  The pod's policy checksum hashes them.
- **Topaz reads its registries only at start.** A registry change rolls topaz (the checksum), and that roll is part of
  every prediction. Reloading without a restart is a later mechanism, not this pass.

`releasability.rego` resolves a destination's nations from `data.openddil.destinations[id]`. During the move it also
reads a `system:` row left in `users.yaml`. An unknown destination still resolves to the empty set and is refused.

### 2. One gate, routes as configuration

The gate is one process with a **route table**. Each route has:

| field | meaning |
|---|---|
| `source` | a topic of release requests |
| `kind` | the declared kind the route carries |
| `destination` | a registry id |
| `sink` | where admitted records go, taken from the destination's `transport` |

- The C2 path becomes one route: source `asset-logistics-status`, sink `egress-c2-status`.
- With no route table, the gate's environment variables give exactly that single route, so today's deployment is
  unchanged.
- Adding a destination is a registry entry plus a route, and it needs no new deployment.

The decision line is unchanged, plus `kind` and `route`. Its `allowed` / `reason` vocabulary is unchanged. Two
reasons are added:
- `kind_not_accepted`: the destination's `accepts` does not list the kind;
- `schema_invalid`: the record does not validate against its kind (§3).

### 3. Kinds are declared schemas in the overlay

A **kind** is a JSON Schema document in the overlay, plus four declarations the code reads:

| declaration | example (the maintenance instantiation) |
|---|---|
| `key` | the JSON pointer of the record's stable id (`/event_id`) |
| `label` | the pointer to `{originator_nation, releasable_to}` (`/label`) |
| `owning_tier` | the pointer to the tier that owns the subject (`/owning_tier`) |
| `episode` | optional: the pointers whose tuple names one episode (`/asset_id`, `/fault/item`, `/fault/fault_code`) |

The code knows a kind only as a name, a schema and these pointers. This pass declares two:
- **`MaintenanceFaultEvent`**, which keeps v1 §1's fields:
  - `event_id`, `asset_id`, `owning_tier`;
  - `fault {item, fault_code, observed_at}`;
  - `sources[]`;
  - `picture {readiness, lifecycle, factors, spare, battle_condition}`;
  - `label`, `provenance`.
- **`MaintenanceAction`**, which keeps v1 §4's fields:
  - `action_id`, `event_id`, `asset_id`, `owning_tier`, `label`;
  - `work_order {task, task_refs[], parts[], outcome}`;
  - `approval_chain[]`, `on_behalf_of`, `provenance`.

Each schema carries its C1 alignment as an annotation (`x-alignment`), by concept name only (§Alignment declared).

### 4. Outbound: release to a destination by kind

A record is released by publishing a **release request** on a route's source topic. The request is the record itself.
The gate reads the route's kind, then for each record:
1. checks the record against the kind's schema;
2. checks the kind against the destination's `accepts`;
3. reads the label at the kind's `label` pointer;
4. decides it exactly as it decides a C2 record.

An admitted record goes to the destination's transport. The event is a record like any other: the gate has no
event-specific path.

**The assembler** produces the release request. It is generic code with overlay configuration.
- **On** a trigger: a CM discrepancy that the CM service records (§8).
- **It builds** a record of the configured kind from the asset's **picture**:
  - readiness (`telemetry_latest_state`'s ADR-0044 columns);
  - lifecycle (`asset_cm_state.lifecycle`);
  - the rollup and constraining factors (`asset_logistics_status`);
  - spares (the parts-availability records, by site and item): one row per site, each with its stock, lead time and
    the system its figures come from, plus the nearest row with stock. Nearest is the spares source's own configured
    nearest-first order, published on its records; the assembler copies that row and adds no rule of its own. It is
    null when no site in that order has stock, and absent when the part is unknown.
  The picture is a generic read of the asset. The kind's schema decides which sections the record carries.
- **One episode, one record.** The record key is a uuid5 of the kind's episode tuple, the owning tier and the time
  the episode was first observed:
  - a second source inside an open episode is appended to `sources[]` and released as a revision with the same key;
  - a fault that clears and reappears, or recurs after the stores are emptied, is a new episode with a new key;
  - records are counted by distinct key, and sources separately.
- **Where it runs in this pass:** on the hub, reading the replicated CM topic. The key is deterministic, so a per-tier
  assembler later mints the same key.

**Red-check (carried by the build):** a route to an ATL-only destination refuses a record whose label is BDR, and logs
the refusal.

### 5. Inbound: artifact intake by kind

A destination with `intake` returns artifacts of a declared kind.
- **First pass: poll.** The intake GETs the destination's `intake.poll.url` every `interval_s`.
- **Later: callback.** When a route from the consumer to the tier exists, it POSTs to `intake.callback.path` behind the
  PEP.

For each artifact, the intake:
1. validates it against its kind;
2. checks that its label equals the label of the record it answers. It refuses a mismatch;
3. resolves every approver subject in the artifact's chain against `users.yaml`, and requires each to be entitled to
   the label by the read path's predicate. An unresolved or unentitled approver refuses the artifact;
4. **logs a local decision at the owning tier.** The line has the gate's shape (`decision_id`, `allowed`, `reason`,
   key), plus the approvers' subjects. The decision and the artifact are stored at that tier in a generic
   `intake_records` table (kind, key, label, body, decision), so the record survives severance.
   **This pass:** the intake runs at the hub, beside the egress, so `intake_records` is in hub postgres with
   `owning_tier` as a column. Storage at the owning tier stays the design; until it lands, a severed tier does not
   hold its own decisions;
5. publishes an admitted artifact as a release request on the route toward the next destination. In this pass that is
   the maintenance-management stand-in (`accepts: [MaintenanceAction]`). It goes through the same gate.

The hub pane reads what the gate released toward a destination, as the C2 pane does:
- **the pane is a generic released-records pane,** configured with a destination and a kind;
- it is filtered by the viewer's nations;
- withheld records are shown only as a count of unlabelled records.

### 6. Delegation

An artifact names the human it acts for (`on_behalf_of`, a subject).
- **This pass:** the intake trusts `on_behalf_of` **by configuration**, and only from a destination whose entry sets
  `trust_on_behalf_of: true`. Every approver is still resolved and entitlement-checked (§5.3).
- **The design:** OAuth 2.0 token exchange (RFC 8693). The consumer presents an actor token and the subject's token,
  and the tier verifies both instead of trusting a field.
- The gap is the ADR-0043 caveat over again: the link is not authenticated yet.

### 7. What v1's build becomes

| v1 artifact | v2 |
|---|---|
| `system:maint-iagent`, `system:mmis-stand-in` in `users.yaml` | removed; overlay entries in `destinations.yaml` |
| `system:c2-stand-in-atl` in `users.yaml` | moved to the shipped `destinations.yaml` |
| `maintenance_actions` table | replaced by `intake_records` (kind, key, label, body jsonb, decision jsonb, decided_at); one new migration creates it and drops the old table; the old table did reach a deployed environment, empty (0 rows), so dropping it loses nothing |
| `RECORD_SOURCE` in pane_api | removed; the pane reads the gate's released records for the requested destination, with no per-destination code |
| `MaintenanceActionsPane` | a generic `ReleasedRecordsPane(destination, kind)`, mounted from runtime configuration |
| v1 §2's second and third gate instances | retired: one gate with routes (§2) |

### 8. The fleet addition, and the two sources of one fault

**The MRAD:**
- one pinned id in edge-01's range;
- a SISO radar entity type, added to `dis_entity_types.yaml` under the ontology's own CI;
- declared ATL in `releasability.yaml`;
- `dis:1:1:1099` stays undeclared.

Both partitions hold:
- no asset belongs to two edges (`test_49`);
- the nation partition has non-empty ATL and BDR sides.

**Source 1: a maintainer's report.** A form on the asset's page in the edge UI takes:
- the component;
- a fault code from a short list (overlay configuration);
- free text.

It produces a CM discrepancy with `source: maintainer_report` and `reported_by`. The reporter's subject comes from the
PEP (`X-OpenDDIL-Subject`), never from the form. This is the first write path through the PEP: it is gated on an
authenticated subject, and its own decision line is logged.

**Source 2: BIT telemetry.** A BIT-style telemetry fault for the same component and fault code produces the same
discrepancy with `source: telemetry_bit`. dis-sim injects it on a schedule.

**One discrepancy, two sources.** The CM service keys a fault discrepancy on `(asset, component, fault_code)`. Both
sources land on one discrepancy with two `sources[]` entries, so the assembler releases one record.

### 9. Dry-run ground truth, shared with the consumer side

**The fault code is `MRAD-ARR-0417`** (an array module fault). The mock manual (six synthetic S1000D data modules,
model ident `ODMRAD`) carries it in its fault isolation module. The four options the consumer is expected to propose,
with the module codes each cites, are in the ground-truth file handed over with the fixture. They are recorded here by
outline:
1. no fault confirmed after a BIT re-run: return to service and monitor;
2. reseat the module connector and re-run BIT;
3. replace the array module from a spare on hand;
4. replace the array module with a spare from the nearest site with stock.

Options 3 and 4 cite the same procedures and parts. They differ only in the event's `picture.spare`. A dry run
passes when the consumer proposes exactly these four for an event with this fault code.

**This list is a draft.** It was derived from the fixture's isolation tree and the spares picture, and it becomes
ground truth when both sides confirm it.

### Noted for later, not built
- Registry reload without a topaz restart.
- Callback intake (needs a route from the consumer to the tier).
- Token exchange (§6).
- A per-tier assembler.
- For a radar, battle condition should include the coverage lost while a section is down for repair.

## Alignment declared (ADR-0038 C1 intake)

**By concept name only.** No schema text, element names or code lists from either specification are copied here or
into the overlay's schemas.

| kind (overlay) | aligned to | concepts named |
|---|---|---|
| `MaintenanceAction.work_order` | ASD S5000F (in-service data feedback) | maintenance task, triggering event, parts consumed, authorisation |
| `MaintenanceFaultEvent.fault`, `sources[]` | MIMOSA CBM (OSA-CBM) | state detection (BIT), health assessment (the fault on an item), advisory (the returned work order) |

The field names are OpenDDIL-local, with a declared alignment intent. Binding them to named elements is owed before any
field is frozen.

## Consequences

### Positive
- One gate and one predicate. A new consumer is a registry entry, a route and a kind schema, with no code change.
- No OpenDDIL repository names the consumer, the domain or an endpoint.
- The owning tier's log names who approved the work, as that tier's own record, and the record survives severance.

### Negative
- Topaz must roll on every registry change until reload exists.
- The overlay now carries real behaviour (kinds, routes, endpoints). It needs a home with review, and ADR-0036's work
  overlay is still doctrine only.
- `on_behalf_of` is trusted by configuration in this pass.
- One consumer instance: a severed tier queues until it is reconnected.

### Neutral
- The C2 pane and the released-records pane are one mechanism with two configurations.

## Related
- `openddil:ADR-0031` (reasoning-plane seams; state vs knowledge)
- `openddil:ADR-0043` (one predicate, two subjects; the gate)
- `openddil:ADR-0044` (lifecycle and readiness columns)
- `openddil:ADR-0028` (owning tier)
- `openddil:ADR-0036` (overlays)
- `openddil:ADR-0038` (C1 intake)

## Amendment 2026-10-05: a refusal for an unknown answered record is provisional

### What happened
An artifact can name an answered record that the intake has not seen yet. When the answers topic is empty, the intake
counts as caught up, so it refuses the artifact `answered_record_unknown`. The unchanged-by-hash skip then never
decides that artifact again.

After a reset, the intake comes back with the producers and its answers topic is empty. It refused every action within
2 s. The record they answered arrived about two minutes later. The refusals stayed, so the admitted action was never
admitted. An earlier run passed only because a separate defect made the intake wait.

### The rule
- A refusal for an unknown answered record is **provisional**. It is stored and logged as a refusal
  (`allowed: false`, `reason: answered_record_unknown`) and carries `provisional: true` and `provisional_since`.
- The hash skip does not apply to a provisional refusal. Each poll re-decides it:
  - when the record has arrived, the artifact goes through the remaining steps like a fresh one;
  - while it has not arrived, nothing is logged or stored again.
- After `answers.provisional_timeout_s` (per intake entry, default 900 s) the refusal becomes **final**:
  `provisional: false`, with a detail that names the timeout. The reason code is unchanged; no new vocabulary.
- Every other decision carries `provisional: false` explicitly.
- A stored `answered_record_unknown` row without the flag predates this rule. It counts as provisional, with its
  `decided_at` as the start. Refusals already held therefore resolve by the same path; none is cleared by hand.

### Why the timeout is final, not indefinite
An action that names a record which never comes must not stay undecided forever. The final refusal states how long the
intake waited. The pane can then tell "not yet" apart from "never arrived".

### What does not change
- The order of the steps, the label rule, the approver rule and the gate.
- The `deferred` path for a process that has not caught up.
- A restart is covered by the same rule: the answers topic is re-read from the log start, and a provisional row is
  re-decided on the next poll.

