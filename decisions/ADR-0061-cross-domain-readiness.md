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

**Revised 2026-11-16, after reading the standards.** ADatP-4774 and ADatP-4778.2 were read, and every statement that
was marked secondary or registry was checked against them. Each one now cites a clause, or is corrected, or is kept as
secondary because neither document settles it. The changes are listed under "Corrections after reading the
standards". Five new points came out of the reading. The project owner's proposed answers to them are recorded under
New points, pending ruling. One half of C, provenance, did not fit the text as first proposed. Option (iv) is now
recommended there, with the alternatives listed.

## Sources, and how much of each was read

| Source | What it is | Read |
|---|---|---|
| ADatP-4774 Edition A Version 1 (STANAG 4774), Confidentiality Metadata Label Syntax | The standard | **Read in full**: Chapters 1-5, Appendix 1 with its Annexes A (schema) and B (examples), and Appendix 2 with its Annexes A, C and D. Appendix 2 Annex B, the NATO policy's information file, was read for its structure, and its per-nation value lists were skimmed. Cited by clause |
| ADatP-4778.2 Edition A Version 1, Profiles for Binding Metadata to a Data Object | A standards-related document to STANAG 4778: the binding profiles | **Read in full**: Chapters 1-12, and Chapter 2's Annexes A-E. The worked examples were scanned, not checked line by line. Cited by chapter and section |
| ADatP-4778 (STANAG 4778), Metadata Binding Mechanism | The standard the profiles apply | **Unread.** What is said here about the binding data object comes from 4778.2's use of it, never from 4778 itself |
| Isode, "Isode Approach to Data Centric Security using NATO Confidentiality Labels", white paper, 13 pages | **Secondary: a vendor's paper.** It describes the standards and the vendor's products | Read in full. Fetched 2026-11-16 from `https://www.isode.com/wp-content/uploads/2023/08/Isode-Approach-to-Data-Centric-Security-using-NATO-Confidentiality-Labels.pdf`. The PDF's metadata gives a creation date of 2026-07-27. Kept as a secondary source. Where it differs from the standards, the standards are followed and the difference is listed |
| IANA media type registration, `application/vnd.nato.bindingdataobject+xml` | **A registry record**, not the standard. Registered 2023-11-27; change controller the NATO Standardization Office | Read in full |
| RFC 3061 (the `urn:oid:` namespace), RFC 8141 (URNs), RFC 8785 (JSON canonicalization), RFC 7515 (JWS), RFC 7444 (the email label header that 4778.2's `Binding-Data` header is based on) | IETF standards | Cited for their names and scope only. Nothing here depends on a clause of them yet |

Statements about what 4774 or 4778.2 contain now cite a clause, for example "4774 App 1 Table 5" or "4778.2 §7.5".
- **4774 is paraphrased, never quoted.** Its element, attribute and value names are given as identifiers.
- **4778.2 is quoted only in short phrases,** where the wording matters.
- A statement still marked **(secondary)** is one that neither document settles, and it says so.

ADatP-4778.2 is a NATO standardization document. Phrases quoted from it here are acknowledged to NATO.

## Findings first

### What the standards say

1. **A 4774 label is XML, and this edition defines no other encoding.** Its stated objective is common label formats based
   on XML (4774 §1.2). The syntax uses XML and is based on the RFC 2634 label (4774 §4.4). The schema's namespace is
   `urn:nato:stanag:4774:confidentialitymetadatalabel:1:0` (4774 App 1 Annex A). No JSON or CBOR encoding is defined
   in Edition A Version 1.
2. **A label's parts, by the standard's names** (4774 App 1).
   - A label is a `ConfidentialityLabel`, with two optional attributes, `Id` and `ReviewDateTime` (Table 4).
   - It has a mandatory `ConfidentialityInformation` and a mandatory `CreationDateTime`, and an optional
     `OriginatorID` and `SuccessionHandling`.
   - `ConfidentialityInformation` has a mandatory `PolicyIdentifier` and `Classification`, and an optional
     `PrivacyMark` and `Category`.
   - The schema has three roles for a label: originator, alternative and metadata (`originatorConfidentialityLabel`,
     `alternativeConfidentialityLabel`, `metadataConfidentialityLabel`, App 1 Annex A).
3. **The lifecycle times are `CreationDateTime` and `ReviewDateTime`.**
   - `CreationDateTime` is when the label was created, which may differ from when the data was (App 1, the label's
     base type). It is mandatory in every label (App 1 Annex A), and the NATO policy requires it again (4774 Ch 5).
   - `ReviewDateTime` is when the label is due for review. It is an attribute on the label, and it is required
     whenever there is no `SuccessionHandling` (4774 §4.3; App 1 Table 4; Ch 5).
   - A review date in the past does not make the label invalid (App 1, the text before Table 4; Ch 5).
   - Both are XML Schema `dateTime` values (App 1 Annex A).
   - `SuccessionHandling` names a later label and the date it takes over, and keeps the label's history (4774 §4.3).
4. **The policy is named by a mandatory text identifier, with an optional `urn:oid:` URI.**
   - The content of `PolicyIdentifier` is a textual identifier for the policy (App 1, PolicyIdentifierType). Under the
     NATO policy it is "NATO" (App 2 Table 10).
   - Its `URI` attribute is optional. If present, it must use the `urn` scheme with the `oid` namespace (App 1 Table 5;
     Ch 5). Another URN namespace is not allowed. The NATO policy's URI is `urn:oid:1.3.26.1.3.1` (App 2 Table 10).
     The PUBLIC policy has its own (App 2 Annex C Table 19).
   - App 1 gives the URI's reason as an identification without the ambiguity of a text identifier.
   - Under the NATO policy, values in `ConfidentialityInformation` are compared case-insensitively (Ch 5).
5. **One classification, and categories of three types.**
   - A label has exactly one `Classification` (4774 §4.2 b; App 1). Its `URI` attribute is not to be used (App 1
     Table 6).
   - A `Category` has a mandatory `Type`, which is `RESTRICTIVE`, `PERMISSIVE` or `INFORMATIVE`, a mandatory
     `TagName`, and an optional `URI` in the `urn:oid:` form (App 1 Tables 7 and 8). Its values are `GenericValue`
     elements only (App 1, CategoryValueType).
   - `INFORMATIVE` categories are not used for access control (App 1 Table 7).
   - The NATO policy's tags are Context, Releasable To and Only (permissive), Additional Sensitivity (restrictive), and
     Administrative (informative) (App 2 Table 11).
   - There is no exclusionary type.
   - The tag names, and how their values are used, are set by the policy in force (App 1, after Table 7).
   - Releasable To widens dissemination to entities outside the context the information was created in (4774 Table 1;
     App 2, after Table 11). Under the NATO policy, ownership is shown by the Context category, which holds a single
     value. When Releasable To is present, Context also carries the value `Releasable` (App 2, the Context rules).
   - `PrivacyMark` is a legacy element, kept for backward compatibility (4774 §4.2 c).
   - **`OriginatorID` identifies whoever originated the label,** which may not be whoever created the information
     (App 1, the label's base type). It is a single element. It names a principal in one of a fixed set of forms: an
     email, DNS, directory, URI, IP, X.400, XMPP or user-principal name (App 1 Table 9). There is no form for a nation,
     and no way to name several.
   - The label's schema allows further elements from other namespaces after its own elements (App 1 Annex A).
6. **A label is checked against a clearance, and a second policy is carried as an alternative label.**
   - A clearance has the same elements as a label, except that it holds several classifications (4774 App 2 Annex A,
     which cites RFC 5913).
   - 4774 supports two policies in parallel, with an agreed equivalence between them (§2.3, requirements 4 and 5). The
     equivalent label in the recipient's policy is an **alternative label, carried in addition to** the originator's
     label (4774 Ch 3, the definition of Alternative Confidentiality Label; App 1).
7. **Labels may be bound to portions of the data,** such as paragraphs, sections, figures and tables (4774 §4.2).
8. **4778.2 records a binding as a Binding Data Object (BDO), and the BDO is XML in every profile.**
   - A binding is recorded as a BDO (4778.2 §1.6). There are three ways to place one: embedded, encapsulated and
     detached (§1.8).
   - In every profile the BDO is a `BindingInformation` document in the namespace
     `urn:nato:stanag:4778:bindinginformation:1:0`, holding one or more metadata bindings, each with references to its
     data and its metadata. The data's media type is declared on its reference (4778.2 Ch 2 Annex A and the profile
     chapters).
   - The data object bound need not be XML. A profile binds an email, an HTTP body or a file (findings 9 and 10).
9. **Outside XML, the BDO is carried whole, as an encoded XML document.**
   - **Email:** a new `Binding-Data` header field. Its `binding-data-object` parameter is the base64 BDO and is always
     present, its `binding-type` is the URI above, and an optional `marking` is a human-readable marking. The BDO is
     detached, and binds the message (4778.2 §3.5). The header is based on RFC 7444's label header.
   - **HTTP:** it is RECOMMENDED to use the same `Binding-Data` header, with a base64 BDO that binds the body (4778.2
     §7.5).
   - **Files:** a sidecar file named after the data file with `.bdo` appended, in the same folder, with a relative
     reference to the data (4778.2 §9.5).
   - **Packages and documents:** an Open Packaging Convention part (Ch 8), Office Open XML custom XML (Ch 5), or an
     XMP property (Ch 10).
   - **XML protocols:** an XMPP element (Ch 4), a SOAP header (Ch 6), a web service messaging profile element (Ch 11),
     and fixed places in common XML artefacts (Ch 12).
10. **A cryptographic binding is optional. The profiled protocols are XML Signature and CMS, not JWS.**
    - A non-cryptographic binding is a reference that can be checked structurally. A cryptographic one adds integrity,
      and authenticity of whoever made the binding. The profiles do not mandate cryptography. The assurance needed is
      a matter for organizational, national or federation policy (4778.2 §2.1).
    - The profiled mechanisms are an XML digital signature (Ch 2 Annexes A and B), an XML HMAC (Annex C) and a CMS
      signature (Annex E). JWS is named only as a possible future subprofile (§2.1).
    - If a binding is cryptographic, the BDO holds at least one signature (Annex A). The signature carries a timestamp
      of when the binding was made (Annex A).
    - The algorithms are listed as mandatory, optional or prohibited. SHA-384 digests are mandatory to support, and
      SHA-1 and MD5 are prohibited (Annex A Table 2-3). RSA-SHA256 and ECDSA-SHA256 signatures are mandatory to
      support (Annex B Table 2-4). HMAC-SHA256 is mandatory (Annex C Table 2-5). The use of the mandatory and optional
      algorithms may be narrowed further by national or organizational policy (Annex E, after Tables 2-6 and 2-7).
    - A signature names its key by an X.509 certificate (Annex B). Certificates MUST be included in strategic,
      high-throughput systems (Annex B). For CMS, they SHOULD NOT be included in tactical systems with low bandwidth
      (Annex E).
    - The registry record says the binding data object has "an optional XML digital signature element" (registry). That
      agrees with Annex A.

### What the standards read do not settle (secondary)

11. **A guard at a domain boundary validates one way, against declared formats and exact labels** (p.9, secondary).
    Neither document specifies a guard. 4778.2 says only that its profiles have been validated since 2011 with an XML
    labelling guard (§1.5). So this is still a description of a vendor's product, and it stays secondary.
12. **Each domain usually has its own policy, and labels are transformed at the boundary** (p.5, p.9, secondary).
    4774's mechanism is narrower: an alternative label in the recipient's policy is carried beside the originator's
    label, not in place of it (finding 6). A transformation that replaces the label is the paper's description, not the
    standard's.
13. **Labels are never compared against labels** (p.3, secondary). 4774 checks labels against clearances (finding 6),
    and does not state this rule.

### What this framework has today

14. **ADR-0055 §6 already aligns by concept:** declared policy to policy identifier, hierarchical to classification,
    permissive and restrictive sets to categories, and the stamped label to 4778's binding "as a concept only".
    `label_key` is a digest of the canonical form, not a cryptographic binding (ADR-0055 §2, §6).
15. **The label has no lifecycle times,** and the policy id is any string matching
    `^[a-z0-9][a-z0-9:._-]{0,62}$` (`DESIGN-2026-11-06-adr0055-compatibility-slice.md` §1.1). Nothing requires it to be
    a URN. The built `lk1` body has exactly three keys, `policy`, `v` and `dims`, and `verify` refuses any other
    (the labels library's `lk1` module, `verify`, on main).
16. **A kind is a JSON Schema document in the overlay** (ADR-0046 §3). Nothing requires a kind to be closed, and
    nothing marks a field as free text. The gate refuses a record that fails its kind's schema as `schema_invalid`
    (ADR-0046 §2).
17. **Every egress route expects an answer.** The forwarder's outcomes are `held`, `delivered` and `failed`
    (`DESIGN-2026-11-10-adr0058-first-increment.md`, finding 2). A destination may declare `intake`, which polls it or
    receives callbacks from it (ADR-0046 §1, §5). There is no route that cannot answer, and no record of what was sent
    that does not depend on an answer.
18. **Free text reaches records in several places** (the flags table below). The maintenance action's
    `work_order.task` is one (ADR-0046 §3; ADR-0052:104).

## Decision

### 1. Label lifecycle fields ride outside `label_key`, under the standard's names

Written as ADR-0055 §2b (PR #38). In short:
- `CreationDateTime` and `ReviewDateTime` ride in the label body under `life`, beside `dims`. The member names are
  4774's (finding 3). `life` is this record's grouping, because 4774 puts one time in an element and the other in an
  attribute.
- Times are written `YYYY-MM-DDThh:mm:ssZ`, with optional fractional seconds: RFC 3339 in UTC, which is also an XML
  Schema `dateTime`, the type 4774 uses.
- `CreationDateTime` is when the label was stamped, not when the data was made (finding 3).
- They never enter the canonical form or the key. Two labels that differ only in `life` give one key, so a record's
  age mints no new key, admitted set or shape.
- The label table holds no `life`, and the PDP never reads it. A past `ReviewDateTime` is counted and reported, never
  a refusal. 4774 says the same: a past review date does not make the label invalid (finding 3).
- `life` is optional and never defaulted. An undeclared member or a bad time is refused at the stamp.
- **A label without both times cannot be written as a 4774 label.** 4774 requires `CreationDateTime` always, and
  `ReviewDateTime` whenever there is no `SuccessionHandling`, which is not taken up here (finding 3).
- **The review time comes from a declared rule, never a default** (New point A). Proposed:
  - A policy that is exported as 4774 labels (New point D) declares a `review_period`. It is an ISO 8601 duration in
    whole days, `P<n>D`, so adding it gives exactly one answer.
  - Under such a policy, the stamp writes `CreationDateTime` as the stamp time, and `ReviewDateTime` as that time plus
    the period. The period is a declaration, not a default.
  - An exported policy that declares no `review_period` is refused at load.
  - A route that writes 4774 labels refuses, with a new reason `label_life_missing`, any record whose label lacks
    either time, for example one stamped before the period was declared. It never fills a time in.
  - Other routes are unaffected, and `life` stays optional on them.

Basis: findings 2 and 3.

### 2. A policy is identified by a `urn:oid:` URI, and declares its text identifier beside it

Written as ADR-0055 §2b (PR #38). In short:
- **The id in the canonical form and the key is the policy's 4774 `URI`,** written `urn:oid:<dotted decimal>`
  (RFC 3061). It must match `^urn:oid:[0-2](\.(0|[1-9][0-9]*))+$`. 4774 allows only the `oid` namespace in that
  attribute (finding 4), so any other URN is refused when it is declared, with the id named.
- The id still matches the slice's pattern, so it is lowercase and at most 63 characters. Both 4774 policy URIs fit.
- **The declaration also carries `PolicyIdentifier`, the policy's text identifier** (for example "NATO"). It is
  mandatory in a 4774 label (finding 2). It is not in the body or the key, and a 4774 label is written by looking it up
  by the URI.
- The key uses the URI, not the text, because the text is compared case-insensitively (finding 4) and a key needs one
  spelling.
- **The body's member stays `policy`, and holds the URI.** This is the one name that differs from the standard. The
  built `lk1` body has exactly `policy`, `v` and `dims` (finding 15), and `lk2` keeps that shape.
- An existing id changes only by re-declaration, through the slice's backfill, because the id is in the canonical form.

Basis: finding 4. **Narrowed after reading:** the earlier text allowed any URN. 4774 allows only `urn:oid:` in the
policy's URI, so this decision now does too (New point E).

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

Basis: finding 11 (a guard checks declared message formats, secondary) and finding 16.

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

Basis: finding 11 (secondary). Free text is what a format check cannot judge.

### 5. One-way egress routes, with a `handed_off` outcome and manifest records

**A destination can be one-way.**
- A destination entry (ADR-0046 §1) may set `one_way: true`. Every route to it is one-way.
- A one-way destination may not declare `intake` or `trust_on_behalf_of`. Either is refused at load, because nothing
  comes back.
- Its transport is a `topic`: the hand-off is the write to a topic that the boundary device reads. An `http` transport
  is refused for a one-way destination, because HTTP needs an answer. A file drop is the next candidate, and 4778.2
  has a profile for it (proposed answer 5).
- **No 4778.2 profile covers a message topic** (findings 8 and 9). How a binding rides on a topic record is decided
  when a boundary device that reads topics is named. The nearest profiles are the HTTP header (4778.2 §7.5) and the
  sidecar file (§9.5).

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
  served to nobody (ADR-0055 §1a). A 4774 label also always has a classification (finding 5), so "no label" cannot be
  written as one. The heartbeat therefore needs a label declared for it, with an owner: for example, per route, from
  the destination's entry. That is not decided here.

Basis: finding 11 (unidirectional validation, secondary) and finding 17.

### 6. A signed binding is designed here and not built

**Corrected after reading.** The earlier text designed a detached JWS over the binding object and called it the
concept of 4778's binding. 4778.2 profiles XML Signature, XML HMAC and CMS, and names JWS only as a possible future
subprofile (finding 10). A JWS binding is therefore not a 4778 binding, and a receiver that expects one cannot check
it. The decision is now in two parts.

**A binding that leaves the domain is a 4778.2 BDO.**
- It is a `BindingInformation` document (finding 8), written per record at release:
  - its data reference is the record's canonical bytes (RFC 8785), declared as JSON by media type. The record itself
    stays JSON (finding 8);
  - its metadata reference is the record's 4774 label, written from the label body (Decision 7). `life` is included
    as `CreationDateTime` and `ReviewDateTime`.
- If the deployment declares the binding cryptographic, the BDO carries an XML Signature (4778.2 Ch 2 Annexes A and
  B), or an XML HMAC where the two sides share a key (Annex C). The signature's timestamp records when the binding was
  made (finding 10), so no separate `signed_at` is needed.
- The BDO is carried as the profile for the transport says: the `Binding-Data` header (4778.2 §7.5) or a `.bdo`
  sidecar (§9.5) (finding 9). A topic has no profile yet (Decision 5).

**Who signs and who checks.**
- The gate makes the binding at release, after its decision admits the record. A refused record is never bound.
- The binding rides beside the record, never inside it, so the record's digest does not depend on it.
- A receiver recomputes `label_key` from the body (as today), checks the bound data against the reference, and checks
  the signature. Any mismatch is a refusal.

**No binding inside one domain; bind at the boundary only** (New point B, proposed).
- Inside a domain, `label_key` and the PEP already tie a record to its label and enforce it.
- An XML binding on every internal record would add cost and no benefit.
- The JWS form is parked: a detached JWS (RFC 7515) over the RFC 8785 bytes of
  `{"v": 1, "kind", "kind_version", "key", "label", "label_key", "digest", "signer"}`. Nothing builds it, and it is
  never sent across a boundary as a 4778 binding.

**What stays as it is.**
- `label_key` stays a digest. It is never a signature, and the binding never replaces it.
- No key is generated, no field is added to any kind, and no service signs or checks anything until key management is
  decided. That is open.
- **The algorithm is declared per deployment, never hard-coded** (proposed answer 2). It is chosen from 4778.2's
  mandatory and optional lists, never a prohibited one, and a national or organizational policy may narrow it further
  (finding 10). A receiver accepts only the algorithm its deployment declares, never one that the signature names
  alone.
- **Keys are per tier** (proposed answer 2). An XML Signature names its key by X.509 certificate (finding 10), so a
  tier's key is a certificate. Whether certificates ride in each binding is declared per route: 4778.2 includes them in
  high-throughput systems and, for CMS, omits them on low-bandwidth tactical links (finding 10). Rotation and
  distribution stay open until a real deployment names its PKI.

**Alignment.** The registry record's "optional XML digital signature element" (registry) is the signature of 4778.2
Ch 2 Annex A. The BDO's own schema is ADatP-4778's, which is unread (Owed).

### 7. JSON Schema is the source; XML is generated

- A kind stays a JSON Schema document (ADR-0046 §3). That is the only source.
- XML Schema for a kind is generated from its closed JSON Schema, later, and never written by hand. The generator is
  chosen when the first guard requires XML payloads, not before (proposed answer 6). A JSON record can be bound as it
  is (finding 8), so a kind needs no XML form to cross.
- Decisions 3 and 4 make the generation possible: a closed schema with bounded strings has one XML shape.
- A disagreement between the generated XML Schema and the JSON Schema is a defect in the generator, never a second
  source.
- **A 4774 label is XML, and is written from the label body.** 4774 Edition A Version 1 has no JSON encoding (finding
  1). The JSON body stays this framework's form, and a 4774 label is generated from it, never stored beside it. The
  mapping, field by field:

| Label body | 4774 element (App 1) |
|---|---|
| `policy` (a `urn:oid:` URI) | `PolicyIdentifier/@URI`. The element's text is the declared `PolicyIdentifier`, looked up by the URI (Decision 2) |
| A hierarchical dimension's value | `Classification`. A 4774 label has exactly one (New point D) |
| A permissive set dimension | `Category` with `Type="PERMISSIVE"`, its `TagName` declared per dimension, one `GenericValue` per value |
| A restrictive set dimension | `Category` with `Type="RESTRICTIVE"`, likewise |
| An exclusionary dimension | None. 4774 has no exclusionary type (New point D) |
| `life.CreationDateTime` | `CreationDateTime` element |
| `life.ReviewDateTime` | `ReviewDateTime` attribute on `ConfidentialityLabel` |
| The nation dimension, for access: its authors and its release set | The release dimension's permissive `Category`, whose values are the authors and the release set together (New point C) |
| The nation dimension, for provenance: who authored the record | Nothing in the label. Authorship stays a declared field in the record body. `OriginatorID` is the stamping tier's declared identity (New point C (iv), recommended, pending ruling) |

- A dimension's `TagName`, and its optional `urn:oid:` URI, are declared with the dimension. Its values are written
  as declared. Under the NATO policy they are compared case-insensitively (finding 4).
- **The nation dimension for access** (New point C, proposed).
  - Today the author branch admits a reader of an author nation, and the release branch admits a reader of a release
    nation. A receiver sees only the label, so the authors are written into the permissive release category beside
    the release set. The far side then grants the same access.
  - If the release set is absent, the authors alone are written. A rollup has no author, so its release set alone is
    written. Either way the written set never admits anyone the label does not.
  - The category's `TagName` and any companion values its policy requires are declared with the policy's export. One
    example of a companion value is the NATO policy's `Releasable` in Context (finding 5).
  - Under the NATO policy this fits the category: Releasable To is a permissive inclusion set (finding 5).
- A dimension is never written as an `INFORMATIVE` category. The PDP reads every dimension, and informative
  categories are not used for access control (finding 5). A provenance copy under New point C (ii) would not be a
  dimension.

## Alignment, with a source per row

| This framework | STANAG 4774 / 4778 concept | Source |
|---|---|---|
| The deployment's declared policy: a `urn:oid:` URI in the key, and its text identifier in the declaration (ADR-0055 §2b) | `PolicyIdentifier`: mandatory text, optional `urn:oid:` `URI` | 4774 App 1 Table 5; Ch 5; App 2 Table 10 (finding 4) |
| A hierarchical dimension | `Classification`, exactly one per label | 4774 §4.2 b; App 1 Table 6 (finding 5); ADR-0055 §6 |
| Permissive and restrictive sets | `Category` with `Type` `PERMISSIVE` or `RESTRICTIVE`, and a `TagName` | 4774 App 1 Tables 7, 8 (finding 5); ADR-0055 §6 |
| An exclusionary dimension | None | 4774 App 1 Table 7 (finding 5) |
| The label's `life`: `CreationDateTime`, `ReviewDateTime` (ADR-0055 §2b), outside the key | The same names: an element and an attribute | 4774 §4.3; App 1 Table 4; Ch 5 (finding 3) |
| The PDP checks a label against a reader's entitlement | A label checked against a clearance | 4774 App 2 Annex A (finding 6). "Never against labels" is secondary (finding 13) |
| One label body per record | A binding of one or more labels to data, or to portions of it. Portion labels are not taken up here | 4774 §4.2 (finding 7); 4778.2 §1.6, Ch 2 Annex A (finding 8) |
| The outbound binding (Decision 6), designed only | A BDO, with an optional XML Signature, XML HMAC or CMS signature | 4778.2 §2.1, Ch 2 Annexes A-C, E (finding 10); the registry record |
| An eligible kind on a one-way route | A guard's unidirectional validation against declared formats and exact labels | Finding 11 (secondary). Neither document specifies a guard |
| Equivalence between policies, declared per deployment (ADR-0055 §6) | An alternative label in the recipient's policy, carried beside the originator's | 4774 §2.3 requirements 4-5; Ch 3; App 1 (finding 6). Transformation at the boundary is secondary (finding 12) |

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

## Corrections after reading the standards (2026-11-16)

Each statement marked secondary or registry in the earlier text, and what became of it.

| Earlier statement | Now | Clause |
|---|---|---|
| A label carries a policy identifier, classification, categories and lifecycle times | **Re-cited.** Confirmed, with the standard's element names | 4774 App 1 (finding 2) |
| Lifecycle is part of the label: "creation data and review date" | **Re-cited and sharpened.** The names are `CreationDateTime` and `ReviewDateTime`. Creation is always mandatory, and review is mandatory without succession handling | 4774 §4.3; App 1 Table 4; Ch 5 (finding 3) |
| The policy is identified by an OID and a string | **Corrected.** The text identifier is mandatory, and the URI is optional and only `urn:oid:` | 4774 App 1 Table 5; Ch 5 (finding 4) |
| XML is one encoding of several, including JSON and CBOR | **Corrected.** This edition defines XML only | 4774 §1.2, §4.4 (finding 1) |
| Labels are checked against clearances, never against labels | **Split.** Checking against clearances is re-cited. "Never against labels" is not in the standard and stays secondary | 4774 App 2 Annex A (findings 6, 13) |
| 4778 binds labels to data, possibly to parts of it | **Re-cited** to 4778.2 and 4774. Portions are 4774's | 4774 §4.2; 4778.2 §1.6 (findings 7, 8) |
| 4778's cryptographic binding is optional | **Re-cited.** The protocols are XML Signature, XML HMAC and CMS. JWS is not profiled | 4778.2 §2.1, Ch 2 Annexes A-C, E (finding 10) |
| The binding data object has an optional XML digital signature element (registry) | **Re-cited** to 4778.2. The BDO's base schema is ADatP-4778's, unread | 4778.2 Ch 2 Annex A (finding 10) |
| A guard validates one way, against declared formats and exact labels | **Kept secondary.** Neither document specifies a guard | 4778.2 §1.5 mentions one (finding 11) |
| Each domain has its own policy, and labels are transformed at the boundary | **Corrected in part.** 4774 carries an alternative label beside the original. Transformation stays secondary | 4774 §2.3; Ch 3; App 1 (findings 6, 12) |
| Decision 1: `created` and `review` | **Renamed** to `CreationDateTime` and `ReviewDateTime` | Finding 3 |
| Decision 2: any URN | **Narrowed** to `urn:oid:`, with `PolicyIdentifier` declared beside it | Finding 4 |
| Decision 6: a detached JWS is the binding | **Corrected.** An outbound binding is a 4778.2 BDO. Nothing is bound inside a domain, and the JWS form is parked (New point B) | Finding 10 |
| Decision 7: 4774 also has a JSON encoding, so the body may map onto it | **Corrected.** The label is XML and is generated from the body, field by field | Finding 1 |
| Proposed answer 5: a file drop directory | **Now has a profile:** the `.bdo` sidecar | 4778.2 §9.5 (finding 9) |

## What this does not establish

- **No conformance to STANAG 4774 or 4778 is claimed.** 4774 and the 4778.2 profiles were read, and the alignment
  above cites them. Nothing is built to them, and ADatP-4778 itself is unread.
- **Not taken up:** `SuccessionHandling`, `PrivacyMark`, alternative labels, and portion labels. A record carries one
  label body. Under New point C's recommended (iv), `OriginatorID` is taken up as the stamping tier's identity.
  `INFORMATIVE` categories and extension elements are taken up only if alternative (i) or (ii) is ruled on instead.
- **Nothing is accredited.** An eligible kind is not permitted to cross. It is shaped so that a guard can check it
  (ADR-0055 §7).
- **No guard, diode or boundary device is chosen.** Nothing here assumes a product.
- **No label transformation between policies is built.** Equivalence stays declared per deployment (ADR-0055 §6).
- **Nothing is built.** No key, schema keyword check, outcome, kind, table, label writer or BDO exists yet.

## Owed

- Read ADatP-4778, Metadata Binding Mechanism, at a named edition, before a BDO writer is specified. The BDO's schema
  is cited here only from 4778.2's use of it.
- Read the CMS signature algorithm table (4778.2 Ch 2 Annex E, Table 2-7) from the document before any CMS algorithm
  is listed. Its text did not extract cleanly, so no status per algorithm is cited from it.
- Findings 11 to 13 stay secondary until a boundary device is named and its documents are read.

## Proposed answers to the six open questions (review, 2026-11-16; revised after reading; for the project owner to rule)

1. **Manifest cadence:** whichever comes first, N records or T seconds, plus an empty heartbeat manifest when idle,
   so the far side can tell silence from loss.
   - A gap is reported only at the far side, because a one-way link has no path back. That is acceptable.
   - Left open by this answer: the heartbeat's label (Decision 5). A 4774 label always has a classification, so the
     heartbeat's label has to be declared.
2. **Keys and algorithm:** the algorithm is declared per deployment and never hard-coded. It is chosen from 4778.2's
   mandatory and optional lists, never a prohibited one, and a national or organizational policy may narrow it
   (finding 10). Keys are per tier, as X.509 certificates for signatures. Rotation and distribution stay open until a
   real deployment names its PKI.
3. **The policy's short name:** it is 4774's `PolicyIdentifier` text, and a 4774 label must carry it (finding 4). It
   lives in the policy declaration, never in the label body or key, and the label writer looks it up by the URI.
4. **Arrays:** `maxItems` is required, on the same reasoning as bounded strings (Decision 3).
5. **Other one-way transports:** a file drop is the next candidate, because many one-way devices work that way. If it
   is built, it follows 4778.2's sidecar profile: a `.bdo` file beside each data file (§9.5). It stays open until a
   guard needs it.
6. **The XML Schema generator for kinds:** chosen when the first guard requires XML payloads, not before. The 4774
   label writer and the BDO writer are needed sooner, for the first cross-domain release, because both are XML in the
   standards (findings 1 and 8).

## New points from the reading (the project owner's proposed answers, pending ruling)

- **A. Both times, by a declared rule.** An exported policy (D) declares a `review_period` (`P<n>D`). The stamp writes
  `CreationDateTime` as the stamp time and `ReviewDateTime` as that time plus the period, so the review time is a
  declared rule, not a default in disguise.
  - An exported policy with no `review_period` is refused at load, so it cannot feed a 4774 route.
  - A route that writes 4774 labels refuses a record whose label lacks either time, with `label_life_missing`, and
    never fills one in.
  - Other routes are unaffected, and `life` stays optional on them (Decision 1).
- **B. No binding inside one domain.** Inside a domain, `label_key` and the PEP already do the job. An XML binding on
  every internal record is cost with no benefit. Bind at the boundary only. The JWS candidate stays parked (Decision 6).
- **C. The nation dimension, split in two.**
  - **Access: proposed as written in Decision 7.** In the export, the author nations are added to the permissive
    release category, so the far side grants the same access the author branch does. Checked against the text, this
    fits. A permissive category is an explicit inclusion set for access control, and Releasable To widens
    dissemination to named entities (finding 5).
  - **Provenance: does not fit the text as proposed.** The proposal was to carry authorship in the binding's originator
    metadata.
    - 4774's `OriginatorID` identifies whoever originated the label, not who created the information. It is one
      element, naming one principal in a fixed set of forms, and none of them is a nation (finding 5).
    - 4778.2's binding data object, as read, has no originator field. "Originator" there is the role of whoever
      creates the signature, and the signer's certificate identifies the binder (Ch 2 Annexes A and B).
    - The base ADatP-4778 is unread, and its schema could hold more.
  - **Recommended for provenance: (iv), pending the project owner's ruling.**
    - `OriginatorID` is the stamping tier's declared identity, in one of 4774's name forms (finding 5). That is what
      the field describes: who originated the label.
    - **Authorship stays in the record body, as a declared field of the kind, never in the exported label.** On an
      eligible kind the field is bounded like any other (Decisions 3 and 4).
    - **Why:** a guard allows labels by exact match (finding 11, secondary). Authorship in an extension element or an
      informative category would make every distinct author set a distinct label. Composites and rollups grow those
      sets combinatorially, so the labels a guard must allow would multiply.
    - Under (iv), the label varies only by its access fields and by `OriginatorID`. `OriginatorID` takes one value
      per exporting tier, a small declared set.
  - **Alternatives, kept listed.**
    - (i) `OriginatorID` names the stamping tier, and authorship rides in an extension element in a declared
      namespace, which the label's schema allows (finding 5).
    - (ii) Authorship rides in a declared `INFORMATIVE` category, which a receiver does not use for access (finding
      5). This needs the policy to declare the tag.
    - (iii) Wait for the base ADatP-4778.
- **D. A policy exported as 4774 labels** declares `exports_4774: true`. Such a policy declares at most one
  hierarchical dimension and no exclusionary one, and this is checked at load. Policies that never export are not
  limited. A route that writes 4774 labels is refused at load unless its policy is exported.
- **E. `urn:oid:` only.** The standard requires it for the policy's URI (finding 4), and no key is stored yet, so the
  narrowing costs nothing (Consequences).

## Consequences

### Positive

- A guard's checks have something to check: closed kinds, bounded strings, labels with a `urn:oid:` policy, and a
  manifest per batch that needs no answer.
- Free text becomes visible. Every free-text field is declared, so a reviewer finds it by search.
- A label's age is recorded without minting keys.
- Field names now match 4774's where 4774 names the thing, so the label writer needs no rename table except for
  `policy`.

### Negative

- Closing a kind refuses records that carry an undeclared field. A deployment whose producer adds fields early sees
  `schema_invalid` where the record passed before. The staged rollout (Decision 3) limits this to kinds a person has
  moved to `enforce` after a clean report.
- Report mode validates each record twice, once as declared and once closed, until its kind is enforced.
- A deployment whose policy id is not a `urn:oid:` URI must re-declare it, and once keys are stored, that is a backfill
  of every stored key.
  - **Today it costs nothing, because no `label_key` is stored anywhere yet.** As read on 2026-11-16, no service on
    any default branch writes one. The labels library computes `lk1` keys and stores none. The SQL function that
    would store them is on an unmerged branch.
  - No deployment was read for this. The claim is about code, and no code has written a key.
  - The cost begins when the compatibility slice ships, so the `urn:oid:` rule is cheapest if it is ruled before then.
- The manifest is a second record per batch on every one-way route.
- Crossing needs XML: a 4774 label writer and a BDO writer, even though records stay JSON.

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
