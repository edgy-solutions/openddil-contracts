# Standard-ontology citations for the semantic-layer ADR

**Fetched 2026-09-08, not recalled.** Anything I could not verify against a
published source is marked so, rather than stated with borrowed confidence.
The advisor's knowledge of CCO and IOF was flagged as dated; mine was too, and
on IOF it was wrong in a way a search alone would have preserved.

## Verified

**BFO / CCO — Common Core Ontologies**
- Repository: https://github.com/CommonCoreOntology/CommonCoreOntologies
- Licence: **BSD-3-Clause** (repository metadata)
- Governance: a **governance board plus a developers group**, "members come
  from academia, government, US national laboratories, and commercial
  industry"
- Standardisation: "CCO is currently being evaluated as a mid-level ontology
  standard by the **IEEE Standards Association under PAR3195.1**" — an active
  evaluation, not a completed standard
- **Roadmap, and this is the material finding:** CCO **3.0** is expected by
  **31 December 2026** and incorporates **GeoSPARQL, QUDT and a refactoring of
  information**; CCO **4.0** is expected **30 June 2027**, and *it is the
  recommendation of the CCO Governance Board that users wait to update
  following the 4.0 release.*
- **Consequence for the ADR:** adopting CCO now means adopting a version its
  own board expects to restructure twice, and which will absorb two of the
  vocabularies we would otherwise cite separately. Align to CCO *concepts* at
  rung 2 and defer any machine-consumable projection (rung 3) past 4.0, or
  accept a rewrite. Not a reason to avoid CCO — a reason to time it.

**IOF — Industrial Ontologies Foundry, maintenance module**
- Repository: `iofoundry/ontology` (the modules were consolidated; there is
  **no** `iofoundry/ontology-maintenance` repo — that URL 404s)
- Current release: **Release_202603, published 2026-09-03** — four days before
  this citation. A web search reported the maintenance ontology as most
  recently published in **2024**; fetching the repository directly corrected
  that by two years.
- Licence: **MIT**
- Maintenance module: `maintenance/Maintenance.rdf`
- Namespace: `https://spec.industrialontologies.org/ontology/202603/maintenance/`
  (versioned IRI — the release number is *in* the namespace, so an alignment
  must cite which release it aligned to)

**W3C SOSA / SSN**
- https://www.w3.org/TR/vocab-ssn/ — **W3C Recommendation, 19 October 2017**
  (link errors corrected 08 December 2017)
- Namespaces: SSN `http://www.w3.org/ns/ssn/`, SOSA `http://www.w3.org/ns/sosa/`

**W3C PROV-O**
- https://www.w3.org/TR/prov-o/ — **W3C Recommendation, 30 April 2013**
- Namespace: `http://www.w3.org/ns/prov#`
- Core classes: `prov:Entity`, `prov:Activity`, `prov:Agent`
- Core properties: `prov:wasGeneratedBy`, `prov:wasDerivedFrom`,
  `prov:wasAttributedTo`

**OGC GeoSPARQL**
- Current approved version **1.1**, OGC Doc No. **22-047r1**, an International
  Standard. Namespace based on `https://www.opengis.net/def/geosparql/`.
- **Not verified:** the exact approval date. The OGC standard page did not
  state it in fetched content.

**IC ISM — attribute semantics**
- `ownerProducer`: ISO 3166-1 **trigraphs** of the owner/producer countries
  and/or CAPCO-specified **tetragraphs** of international organisations
- `releasableTo`: one or more countries and/or international organisations to
  which classified information may be released, per an originator's
  determination under established foreign-disclosure procedures
- For the `REL` abbreviation the trigraphs are omitted from the marking and
  placed in `releasableTo`
- `ownerProducer` is **required** within `SecurityAttributesGroup` and
  **optional** within `SecurityAttributesOptionGroup`
- **Not verified:** the current ISM.XML DES version number. Sources reachable
  from open search are mirrors of IC-ISM-v2 schemas hosted by third parties
  (OGC, FinCEN); the authoritative CAPCO/ODNI register was not fetched.

## Not verified — do not cite without checking

- **QUDT** current release and namespace. Not fetched this pass.
- **OWL-Time** current Recommendation date. Not fetched this pass.
- **JC3IEDM / MIP Information Model** current edition. Not fetched; NATO MIP
  material is typically behind registration, so expect this to need a
  different route than a public fetch.
- **GeoSPARQL 1.1 approval date** (above).
- **ISM.XML DES version** (above).

## One methodological note worth keeping

The IOF search result and the IOF repository disagreed by two years, and the
search result was the plausible one. `ontology-maintenance` is exactly the
repository name a reasonable person would guess, and it does not exist. Both
errors would have survived into an ADR as confident prose.

*Fetch before citing* is the same rule as *fetch before reporting board
state*, applied to the literature.

---

## Annex note — FD/FI concepts and where they align

Added 2026-09-08 alongside the fault-detection / fault-isolation reframing:

* **IOF-MRO** (Release_202603, namespace
  `https://spec.industrialontologies.org/ontology/202603/maintenance/`) —
  failure event, fault state, failure mode, component. It is the reason this
  corpus now distinguishes **failure** (the event, a loss of function) from
  **fault** (the underlying state): the formal ontology separates them, and
  the FD/FI metrics cannot be stated without that separation.
* **CCO artifact-parts** — the wear-component manifest is mereology, so the
  manifest's "declared present / declared absent / no manifest" trichotomy
  aligns to artifact part-of assertions.
* **PROV-O** — the returned advisory cites a reasoning-plane graph node.
  `AdvisoryProvenance` with a reasoning-plane basis is
  `prov:wasDerivedFrom` a `prov:Entity` that is the TM node.

**And the forward-compatibility note the ADR should carry:** CCO 3.0
(expected 2026-12-31) *incorporates GeoSPARQL and QUDT*. So aligning to
GeoSPARQL and QUDT **directly, now** moves toward CCO's own plan rather than
away from it — there is no reason to defer those two behind CCO 4.0. Only the
CCO-specific alignment waits.
