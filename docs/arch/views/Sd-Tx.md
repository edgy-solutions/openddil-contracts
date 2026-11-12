# Standards-Taxonomy (Sd-Tx)

The standards the decision records align with, and how strongly. Alignment is by concept name only. Field names stay local to this architecture, and a binding is owed before any field is frozen. Editions: {{slot:standards-editions}}. Bindings: {{slot:attribute-bindings}}.

No row here is a conformance claim. The condition-monitoring, built-in test and usage rows sit at the rung their read supports, and ADR-0059 §1 says how much of each was read.

This view is also the Standards-Profile: its StdV-1 export lists the same rows.

| Standard | Used for | Rung | Cited by |
|---|---|---|---|
| EIA-649, NATO ACMP-2000 | Configuration status accounting | Concept aligned | ADR-0009, ADR-0051 |
| ISO 3166-1 alpha-3 | Nation codes in labels | Concept aligned | ADR-0029, CoT design |
| STANAG 4774, STANAG 4778 | Confidentiality label concepts; not implemented | Declared intent | ADR-0029, CoT design |
| IC ISM | Security marking vocabulary | Citation verified | Citations note, CoT design |
| JC3IEDM, MIP | Status vocabulary | Declared intent, not fetched | ADR-0044, ADR-0050, CoT design |
| DIS, IEEE 1278.1 | Entity state, fire and detonation signals | Concept aligned | ADR-0044, ADR-0048 |
| ASD S5000F | In-service data feedback | Concept aligned | ADR-0044, ADR-0046, ADR-0050, ADR-0051, ADR-0052 |
| MIMOSA OSA-CBM | State detection, health assessment, advisory | Concept aligned | ADR-0046, ADR-0059 |
| MIMOSA OSA-EAI, CCOM | Enterprise asset information; component names only | Declared intent, definitions unread | ADR-0059 |
| MIL-HDBK-2155 | Failure reporting, closure verification | Concept aligned | ADR-0051, ADR-0059 |
| MIL-HDBK-2165 | Built-in test, fault detection and isolation, ambiguity group, false alarm, cannot duplicate | Concept aligned | ADR-0059 |
| MIL-STD-1309 | Test and diagnosis terms | Declared intent, unread | ADR-0059 |
| IEEE 1232, IEC 62243 | Diagnostic model interchange | Declared intent, preview only | ADR-0059 |
| ARINC 624 | Onboard maintenance system | Declared intent, abstract only | ADR-0059 |
| ISO 14224 | Failure mode, mechanism and cause; failure classes | Declared intent, definitions unread | ADR-0059 |
| IEC 60812 | Failure mode | Concept aligned, one term read | ADR-0059 |
| MIL-STD-1388-2B | Usage meters | Concept aligned | ADR-0051, ADR-0059 |
| MIL-STD-882E | Hazard and risk vocabulary | Concept aligned | ADR-0052 |
| NIST SP 800-82, MITRE ATT&CK for ICS | Control-system detection vocabulary | Concept aligned | ADR-0053 |
| STIX 2.1 | Indicators through the gate | Concept aligned | ADR-0053 |
| CJCSM 6510.01 | Incident handling vocabulary | Concept aligned | ADR-0053 |
| RFC 9562 | UUID v7 as an identity, v5 as a lookup key | Concept aligned | ADR-0056 |
| ISO/IEC 15459, MIL-STD-130 IUID, DoDI 8320.04 | Item identifiers, held as aliases | Concept aligned | ADR-0056 |
| ISO/IEC 11179 | A registry of identifier schemes, each with an owner | Concept aligned | ADR-0056 |
| SKOS | Vocabularies, and equivalence with an owner | Concept aligned | ADR-0056 |
| SD-22, MIL-STD-3018, IEC 62402 | Obsolescence, served by the where-used graph | Concept aligned | ADR-0056 |
| DCAT, ODRL | Data products and their terms; owed | Declared intent | ADR-0056 |
| DMRA 2.6 | A unique identifier as a core data service; the edition read is a draft | Concept aligned | ADR-0056 |
| ISO 13374 | Reading of the condition-monitoring blocks; block names from a secondary source | A reading, not conformance | ADR-0038, ADR-0059 |
| ISO 17359 | A condition-monitoring programme | Declared intent, abstract only | ADR-0059 |
| ISO 13381-1 | Prognosis, remaining useful life, predictive horizon; the 2015 edition, withdrawn, and the 2025 edition unread | Concept aligned, terms read | ADR-0059 |
| PHM prognostic metrics (IJPHM 2010) | Scoring remaining-life predictions | Concept aligned | ADR-0059 |
| UCUM | Unit codes on quantities and usage meters | Concept aligned | ADR-0013, ADR-0059 |
| FCAPS (ITU-T M.3400) | The frame for network state as an input: fault and performance only | Declared intent, unread | ADR-0059 |
| Prometheus exposition format | The outbound format for the system's own health | Concept aligned, documentation read | ADR-0059 |
| Alertmanager webhook and inhibition | One supported input format for a network management system; muting symptoms below a severed link | Concept aligned, documentation read | ADR-0059 |
| Prometheus Remote-Write 1.0 | Upward catch-up of a tier's metrics after a cut | Concept aligned, specification read in part | ADR-0059 |
| Cursor on Target | Bridge shape | Not in the citations note | CoT design |
| BFO, CCO, IOF maintenance, W3C SOSA/SSN, PROV-O, OGC GeoSPARQL | Ontology alignment | Citation verified | Citations note, ADR-0059 |
| ROMAIN, ISO 15926 | Maintenance and lifecycle ontologies | Declared intent, unread | ADR-0059 |
| QUDT, OWL-Time | Ontology alignment | Not verified | Citations note |

Editions the citations note could not verify: the JC3IEDM edition, the date of GeoSPARQL 1.1 and the ISM.XML DES version.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| The rungs for the ontologies and IC ISM | [Citations note](../../../decisions/CITATIONS-2026-09-08-standard-ontologies.md) | Design note | Not stated |
| The configuration row | [ADR-0009](../../../decisions/ADR-0009-configuration-management-data-model.md) | Accepted | Not stated |
| The status rows | [ADR-0044](../../../decisions/ADR-0044-lifecycle-two-columns-no-deletes.md) | Proposed | Not stated |
| The label rows | [ADR-0029](../../../decisions/ADR-0029-coalition-releasability-abac-enforcement.md), [CoT design](../../../decisions/DESIGN-2026-10-01-cot-bridge.md) | Accepted | Not stated |
| The maintenance rows | [ADR-0046](../../../decisions/ADR-0046-maintenance-bridge-events-out-actions-in.md) | Accepted | Not stated |
| The failure rows | [ADR-0051](../../../decisions/ADR-0051-failure-records-for-fracas.md) | Accepted | Status line |
| The identity rows | [ADR-0056](../../../decisions/ADR-0056-one-identity-per-thing-every-other-id-is-an-alias.md) | Proposed | Status line |
| The hazard row | [ADR-0052](../../../decisions/ADR-0052-safety-states-and-release-interlocks.md) | Accepted | Status line |
| The detection rows | [ADR-0053](../../../decisions/ADR-0053-logistics-cyber-detection-as-surfaced-disagreement.md) | Accepted | Status line |
| The ISO 13374 reading | [ADR-0038](../../../decisions/ADR-0038-anticipated-capability-envelope.md) | Accepted | Not stated |
| The condition-monitoring, built-in test, usage and network-state rows | [ADR-0059](../../../decisions/ADR-0059-condition-monitoring-bit-and-usage-alignment.md) | Proposed | Status line |
| Arrival alignment | [ADR-0050](../../../decisions/ADR-0050-asset-arrivals-declare-and-expect.md) | Proposed | Not stated |
| Munition signal alignment | [ADR-0048](../../../decisions/ADR-0048-effector-tracking-from-fire-and-detonation.md) | Accepted | Not stated |
