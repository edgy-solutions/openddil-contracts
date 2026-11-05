# Inventory: what supplies each view

Which declared artefact supplies which view's content, and which views have no source yet. Counts were read on 2026-11-02 from chart `openddil-demo` 0.1.160. They come from `helm template` and from reading files. Nothing here was observed running.

## Gaps first

1. **The public example's base values declare no kinds, no destinations and no routes, and leave releasability off.** `k8s/tier-node-values.yaml` alone renders no egress, and a kind check on it alone would prove nothing. Its public twin, `k8s/egress-values.yaml`, adds two kinds, two destinations and two routes. The twin is authored for the sample deployment and is definitive for that only; it attests to nothing about any other deployment. [`specimen/`](specimen/) holds the views rendered from it.
2. **A consumer group's topics are not declared.** The annotation gives broker and group only. The generator binds a group to topics only where a mounted config or environment variable says so, and names every other group as an exception. On the public bundle, 27 groups have no bound topic: the hub projector's groups, the Faust groups and the DIS mapper.
3. **Bridges write without declaring it.** A bridge writes to its parent's broker, and its workload annotation does not list those writes. This accounts for all 26 `writer-not-annotated` rows.
4. **The two keys that would close gaps 2 and 3 are not built.** [ADR-0054](../../decisions/ADR-0054-workload-annotations-declare-broker-use.md) defines the annotations the chart renders, and its decisions 5 and 6 are the next increment. [`tools/check_annotations.py`](tools/check_annotations.py) holds a render to that record, and no workflow runs it yet.
5. **A decision record's status line can lag the code.** ADR-0043 says it is not deployed anywhere, and the chart renders the gate when a deployment enables it. These views copy each record's words, and the marks are not re-verified.

## Artefact to view

| Artefact | Where | Supplies | How it is read |
|---|---|---|---|
| Tier template | `openddil-helm/openddil-demo/templates/tier-node.yaml` | Op-Sr, Rs-Sr, Rs-Cn | Render, by the generator |
| Workload annotations: produces-topics, consumer-groups | Chart render | Rs-Cn | Render, by the generator |
| `produces.yaml` | 8 repositories | Rs-Cn, indirectly | Not read by the generator. `openddil-helm/scripts/check-produces-declarations.py` holds it to the chart's annotations. |
| Consumer declarations | `openddil-helm/scripts/check_consumer_declarations.py` and its expected list | Rs-Cn, indirectly | Not read by the generator. The script holds the annotations to an expected list. |
| Bridge and projector config | Chart ConfigMaps | Rs-Cn | Render, by the generator: topics, groups, tables |
| Overlay kind schemas | `egress.kinds` in a deployment's values; the sample in the example bundle's `k8s/egress-values.yaml` | Rs-If, Op-If, Sc-Pr | Render, by the generator: `x-openddil` pointers |
| Egress routes | `egress.routes` in a deployment's values | Rs-Cn, Rs-If, Sc-Cn | Render, by the generator |
| Egress destinations | Destination entries in a deployment's values | Rs-Cn, Rs-If, Sc-Cn | Render, by the generator: display name, nations, accepts, asserted by and on. No other field is output. |
| Labelled tables | `releasability.labeledTables` in chart values | Rs-Cn, Sc-Cn | Values, by the generator |
| Proto contracts | `proto/`, 16 files and 68 messages | Op-If, Rs-If | By hand for now |
| Ontology files | `ontology/` | Op-If, Rs-If | By hand for now |
| Contract B | Defined in `decisions/DESIGN-2026-09-06-interface-contracts.md`; held by the kit in `openddil-customer-bundle-example/conformance/contract-b/`. There is no separate schema file. | Rs-If, Rs-Cn | By hand for now |
| Interface contracts | `decisions/DESIGN-2026-09-06-interface-contracts.md` | Op-Tx, Op-Cn, Rs-Cn | By hand |
| Decision records | `decisions/ADR-*.md` | Every view's Sources table | By hand. `tools/check_views.py` checks Proposed and design-only marks against each status line. |
| Alignment declared tables | ADR-0009, 0043, 0044, 0046, 0050, 0051, 0052, 0053 and the CoT design | Sd-Tx | By hand |
| Citations note | `decisions/CITATIONS-2026-09-08-standard-ontologies.md` | Sd-Tx | By hand |
| Roadmap note | `decisions/ROADMAP-2026-10-29-isolation-increments.md` | St-Rm-P, St-Tx | By hand |
| UAF 1.2 Appendix A | OMG formal/22-07-07 | [`APPENDIX-A.md`](APPENDIX-A.md), then `profiles.yaml` | Looked up 2026-11-02 |

## The UAF grid

Output names are those [Appendix A](APPENDIX-A.md) gives. Where the mapping is not one-to-one, `profiles.yaml` says which this repository selects.

### Written

| View | Main source | DoDAF 2.02 | NAF v4 |
|---|---|---|---|
| [Sm-Ov](views/Sm-Ov.md) | ADR-0021, 0022, 0033, 0039 | AV-1 | None in Appendix A |
| [Am-If](views/Am-If.md) | Generated from `ontology/` | AV-2 | A1 |
| [St-Tx](views/St-Tx.md) | ADR-0038, roadmap note | CV-2 | C1 |
| [St-Pr](views/St-Pr.md) | ADR-0038, 0039, 0040 | CV-1 | C2 |
| [St-Cn](views/St-Cn.md) | Generated from the roadmap note and `capability-record.yaml` | CV-4 | C3 |
| [St-Rm-P](views/St-Rm-P.md) | Roadmap note | CV-3 | Cr |
| [Op-Tx](views/Op-Tx.md) | ADR-0033, interface contracts | OV-1 | L1 |
| [Op-Sr](views/Op-Sr.md) | ADR-0022, 0023, 0033 | OV-2 | L2 |
| [Op-Cn](views/Op-Cn.md) | ADR-0021, 0043, 0046, interface contracts | OV-2, OV-3 | L3 |
| [Op-Pr](views/Op-Pr.md) | ADR-0030, 0043, 0046, 0050 | OV-5a, OV-5b | L4 |
| [Op-St](views/Op-St.md) | ADR-0044, 0050 | OV-6b | L5 |
| [Op-Sq](views/Op-Sq.md) | ADR-0043, 0046 | OV-6c | L6 |
| [Op-If](views/Op-If.md) | ADR-0009, 0026, 0029, 0044, 0046 | DIV-2 | L7 |
| [Op-Ct](views/Op-Ct.md) | ADR-0029, 0033, 0038, 0044, 0050, interface contracts | OV-6a | L8 |
| [Sv-Cn](views/Sv-Cn.md) | ADR-0041, 0043, 0046, interface contracts | SvcV-3a, SvcV-3b, SvcV-6 | S3 |
| [Rs-Tx](views/Rs-Tx.md) | Generated from `model/openddil.sysml`; ADR-0033, 0046 | SV-1, SV-2 | P1 |
| [Rs-Sr](views/Rs-Sr.md) | ADR-0021, 0033 | SV-1, SV-2 | P2 |
| [Rs-Cn](views/Rs-Cn.md) | Generated from a bundle; ADR-0021, 0030, interface contracts | SV-3, SV-6 | P3 |
| [Rs-Pr](views/Rs-Pr.md) | ADR-0029, 0030, 0038, 0043, 0046 | SV-4 | P4 |
| [Rs-St](views/Rs-St.md) | ADR-0026, 0044 | SV-10b | P5 |
| [Rs-Sq](views/Rs-Sq.md) | ADR-0029, 0043, 0046 | SV-10c | P6 |
| [Rs-If](views/Rs-If.md) | Proto contracts, ontology files | DIV-3 | P7 |
| [Rs-Ct](views/Rs-Ct.md) | ADR-0033, 0046 | SV-10a | P8 |
| [Rs-Tr](views/Rs-Tr.md) | Op-Pr joined to Rs-Pr | SV-5a, SV-5b | L4-P4 |
| [Sc-Sr](views/Sc-Sr.md) | ADR-0029, 0043, 0045 | None in Appendix A | None in Appendix A |
| [Sc-Cn](views/Sc-Cn.md) | ADR-0029, 0043, 0045, 0046 | None in Appendix A | None in Appendix A |
| [Sc-Pr](views/Sc-Pr.md) | ADR-0043, 0046, 0053 | None in Appendix A | None in Appendix A |
| [Sd-Tx](views/Sd-Tx.md) | Alignment declared tables, citations note | StdV-1 | A8 |

### No source yet

| View | What is missing | Would export |
|---|---|---|
| St-Rm-Dm Strategic deployment roadmap | The roadmap note has no dates, deliberately | CV-5, Cr |
| Pj-Sr, Pj-Tx, Pj-Rm, Pj-Tr Projects | No project records in the public corpus | PV-1, PV-2, PV-3, Lr |
| Ps-* Personnel | No organisation. The public user list is fiction and has only roles. | OV-4 |
| Sd-Rm Standards roadmap | Only the CCO roadmap note in the citations note | StdV-2, A8 |
| Me-Pm Metrics | Figures are scattered through records with no register | SV-7, SvcV-7, C7, S7 |
| Ar-* Actual resources | Deployment facts, which stay private. Slots only. | |
| Sc-Ct Security-Constraints | ADR-0053 lists detectors, and no risk assessment exists | SecV-1 |

Appendix A's own tables label a few rows inconsistently. [`APPENDIX-A.md`](APPENDIX-A.md) lists each one and how it is read here.

## Declaration exceptions, by bundle

Each is named row by row in the generator's Exceptions section. None of these is a fault in a running system: each says a declaration is absent.

Counts are from chart 0.1.161.

| Exception | Base values | With the public twin |
|---|---|---|
| writer-not-annotated | 26 | 26 |
| group-without-topic | 27 | 27 |
| consumer-without-writer | 16 | 12 |
| writer-without-consumer | 57 | 52 |
| labels-not-declared (rows) | 34 | 35 |
| workload-no-declaration | 18 | 24 |
| destination-without-entry | 0 | 0 |
| releasability-disabled | 1 | 0 |

[`annotation-exceptions.yaml`](annotation-exceptions.yaml) lists the writer-not-annotated, group-without-topic and workload-no-declaration rows for the twin, each class with its reason.

## Slots

[`slots.yaml`](slots.yaml) lists every slot. Thirteen have no declared artefact and need a person to write them. Those are the facts a framework cannot know, and they are also what a deployment's architecture work would start from. Each line below names the declaration that would fill one of them, and the artefact it would live in. None of these exists yet.

| Slot | Declaration that would fill it | Artefact |
|---|---|---|
| `mission-thread` | A mission-thread statement beside the system's name, in the deployment's own words | Bundle values, under `system` beside `system.name`. The chart reads no such key today. |
| `operator-roles` | Each role that signs in at a tier, with the entitlements it holds there | The deployment's user and role file, the one each tier's policy decision point loads |
| `sustainment-system-of-record` | The system the read pipeline extracts from, by name | The integrator's private overlay that configures the Contract B read pipeline. The `source` field on parts records would then carry it. |
| `feeds` | An owner for each ingress definition | Bundle ingress definitions, one owner field on each |
| `classification-scheme` | The marking scheme the deployment applies, and its levels | The overlay's releasability values. Nothing evaluates a scheme today. |
| `standards-editions` | Each standard, the edition the deployment binds, and the artefact that binds it | A standards-profile file in the bundle. The ontology already pins one reference edition. |
| `attribute-bindings` | For each standard, which field maps to which of its attributes | A binding table per standard in the bundle. The kinds' `x-openddil` pointers bind fields to the picture, not to a standard. |
| `link-characteristics` | Bandwidth, latency and expected outage for each uplink | Chart values, an entry per uplink under `edges[]`. No such keys exist today. |
| `severance-test-results` | One severance result per uplink, with its date | A deployment-owned readiness record, shaped like the one `render_profile.py --readiness` reads |
| `measured-results` | Each measured figure with its conditions and date | The same deployment-owned readiness record |
| `approval-authorities` | Who approves architecture change | An owners file in the deployment's private overlay. Release and work-action approvers already resolve through the intake's approver entitlements in policy data. |
| `capabilities-in-scope` | The capabilities the deployment fields, by name | Bundle values, a list of capability names checked against the model's capability taxonomy |
| `increment-dates` | A date for each roadmap increment | A deployment plan file keyed by the roadmap note's increment names. The note itself stays dateless. |
