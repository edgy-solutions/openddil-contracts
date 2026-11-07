# DESIGN 2026-11-06 — The site declaration: a stated answer for a class of records

**Status:** design only, nothing built, nothing run. It is the first increment of ADR-0055 §1a, signed by Chris
2026-11-06; the rest of ADR-0055 is still proposed. The migration script `scripts/migrate_site_declarations.py` is written and tested offline only; it has
never touched a cluster. Local branch, not merged. O1 to O5 are ruled by Chris (2026-11-06).
**Builds on:** ADR-0055 §1a (a default is not a declaration; signed 2026-11-06), §3b (high-water), §4 step 0 (load before amend), §6
(schemes as declared policies); ADR-0050 §2 (the declaration record and its door) and its amendment of
2026-11-06, ruled the same date; ADR-0042 (named exceptions at the parent).

## What this designs, and why it comes first

ADR-0055 §1a, signed 2026-11-06, rules that a default labels nothing, and that a deployment which knows the answer for a class of records
states it as a **site declaration**: a scope, the dimension values, an owner and a date. Until that record exists,
the ruling can only take effect by withholding every record a default labels today. So the record, its door, and the
migration that loads it before any default is removed are the first increment.

This document gives:
1. the record (§1), on the wire and in the store;
2. the owner and the date, and the same two fields on a per-asset file row (§2);
3. the three scopes: a site, a rule, and an exemption (§3);
4. the door, through ADR-0050's intake (§4);
5. where a site declaration is evaluated, and how a stamp cites it (§5);
6. conflicts, at one tier and across two (§6);
7. the load-before-amend migration for the lab, and its script (§7).

## Findings first

What the six default rows of ADR-0055 Findings 3 and the ingest stamp need from a declaration, read from source:

1. **The ingest stamp is evaluated per DIS entity in the ingest sidecar** (`openddil-sensor-ingest/assign.py`).
   Its rules match on a geofence, a marking or a DIS country code (`_parse_match`, `:94`), over the facts
   `marking`, `country` and ECEF location (`_Facts`, `:161`). First match wins, kind 1 only, and the answer is sticky
   per entity (`NationStamper`, `:355`). Overrides map an id to a nation, or to `exempt`. All of it arrives as one
   JSON env var, `DIS_NATION_RULES`, rendered from chart values, with no owner and no date.
2. **The logistics sim's three defaults are per edge, per document, and per deployment**
   (`releasability.py:192-229`). It already consumes `asset-declarations` (`declarations.py`), so a second topic is
   one more consumer of the same kind.
3. **The publisher's spares are keyed by logistics site, not by edge** (`publisher.py:505-520`). A site with no nation
   has no label (`config.py:257`). So a site declaration's scope has to name a logistics site, not only an edge.
4. **The mapper's order is declared, file row, stamp, document default** (`sim-dis-mapping.yaml:60-90`). It reads the
   stamp from `provenance.stamped_nation` and does not know where the stamp came from.
5. **ADR-0050's door is a PEP route that posts to a Connect `http_server` intake**, which writes the compacted topic
   `asset-declarations`, keyed by `asset_id`. The PEP sets `declared_by` from the session and `declared_at` itself,
   refuses unknown body keys, and logs a decision line (`pep.py:1773`, `:2804-2970`).
6. **Nothing exports which source labelled a record.** The sim counts its sources (`_counts`, `:232`), and nothing
   reads the counter. The sidecar keeps no count by source. So "every record a default labelled now cites a
   declaration" (ADR-0055 §4 step 0) cannot be checked today. The census in §7 is the only check that works on the
   current build, and it checks values, not citations.

## 1. The record

A site declaration is its own record on its own topic. It is not a variant of the asset declaration, because every
consumer of `asset-declarations` keys by `asset_id`, and a site declaration has no asset.

### 1.1 Wire: topic `site-declarations`

- Compacted, keyed by `declaration_id`, the same spec as `asset-declarations` (partitions, `retention.ms=-1`).
- Bridged up the tier rail like `asset-declarations`, so the parent holds every child's declarations (§6.2 needs it).
- Never deleted. Withdrawal is a new record with the same id and `status: withdrawn` (§1.3).

| field | value |
|---|---|
| `declaration_id` | assigned by the PEP: `sd:<owning_tier>:<uuid>`. The body never sets it on create |
| `kind` | `site`, `rule` or `exemption` (§3) |
| `scope` | `site`: `{"kind": "edge" \| "tier" \| "logistics-site", "id": "<id>", "records": [...]}`. `rule`: the edge or tier it applies at, in the same form, with `records: ["entity"]`. `exemption`: absent |
| `match` | `rule` only. One of `{"geofence": ...}`, `{"marking": ...}`, `{"country": ...}`, in exactly the shapes `assign.py` parses today, so the evaluator is the one already tested |
| `asset_id` | `exemption` only. The id as observed (ADR-0047) |
| `labels` | the dimension values. For the first dimension: `{"originator_nation": "ATL", "releasable_to": []}`. Absent for `exemption` |
| `declared_by` | the owner: the PEP's session subject, never the body |
| `declared_at` | set by the PEP |
| `declared_role` | the role the PDP decided on for `declared_by`, set by the PEP from the decision, never the body (O3) |
| `reason` | free text, required, at most 512 bytes. The owner says why they know |
| `status` | `active` or `withdrawn` |
| `supersedes` | optional: the id this one replaces. The replaced id gets its own `withdrawn` record in the same request |
| `edge_id`, `region_id`, `owning_tier` | where it was declared, as ADR-0050 §2 sets them |

**`records` names the class of records the owner is speaking for:** `entity` (DIS entities, stamped at ingest),
`logistics` (the sim's per-asset records) or `spares` (a logistics site's spares). It is required. Today's defaults
are each scoped to one class: the sim's per-edge default labels the sim's records and not the DIS records at the same
edge. A declaration scoped to the whole edge would label records no default labels today, and the load would stop
being value-neutral. An owner who knows the answer for every class at a site says so with all three.

### 1.2 Store: table `site_declaration`

Written by a projector handler, the same upsert shape as `asset_declaration` (`handlers/asset_declaration.py`):

```sql
CREATE TABLE site_declaration (
  declaration_id     text PRIMARY KEY,
  kind               text NOT NULL CHECK (kind IN ('site','rule','exemption')),
  scope_kind         text CHECK (scope_kind IN ('edge','tier','logistics-site')),
  scope_id           text,
  records            text[] CHECK (records <@ ARRAY['entity','logistics','spares']),
  match              jsonb,
  asset_id           text,
  originator_nation  text,
  releasable_to      text[],
  declared_by        text NOT NULL,
  declared_at        timestamptz NOT NULL,
  declared_role      text NOT NULL,
  reason             text NOT NULL,
  status             text NOT NULL CHECK (status IN ('active','withdrawn')),
  supersedes         text,
  edge_id            text NOT NULL,
  region_id          text,
  owning_tier        text NOT NULL,
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CHECK (kind <> 'rule'      OR match IS NOT NULL),
  CHECK (kind <> 'exemption' OR (asset_id IS NOT NULL AND originator_nation IS NULL)),
  CHECK (kind =  'exemption' OR (scope_kind IS NOT NULL AND originator_nation IS NOT NULL
                                  AND cardinality(records) > 0))
);
CREATE INDEX site_declaration_scope ON site_declaration (scope_kind, scope_id) WHERE status = 'active';
```

- Never pruned, as `asset_declaration` is not.
- `releasable_to` NULL is refused for `site` and `rule` at the door, so the declared-empty versus absent case of
  ADR-0055 §2 does not arise: a site declaration always states its release, even when it is `{}`.

### 1.3 Withdrawal and replacement

- A withdrawal is a new record with the same `declaration_id`, `status: withdrawn`, its own `declared_by` and
  `declared_at`, and a reason. Compaction keeps the latest, and the table keeps the row.
- A stamp already given under a withdrawn declaration keeps its citation (ADR-0055 §1a: neither is rewritten).
  New stamps stop citing it at the evaluator's next load.
- There is no edit. A change of value is a new declaration that supersedes the old one, so the old id stays
  readable for every record that cites it.

## 2. The owner and the date

- The owner is the session subject that made the request. The date is the PEP's clock at the request. Both are set
  server-side, as ADR-0050 §2 sets them for an asset declaration.
- A role list gates the route (§4). The owner is a person, not a role: the record names the subject.
- **A per-asset file row carries the same two fields.** ADR-0055 §1a: without them it is a default. In
  `releasability.yaml`, each `assets` row gains `declared_by` and `declared_at`. The stamp treats a row without both
  as absent. That edit is to the deployment's bundle, and it is the bundle owner's, not this increment's. Until it is
  made, the precedence in §5.3 keeps the file row in place, so nothing changes at the load.

## 3. Scope: a site, a rule, or an exemption

| kind | covers | used for |
|---|---|---|
| `site` | every record whose edge, tier or logistics site is the scope id | the sim's per-edge default (Findings 3 row 1), its deployment default and `site_nation` (rows 2 and 3, one declaration per edge), the spares (row 4, scope `logistics-site`), the mapper's document default (row 5) |
| `rule` | every DIS entity at the scope whose observed facts match | the ingest stamp's geofence and marking rules |
| `exemption` | one asset id, by name | an ingest override set to `exempt`: a stated "do not stamp this one by rule" |

- **A country-code rule is a `rule` whose match is `country`.** It is also the declared equivalence of ADR-0055 §6:
  the owner states that, at this scope, the source's code means this nation. It is stored the same way, so no second
  record type is needed for the first dimension.
- **An ingest override with a nation is not a site declaration.** It is a per-asset statement. It becomes an
  ADR-0050 asset declaration through the Arrivals panel, made by a person. The migration lists each one and does not
  write them (§7.2).
- **An exemption labels nothing.** It removes one asset from every `rule` at its scope. A `site` declaration still
  covers it. The ingest override `exempt` meant "not by this mechanism", and the sidecar's rules were the mechanism.
- Precedence among them is in §5.3. The exemption's rank there is ruled (O1, 2026-11-06).

## 4. The door: through ADR-0050's intake

- **Route:** `POST /declarations/site` and `GET /declarations/site` on the PEP of the owning tier.
  - The same pre-PDP checks as `/arrivals/declare`: not configured is 404, JSON only (415), a cross-site origin 403,
    a body over 8 KiB 413, unknown keys refused, and server-set fields never read from the body.
  - The PDP checks the role (`OPENDDIL_SITE_DECLARE_ROLES`, default `supervisor`, ruled O3) and that every nation
    in `labels` is within the subject's `allowed_nations`.
  - Vocabulary: each value is checked against the dimension's declared vocabulary (ADR-0055 §1). Outside it is 422.
  - A `rule` match is parsed with the sidecar's own parser before it is accepted, so a match the sidecar would reject
    never reaches the topic.
  - The decision line is `resource: declaration:site`, with the decision id, as for every PEP decision.
  - `GET` answers `{"owning_tier", "root", "edges", "declarations"}`: the tier this PEP declares for, whether it is
    the root tier, the edges it serves (`ARRIVALS_EDGES`), and the active and withdrawn declarations there. The
    migration routes each declaration from these answers, so it never restates the PEP's configuration. A
    `logistics-site` declaration goes to the root tier's PEP, because the spares catalog is one per deployment today.
- **Intake:** the same declaration intake Deployment, a second path `/site-declarations`, which writes topic
  `site-declarations`. One intake, two paths, so there is one door to sever and one to watch.
- **Refusals** carry the decision id, as `/arrivals/declare` refusals do, and the migration logs each one.

## 5. Evaluation and citation

### 5.1 Where it is evaluated

| evaluator | scope kinds | reads declarations from |
|---|---|---|
| ingest sidecar | `rule`, `exemption`, and `site` for its edge | the `site-declarations` topic on the owning tier's broker, consumed from the start |
| logistics sim | `site` (edge and logistics-site) | the same topic, as it already consumes `asset-declarations` |
| DIS mapper | none of its own | the stamp's citation, which the sidecar puts in provenance |

- The sidecar holds the latest record per id in memory and keeps its last known set through a broker outage, as the
  mapper's `declared_labels_known` cache does for asset declarations. A known answer served through an outage is a
  declared answer (ADR-0050, amendment of 2026-11-04).
- Stickiness is today's, so the load cannot move a value: the first observation of an entity decides, and an entity
  no rule matched stays unstamped, as `NationStamper` does now (`assign.py:355`). One change: when a declaration
  loads, an entity whose sticky answer came from a legacy rule is re-cited to the declaration that states the same
  answer. The value does not change, because the plan refuses any translation that would change it (§7.2).

### 5.2 The citation

Each stamp carries, in provenance:
- `label_source`: `declaration` (ADR-0050 asset declaration), `file-row`, `site-declaration`, or `default` while a
  legacy default remains;
- `label_declaration_id`: the declaration id, for `site-declaration`; the asset id, for `declaration`; empty
  otherwise.

The proto fields are numbered at implementation. The projector writes both beside the label, and a table
`asset_label_citation` keeps one row per (asset_id, dimension, declaration_id) with the value, source, first seen
and last seen. That table is what the parent reads to find a two-tier conflict (§6.2), and what the migration's
verify step reads for citations.

Both evaluators export a counter by source: the sidecar `openddil_label_source_total{source}`, and the sim's
existing counts on its metrics endpoint. Without them, §7's verify can check values but not citations (Findings 6).

### 5.3 Precedence

**Target (after the amend):** a per-asset declaration, then a file row with owner and date, then an exemption against
rules, then a site declaration, then nothing.

**Transitional (between load and amend):** a per-asset declaration, then a file row or a legacy ingest override
(with or without owner and date), then a site declaration, then the legacy default or rule, then nothing.
- The site declaration sits above the default it replaces, so loading one that states the same answer changes the
  citation and not the value. That is the whole safety of load before amend.
- The legacy per-asset statements stay above it until a person replaces them, because they outrank rules today. An
  override removed at the amend without a per-asset declaration in its place moves its entity to whatever the rules
  give, or to unlabelled. The prediction lists each one (§7.2), and `verify` reports the amend not ready until each
  is declared.

## 6. Conflicts

### 6.1 At one tier

- Two active declarations of kind `site` or `rule` at one tier that both cover a record and disagree give no stamp
  for that record, and a row in `label_exception` naming both declarations and both owners (ADR-0055 §1a).
- Two that agree give the answer and cite both (`label_declaration_id` holds the sorted ids, comma-joined).
- The evaluator writes the exception through the topic it already writes, not to the store directly.
- The door does not refuse a declaration that conflicts with another one. It cannot know every entity a rule will
  match, and a declaration refused at the door would leave the conflict in the owner's head instead of on the record.
  The migration does refuse to load one, because there the overlap is a sign of a translation error (§7.2).

### 6.2 Across two tiers

- The common parent reads both children's citations from `asset_label_citation`: the same asset and dimension, two
  different declaration ids, two different values. It writes a `label_exception` naming both.
- ADR-0055 §1a: from detection on, the parent serves the asset's records under the high-water of the two answers.
  For nation, the intersection of the audiences.
- **Interim, until `label_key` exists:** the parent cannot serve an intersection on the current columns, so it
  withholds the conflicted asset's records. That is stricter than the ruling, and it is ruled (O2, 2026-11-06).

## 7. Load before amend, on the lab

### 7.1 The order

1. **Plan** (read only). Read every default in use, translate each into a site declaration, read the census, and
   write the plan.
2. **Predict** (separate step). Write what the load and the amend will change, from the plan, with the plan's hash.
   Confirm the file on disk before the next step.
3. **Load.** Post each planned declaration through the PEP, with the operator's own session. Halt at the first
   refusal, with the state named.
4. **Verify.** Read the census again and compare it to the prediction. It must match exactly.
5. **Amend.** Chris's change, not the script's: remove the defaults from the chart values and the bundle, and remove
   step 3 from the mapper and the sim. The script does none of it.
6. **Verify after the amend.** The same comparison, plus `label_source=default` at zero on every evaluator.

There is no rollback past step 3 by the script. A loaded declaration is withdrawn by a person through the door,
with a reason, and the record of both stays.

### 7.2 What the plan translates

| default today | becomes |
|---|---|
| sim `LOGISTICS_SIM_RELEASABILITY_EDGE_DEFAULTS` entry `edge=nation` | `site`, scope edge, records `logistics` |
| sim `LOGISTICS_SIM_SITE_NATION`, or the document's `default_originator_nation` | `site` for each edge that has no edge default, scope edge, records `logistics` |
| a logistics site's nation in `cfg.sites` | `site`, scope `logistics-site`, records `spares` |
| ingest rule with `geofence`, `marking` or `country` | `rule`, scope edge, same match |
| ingest override `exempt` | `exemption` |
| ingest override with a nation | **not written.** Listed for a person to declare in Arrivals |
| mapper document default (`/ontology/releasability.yaml`) | `site` for each edge, records `entity` |
| a file `assets` row without `declared_by` and `declared_at` | **not written.** Listed as owed by the bundle owner (§2) |

Refusals at plan time, each of which halts the run with the state named:
- a value outside the declared vocabulary;
- an override with a nation whose file row gives a different nation;
- two translated declarations whose scopes overlap with different values, for the same record class. A box against
  a box and a country against a country are decided. A marking regex, or two different match kinds, is undecidable
  and refused, for a person to rewrite as disjoint boxes or countries. A `site` covers every record of its class at
  its scope, so an entity `site` against any `rule` of another nation at that edge is a conflict. Today these
  resolve by first match, or by the stamp outranking the document default; §1a has neither rule, so loading them
  would turn today's answer into no answer;
- an env var that is not inline (from a ConfigMap or Secret reference), because the plan would be reading the chart
  and not the deployment;
- the increment not deployed: no `site_declaration` table, or the PEP route answering 404.

### 7.3 The census

For every table with both `asset_id` and `originator_nation` columns, discovered from `information_schema` and not
listed by hand, at every tier store: the distinct (asset_id, originator_nation, releasable_to) triples, and the
unlabelled ids. The prediction for the load and for the amend is the same: **no triple changes, no id moves between
labelled and unlabelled.** Any difference fails the step, and is not tuned away.

Bulk writes reach Electric shapes 10 to 100 s after the commit, so the census reads postgres directly, never a shape.

### 7.4 The script

`scripts/migrate_site_declarations.py`, with subcommands `plan`, `predict`, `load` and `verify`.

- It runs the chart's cluster guard first (`<helm>/scripts/lib/require-cluster.sh`), refuses on its exit 78, and
  pins every kubectl call to the asserted context.
- Each step writes its output to `--out`: `plan.json`, `census-before.json`, `prediction.json` and
  `prediction.md`, `load-log.json`, `verify-<ts>.json`.
- `load` refuses without a prediction whose plan hash and census hash match the files on disk, and refuses at
  another context or namespace than the plan's. It skips a declaration already active with the same kind, scope,
  match and values (read from `GET /declarations/site`), and never retries a refusal.
- `verify` exits 0 only when the census is equal, `label_exception` is empty at every store, and every
  `--metrics-url` reads zero for `label_source="default"`. With no metrics URL it exits 4, "census equal, citations
  not read", which is not a pass. With `--after-amend` it also requires every listed override to be declared.
- The pure parts (translation, overlap, census diff, the prediction) are tested offline in
  `tests/test_migrate_site_declarations.py` (37 tests, run locally). No workflow runs that directory yet. Nothing
  else is tested, because nothing else has run.
- It lives in contracts until the design is ruled, then moves to `openddil-helm/scripts`, beside the guard.

## Check

1. **Load changes no value.** On the lab, the census after `load` equals the census before it, to the triple.
2. **Load changes the citation.** After `load`, `label_source=default` is zero on the sidecar and the sim, and every
   record a default labelled cites a site declaration.
3. **Amend changes nothing further.** After the amend, the census still equals the census before the load.
4. **A refusal halts.** A planted planned declaration with a value outside the vocabulary halts `load` at that
   declaration, with the ones before it named as loaded and the rest as not attempted.
5. **One-tier conflict.** Two planted `site` declarations at one edge with different nations give no stamp and one
   `label_exception` row naming both.
6. **Two-tier conflict.** One asset stamped under different declarations at two children gives one exception at the
   parent, and the parent withholds it (interim) while each child keeps its own label.
7. **Withdrawal.** Withdrawing a loaded declaration stops new stamps citing it and leaves old citations in place.

## What this does not establish

- Nothing is built, and nothing has run against a cluster. The script's cluster paths are untested.
- The PEP route, the intake path, the topic, the table, the projector handler, the sidecar consumer, the citation
  fields and both counters are all designed here and exist nowhere.
- Overlap of marking regexes is not decided. The plan refuses them rather than guessing.
- The effector path (Findings 3 row 6) has no declaration lookup, and this design does not give it one. It is
  already open in `FOLLOW-UPS.md`.
- It does not design the screen where an owner sees their declarations and exceptions. `GET /declarations/site` is
  the read it would use.
- It does not cover any deployment other than the lab.

## Rulings (were open items)

- **O1. The exemption kind and its rank. RULED by Chris, 2026-11-06: keep the kind, with an owner, at the rank
  proposed.** An exemption declares that a class of records carries no label by decision, such as a non-asset source
  or a test entity. Dropping the kind would force per-asset declarations for things that are not assets. The rank is
  a per-asset declaration, then a file row, then an exemption against rules, then a site declaration (§5.3).
- **O2. The interim withhold at the parent. RULED by Chris, 2026-11-06: yes.** Stricter than §1a is the right
  direction for an interim. Until `label_key` can serve the intersection, a two-tier conflict shows as a named
  exception with nothing served, not as something served wrongly (§6.2).
- **O3. The role. RULED by Chris, 2026-11-06: supervisor only.** One declaration labels a class of records, which is
  a wider act than declaring one arrival. The arrivals roles are for the one-asset case and stay there. The role name
  is written into the declaration record (`declared_role`, §1.1). Whether a declaration was made under the
  right role is then read from the record corpus, never from what the UI allowed.
- **O4. The sidecar's broker. RULED by Chris, 2026-11-06: the owning tier's broker.** A mounted file would be chart
  configuration that only looks like a record, and it would need a roll to change. A record on the tier's broker is
  declared through the door, is versioned, and is still there when the edge is severed.
- **O5. The record class. RULED by Chris, 2026-11-06: yes.** §1a names a scope as a site or a rule. This design adds
  `records` to the scope (§1.1). Without it the sim's per-edge default would leak into the DIS entities at that edge,
  which is the kind of mislabel §1a exists to stop. It narrows what one declaration says; it does not add a source.

## Related

- ADR-0055 §1a, §3b, §4, §6 (`ADR-0055-a-label-is-a-set-of-declared-dimensions.md`).
- ADR-0050 §2 and the amendment of 2026-11-06, ruled (`ADR-0050-asset-arrivals-declare-and-expect.md`).
- ADR-0042, named exceptions at the parent (`ADR-0042-intent-custody-retention-and-multi-tier-reconciliation.md`).
- ADR-0029 §3, labels propagate and never default.
