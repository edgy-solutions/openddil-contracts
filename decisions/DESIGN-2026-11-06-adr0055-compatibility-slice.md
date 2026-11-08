# DESIGN 2026-11-06 — ADR-0055's compatibility slice: `label_key` beside the two columns

**Status:** an implementer spec. Design only: nothing built, nothing run, nothing measured for this slice. Local
branch, not merged. ADR-0055 is PROPOSED except §1a, signed by Chris 2026-11-06. This spec builds ADR-0055 §4 steps
1, 2 and 4 for nation only, and stops before step 3.
**Builds on:** ADR-0055 §2 (the key, the label table, the PEP's one predicate) and §4 (nation first, acceptance to
the row); ADR-0029 (the two columns, the reserved `policy_label`, the current predicate).

## What the slice is

- Every table that carries `originator_nation` and `releasable_to` also carries `label_key` and `label`, the label
  body. Both are computed from the two columns, in the store, at every write.
- Nation is the only dimension, named `nation` (snake_case, ADR-0055 §1, ruled 2026-11-07). The two columns stay authoritative in this slice. The label is derived from them,
  the reverse of ADR-0055 §4 step 3, which comes later.
- The PEP gains a filter switch, `OPENDDIL_LABEL_KEY_FILTER`, **off by default**. Off, the PEP behaves exactly as
  today. On, the PEP filters `label_key IN (:admitted)` in place of the two-column predicate.
- Acceptance is a script that reads before and after the switch and compares, to the row.

**Not in the slice:** the label on the wire (proto `Provenance` field 11 stays reserved), a second dimension, the
PDP computing keys, moving the egress gate onto the key, and any vocabulary beyond the format check below.

## Findings that shape it

1. **Seventeen tables carry the pair** (`openddil-stack` `schema.hcl`): `inventory_items`, `asset_cm_state`,
   `asset_logistics_status`, `telemetry_latest_state`, `tactical_events`, `asset_telemetry_windows`,
   `parts_availability`, `asset_capability_state`, `asset_element_telemetry`, `asset_element_state`,
   `intake_records`, `effector_launch`, `effector_resupply`, `munition_track`, `asset_declaration`,
   `asset_correlation`, `asset_fielding`. A grouped view near `schema.hcl:615-674` uses them too.
2. **The writers are not one path.** Most handlers go through `base.releasability_from`
   (`openddil-projector/src/handlers/base.py:280`). `asset_element_state` and `munition_track` write through
   `postgres.py` (`:918-984`, `:606`). Declaration, correlation and fielding handlers set the columns themselves.
   No projector writer was found for `intake_records`, and the `inventory_items` writer is unconfirmed. **So the key
   is computed in the store, by trigger, not in any one writer.** A trigger covers every writer, including the ones
   not found.
3. **The PEP has no postgres path.** Its reads are Electric shapes (`openddil-demo/gateway/pep.py`). It cannot query
   a label table. It reads one by a shape, like every other read.
4. **Today's predicate** (`pep.py:1462-1488`, `policy_predicate()`):
   `(originator_nation IS NOT NULL AND originator_nation IN (...)) OR (releasable_to IS NOT NULL AND releasable_to && ARRAY[...]::text[])`,
   or `false` with no nations. It is composed into shape where-clauses at `:1533`, `:2693`, `:2766`, `:2914`,
   `:3542`, `:4151`.
5. **One case is not value-neutral, by ADR-0055 §2's ruling.** A row with `originator_nation` NULL and a non-empty
   `releasable_to` is served today by the second clause. Under the key it is unlabelled, so it compiles to no key and
   is served to nobody. `releasability_from` never writes that shape (no originator gives both columns omitted), but
   the writers in Finding 2 that set the columns themselves might. **Ruled by Chris, 2026-11-07:** serving these
   rows today is the defect, so the slice withholds them. The acceptance script lists them as a declared exception
   with the reason `no_originator`, and the row-match is "to the row, except these N, listed". Each listed row is
   owed a declaration (ADR-0055 §4). It is not a permanent exception. It is the only difference the slice is allowed.
6. **Booleans in `pep.py` are parsed inline**, for example `:489-490` (`.strip().lower() == "true"`). The switch
   follows that form. There is no helper to reuse.

## 1. The store

One Atlas migration in `openddil-stack/schema/migrations/`, with `schema.hcl` updated to match.

### 1.1 The policy identifier

```sql
CREATE TABLE label_policy (
  singleton   boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  policy_id   text NOT NULL CHECK (policy_id ~ '^[a-z0-9][a-z0-9:._-]{0,62}$'),
  declared_by text NOT NULL,
  declared_at timestamptz NOT NULL
);
```

- The policy identifier is declared per deployment (ADR-0055 §6), never built in. The migration creates the table
  **empty**.
- The row is written from the deployment's bundle, by whatever the bundle owner names (owed, §6). Nothing in this
  slice writes it.
- With no row, every key is NULL. The switch must then stay off, and the acceptance script refuses to call the
  switch safe (§4).
- Changing `policy_id` later changes every key. That is a backfill (§1.4), not an edit.

### 1.2 The canonical form and the key

One SQL function, `IMMUTABLE` apart from its read of `label_policy` (so it is declared `STABLE`):

```
canonical := 'lk1' || '|' || policy_id
          || '|nation|' || originator_nation
          || '|' || CASE WHEN releasable_to IS NULL THEN '~'
                         ELSE coalesce((SELECT string_agg(DISTINCT x, ',' ORDER BY x COLLATE "C")
                                        FROM unnest(releasable_to) x), '')
                    END
label_key := 'lk1:' || encode(sha256(convert_to(canonical, 'UTF8')), 'hex')
label     := jsonb_build_object('policy', policy_id, 'v', 1,
               'dims', jsonb_build_object('nation', jsonb_build_object(
                 'author', originator_nation,
                 'release', CASE WHEN releasable_to IS NULL THEN NULL
                                 ELSE to_jsonb(<the sorted distinct array>) END)))
```

- **No key** (`label_key` and `label` both NULL) when any of these holds:
  - `originator_nation` is NULL or empty: unlabelled whatever `releasable_to` holds (ADR-0055 §2);
  - no `label_policy` row;
  - any value fails `^[A-Z]{3}$`. That is the format check only. The declared vocabulary is a later slice.
- **Declared-empty and absent differ.** `{ATL}/{}` canonicalises to `...|nation|ATL|` and `{ATL}/NULL` to
  `...|nation|ATL|~`, so they give two keys (ADR-0055 §2).
- **Set semantics.** `releasable_to` is sorted, duplicates dropped, in `"C"` collation, so `{BDR,ATL}` and
  `{ATL,BDR,ATL}` give one key.
- `sha256()` needs postgres 11 or later. The migration asserts `server_version_num >= 110000` and fails otherwise.
- The `lk1` prefix is the canonical form's version. A change to the form is `lk2`, never an edit to `lk1`.

### 1.3 The columns, the label table and the trigger

- Each of the 17 tables gains `label_key text NULL` and `label jsonb NULL`, plus
  `CREATE INDEX ... (label_key)`. Use `CONCURRENTLY` where Atlas allows it; where it does not, the migration names
  the lock taken.
- `label_registry (label_key text PRIMARY KEY, label jsonb NOT NULL, first_seen timestamptz NOT NULL DEFAULT now())`.
  It holds one row per key, and it is a cache (ADR-0055 §2): losing it costs a backfill, never data.
- One trigger function, `BEFORE INSERT OR UPDATE` on each of the 17 tables, `FOR EACH ROW`:
  - it sets `NEW.label_key` and `NEW.label` from `NEW.originator_nation` and `NEW.releasable_to`;
  - when the key is not NULL, it runs `INSERT INTO label_registry ... ON CONFLICT DO NOTHING`.
- Row triggers fire for `COPY` too. **The implementer greps every writer for `session_replication_role`**, because
  `replica` mode skips triggers. Any hit is a refusal to build until it is named in the PR.
- A `BEFORE` trigger changes the row before it is written, so the columns are in the WAL and Electric replicates
  them like any other column. Do not use a generated column. Whether Electric replicates generated columns was not
  checked, and a trigger avoids the question.

### 1.4 The backfill

- Existing rows get their key from one `UPDATE <t> SET originator_nation = originator_nation WHERE label_key IS NULL
  AND originator_nation IS NOT NULL`, run in batches of 5,000 rows by primary key, with the batch count logged.
- **It rewrites every labelled row**, so every Electric shape over those tables sees an update. The repo's record
  shows a bulk commit reaching shapes 10 to 100 s late, and old shapes growing until evicted. The backfill is a
  separate, named step with its own prediction: rows per table, and the shape bytes expected. It is never folded
  into the migration.
- The backfill is a script in this slice, `scripts/backfill_label_key.py`. It is not part of the acceptance script,
  and it never runs inside a helm hook.

## 2. The PEP

### 2.1 The switch

```python
LABEL_KEY_FILTER = os.getenv("OPENDDIL_LABEL_KEY_FILTER", "false").strip().lower() == "true"
```

- It is read once at start, like the other switches. A change is a roll of that PEP: one PEP at a time (ADR-0055 §4
  step 4).
- The chart value that sets it is owed by the helm owner (§6). Its default is `false`.

### 2.2 One function in place of six calls

- Add `row_filter(nations)`. It returns `policy_predicate(nations)` when the switch is off. When it is on, it
  returns the key predicate.
- Every site in Finding 4 calls `row_filter`, not `policy_predicate`. **Check:** `grep -n "policy_predicate(" pep.py`
  shows the definition and the one call inside `row_filter`, and nothing else.

### 2.3 The admitted set, when the switch is on

- The PEP holds one shape over `label_registry`, unfiltered, columns `label_key, label`. It is small: one row per
  distinct label.
- For a viewer with nations `N`, a key is admitted when its body passes today's predicate on the body:
  `author ∈ N`, or `release` is not null and `release ∩ N ≠ ∅`. The test is the same as `policy_predicate`, per
  label instead of per row, so the rows admitted are the same rows.
- The filter is `label_key IN ('k1','k2',...)`, with the keys sorted in `"C"` order and quoted the same way every
  time, so two viewers with the same set give byte-identical definitions (ADR-0055 §2). No admitted keys gives
  `false`.
- **Fail closed.**
  - Before the registry shape is up to date, the filter is `false`.
  - A row whose key is not yet in the PEP's copy of the registry is served to nobody until it arrives. That is
    ADR-0055 §2's "invisible until decided", and it is the one behaviour a viewer can see change when the switch is
    on.
- The decision line gains `filter: predicate|key` and, for `key`, the count of admitted keys. It never lists the keys.

## 3. What must not change

- With the switch off: the PEP's shape definitions are byte-identical to today's, for every route. **Check:** a test
  in the gateway suite renders each route's where-clause with the switch off, and compares it against the output of
  the current code captured before the change.
- The egress gate still reads the two columns. The gate's decisions are recorded by the acceptance script to show
  they did not move.
- `releasability_from` is unchanged.

## 4. The acceptance run, as a script

`scripts/label_key_rowmatch.py` (contracts repo). It only reads: `SELECT`s and HTTP `GET`s. The switch flip is not
the script's. A person flips it, through the chart.

**Exit codes**, as for `migrate_site_declarations.py`: 0 match, 1 diff, 3 refused, 4 unchecked, 78 guard.
**Guard:** it sources `require-cluster.sh` from the helm checkout and halts unless the asserted context is the one
passed. Same mechanism, same code, as the migration script.

### 4.1 Steps

Each step writes its file and stops. The prediction is its own step, and its file is on disk before `read --phase
after` will run. A refusal at any step halts the run, with the state named.

1. **`read --phase before`** (switch off on the PEP under test). It writes `before.json`:
   - **Store, per table, read on postgres directly:** total rows, rows with a key, rows without a key, split by why
     (no originator, no policy row, format), and **Finding 5's count**, rows with NULL originator and non-empty
     `releasable_to`.
   - **Store, per table, per viewer nation set:** the primary keys admitted by the predicate, and the primary keys
     admitted by the key against the registry, both computed in SQL on postgres. This is the strong check. It needs
     no switch, and it runs again in the after phase.
   - **PEP, per viewer session, per shaped route:** the row ids served, read through the PEP to `up-to-date`, never
     from one `offset=-1` GET, plus the Electric handle and offset reached.
   - **Gate:** the forwarder's decision counts, if `--metrics-url` is given. Without it the run exits 4, unchecked,
     and says so.
   - **Shape census:** shapes and bytes per admitted set, from Electric's own figures.
2. **`predict`**. It writes `prediction.json` and `prediction.md`:
   - for each viewer and route, the after set equals the before set, minus Finding 5's rows for that viewer, by id;
   - the `no_originator` list itself: each row's table, primary key and `releasable_to`, so the exception is named
     row by row, not as a count only;
   - for each admitted set, the shapes that will be minted when the switch is on, and their bytes;
   - for one planted key arrival, the shapes replaced and the old shapes' bytes. The planted arrival is made through a
     real path, by a person. It is never an `INSERT`.
3. **`read --phase after`** (switch on, after the PEP's roll). It refuses if `prediction.json` is missing, or if its
   hash of `before.json` does not match. It reads the same things as the before phase.
4. **`compare`**. It writes `compare.json` and `compare.md`, and exits 0 only when every difference is one predicted.
   - `compare.md` opens with the declared exception: "matches to the row, except N rows, reason `no_originator`",
     with the list. It also writes `owed-declarations.json`, one entry per listed row, for a person to declare. The
     script writes nothing to any store.
   - An extra id, a missing id that is not a Finding 5 row, or a gate count that moved is a diff (exit 1).
   - A keyless row that the predicate admits but that is not in Finding 5's class is a diff, and it is named first.
     It means a writer bypassed the trigger.

### 4.2 Inputs

- `--helm-dir`, `--context`, `-n`, and per tier the store pod and database.
- One or more `--viewer NAME --session FILE`. Each session file is read for its first non-empty line only.
- `--pep URL`, `--metrics-url URL` (optional), `--out DIR`.
- The viewer list and routes come from the arguments, never from the script. No deployment name, host or nation set
  is written into the script.

### 4.3 Tests

- Offline unit tests in `tests/test_label_key_rowmatch.py` cover: the canonical form and the key, against fixed
  vectors (`{ATL}/{}`, `{ATL}/NULL`, `{BDR,ATL}` against `{ATL,BDR,ATL}`, NULL originator, a two-letter value);
  admission per label against `policy_predicate`'s truth table; prediction hashing; and compare's classes.
- **The key vectors are shared.** The same fixed vectors run against the SQL function in the migration's test,
  against a real postgres in CI. The SQL and the Python agree because both are tested against one table of vectors,
  not because one was ported from the other.

## 5. Checks for the PR

1. The migration applies on an empty database and on a copy with rows. Every labelled row gets a key after the
   backfill, and no unlabelled row gets one.
2. The key vectors pass in SQL and in Python.
3. With the switch off, the where-clause comparison test passes on every route.
4. With the switch on, in the gateway tests, an empty registry gives `false`, and a viewer's filter is
   byte-identical to another viewer's with the same nations.
5. `grep -n "policy_predicate(" pep.py` shows only the definition and `row_filter`.
6. The writer grep for `session_replication_role` is in the PR description, with its result.

## 6. Owed by others, not built here

- **The bundle owner:** the declared `policy_id`, and what writes the `label_policy` row (§1.1).
- **The helm owner:** the chart value for `OPENDDIL_LABEL_KEY_FILTER`, default `false`, per PEP.
- **Chris:** when the backfill runs, and when each PEP's switch is flipped. The acceptance run's before phase comes
  first each time.

## What this does not establish

- Nothing here has run. The trigger's write cost, the backfill's Electric churn, and the registry shape's lag are
  predicted at run time, not measured here.
- Whether Electric replicates generated columns is not checked. The trigger avoids depending on it.
- `inventory_items` and `intake_records` writers were not found. The trigger covers them whatever they are, and the
  acceptance run's keyless-row check would catch a bypass.
- It does not move the egress gate, the wire, or any dimension but nation.

## Related

- [ADR-0055](ADR-0055-a-label-is-a-set-of-declared-dimensions.md) §2, §4.
- [ADR-0029](ADR-0029-coalition-releasability-abac-enforcement.md): the two columns and the reserved `policy_label`.
- [DESIGN-2026-11-06 site declaration](DESIGN-2026-11-06-site-declaration.md): its migration script's exit codes and
  guard, which this script reuses.
