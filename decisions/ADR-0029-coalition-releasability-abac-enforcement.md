# ADR-0029 — Coalition releasability: ABAC enforcement with one PDP and many PEPs

## Status

Accepted (2026-08-05). Slice 1 (read path) is the scoped implementation;
Slices 2–3 are named and fenced below.

## Context

OpenDDIL is deployed into coalition and multinational environments. In
those deployments the fleet visible on a single cluster is not uniformly
visible to every operator using it: an asset's telemetry carries an
originating nation, and what may be shown to whom is governed by
releasability rules that are a property of the *data*, not of the
application.

Two consequences fall out of that, and they are the reason this ADR
exists rather than a configuration note:

1. **Access is a data attribute question, not a screen question.** The
   same Regional view, rendered for two different operators on the same
   cluster, must show different fleets. Role-based access control
   ("regional operators see the Regional view") cannot express this —
   the two operators hold the same role. The deciding inputs are
   attributes of the subject (which nations they are cleared into),
   attributes of the resource (which nation originated the row, who it
   is releasable to), and attributes of the environment (which tier the
   request arrived at). That is attribute-based access control (ABAC).

2. **Enforcement must survive severance.** ADR-0021 and ADR-0022
   establish that the edge→regional→HQ topology is load-bearing and that
   tiers must keep functioning when the link above them is cut. An
   authorization design that requires a call to a central decision
   service is therefore disqualified: the first DDIL sever would either
   fail every request closed (edge goes dark) or fail open (enforcement
   is theatre). Whatever mechanism we choose has to make decisions
   locally at each tier.

This is a generic OSS capability. The labelling concepts align with
STANAG 4774 (confidentiality label syntax) and STANAG 4778 (metadata
binding) — the point being that "originator nation + releasable-to set,
bound to the data" is a standardized shape in this domain, not something
OpenDDIL is inventing. OpenDDIL does not implement those STANAGs; it
adopts the attribute shape so a deployment that does implement them has
somewhere to put the values.

### Classification rides the same mechanism

Coalition releasability (nation) and classification tiering (e.g.
restricted vs. releasable) are two axes of the same question: *is this
subject permitted to see this resource?* They differ in the attribute
consulted, not in the machinery.

This ADR shapes policy for **both** axes now and demonstrates **nation**
first. `Provenance.classification` already exists on the wire (field 6,
free-text, application-defined). The policy model treats it as a second
resource attribute from the outset so that adding the classification
axis later is a policy-rule change and a column, not an architecture
change.

## Decision

### 1. One PDP, many PEPs

A single **policy decision point** (PDP) — [Topaz](https://www.topaz.sh/)
— owns every access decision. Multiple **policy enforcement points**
(PEPs) sit at system boundaries and *ask* the PDP; none of them decide
anything themselves.

The discipline that makes this worth stating: **no component may contain
independent authorization logic.** A PEP's only authorization behaviour
is (a) gather attributes, (b) ask Topaz, (c) apply the answer verbatim.
When a PEP translates a decision into a query filter, that filter must
encode only what Topaz decided — it is a *transport* for the decision,
not a second decision.

The corollary is that frontend role views are not access control. They
consume an already-filtered data stream. They must not filter for
security, and any filtering they do for presentation must be understood
(and reviewed) as cosmetic.

### 2. Three attribute categories

| Category | Attributes | Source |
|---|---|---|
| **Subject** | `nation`, `clearance`, `role` | Asserted entitlements (see §5) |
| **Resource** | `classification`, `originator_nation`, `releasable_to`, provenance | Stamped at ingress (see §3) |
| **Environment** | `tier`, time, request origin | Known by the PEP at request time |

`clearance` is shaped into the subject model from the start and left
unused in Slice 1. It is the hook the classification axis needs; carrying
it now costs nothing and avoids a subject-schema migration later.

### 3. Labels are provenance, stamped at ingress

Releasability labels are **provenance**, and OpenDDIL already has a
discipline for provenance: stamp it at the earliest tier that knows the
answer, carry it on the Silver event, never re-derive it downstream
(ADR-0022/0023, `Provenance.edge_id` / `region_id`).

Releasability labels join that block:

```protobuf
message Provenance {
  // ... existing fields 1-8 ...

  // ADR-0029: coalition releasability labels. Stamped at ingress by the
  // adapter that knows the source's national origin; never re-derived
  // downstream. Aligned to STANAG 4774/4778 label concepts.
  string          originator_nation = 9;   // e.g. ISO-3166 alpha-3
  repeated string releasable_to     = 10;  // nations this may be released to
  reserved 11;                             // policy_label — structured
                                           // confidentiality label, when a
                                           // deployment needs full 4774 syntax
}
```

`policy_label` is **reserved, not defined**. A structured
confidentiality label is a real requirement for some programs and a
premature abstraction for OpenDDIL today; reserving the field number
keeps the door open without shipping a shape we would have to guess at.

How the values get stamped is adapter-specific and deployment-specific.
Deployments whose asset identifiers already encode national origin (a
nation prefix on the asset id, for example) parse it in the adapter's
mapping layer. That mapping is deployment configuration and lives in the
deployment's own bundle overlay — the OSS core defines the field and the
discipline, not any particular naming convention.

### 4. Decisions at boundaries

PEPs sit where data crosses a trust boundary:

- **Read path (Slice 1):** the gateway that constructs client data
  subscriptions.
- **Egress (Slice 2, fenced):** connectors publishing to external
  systems.
- **Tier bridges (Slice 3, fenced):** edge→regional→HQ forwarding.

Internal service-to-service traffic inside one tier is not a boundary
for this purpose and is not gated. Gating it would multiply decision
volume for no change in outcome — the data has already been admitted to
that tier.

### 5. Entitlements are asserted, never inferred

Subject entitlements come from a **git-managed `users.yaml`**: a
hand-authored mapping of user → nations (plus the shaped-in `clearance`
field), PR-reviewed, with a named human accountable for every
entitlement.

There is no directory sync and no inference. This is a deliberate
constraint, not a missing feature:

- An inferred entitlement has no accountable author. An asserted one has
  a commit, a reviewer, and a date.
- Directory integration is a per-deployment concern (every program has a
  different identity provider). Baking one in would make the OSS core
  carry an integration most deployments would replace.
- Entitlement changes become reviewable diffs, which is the property an
  accreditor asks for.

Deployments that need IdP integration replace this component. The
contract — Topaz receives subject attributes from an authenticated
identity — is unchanged.

**"No directory sync" is a statement about derivation, not about
transport.** Policy content still has to reach the running authorizer,
and tooling that does so is not a violation of this stance. The
boundary, which OpenDDIL shares verbatim with the co-located reasoning
plane's policy corpus (ADR-0031):

> **Sync tooling transports asserted, PR-reviewed policy content into
> the authorizer; it never derives entitlements from a directory or any
> other source.**

A directory may seed a *draft* entitlement for a human to review. The
PR approval is what makes it an entitlement. That distinction is what
keeps the audit property intact — every entitlement has a named author,
a reviewer, and a date — while still allowing normal deployment
automation.

### 6. DDIL alignment: local authorizers, policy as bundles

The ADR architecture is **one local Topaz authorizer per tier**, with
policy distributed as versioned bundles. Each tier decides locally
against its own copy; a severed link stops *policy updates*, not
*decisions*. Policy is a slow-changing artifact — a tier running
yesterday's bundle through a severance window is a correct and
acceptable posture, and it is auditable because every decision records
the policy version that produced it.

Slice 1 deploys **a single Topaz instance at the HQ tier** because the
read-path gateway it serves is an HQ-tier component. This is a scope
decision, not a revision of the architecture. Per-tier locals land with
the tier-bridge slice, which is the first slice where an edge must
decide during severance.

### 7. Label first, enforce second — never the reverse

The target policy is **deny-unlabeled**: a row with no
`originator_nation` is not releasable to anyone.

Deny-unlabeled is only safe once every row is labelled. Turning it on
against a partially-labelled dataset silently blanks legitimate data,
and the failure mode is indistinguishable from correct enforcement — an
operator sees an empty screen either way.

Therefore a **hard gate** binds this work:

```sql
SELECT count(*) FROM telemetry_latest_state WHERE originator_nation IS NULL;
-- must return 0 before enforcement is enabled
```

Enforcement must not be enabled in any environment until that query
returns zero in that environment. Entities without a derivable national
origin (simulation-sourced entities, synthetic demo assets) receive a
default `originator_nation` from deployment configuration — the same
overlay that owns site topology — so that "unlabelled" means "genuinely
unknown", not "we haven't got to it yet".

#### Constraint on the gate's implementation (added 2026-08-12)

**The gate must enumerate the labelled tables from `information_schema`
at run time. It must never carry a hardcoded list, and in particular
never the migration's scope comment.**

```sql
SELECT table_name FROM information_schema.columns
 WHERE column_name = 'originator_nation';
```

*Why this is a constraint and not a style preference.* Running the check
against the lab on 2026-08-12 found `inventory_items` — named in the
migration's scope list **and** present in `schema.hcl` — **absent from
the deployed schema**. A gate iterating the migration's list would issue
`SELECT … FROM inventory_items` and get:

```
ERROR:  column "originator_nation" does not exist
```

A gate that errors is a gate that did not run, and **an errored gate is
indistinguishable from an unreachable database** — both surface as "the
check failed", both invite a retry, and neither says *"your schema of
record and your deployed schema disagree."* That turns the one
instrument standing between partially-labelled data and enforcement into
a source of ambiguous failures, which is precisely the shape §7 exists
to prevent one layer down.

*The deeper reason:* the gate's question is **"is every labelled row in
this deployment labelled?"** — a question about *this deployment*. A
hardcoded list answers a question about the schema of record instead,
and silently substitutes one for the other.

**Third recorded instance of schema-of-record versus deployed-state
drift**, after the Atlas checksum divergence and chart-version /
bundle-version independence. The three share a standing rule:

> **Ask the running system.** Repository artifacts — migrations, HCL,
> chart defaults, scope comments — describe what *should* be deployed.
> Only the deployment knows what *is*. Any check whose purpose is to
> gate on live state must derive its own inputs from live state,
> including the list of things it intends to check.

*Corollary, and the reason this is worth stating at all:* the drift here
is **benign in isolation** — a table missing two nullable columns breaks
nothing today. It becomes consequential only because a gate depends on
the list. Drift is not dangerous where it occurs; it is dangerous where
something reads the record as if it were the state.

## Slice 1 — read-path releasability

Scope: two users of different nations, on one cluster, see different
fleets, and the difference is fully explained by a decision log.

### Phase 0 — Foundations

Land the proto captures (§3) and the deployment-side label stamping.
These are additive and independently deployable.

**Note on status:** as of this ADR, `originator_nation` /
`releasable_to` / reserved `policy_label` are **not yet in
`telemetry.proto`**. They are a Phase 0 deliverable, not a completed
capture.

**Priority raised 2026-08-07 — this now blocks two downstream design
questions.** The dependency chain, made explicit because the blockage is
not obvious from either end:

```
Phase 0 proto captures
   → labels present on the wire
      → labels present on aggregation inputs
         → label composition for aggregates is designable
```

Arc 1 Phase 1 put the labels on **Postgres tables**, which is what the
read-path filter needs. It did **not** put them on the **wire**, which
is what anything wire-fed needs.
[AUDIT-2026-08-07](AUDIT-2026-08-07-aggregation-composability.md)
confirmed the consequence empirically: *no* aggregation's inputs carry
labels today — `AssetState` has no such fields, and a grep across the
regional aggregator returns nothing.

So Phase 0 is currently the blocking node for:

1. **Label composition for aggregates** (the named design question
   above) — undesignable while the input inventory is empty.
2. **The audit's label inventory** — it can only ever report "none"
   until the captures land.

Neither is urgent on its own; together they mean Phase 0 has more
downstream weight than "additive proto fields" suggests, and it should
be sequenced early within Arc 2's runway rather than treated as
paperwork.

### Phase 1 — Labels queryable (~½ day)

Projector writes `originator_nation` and `releasable_to` as **real
columns** on `telemetry_latest_state` and sibling tables — not buried in
JSONB. Schema-additive Atlas migration.

Real columns because the read-path filter is a `WHERE` clause the
gateway composes; JSONB extraction in a hot filter path is both slower
and harder to express in a subscription filter.

Verify: SQL shows rows carrying parsed nations.

### Phase 2 — Label completeness gate (~½ day)

Entities without derivable national origin get a default
`originator_nation` from the deployment overlay. Then the hard gate in
§7 must pass. No enforcement before it does.

### Phase 3 — Topaz + asserted entitlements (~1 day)

Deploy Topaz (single HQ instance, per §6). Author git-managed
`users.yaml` per §5.

> **DEPLOYMENT GATE RUN 2026-08-09 — the seat is proven.** Topaz was
> deployed to a real cluster (`topazd 0.33.16`, now pinned by digest) and
> **answered 4/4 releasability decisions correctly** against a
> hand-authored local bundle and an asserted-entitlement corpus in the §5
> `users.yaml` shape — including default-deny for a subject absent from the
> corpus. The invocation is `topazd run --config-file <path>` (`-b/--bundle`
> loads local policy roots); `args: ["run"]` alone exits immediately.
> Phase 3 therefore starts from a verified component rather than an
> assumption.
>
> **Two findings carried into this phase:**
>
> **1. Topaz's internal `decision_logger` is not configurable on this
> build, and that does NOT block Phase 5.** Both `plugins` and
> `decision_logger` — documented online and present in the published JSON
> schema — are rejected by 0.33.16 with `'config.Config' has invalid keys`.
> Checked against the co-located reasoning plane (ADR-0031), which runs
> Topaz in production: it is on **0.33.13**, the same generation, and its
> config carries **no decision-logger block either**. So there is no newer
> version to inherit and no solved configuration to copy.
>
> This does not block Phase 5, because **Phase 5's stated mechanism is
> PEP-side**: *"the gateway logs every decision — user, attributes
> considered, policy version, outcome, timestamp."* The gateway records the
> decision it received; Topaz's internal logger would be a second,
> independent record — defence in depth, not the critical path.
>
> **But there is nothing to copy for the PEP side either — Phase 5 builds
> it.** A first version of this note implied the reasoning plane
> demonstrated the PEP-side mechanism. Reading its gateway showed
> otherwise: it logs **failures** (`TOPAZ AUTHZ DENIED …` with user, URN,
> status and body) and returns successful authorizations **silently**.
> There is therefore no per-decision audit record on either side, anywhere,
> today. Phase 5's decision log is new construction, not an integration.
>
> **Named Arc 2 tasks:** (a) build the PEP-side decision record — it is the
> critical path and has no prior art here; (b) revisit Topaz's internal
> logger when its config schema catches up with its own documentation.
>
> *Worth raising with the `dag-tools` side separately, as a **verify-first
> question** rather than a finding:* by this standard its data-access authz
> appears to have no positive-decision audit trail. Read from an installed
> copy, so confirm against that project's source before treating it as
> true. Not a dependency of ours either way.
>
> ---
>
> **AMENDMENT 2026-08-09 — what this note said first, and why it was
> wrong.** Finding 2 originally described the `ALLOW_MOCK_AUTH` fail-open as
> a **live hazard** in the reasoning plane, and attributed the gateway to
> that project. Both were wrong:
>
> - **Tense.** The source was a *comment recording a defect that had already
>   been found and fixed* — its own next lines say the branch "is removed in
>   this same arc". The prose was accurate; the tense was inferred.
> - **Attribution.** The gateway is `dag-tools/central_gateway`, read from
>   an installed package inside the other project's virtualenv. The
>   consuming project's chart references it; the code is not its own.
>
> The report that produced this note also **contained its own refutation**:
> it asserted the fail-open was current *and* quoted the fail-closed
> implementation verbatim from the same file. Those cannot both describe one
> system at one time. Caught by a reviewer who read the report cold, without
> having produced or endorsed it.
>
> Recorded rather than silently amended, because a decision record that
> quietly revises its own history is worth less than one that shows where it
> was wrong — and because the failure mode (a true comment read in the wrong
> tense) is one this project keeps meeting. See PRINCIPLES,
> *"a deliverable's self-description is a claim"* and its tense variant.
>
> **2. Inherited pattern — the PEP must fail CLOSED.** *(Corrected
> 2026-08-09; see the amendment note below for what this said first and
> why it was wrong.)*
>
> **`dag-tools/central_gateway`** — the PEP used by the co-located
> reasoning plane, and a separate component from it — once carried an
> `ALLOW_MOCK_AUTH` branch that converted *every* authorizer exception into
> allow-by-default. For a period, data-access authz was mock-allow while
> appearing to function. **That defect was found and removed in the same arc
> that found it** (`dag-tools 60cf283`), together with the interim it
> served, per ADR-0026's *coupled interim mechanisms retire together*. The
> current posture there is fail-closed with no flag.
>
> Phase 4 inherits this as a design constraint: a PEP that cannot reach its
> PDP must **deny**, and any mock/bypass branch retires the moment the real
> path works.
>
> **The provenance is stronger for being historical, not weaker.** A
> constraint inherited from an open wound is a warning; one inherited from a
> hazard that was found, fixed, and retired *with its interim* is a
> demonstrated pattern with a demonstrated remedy. The lesson is not "beware
> a broken neighbour" but "this failure mode is real, it hides inside a
> system that looks like it works, and here is the shape of the fix."
>
> **Copy the fix's shape verbatim.** Every non-200 and every exception is a
> hard deny carrying a single searchable marker — `TOPAZ AUTHZ DENIED` —
> followed by cause, user, resource and upstream status. An operator facing
> a 403 storm gets one string to grep, and *"authz is broken"* cannot be
> confused with *"authz denied you"*, which is precisely the distinction a
> fail-open erases.
>
> **Their fix is worth copying verbatim in shape.** Every non-200 and every
> exception is a hard deny carrying a single searchable marker —
> `TOPAZ AUTHZ DENIED` — followed by the cause, the user, the resource and
> the upstream status. That gives an operator facing a sudden 403 storm one
> string to grep, and it makes "authz is broken" impossible to confuse with
> "authz denied you", which is the distinction a fail-open erases. Phase 4
> adopts the same marker discipline.
>
> Note the asymmetry this creates and do not repeat it: loud on failure,
> silent on success is exactly the shape that leaves an authorization
> system with no positive audit trail. Phase 5's decision log is what
> closes it.

### Phase 4 — Read-path gateway PEP (~1–2 days)

A thin authenticated component that constructs the client's data
subscription:

```
authenticate user
  → ask Topaz for a decision on that subject
  → filter = originator_nation = ANY(user_nations)
             OR user_nation = ANY(releasable_to)
  → return subscription scoped by that filter
```

**Clients never compose their own subscriptions.** That is the property
that makes the gateway a real PEP rather than a suggestion.

Three questions answered before building, not during:

- **(a) Gateway placement** relative to the current frontend→data-stream
  path — what it fronts, and what stops a client bypassing it.
- **(b) Subscription-filter expressiveness** against array-typed columns
  — verified *before* committing to `releasable_to` as a `text[]`
  column. If array containment isn't expressible in the filter grammar,
  the column shape changes (join table, or denormalized membership) and
  it is much cheaper to learn that now.

  **PARTIALLY RETIRED 2026-08-07 — do not redo the Postgres half.** Arc 1
  Phase 1 verification executed the exact filter shape against the real
  column types on a live Postgres:

  ```sql
  SELECT count(*) FROM telemetry_latest_state
   WHERE originator_nation = ANY(ARRAY['NAT_A'])
      OR 'NAT_A' = ANY(releasable_to);
  ```

  It runs, and `text[]` containment is expressible and indexed (GIN).
  So the *column shape* is validated at the database layer.

  **What remains open** is the narrower question: whether the
  **subscription/shape filter grammar** the gateway composes into can
  express array containment, which is a property of that layer, not of
  Postgres. If it cannot, the resolution is a projected boolean or a
  membership join *for the subscription path only* — the underlying
  column stays as validated.
- **(c) Cheapest stable demo identity** — identity, not SSO. Enough to
  distinguish two users reproducibly.

### Phase 5 — Demonstration + decision provenance (~½ day)

Two users, different nations, same cluster → different visible fleets.

The gateway logs **every decision**: user, attributes considered, policy
version, outcome, timestamp.

Verification is falsifiable and specific: *the difference between the
two screens is fully explained by the decision log.* Not "access control
works" — the delta is accounted for, row class by row class.

## Fenced — tracked, not built

Named so they are decisions rather than omissions:

- **Releasability label composition for aggregates** *(named design
  question, added 2026-08-07 — deferred, not designed).* The Arc 1
  Phase 1 migration deliberately excluded the `region_*` rollup tables,
  because **what an aggregate is releasable to has no default answer**.
  A rollup over assets from three nations is releasable to the
  *intersection* of their `releasable_to` sets? The *union*? Neither is
  automatically right.

  Worse, neither captures the real concern. This is the classic
  **aggregation-sensitivity** problem: composition can *change*
  sensitivity, and an aggregate of individually-releasable facts can be
  *less* releasable than any component, because the pattern reveals more
  than the parts do. A count of degraded assets per nation may be
  releasable per-nation and disclosive in aggregate.

  Two connections make this more than a labelling detail:

  1. **Label composition is itself an aggregation-composability
     property** — the same class of question as
     [AUDIT-2026-08-07](AUDIT-2026-08-07-aggregation-composability.md).
     Union and intersection rules are distributive (they compose like
     counts); the aggregation-sensitivity concern is *not* expressible
     as either, and resembles the non-composable top-N case: information
     that cannot be recovered from the emitted artifact alone.
  2. **The input inventory is currently empty.** That audit's label
     column found that *no* aggregation's inputs carry labels today —
     the labels landed on Postgres tables while the proto `Provenance`
     additions remain a Phase 0 deliverable. Any composition design must
     account for all three aggregation inputs arriving unlabelled.

  Belongs to Slice 2/3. Do not design it before labels are on the wire.

- **Slice 2 — egress gating.** Releasability enforcement on outbound
  connectors.
- **Slice 3 — tier-bridge decisions.** Enforcement on edge→regional→HQ
  forwarding; this is the slice that requires per-tier local
  authorizers.
- **Classification-axis demonstration.** Policy is shaped for it; no
  demonstration in Slice 1.
- **Frontend role-view rework.** Role views consume the filtered stream;
  reworking them is presentation work, not enforcement work.

## Consequences

### Positive

- Two operators on one cluster provably see different fleets, decided by
  data attributes rather than by which screen they opened.
- Enforcement survives severance by construction (local decisions,
  policy as bundles) rather than by exception handling.
- Single-PDP discipline means "why did this user see this row?" has
  exactly one answer, in one decision log, with a policy version.
- Classification can be added as a rule + column rather than a redesign.
- Asserted entitlements produce an audit trail an accreditor can read:
  every entitlement is a reviewed commit.

### Negative

- The gateway is a new component in the read path — one more hop, and a
  new availability dependency for clients.
- Asserted entitlements do not scale to large user populations. This is
  acceptable for the deployments in scope and is the explicit trade
  against unaccountable inference; large deployments replace the
  component.
- Real columns on `telemetry_latest_state` mean a schema migration and a
  projector change per labelled table.
- Slice 1's single HQ Topaz is not the target architecture. There is a
  real risk of it being mistaken for the finished state; §6 exists to
  prevent that.

### Neutral / acknowledged

- Labels are only as good as what the adapter can derive. A deployment
  whose identifiers don't encode national origin needs a real mapping
  source; the default-from-config path keeps such deployments
  *labelled*, not *correct*. Config-defaulted labels are honest about
  being defaults.
- OpenDDIL adopts STANAG 4774/4778 label *concepts*; it does not
  implement the standards. Programs requiring conformance use the
  reserved `policy_label` slot.
- Deny-unlabeled means a labelling regression blanks data rather than
  leaking it. That is the correct direction to fail, and it makes the
  Phase 2 gate load-bearing forever, not just at rollout.

## Slice 1 status — executed 2026-09-05 on `edgy-lab`

**Every line below was verified by running it against the lab. Nothing here
is inferred from source.** The cluster is named because a claim about
authorization is a claim about one deployment (EXCHANGE-LEDGER X-7).

| Phase | Status | Evidence |
|---|---|---|
| **P0** proto captures | **DONE** | `originator_nation`=9, `releasable_to`=10, `reserved 11` on `Provenance`. Acceptance is the conformance stage, not the diff: `tests/bloblang/run.sh` encodes every case through the real ingress's `protobuf from_json`. Red-checked by dropping the capture — goldens stay 11/11 green, conformance goes 0/11 red |
| **P1** labels queryable | **DONE** | Stamped at DIS ingress from a declared overlay; carried by the projector onto all five tables; propagated by fusion, cm-service and the prognostics derivation |
| **P2** completeness gate | **PASSES** | 3 populated tables, 14 rows each, **zero** unlabelled on either column. 2 tables empty and reported as proving nothing |
| **P3** Topaz + entitlements | **DONE** | One HQ Topaz on a local bundle; `users.yaml` asserted, 3 subjects, PR-reviewable |
| **P4** gateway PEP | **DONE** | Fronts Electric's shape endpoint; owns the where-clause; fail-closed proven by scaling the PDP to zero |
| **P5** decision log | **DONE** | Every decision, allow and deny, with subject, allowed nations, policy version, predicate, shape handle and timestamp |

**Demo result, `demos/releasability-partition.sh`: 13 passed, 0 failed.**
user-a 8 assets, user-b 6, disjoint, liaison 14, unlisted subject 403,
anonymous 403, and a client where-clause asking for the other nation's rows
narrowed to 0 against a control of 6.

### Open question (b) is ANSWERED, affirmatively

*"Whether the subscription filter grammar can express array containment"* —
**it can.** Verified against live Electric: `releasable_to && ARRAY['BDR']::text[]`
is accepted and, with one row seeded, returns exactly that row alongside the
nation clause. `text[]` stands and needs no reshaping.

Worth noting how nearly this was mis-answered. The first run returned **zero
rows and HTTP 200**, which is indistinguishable from "the operator was parsed
and ignored" — because every demo asset declares `releasable_to: []`. Seeding
a single row is what turned a vacuous zero into a positive result.

### The propagation graph had more producers in it than this ADR named

§3 says labels are stamped at ingress and carried. In practice **four**
components had to be changed to carry them, and the fourth was found only by
running the pipeline:

1. the ingress mapping (stamps),
2. the projector (writes the columns),
3. cm-service and fusion (derived rows),
4. **the prognostics derivation** — which nothing had named, and which is
   fusion's highest-volume inbound path.

With the first three done, two tables went fully labelled and
`asset_logistics_status` stayed at **zero**. Nothing errored. Fusion never
receives `raw-sensor-stream` at all; its inbound handlers are
`derived-sustainment`, `asset-cm-state` and `asset-capability-snapshot`.

The mechanism appeared **three times in one night**, and is worth naming as
one shape: *a message rebuilt field by field drops everything not explicitly
listed, silently.* The prognostics agent's provenance copy, cm-service's
`_dict_to_record`, and cm-service's `_recompute` preservation block are the
three. In every case the loss is invisible at the seam — the consumer sees a
message with no label and cannot tell *"the source had none"* from *"a hop
lost it."*

### Scope — what "PEP live" does NOT mean

**This covers the USER READ PATH and nothing else.** Stated here because a
reader will otherwise take "enforcement is live" for "all data paths
enforced", and the two differ by the half that matters most in a shared
fabric.

- **Internal service reads** — fusion into edge brokers, Restate
  subscriptions, the projector — are out of scope **by design** (§4): the
  data has already been admitted to that tier.
- **Egress is Slice 2 and is enforced by nothing here.** Connectors
  publishing outward, tier bridges forwarding upward, peer links forwarding
  laterally: all unguarded today.

These are not two implementations of one gate. They are **two gates against
two different adversaries**, and neither is sufficient alone:

| | read gate (Slice 1) | egress gate (Slice 2) |
|---|---|---|
| protects against | the wrong **person** | the wrong **destination** |
| enforcement subject | a subject | a link |
| cadence | per shape (cheap, cacheable) | per message or per bridge |
| placement | reverse proxy at the read surface | the bridge / connector boundary |
| failure mode | a human sees a screen they should not | a system durably **holds** data it should not |

The egress failure is worse in two ways: it is **durable** (the receiving
system now has it) and there is **no human in the loop to notice**. Sharing
the policy engine is what keeps the two from drifting into two truths;
separating the enforcement points is what makes each complete for its own
threat.

Three things follow for Slice 2, recorded now while they are cheap:

1. **The seams already exist.** Every hop out of a tier is a bridge
   (edge→HQ), a peer link (ADR-0033), or a connector. Three chokepoints, all
   already architectural objects carrying echelon context (ADR-0022 §4). The
   egress PEP is a policy decision inserted into plumbing that exists, not
   new plumbing.
2. **Deny-unlabeled matters more there than here.** At the read surface an
   unlabelled row rendering is a leak you revoke by fixing a screen. At
   egress, an unlabelled message crossing to a partner's system is a leak
   that has *happened*. The completeness gate is a harder precondition for
   Slice 2 than it was for Slice 1.
3. **Per-message Topaz calls will not scale, and the fix is a compile step,
   not a cache.** A bridge carrying a mixed-nation topic to a single-nation
   parent must decide per message or partition the stream. That is naturally
   a predicate applied AT the bridge (Bloblang / Connect-level, keyed on the
   label) — the same policy source compiled to a different enforcement form.
   Worth designing before Slice 2 starts, because "call Topaz per Kafka
   message" is the naive version and it does not work.

### Severance — what was and was not shown

With `hq-link` severed via toxiproxy, the partition **held: 13/13**.

**What that proves:** the authorization decision path has no dependency on
the inter-tier link. The PEP asks the tier's own Topaz against the tier's own
bundle, and every component in that path is tier-local.

**What it did NOT prove, and must not be reported as:** that an *edge*
decides during severance. Slice 1 deployed **one** Topaz, at HQ (§6).

**PARTLY DISCHARGED 2026-09-05** — see §Per-tier PDP. Each tier's PEP now
decides against that tier's own authorizer, against a policy bundle and
corpus distributed to it, so an edge does decide for itself. Taken as its
own increment ahead of the tier-bridge slice because it was fixing a
regression rather than adding a feature.

**Still not proven on hardware:** the lab runs `tierNode.enabled: false`,
so this is verified by render and by reasoning, not by a severed tier. The
capstone remains a recording nobody has made. What HAS changed is that it
is now possible to make honestly.

### Two defects worth keeping, both found by asking the running system

**The decision rule was undefined for exactly the case it exists to deny.**
`subject_record` is undefined for a subject absent from the corpus — correct
Rego for absence — but `decision` was an object literal containing
`subject_record != null`, and an expression over an undefined value is
undefined, which made the whole object undefined. Topaz answered
`{"response":{"result":[]}}`, and the gateway, unable to read a decision,
reported the PDP as **unavailable**. Fail-closed either way, so the user was
still refused; but the audit trail recorded an **outage** where the truth was
an **unlisted subject**. Those call for different responses. Every field of
`decision` now has an explicit default, and that totality is precisely the
property that lets a PEP tell a deny from a broken PDP.

**The bundle never rebuilt for the policy.** The notify workflow's path
filter and the bundle Dockerfile's COPY list are two copies of one fact, in
two repositories, with nothing enforcing their agreement. `policy/` and
`gateway/` were added to the bundle and not to the filter, so the edit
committed, CI went green, the pod restarted, and **the old policy kept
running** — with no error anywhere in the sequence. An authorization
component silently running last week's policy is the worst instance of this
available, and it did not present as a stale artifact; it presented as the
PDP rejecting every request.

### Authentication — Keycloak, and why the browser holds no token

*(Added 2026-09-05. Slice 1 shipped with a trusted-header subject; this is
the decision that replaced it.)*

**Keycloak answers *who is this*. Topaz answers *what may they see*.** The one
value crossing that seam is a stable subject id, used as the join key into
the git-asserted entitlements corpus. Keycloak may perfectly well carry group
or role claims; nothing reads them, and nothing should start to — a
deployment with entitlements in two places has two truths to keep in sync and
no way to tell which one an operator's screen reflected.

#### Backend-for-frontend, not the SPA pattern

The gateway is a **confidential** OIDC client. It runs the authorization-code
flow server-side and hands the browser an httpOnly, SameSite session cookie;
tokens never reach JavaScript. An XSS in the frontend can ride a live session
but cannot exfiltrate a credential, which is a strictly smaller blast radius
than a page that holds its own tokens.

This is a deliberate divergence from the co-located reasoning plane
(ADR-0031), whose realm and gateway were **read before deciding** rather than
assumed. Recorded in full because "how hardened is that?" deserves specifics,
and because a vague worry attached to a sibling project is worse than an
accurate one:

**Its browser flow is authorization CODE, not implicit.** That part of the
concern was unfounded and is worth saying plainly.

**Inherited, because it is right:**

- `PyJWKClient` with a cached JWKS — the primitive that makes
  severance-tolerant validation possible at all;
- `algorithms=["RS256"]` **pinned**, which closes algorithm confusion and the
  `alg: none` family;
- authorization identity kept separate from `email`, with email treated as
  display/audit only and permitted to be absent;
- **Topaz as the sole source of entitlements**, with no JWT-claim reads left.
  That is the same seam this ADR keeps, and it is the strongest thing in
  their implementation.

**Declined, deliberately:**

| Their setting | Why not here |
|---|---|
| `options={"verify_aud": False}` | The realm also holds **service clients**. Without an audience check, a token minted for any of them is accepted by the user-facing gateway. |
| no `issuer=` on decode | A token from another realm, signed by a key this process trusts, would pass. |
| `publicClient: true` for the UI | Puts tokens in the browser — the thing this design exists to avoid. |
| `redirectUris: ["*"]` | A wildcard redirect is how an authorization code is delivered somewhere other than the gateway that asked for it. |
| `directAccessGrantsEnabled: true` on the UI client | The resource-owner password grant, which OAuth 2.1 removes, sitting beside the browser flow as a second way in. |
| no PKCE enforcement | A public client's intercepted code can be redeemed without a verifier. |

None of that is a criticism of their shipped state — their gateway is a
bearer-token API, where the SPA pattern is conventional. It is a record of
which parts were copied and which were not, so neither answer has to be
re-derived. **If this BFF proves out, the pattern is available to flow back
the other way.**

#### Signature verification is written out, and therefore tested hard

The PEP runs stdlib-only in a stock python image (see the bundle Dockerfile:
a component whose job is to *refuse* requests must not have a dependency that
can fail to install). So RS256 verification is implemented rather than
imported. That trade is only defensible if it is exercised against bad
tokens, so it is: **16 tests, every negative case a token a lax verifier
would accept** — tampered payload, wrong audience, wrong issuer, expired,
`alg: none`, and HS256 signed with the RSA public key (assembled by hand,
because PyJWT refuses to *mint* that one).

Red-checked by mutating the verifier to match the sibling's posture: exactly
the audience and issuer tests fail, and only those two.

#### Two auth modes, chosen at boot — and why that is not `ALLOW_MOCK_AUTH`

`oidc` and `header` are selected before the first request and are mutually
exclusive. In `oidc` mode the trusted header is **never read**.

The constraint this ADR inherited from `dag-tools` was about a branch **inside
the real path** that converted an authorizer exception into allow-by-default
— a request could take the bypass at runtime without anyone choosing it.
Here there is no input a caller can supply that selects the other mode, and
no failure that degrades into it: a half-configured OIDC **refuses to start**,
because a gateway that silently fell back would be a fail-open wearing a
configuration error as a disguise. Every decision record names the mode that
produced its subject, so the audit trail can never be ambiguous about which
was live.

#### The subject is `sub`

Never `email`, never `preferred_username`. Both are mutable and re-assignable
in an identity provider: an address freed by one person and later handed to
another would **silently inherit the first person's entitlements**, and
nothing in the corpus would look wrong — the row would still name a plausible
principal. `sub` is opaque and stable, so a re-issued username produces a
subject nobody has entitled, which fails closed.

The cost is readability, paid two ways: the demo realm **pins its user ids**
so the corpus stays greppable across re-imports, and every row carries
`username` and `display_name` for the human reading the diff. Those two
fields are documentation; nothing reads them.

*Unpinned ids are not a cosmetic problem.* Every realm re-import would issue
fresh UUIDs, orphaning every entitlement — each user authenticating
successfully and then being denied everything, which looks exactly like a
policy bug and is not one.

#### Two versions in every decision, not one

`policy_version` versions the **rules**; `corpus_version` versions the
**entitlements**. They move on completely different cadences — a promotion
changes one list in one file and touches no rule — so a record carrying only
the first cannot answer *"which entitlements were in force when this person
was allowed?"*, which is the question an accreditor asks.

Found by rehearsing the promotion beat and watching `policy_version`
correctly **not** change.

#### DDIL: what survives a severed link, and what does not

Authentication has the same locality problem authorization does, and Slice 1
answers it the same way — honestly, and not yet.

- **Existing sessions survive.** Validation is against a locally cached JWKS
  and a local session table; neither needs the identity provider. The JWKS
  cache refreshes **only on an unknown key id**, never on a timer — a timer
  would turn an unreachable IdP into an outage for sessions that were already
  validated, which is precisely the behaviour this is trying to avoid.
- **New logins do not.** The code exchange is a live call to the token
  endpoint. A severed tier cannot mint a session.
- **Session lifetime is therefore a DDIL parameter, not a security
  constant**: long enough to outlast a plausible severance window, short
  enough to bound a stolen cookie. It is a chart value for exactly that
  reason.

**Per-tier identity rides the same seam as per-tier Topaz** — a Keycloak
replica or a local IdP — and lands with the tier-bridge slice. They are one
passenger, not two, and should be designed together.

#### Operational notes worth keeping

- **`SameSite=Lax`, and that is a considered choice.** `Strict` is the
  instinctive answer and it breaks the login round trip when the IdP is on a
  different *site*: the post-callback navigation is attributed to the
  cross-site initiator, the cookie is withheld, and the user lands logged out
  — intermittent, and indistinguishable from a flaky login. The bundled
  Keycloak is served under the app's own host, so the two are same-site and
  `Strict` is available to a deployment that wants it.
- **The identity provider has two addresses and they are not
  interchangeable.** The browser arrives through the ingress; the gateway
  goes straight to the Service. Conflating them fails in two shapes that both
  look like something else — an internal issuer the browser can never reach,
  or a pod hairpinning through its own ingress, which *sometimes* works and
  therefore sometimes stops. `iss` is validated against the configured public
  issuer; server-side calls are rewritten onto the internal base.
- **Keycloak was OOMKilled at 1Gi and again at 2Gi.** Raising the limit alone
  does not help: the JVM sizes its heap as a percentage of the limit it is
  given, so a larger limit produces a proportionally larger heap and the same
  overshoot. An absolute heap cap plus headroom is the fix. The symptom is a
  CrashLoopBackOff whose container log ends mid-startup **with no error** —
  the kill happens outside the JVM, so there is no `OutOfMemoryError` to
  print, and the diagnosis lives in the pod's `lastState`, which is not where
  anyone looks first.

### Per-tier PDP — the enforcement point stops being a severance hazard

*(2026-09-05. Taken as its own increment ahead of the tier-bridge slice,
because it stands alone and because it was fixing a regression.)*

**The regression, stated as a regression.** Slice 1's per-tier PEP enforced
locally and decided against the **root's** Topaz. That was recorded at the
time as *"enforce locally, decide remotely — correct, and not the
capstone"*, which was accurate and understated the consequence by a wide
margin. The consequence is:

> Sever the tier's uplink and the PEP cannot reach its PDP. It fails closed
> — correctly, loudly, with the marker — and **the maintainer UI at a
> severed edge shows DENIED instead of data.**

That is **ADR-0036 clause 4 violated by the enforcement point**: severance
turned from a degraded mode into an outage. And it did not merely fail to
deliver Arc 2's capstone — **it regressed a capability that already
worked.** Phase 5 rung (iii), *"the tier UI live while severed"*, is Arc 1's
proof artifact, and with enforcement enabled it could no longer be
demonstrated, because the enforcement was the thing going dark.

*Worth keeping as a shape:* **a fail-closed component placed across a link
that is expected to fail converts a designed degraded mode into an
outage.** Fail-closed is right; where it sits is the decision. The PEP
belongs at the tier — it always did — but so does the thing it asks.

**The fix, and why it was smaller than the slice it belongs to.** Per-tier
Topaz pods already existed: `tier-topaz-<id>` shipped as a **reserved seat**
in Phase 3, running healthy against an *empty bundle* — deployed, serving,
and deciding nothing, which was honest and was precisely the argument for
shipping the seat early. Two things were missing:

1. **each tier's PEP pointed at its own authorizer** rather than the root's;
2. **policy and the entitlements corpus distributed to each tier**, which is
   the distribution seam's first real passenger.

The corpus rides the runtime bundle, pulled at pod start — ADR-0029 §6's
model without adding a mechanism: *policy distributed as versioned bundles,
each tier deciding against its own copy, a severed link stopping policy
UPDATES rather than decisions.* A tier running yesterday's bundle through a
severance window is a correct posture, and it is auditable because every
decision records the policy and corpus versions that produced it.

**What fail-closed now means.** With the tier's own PDP, a refusal caused by
an unreachable authorizer means *"my own decision point is down"* — a real,
local fault worth paging about. Before, the identical refusal meant *"the
link is cut"*, which is a condition this system exists to survive. Same
marker, same status code, opposite operational meaning; that is the
distinction the change buys.

**The completeness gate follows the stores.** §7's question is *"is every
labelled row in THIS deployment labelled?"*, and once tiers decide locally
against their own data, "this deployment" stops being one place. Enabling
enforcement at a tier is a decision about **that** store, and a pass at the
root says nothing about it — the same error §7 already refuses one level up
(a result about one cluster restated as a claim about another), now
available one level down inside a single cluster. `--tier <id>` gates one;
`--all-tiers` discovers the stores from the running cluster and fails if any
of them does. Over zero tier stores it says so rather than reporting a pass
that reads as a claim about tiers.

**What this still does NOT do.** Keycloak remains at the root, so a severed
tier keeps existing sessions (cached JWKS, local session table) and cannot
mint new ones. Per-tier identity rides the tier-bridge slice alongside the
rest of it. The honest sentence for a severed edge is therefore: *decides
locally, enforces locally, and cannot log anybody new in.*

### Carried forward

- **Multi-replica PEP needs shared shape-handle storage.** Bindings are
  in-memory, so a second replica refuses valid resumptions. It fails closed,
  which is the right direction, but the chart runs one replica and says so
  rather than pretending the component is stateless.
- **`asset_capability_state` and `asset_element_telemetry` are empty on this
  lab**, so their zero proves nothing. logistics-sim is idle; the projector
  half of its labelling is wired, its producer half is untested.
- **Topaz's own decision logger remains unconfigurable** on 0.33.16. The
  gateway record is the audit trail, not defence in depth alongside a second
  independent one.
- ~~**Demo identity is a header.**~~ **RESOLVED 2026-09-05** — replaced by a
  Keycloak backend-for-frontend; see the authentication section above. The
  header mode remains, selected at boot, for the headless suite and for a
  gateway reachable only in-cluster. The prediction held: the contract Topaz
  sees did not change, only what establishes the subject.
- **A browser-readable decision feed was deliberately NOT built.** The demo
  wants a pane showing every subject's decisions side by side; serving that
  to a browser would create a new read surface with its own releasability
  question, and inventing one to make a demo pane work is the wrong
  instinct — it is the shape of the problem this whole arc exists to fix.
  The pane stays a terminal tail of the gateway's log. A per-subject
  endpoint (a user asking *"why can't I see X?"* about their OWN decisions)
  is safe and worth building; a global one is a Slice-2-sized question.

## Related

- ADR-0021 — the edge→HQ topology is load-bearing (why decisions must be
  local).
- ADR-0022 / ADR-0023 — hierarchical aggregation; provenance stamped at
  the earliest knowing tier (the discipline labels inherit).
- ADR-0025 — build-pass deployment verification (enforcement must be
  verified live, not just in tests).
- ADR-0031 — converged edge node; the co-located reasoning plane shares
  this ADR's policy engine rather than introducing a second authorization
  truth.
