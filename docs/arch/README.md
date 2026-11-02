# Architecture views

The OpenDDIL architecture as framework views, modelled in UAF 1.2. The content lives once, in [`views/`](views/) and [`model/`](model/). DoDAF 2.02 and NAF v4 are output profiles that rename and select those views.

This is a framework description. A deployment fills the `{{slot:name}}` placeholders from its bundle or a private file; [`slots.yaml`](slots.yaml) lists every slot and where its value comes from. Nothing here describes a real deployment until those are filled.

[`INVENTORY.md`](INVENTORY.md) says which declared artefact supplies each view, and which views have no source yet.

## The views

| | Taxonomy | Structure | Connectivity | Processes | States | Information | Roadmap | Traceability | Summary |
|---|---|---|---|---|---|---|---|---|---|
| **Summary** | | | | | | | | | [Sm-Ov](views/Sm-Ov.md) |
| **Strategic** | [St-Tx](views/St-Tx.md) | | | | | | [St-Rm-P](views/St-Rm-P.md) | | |
| **Operational** | [Op-Tx](views/Op-Tx.md) | [Op-Sr](views/Op-Sr.md) | [Op-Cn](views/Op-Cn.md) | [Op-Pr](views/Op-Pr.md) | [Op-St](views/Op-St.md) | [Op-If](views/Op-If.md) | | | |
| **Resources** | | [Rs-Sr](views/Rs-Sr.md) | [Rs-Cn](views/Rs-Cn.md) | [Rs-Pr](views/Rs-Pr.md) | | [Rs-If](views/Rs-If.md) | | [Rs-Tr](views/Rs-Tr.md) | |
| **Security** | | [Sc-Sr](views/Sc-Sr.md) | [Sc-Cn](views/Sc-Cn.md) | [Sc-Pr](views/Sc-Pr.md) | | | | | |
| **Standards** | [Sd-Tx](views/Sd-Tx.md) | | | | | | | | |

## How to read the marks

Every view has a Sources table with a Decision and an Evidence column. Both copy the words of the decision record they cite. They were not re-verified against a running system, and a status line can lag the code.

| Decision | Meaning |
|---|---|
| Accepted | The record says accepted, including as amended. |
| Proposed | The record says proposed. |
| Standing | A standing engineering position. |
| Positioning | Accepted, as a statement of what the system is and is not. Nothing follows from it directly. |
| Anticipated | The record names the capability as anticipated, not committed. |
| Design note | A design document and not a decision record. |
| Roadmap note | The roadmap note, which says it is not a decision. |

| Evidence | Meaning |
|---|---|
| Measured under compose | The record says built and measured under compose. It does not say deployed. |
| Built, unit-tested | The record says built and unit-tested, not run against live services. |
| Built | The record says done or implemented. |
| Partial | The record's own reading says partly implemented. |
| Declared | Read from a chart render. Nothing was observed running. |
| Pending | The record says implementation is pending or generalisation is deferred. |
| Fenced | The record names it and fences it off. |
| Design only | The record says design only. |
| Nothing built | The record says nothing is built. |
| Not stated | The record does not say. Read its body before relying on the row. |

## Models and diagrams

[`model/openddil.sysml`](model/openddil.sysml) holds the structure in SysML v2 textual notation. A view pulls a package in with a `<!-- model: Package -->` marker, and the renderer inlines it. GitHub does not render SysML, so anything meant to be looked at as a picture is Mermaid in the view. On 2026-11-02 the file parsed with every name resolved under OMG's SysML v2 pilot implementation 0.63.1. That check was run by hand and is not part of `check_views.py`.

## Running the tools

Python 3.10 or later with PyYAML, and `helm` for a real render. Nothing here reaches a cluster.

Generate the data-exchange view from a bundle:

```sh
python docs/arch/tools/data_exchange.py \
  --chart ../openddil-helm/openddil-demo \
  --values ../openddil-customer-bundle-example/k8s/tier-node-values.yaml \
  --values docs/arch/tools/testdata/example-overlay.yaml \
  --profile dodaf202 --check
```

`--check` fails when a tier, kind or route has no row. The public example bundle declares no kinds, so running it alone needs `--allow-no-kinds "<reason>"`. That exception goes red as soon as kinds appear. The example overlay is fiction and exists to exercise the kind rows.

Render a profile, then check the views:

```sh
python docs/arch/tools/render_profile.py --profile naf4
python docs/arch/tools/check_views.py
```

Output goes to `docs/arch/out/<profile>/`, which is not committed. To fill slots from a private file, pass `--slots FILE` and keep the output out of this repository.

Run the tests:

```sh
python -m unittest discover -s docs/arch/tools -p "test_*.py"
```

The integration tests need `helm`, and look for the chart and the example bundle beside this repository or under `OPENDDIL_REPOS`. They print why when they skip.

## Profile mapping

[`APPENDIX-A.md`](APPENDIX-A.md) is the mapping from UAF 1.2 Appendix A, formal/22-07-07, Tables 2:1, 2:3 and 2:5, and the only copy of it. `exports` in [`profiles.yaml`](profiles.yaml) selects from it, and `tools/check_views.py` fails on an export the table does not name. The mapping is not one-to-one. A view a profile cannot name is listed in that profile's `NOT-EXPORTED.md` and is not dropped silently.

The security views have no DoDAF 2.02 or NAF 4.0 target. Appendix A maps them only to DNDAF SecV views.

The data-exchange view sits in Resources-Connectivity, where Appendix A names it: SV-6 under DoDAF 2.02, P3 under NAF v4. Resources-Information exports as DIV-3 and P7. Under DoDAF 2.02 the generated table is its own file, SV-6, and SV-3 carries the rest of the view. NAF v4 names one output for the whole view, so P3 holds both.
