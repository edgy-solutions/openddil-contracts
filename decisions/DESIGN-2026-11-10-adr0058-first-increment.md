# DESIGN 2026-11-10 — ADR-0058's first increment: iagent at every tier, its tasks and our reports in each tier's feed

**Status:** an implementer spec. Design only: nothing built, nothing run, nothing measured for this increment. Draft,
not merged. ADR-0058 is PROPOSED. This spec builds the part of it that has no card declaration yet: what each tier's UI
shows of work owned by iagent, and what it shows of the reports its own people filed. Ordered 2026-11-10, with its
scope, as stated in "What the increment is".
**Builds on:** ADR-0058 §3 (cortex owns task and approval shapes; OpenDDIL owns record, finding and indicator) and
§6; ADR-0046 (decision 1: OpenDDIL holds no workflow state; decision 2 and §5.4: per-tier instances and owning-tier
intake are the design; §6: delegation); ADR-0042 §3 (custody is recursive, and a parent never merges); ADR-0040 (no
merge semantics); ADR-0031 (per-tier reasoning plane).

**Read at:** OpenDDIL working trees of 2026-11-10; iagent `b4b41ad1`; cortex-ui `c51f932`. Line numbers move with them.
These are reads, not runs. One is an inference from code and is marked as one.

## What the increment is

- **iagent runs at every tier.** Each tier's OpenDDIL is a consumer of its local iagent's BFF. It uses the person's
  token once that person has a session, and the service principal until then. OpenDDIL stores no task state.
- **"Needs you" and Tasks in each tier's feed,** per viewer. The action is a deep link to the pending task's card in
  cortex now, and the card rendered in place later.
- **"My reports" on the edge maintenance pane:** the filer's episodes, each with a state timeline (filed, sent, case
  opened, proposed, approved, released, work recorded). It is joined from the episode, the egress ledger and the intake
  records. Severed states are named: "queued for send", "sent, awaiting reply".
- **The disposition on the asset's card** at the tier that reported it.
- **The maintainer's day from four owned sources:** tasks (iagent), work orders (the maintenance management system,
  MMIS, through iagent), my reports (OpenDDIL), and due and recommended items (OpenDDIL, advisory). An accepted advisory
  item becomes a task or a work order in its owner's system.
- **Workflow scope:**
  - local workflows run severed;
  - a cross-tier workflow runs its local steps and waits at the first step another tier owns, with an honest state;
  - one owning tier per step; decisions are replicated, never merged;
  - a severed cross-tier step may be delegated only by a declared delegation with an owner and an expiry, and the
    delegation is marked on what replicates.
- **The route change.** The edge's door is its local iagent. The hub carries the cross-tier steps.
- **Questions for iagent's architect** are named at the end. This spec does not answer them.

**Not in the increment:**

- No task table, task cache or task column anywhere in OpenDDIL's store, Electric publication or topics.
- No card rendered in place. That needs cortex's task card declared under ADR-0058 §5's profile.
- No closed-episode table. ADR-0051's `failure_episodes` stays unscheduled (finding 3).
- No MMIS connector. That is iagent's (finding 12).
- No change to how the PEP filters, and no change to the intake's decision rule (ADR-0046, amended 2026-11-10).
- No chart change in this repository. The route change's chart work is owed (§7, §10).

## Findings that shape it

**OpenDDIL**

1. **The filer is stored on the episode, not on the ledger.** The PEP sets `recordedBy` to the subject
   (`openddil-demo/gateway/pep.py:2448`, posted at `:2463`). The subject is the OIDC `sub`, or the header value in header
   mode (`:3595`). cm-service stores it as `sources[].reported_by` (`openddil-cm-service/src/events/asset_cm.py:587`),
   and it reaches `asset_cm_state.manual_discrepancies[].sources[]` (`openddil-stack/schema/schema.hcl:286`).
   `egress_delivered_events` has no filer column.
2. **The ledger already carries the episode.**
   - `egress_delivered_events` (`schema.hcl:2051`) has route, event_id, outcome, http_status, case_id, topic,
     partition, kafka_offset, first_recorded_at, recorded_at, episode_id, asset_id, component and fault_code.
   - The four episode columns arrive as `stamps` (`openddil-demo/egress/forwarder.py:454-481`). Rows recorded before
     2026-10-17 have them null.
   - Outcomes are `held` (retries exhausted, `forwarder.py:43`), `delivered` and `failed`.
3. **Closed episodes have no table.** An episode is cm-service state (`persistence_model.py:83-105`, closed at
   `:126-150`). Only the open set is projected to `asset_cm_state`. ADR-0051's `failure_episodes` is proposed and not
   scheduled.
4. **The cases route exists per asset.** `GET /egress/cases` (`pep.py:3822`, `_handle_egress_cases` at `:3925`) proxies to
   `egress/pane_api.py:196-225`: delivered rows with a case id, for one asset, newest first, at most 50. It is the read
   behind `CortexApprovalLink`, which builds `${baseUrl}/case/<id>` (`frontend/src/components/CortexApprovalLink.tsx:17-26`).
5. **The intake keeps the decision, not the chain.** `intake_records` (`schema.hcl:1532`) has kind, key, owning_tier,
   body, body_sha256, decision, decided_at, originator_nation and releasable_to. The decision holds allowed, reason,
   provisional, provisional_since, approvers and on_behalf_of (`egress/intake.py:378-425`). The key comes from a pointer
   the kind declares (`intake.py:489`). No column holds the case id.
6. **The egress runs at the hub only.** The forwarder, intake and assembler render only from `templates/egress.yaml`,
   behind releasability and labelled for the hub (`:1`, `:16-19`, `:605`). Each route has its own URL and credentials
   (client credentials or a token file, `forwarder.py:154`, `:176`).
7. **The PEP has no token to pass on.** A session keeps the ID token, for sign-out only, and the refresh token, both
   server-side (`gateway/oidc.py:767`, `:806-812`). No access token is kept, and there is no token exchange (noted for
   later at `pep.py:161`).
8. **A viewer has one role in OpenDDIL.** `/auth/me` returns a single role from the policy decision (`pep.py:3786`).
   The roles are edge-operator, supervisor, regional-operator and observer, and observer is the default. OpenDDIL has
   no maintainer role.
9. **No component lists tasks, reports or a disposition.** The maintainer page has the fault report form
   (`FaultReportForm.tsx`) and the case link, and nothing else of this increment.
10. **Due and recommended items have producers, and one is missing:**
    - modification due dates (`configuration_baseline.proto:51`), with the analyzer's "apply before" and overdue text
      (`openddil-cm-service/src/discrepancy/analyzer.py:295-335`);
    - fielding due times (`logistics-sim` `config.py:346-357`);
    - the nearest spare (`egress/assembler.py:463-487`);
    - wear remaining life (`windowed_telemetry.proto:44-53`).

    No producer for an expired inspection was found.

**iagent and cortex-ui**

11. **The task queue is per person, and fanned out at registration.**
    - `GET /me/human_tasks` (`src/iagent/gateway.py:1710`) returns the caller's pending rows, filtered on
      `recipient_id` = the caller's identity. It takes no role, audience or `on_behalf_of`.
    - Rows are materialised one per actor that the audience's grants authorise, when the task is registered
      (`src/iagent/human_tasks.py:8-12`, `:168-191`). Each row carries `audience`, `subject_ref` and a nullable
      `case_id` (`:72-102`).
    - No route lists tasks by role, and no route reads one task by id.
12. **No work-order system is connected.** The work order exists only inside the action record that the release step
    emits. It is served by `GET /cases/{id}/action` (`gateway.py:16535`).
13. **A delegate reads less than a person.**
    - OpenDDIL's delegate client may assert `on_behalf_of` for a declared set of principals (`gateway.py:5582-5600`),
      trusted by configuration. "Token exchange replaces it" (`:5590`).
    - `GET /cases/{id}` refuses a delegate (`:12614-12618`).
    - `GET /cases/{id}/action` serves a delegate only the cases it seeded (`:16535`).
    - **Inference, not run:** `GET /me/human_tasks` has no body to carry `on_behalf_of`, so the route's door
      (`:1680-1704`) refuses a service caller there.
14. **The BFF accepts its own realm's tokens.** It verifies a bearer against its realm's keys (`src/iagent/auth.py:144`,
    `:198-213`). OpenDDIL's realm is brokered into it, and a cortex link may carry `?idp=` as a sign-in hint
    (cortex-ui `src/lib/deepLink.ts:61-78`).
15. **cortex-ui links to a case, never to a task.** The deep-link vocabulary is `/case/{id}` and `/ask?q=`, "the
    whole vocabulary" (`deepLink.ts:1-3`, `:32-34`).
16. **iagent has no notion of tiers.**
    - `owning_tier` is a field of the incoming event. It is used only as an audience suffix in the maintenance workflow
      definitions in iagent's deployment overlay.
    - No code reads it. The chart has no site, tier, parent or peer setting.
17. **A wait ends at its deadline without a disposition.**
    - An await races a durable sleep. On the deadline it ends `TIMED_OUT`, with no disposition
      (`agent_fleet/restate_analyst/main.py:2520-2550`).
    - The maintenance decide and review awaits have 72 h deadlines.
    - The release step is one emit, with no step of its own for the decision.
18. **Nothing replicates a decision, and a delegation has no expiry.**
    - A person's act needs a live BFF and a live permission check, and a cache miss with the permission service down is
      a denial (`auth.py:259-262`).
    - There is no offline queue and no decision replication.
    - A delegation is recorded as `acted_via` on the approval (`main.py:3099-3131`), with no owner and no expiry.

## 1. iagent at every tier; the tier's OpenDDIL as its consumer

### 1.1 One consumer per tier

- Each tier's PEP reaches exactly one BFF, its tier's own: `iagent.bffUrl`, one value per tier. The PEP never calls
  another tier's BFF.
- Cross-tier work goes through §7, never through a PEP calling across.

### 1.2 Which token

| Situation | Token the PEP presents | What it can read |
|---|---|---|
| A person has a session | the person's token for the BFF's realm (§1.3) | that person's queue and the cases that person may view |
| No session yet | the tier's service principal | only what a delegate may read: actions on cases OpenDDIL seeded (finding 13) |
| Neither available | none, and no request leaves | nothing. The UI names it: "sign in to see your tasks" |

- **Never the service principal on a person's behalf for a read**, unless iagent rules that a delegate may read a named
  person's queue (Q2). Until then, a feed before sign-in shows no tasks and says why.
- **The token is held server-side, like the refresh token** (finding 7): never a cookie, a response body or a log line.

### 1.3 How the PEP gets the person's token

- OpenDDIL keeps no access token today (finding 7), and the BFF accepts only its own realm's tokens (finding 14).
- ADR-0046 §6 names OAuth 2.0 token exchange (RFC 8693) as the design. The PEP would exchange the session's token for
  one the BFF's realm issues to that person.
- **Which way, and with which issuer and audience, is iagent's (Q1).**
- Until it is ruled, the increment builds the PEP side behind one function, `bff_token(session) -> str | None`, which
  returns `None`. Every row of §1.2 is testable with it returning `None` or a fixed token.

### 1.4 No task state

- The PEP proxies. It does not store task rows, counts, ids or states in postgres, Electric, a topic or a file.
- It does not cache across requests. The browser's own fetch cache is the only one.
- **The ledger and intake rows are not task state.** They are OpenDDIL's own records of what it sent and what it
  admitted (ADR-0046 decision 1).

## 2. "Needs you" and Tasks in each tier's feed

- **One PEP route,** `GET /tasks`. It calls the tier's `GET /me/human_tasks` with the person's token, and returns the
  rows unchanged, with an added `link` for each.
- **"Needs you"** is the count of rows returned. **Tasks** is the list.
  - Both sit beside the tier's existing feed on each page: Maintainer, Regional and HQ (ADR-0058 finding 1).
  - Neither sits inside `tactical_events`. No task row is written there.
- **Per viewer, not per OpenDDIL role.**
  - iagent already fans a task out to every actor its grants authorise (finding 11). The person's queue is the
    role-scoped view, decided by its owner.
  - OpenDDIL does not filter it again by its own single role (finding 8). It has no maintainer role to filter by, and a
    second filter would be a second authority over who sees a task.
- **The action is a deep link.**
  - `link` = `${cortexBase}/case/${encodeURIComponent(case_id)}`, with the sign-in hint, as `CortexApprovalLink` builds
    it. `cortexBase` is the tier's own cortex.
  - A row with no `case_id` gets no link. The UI names it: "open in cortex".
  - A link to the task itself waits for cortex-ui to have one (Q4). The card rendered in place waits for ADR-0058 §5.
- **Severed or unreachable BFF:** the route returns `503` with `{"state": "iagent unreachable at this tier"}`. The UI
  shows that, never an empty list.

## 3. "My reports" on the edge maintenance pane

### 3.1 States, their owners and where each is read

| State | Read from | Owner | Note |
|---|---|---|---|
| filed | the open episode: `sources[].reported_by`, time | OpenDDIL | open episodes only (finding 3) |
| queued for send | no ledger row for the episode's event at this tier's door, or a `held` row | OpenDDIL | `held` shows "retries exhausted" beside it |
| sent | a `delivered` row: `recorded_at`, `http_status` | OpenDDIL | |
| case opened | that row's `case_id` | iagent's id, kept in OpenDDIL's ledger | a `case_id_mismatch` stays visible |
| proposed | the case's decide step: the choice, the actor, the time | iagent | read with the person's token (Q12) |
| approved | the case's review step: the actor, the time, `acted_via` | iagent | read with the person's token (Q12) |
| released | the admitted action in `intake_records` (decision, `decided_at`), or a refusal with its reason | OpenDDIL's decision on iagent's artifact | a refusal is a state, not a gap |
| work recorded | the work order | MMIS | no source today (finding 12). Shown as "no source", never as pending |
| sent, awaiting reply | `delivered`, and the next state cannot be read because the step that owns it is at a tier this one cannot reach | — | named; distinct from "case opened, nothing proposed yet" |

- **No combined status.** Each state is a row with its source and time. There is no overall badge (ADR-0058 §2b).

### 3.2 The joins

- **Filer → ledger.** The ledger gains `reported_by text[]`, carried in `stamps` the way the four episode columns are
  (finding 2). It holds every subject in the episode's sources at assembly.
  - Rows recorded before the change have it null, and are not listed. The pane says "reports sent before <date> are
    not listed".
  - This is the only store change in the increment. It is a fact about a record OpenDDIL sent, not task state.
- **Episode → ledger:** by `episode_id`.
- **Ledger → case:** by `case_id`.
- **Case → action.** The kind declaration gains `case_ref`, a pointer into the action body to its case id. The join
  reads that pointer.
  - Matching on the intake key's prefix is refused. The key's format is the consumer's, not ours.
  - An action whose kind declares no `case_ref` is not joined. The pane names it.
- **Case → proposed and approved:** read through the PEP from the tier's BFF, per request, not stored (§1.4).

### 3.3 The route

- `GET /reports/mine` on the PEP. It reads the viewer's subject from the session and returns the timeline rows above.
- The filer's own subject is the only filter. A supervisor's "reports at this tier" is not in the increment.

## 4. The disposition on the asset's card

- **At the tier that reported it.** The card reads the latest admitted or refused action for each of the asset's cases.
  It does this by extending the existing `/egress/cases` response (finding 4) with:
  - `disposition`: the action's work-order option and stage;
  - `decided_at`;
  - `decision.allowed` and `decision.reason`.
- **A finding in ADR-0058's sense:** a judgment, drawn with its producer (the case, by id) and its time.
- **A refusal is drawn as a refusal,** with its reason, such as `schema_invalid`. It is never drawn as "no
  disposition".
- **It needs the route change (§7) to show at the edge.** Until then, the action is admitted at the hub only (finding
  6), and the edge's card names it: "disposition held at the hub".

## 5. The maintainer's day: four sources, each with its owner

| Source | Owner | Read | Today |
|---|---|---|---|
| Tasks | iagent | §2 | per person, needs a person's token (Q1) |
| Work orders | MMIS, through iagent | iagent's BFF | no connector (finding 12). The row reads "no source" |
| My reports | OpenDDIL | §3 | open episodes and stamped ledger rows |
| Due and recommended | OpenDDIL, advisory | the producers in finding 10 | no expired-inspection producer |

- **Advisory means advisory.**
  - A due or recommended item is drawn as a finding, with its producer.
  - Accepting it files a record out through N5, through the same gate, to the owner's system. That system turns it into
    a task or a work order. Which trigger takes it is Q11.
  - OpenDDIL keeps no "accepted" state beyond the record it released.
- **The four are drawn side by side, never merged into one list with one order.** Each keeps its owner's order and
  its owner's name.

## 6. Workflow scope

What this increment holds OpenDDIL to, and what it asks of iagent:

| Rule | OpenDDIL's side | iagent's side |
|---|---|---|
| Local workflows run severed | the tier's door is local (§7). Nothing in OpenDDIL's path to it crosses a tier | the tier's iagent, its permission service and its realm must be local too (Q3) |
| A cross-tier workflow runs its local steps, then waits with an honest state | "sent, awaiting reply" (§3.1) | the wait must outlast a sever, and say so in the case view (Q7). Today it ends `TIMED_OUT` at 72 h (finding 17) |
| One owning tier per step | every state in §3.1 shows the tier that owns it | each step names its owning tier (Q3, Q6) |
| Decisions replicated, never merged | the UI draws each tier's decision as its own row, never a reconciled one (ADR-0042 §3, ADR-0040) | who replicates, and in what record (Q8) |
| Declared delegation for a severed cross-tier step, with owner and expiry, marked on replication | a delegated decision is drawn "via <delegate>, for <subject>, until <expiry>" | where owner and expiry are declared (Q9). Today `acted_via` has neither (finding 18) |

## 7. The route change

- **Today:** one egress at the hub serves every tier (ADR-0046 decision 2, finding 6). A severed edge queues at its
  gate output.
- **After:**
  - Each tier renders its own assembler, forwarder and intake, with one route to its local BFF.
  - Each tier's `intake_records` rows are stored at that tier.
  - The hub keeps a route to its own iagent for the steps the hub owns.
- **This is ADR-0046's stated design,** not a reversal: "Per-tier instances are the design" (decision 2), and "storage
  at the owning tier stays the design" (§5.4). When it is built, ADR-0046 gains a status line saying so.
- **One door per record.** A record is delivered by the door at its owning tier only. The hub's door skips records
  whose owning tier has its own door. A record delivered twice would open two cases (ADR-0046, "The consumer's case
  key").
- **How a hub-owned step gets its input from an edge case is open (Q6).**
  - Proposed for iagent's ruling: the input rides OpenDDIL's tier rail as a record under ADR-0042 custody, and is
    delivered at the hub's door. The rail already holds custody through a sever.
  - The alternative is iagent calling iagent.
- **The chart work is owed** (§10). This repository does not change the chart.

## 8. What must not change

- **ADR-0046 decision 1:** OpenDDIL holds no workflow state.
- **The intake's decision rule,** including the re-decide amendment of 2026-11-10.
- **The ledger's existing columns and outcomes.** `reported_by` is added, and nothing else changes.
- **The forwarder's dedupe on `episode_id`** (ADR-0046, "The consumer's case key").
- **The cases route's response for existing readers.** New fields are added, and none are removed or renamed.
- **No combined status anywhere in the increment.**

## 9. Checks for the PR

Each is a test a named workflow runs.

1. **No task state.** With a store fake that raises on any write, `GET /tasks` and `GET /reports/mine` succeed.
   - No migration in the PR adds a table or column holding a task id or task status.
   - Red: a planted write to a task table fails the test.
2. **The token rows.**
   - Against a stub BFF: with a session, the outbound request carries the person's token.
   - Without a session, `GET /tasks` sends nothing and returns the "sign in" state.
   - The service principal is never sent on `GET /tasks`.
3. **Unreachable is named.** With the stub BFF down, `GET /tasks` returns 503 with the named state, never `[]`.
4. **Every state in §3.1 from fixtures.** One fixture per state, including:
   - "queued for send" for no row and for `held`;
   - "sent, awaiting reply" with the BFF unreachable;
   - "work recorded" as "no source".
5. **The filer stamp.**
   - A delivered row carries `reported_by`.
   - An episode with two sources carries both subjects.
   - A row without the stamp is not listed, and the pane's note is present.
6. **The case join uses `case_ref` only.** An action whose key starts with a case id, but whose kind declares no
   `case_ref`, is not joined.
7. **The disposition.**
   - An admitted action draws its option with producer and time.
   - A refused one draws "refused" with its reason.
   - A case with no action draws nothing, and the absence is named.
8. **The link.**
   - `link` equals the case link `CortexApprovalLink` builds for the same id and base.
   - A row without `case_id` has none.
9. **One door per record** is a chart test, owed with §10. Rendered for an edge and the hub, each record kind has
   exactly one delivering route per owning tier.

## 10. Owed by others, not built here

- **iagent:**
  - the person's token path (Q1);
  - a deployment per tier (Q3);
  - a task deep link in cortex-ui (Q4);
  - decision replication (Q8), delegation owner and expiry (Q9);
  - the MMIS connector (Q10);
  - the trigger for an accepted advisory item (Q11);
  - the case view's step history (Q12).
- **The chart's owner:**
  - the egress, intake and assembler at every tier, each with its own route and `intake_records`;
  - `iagent.bffUrl` and the cortex base per tier;
  - the one-door test (check 9).
- **Operations:** the deployments' routes and credentials per tier, at a roll.

## Questions for iagent's architect

Named here, and not answered by this spec.

1. **The person's token.** Which token will the BFF accept from a tier's PEP for a person? Token exchange at iagent's
   realm (ADR-0046 §6), a sign-in through the broker, or another way? Which issuer and audience must it carry?
2. **Before a session.** May OpenDDIL's delegate read a named person's queue, with `on_behalf_of` on a read? Or does the
   feed show no tasks until the person signs in, as §1.2 assumes?
3. **Per tier.** Is iagent deployed once per tier, with its own permission service, realm, workflow runtime and
   cortex-ui? What names the tier an instance serves, given that `owning_tier` is today only an audience suffix?
4. **The task link.** Will cortex-ui have a deep link to one pending task, and in what form? Until then, the link is
   the task's case.
5. **Grant changes.** Tasks are fanned out at registration. Is a pending task fanned out again when a grant changes?
6. **Cross-tier steps.** How does a step owned by another tier's iagent receive its input and return its decision:
   iagent to iagent, or a record on OpenDDIL's tier rail delivered at that tier's door (§7's proposal)?
7. **Severed waits.** An await ends at its deadline with no disposition. Does a step waiting on another tier keep
   waiting through a sever? How does the case view name that state?
8. **Decision replication.** Who replicates a decision from its owning tier to the others, and in what record? Does a
   replicated decision carry its owning tier and `acted_via`?
9. **Delegation.** Where are a delegation's owner and expiry declared? Are they on the decision record that replicates?
10. **Work orders.** Which system holds the work order, and through what connector? Until then, the action record's
    `work_order` is the only one.
11. **An accepted advisory item.** Which trigger kind takes an accepted due or recommended item and makes it a task or a
    work order?
12. **The case's history for a person.** Does `GET /cases/{id}` give each step's choice, actor, time and `acted_via` to
    a person who may view the case, so that §3.1 can show proposed and approved without OpenDDIL storing them?

## What this does not establish

- Nothing is built or run. Finding 13's door refusal is an inference from code.
- Closed episodes are not listed unless they were sent after the stamp lands. An episode filed and resolved before it
  was sent leaves no row (finding 3).
- No measurement of the extra BFF load from per-request reads.
- Nothing is decided for iagent or cortex-ui.

## Related

- [ADR-0058](ADR-0058-a-card-is-a-declaration-one-grammar-across-both-uis.md): the shape split this increment follows.
- [ADR-0046](ADR-0046-maintenance-bridge-events-out-actions-in.md): the bridge, its pass decisions and its delegation
  design.
- [ADR-0042](ADR-0042-intent-custody-retention-and-multi-tier-reconciliation.md): custody and no merge at the parent.
- [ADR-0040](ADR-0040-offline-sustainment-and-intent-reconciliation.md): no merge semantics.
- [ADR-0031](ADR-0031-converged-edge-node-reasoning-plane-seams.md): a reasoning plane per tier.
- [ADR-0051](ADR-0051-failure-records-for-fracas.md): the closed-episode table, not scheduled.
- [Op-Cn](../docs/arch/views/Op-Cn.md): the operational view of N5 and N6, the record out and the action back.
