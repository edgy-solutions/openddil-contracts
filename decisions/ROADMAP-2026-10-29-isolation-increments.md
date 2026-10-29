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
2. **"Increment 2" has two readings.** `ADR-0045` numbers identity as **rung 2**: rung 1, the per-tier PDP, shipped
   with `ADR-0029` on 2026-09-05. Counting from the list order instead would make the chain increment 2. The dispatch
   places the FRACAS record "with the per-tier chain" separately from "increment 2", so this note reads increment 2 as
   **identity per tier**. If the other reading was meant, only rows A and B below move: one increment later, with no
   change to their content.
3. **"The census work" has no row.** The writer/consumer census exists only as reset phase 3b
   (`openddil:openddil-helm/scripts/reset-scenario.sh:2400-2456`). No ledger entry schedules running it outside a reset.
   This note places it as a side track on increment 3 (below), because a per-tier chain adds writers that the census
   must know.

## Order

| # | increment | what isolates | home | depends on |
|---|---|---|---|---|
| 1 (done) | **PDP per tier** | a severed tier still decides and enforces | `ADR-0029` §Per-tier PDP | — |
| 2 | **Identity per tier** | a severed tier can log people in | `ADR-0045` (PROPOSED-v2: own realm per tier, trust between tiers) | rung 1 |
| 3 | **Chain per tier** | a severed tier assembles, gates and forwards its own records (assembler, gate, forwarder, intake per tier) | `ADR-0046` decision 2, Noted for later; `ADR-0031` | 2: the tier's gate and intake resolve approvers and `on_behalf_of` locally |
| 4 | **Workflow per tier** | a severed tier keeps durable timers and state | `ADR-0034`; per-tier Restate | 3: the chain's durable steps move onto it |
| 5 | **One session** | a person who moves between tiers is honoured without signing in again, and no token crosses tiers | `ADR-0045` Still open | 2. ADR-0045 v2 §6 delivers it partly with 2: down the tree, link up. Up the tree and severed stay open. |

Rung 1 is done. Increments 2 to 5 are the four in the dispatch.

## Where the first slices fold in

| row | slice | folds into | why it costs the increment nothing |
|---|---|---|---|
| A | **False-readiness view** (`ADR-0053`, about 3 d) | increment 2 | It is a PEP-mediated read. Increment 2's four-profile login under a cut is the natural proof: the view must draw at a severed tier for a locally signed-in user. No new store. |
| B | **Interlock refusals** (`ADR-0052`, about 4.5 d) | increment 2 | It is two reasons in the existing intake, plus two columns. The refusal names the approver's tier identity once identity is per tier. No new route. |
| C | **FRACAS record** (`ADR-0051`, about 4 d) | increment 3 | The closed episode and its frozen context are written where the episode is owned. Once the chain is per tier, that is the owning tier's assembler and store, not the root's. Building it before increment 3 would put it at the root and move it again. |
| D | **Cyber alerts** (`ADR-0053` §1, the other detectors) | the census side track, alongside increment 3 | `undeclared_writer` is the census on a schedule. `undeclared_source` and `source_rate` need the source label at ingest, which the per-tier chain's ingest work touches anyway. |

None of A–D is on an increment's critical path. Each can be dropped from its increment without moving the increment.

## Not decided here

- Since decided as PROPOSED-v2: increment 2 is an own realm per tier plus trust between tiers, with credentials kept at the home tier (`ADR-0045` v2). Rows A and B are unchanged by it.
- Any date. The three first slices (A to C) are marked not scheduled in `FOLLOW-UPS.md`; D has no slice yet.
