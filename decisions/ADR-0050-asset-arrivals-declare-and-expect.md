# ADR-0050 — An asset enters the fleet only by a person's declaration: arrivals are declared or expected, never created

## Status

**PROPOSED — 2026-10-15.** Extends ADR-0029 §3 (labels propagate, never default) with a second label source: a
declaration record in the owning tier's store. Uses ADR-0047 (the observed id is opaque; serial correlation is the
mapper's concern) and ADR-0044 (lifecycle columns unchanged). Adds a fielding record to Contract B
(DESIGN-2026-09-06 §2), read side.

**Amended 2026-11-04:** a store outage serves the last known answer per asset. See
[the amendment](#amendment-2026-11-04-a-store-outage-serves-the-last-known-answer).

**Amendment ruled 2026-11-06:** a default is not a declaration, so step 3 of item 2.6 is replaced by a cited
site declaration, following ADR-0055 §1a, signed the same date. It takes effect on each deployment only in
load-before-amend order. See [the amendment](#amendment-2026-11-06-ruled-a-default-is-not-a-declaration).

## Context

- **Labels come from one file today.** Ingress stamps `originator_nation` and `releasable_to` from the deployment's
  `releasability.yaml`. No runtime path writes a label.
- **An entity missing from the file is withheld.** Its rows exist in the store with null labels. The PEP's predicate
  hides them, and the egress gate refuses them as unlabelled. The only visible trace is a count.
- **So a new arrival has two exits, both wrong.**
  - An operator edits the chart file and rolls the pods: a deploy, not a decision, with no record of who.
  - Or the entity stays invisible forever.
- **There is no "create asset" verb, and there must not be one.** A free-text create would mint fleet members that
  nothing observed.

## Decision

### 1. Three states before the fleet, and one write that ends them

An entity can be in exactly one of these states before it is a fleet asset. Each state is shown as itself.

| state | what is true | shown as |
|---|---|---|
| **observed-undeclared** | the tier hears an entity; no declaration names its id | a row in the edge's Arrivals panel; a count at every tier above |
| **expected-unobserved** | a fielding record names a serial for this tier; no declaration correlates that serial | an expected row in Arrivals, flagged **overdue** past `due_by` and never hidden |
| **expected-observed-unconfirmed** | an undeclared entity's resolved variant matches an open expected serial at the same tier | the undeclared row offers **Confirm as \<serial\>**. It is a candidate, never a match |

- **The one write that ends all three is the declaration record (§2).** It has two sources:
  - `declare`: a person signs for an observed entity;
  - `expect-confirm`: a person confirms an observed entity as an expected serial.
- **Nothing is auto-matched.** A matching variant only offers the confirm. An undeclared entity stays undeclared
  until a person declares it.
- **An expected serial that is never observed stays expected.** It is flagged overdue, and nothing expires it.

### 2. The declaration record (custody-grade, at the owning tier)

| field | value |
|---|---|
| `asset_id` | the id as observed (opaque, ADR-0047) |
| `serial` | the serial, or `none` |
| `unit` | an id from the deployment's declared unit list (`arrivals.units`) |
| `originator_nation` | a nation from the deployment's `releasability.yaml` |
| `releasable_to` | a list of those nations, excluding the originator |
| `baseline_id` | one of the resolved variant's loaded baselines, or `none` |
| `declared_by` | the subject from the session, never from the body |
| `declared_at` | set by the PEP |
| `source` | `declare` or `expect-confirm` |
| `edge_id`, `owning_tier` | where it was declared |

**The owning tier** is the edge's tier node when the edge has one. Otherwise it is the root, which already holds that
edge's records.

**The write path.** Every step is local to the owning tier, and none calls the hub, so a declaration works while the
edge is cut.

1. **The PEP that serves the edge's screen checks the request:**
   - session subject present;
   - role in `arrivals.declareRoles`;
   - the chosen nation is in the subject's `allowed_nations`, by the read path's own predicate (one PDP question,
     ADR-0029);
   - unit and nations are from the declared lists;
   - the baseline is one of the variant's baselines;
   - the id is currently observed-undeclared.
2. **It logs one local decision line** (`resource: arrival:declare`). The line carries the declarer, the id, the
   nation, the source and the serial, for allows and refusals alike.
3. **It posts the record to the tier's declaration intake.** That is a Connect `http_server`, the cm-intake pattern.
   The intake writes topic `asset-declarations`, compacted and keyed by `asset_id`.
4. **When `baseline_id` is not `none`,** the PEP posts a `BaselineAssigned` CmEvent to cm-intake with
   `recordedBy` = the declarer. This is the baseline assignment.
   - cm-service also reads the declaration record whenever an asset is first seen with empty state: a new asset,
     or every asset after the state wipe an upgrade or reset runs. A declared baseline that is loaded is used over
     the variant default. One that is not loaded warns and falls back to the variant default. So the assignment
     survives a state wipe without the event being replayed.
5. **The projector writes the store.**
   - `asset_declaration` always gets a row.
   - `asset_correlation` (`serial` ↔ `asset_id`) gets a row when a serial is given.
   - The topic bridges up with the other edge topics. Region and hub project the same rows when it arrives, so a cut
     edge's declaration reaches HQ on heal.
6. **The releasability row for the id is the declaration row itself.**
   - Ingress looks the id up in this order:
     1. the owning store's `asset_declaration`, through a short-TTL cached query;
     2. else the file's `assets` row;
     3. else the file's `default_originator_nation` (a deployment default, e.g. per edge);
        *(ruled 2026-11-06: replaced by a cited site declaration, load before amend. See the amendment.)*
     4. else unlabelled.
   - The file's rows win over a declaration for the same id, so a declaration for an id the file already labels
     is refused (already in fleet). Only `assets` rows count; the default never does.
   - An asset labelled only by a default is still undeclared and may be declared.
   - A failed lookup stamps nothing. A store outage serves the store's last answer per asset, withholds a record
     with no answer and no file row, and never mislabels. See the amendment of 2026-11-04.

**From that record forward the asset is in the fleet.**
- The next sample carries labels.
- Fusion, CM, the registry and the egress gate already relabel on a positive statement and never clear one
  (ADR-0029 §3).
- Rollups, lifecycle and egress take the asset from that sample on, with no step of their own.

**Limits, stated:**
- **`baseline_id: none` writes no CM event.** CM keeps its first-seen state: REGISTERED when the variant has no
  baseline loaded, otherwise the variant default.
- **Samples before the cache refresh** (≤ the TTL) still arrive unlabelled.

**Reset.** By default, the full reset keeps the declaration and correlation tables and the `asset-declarations`
topic, and confirms that they are unchanged. Declarations are custody records, not exercise state. With
`exerciseControl.resetJob.clearExerciseDeclarations: true` (a lab exercising the arrival beat), the reset clears all
three tables and trims the topic, and the id returns to observed-undeclared on its next sample. Fielding records are
exercise state and are always cleared. The decision log is not cleared: decision lines are
permanent (ADR-0029).

**Roles.**
- The deployment has no `maintainer` role.
- "Maintainer and above" is declared as `arrivals.declareRoles`, default `[edge-operator, regional-operator,
  supervisor]`.
- `observer` and `auditor` are refused.
- This is the PEP's second role gate after the reset, for the same reason: a declaration creates custody state.

### 3. The edge screen: an Arrivals panel

- **Undeclared rows.** The panel lists the edge's observed-undeclared entities: id, first seen (registry
  `assigned_at`), last seen, resolved variant or `UNKNOWN`, and position.
  - The PEP serves these rows from a dedicated route, only to declare roles.
  - The route returns these columns only. The withheld set stays withheld from every other read.
- **Expected rows.** The panel also lists expected-unobserved rows: serial, variant, unit, due-by and overdue. They are
  filtered by the viewer's nations, because a fielding record carries its owning nation.
- **One action per row:**
  - **Declare**, or **Confirm as \<serial\>** where §1's candidate rule holds.
  - Either action opens one form pre-filled from the observation (and from the fielding record for a confirm).
  - Submit writes §2's record. The row then leaves the panel and the asset appears in the fleet.

### 4. Expected: a fielding record in Contract B

- **The record.** Contract B's read side gains a fielding record: `serial`, `platform_variant`, `unit`,
  `owning_nation`, `releasable_to`, `fielded_to` (tier id) and `due_by`.
- **Where it travels.**
  - It is produced by the logistics system of record; logistics-sim is the stand-in.
  - It goes onto the fielded-to edge's broker as topic `asset-fielding`, compacted and keyed by serial.
  - It is projected to `asset_fielding` and bridges up like any edge topic.
- **When a serial is expected.** A serial is expected while no `asset_correlation` row names it.
- **On the wire** it is Contract B's fielding plane (DESIGN-2026-09-06, amendment 2026-10-15). `fielded_to` is the
  plane's `site`, `due_by` is `due_by_ns`, and the owning nation and `releasable_to` are the labels under
  `provenance`.

### 5. Every tier sees the unknowns

The HQ fleet summary shows **undeclared N · expected M** per edge.
- **N** is a count of null-label rows by edge. It names no ids, the same shape as the egress pane's withheld count.
- **M** is the open fielding rows for that edge.

## Alignment declared (ADR-0038 C1 intake)

**By concept name only.** No schema text, element names or code lists are copied here or into the record.

| OpenDDIL | aligned to | concepts named |
|---|---|---|
| declaration record | hand receipt / sign-for (property accountability practice) | an item on hand at a location, signed for by a named person, at a time |
| fielding record | property book fielding | an item owned by a unit, en route or due to a location |
| `asset_id`, `unit`, `asset_correlation` | JC3IEDM | object item (materiel), the holding unit (organisation), the association between them; reporting data (who reported, when) |
| fielding record, `serial`, baseline | ASD S5000F | product instance (serialized item), operator organisation, configuration of the fielded instance |

The field names are OpenDDIL-local, with a declared alignment intent. Binding them to named elements is owed before any
field is frozen.

## Amendment 2026-11-04: a store outage serves the last known answer

Item 2.6 said a store outage withholds. Withholding every record would take every asset on that tier off the wire for
the whole outage, and a last answer is still a declared label, which is what the item protects. So, on a failed lookup
at ingress:

1. **An asset with an answer keeps it.** The process serves the store's last answer for that asset.
2. **A record with no answer is withheld,** unless the file's `assets` row labels it. That row is the one source a
   declaration may not contradict, so it stands.
3. **No stamp and no default.** Neither labels a record whose lookup failed with no answer.

**The class this closes:** a store outage puts a declared asset's Entity State record under its stamp or a default. It
was seen twice before `openddil-demo` 2309dc5, which makes it impossible.

**Outside that class, each a row in `FOLLOW-UPS.md`:**

- A stored "no row" is an answer. An asset declared after the process last read it can take that answer into an outage.
- A file row added after a declaration, with a restart in an outage, wins for that time.
- A Fire record has no declaration lookup at all, store up or down, so this amendment does not reach it.

**Not proven:** a real declaration under a real outage. The outage branch was read with a row inserted directly and on
the real binary. A real declaration was read with the store up.

## Amendment 2026-11-06 (ruled): a default is not a declaration

**Ruled by Chris, 2026-11-06, with ADR-0055 §1a signed the same date.** It takes effect on each deployment only in the order below.

**Why.** Item 2.6 step 3 lets a deployment default label a record. The 2026-11-04 amendment refuses a default only
after a failed lookup. Both sit against this record's own summary of ADR-0029 §3, "labels propagate, never default"
(Status, and Related). A default is a label nobody stated about the record. This amendment makes the summary true.

**Step 3 becomes a site declaration.** The lookup order is:
1. the owning store's `asset_declaration`;
2. else the file's `assets` row;
3. else a **site declaration** that covers the record: a stored statement of scope, dimension values, owner and
   date, through this record's intake. The stamp cites its id.
4. else unlabelled, so withheld.

- Two site declarations at one tier that cover a record and disagree give nothing, and a named exception to both
  owners. The case across two tiers is in ADR-0055 §1a.
- A per-asset declaration outranks a site declaration. So an asset labelled only by a site declaration is still
  undeclared and may be declared, as an asset labelled only by a default may be today.
- The 2026-11-04 amendment stands. A last known answer from a site declaration is a declared answer. "No stamp and
  no default" now reads "no stamp": the default is gone.
- The file's `assets` row keeps its place, and carries an owner and a date, as a site declaration does. Without
  them it is a default (ADR-0055 §1a).

**Order: load before amend.** On each deployment:
1. Write a site declaration for every default in use, stating the same answer.
2. Load them, and confirm every record a default labelled now cites one with the same value. The labelled and
   unlabelled counts must not change.
3. Only then remove step 3 and the defaults.

In the other order, every record labelled only by a default is withheld at the change.

**What it reaches.** Each row is a default today. Each becomes a cited declaration or stops stamping. The paths are
in ADR-0055 Findings 3.
- The logistics sim's edge default, its document default, and its `site_nation` fallback.
- The publisher's spares, under a site declaration scoped to the site.
- The DIS mapping's stamp-then-default.
- The ingest's nation stamp:
  - its per-entity overrides become per-asset declarations;
  - its geofence and marking rules become site declarations scoped by rule;
  - its country-code rules become a declared mapping between schemes (ADR-0055 §6).
- The effector's path, already open in `FOLLOW-UPS.md` because it has no declaration lookup.

**Not established.** The site declaration has no schema yet. No deployment has loaded one. Nothing here was run.

## Consequences

### Positive
- No fleet member exists without a named declarer. The decision log says who signed for what, and when.
- The unknowns are visible at every tier as counts. They are not hidden where they sit.

### Negative
- Ingress gains a store lookup. While the store is down, new arrivals stay withheld. That is the safe direction, but
  it is a dependency.
- The PEP gains a second role gate and a route that reads null-label rows, with fixed columns, for declare roles.

### Neutral
- The file stays the deployment's label source for the planned fleet. Declarations add to it at runtime and never
  edit it.

## Related
- ADR-0029: one PDP, labels never default. A declaration is a positive statement.
- ADR-0044: lifecycle columns are unchanged. Declaration is membership, not lifecycle.
- ADR-0046: intake pattern and the local decision line at the owning tier.
- ADR-0047: the observed id is opaque; serial correlation is a separate record.
- DESIGN-2026-09-06 §2: Contract B read side.

- 2026-10-15: §2 item 6 amended to declaration, then row, then default, then unlabelled. A default must never beat a person's declaration.
- 2026-10-15: §2 item 4: cm-service reads the declaration on first-seen registration, so a declared baseline survives a state wipe. Reset: declarations are kept unless `clearExerciseDeclarations` is set.
- 2026-11-06 (ruled): §2 item 6 step 3, the deployment default, replaced by a cited site declaration; load before amend. See the amendment.
