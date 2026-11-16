# ADR-0061 — Cross-domain readiness: labels aligned to STANAG 4774, closed outbound kinds, one-way routes, a binding designed

## Status

**PROPOSED — 2026-11-16. Design only. Nothing here is built.** Ordered 2026-11-16 by the project owner, with the seven
decisions below named in the order.
**Builds on:** ADR-0055 (a label is a set of declared dimensions; §6, alignment by concept name; §7, the accreditation
boundary); ADR-0046 (destinations, routes and kinds); ADR-0029 (the releasability label); ADR-0060 (opaque ids in
spans and logs).
**Folds into ADR-0055:** the two label rules (Decisions 1 and 2) are written as ADR-0055 §2b on the `lk2` proposal
branch (PR #38), so that they are ruled with the key form, not after it.
**Read at:** working trees of 2026-11-16. Line numbers move with them. These are reads, not runs.
**Reviewed 2026-11-16:**
- Decision 3 is corrected to a staged rollout: report mode first, then enforcement per kind by declaration.
- The choices made inside the seven decisions are accepted.
- The six open questions have proposed answers (Proposed answers, below). They are not ruled.

## Sources, and how much of each was read

| Source | What it is | Read |
|---|---|---|
| ADatP-4774 (STANAG 4774), confidentiality metadata label syntax | the standard | **Unread.** No edition was obtained |
| ADatP-4778 (STANAG 4778), metadata binding mechanism | the standard | **Unread.** No edition was obtained |
| Isode, "Isode Approach to Data Centric Security using NATO Confidentiality Labels", white paper, 13 pages | **Secondary: a vendor's paper.** It describes the standards and the vendor's products | Read in full. Fetched 2026-11-16 from `https://www.isode.com/wp-content/uploads/2023/08/Isode-Approach-to-Data-Centric-Security-using-NATO-Confidentiality-Labels.pdf`. The PDF's metadata gives a creation date of 2026-07-27 |
| IANA media type registration, `application/vnd.nato.bindingdataobject+xml` | **A registry record**, not the standard. Registered 2023-11-27; change controller the NATO Standardization Office | Read in full |
| RFC 8141 (URNs), RFC 3061 (the `urn:oid:` namespace), RFC 8785 (JSON canonicalization), RFC 7515 (JWS) | IETF standards | Cited for their names and scope only. Nothing here depends on a clause of them yet |

Every statement below about what STANAG 4774 or 4778 contains comes from the white paper or the registry record, and
is marked **(secondary)** or **(registry)**. None is a reading of the standard. Each is checked against the standard
before any field freezes (Owed).

## Findings first

### What the secondary sources say

1. **A 4774 label carries a policy identifier, a classification, categories, and lifecycle times** (secondary). The
   paper's example label (p.2-3) has `PolicyIdentifier URI="urn:oid:1.3.6.1.4.1.31778.102.25"` with a short name, a
   `Classification`, a `Category` with `Type="PERMISSIVE"` and a `TagName`, a `CreationDateTime`, and a
   `ReviewDateTime` attribute on the label.
2. **Lifecycle is part of the label, and is called a key feature.** "The label contains label lifecycle information
   (creation data and review date), which is a key feature of STANAG 4774" (p.3, secondary).
3. **The policy is identified by an object identifier and a string.** "The security policy, which defines label
   structure, is identified by an object identifier (globally unique reference) and a string" (p.3, secondary). The
   example writes the identifier as a `urn:oid:` URI.
4. **XML is one encoding of several.** "This label is XML-encoded, noting that STANAG 4774 supports other encodings,
   including JSON and CBOR" (p.3, secondary).
5. **Labels are checked against clearances, never against labels.** "It is not possible to compare labels against
   labels" (p.3, secondary).
6. **4778 binds labels to data, possibly to parts of it.** It "specifies generic mechanisms, with specific bindings for
   a number of data formats and protocols", and "allows association of multiple labels with data and can associate
   labels with different parts of the information" (p.3, secondary).
7. **4778's cryptographic binding is optional.** It "provides an option for cryptographic binding using digital
   signature mechanisms", which validates "That a valid label is provided", "That the label is correctly associated
   with the data" and "That the data has not been modified since the label binding" (p.4, secondary). The registry
   record says the binding data object "contains an optional XML digital signature element to provide integrity and
   authentication services, that may be used if required" (registry).
8. **At a domain boundary, a guard validates one way, against declared formats and exact labels.** The paper's guard
   "provides secure unidirectional validation of XML messages, suitable for use across a domain boundary", under an
   application profile that "specifies XML message formats and checking rules", with "STANAG 4774 label checking,
   using exact match of allowed labels" (p.9, secondary).
9. **Each domain usually has its own policy, so labels are converted at the boundary.** "Typically different security
   policies will be used in each domain" (p.9); label transformation, "mapping to a different security policy… is often
   important in conjunction with cross domain" (p.5, secondary).

### What this framework has today

10. **ADR-0055 §6 already aligns by concept:** declared policy to policy identifier, hierarchical to classification,
    permissive and restrictive sets to categories, and the stamped label to 4778's binding "as a concept only".
    `label_key` is a digest of the canonical form, not a cryptographic binding (ADR-0055 §2, §6).
11. **The label has no lifecycle times,** and the policy id is any string matching
    `^[a-z0-9][a-z0-9:._-]{0,62}$` (`DESIGN-2026-11-06-adr0055-compatibility-slice.md` §1.1). Nothing requires it to be
    a URN.
12. **A kind is a JSON Schema document in the overlay** (ADR-0046 §3). Nothing requires a kind to be closed, and
    nothing marks a field as free text. The gate refuses a record that fails its kind's schema as `schema_invalid`
    (ADR-0046 §2).
13. **Every egress route expects an answer.** The forwarder's outcomes are `held`, `delivered` and `failed`
    (`DESIGN-2026-11-10-adr0058-first-increment.md`, finding 2). A destination may declare `intake`, which polls it or
    receives callbacks from it (ADR-0046 §1, §5). There is no route that cannot answer, and no record of what was sent
    that does not depend on an answer.
14. **Free text reaches records in several places** (the flags table below). The maintenance action's
    `work_order.task` is one (ADR-0046 §3; ADR-0052:104).

## Decision

### 1. Label lifecycle fields ride outside `label_key`

Written as ADR-0055 §2b (PR #38). In short:
- `created` and `review` ride in the label body under `life`, beside `dims`. Times are RFC 3339, in UTC.
- They never enter the canonical form or the key. Two labels that differ only in `life` give one key, so a record's
  age mints no new key, admitted set or shape.
- The label table holds no `life`, and the PDP never reads it. A past review time is counted and reported, never a
  refusal.
- `life` is optional and never defaulted. An undeclared member or a bad time is refused at the stamp.

Basis: findings 1 and 2 (secondary).

### 2. Policy ids are URNs; an OID is written in its `urn:oid:` form

Written as ADR-0055 §2b (PR #38). In short:
- A policy id is a URN (RFC 8141). A policy identified by an object identifier is written `urn:oid:<dotted decimal>`
  (RFC 3061).
- The id still matches the slice's pattern, so it is lowercase and at most 63 characters.
- A non-URN id is refused when declared. An existing one changes only by re-declaration, through the slice's backfill,
  because the id is in the canonical form.
- The policy's short name is not part of the id or key.

Basis: findings 1 and 3 (secondary). The order allowed "OID or URN". A URN admits both, with one syntax to check.

### 3. Outbound kinds are closed, and free text is declared

Applies to every kind that a destination `accepts` (ADR-0046 §1), whether or not it is cross-domain.
- **Closed.** Every object in the schema sets `additionalProperties: false`. A record with a field its kind does not
  declare already fails validation, so the gate refuses it as `schema_invalid` (ADR-0046 §2). No new reason is needed.
- **Every string is bounded or declared free text.** A string property is bounded when it has an `enum`, a `const`, a
  `pattern`, or a `format` from a declared list (`date-time`, `date`, `uuid` to begin with). Any other string must
  carry `x-free-text: true` and a `maxLength`.
- **Every array declares `maxItems`** (proposed answer 4), on the same reasoning as a bounded string.
- `maxLength` alone does not make a string bounded. A long string with no pattern is free text and must say so.

**Rolled out in stages: report mode first, then enforcement per kind by declaration** (review, 2026-11-16).
Enforcing all of this at once would refuse a deployment's own records on the next roll, the moment a producer sent
a field nobody had declared. So each kind is in one of two modes, declared in its schema as `x-closure`.
- **`report`.** This is the default, and an absent or unknown value is `report`.
  - The kind loads, and its records are validated and admitted exactly as today.
  - The load check names every failing pointer: an open object, an undeclared unbounded string, an array with no
    `maxItems`.
  - The gate also validates each record against the closed form, and counts the records that form would refuse, per
    kind and per failing pointer. It refuses none of them.
  - The pointer named is the schema's (the object or property that would refuse), never an undeclared field's own
    name. That name comes from the record, so it is content (ADR-0060).
- **`enforce`.** The closed form is the kind's schema.
  - A failing kind is refused at load, with the kind and the pointer named. A refused kind is not loaded, and routes
    that carry it do not start.
  - A record that fails is refused as `schema_invalid` (ADR-0046 §2). No new reason is needed.
- **A kind moves to `enforce` only by declaration, once its report is clean.**
  - A clean report has no failing pointer at load, and no record counted as would-be-refused.
  - An `enforce` declaration on a kind whose load report still names a pointer is refused at load. The record count
    is the evidence the declaring person reads. The load cannot check it.
  - Nothing switches a kind to `enforce` by itself, and nothing switches one back.
- **An eligible kind (Decision 4) must be in `enforce`.** One in `report` is refused at load. A one-way route
  (Decision 5) therefore carries only enforced kinds.

Basis: finding 8 (a guard checks declared message formats, secondary) and finding 12.

### 4. A kind may be declared cross-domain eligible, and an eligible kind has no free text

- A kind declares `x-cross-domain: eligible` in its schema. The default is not eligible. An absent or misspelt value
  is not eligible.
- **An eligible kind has no free-text field.** An eligible kind with any `x-free-text` property, at any depth, is
  refused at load. A deployment that needs a record to cross declares a second kind without the free text and
  projects into it.
- An eligible kind must also pass Decision 3. Eligibility is a stricter closure, never a looser one.
- **Eligible is not accredited.** It says the kind's shape can be checked by a guard: closed, bounded, labelled. It
  says nothing about whether the far domain may hold the data. That is an accreditation decision, outside the system
  (ADR-0055 §7). The boundary device's own rules decide what crosses.

Basis: finding 8 (secondary). Free text is what a format check cannot judge.

### 5. One-way egress routes, with a `handed_off` outcome and manifest records

**A destination can be one-way.**
- A destination entry (ADR-0046 §1) may set `one_way: true`. Every route to it is one-way.
- A one-way destination may not declare `intake` or `trust_on_behalf_of`. Either is refused at load, because nothing
  comes back.
- Its transport is a `topic`: the hand-off is the write to a topic that the boundary device reads. An `http` transport
  is refused for a one-way destination, because HTTP needs an answer. A file drop directory is the next candidate (proposed answer 5).

**Only eligible kinds travel one way.**
- A route that carries a kind that is not eligible (Decision 4) to a one-way destination is refused at route load,
  with the route and the kind named.
- The gate also checks each record and refuses it with a new reason, `kind_not_eligible`. That reason cannot fire
  while the load check holds. It is there so a load check that is later bypassed fails closed.

**The outcome is `handed_off`, never `delivered`.**
- A record written to a one-way destination's sink is recorded with the outcome `handed_off`, where `held`,
  `delivered` and `failed` are recorded today.
- `handed_off` means the sending tier's write was acknowledged by its own broker. It says nothing about the far side.
- There is no answer to wait for, so a missing answer is never retried. A failed write before the hand-off is
  retried as today, up to `held`. A retry can send a record twice, and the far side deduplicates by the kind's `key`.
- There is no case id. A screen that shows a case link shows `handed_off` instead, with no link.

**Every batch on a one-way route is followed by a manifest.**
- A manifest is a record of a declared kind, `EgressManifest`, which is eligible and closed. It is sent on the same
  route, after the records it lists.
- It lists, for one route and one batch:
  - the route and the destination;
  - the manifest's sequence number on that route, and the SHA-256 digest of the previous manifest, so the far side can
    see a gap without asking;
  - the batch's first and last record sequence numbers, and its count;
  - per record: the kind and its version, the `key`, the `label_key`, and the SHA-256 digest of the record's
    canonical bytes (RFC 8785).
- Its label is computed as a single derived record's (ADR-0055 §3), and it passes the gate like any record. It lists
  only records the gate admitted on that route, so it names nothing the destination may not hold.
- **The sending tier keeps every manifest durably, in a projection table,** not only in a workflow journal. A durable
  record that lives only in a journal is lost when the journal is wiped.
- **Cadence** (proposed answer 1): a manifest is sent when N records or T seconds have passed, whichever comes
  first. When the route is idle, an empty heartbeat manifest is sent every T seconds, so the far side can tell
  silence from loss. N and T are declared per route.
- **An empty manifest's label is open.** The high-water of no entries is no label, and an unlabelled record is
  served to nobody (ADR-0055 §1a). The heartbeat therefore needs a label declared for it, with an owner: for example,
  per route, from the destination's entry. That is not decided here.

Basis: finding 8 (unidirectional validation, secondary) and finding 13.

### 6. A signed binding is designed here and not built

**What would be signed.** A binding object, per released record:
`{"v": 1, "kind": <name>, "kind_version": <version>, "key": <value>, "label": <label body>, "label_key": <key>,
"digest": "sha-256:<hex>", "signed_at": <time>, "signer": <id>}`.
- `digest` is over the record's canonical bytes (RFC 8785), without the binding.
- The label body is the one on the record (ADR-0055 §2), `life` included.
- The signed bytes are the binding object's RFC 8785 form. The JSON carriage is a JWS (RFC 7515) with a detached
  payload.

**Who signs and who checks.**
- The gate signs at release, after its decision admits the record. A refused record is never signed.
- The binding rides beside the record in the envelope, never inside the record, so the record's digest does not
  depend on it.
- A receiver recomputes `label_key` from the body (as today), recomputes the digest, and checks the signature. Any
  mismatch is a refusal.

**What stays as it is.**
- `label_key` stays a digest. It is never a signature, and the binding never replaces it.
- No key is generated, no field is added to any kind, and no service signs or checks anything until key management is
  decided. That is open.
- **The algorithm is declared per deployment, never hard-coded** (proposed answer 2), because national approvals of
  cryptography differ. A receiver accepts only the algorithm its deployment declares, never one that the signature's
  own header names alone.
- **Keys are per tier** (proposed answer 2), and `signer` names the tier. Rotation and distribution stay open until a
  real deployment names its PKI.

**Alignment.** This is the concept of 4778's optional cryptographic binding: a valid label, correctly associated, over
unmodified data (finding 7, secondary). The XML carriage named by the registry record, an XML digital signature in a
binding data object (registry), is generated from this design later (Decision 7), once 4778 is read.

### 7. JSON Schema is the source; XML Schema is generated later

- A kind stays a JSON Schema document (ADR-0046 §3). That is the only source.
- XML Schema for a kind is generated from its closed JSON Schema, later, and never written by hand. The generator is
  chosen when the first guard requires XML, not before (proposed answer 6).
- Decisions 3 and 4 make the generation possible: a closed schema with bounded strings has one XML shape.
- A disagreement between the generated XML Schema and the JSON Schema is a defect in the generator, never a second
  source.
- A 4774 XML label encoding is generated the same way, and only after 4774 is read. The paper says 4774 also has a
  JSON encoding (finding 4, secondary). Whether ADR-0055's body maps onto it is unread.

## Alignment, with a source per row

| This framework | STANAG 4774 / 4778 concept | Source |
|---|---|---|
| The deployment's declared policy, a URN (ADR-0055 §2b) | Policy identifier, with a short name | Finding 1, 3 (secondary) |
| A hierarchical dimension | Classification | Finding 1 (secondary); ADR-0055 §6 |
| Permissive and restrictive sets | Categories, with a type | Finding 1 (secondary, a permissive category only); ADR-0055 §6 |
| The label's `life`: `created`, `review` (ADR-0055 §2b), outside the key | Creation and review times | Finding 1, 2 (secondary) |
| The PDP checks a label against a reader's entitlement | Labels checked against clearances, never against labels | Finding 5 (secondary) |
| One label body per record | 4778 binding of one or more labels to data, or parts of it. Portion labels are not taken up here | Finding 6 (secondary) |
| The signed binding (Decision 6), designed only | 4778's optional cryptographic binding | Finding 7 (secondary); the registry record |
| An eligible kind on a one-way route | A guard's unidirectional validation against declared formats and exact labels | Finding 8 (secondary) |
| Equivalence between policies, declared per deployment (ADR-0055 §6) | Label transformation between policies at the boundary | Finding 9 (secondary) |

## Free-text fields, flagged

| Where | Field | Today | What Decisions 3 and 4 need |
|---|---|---|---|
| Built-in test record kind (PR #23, merged; `DESIGN-2026-11-11-bit-record-kind.md`) | fault code | "Never a free string" (:41) | Nothing |
| The same | an isolated unit with no identity yet, "carried as its alias, marked unresolved" (:68) | a source's alias, from no declared vocabulary | A `pattern` and `maxLength`, or `x-free-text`. With `x-free-text` the kind is not eligible |
| Remaining-life output kind (PR #23, merged; `DESIGN-2026-11-11-remaining-life-output-kind.md`) | an Asserted confidence, "stated with its reason" (:82) | the reason's carriage is not specified | The record carries a reference to the declaration, never the reason's text. Otherwise the kind is not eligible |
| Closure reasons and repair types (PR #34, draft) | none | Both vocabularies are closed values. `permanent_repair_due` is a date | Nothing. The completion contract that cites them must declare any free text it carries (for example work notes) |
| `MaintenanceAction` (ADR-0046 §3) | `work_order.task` | free text, never matched (ADR-0052:104) | `x-free-text` with a `maxLength`. The kind is not eligible as it stands |
| A maintainer's report (ADR-0046 §8, source 1) | "free text" (ADR-0046:231) | Whether it reaches `MaintenanceFaultEvent` is not read here | If it does, that kind declares it and is not eligible |
| Site declaration (`DESIGN-2026-11-06-site-declaration.md`:72) | `reason` | free text, at most 512 bytes | `x-free-text`, if it is ever outbound |
| Condition-monitoring closure (ADR-0059:56) | `resolution`, `cleared_by` | free text | `x-free-text`, if either is ever outbound. Counts read the closure reason, never these |
| Telemetry (`proto/openddil/telemetry/v1/telemetry.proto`:284; `proto/openddil/logistics/v1/windowed_telemetry.proto`:95) | `active_fault_codes`, `active_fault_codes_latest` | free strings, kept until every source is mapped (PR #23's ruling) | Never on an eligible kind |
| Gate, forwarder and intake log lines (`FOLLOW-UPS.md`, the ADR-0060 row) | details | free text | Out of scope: logs, not records. ADR-0060's redaction processor covers them |

The overlay's two declared kinds are not read for this record. Whether they already pass Decision 3 is found by the
load check when it is built, which names each failing pointer.

## What this does not establish

- **No conformance to STANAG 4774 or 4778 is claimed.** Neither standard was read. Every alignment above is by
  concept, from a vendor's paper and a registry record.
- **Nothing is accredited.** An eligible kind is not permitted to cross. It is shaped so that a guard can check it
  (ADR-0055 §7).
- **No guard, diode or boundary device is chosen.** Nothing here assumes a product.
- **No label transformation between policies is built.** Equivalence stays declared per deployment (ADR-0055 §6).
- **Portion labels are not taken up.** A record carries one label body.
- **Nothing is built.** No key, schema keyword check, outcome, kind or table exists yet.

## Owed

- Read ADatP-4774 and ADatP-4778 at named editions. Check every **(secondary)** and **(registry)** statement above
  against them, and correct this record where they differ.
- Name `created` and `review` from 4774, if 4774 names them differently, before any field freezes.

## Proposed answers to the six open questions (review, 2026-11-16; for the project owner to rule)

1. **Manifest cadence:** whichever comes first, N records or T seconds, plus an empty heartbeat manifest when idle,
   so the far side can tell silence from loss.
   - A gap is reported only at the far side, because a one-way link has no path back. That is acceptable.
   - Left open by this answer: the heartbeat's label (Decision 5).
2. **Keys and algorithm:** the algorithm is declared per deployment and never hard-coded, because national approvals
   of cryptography differ. Keys are per tier. Rotation and distribution stay open until a real deployment names its
   PKI.
3. **The policy's short name:** not in the label body. It lives in the policy declaration and is looked up.
4. **Arrays:** `maxItems` is required, on the same reasoning as bounded strings (Decision 3).
5. **Other one-way transports:** a file drop directory is the next candidate, because many one-way devices work that
   way. It stays open until a guard needs it.
6. **The XML Schema generator:** chosen when the first guard requires XML, not before.

## Consequences

### Positive

- A guard's checks have something to check: closed kinds, bounded strings, labels with a URN policy, and a manifest
  per batch that needs no answer.
- Free text becomes visible. Every free-text field is declared, so a reviewer finds it by search.
- A label's age is recorded without minting keys.

### Negative

- Closing a kind refuses records that carry an undeclared field. A deployment whose producer adds fields early sees
  `schema_invalid` where the record passed before. The staged rollout (Decision 3) limits this to kinds a person has
  moved to `enforce` after a clean report.
- Report mode validates each record twice, once as declared and once closed, until its kind is enforced.
- A deployment whose policy id is not a URN must re-declare it, and once keys are stored, that is a backfill of every
  stored key.
  - **Today it costs nothing, because no `label_key` is stored anywhere yet.** As read on 2026-11-16, no service on
    any default branch writes one. The labels library computes `lk1` keys and stores none. The SQL function that
    would store them is on an unmerged branch.
  - No deployment was read for this. The claim is about code, and no code has written a key.
  - The cost begins when the compatibility slice ships, so the URN rule is cheapest if it is ruled before then.
- The manifest is a second record per batch on every one-way route.

### Neutral

- The two label rules move with ADR-0055's `lk2` proposal (PR #38). Nothing else here changes a key.
- The free-text flags change no merged design. They say what each needs when its kind is declared.

## Related

- ADR-0055 §2b (PR #38): the label rules written in full.
- ADR-0046: destinations, routes, kinds, and the gate's refusal reasons.
- ADR-0029: the releasability label.
- ADR-0060: opaque ids only, and the redaction processor.
- `DESIGN-2026-11-06-adr0055-compatibility-slice.md` §1.1, §1.4: the policy id's pattern and the backfill.
- `DESIGN-2026-11-10-adr0058-first-increment.md`: today's forwarder outcomes.
