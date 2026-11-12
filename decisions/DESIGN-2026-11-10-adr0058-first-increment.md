# DESIGN 2026-11-10 — ADR-0058's first increment: iagent at every tier, its tasks and our reports in each tier's feed

**Status:** records a decision. The project owner's rulings of 2026-11-11 on ADR-0058's first increment, as an
implementer spec in three slices (3a, 3b, 3c), each with its own checks. Design only: nothing built, nothing run,
nothing measured for this increment. ADR-0058 is PROPOSED. This spec builds the part of it that has no card declaration
yet: what each tier's UI shows of work owned by iagent, and what it shows of the reports its own people filed. Ordered
2026-11-10, with its scope; sliced, and the closed-episode projection chosen over a ledger stamp, 2026-11-11.
**Builds on:** ADR-0058 §3 (cortex owns task and approval shapes; OpenDDIL owns record, finding and indicator) and
§6; ADR-0046 (decision 1: OpenDDIL holds no workflow state; decision 2 and §5.4: per-tier instances and owning-tier
intake are the design; §6: delegation); ADR-0051 (§1 and its first slice: a closed episode is kept, and projected at the
tier); ADR-0042 §3 (custody is recursive, and a parent never merges); ADR-0040 (no merge semantics); ADR-0031 (per-tier
reasoning plane).

**Read at:** OpenDDIL working trees of 2026-11-10, and `openddil-cm-service` at `a7a87f9` for closed episodes; iagent
`b4b41ad1`, iagent's two reports of 2026-11-11 on its task routes and task events, and its ADR-0068 draft PR at `e2ae0272`
(Proposed); cortex-ui `c51f932`. Line numbers move with them. These are reads, not runs. One is an inference from code
and is marked as one.

## What the increment is

Three slices. Each ships on its own, with its own checks (§9).

**3a. OpenDDIL only.** Nothing in it waits on iagent.

- **"My reports" on the edge maintenance pane:** the filer's episodes, open and closed, each with a state timeline
  (filed, sent, case opened, proposed, approved, released, work recorded). It is joined from the episode, the egress
  ledger and the intake records. Severed states are named: "queued for send", "sent, awaiting reply".
- **Closed episodes are projected** to a table at the tier, ADR-0051's `failure_episodes` (its first slice, item 2).
  The filer is read from the episode's sources. The egress ledger is unchanged: it stays a record of deliveries.
- **A supervisor's reports at the tier:** every episode filed at the tier, scoped by the PEP's existing label rule for
  that viewer.
- **The disposition on the asset's card** at the tier that reported it.
- **The OpenDDIL sources of the maintainer's day:** my reports, and due and recommended items (advisory).
- The states iagent owns (proposed, approved) are named "read in 3b" in this slice, never drawn as pending.

**3b. The task stream.** It waits on three things: iagent's answer on the person's token (Q1), the per-viewer seal
deployed on the instance read, and iagent's confirmation that its token checks are on at the tier (§1.2, the hold).

- **"Needs you" and Tasks in each tier's feed,** per viewer. The action is a deep link to the pending task's case in
  cortex now, and the card rendered in place later.
- **The iagent-owned states of My reports:** proposed and approved, read per request with the person's token (Q12).
- **iagent's four accepted positions** (§2a): dark until sealed, a withheld task is a routing fault, a delegated act
  shows its three parties, a manual shows its revision, digest and age.
- **Tasks in the maintainer's day.**

**3c. The route change.** A door per tier, the chart work, and Q6.

- **The edge's door is its local iagent.** The hub carries the cross-tier steps.
- **The disposition at the edge** is read from the edge's own intake.

**Across the slices:**

- **iagent runs at every tier.** Each tier's OpenDDIL is a consumer of its local iagent's BFF. OpenDDIL stores no task
  state.
- **Workflow scope (§6):**
  - local workflows run severed;
  - a cross-tier workflow runs its local steps and waits at the first step another tier owns, with an honest state;
  - one owning tier per step; decisions are replicated, never merged;
  - a severed cross-tier step may be delegated only by a declared delegation with a delegator, a delegate and an
    expiry, and the delegation is marked on what replicates.
- **The twelve questions for iagent's architect** are at the end, each tagged with the slice it blocks. This spec
  does not answer them.

**Not in the increment:**

- No task table, task cache or task column anywhere in OpenDDIL's store, Electric publication or topics.
- No column added to the egress ledger.
- No card rendered in place. That needs cortex's task card declared under ADR-0058 §5's profile.
- No MMIS connector. That is iagent's (finding 12).
- No change to how the PEP filters, and no change to the intake's decision rule (ADR-0046, amended 2026-11-10).
- No chart change in this repository. The chart work is owed (§7, §10).
- The rest of ADR-0051's first slice (the episode history pane, the usage meters at open and close) is not built here;
  only its table, which My reports reads.

## Findings that shape it

**OpenDDIL**

1. **The filer is stored on the episode, not on the ledger.** The PEP sets `recordedBy` to the subject
   (`openddil-demo/gateway/pep.py:2448`, posted at `:2463`). The subject is the OIDC `sub`, or the header value in header
   mode (`:3595`). cm-service stores it as `sources[].reported_by` (`openddil-cm-service/src/events/asset_cm.py:587`),
   and it reaches `asset_cm_state.manual_discrepancies[].sources[]` (`openddil-stack/schema/schema.hcl:286`).
   `egress_delivered_events` has no filer column, and gets none (§3.2).
2. **The ledger already carries the episode.**
   - `egress_delivered_events` (`schema.hcl:2051`) has route, event_id, outcome, http_status, case_id, topic,
     partition, kafka_offset, first_recorded_at, recorded_at, episode_id, asset_id, component and fault_code.
   - The four episode columns arrive as `stamps` (`openddil-demo/egress/forwarder.py:454-481`). Rows recorded before
     2026-10-17 have them null.
   - Outcomes are `held` (retries exhausted, `forwarder.py:43`), `delivered` and `failed`.
3. **Closed episodes are kept, and not projected.**
   - Since 2026-10-29 (`a7a87f9`, ADR-0051's first slice, item 1), cm-service keeps each closed episode on the asset's
     durable state instead of dropping it: `ClosedEpisodeRecord`
     (`openddil-cm-service/src/as_maintained/persistence_model.py:126-150`, the list at `:222`), appended at close
     (`src/events/asset_cm.py:689`).
   - It carries the episode's id, type, description, severity, recommended action, `detected_at_ns`, component,
     fault code, `sources[]` with `reported_by`, `cleared_at_ns`, `cleared_by`, `resolution`, `baseline_id` and
     `mod_compliance`. Its identity is `(discrepancy_id, detected_at_ns)`, as ADR-0051 was amended to key it.
   - It is removed from the published payload (`asset_cm.py:912`), so the `asset-cm-state` wire shape did not change.
     Only the open set reaches `asset_cm_state`. No table holds closed episodes: ADR-0051's item 2, `failure_episodes`
     at the tier, was left for later.
   - Closed episodes live only in the workflow engine's durable state. A wipe of that state loses every closed episode
     not yet projected.
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
    - iagent reports (2026-11-11) that "Needs you" has no route today: its own UI counts the viewer's drops awaiting a
      kind, in the browser. A per-viewer read, with label scoping on the task list, the live feed and the task holder's
      case view, comes in iagent's first change after its 0.4.85 release. Its route name comes when that change opens.
    - iagent reports that task opened and task closed are not events today. It proposes them as ADR-0068's first case
      journal entry kinds, with an occurrence id per transition and an "after N" cursor, scoped per viewer and dark
      until sealed. Nothing of that is built.
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
16. **iagent has no notion of tiers in code yet.**
    - `owning_tier` is a field of the incoming event. It is used only as an audience suffix in the maintenance workflow
      definitions in iagent's deployment overlay.
    - No code reads it. The chart has no site, tier, parent or peer setting.
    - iagent's ADR-0068 (draft, Proposed) decides tier profiles as configuration (§1), a minimal edge profile that owns
      steps offline (§2), a case journal replicated by entry (§3), and one owning tier per step (§4).
17. **A wait ends at its deadline without a disposition.**
    - An await races a durable sleep. On the deadline it ends `TIMED_OUT`, with no disposition
      (`agent_fleet/restate_analyst/main.py:2520-2550`).
    - The maintenance decide and review awaits have 72 h deadlines.
    - The release step is one emit, with no step of its own for the decision.
18. **Nothing replicates a decision, and a delegation has no expiry, today.**
    - A person's act needs a live BFF and a live permission check, and a cache miss with the permission service down is
      a denial (`auth.py:259-262`).
    - There is no offline queue and no decision replication.
    - A delegation is recorded as `acted_via` on the approval (`main.py:3099-3131`), with no owner and no expiry.
      ADR-0068 §5 and §7 (draft) make the expiry required and record the delegator, the delegate and the expiry on a
      delegated act.

## 1. iagent at every tier; the tier's OpenDDIL as its consumer

### 1.1 One consumer per tier

- Each tier's PEP reaches exactly one BFF, its tier's own: `iagent.bffUrl`, one value per tier. The PEP never calls
  another tier's BFF.
- Cross-tier work goes through §7, never through a PEP calling across.

### 1.2 Which token, and the hold

**The hold.** No person's token is forwarded to the BFF until iagent confirms that the release which checks a token's
audience and issuer is deployed at that tier. iagent's instruction until then: send only the tier's client-credentials
token, with `on_behalf_of` naming the person. The hold is a per-tier setting, `iagent.personToken.confirmed`, false by
default, set true at a roll only on iagent's confirmation for that tier's instance.

| Situation | Token the PEP presents | What it can read |
|---|---|---|
| A person has a session, the hold lifted at this tier | the person's token for the BFF's realm (§1.3) | that person's queue and the cases that person may view |
| A person has a session, the hold in place | the tier's client-credentials token, with `on_behalf_of` naming the person | what iagent serves its delegate for that person (finding 13) |
| No session yet | none, and no request leaves | nothing. The UI names it: "sign in to see your tasks" |

- **Never a person's token while the hold is in place,** and never the client-credentials token without
  `on_behalf_of` naming the person on a read for that person.
- **Before a session, nothing is sent.** Whether the delegate may read a person's queue with no session is Q2.
- **The token is held server-side, like the refresh token** (finding 7): never a cookie, a response body or a log line.

### 1.3 How the PEP gets the person's token

- OpenDDIL keeps no access token today (finding 7), and the BFF accepts only its own realm's tokens (finding 14).
- ADR-0046 §6 names OAuth 2.0 token exchange (RFC 8693) as the design. The PEP would exchange the session's token for
  one the BFF's realm issues to that person.
- **Which way, and with which issuer and audience, is iagent's (Q1).**
- Until it is ruled, the increment builds the PEP side behind one function, `bff_token(session) -> str | None`, which
  returns `None` while the hold is in place, and the client-credentials path carries the person in `on_behalf_of`.
  Every row of §1.2 is testable with it returning `None` or a fixed token.

### 1.4 No task state

- The PEP proxies. It does not store task rows, counts, ids or states in postgres, Electric, a topic or a file.
- It does not cache across requests. The browser's own fetch cache is the only one.
- **The ledger, intake and closed-episode rows are not task state.** They are OpenDDIL's own records of what it sent,
  what it admitted and what its people filed (ADR-0046 decision 1, ADR-0051 §1).

## 2. "Needs you" and Tasks in each tier's feed (3b)

- **One PEP route,** `GET /tasks`. It calls the tier's task list with the token of §1.2, and returns the rows
  unchanged, with an added `link` for each.
- **"Needs you"** is iagent's per-viewer read when it ships (finding 11); until then it is the count of rows returned.
  **Tasks** is the list.
  - Both sit beside the tier's existing feed on each page: Maintainer, Regional and HQ (ADR-0058 finding 1).
  - Neither sits inside `tactical_events`. No task row is written there.
- **Per viewer, not per OpenDDIL role.**
  - iagent fans a task out to every actor its grants authorise (finding 11). The person's queue is the role-scoped
    view, decided by its owner.
  - OpenDDIL does not filter it again by its own single role (finding 8). It has no maintainer role to filter by, and a
    second filter would be a second authority over who sees a task.
- **The action is a deep link.**
  - `link` = `${cortexBase}/case/${encodeURIComponent(case_id)}`, with the sign-in hint, as `CortexApprovalLink` builds
    it. `cortexBase` is the tier's own cortex.
  - A row with no `case_id` gets no link. The UI names it: "open in cortex".
  - A link to the task itself waits for cortex-ui to have one (Q4). The card rendered in place waits for ADR-0058 §5.
- **Severed or unreachable BFF:** the route returns `503` with `{"state": "iagent unreachable at this tier"}`. The UI
  shows that, never an empty list.

### 2a. iagent's four accepted positions

iagent's architect accepted these on 2026-11-11, and drafted them as ADR-0068 §6–§9 (Proposed). This increment holds
OpenDDIL's side to them.

| Position | ADR-0068 | OpenDDIL's side |
|---|---|---|
| The stream stays dark until the per-viewer seal is deployed on the instance read | §8 | `GET /tasks` makes no call to the BFF and returns `{"state": "tasks not yet available at this tier"}` until the tier's setting `iagent.sealed` names the release and instance iagent reports the seal deployed on, read from that instance's release record. Unset, it is dark. The UI shows the state, never an empty list |
| A label-withheld task is a routing fault, never shown redacted | §6 | OpenDDIL draws only the rows the BFF returns. It never draws a placeholder, a "hidden" count or a redacted row for a task it was not given. The routing fault is iagent's record |
| A delegated act shows the delegator, the delegate and the expiry | §7 | a delegated decision is drawn "via <delegate>, for <delegator>, until <expiry>". One missing any of the three is drawn "delegation incomplete", never as an undelegated act |
| Edge manuals show revision, digest and age | §9 | wherever a task, a case or the maintainer's day shows a manual, it shows the copy's revision, digest and age. A copy without them is drawn "unversioned copy" |

## 3. "My reports" on the edge maintenance pane (3a)

### 3.1 States, their owners and where each is read

| State | Read from | Owner | Note |
|---|---|---|---|
| filed | the episode, open (`asset_cm_state`) or closed (`failure_episodes`): `sources[].reported_by`, time | OpenDDIL | a closed episode also shows `cleared_at`, `cleared_by` and `resolution` |
| queued for send | no ledger row for the episode's event at its door, or a `held` row | OpenDDIL | `held` shows "retries exhausted" beside it |
| sent | a `delivered` row: `recorded_at`, `http_status` | OpenDDIL | |
| case opened | that row's `case_id` | iagent's id, kept in OpenDDIL's ledger | a `case_id_mismatch` stays visible |
| proposed | the case's decide step: the choice, the actor, the time | iagent | 3b: read with the person's token (Q12). In 3a, "read in 3b" |
| approved | the case's review step: the actor, the time, the delegation (§2a) | iagent | 3b, as proposed |
| released | the admitted action in `intake_records` (decision, `decided_at`), or a refusal with its reason | OpenDDIL's decision on iagent's artifact | a refusal is a state, not a gap |
| work recorded | the work order | MMIS | no source today (finding 12). Shown as "no source", never as pending |
| sent, awaiting reply | `delivered`, and the next state cannot be read because the step that owns it is at a tier this one cannot reach | — | named; distinct from "case opened, nothing proposed yet" |

- **No combined status.** Each state is a row with its source and time. There is no overall badge (ADR-0058 §2b).
- **Until 3c, the door is the hub's** (finding 6). The edge reads the ledger and the intake through the hub's pane API.
  Severed from the hub, those states read "door at the hub, unreachable", never "queued".

### 3.2 The closed-episode projection, and the joins

- **Closed episodes are projected** (ADR-0051's first slice, item 2): a `failure_episodes` table at the tier, keyed
  `(episode_id, detected_at)`, with `asset_id`, `component`, `fault_code`, `detected_at`, `cleared_at`, `cleared_by`,
  `resolution`, `sources` (with each `reported_by`), `baseline_id`, `mod_compliance` and the labels. Atlas migration.
  - cm-service emits one record per close, on a topic of its own. The `asset-cm-state` wire shape does not change
    (finding 3).
  - The projector writes it idempotently on the key. A replay writes no second row.
  - **Backfill at first start, from the live state and from exported files** (ruled 2026-11-12):
    - cm-service emits each closed episode it already holds once, on the same key.
    - The backfill also loads exported files. Each is an export of the closed episodes in the workflow engine's state,
      taken before a wipe, one line per episode with its asset. A file line goes through the same emit, so an episode
      found in the state and in a file, or in two files, is one row on the key.
    - **Both record shapes are accepted:** the shape stored in the workflow engine's state on a running tier, and the
      shape the current code declares (`ClosedEpisodeRecord`). Fields are mapped by name. A field a record lacks is
      left empty, never invented. A record without `discrepancy_id` or `detected_at_ns` is refused, counted and
      named. It is never written, and never dropped silently.
    - **Labels come from the asset's record, not the episode.** Neither shape carries labels on the episode. The
      asset's record carries them. A file line is loaded only with its asset's labels from the same export. A line
      without them is refused and named. It is never loaded unlabelled.
    - Closed episodes cleared by a wipe before this lands are gone unless an exported file holds them, and the pane
      says so.
  - The usage-meter columns at open and close are ADR-0051's and not filled here (out of the increment).
- **The ledger is unchanged.** It stays a record of deliveries. The filer is read from the episode, never from the
  ledger.
- **Filer → episodes:** the viewer's subject in the `sources[].reported_by` of an open or a closed episode.
- **Episode → ledger:** by `episode_id`. Where a refile after a close gives two episodes the same id, a ledger row
  joins the episode whose open interval holds its `first_recorded_at`. A row that fits none is listed as unmatched,
  never dropped.
- **Ledger → case:** by `case_id`.
- **Case → action.** The kind declaration gains `case_ref`, a pointer into the action body to its case id. The join
  reads that pointer.
  - Matching on the intake key's prefix is refused. The key's format is the consumer's, not ours.
  - An action whose kind declares no `case_ref` is not joined. The pane names it.
- **Case → proposed and approved (3b):** read through the PEP from the tier's BFF, per request, not stored (§1.4).

### 3.3 The routes

- `GET /reports/mine` on the PEP. It reads the viewer's subject from the session and returns the timeline rows above.
  The filer's own subject is the only filter.
- **`GET /reports/tier`, a supervisor's reports at the tier.** Every episode filed at the tier, open and closed, with
  the same timeline. It is scoped by the PEP: the viewer's role must be supervisor (finding 8), and the PEP's existing
  label rule for that viewer decides which episodes come back. Any other role gets `403` with the named state "reports
  at this tier are for a supervisor". Nothing from another tier is listed.
- The PEP reads store rows through shapes. One shape per tier on `failure_episodes` serves both routes, filtered in the
  PEP; the number of shapes does not grow with viewers.

## 4. The disposition on the asset's card (3a; at the edge, 3c)

- **At the tier that reported it.** The card reads the latest admitted or refused action for each of the asset's cases.
  It does this by extending the existing `/egress/cases` response (finding 4) with:
  - `disposition`: the action's work-order option and stage;
  - `decided_at`;
  - `decision.allowed` and `decision.reason`.
- **A finding in ADR-0058's sense:** a judgment, drawn with its producer (the case, by id) and its time.
- **A refusal is drawn as a refusal,** with its reason, such as `schema_invalid`. It is never drawn as "no
  disposition".
- **At the edge it needs the route change (3c).** Until then, the action is admitted at the hub only (finding 6), and
  the edge's card names it: "disposition held at the hub".

## 5. The maintainer's day: four sources, each with its owner

| Source | Owner | Read | Slice | Today |
|---|---|---|---|---|
| Tasks | iagent | §2 | 3b | per person, needs a person's token (Q1) and the seal |
| Work orders | MMIS, through iagent | iagent's BFF | later | no connector (finding 12). The row reads "no source" |
| My reports | OpenDDIL | §3 | 3a | open and closed episodes |
| Due and recommended | OpenDDIL, advisory | the producers in finding 10 | 3a | no expired-inspection producer |

- **Advisory means advisory.**
  - A due or recommended item is drawn as a finding, with its producer.
  - Accepting it files a record out through N5, through the same gate, to the owner's system. That system turns it into
    a task or a work order. Which trigger takes it is Q11.
  - OpenDDIL keeps no "accepted" state beyond the record it released.
- **The four are drawn side by side, never merged into one list with one order.** Each keeps its owner's order and
  its owner's name.
- **A manual shown in the day** carries its revision, digest and age (§2a).

## 6. Workflow scope

What this increment holds OpenDDIL to, and what it asks of iagent:

| Rule | OpenDDIL's side | iagent's side |
|---|---|---|
| Local workflows run severed | the tier's door is local (3c, §7). Nothing in OpenDDIL's path to it crosses a tier | the tier's iagent, its permission service and its realm must be local too (Q3; ADR-0068 §1–§2, draft) |
| A cross-tier workflow runs its local steps, then waits with an honest state | "sent, awaiting reply" (§3.1) | the wait must outlast a sever, and say so in the case view (Q7). Today it ends `TIMED_OUT` at 72 h (finding 17) |
| One owning tier per step | every state in §3.1 shows the tier that owns it | each step names its owning tier (Q3, Q6; ADR-0068 §4, draft) |
| Decisions replicated, never merged | the UI draws each tier's decision as its own row, never a reconciled one (ADR-0042 §3, ADR-0040) | who replicates, and in what record (Q8; ADR-0068 §3's case journal, draft) |
| Declared delegation for a severed cross-tier step, with its three parties, marked on replication | a delegated decision is drawn "via <delegate>, for <delegator>, until <expiry>" (§2a) | where the delegation is declared (Q9; ADR-0068 §5 and §7, draft). Today `acted_via` has no owner and no expiry (finding 18) |

## 7. The route change (3c)

- **Today:** one egress at the hub serves every tier (ADR-0046 decision 2, finding 6). A severed edge queues at its
  gate output.
- **After:**
  - Each tier renders its own assembler, forwarder and intake, with one route to its local BFF.
  - Each tier's `intake_records` rows are stored at that tier.
  - The hub keeps a route to its own iagent for the steps the hub owns.
- **This is ADR-0046's stated design,** not a reversal: "Per-tier instances are the design" (decision 2), and "storage
  at the owning tier stays the design" (§5.4). ADR-0046's status block says so (noted 2026-11-11). The note applies
  when this is built.
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
- **The ledger's columns and outcomes.** Nothing is added; it stays a record of deliveries.
- **The `asset-cm-state` wire shape** (finding 3). Closed episodes reach the store on their own topic.
- **The forwarder's dedupe on `episode_id`** (ADR-0046, "The consumer's case key").
- **The cases route's response for existing readers.** New fields are added, and none are removed or renamed.
- **No combined status anywhere in the increment.**

## 9. Checks, per slice

Each is a test a named workflow runs. A slice merges on its own checks.

### 3a

1. **The closed-episode projection.**
   - A close emits one record; the projector writes one `failure_episodes` row on `(episode_id, detected_at)`.
   - A replay of the topic writes no second row.
   - Over a fixture of 1,001 closes, the topic's count and the table's count are equal.
   - The backfill emits each held closed episode once; a second start adds no row.
   - **From an exported file:** a fixture export loads one row per line. An episode in both the live state and the
     file is one row. Loading the same file twice adds no row.
   - **The stored shape:** a fixture with the field set stored in the workflow engine's state on a running tier (read
     2026-11-12) loads, each field in its column.
   - **The current code's shape:** a fixture built from the current `ClosedEpisodeRecord` loads the same way.
   - Red: a record without `detected_at_ns` is refused and counted, not written. A file line without its asset's
     labels is refused, not loaded unlabelled.
   - The published `asset-cm-state` payload is byte-equal to a golden payload taken before the change.
2. **No task state, ledger unchanged.** With a store fake that raises on any write, `GET /reports/mine` and
   `GET /reports/tier` succeed.
   - The slice's only migration adds `failure_episodes`. No migration adds a column to the ledger, or a table or column
     holding a task id or task status.
   - Red: a planted ledger column fails the test.
3. **Every OpenDDIL-owned state in §3.1 from fixtures.** One fixture per state, including:
   - "filed" for an open and for a closed episode, the closed one with `cleared_by` and `resolution`;
   - "queued for send" for no row and for `held`;
   - "door at the hub, unreachable" with the hub's pane API down;
   - "proposed" and "approved" as "read in 3b";
   - "work recorded" as "no source".
4. **The filer.**
   - An episode with two sources lists for both filers.
   - A viewer in no episode's sources gets an empty list, with the state "no reports filed by you".
   - Two episodes sharing an id join their ledger rows by interval; a row that fits neither is listed as unmatched.
5. **A supervisor's reports at the tier.**
   - A supervisor sees every episode at the tier that the PEP's label rule admits.
   - A planted episode with a label the supervisor lacks is absent.
   - An edge-operator gets `403` with the named state.
   - An episode from another tier is absent.
6. **The case join uses `case_ref` only.** An action whose key starts with a case id, but whose kind declares no
   `case_ref`, is not joined.
7. **The disposition.**
   - An admitted action draws its option with producer and time.
   - A refused one draws "refused" with its reason.
   - A case with no action draws nothing, and the absence is named.
   - At the edge, the card reads "disposition held at the hub".
8. **Shapes do not grow with viewers.** Twenty viewers on `GET /reports/mine` open no more shapes than one.

### 3b

1. **The hold.** With `iagent.personToken.confirmed` false, against a stub BFF:
   - no outbound request carries a person's token;
   - each carries the client-credentials token with `on_behalf_of` naming the session's person;
   - red: a planted forward of the person's token fails the test.
   With it true, the outbound request carries the person's token, and never the client-credentials one.
2. **Dark until sealed.** With `iagent.sealed` unset, `GET /tasks` makes no outbound call and returns the named dark
   state. With it naming a release the instance does not report, the same.
3. **No session sends nothing.** Without a session, `GET /tasks` sends nothing and returns the "sign in" state.
4. **A withheld task is not drawn.** A stub that withholds a task returns fewer rows; the UI draws no placeholder, no
   hidden count and no redacted row.
5. **Unreachable is named.** With the stub BFF down, `GET /tasks` returns 503 with the named state, never `[]`.
6. **The link.**
   - `link` equals the case link `CortexApprovalLink` builds for the same id and base.
   - A row without `case_id` has none.
7. **The delegation.** A delegated approval draws all three parties. One missing its expiry draws "delegation
   incomplete".
8. **The manual.** A manual reference draws revision, digest and age. One without them draws "unversioned copy".
9. **Proposed and approved** are read per request with the person's token, and a store fake that raises on any write
   still passes.

### 3c

1. **One door per record,** a chart test, owed with §10. Rendered for an edge and the hub, each record kind has exactly
   one delivering route per owning tier.
2. **The hub skips.** A record whose owning tier has its own door is not delivered by the hub's.
3. **The disposition at the edge** is read from the edge's own `intake_records`, and the "held at the hub" state no
   longer appears there.

## 10. Owed by others, not built here

- **iagent:**
  - the person's token path (Q1), and the confirmation that lifts the hold, per tier;
  - the seal and its release and instance, per tier;
  - a deployment per tier (Q3);
  - a task deep link in cortex-ui (Q4);
  - decision replication (Q8), the delegation's declaration (Q9);
  - the MMIS connector (Q10);
  - the trigger for an accepted advisory item (Q11);
  - the case view's step history (Q12).
- **The chart's owner:**
  - 3b: `iagent.bffUrl`, `iagent.personToken.confirmed`, `iagent.sealed` and the cortex base per tier;
  - 3c: the egress, intake and assembler at every tier, each with its own route and `intake_records`;
  - 3c: the one-door test.
- **Operations:** the deployments' routes and credentials per tier, at a roll; setting the hold and the seal only on
  iagent's word for that tier.

## Questions for iagent's architect

Named here, and not answered by this spec. Each is tagged with the slice it blocks. They go to iagent's architect as
one packet.

1. **[3b] The person's token.** Which token will the BFF accept from a tier's PEP for a person? Token exchange at
   iagent's realm (ADR-0046 §6), a sign-in through the broker, or another way? Which issuer and audience must it carry?
   *In part:* until iagent confirms its token checks at the tier, no person's token is sent (§1.2).
2. **[3b] Before a session.** May OpenDDIL's delegate read a named person's queue, with `on_behalf_of`, when the person
   has no session? Or does the feed show no tasks until the person signs in, as §1.2 assumes? *In part:* with a
   session, the client-credentials token with `on_behalf_of` is iagent's interim instruction.
3. **[3c] Per tier.** Is iagent deployed once per tier, with its own permission service, realm, workflow runtime and
   cortex-ui? What names the tier an instance serves, given that `owning_tier` is today only an audience suffix?
   *In part:* ADR-0068 §1–§2 (draft).
4. **[later] The task link.** Will cortex-ui have a deep link to one pending task, and in what form? Until then, the
   link is the task's case.
5. **[3b] Grant changes.** Tasks are fanned out at registration. Is a pending task fanned out again when a grant
   changes?
6. **[3c] Cross-tier steps.** How does a step owned by another tier's iagent receive its input and return its decision:
   iagent to iagent, or a record on OpenDDIL's tier rail delivered at that tier's door (§7's proposal)? *In part:*
   ADR-0068 §4 (draft): ownership moves only by an entry its owner writes.
7. **[3c] Severed waits.** An await ends at its deadline with no disposition. Does a step waiting on another tier keep
   waiting through a sever? How does the case view name that state?
8. **[3c] Decision replication.** Who replicates a decision from its owning tier to the others, and in what record? Does
   a replicated decision carry its owning tier and its delegation? *In part:* ADR-0068 §3's case journal (draft).
9. **[3c] Delegation.** Where is a delegation declared? Are its delegator, delegate and expiry on the decision record
   that replicates? *In part:* ADR-0068 §5 and §7 (draft).
10. **[later] Work orders.** Which system holds the work order, and through what connector? Until then, the action
    record's `work_order` is the only one.
11. **[later] An accepted advisory item.** Which trigger kind takes an accepted due or recommended item and makes it a
    task or a work order?
12. **[3b] The case's history for a person.** Does `GET /cases/{id}` give each step's choice, actor, time and delegation
    to a person who may view the case, so that §3.1 can show proposed and approved without OpenDDIL storing them?
    *In part:* iagent's per-viewer change applies the label rule to `approvals[].task` and to the task holder's case
    view.

## What this does not establish

- Nothing is built or run. Finding 13's door refusal is an inference from code.
- Closed episodes before 2026-10-29 were dropped, not kept, and are not listed. Ones cleared by a wipe of the workflow
  engine's state before the projection lands are gone too (finding 3).
- No measurement of the extra BFF load from per-request reads, or of the shape cost of §3.3.
- ADR-0068 is a draft on iagent's side. The positions in §2a are iagent's accepted positions; their section numbers
  follow the draft.
- Nothing is decided for iagent or cortex-ui.

## Related

- [ADR-0058](ADR-0058-a-card-is-a-declaration-one-grammar-across-both-uis.md): the shape split this increment follows.
- [ADR-0046](ADR-0046-maintenance-bridge-events-out-actions-in.md): the bridge, its pass decisions and its delegation
  design.
- [ADR-0051](ADR-0051-failure-records-for-fracas.md): the closed episode kept (§1), and the `failure_episodes` table
  this increment builds (first slice, item 2).
- [ADR-0042](ADR-0042-intent-custody-retention-and-multi-tier-reconciliation.md): custody and no merge at the parent.
- [ADR-0040](ADR-0040-offline-sustainment-and-intent-reconciliation.md): no merge semantics.
- [ADR-0031](ADR-0031-converged-edge-node-reasoning-plane-seams.md): a reasoning plane per tier.
- [Op-Cn](../docs/arch/views/Op-Cn.md): the operational view of N5 and N6, the record out and the action back.
- iagent's ADR-0068, the edge tier: draft, Proposed, on iagent's side.
