# ADR-0056 — One identity per thing, minted once; every other id is an alias or a record id scoped to it

## Status

**PROPOSED — 2026-11-07. Design only. Nothing here is built, nothing is deployed, and nothing has been measured.**
- **Read by Chris on 2026-11-07 and accepted as PROPOSED, with four edits.** They are lookup before mint (§1),
  "observation never mints" (§1), the v7 timestamp as an accepted cost (§1), and two corrections (§5, §8). Check 10 was
  added with them.
- The number is provisional until the record is accepted.
- **One text, two citations.** The base text is iagent's architect's, delivered by Chris on 2026-11-07. Lane 02 drafted
  this record from it. iagent aligns to this text under its own number, which its architect calls ADR-0067. Both sides
  cite this one text, and neither keeps a second copy.
- **What iagent has on disk today (read 2026-11-07).** There is no ADR-0067 and no ADR-0065 on any iagent branch, and
  no `graph_mapping`. This record names all three as forthcoming. It does not cite them as records until they exist.
- **The five items lane 02 left open are ruled by Chris, 2026-11-07** (see Rulings).

## Findings first

**1. Every record id today is a uuid5 over `asset_id`, under `uuid.NAMESPACE_URL`.** There are three minters, and
none of them carries an identity for the physical thing.

| Id | Where | Seed |
|---|---|---|
| CM discrepancy (episode) | `openddil-cm-service/src/events/asset_cm.py:581-585` | `episode\|{asset_id}\|{component}\|{fault_code}` |
| CM manual discrepancy | `asset_cm.py:561-565` | `manual\|{asset_id}\|{description}` |
| Egress occurrence (`event_id`) | `openddil-demo/egress/assembler.py:150-164` (`record_key`) | `{kind}\|{owning_tier}\|{asset}\|{component}\|{fault_code}\|{detected_at_ns}` |
| Egress episode (`episode_id`) | `assembler.py:167-174` (`episode_key`) | `{kind}\|{owning_tier}\|{asset}\|{component}\|{fault_code}` |

- **The two episode ids differ for the same fault.** The CM seed has no kind and no owning tier. The egress seed has
  both, and nothing maps one to the other.
  - **Ruled (Chris, 2026-11-07): CM's id is the right one, and the egress id carrying kind and tier is a bug.** Egress
    adopts CM's id. The fix belongs to the occurrence work (§5).

**2. The 2026-11-06 collision was a record id borrowing an entity-scoped key.**
- In `openddil-demo` `d155dd9` ("Egress: event_id is the occurrence id, episode_id spans occurrences"), the record
  key had been the episode id. Every event of an episode shared one id, so dedupe dropped revisions and re-files.
- ADR-0046's amendment of 2026-10-13 fixed the same shape a month earlier, at the posture re-send.
- Two instances of one shape is the reason this record states the scoping rule (§5) once, for every record kind.

**3. October's ids are protected by a test, not only by a sentence.**
- ADR-0046 §4 keys "one episode, one record" on the first-observed time. Its 2026-10-13 amendment keeps that identity
  "unchanged" at `episode_id`.
- `openddil-demo/egress/test_assembler.py:123-127` pins the October formula by literal, so a formula change fails
  loudly.
- Any new identity rule therefore has to leave every id already issued exactly as it is (§6).

**4. The registry has no identity column.**
- `asset_registry` (`openddil-stack/schema/migrations/20260604202813_phase8_asset_registry.sql:26-43`) holds
  `asset_id` (the primary key), the edge and region assignment, its source and times, the observed edge and
  `divergent`. `platform_variant` was added on 2026-10-06.
- It has no serial number, UII, external id or hull number. Nothing in the migrations or in the service names one.

**5. `asset_id` is opaque and is mapped at every boundary (ADR-0047, accepted).** An asset enters the fleet only by a
person's declaration (ADR-0050, proposed). That declaration is the act this record binds an identity to (§1).

**6. iagent's asset of record lives in a different id space.** It is the physical platform's URN in iagent's
catalog, not `asset_id` (ADR-0055 §6). Nothing maps one to the other today.

**7. Neither side has a vocabulary file that can be exported as written.**
- iagent's `ia-saf/policy/classification/dimensions.yaml` declares `dimensions: []`, with no `required` or
  `empty_means` key.
- No lifecycle status vocabulary exists as a file. The nearest is `iagent-mesh-sdk/iagent_mesh/lifecycle_status.py`, a
  Python module.

## Decision

### 1. One identity per thing

- **Each thing has exactly one identity.** It is a UUID version 7 (RFC 9562), written as the IRI `urn:uuid:<uuid>`.
- **"Thing" is any object, not only an asset.** That covers a physical asset, a component, a vocabulary term, a data
  product and a BOM item. The scope comes from DMRA 2.6 as iagent's architect read it (§8).
- **A declaration binds before it mints (Chris, 2026-11-07).**
  - **Most things already have an identity elsewhere.** A tank has a UII and a serial number in the maintenance system
    of record. A tier that minted a fresh identity on arrival would make OpenDDIL a second system of record for
    identity. That sidestep is ruled out.
  - **So the arrival declaration (ADR-0050) binds first.** The tier that holds it looks up every alias the declaration
    carries (UII, serial number, hull number) against the registry it holds (§3). If one resolves, the tier binds the
    observed `asset_id` to that existing identity, and mints nothing.
  - **It mints only when no alias resolves.** The tier then records itself as the minting authority, with its
    generator, on the row.
  - **A tier-minted identity is provisional against the system of record.** When the link to the system of record
    returns, the two are reconciled by declared equivalence (§4), never by matching.
  - **A vocabulary term or a data product is minted by the authority that owns the vocabulary or the catalog (ruled by
    Chris, 2026-11-07).**
    - Each authority has one generator.
    - The generator is recorded in the vocabulary file itself, at release.
    - For OpenDDIL's own vocabularies, the authority is the contracts repo.
  - **Observation never mints. A declaration may, after the lookup above, and the row names the generator.**
    - Every tier runs declaration intake, edges included, so an edge holding a declaration may mint.
    - An observation is kept under its `asset_id` until a declaration binds it.
- **It never encodes meaning.**
  - Nobody reads a site, nation, kind, tier or time from it. ADR-0047's opacity rule covers it as it covers `asset_id`.
  - Version 7's leading bits are a timestamp. That makes the identity sortable within one generator. They are never
    read as a fact about the thing.
  - **The timestamp is a stated cost, and it is accepted (Chris, 2026-11-07).** An identity that crosses the seam
    carries the minute it was declared, whether anyone reads it or not. A sortable index is worth that. The rule
    against reading it stands, and v4 for identities was considered and not taken.
- **Minting while severed.**
  - Version 7 is unique without coordination, so a severed tier holding a declaration can still mint. It does so only
    after the lookup, when no alias resolves against the registry it holds.
  - The row records which generator minted the identity, as a declared authority. This follows the idea behind
    MIP/JC3IEDM OIDs: a minting authority is itself declared, so an id minted apart can be traced to who minted it.
    The OID scheme itself is cited by concept and unread here.
  - If two severed tiers each mint an identity for one thing, that is reconciled by a declared equivalence (§4),
    never by matching.

### 2. Every other id is an alias, held as a row

- **An alias is a row:** `{scheme, value, authority, valid_from}`, with a `valid_to` once it stops holding (§4).
  - Examples of a scheme: a DIS entity id, `asset_id`, a serial number, an NSN, a PDM item number, a UII, a dataset
    URN.
  - **`asset_id` is an alias too.** Its scheme is the deployment's own, and its authority is the deployment.
- **Aliases are rows, not columns.** A new connected system adds rows and never a column. One asset's aliases, read
  together, are the mapping table Chris described: `asset_id`, the identity, the UII or serial number, and the URN
  each connected system uses. Each entry is a declaration with an owner and a date.
- **Schemes are registered.**
  - Each scheme has one row naming its owner and its value form, in the manner of an ISO/IEC 11179 registry.
  - A UII follows ISO/IEC 15459 and IUID marking under MIL-STD-130, with DoDI 8320.04. These are cited by concept.
- **An alias is never parsed** (ADR-0047). Its value is compared, hashed and stored. Nothing is derived from its form.
- **Events across the iagent seam carry both the `asset_id` and the identity.** The maintenance system and the failure
  reporting system then agree on which physical thing failed, by the UII alias, without either one parsing the
  other's id.

### 3. Lookups go from alias to identity, through a key that is an index

- **The lookup key is `UUIDv5(namespace = the scheme authority's namespace, name = the alias value)`.**
- **It is an index, never the identity.**
  - Any tier can compute it without a store.
  - Only a binding row says which identity it points to.
  - A lookup key is never written where an identity belongs (Check 3).
- An observation whose key finds no binding row is kept under its `asset_id`. Observation never mints (§1).

### 4. Reconciliation is by declared equivalence, with an owner

- **Two identities are the same thing only when someone declares it.** The equivalence is a row with the two
  identities, an owner, a date and a reason. In SKOS terms it is `skos:exactMatch` with an owner.
- **Never by string similarity.** No rule matches names, serial numbers or URNs to propose or apply an equivalence.
- **Two identities declared for one thing: neither wins by rule (ruled by Chris, 2026-11-07).**
  - The parent that sees both raises a named exception to both owners. This is the same path as two conflicting site
    declarations (the site-declaration design, §6).
  - A declared equivalence with an owner merges them.
    - One identity survives.
    - The other becomes an alias row of the survivor, with a `valid_to`. It is never deleted.
  - Nothing is chosen by recency, and nothing by tier rank.

### 5. Record ids are scoped to the entity, and never borrow its key

- **Episode:** a uuid5 over (identity, component, fault code).
- **Occurrence:** the episode plus `detected_at_ns`, as the agreed contract spells it.
- **Label key:** a content hash of the label (ADR-0055 §2).
- **The rule.** A record id is never an entity-scoped key reused as it is. An id that names one event carries what
  makes that event distinct. Finding 2 is what breaking this rule looks like.
- **Kind and owning tier are not in the episode id (ruled by Chris, 2026-11-07).**
  - An episode is the fault on the thing: entity, component and fault code.
  - Which kind carried a fault and which tier owns the record are attributes of the record. They are not attributes of
    the fault.
  - So CM's id is the episode id, and egress adopts it (finding 1). The two-eras rule (§6) covers that change as it
    covers the identity.
  - **The October test still holds.** The pinned literal tests the era-1 function for ids already issued. That function
    stays and the literal stays unedited. Only occurrences opened after the change take the new tuple.

### 6. Two id eras, and the rebinding row

- **Era 1 is every id issued today:** a uuid5 over `asset_id` (finding 1). Era 2 keys on the identity.
- **An episode keeps its era-1 id until its asset has a bound identity.**
- **The binding is a row, with a date:** `{asset_id, identity, bound_at, bound_by, declaration}`. Nothing is
  renumbered silently.
- **The first-occurrence rule holds.**
  - Every id already issued stays as issued, and the October test (finding 3) keeps passing unchanged.
  - **An episode open at the binding keeps its old id until it closes (ruled by Chris, 2026-11-07).** The rebinding
    row records the date. The next occurrence opens under the entity-scoped id.
- **The era is read from the binding row, never from the id.** A reader compares an episode's first-observed time with
  `bound_at`. The id itself encodes nothing (§1).

### 7. Datasets keep their URNs; the mapping lives in the registry

- **A dataset keeps its URN.** The URN is a locator, not an identity.
- **The mapping lives in the registry, never in the URN's text.** The architect's text calls it `graph_mapping`:
  column, then alias lookup, then node. It is forthcoming and is not yet a record.
- **This closes ADR-0055 §6's gap by declaration.** iagent's platform URN becomes an alias row of the platform's
  identity, under the catalog's scheme. It is never derived by parsing.

### 8. Declared relations: "sustained-under"

- **The relation:** a thing (an asset or a component, by identity) is sustained under program P, by OEM O, for scope
  S, with an owner and a date.
- **It is declared per asset and per component.**
  - A component reaches its OEM and its program through iagent's where-used graph, named by the architect as ADR-0065.
    ADR-0065 is forthcoming and not yet a record.
  - The nearest file is `setup/ontologies/product_structure_extension.ttl` (iagent ADR-0051).
- **Program at the funnel.**
  - **The edge never declares program** (ADR-0055 §5, ruled 2026-11-07).
  - **The hub composing an OEM-bound flow declares program as required at that boundary.** This uses the ADR-0055
    amendment on `required` and `empty_means` (§9).
  - The value is filled from the relation, in ADR-0055 §1a's order: the per-asset row, then a scoped rule (for example
    "every asset of type T in fleet F is sustained under P"), then nothing.
  - **Nothing means withheld, loud, as `dimension_missing`.**
- **Access and routing stay separate.**
  - `program` as an access dimension is in the label, and the PEP reads it.
  - "Sustained-under" is a routing relation, and egress reads it.
  - **The relation never writes the stored label.** If it did, a routing default would become an access grant.
  - **`program` goes on outbound records at that boundary only (ruled by Chris, 2026-11-07).** It is a relation
    declared at the funnel. No tier's stored label ever carries it.

### 9. `required` and `empty_means`, per deployment and per boundary

This is the ADR-0055 amendment drafted on 2026-11-07, in its types section. It is cited here and not restated. One
line: a deployment, and each egress destination it declares, may set `required` and `empty_means` per dimension, and a
required dimension that is empty at that boundary is withheld as `dimension_missing`.

### 10. Owed rows (not built)

- **A SKOS export of the dimension vocabulary and the lifecycle vocabulary.**
  - Each term gets an identity under §1, and an equivalence across the two sides is `skos:exactMatch` with an owner.
  - Its sources are named in finding 7. Neither side's file can be exported as written.
- **Declaration and downgrade records in PROV-O.** Expressed as an entity, an activity and an agent, by concept. iagent
  already aligns to PROV-O (its ADR-0019, ADR-0045 and ADR-0054).
- **DCAT and ODRL** for data products and their terms, later.

## Standards, cited by concept

Every standard below is cited by concept only.
- **No class or property names are asserted from memory.** Where one would be needed, it is marked unread.
- ADR-0055 §7 applies: carrying an identity, a label or a relation correctly is not accreditation to hold the data.

| Standard | Concept used here | Read by lane 02 |
|---|---|---|
| RFC 9562 | UUID v7 as the identity; v5 as the lookup key | Concept only |
| ISO/IEC 15459, IUID/UII under MIL-STD-130, DoDI 8320.04 | A physical item's unique identifier, as an alias | Concept only |
| ISO/IEC 11179 | A registry of schemes, each with an owner | Concept only |
| MIP/JC3IEDM (STANAG 5525) OIDs | Minting by a declared authority while severed | Concept only. The OID allocation itself is unread |
| BFO (ISO/IEC 21838-2), through IOF Core | The thing that an identity names | Unread. No IOF Core class is named here |
| ASD S-Series SX002D, AP242 on the PDM side | BOM items and part numbers as aliases | Unread. No SX002D class is named here |
| SKOS | Vocabularies; equivalence as `skos:exactMatch` with an owner | Concept only |
| PROV-O | Declaration and downgrade records | Concept only |
| STANAG 4774/4778, NIST SP 800-162, SP 800-53 AC-16 | Labels, as in ADR-0055 | As cited in ADR-0055 |
| EU 2013/488/EU, NATO C-M(2002)49 | Declared policies, as in ADR-0055 | As cited in ADR-0055 |
| SD-22, MIL-STD-3018, IEC 62402 | Obsolescence, which the where-used graph serves | Concept only |
| DCAT, ODRL | Data products and their terms, later | Concept only |
| **DMRA 2.6** (CDAO, March 2024, **draft, watermarked**) | UID as core service 1 of 15: unique, persistent, never reused, machine-readable, "ascribed to any object", with a multi-generator form (p.13, Fig. 8). Each CCV term gets a UID (p.14). xBOMs translate serial numbers and part numbers (p.15) | **Not read by lane 02.** The reading and page citations are iagent's architect's. "Sequenced" is met by v7 if it means monotonic within one generator |

## Check

Each check is a test or a script that a named workflow runs. A check that nothing runs does not count.
1. **October unchanged.** `test_assembler.py`'s pinned literal passes, unedited, after era 2 lands.
2. **Scoping.** For each record kind, no record id equals an entity-scoped key. Finding 2 is the failing case.
3. **Index is not identity.** No identity column holds a value that equals a lookup key computed from any alias.
4. **No parsing.** Alias values enter ADR-0047's CI allowlist rule: equality, hash and store only.
5. **No matching.** No code path creates an equivalence row except a declaration with an owner.
6. **Rebinding is a row.** Each era-2 id has a binding row for its asset with `bound_at` at or before the episode's
   first-observed time.
7. **Routing never writes access.** No write path from "sustained-under" reaches a stored label, and no stored label
   carries `program`.
8. **One episode id.** For one fault on one thing, CM's episode id equals egress's `episode_id`, for every episode
   opened after the change.
9. **Generators are declared.** Each released vocabulary file names its one generator.
10. **Lookup before mint.** A declaration carrying a UII that already resolves never mints. The failing case is a
    second identity row for a UII that the registry already binds.

## Rulings (were open items; Chris, 2026-11-07)

1. **Kind and owning tier come out of the episode id.** An episode is the fault on the thing. CM's id is the right
   one, and egress adopts it under the two-eras rule (§5, §6).
2. **An open episode keeps its old id until it closes.** The rebinding row records the date, and the next occurrence
   opens under the entity-scoped id (§6).
3. **Two identities declared for one thing: neither wins by rule.** It is raised as a named exception to both owners.
   An owned equivalence merges them, and the loser becomes an alias row with a `valid_to`. There is no recency rule and
   no tier rank (§4).
4. **`program` goes on outbound records at that boundary only.** No tier's stored label carries it (§8).
5. **Terms and data products are minted by the authority that owns the vocabulary or the catalog.** Each authority has
   one generator, recorded in the vocabulary file at release. For OpenDDIL's own vocabularies, that is the contracts
   repo (§1).

## What this does not establish

- Nothing is built: no identity table, no alias table, no binding row, no export.
- It changes no id issued today.
- It does not decide iagent's catalog, where-used graph or `graph_mapping`. Those are iagent's.
- It does not accredit anything (ADR-0055 §7).

## Related

- [ADR-0046](ADR-0046-maintenance-bridge-events-out-actions-in.md): one episode, one record; the 2026-10-13 amendment.
- [ADR-0047](ADR-0047-asset-id-is-opaque.md): `asset_id` is opaque, and every boundary has a mapper.
- [ADR-0050](ADR-0050-asset-arrivals-declare-and-expect.md): an arrival is a person's declaration.
- [ADR-0055](ADR-0055-a-label-is-a-set-of-declared-dimensions.md): labels, §1a precedence, the boundary amendment, and
  §7.
- iagent ADR-0067 (forthcoming, not yet a record): iagent's citation of this text.
- iagent ADR-0065 (forthcoming, not yet a record): the where-used graph.
