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
