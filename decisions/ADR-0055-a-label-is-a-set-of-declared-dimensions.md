# ADR-0055 — A label is a set of declared dimensions, compiled to one key

## Status

**PROPOSED — 2026-11-06. Design only. Nothing here is built, nothing is deployed, and nothing has been measured.**
- It generalises [ADR-0029](ADR-0029-coalition-releasability-abac-enforcement.md)'s two nation fields into a label of declared dimensions. It does not supersede ADR-0029. ADR-0029's predicate, its addendum and its gate stay true for the nation dimension.
- The number is provisional until the record is accepted.
- **§1a is signed by Chris, 2026-11-06, and is decided.** The rest of the record stays PROPOSED until it is accepted after review. The ADR-0050 amendment §1a implies is ruled the same date, in load-before-amend order.

## Findings first

This comes from a read-only inventory of every line that names `originator_nation` or `releasable_to`, across all 15 repos.
- **Method:** `git grep -n -I -E "originator_nation|releasable_to"` on each repo's checked-out tree. A hit is one matching line per field, and substrings count.
- **Classification:** each hit was put in one role by reading its file. Tests and docs were classified by path.

**1. 1,889 hits in 268 files, across 15 repos.**

| Repo | Files | Hits |
|---|---|---|
| openddil-demo | 66 | 543 |
| openddil-projector | 18 | 228 |
| openddil-customer-bundle-example | 66 | 197 |
| openddil-stack | 18 | 189 |
| openddil-contracts | 28 | 162 |
| openddil-logistics-sim | 10 | 162 |
| openddil-helm | 17 | 110 |
| openddil-tactical-agents | 10 | 84 |
| openddil-cm-service | 3 | 40 |
| openddil-logistics-fusion-service | 2 | 20 |
| cortex-ui | 5 | 16 |
| iagent-mesh-sdk | 2 | 9 |
| invincible-agent (iagent) | 6 | 9 |
| Two private repos (counted only, not listed) | 17 | 120 |

| Field | Writer | Enforce | Display | Pass-through | Schema | Config | Test | Doc | Total |
|---|---|---|---|---|---|---|---|---|---|
| `originator_nation` | 103 | 36 | 20 | 78 | 77 | 77 | 413 | 192 | 996 |
| `releasable_to` | 85 | 35 | 5 | 76 | 68 | 65 | 365 | 194 | 893 |
| **Total** | 188 | 71 | 25 | 154 | 145 | 142 | 778 | 386 | 1,889 |

- Writers are in 29 files. Enforcing readers are in 13.
- Of the 1,889 hits, 1,164 are tests or docs.

**2. One definition, and two places that decide.**
- **The definition.** The fields are defined in one place, `openddil-contracts/proto/openddil/telemetry/v1/telemetry.proto`:
  - `:419` is field 9 and `:425` is field 10.
  - `:432` reserves 11 for `policy_label`.
  - `:455` has relays carry the leaf fields unchanged.
- **The read path.** `openddil-demo/gateway/pep.py:1462-1488` (`policy_predicate`) renders `(originator_nation IS NOT NULL AND originator_nation IN (…)) OR (releasable_to IS NOT NULL AND releasable_to && ARRAY[…])`.
- **The egress gate.** `openddil-demo/egress/gate.py:372-399` (`compile_predicate`) is "clause for clause the read path's SQL". It refuses an unlabelled record at `:675`.
- **Re-applications, not decisions.**
  - The pane's viewer filter (`openddil-demo/gateway/egress_view.py:52-130`).
  - The intake's label-equality check (`openddil-demo/egress/intake.py:584-585`).
- **The other enforcing readers** check that a label is present or well formed. None decides who sees what:
  - the SDK's maintenance bridge;
  - iagent's maintenance-fault intake trigger;
  - the contract-b conformance validator;
  - the declaration-intake config;
  - logistics-sim config;
  - two projector handlers;
  - the regional aggregator.

**3. Six places admit or label without a source label. Everything else read fails closed.**

Three are declared positions or configuration:
1. **With nothing configured, the PEP's refusal of unclassified tables is off.**
   - Every table falls to the nation class (`openddil-demo/gateway/pep.py:1436-1437`).
   - The comment: "EMPTY MEANS THE CHECK IS OFF, and that is announced at boot" (`:944`).
2. **The role class applies no clause** (`pep.py:4135-4143`). This is declared for tables that carry no asset data, and "Widening it to anything asset-bearing would be a bypass wearing this class's name" (`:966-973`).
3. **Oversight roles read subject-scoped tables unfiltered** (`pep.py:4146-4147`). The default role is `auditor` (`:996-997`).

The other three stamp a nation the source did not give. They are six default rows in three places:

| # | Path | What is stamped | When | Against ADR-0050 §2.6 |
|---|---|---|---|---|
| 1 | `openddil-logistics-sim/src/logistics_sim/releasability.py:204-208` | The per-edge default (`releasability_edge_defaults`) | No arrival declaration and no file row | Step 3, "a deployment default, e.g. per edge" (ADR-0050:92) |
| 2 | `releasability.py:210-212` | The document's `default_originator_nation` | After row 1 | Step 3 |
| 3 | `releasability.py:214-224` | The deployment's `site_nation`. It logs "as a default, not a declaration" | After row 2 | **Not in §2.6.** It is a fourth fallback |
| 4 | `openddil-logistics-sim/src/logistics_sim/publisher.py:513-516` | The site's nation on every site-spares record | Every sweep, unconditionally | Not covered. A spares record is not an asset, and no declaration source exists for a site |
| 5 | `openddil-demo/dynamic-mappings/sim-dis-mapping.yaml:75-82`, and the same at `:261-268` | The ingest stamp, then the document default | No declaration and no file row, and the lookup did not fail | Follows step 3 and the 2026-11-04 amendment. A failed lookup stamps nothing (`:82`, `:268`; ADR-0050:180) |
| 6 | `openddil-demo/dynamic-mappings/dis-effector.yaml:93-106` | The launcher's file row, then the ingest stamp, then the document default | Always. There is no declaration lookup and no failed-lookup guard | **Does not follow §2.6's order.** Already OPEN as a Fire defect (FOLLOW-UPS.md:109-118) |

- The shipped document default is null, so rows 2, 5 and 6 stamp nothing unless a deployment sets one. Rows 1 and 3 are also deployment settings.
- FOLLOW-UPS.md:30 records that rows 1 and 3, on a deployment with declared assets, give the mislabel already seen once.
- **ADR-0050 §2.6 permits a deployment default.** Its step 3 is one (ADR-0050:92). The 2026-11-04 amendment refuses a stamp or a default only when the lookup failed with no answer (ADR-0050:180).
- ADR-0050 also summarises ADR-0029 §3 as "labels propagate, never default" (ADR-0050:5, :210). Its own step 3 contradicts that.
- §1a below rules that a deployment default is not a declaration. Chris signed it on 2026-11-06.

The projector copies the label as it receives it (`openddil-projector/src/handlers/base.py:289-297`):
- With no nation it writes neither column, so both are NULL.
- With a nation and no further release, it stores `releasable_to = []`, so the row is labelled on both columns.
- An aggregate stores no nation and a list (`:356-357`).

**4. No derived record computes a high-water label.**
- **Copy one input's label:**
  - fusion (`openddil-logistics-fusion-service/src/workflows/asset_logistics.py:171-192`, `:967-969`);
  - the edge agents (`openddil-tactical-agents/edge/faust_edge.py`; `edge/prognostics/agent.py:197-198`).
- **Sticky label:** CM state takes the label of the latest event that states one. An event that omits it clears nothing (`openddil-cm-service/src/events/asset_cm.py:196-205`).
- **The regional rollup partitions instead of intersecting.**
  - `openddil-tactical-agents/regional/aggregator_app.py:591-607` (`_effective_audience`) and `:633-656` (`_partition_by_audience`) group contributors by effective audience and emit one row per class.
  - Its docstring reads: "fourteen contributors in three classes … whose intersection is EMPTY … each class becomes an ORDINARY LABELLED ROW whose releasable_to IS its class."
  - ADR-0029 decides "the intersection of effective audiences" (ADR-0029:1102).
  - The regional tier design called intersection "the candidate rule" (DESIGN-2026-09-05-regional-tier-node.md:267).
  - No decision record decides the partition. §3 below adopts it as the decision for composable rollups.

**5. Contradictions in the record.**
- ADR-0029:302 says the fields are "not yet in" the proto. ADR-0029:631 marks that step DONE, and the proto has them.
- iagent ADR-0064 (`docs/adr/ADR-0064-classification-propagates-through-derivation.md`, Proposed) agrees on the structure:
  - a derived column takes the maximum of its sources (`:35-36`);
  - an unlabelled source is most restrictive;
  - downgrades are recorded with level, reason and steward (`:48-49`).
- But it then makes one downgrade automatic: "One downgrade is automatic", for an aggregation that drops identifying columns (`:50-51`). §3 below refuses that, and §6 names it as an open alignment item.
- Its levels are one ordered registry (`:92`), so it has only the hierarchical type.
- These are the findings as read on 2026-11-05. Since then, invincible-agent PR #281 (branch
  `lane/01-adr-0064-dimensions`, commit `4685ca45`) amends ADR-0064 to align with this record. ADR-0064 is still
  Proposed. §6 records what the amendment changes.

**6. The value format diverges.**
- The contract-b validator requires three uppercase letters.
- The SDK accepts any non-blank string.
- Agent tests use two-letter or placeholder codes.
- The SDK validator and iagent's trigger refuse a blank originator. Nothing checks the format of `releasable_to`.

**7. What the inventory does not cover.**
- The ingest's stamped nation (`stamped_nation`, openddil-sensor-ingest) is under another name, so the grep does not count it. The DIS mapping reads it into `originator_nation` (`openddil-demo/dynamic-mappings/sim-dis-mapping.yaml:80`). It comes from per-entity overrides and from rules matched on an entity's geofence, marking or DIS country code (`openddil-sensor-ingest/assign.py:102-145`, `:331-338`). §1a classifies it.
- The policy engine's rules are not in the runtime repos.
- A hit's role is a reading of its file, not a run.

## Decision

### 1. A label is a set of declared dimensions

A deployment declares each dimension it labels by. A declaration gives a name, one of four types, the vocabulary of values, and the owner who decides what the values mean. A record's label holds a value set for every dimension the deployment declares.

**Dimension names are snake_case, by rule (ruled by Chris, 2026-11-07).** A name matches `^[a-z][a-z0-9_]*$`, and the
contract vocabulary writes that form. The key is built from the name (§2), so the key builder normalises a name to
that form before it digests it, and one dimension cannot mint two keys by its spelling. The first restrictive
dimension is `data_rights_holder`, which is also iagent's form.

| Type | A record carries | A viewer is admitted when | Empty set means |
|---|---|---|---|
| **Hierarchical** | One level from an ordered list | The viewer's level is at or above it | Not allowed. A hierarchical dimension always has a level |
| **Permissive set** | Values that widen the audience, such as nations it is releasable to | The viewer holds at least one of them | Released to nobody by this dimension |
| **Restrictive set** | Values that narrow the audience, such as caveats, compartments or data-rights holders | The viewer holds every one of them | No restriction from this dimension |
| **Exclusionary** | Values that bar a holder | The viewer holds none of them | No exclusion from this dimension |

**The last column is the default inside a deployment. A boundary may declare otherwise (amendment, drafted
2026-11-07, not yet ruled).**
- A deployment, and each egress destination it declares, may set per dimension:
  - `required`: an empty or absent value at that boundary is withheld there;
  - `empty_means`: what an empty set means at that boundary.
- **Why.** "An empty restrictive set means no restriction" is right inside a mesh and wrong at an egress to a third
  party. Take a record with no `program` value bound for an OEM. Inside the mesh it is unrestricted. At the OEM
  boundary it must not leave by default.
- **A required dimension that is empty or absent at a boundary is withheld, loud.**
  - The reason is `dimension_missing`, named and counted for the owner.
  - It is never a silent drop.
- **The declaration is per boundary.** Nothing moves the in-mesh default. A destination that declares nothing keeps
  the table's meaning.

**Access is the conjunction.** A viewer sees a record only when every declared dimension admits them.

**Undeclared fails closed, both ways.**
- A record with no value for a declared dimension is served to nobody. This is ADR-0029 §7's deny-unlabeled, generalised.
- A record carrying a dimension the deployment does not declare is served to nobody, and the stamp that wrote it is a defect.
- **On an inbound record, that refusal is loud (ruled by Chris, 2026-11-07).**
  - It is refused at intake with the reason `dimension_undeclared`, and the dimension is named and counted. It is
    never a silent withhold.
  - **The record is kept, served to nobody, and counted (ruled by Chris, 2026-11-07).** It is handled like an
    out-of-vocabulary value: withheld so it can be corrected, never dropped.
  - A deployment that wants to receive the dimension declares it.
  - `program` is never declared at an edge (§5).

**Values are validated at the stamp.**
- Each dimension declares its vocabulary. For nation, that is ISO 3166-1 alpha-3, by the dimension's declaration, not by code.
- A value outside the declared vocabulary is refused at the stamp, the same as an undeclared dimension.
- The record is withheld, not dropped. It is kept and served to nobody, so it can be corrected. ADR-0050 withholds the same way.
- The reason is Findings 6: three readers accept three formats for one field today.

**The nation dimension keeps its author.** A permissive dimension may declare one author value. For nation, that value is `originator_nation`, and the audience is ADR-0029's effective audience, `{originator} ∪ releasable_to` (ADR-0029:1100-1106). The author value grants access only on records whose derivation preserved single authorship (ADR-0029:1086-1088).

### 1a. A default is not a declaration (SIGNED BY CHRIS, 2026-11-06)

**Ruling.** A default is a label nobody stated about this record. It is not a declaration, and it labels nothing.

**What it covers.**
- Every row of Findings 3's default table.
- The ingest stamp, which is three things. None of them carries an owner or a date today:
  - per-entity overrides, which are per-asset statements held in configuration;
  - rules matched on an entity's geofence, marking or DIS country code, which are standing statements about a class of entities;
  - for a country rule, a mapping from the source's code to the nation vocabulary.
- Each becomes a declaration of its kind, or it stops stamping.

**A site declaration is a declaration.**
- Where a deployment knows the answer for a class of records ("everything at this site is ATL unless declared otherwise"), it writes a **site declaration**: the scope, the dimension values, the owner and the date.
- The scope is a site, or a rule over observed attributes such as a geofence, a marking or a country code.
- It is stored as a record through the declaration intake (ADR-0050 §2).
- Every stamp it gives cites its id.
- A country-code mapping is an equivalence between schemes, declared per deployment with an owner (§6).
- A site's own records, such as its spares, are covered by a site declaration whose scope is that site.

**The stamp has two outcomes:** a declared answer, citing the declaration it came from, or nothing. Nothing means unlabelled, so withheld. A last known answer served through a store outage is a declared answer (ADR-0050, amendment of 2026-11-04).

**Precedence: a per-asset declaration, then a site declaration, then nothing.**
- Among per-asset sources, ADR-0050 §2.6's order holds: the file's `assets` row wins for an id already in the fleet.
- **A per-asset row in the deployment file carries an owner and a date, or it is a default.** It is the strongest source in the order, so it carries the same two fields as a site declaration. Without them it is a default with a narrower scope, and it labels nothing.
- Two site declarations at one tier that both cover a record and disagree give nothing for that record, and a named exception to both owners. No first-match or narrowest-scope rule picks between them.
- Two that agree give the answer and cite both.

**Two tiers, two answers.** Each tier stamps from the declarations it holds, with no coordination, so stamping works while severed. So two tiers can hold different site declarations that cover one asset: an asset that moved between sites, or two owners who disagree.
- Each record keeps the label its stamp gave, and the declaration it cites. Neither is rewritten.
- The tier that receives both, their common parent, detects the conflict: the same asset and dimension, under two different declarations with different values. It raises a named exception to both owners, as ADR-0042 does for cross-child conflicts (ADR-0042:220).
- From detection on, that parent serves the asset's records under the high-water of the two answers (§3b). For nation, that is the intersection of the two audiences. If it is empty, nobody sees them. This raise is a standing rule of this record.
- Only a per-asset declaration resolves the conflict, because it outranks both. No recency rule and no tier rank picks a winner.

**What it changes.**
- ADR-0050 §2.6 step 3. The amendment is in ADR-0050, dated 2026-11-06, ruled the same date.
- Each default row in Findings 3, and the ingest stamp, becomes a declared source or stops stamping.
- ADR-0029 §3's "never default", as ADR-0050:5 summarises it, becomes true as written.
- The order is load before amend (§4, step 0).

### 2. Labels compile to a `label_key` at stamping

The stamp that writes a label today, at ingress (ADR-0029 §3), also compiles it to a `label_key`:
- The key is a digest of the label's canonical form: the policy identifier, then each declared dimension in a declared order, with its values sorted.
- The same label gives the same key at every tier, with no coordination. Two tiers that stamp independently while severed agree on the key.
- **The label body rides on every record, always, beside its key.**
  - A sender cannot know what a receiver holds across a sever, or after the receiver's store is wiped, so "the first record" is not something a sender can rely on.
  - A later record that arrives first carries everything it needs, so a reorder costs nothing.
- Each tier keeps a label table, one row per key. It is a cache: losing it costs a recompute, never data.
- A receiver recomputes the key from the body. A key that does not match its body is refused at the stamp, like an undeclared dimension.

**The PDP computes admitted keys per viewer.** For each viewer, the tier's decision point evaluates each distinct label against the viewer's asserted entitlements (ADR-0029 §5). It returns the set of keys the viewer is admitted to. Distinct labels are few next to records, so the decision runs per label, not per row. The set is recomputed when a policy bundle, a viewer's entitlements, or the set of known keys changes.

**The PEP filters on the key.** The read path's filter becomes one predicate, `label_key IN (:admitted)`, in place of ADR-0029's disjunction. A key the PDP has not yet evaluated is admitted to nobody, so a record with a new label is invisible until it has been decided, never visible before.

**Shapes are per admitted set, not per viewer.**
- **One canonical filter.** The PEP writes the filter in one form: the admitted keys sorted, with the same columns and the same flags. Two viewers with the same admitted set produce byte-identical shape definitions and share one shape. Any difference in the definition mints a new shape, as this stack has measured.
- **Shapes scale with entitlement profiles, not people.** The count is distinct admitted sets, a handful of profiles, times the bounded reads. Today a bounded read is one shape per asset.
- **A person's change mints nothing new.** A change to one person's entitlements moves them to the shape of the set they now hold. If another viewer already holds that set, no shape is minted.
- **The cost moves; it does not go away.**
  - A new key admitted to a set changes that set's filter, so every shape of every set admitted to the key is replaced.
  - Each old shape stays, unread, until it is evicted.
  - So a key's arrival costs (sets admitted to it × bounded reads) new shapes, plus the old shapes' bytes until eviction.

**The key carries what the wire cannot.** ADR-0029's addendum records that proto3 cannot tell an empty `releasable_to` from an absent one (ADR-0029:1120-1136). A canonical form encodes "declared and empty" and "absent" differently, so the key keeps a distinction the two repeated fields lose.
- **The distinction applies only to `releasable_to` on a record that has an originator.** There, `{ATL}/{}` and `{ATL}/absent` give two keys.
- **A record with no originator is unlabelled, whatever `releasable_to` holds.** NULL/NULL and NULL/`{}` compile to no key at all, not to two keys, and the record is served to nobody (§1).

### 3. Derived records: a split by audience for composable rollups, high-water for single derived records

There are two rules, chosen by what is derived.

#### 3a. A composable rollup splits by audience

A **composable rollup** is an aggregate over many contributors whose parts a reader may combine, such as a count, a sum or a tally by status.
- It first splits its contributors into classes.
- A class holds the contributors that share one label, as each would carry it in the aggregate. For nation, that is the effective audience: in an aggregate the author value no longer grants access alone (ADR-0029:1086-1088). For every other dimension, it is the value set.
- The rollup computes one row per class, **from only that class's contributors**.
- **A contributor with no label forms no class.**
  - It is excluded from every row.
  - It is counted in a withheld-contributor tally that the rollup's owner can see.
  - So the rollup never hides that it is missing a contributor.
- Each row carries its class's label, so its key is that label's `label_key`.

**Why this rule, and not high-water.**
- A high-water rollup over contributors with disjoint audiences takes an empty intersection, so nobody can read it. These are ADR-0029's collapse cases (ADR-0029:1116-1118).
- The built rollup's own case shows it: fourteen contributors in three classes, {ATL} ×7, {BDR} ×6 and {ATL, BDR} ×1, whose intersection is empty (`openddil-tactical-agents/regional/aggregator_app.py:633-656`).
- The split gives every viewer a rollup of exactly what they may see. Combining the rows a viewer is admitted to gives that viewer's whole rollup. No row holds a contributor its viewers may not see.
- Each row is also high-water within its class, because every contributor in a class has one label.

**Status.** This is the rule the regional rollup already builds, and no record decided it before this one (Findings 4). It generalises from the nation audience to the full label.

**Limit.** An aggregate that cannot be combined across classes is not a composable rollup. A median, a single fleet status or a ranking each come out as one record, so §3b applies.

#### 3b. A single derived record takes the high-water label

A record computed from labelled inputs and emitted as one record, such as a fusion result, takes the most restrictive combination of its inputs' values, dimension by dimension:

| Type | High-water of the inputs |
|---|---|
| Hierarchical | The highest level |
| Permissive set | The intersection of effective audiences. This is ADR-0029's addendum, unchanged (ADR-0029:1100-1118) |
| Restrictive set | The union |
| Exclusionary | The union |

- An input with no label makes the derived record unlabelled, so nobody sees it. These are ADR-0029's collapse cases (ADR-0029:1116-1118).

#### Both rules

- The label each rule gives is a floor, not the answer. An aggregate can be more sensitive than every input (ADR-0029:546-552). Raising a derived record above it is a policy decision, like lowering one.

**Sanitised release is a policy decision with an owner.** Any label on a derived record below the label its rule gives is a downgrade. A downgrade is a record of four things: the label it gives, the reason, the inputs it covers, and the owner who decided it. The owner is a person or role named in the declaration of each dimension the downgrade lowers. A downgrade with no owner or no reason is refused. The framework performs no automatic downgrade. A standing downgrade rule is allowed only as a declared rule that a named owner has signed. It is applied as that owner's decision, and every application records it.

### 4. Migration: nation is the first declared dimension

0. **Load the site declarations, and read the values, before anything changes.**
   - On every deployment that stamps by a default today (any row of Findings 3, or an ingest nation rule or override):
     1. Write the site declarations that state the same answers, and load them.
     2. Confirm that every record a default labelled now cites a declaration with the same value.
     3. Only then amend ADR-0050 step 3 and remove the defaults.
   - In the other order, every record labelled only by a default goes unlabelled at the amendment, and acceptance fails by exactly those rows.
   - Before the stamp validates vocabulary, read the distinct values in every labelled table on each deployment. A value outside the vocabulary is corrected by declaration before the run.
   - **Measured starting point (both lab deployments, read at 04:10Z):** nation values are `ATL` and `BDR`. All are three letters, with no variants. No correction is owed there.
1. Declare `nation` as a permissive dimension, with `originator_nation` as its author value.
2. Stamp the label and the `label_key` where `originator_nation` and `releasable_to` are stamped today.
3. Keep `originator_nation` and `releasable_to` as **projections** of the label. They are written from the label at the same stamp, never set on their own. Every reader of the old columns keeps working unchanged.
4. Move enforcement to `label_key`, one PEP at a time.

**Acceptance is a run that matches today, to the row.** The run uses the lab fixture fleet and its viewers. Before and after the move, it records:
- for every viewer, the ids of the rows each screen serves;
- for every destination, the gate's decisions;
- for every labelled table, its row counts, labelled and unlabelled;
- the shape census. For every admitted set, its shapes and their bytes. At one planted key arrival, the shapes replaced and the old shapes' bytes, against a prediction written before the run.

Any difference fails the migration. A difference is not tuned away.

**One difference is named, not tuned away (ruled by Chris, 2026-11-07).**
- A row with no originator and a non-empty `releasable_to` is served today, by the second clause of ADR-0029's
  predicate. Under §2 it is unlabelled, and serving it today is the defect.
- So the move withholds it.
- The acceptance run reports these rows as a declared exception, with the reason `no_originator` and their count.
  The row-match is to the row, except these N rows, which are listed.
- **Each listed row is owed a declaration. It is not a permanent exception.** A row that gains a per-asset or site
  declaration is labelled by it and leaves the list.

### 5. First slice: one restrictive dimension

The first new dimension is **`data_rights_holder`**, a restrictive set. A record that carries data a holder licensed is visible only to viewers entitled by that holder.

**Its red case is a same-nation refusal:**
- The viewer is `ATL`. The record has `originator_nation = ATL`, so today's predicate admits the viewer on the author branch alone.
- The record also carries `data_rights_holder = {H}`, and the viewer holds no entitlement from H.
- After the slice, the viewer is refused.

Today's two fields cannot express that refusal. The test fails on the current predicate and passes on the conjunction.

**Against iagent's first dimensions.** iagent answered the brief's first question (its reply of 2026-11-06, and ADR-0064
as amended by PR #281, "Classification is a label of declared dimensions"):

| iagent dimension | Type | Here |
|---|---|---|
| `level` | hierarchical | not declared. No first slice here has a hierarchical dimension. Inbound, it is refused as `dimension_undeclared` (§1) |
| `program` | restrictive set | not declared, and never at an edge. iagent keeps it as a row filter at ticket time, not stamped on the dataset. Inbound, it is refused as `dimension_undeclared` (§1) |
| `data_rights_holder` | restrictive set | this slice, by the same name (§1, ruled 2026-11-07) |
| `nation` | permissive set | §4, the first dimension. iagent takes its vocabulary from this side |

- **Two dimensions are shared:** nation, and the data-rights holder of this slice. Both sides type them the same.
- **One name (ruled by Chris, 2026-11-07).** Both sides write `data_rights_holder`. §1's snake_case rule makes that
  the only form.
- **`level` and `program` have no declaration here.**
  - A record that crosses from iagent carrying either is refused at intake as `dimension_undeclared`, named and
    counted (§1). That failure is correct, and it is loud.
  - A deployment that receives them declares them.
  - `program` is never declared at an edge. Where it is declared, and how it is filled, belongs to the
    identity draft's "sustained-under" relation (ADR-0056, provisional), not to this record.

### 6. Alignment by concept name, schemes as declared policies

| This record | STANAG 4774 / 4778 concept |
|---|---|
| The deployment's declared policy | Policy identifier (4774) |
| Hierarchical dimension | Classification (4774) |
| Permissive set | Permissive category (4774) |
| Restrictive set | Restrictive category (4774) |
| Exclusionary | No 4774 category type in the sources read. It is carried as a declared policy |
| The label stamped on the record and carried with it | Metadata binding (4778), as a concept only. `label_key` is not a cryptographic binding |

ADR-0029 already adopts the concepts and not the standards (ADR-0029:39-45, 616-618). This record keeps that position, and its structured label fills the `policy_label` slot ADR-0029 reserved (ADR-0029:112-121).

**CUI, NATO, EU and national schemes are declared policies under this one structure.** Each is a policy identifier, with its dimensions declared by type. No scheme is built in.

**Equivalence between schemes is declared per deployment, never inferred.**
- A deployment that treats one scheme's marking as equal to another's writes that mapping down, with an owner.
- No code maps one scheme to another by name, by level order or by position.
- A record under a policy the deployment does not declare is served to nobody.

**Aligned with iagent ADR-0064, by invincible-agent PR #281.** ADR-0064 is still Proposed. The amendment is docs
only, on branch `lane/01-adr-0064-dimensions` (commit `4685ca45`). iagent's reply of 2026-11-06 concedes both points
that were open here.
- **No automatic downgrade.** ADR-0064's "One downgrade is automatic" now reads "No downgrade is automatic".
  - A standing downgrade is a declared rule with a named owner. It is applied as that owner's decision, and each
    application is recorded.
  - The de-identifying aggregation is the first such rule. A rule with no named owner applies to nothing.
  - This is §3's position.
- **The four types.** Classification in ADR-0064 is now a label of declared dimensions of this record's four types.
  - Access is the conjunction.
  - A dimension is a registry row with a name, a type, a vocabulary and an owner.
  - A value outside its dimension's vocabulary is refused at validation.
  - iagent's levels are its first hierarchical dimension, and its program cell is its first restrictive one. No
    exclusionary dimension is declared there yet.
- **What ADR-0064 takes from this record.**
  - It adopts §1a's wording and cites it. Its text still says §1a awaits signature. §1a was signed on 2026-11-06, and
    updating that text is iagent's.
  - It cites §3b's composition per type, and adopts §3a, because its cell filter at ticket time already gives a reader
    exactly their classes' rows.
- **iagent's asset of record is the physical platform's URN.** That is the URN a data product's label is registered
  under, and the catalog sync registers under it (ADR-0064, open question 1, closed 2026-11-06). It is not this
  record's `asset_id`.
  - An iagent product and an OpenDDIL asset are two different things, in two id spaces.
  - Nothing maps one to the other by name.
  - A record that crosses carries its label body (§2), so its label does not depend on joining the ids.
- **The two items once open here are ruled (2026-11-07):** the name is `data_rights_holder`, and an undeclared
  dimension inbound is refused, loud (§1, §5).
- **ADR-0064's line saying §1a still awaits signature** is iagent's to update. Their architect has put it on Lane 1's
  list. This side sends no packet.

### 7. The accreditation boundary

**Carrying a marking correctly is not authorisation to hold the data.** This framework stamps declared labels, carries them, and enforces them. Whether a tier, a store or a person may hold data of a given marking at all is an accreditation decision. That decision is made outside the system and is not recorded by it. Declaring a policy does not accredit anything to hold data under it. The framework refuses what is undeclared. It never treats declared as permitted.

## Check

Each of these is a test to write when the record is accepted. None exists.
1. **Truth tables.** Each type admits and refuses per the table in §1, including the empty-set row.
2. **Fail closed.** A record missing a declared dimension, and a record carrying an undeclared one, are each served to nobody. An inbound undeclared dimension is refused as `dimension_undeclared` and counted. A required dimension empty at a boundary is withheld there as `dimension_missing`.
3. **Key determinism.** The same label stamped by two tiers gives the same key. Labels that differ in any value, or in declared-empty versus absent `releasable_to` on a record with an originator, give different keys. A record with no originator, under NULL/NULL or NULL/`{}`, gives no key, and is served to nobody.
4. **High-water.** Each type composes per §3b. One unlabelled input leaves the result unlabelled.
5. **The split.** The three-class case in §3a gives three rows, each readable only by its class. For each viewer, the sum of the rows they are admitted to equals the rollup computed from only the contributors they may see. With one unlabelled contributor added, the rows are unchanged and the withheld-contributor tally reads 1.
6. **Downgrade refusal.** A downgrade without an owner or a reason is refused.
7. **The red case.** The same-nation refusal in §5.
8. **Acceptance.** The run in §4 matches to the row, except the listed `no_originator` rows.
9. **Vocabulary.** A value outside a dimension's vocabulary is refused at the stamp, and its record is withheld, not dropped.
10. **Reorder.** A record whose key the tier has never seen arrives first. It is served as soon as its key is decided, without waiting on any other record.
11. **Key and body.** A key that does not match its body is refused.
12. **Shape sharing.** Two viewers with the same admitted set share one shape. An entitlement change into an existing set mints no shape.
13. **No default.** With no per-asset declaration and no site declaration, the stamp writes nothing.
14. **Two tiers.** Two site declarations giving different values for one asset raise the exception at the parent. The parent serves the intersection.

## What this does not establish

- Nothing is measured. The row count of a split rollup grows with its classes and is measured on no fleet beyond the three-class case. The cost of recomputing admitted keys, and of a viewer's read filter changing when a new key appears, is unknown.
- It does not settle aggregation sensitivity (ADR-0029:539-570). It only makes raising a label a decision with an owner.
- It does not define a cryptographic binding.
- The site declaration is named, not designed. It has no schema, and its intake is not specified beyond "through the declaration intake". Its design is the first increment after acceptance: its schema, its intake path through ADR-0050's door, and the load-before-amend migration (§4 step 0) on the lab.
- The vocabulary reading covers the lab deployments only (§4 step 0). Any other deployment is unread.
- The STANAG concept names were checked against vendor documentation, not the standards' text.
- It does not accredit anything (§7).

## Consequences

### Positive
- A new dimension is a declaration and a policy rule, not a column and a predicate change.
- One read predicate, whatever the number of dimensions.
- No rollup over mixed audiences becomes unreadable. Each viewer gets the rollup of what they may see.
- The empty-versus-absent distinction for `releasable_to` survives the wire.

### Negative
- A record with a new label is invisible until its key is decided. The delay is unmeasured.
- A new key replaces the shapes of every admitted set it joins, and the old shapes hold their bytes until they are evicted. The cost is unmeasured.
- Under §1a, a deployment that relies on defaults today must write and load site declarations before the change. Until it does, it cannot take the amendment.
- During migration, every label is held twice: as the label and as the two projected columns.

### Neutral
- ADR-0029's nation predicate, gate and addendum keep their meaning as the first dimension.

## Related
- [ADR-0029](ADR-0029-coalition-releasability-abac-enforcement.md): releasability, deny-unlabeled, the reserved `policy_label`, effective audience.
- [AUDIT-2026-08-07](AUDIT-2026-08-07-aggregation-composability.md): label composition as a composability question.
- [ADR-0050](ADR-0050-asset-arrivals-declare-and-expect.md): the declaration record and §2.6's lookup order. The amendment of 2026-11-06 is ruled the same date (§1a).
- [ADR-0042](ADR-0042-intent-custody-retention-and-multi-tier-reconciliation.md): cross-child conflicts as named exceptions at the authority (ADR-0042:220).
- iagent ADR-0064, *Classification propagates through derivation* (proposed 2026-11-05, amended 2026-11-06 by invincible-agent PR #281): aligned with this record, with four types and no automatic downgrade (§6). Two items are open, both in §5.
