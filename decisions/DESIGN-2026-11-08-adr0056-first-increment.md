# DESIGN 2026-11-08 — ADR-0056's first increment: the alias table and the binding row at the registry

**Status:** an implementer spec. Design only: nothing built, nothing run, nothing measured for this increment. Local
branch, not merged. ADR-0056 is PROPOSED, with its five rulings signed 2026-11-07. Its two open items, the
writer and the UII field, were ruled 2026-11-11 (§2.1, §2.2). This spec builds §1's
bind-before-mint on the declaration path, §2's alias rows, §3's lookup key, §4's equivalence row and §6's binding row
and era read, at the asset registry only. It stops before any id changes.
**Builds on:** ADR-0056 §1-§4 and §6, and its checks 1, 3, 4, 5, 6 and 10; ADR-0047 (`asset_id` is opaque); ADR-0050
(an arrival is a person's declaration).

## What the increment is

- The registry's store gains five tables: the scheme registry, the identity, the alias, the binding and the
  equivalence.
- The registry consumes the declaration topic. For each declaration it looks up every alias the declaration carries.
  - If one alias resolves, it binds the declared `asset_id` to that identity.
  - If none resolves, it mints a UUIDv7, records itself as the minting authority with its generator, and binds.
  - If two aliases resolve to two different identities, it binds nothing and records a conflict.
- A reader asks the registry which era an id belongs to. The answer comes from the binding row: era 2 only when the
  asset is bound and `bound_at` is at or before the episode's first-observed time.
- An equivalence row is written by one function, which requires an owner, a date and a reason.

**Not in the increment:**

- No id changes. No record id is computed from the identity: CM and egress keep their era-1 functions, and no caller
  reads the era yet. Era-2 ids are the next increment.
- No route serves the new tables, and they are not added to Electric's publication. Serving them needs labels first
  (§6).
- No edge mints. The registry runs at one tier today (finding 4). Minting while severed is §6, owed.
- No equivalence route for owners, and no notification of a conflict to its owners (§6).
- No SKOS, PROV-O or vocabulary identities (ADR-0056 §10).

## Findings that shape it

1. **Nothing mints today.** `asset_id` is the opaque DIS URN made by sensor ingest (`dis_ingestor.py:876`) and
   copied by the dynamic mapping. There is no identity column anywhere in the store.
2. **The registry's only insert is on first observation.** `INSERT INTO asset_registry` exists once, at
   `asset-registry-service/src/asset_registry_service/db.py:193-205`, inside `upsert_observation`. It must stay as it
   is: observation never mints (ADR-0056 §1).
3. **The declaration path never touches the registry.** The PEP's `POST /arrivals/declare` (`pep.py:2804`) builds
   `declared_rec` (`pep.py:2944-2952`) and posts it to intake. Intake writes `asset-declarations`, compacted and keyed
   by `asset_id`. The projector's `asset_declaration` and `asset_correlation` handlers consume it
   (`projector_config.yaml:134-146`). The record carries no id of its own, and its only alias is `serial`, which is
   optional (`pep.py:1791`). There is no UII field.
4. **The registry is one process at one tier.** `main.py:142` reads `ASSET_REGISTRY_EDGES` and subscribes to each
   edge's broker, then writes one store. So "every tier runs intake" (ADR-0056 §1) does not hold for the registry
   yet. This increment binds where the registry runs.
5. **`asset_correlation` is the nearest alias table today.** It maps serial to `asset_id` and is labelled
   (`schema.hcl:2210`, `electrify.sql:262`). It stays as it is. The alias table does not replace it in this increment.
6. **Every id issued today is a uuid5 over `asset_id`.** Egress: `record_key` and `episode_key`
   (`egress/assembler.py:164-175`). CM: `discrepancy_id` (`asset_cm.py:561-563`, `:581-584`). The October literal is
   pinned at `test_assembler.py:123-127`. Any change to those functions, or to their inputs, moves an issued id.
7. **`schema.hcl` does not declare `asset_registry`.** It is created by
   `20260604202813_phase8_asset_registry.sql` and altered by four later migrations. The migrations are the record of
   what exists. `schema.hcl` declares `asset_correlation` but not the registry.
8. **Python 3.11 has no UUIDv7.** The service image is `python:3.11-slim` and the package says `>=3.11`. `uuid.uuid7`
   arrives in 3.14. The generator is written here, or taken as a dependency. Either way it is declared (check 9).
9. **ADR-0047's opacity check is a reusable workflow.** `openddil-stack/.github/workflows/asset-id-opaque.yml` calls
   the contracts workflow, with exceptions in `.asset-id-allowlist`. It looks for places that parse `asset_id`. It does
   not yet look at any other alias.

## 1. The store

One Atlas migration, `<timestamp>_asset_identity.sql`, listed in `atlas.sum`. The same tables are added to
`schema.hcl` (finding 7: the registry's own table is not added here, and that gap is a row, §6).

### 1.1 Tables

- **`alias_scheme`**: `scheme text PK`, `owner text NOT NULL`, `value_form text NOT NULL`, `namespace uuid NOT NULL
  UNIQUE`, `registered_at timestamptz NOT NULL`, `registered_by text NOT NULL`.
  - `namespace` is the uuid5 namespace for that scheme's lookup keys (ADR-0056 §3). It is generated once, when the row
    is written, and never derived from the scheme's name.
  - Seeded by the migration with three rows: the deployment's `asset_id` scheme, `serial` as the declaration carries
    it, and `identity`, which holds a merged identity as an alias of its survivor (§2.8). A fourth row, `uii`, is
    seeded too, since the UII field is in this increment (§2.1).
- **`asset_identity`**: `identity uuid PK`, `minted_at timestamptz NOT NULL`, `minting_tier text NOT NULL`,
  `generator text NOT NULL`, `generator_version text NOT NULL`, `declaration text NOT NULL`.
  - Stored as `uuid`. It is written as `urn:uuid:<uuid>` only at a seam, and no seam carries it in this increment.
- **`asset_alias`**: `scheme text REFERENCES alias_scheme`, `value text NOT NULL`, `lookup_key uuid NOT NULL`,
  `identity uuid REFERENCES asset_identity`, `authority text NOT NULL`, `valid_from timestamptz NOT NULL`, `valid_to
  timestamptz`, `declaration text NOT NULL`.
  - Unique index on `(scheme, lookup_key) WHERE valid_to IS NULL`. This index is what makes lookup-before-mint
    atomic (§2.3).
  - No column is derived from `value`. `lookup_key` is computed from it and stored next to it.
- **`asset_binding`**: `asset_id text NOT NULL`, `identity uuid REFERENCES asset_identity`, `bound_at timestamptz NOT
  NULL`, `bound_by text NOT NULL`, `declaration text NOT NULL`. Primary key `(asset_id, identity)`.
  - These are ADR-0056 §6's five fields, as written.
  - Unique index on `asset_id`. One asset binds once in this increment. A later rebinding is a new row under an owned
    equivalence, never an update (§1.2).
- **`identity_equivalence`**: `survivor uuid`, `merged uuid`, both referencing `asset_identity`, `owner text NOT
  NULL`, `declared_at timestamptz NOT NULL`, `reason text NOT NULL`, `declaration text NOT NULL`. Primary key `(merged)`.
  A `CHECK (survivor <> merged)`.
- **`identity_conflict`**: `declaration text`, `asset_id text`, `identities uuid[]`, `raised_at timestamptz`. One row
  per declaration whose aliases resolve to more than one identity. Nothing reads it in this increment except the
  acceptance script.

### 1.2 What is never done to these tables

- No `UPDATE` of `identity`, `asset_id`, `value` or `lookup_key`, and no `DELETE`. A merged identity becomes an alias
  row of the survivor with `valid_to` set; it is never deleted (ADR-0056 §4).
- The only column that is ever updated is `asset_alias.valid_to`, from NULL to a time, inside `declare_equivalence`.
- Each rule has a test (§5).

### 1.3 The declaration reference

The declaration record has no id (finding 3). `declaration` on every row is the SHA-256 of the record's canonical JSON
(sorted keys, no whitespace, UTF-8), as hex. Replaying the compacted topic yields the same hash, so the same
declaration is recognised and changes nothing (§2.4).

### 1.4 Labels

The new tables carry no `originator_nation` or `releasable_to` in this increment, because nothing serves them. A test
asserts that none is in `electric_publication` and that no PEP route names them. Serving them is owed, and it comes
with labels (§6).

## 2. The declaration path

### 2.1 What the declaration carries

- **Today:** `asset_id` (an alias under the deployment's scheme) and, when given, `serial`.
- **Ruled 2026-11-11: an optional `uii` field is in.** Check 10 is written against a UII. Without the field, the only
  lookup that can resolve is `serial`, and check 10 would be tested on `serial` instead.
  - `pep.py:1790-1806` accepts optional `uii` as text, never parsed. `declared_rec` carries it. Intake's declaration
    schema accepts it. The projector ignores it.
  - It costs one optional field at three places and makes check 10 the check ADR-0056 states.

### 2.2 Who writes

- **Ruled 2026-11-11: the writer is the asset registry service.** It already owns `asset_registry`, it holds
  the store, and the declaration's subject is the registry's subject. It gains a second agent that consumes
  `asset-declarations` at its own tier. The projector's two handlers are unchanged.
- The alternative, a third projector handler on the same topic, was not taken: the projector is a table writer with
  no lookups, and lookup-before-mint is a decision.

### 2.3 Bind before mint

For each declaration, in one transaction:

1. Compute `declaration` (§1.3). If an `asset_binding` row already has it, stop. That is a replay.
2. Build the alias list: one entry per carried alias with a registered scheme. A carried alias whose scheme is not
   registered is logged and skipped, never registered on the fly.
3. For each alias, compute `lookup_key = uuid5(alias_scheme.namespace, value)` and select the open alias row
   `FOR UPDATE`.
4. Collect the identities found.
   - **One identity:** bind `asset_id` to it. Write alias rows for the carried aliases that are not yet held,
     pointing at it. Mint nothing.
   - **None:** mint (§2.5), write the identity row, the alias rows and the binding row.
   - **More than one:** write one `identity_conflict` row. Bind nothing, mint nothing, write no alias row.
5. If `asset_id` is already bound to a different identity than the one found, that is a conflict too (step 4,
   third case).
6. On a unique-index violation from step 4 (two declarations racing on one alias), roll back and redo from step 1.
   The second pass finds the first's identity and binds to it.

### 2.4 Replay and restart

- The topic is compacted and keyed by `asset_id`. A new consumer group, or a reset, re-reads every declaration.
- Each one stops at step 1, or finds its identity at step 3. No replay mints.
- A test replays the same topic twice into one store and asserts row counts are equal after both passes.

### 2.5 The generator

- One function, `mint_identity()`, in the registry package. It is RFC 9562 §5.7 UUIDv7: 48 bits of Unix
  milliseconds, the version and variant bits, and the rest from `os.urandom`. Within one millisecond, `rand_a` is a
  12-bit counter seeded from random, so ids from one process sort in mint order.
- `generator` is the fully qualified function name. `generator_version` is a module constant, bumped when the
  function changes.
- No dependency is added. If one is preferred, it is pinned in `uv.lock` and named in `generator` the same way.
- **The minting tier** comes from a new required setting, `ASSET_REGISTRY_TIER`. The service refuses to start
  without it. There is no default, because a wrong default would name the wrong authority on every row.

### 2.6 Observation is unchanged

`upsert_observation` and its insert stay byte-identical. An observed asset with no declaration has a registry row and
no binding. A test asserts that an observation, alone, writes no row to any of the five tables.

### 2.7 The era read

- One SQL function, `asset_id_era(asset_id text, first_observed timestamptz) RETURNS smallint`, in the migration. It
  returns 2 when a binding row for `asset_id` has `bound_at <= first_observed`, and 1 otherwise.
- One Python function of the same name in the registry package calls it. Nothing else calls either in this
  increment.
- `bound_at` is the time the binding row is written, not `declared_at`. An episode first observed between the
  declaration and the binding is era 1. That is the conservative side of Ruling 2.
- The era is never read from an id (ADR-0056 §6). The function's inputs are an `asset_id` and a time, never an id.

### 2.8 The equivalence

- One function, `declare_equivalence(survivor, merged, owner, reason, declaration)`, in the registry package.
  - In one transaction it writes the equivalence row, sets `valid_to` on `merged`'s open alias rows, and writes an
    alias row of the survivor under the registered `identity` scheme with `value = urn:uuid:<merged>` and `valid_to`
    set.
  - It refuses an empty `owner` or `reason`, a `survivor` equal to `merged`, and a `merged` already merged.
- No route calls it in this increment. Its caller is the owners' route, owed (§6).

## 3. What must not change

- **No id issued today moves.** Every `asset_id`, every egress `event_id` and `episode_id`, and every CM
  `discrepancy_id` read before the increment reads the same after it.
  **Check:** the acceptance run (§4).
- **The October literal.** `test_assembler.py:123-127` passes unedited.
  **Check:** CI runs it; the PR touches no file under `openddil-demo/egress/` and does not touch
  `openddil-cm-service/src/events/asset_cm.py`. A step in the PR's workflow fails if either path is in the diff.
- **Observation.** `upsert_observation` is byte-identical, and the registry's existing tests pass unedited.
  **Check:** `tests-asset-registry.yml`, plus §2.6's test.
- **The projector.** The `asset_declaration` and `asset_correlation` tables get the same rows for the same topic.
  **Check:** the acceptance run counts both tables before and after.
- **No new served data.** No shape, no route.
  **Check:** §1.4's test.

## 4. The acceptance run, as a script

`scripts/identity_increment_rowmatch.py` (contracts repo). It only reads: `SELECT`s. The roll that ships the increment
is not the script's. A person does it, through the chart.

**Exit codes**, as for the compatibility slice: 0 match, 1 diff, 3 refused, 4 unchecked, 78 guard.
**Guard:** it sources `require-cluster.sh` from the helm checkout and halts unless the asserted context is the one
passed. Same mechanism as the compatibility slice.

### 4.1 Steps

Each step writes its file and stops. A refusal at any step halts the run, with the state named.

1. **`read --phase before`**. It writes `before.json`, read on postgres directly at each tier passed:
   - every `asset_id` in `asset_registry`, with `last_observed_at`;
   - every `event_id` and `episode_id` in `egress_delivered_events`, with its `asset_id`;
   - every `discrepancy_id` in `asset_cm_state.discrepancies` and `asset_cm_state.manual_discrepancies` (jsonb
     lists), with its `asset_id`;
   - row counts of `asset_declaration` and `asset_correlation`, and the set of their keys.
2. **`predict`**. It writes `prediction.json` and `prediction.md`:
   - every set read before is a subset of the set read after, and every id read before has the same `asset_id`;
   - for each declared asset, one binding row, one identity, and one alias row per carried alias;
   - zero `identity_conflict` rows, unless the before read finds a serial held by two assets in `asset_correlation`,
     in which case each such pair is named;
   - `asset_id_era` returns 1 for every episode read before.
3. **`read --phase after`**, after the roll and once the declaration consumer reports the topic's end offset. It
   refuses if `prediction.json` is missing or its hash of `before.json` does not match. Without a way to read the
   consumer's position, it exits 4, unchecked, and says so.
4. **`compare`**. It writes `compare.json` and `compare.md`, and exits 0 only when every difference is one predicted.
   - A missing id, an id whose `asset_id` changed, or a projector count that moved is a diff (exit 1), named first.
   - A declared asset with no binding and no conflict row is a diff.
   - An identity with no binding is a diff. It means a mint path skipped the bind.

### 4.2 Inputs

- `--helm-dir`, `--context`, `-n`, and per tier the store pod and database.
- `--out DIR`.
- The tier list comes from the arguments. No deployment name, host or tier name is written into the script.

### 4.3 Tests

- Offline unit tests in `tests/test_identity_increment_rowmatch.py` cover prediction hashing, the refusal without a
  prediction, and compare's classes.
- **The lookup-key vectors are shared.** A fixed table of `(namespace, value, lookup_key)` runs against Python's
  `uuid.uuid5` and against the store's computation in the migration's test, on a real postgres in CI.

## 5. Checks for the PR

Each of ADR-0056's checks that this increment can meet is a named test. The real-Postgres tests follow the projector's
pattern: `ASSET_REGISTRY_TEST_PG_DSN`, skipped locally when unset, failing in CI when unset.

| ADR-0056 check | Test | What it plants and asserts |
| --- | --- | --- |
| 1. October unchanged | `test_assembler.py` (unedited) and the path step (§3) | The literal passes; the diff touches neither path. |
| 3. Index is not identity | `test_identity_not_lookup_key` | After 1,000 declarations, no `asset_identity.identity` equals any `lookup_key`, and every identity has version 7. |
| 4. No parsing | `asset-id-opaque.yml`, scope widened | The workflow's scan covers the registry package's alias code. A planted split of `value` in a fixture file fails it; the plant is in the test, never in the package. |
| 5. No matching | `test_equivalence_single_writer` | No `INSERT INTO identity_equivalence` outside `declare_equivalence`, read from the source tree; and the function refuses an empty owner. |
| 6. Rebinding is a row | `test_era_from_binding_row` | `asset_id_era` returns 1 before a binding, 1 for an episode first observed before `bound_at`, and 2 at or after it. |
| 10. Lookup before mint | `test_lookup_before_mint` | An alias row for a UII (§2.1) bound to identity X; a declaration for a new `asset_id` carrying it binds to X, and the identity count is unchanged. |

Also:

- `test_replay_is_idempotent` (§2.4) and `test_race_one_identity`: two concurrent declarations carrying one serial
  leave one identity.
- `test_conflict_binds_nothing`: two aliases resolving to two identities write one conflict row and nothing else.
- `test_observation_writes_no_identity` (§2.6).
- `test_no_served_identity_table` (§1.4).
- `test_uuid7_shape`: version and variant bits, and order across 10,000 mints in one process.
- `test_migrations.py` passes with the new file in `atlas.sum`.

Checks 2, 7, 8 and 9 are not this increment's. Check 2 and check 8 need era-2 ids, check 7 needs "sustained-under",
and check 9 is the vocabulary files.

## 6. Owed by others, not built here

- **Era-2 ids.** CM and egress compute the episode id over the identity, for episodes first observed at or after
  `bound_at`, under Rulings 1 and 2. That increment is where checks 2 and 8 land.
- **Serving.** A route or a shape for the alias and binding tables, with labels on each row.
- **The owners' equivalence route**, and the named exception to both owners on a conflict row.
- **Every tier holds a registry.** Finding 4: the registry runs at one tier. An edge that holds a declaration while
  severed cannot look up or mint until it does.
- **`schema.hcl` and `asset_registry`.** Finding 7: the desired-state file does not declare the registry's table. It is
  a gap that predates this increment and is not closed by it.
- **The UII at the seam.** Events across the iagent seam carry the identity beside `asset_id` (ADR-0056 §2). Not in
  this increment, since no seam carries the identity yet.

## What this does not establish

- Nothing is built, run or measured.
- No identity has been minted, and no alias has been declared.
- The writer and the UII field are ruled (2026-11-11, §2.1, §2.2). Neither is built.
- It does not decide what a tier with no registry does with a declaration.

## Related

- [ADR-0056](ADR-0056-one-identity-per-thing-every-other-id-is-an-alias.md): the decision this builds.
- [ADR-0047](ADR-0047-asset-id-is-opaque.md): opacity, and the workflow check 4 widens.
- [ADR-0050](ADR-0050-asset-arrivals-declare-and-expect.md): the declaration this reads.
- [DESIGN-2026-11-06](DESIGN-2026-11-06-adr0055-compatibility-slice.md): the spec this one follows in shape.
