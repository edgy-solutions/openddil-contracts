# Plan — Arc 2 Slice 1 opening package

**Date:** 2026-08-12 · **Status: PLAN ONLY. Nothing built, nothing
scheduled, go-signal reserved.** · **Method:** state verified by reading and
executing, not inferred from the ADR's own status text.

Arc 2 Slice 1 is ADR-0029's read-path releasability: *two users of different
nations, on one cluster, see different fleets, and the difference is fully
explained by a decision log.*

This package establishes **where the arc actually starts from**. That turned
out not to match what a reader of ADR-0029 would conclude, which is the
reason the package exists.

---

## 1. Verified state, phase by phase

Each row was checked directly. Where the check was a command, it is quoted.

| Phase | ADR-0029 says | **Verified 2026-08-12** |
|---|---|---|
| **P0** — proto captures | "a Phase 0 deliverable, not a completed capture" | **NOT DONE.** `originator_nation` / `releasable_to` / `policy_label` occur in **zero** `.proto` files, workspace-wide |
| **P1** — labels queryable | done in Arc 1 | **HALF DONE, and the half that shipped cannot function.** Columns exist on 5 tables (`20260807000000_arc1_releasability_labels.sql`). **Nothing writes them** |
| **P2** — completeness gate | must pass before enforcement | **CANNOT PASS TODAY**, and not for want of effort — see §2 |
| **P3** — Topaz + `users.yaml` | seat proven on a real cluster 2026-08-09 | **Split.** Topaz *is* in `tier-node.yaml` and the deployment gate genuinely ran. **No `users.yaml` exists in any repository** |
| **P4** — gateway PEP | ~1–2 days | **Not started.** No component matches |
| **P5** — decision log | ~½ day | **Not started.** Consistent with the ADR's own note that this is new construction with no prior art here |

---

## 2. The finding that reorders the arc

**P1 shipped a schema that no code path can fill, and P0 is the reason.**

The columns are real, correctly typed, indexed, and thoughtfully justified —
the migration's *why real columns and not JSONB* rationale is sound and its
deny-unlabeled warning is exactly right. But:

- the labels are not in the proto, so they are not on the wire;
- the projector composes its SQL from per-handler column dicts
  (`persistence/postgres.py`), and **no handler mentions either label**, so
  the columns are never in a dict and never written;
- therefore every row has `originator_nation IS NULL`.

The §7 gate is `SELECT count(*) … WHERE originator_nation IS NULL` returning
zero. **Today it returns the row count.** Not because labelling is
incomplete — because labelling is *unimplementable* until P0 lands. There is
no value any producer could stamp that would reach that column.

### Confirmed by query, 2026-08-12 — `edgy-lab`

This section was written as a source reading and flagged as unverified. It
has since been run against a live store (lab cluster, `openddil-postgres-hq-0`;
the work cluster was **not** touched):

```
                          rows   labelled_nation   labelled_releasable_to
asset_capability_state       0                 0                        0
asset_cm_state              14                 0                        0
asset_element_telemetry      0                 0                        0
asset_logistics_status      14                 0                        0
telemetry_latest_state      14                 0                        0
```

**42 populated rows across three tables, zero labelled on either column.**
The query executing at all proves the columns exist; the zeros prove nothing
writes them. §2 is **confirmed, not falsified**.

*Two of the five tables are empty and therefore prove nothing* — a zero over
zero rows is vacuous, and counting it as evidence would be the same error
this document is about. The finding rests on the three populated tables.

**A second finding fell out of the same query.** `inventory_items` — named in
the migration's scope list and carrying the columns in `schema.hcl` — **does
not have them in the lab's deployed schema**:

```
ERROR:  column "originator_nation" does not exist
```

The deployed bundle's Atlas migrations lag the contracts' `schema.hcl`. That
is a known recurring condition rather than a new defect, but it matters here
specifically: **the labelled-table set differs between the schema of record
and the schema actually deployed**, so any completeness gate must enumerate
tables from `information_schema` rather than from the migration's scope
comment. A gate that hardcodes the migration's list would query a table that
does not exist and fail in a way indistinguishable from a connection error.

This is not a criticism of the sequencing decision. Arc 1 deliberately landed
the columns early so every tier-local store is born with the final schema
(ADR-0032 §b), and that was correct. **The defect is that "P1 done" and "P0
pending" read as independent facts when P1's output is inert without P0.**

*The generalizable shape:* **a schema-only phase reports as complete on
evidence that cannot distinguish it from a phase that also has a producer.**
`\d telemetry_latest_state` looks identical either way. Same family as the
buffer probe — the healthy reading and the broken reading are byte-identical
from the observer's position, one layer up in the plan rather than the code.

### Consequence for sequencing

P0 is already documented as blocking two *design* questions (label
composition for aggregates; the audit's label inventory). It also blocks the
**entire enforcement chain**, because P2 gates P3–P5 and P2 cannot pass.

**P0 is not merely first. It is the only phase with no prerequisite, and
every other phase is downstream of it.** The phase numbering already says
this; what it does not convey is that P1 being marked done changes nothing
about that.

---

## 3. The specimen already emits into the hole — and it hard-fails

`sample-sensor-mapping.yaml` — the file ADR-0030 designates as the reference
adapter authors copy — writes both labels:

```
root.provenance.originator_nation = this.sensor_id.split("_").index(0) | "UNKNOWN"
root.provenance.releasable_to     = this.releasable_to | []
```

`Provenance` declares `producer_id`, `source_protocol`, `source_sequence`,
`sample_time`, `ingest_time`, `classification` and the origin-node fields.
**It declares neither label.**

**Executed, not reasoned about.** Feeding that shape through the same encode
step the real ingress uses (`protobuf: operator: from_json, message:
openddil.telemetry.v1.EntityTelemetryEvent`):

```
{"RESULT":"FAILED","error":"unmarshalling JSON message
 'openddil.telemetry.v1.EntityTelemetryEvent': proto: (line 1:54):
 unknown field \"originator_nation\""}
```

The encoder **rejects the message**; it does not drop the field. In the real
pipeline that step sits inside a `try:` whose `catch:` stamps
`dlq_stage = "…_or_protobuf_encode"` and routes to `ingress-dlq`.

**So an adapter built by copying the specimen sends 100% of its traffic to
the DLQ.** Not a subtle degradation — total ingress failure for that source,
attributed to a stage name that names two possible causes.

**Live blast radius is zero, today.** The specimen is not wired into any
connect pipeline; it is a teaching artifact, and no shipping mapping sets
either field. **The hazard is the propagation, not the file** — which is the
same reason F3 was worth fixing in the same file yesterday.

*Not a defect in the specimen's intent.* It was written against the
post-P0 contract, which is defensible for a document teaching the target
shape. The defect is that **nothing says so**, and the artifact is
indistinguishable from one that works.

**Third instance of the same construction in one week**, all in this file:
the specimen teaches by being copied, so anything wrong in it is wrong
everywhere downstream, silently, later.

---

## 4. Why no test caught it, including the one I just added

The golden suite runs **JSON → mapping → JSON**. It never encodes to proto.
So all seven goldens pin `originator_nation` and `releasable_to` in their
expected output and **pass**, while the mapping they pin cannot be encoded.

That includes `unrecognised-mode`, added yesterday. The suite is green and
the specimen is unencodable, simultaneously, with no contradiction — because
the suite tests a layer above the one that fails.

**A golden file records what a mapping produces. It says nothing about
whether the consumer can accept it.** The harness's own header documents its
scope honestly and this is not a violation of it; the gap is that no *other*
check covers the seam.

**Candidate fix (not scheduled, ~½ day):** add a proto-conformance stage to
`run.sh` — encode each case's actual output through `from_json` against the
canonical message and fail on error. It needs the contracts proto tree
available to the overlay's tests, which is a real dependency question and
the reason this is a candidate rather than a task. It would have caught this
on the day the specimen was written.

*This is worth stating plainly: the check I would have to add to catch this
is one I could have added yesterday while extending the same suite, and did
not, because I was testing the mapping against its own intent rather than
against its consumer.* Same error as the audit that read fallbacks by shape
rather than by effect.

---

## 5. Proposed opening sequence — for a go-signal, not for execution

**Step 1 — P0 proto captures.** Add `originator_nation` (string),
`releasable_to` (repeated string) and reserved `policy_label` to
`Provenance`. Purely additive.
*Prerequisite for everything else in the arc. Blocks nothing itself.*

> **Acceptance test, already identified:** the §4 conformance stage. When
> the captures land, the specimen encodes and the stage passes; until they
> land, it fails on the exact error quoted in §3. That makes P0's
> completion **observable rather than asserted** — which is the property
> §2 shows P1 lacked, and the reason P1 could report done while inert.
> Build the stage as part of P0, not after it.
>
> **The specimen now has TWO independent encode defects, found on separate
> days by separate work** — which strengthens the case for running the
> conformance stage against it as P0's first acceptance:
>
> 1. `provenance.originator_nation` / `releasable_to` — fields the proto
>    does not declare; the encoder rejects the message outright.
> 2. `kinematics.position.wgs84.lat` / `lon` set as **bare numbers** where
>    `Wgs84Position` declares `Quantity` messages (ADR-0013's unit
>    discipline). Found 2026-08-19 while building the ASTERIX CAT062
>    mapping, which hit the identical defect and was caught by an encode
>    check the specimen has never had.
>
> Two unrelated causes, one file, both invisible to a JSON-only suite. The
> second is the more instructive: it is **not** a *pending contract* like
> the releasability fields — it is simply wrong today, against a contract
> that has not changed.

**Step 2 — decide, explicitly, what stamps them.** ADR-0029 says labels are
"stamped at ingress"; the specimen parses nation from an id convention and
the config supplies a default that is *honest about being a default*. That is
the right shape for the sample overlay and is **not** a general mechanism.
The question this arc must answer before P1 can be completed: **for each live
producer, what declares nationality?** Note the shape — it is the
declared-vs-inferred question again, third occurrence (GD-10 payload shape,
GD-11 class property, GD-12 absence semantics). *An id-parsing convention is
inference from a naming habit.* Worth deciding as such rather than inheriting
the specimen's approach by default.

**Step 3 — complete P1.** Projector handlers carry the labels from the
(now-existing) proto fields into the (already-existing) columns. Small, and
only small because P1's schema half is genuinely done.

**Step 4 — P2 gate.** The §7 count. Cannot be attempted before step 3.

**Step 5 — `users.yaml`.** Does not exist; P3's other half. Independent of
steps 1–4 and can proceed in parallel — the only genuinely parallel item in
the arc.

**Steps 6–7 — P4 gateway PEP, P5 decision log.** Per ADR-0029, including its
open question (b): whether the subscription filter grammar can express array
containment. **Do not redo the Postgres half** — Arc 1 verified `text[]`
containment against live Postgres with a GIN index.

### The one thing to settle before step 1

**Whether the specimen is corrected now or at step 1.** Options: (a) fix
with P0 so the specimen becomes true the moment the proto lands; (b) annotate
now that it targets the post-P0 contract and does not currently encode. **(b)
is near-free and stops the bleeding without pre-empting the arc** — the file
is copied by people who will never read this plan. Recommended, but it is a
change to a shipped artifact and therefore sits behind the go-signal like
everything else here.

---

## 6. What this package did not establish

Per ADR-0037 clause 6.

- ~~**No live cluster was queried.**~~ **RESOLVED 2026-08-12** — run against
  `edgy-lab`, result in §2. The source reading was correct. Note what the
  query could *not* settle: it confirms **this** deployment writes no labels,
  not that no writer exists anywhere. A deployment whose overlay stamps them
  by another route would show a non-zero count, which is why the private
  overlay remains open below.
- **The work cluster was not queried**, per standing scope. If its bundle
  digest differs from the lab's, its labelled-table set may differ too — the
  `inventory_items` discrepancy in §2 is direct evidence that deployed
  schemas diverge from `schema.hcl`, so *"the lab shows zero"* should not be
  restated as *"the pilot cluster shows zero"* without running it there.
- **Only the projector was read for writers.** Another component could write
  those columns; nothing suggests one does, and the grep was workspace-wide,
  but "no match" is not "no writer" if a writer composes the name.
- **The DLQ consequence is inferred one step.** The encoder failure is
  executed and quoted; that a failing message *reaches* `ingress-dlq` is read
  from the connect config's `catch:` block, not observed end-to-end.
- **Effort estimates are ADR-0029's, not re-estimated.** Notably they were
  written when P0 was assumed near, and step 2 above may not have been
  costed at all.
- **No private overlay was examined.** A live deployment's mapping may
  already stamp labels by some other route, which would change §2 materially.
  This is the second item this week whose resolution sits outside these
  repositories.
- **`policy_label` was not investigated** beyond confirming its absence.
  ADR-0029 calls it reserved and unused in Slice 1.

---

## Related

- **ADR-0029** — Arc 2's governing decision; §7's gate and the Slice 1 phases.
- **ADR-0030** — designates the specimen; why §3 propagates.
- **ADR-0032** — why the columns landed early; the decision §2 declines to
  criticise.
- **ADR-0037** — evidence as deliverable; §6 is clause 6 applied here.
- **`PRINCIPLES.md`** §*Ordering* (label first, enforce second — the gate §2
  shows is unreachable), §*A probe must fail distinguishably from its own
  zero* (§2's schema-only-phase shape), §*Measure the fix, not the fix's
  worst imaginable form* (§4's candidate fix is quoted as a candidate
  precisely because its cost is a real dependency question, not a guess).
- **GD-10 / GD-11 / GD-12** — the declared-vs-inferred family step 2 joins.
