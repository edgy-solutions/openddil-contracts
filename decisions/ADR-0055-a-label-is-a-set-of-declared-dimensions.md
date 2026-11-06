# ADR-0055 — A label is a set of declared dimensions, compiled to one key

## Status

**PROPOSED — 2026-11-06. Design only. Nothing here is built, nothing is deployed, and nothing has been measured.**
- It generalises [ADR-0029](ADR-0029-coalition-releasability-abac-enforcement.md)'s two nation fields into a label of declared dimensions. It does not supersede ADR-0029. ADR-0029's predicate, its addendum and its gate stay true for the nation dimension.
- The number is provisional until the record is accepted.

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

Three stamp a default nation the source did not give:
- logistics-sim (`src/logistics_sim/releasability.py:209-226`);
- the DIS mapping and effector configs in openddil-demo (`dynamic-mappings/sim-dis-mapping.yaml:75-80`, `:261-266`; `dis-effector.yaml:93-98`), whose shipped default is null;
- logistics-sim's site spares (`publisher.py:514-515`).

Only the three stamps put a nation on a record that its source did not carry.

The projector copies the label as it receives it. With no nation it stores `[]`, not NULL (`openddil-projector/src/handlers/base.py:289-297`), and an aggregate stores no nation and a list (`:356-357`).

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
  - No decision record decides the partition. §3 below names it.

**5. Contradictions in the record.**
- ADR-0029:302 says the fields are "not yet in" the proto. ADR-0029:631 marks that step DONE, and the proto has them.
- iagent ADR-0064 (`docs/adr/ADR-0064-classification-propagates-through-derivation.md`, Proposed) agrees on the structure:
  - a derived column takes the maximum of its sources (`:35-36`);
  - an unlabelled source is most restrictive;
  - downgrades are recorded with level, reason and steward (`:48-49`).
- But it then makes one downgrade automatic: "One downgrade is automatic", for an aggregation that drops identifying columns (`:50-51`). §3 below refuses that.
- Its levels are one ordered registry (`:92`), so it has only the hierarchical type.

**6. The value format diverges.**
- The contract-b validator requires three uppercase letters.
- The SDK accepts any non-blank string.
- Agent tests use two-letter or placeholder codes.
- The SDK validator and iagent's trigger refuse a blank originator. Nothing checks the format of `releasable_to`.

**7. What the inventory does not cover.**
- The ingest's stamped nation (`stamped_nation`, openddil-sensor-ingest) is under another name, so the grep does not count it. The DIS mapping reads it into `originator_nation` (`openddil-demo/dynamic-mappings/sim-dis-mapping.yaml:80`).
- The policy engine's rules are not in the runtime repos.
- A hit's role is a reading of its file, not a run.

## Decision

### 1. A label is a set of declared dimensions

A deployment declares each dimension it labels by. A declaration gives a name, one of four types, the vocabulary of values, and the owner who decides what the values mean. A record's label holds a value set for every dimension the deployment declares.

| Type | A record carries | A viewer is admitted when | Empty set means |
|---|---|---|---|
| **Hierarchical** | One level from an ordered list | The viewer's level is at or above it | Not allowed. A hierarchical dimension always has a level |
| **Permissive set** | Values that widen the audience, such as nations it is releasable to | The viewer holds at least one of them | Released to nobody by this dimension |
| **Restrictive set** | Values that narrow the audience, such as caveats, compartments or data-rights holders | The viewer holds every one of them | No restriction from this dimension |
| **Exclusionary** | Values that bar a holder | The viewer holds none of them | No exclusion from this dimension |

**Access is the conjunction.** A viewer sees a record only when every declared dimension admits them.

**Undeclared fails closed, both ways.**
- A record with no value for a declared dimension is served to nobody. This is ADR-0029 §7's deny-unlabeled, generalised.
- A record carrying a dimension the deployment does not declare is served to nobody, and the stamp that wrote it is a defect.

**The nation dimension keeps its author.** A permissive dimension may declare one author value. For nation, that value is `originator_nation`, and the audience is ADR-0029's effective audience, `{originator} ∪ releasable_to` (ADR-0029:1100-1106). The author value grants access only on records whose derivation preserved single authorship (ADR-0029:1086-1088).

### 2. Labels compile to a `label_key` at stamping

The stamp that writes a label today, at ingress (ADR-0029 §3), also compiles it to a `label_key`:
- The key is a digest of the label's canonical form: the policy identifier, then each declared dimension in a declared order, with its values sorted.
- The same label gives the same key at every tier, with no coordination. Two tiers that stamp independently while severed agree on the key.
- The label body is stored once per key, in a label table at the tier, and travels with the first record that carries it.

**The PDP computes admitted keys per viewer.** For each viewer, the tier's decision point evaluates each distinct label against the viewer's asserted entitlements (ADR-0029 §5). It returns the set of keys the viewer is admitted to. Distinct labels are few next to records, so the decision runs per label, not per row. The set is recomputed when a policy bundle, a viewer's entitlements, or the set of known keys changes.

**The PEP filters on the key.** The read path's filter becomes one predicate, `label_key IN (:admitted)`, in place of ADR-0029's disjunction. A key the PDP has not yet evaluated is admitted to nobody, so a record with a new label is invisible until it has been decided, never visible before.

**The key carries what the wire cannot.** ADR-0029's addendum records that proto3 cannot tell an empty `releasable_to` from an absent one (ADR-0029:1120-1136). A canonical form encodes "declared and empty" and "absent" differently, so the key keeps a distinction the two repeated fields lose.

### 3. A derived record takes the high-water label

A record computed from labelled inputs takes, dimension by dimension, the most restrictive combination of its inputs' values:

| Type | High-water of the inputs |
|---|---|
| Hierarchical | The highest level |
| Permissive set | The intersection of effective audiences. This is ADR-0029's addendum, unchanged (ADR-0029:1100-1118) |
| Restrictive set | The union |
| Exclusionary | The union |

- An input with no label makes the derived record unlabelled, so nobody sees it. These are ADR-0029's collapse cases (ADR-0029:1116-1118).
- **Partition, then label, is allowed and is high-water.**
  - A rollup may first split its inputs into classes that share one effective audience, and emit one derived row per class.
  - Within a class every input has the same audience, so the intersection is that audience, and each row is high-water.
  - This is what the regional rollup builds (Findings 4). This record names it as the rule that was built and not recorded.
  - A rollup that emits one row across classes still takes the intersection.
- The high-water mark is a floor, not the answer. An aggregate can be more sensitive than every input (ADR-0029:546-552). Raising a derived record above the high-water mark is a policy decision, like lowering one.

**Sanitised release is a policy decision with an owner.** Any label on a derived record below its high-water mark is a downgrade. A downgrade is a record of four things: the label it gives, the reason, the inputs it covers, and the owner who decided it. The owner is a person or role named in the declaration of each dimension the downgrade lowers. A downgrade with no owner or no reason is refused. The framework performs no automatic downgrade. A standing downgrade rule is allowed only as a declared rule that a named owner has signed. It is applied as that owner's decision, and every application records it.

### 4. Migration: nation is the first declared dimension

1. Declare `nation` as a permissive dimension, with `originator_nation` as its author value.
2. Stamp the label and the `label_key` where `originator_nation` and `releasable_to` are stamped today.
3. Keep `originator_nation` and `releasable_to` as **projections** of the label. They are written from the label at the same stamp, never set on their own. Every reader of the old columns keeps working unchanged.
4. Move enforcement to `label_key`, one PEP at a time.

**Acceptance is a run that matches today, to the row.** The run uses the lab fixture fleet and its viewers. Before and after the move, it records:
- for every viewer, the ids of the rows each screen serves;
- for every destination, the gate's decisions;
- for every labelled table, its row counts, labelled and unlabelled.

Any difference fails the migration. A difference is not tuned away.

### 5. First slice: one restrictive dimension

The first new dimension is **`data-rights-holder`**, a restrictive set. A record that carries data a holder licensed is visible only to viewers entitled by that holder.

**Its red case is a same-nation refusal:**
- The viewer is `ATL`. The record has `originator_nation = ATL`, so today's predicate admits the viewer on the author branch alone.
- The record also carries `data-rights-holder = {H}`, and the viewer holds no entitlement from H.
- After the slice, the viewer is refused.

Today's two fields cannot express that refusal. The test fails on the current predicate and passes on the conjunction.

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

### 7. The accreditation boundary

**Carrying a marking correctly is not authorisation to hold the data.** This framework stamps declared labels, carries them, and enforces them. Whether a tier, a store or a person may hold data of a given marking at all is an accreditation decision. That decision is made outside the system and is not recorded by it. Declaring a policy does not accredit anything to hold data under it. The framework refuses what is undeclared. It never treats declared as permitted.

## Check

Each of these is a test to write when the record is accepted. None exists.
1. **Truth tables.** Each type admits and refuses per the table in §1, including the empty-set row.
2. **Fail closed.** A record missing a declared dimension, and a record carrying an undeclared one, are each served to nobody.
3. **Key determinism.** The same label stamped by two tiers gives the same key. Labels that differ in any value, or in declared-empty versus absent, give different keys.
4. **High-water.** Each type composes per §3. One unlabelled input leaves the result unlabelled.
5. **Downgrade refusal.** A downgrade without an owner or a reason is refused.
6. **The red case.** The same-nation refusal in §5.
7. **Acceptance.** The run in §4 matches to the row.

## What this does not establish

- Nothing is measured. The cost of recomputing admitted keys, and of a viewer's read filter changing when a new key appears, is unknown.
- It does not settle aggregation sensitivity (ADR-0029:539-570). It only makes raising a label a decision with an owner.
- It does not define a cryptographic binding.
- The STANAG concept names were checked against vendor documentation, not the standards' text.
- It does not accredit anything (§7).

## Consequences

### Positive
- A new dimension is a declaration and a policy rule, not a column and a predicate change.
- One read predicate, whatever the number of dimensions.
- The empty-versus-absent distinction survives the wire.

### Negative
- A record with a new label is invisible until its key is decided. The delay is unmeasured.
- A read's filter changes whenever a viewer's admitted set changes, so a read path that holds subscriptions by filter pays for each change.
- During migration, every label is held twice: as the label and as the two projected columns.

### Neutral
- ADR-0029's nation predicate, gate and addendum keep their meaning as the first dimension.

## Related
- [ADR-0029](ADR-0029-coalition-releasability-abac-enforcement.md): releasability, deny-unlabeled, the reserved `policy_label`, effective audience.
- [AUDIT-2026-08-07](AUDIT-2026-08-07-aggregation-composability.md): label composition as a composability question.
- iagent ADR-0064, *Classification propagates through derivation* (proposed 2026-11-05): high-water by column (see Findings).
