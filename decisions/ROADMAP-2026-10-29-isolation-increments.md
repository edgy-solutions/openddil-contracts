# ROADMAP 2026-10-29 — the isolation increments, and where three first slices fold in

**One page. Not a decision.** Each increment is decided in its own ADR. This note orders the increments and says where
each first slice from `openddil:ADR-0051`, `openddil:ADR-0052` and `openddil:ADR-0053` can ride along without delaying
the increment.

## Findings first

1. **The four increments were not defined anywhere as a set.** Each appears separately:
   - identity per tier: `ADR-0045` (identity rung 2);
   - chain per tier: `ADR-0046` "Noted for later: a per-tier assembler" and decision 2 (one consumer instance in this
     pass; per-tier is the design, `ADR-0031`);
   - workflow per tier: `ADR-0034` (per-tier Restate is the durable-workflow substrate);
   - one session: `ADR-0045` "Still open: federation across tiers".

   This note is the first place they are listed together.
2. **Numbering, corrected 2026-10-29.** This note first read "increment 2" as identity, following `ADR-0045`'s rung
   numbering (rung 1, the per-tier PDP, shipped with `ADR-0029` on 2026-09-05). That reading was wrong. The
   architect's roadmap counts increments from identity: **1 identity per tier, 2 the maintenance chain per tier,
   3 workflow per tier, 4 one session.** The per-tier PDP is done and sits outside the count. Rows A and B below
   moved one, from identity to the chain.
3. **"The census work" has no row.** The writer/consumer census exists only as reset phase 3b
   (`openddil:openddil-helm/scripts/reset-scenario.sh:2400-2456`). No ledger entry schedules running it outside a reset.
   This note places it as a side track on increment 2 (below), because a per-tier chain adds writers that the census
   must know.

## Order

| # | increment | what isolates | home | depends on |
|---|---|---|---|---|
| done (not counted) | **PDP per tier** | a severed tier still decides and enforces | `ADR-0029` §Per-tier PDP | — |
| 1 | **Identity per tier** | a severed tier can sign its own people in | `ADR-0045` (ACCEPTED v2: own realm per tier, trust between tiers) | the PDP per tier |
| 2 | **Maintenance chain per tier** | a severed tier assembles, gates and forwards its own records (assembler, gate, forwarder, intake per tier) | `ADR-0046` decision 2, Noted for later; `ADR-0031` | 1: the tier's gate and intake resolve approvers and `on_behalf_of` locally |
| 3 | **Workflow per tier** | a severed tier keeps durable timers and state | `ADR-0034`; per-tier Restate | 2: the chain's durable steps move onto it |
| 4 | **One session** | a person who moves between tiers is honoured without signing in again, and no token crosses tiers | `ADR-0045` Still open | 1. `ADR-0045` v2 §6 delivers it partly with 1: down the tree, link up. Up the tree and severed stay open. |

## Where the first slices fold in

| row | slice | folds into | why it costs the increment nothing |
|---|---|---|---|
| A | **False-readiness view** (`ADR-0053`, about 3 d) | increment 2 | It is a PEP-mediated read of the declared and derived records the tier's chain owns. Increment 2's severed proof (the tier assembles, gates and forwards its own records) is the natural moment to show the three sources draw at a severed tier, for a person signed in locally (increment 1). No new store. |
| B | **Interlock refusals** (`ADR-0052`, about 4.5 d) | increment 2 | It is two reasons in the intake, plus two columns. Increment 2 puts the intake at each tier, so building the refusal there avoids building it at the root and moving it, as with C. The refusal names the approver's tier identity from increment 1. It is demonstrable only once iagent sends a release before work (`ADR-0052` §5). |
| C | **FRACAS record** (`ADR-0051`, about 4 d) | increment 2 | The closed episode and its frozen context are written where the episode is owned. Once the chain is per tier, that is the owning tier's assembler and store, not the root's. Building it before increment 2 would put it at the root and move it again. |
| D | **Cyber alerts** (`ADR-0053` §1, the other detectors) | the census side track, alongside increment 2 | `undeclared_writer` is the census on a schedule. `undeclared_source` and `source_rate` need the source label at ingest, which the per-tier chain's ingest work touches anyway. |

None of A–D is on an increment's critical path. Each can be dropped from its increment without moving the increment.

## Not decided here

- Decided 2026-10-29: increment 1 is an own realm per tier plus trust between tiers, with credentials kept at the home tier, and the home tier follows the system of record's assignment (`ADR-0045` v2, accepted).
- Any date. The three first slices (A to C) are marked not scheduled in `FOLLOW-UPS.md`; D has no slice yet.
