# Architecture views

The OpenDDIL architecture as framework views, modelled in UAF 1.2. The content lives once, in [`views/`](views/) and [`model/`](model/). DoDAF 2.02 and NAF v4 are output profiles that rename and select those views.

This is a framework description. A deployment fills the `{{slot:name}}` placeholders from its bundle or a private file; [`slots.yaml`](slots.yaml) lists every slot and where its value comes from. Nothing here describes a real deployment until those are filled.

[`INVENTORY.md`](INVENTORY.md) says which declared artefact supplies each view, and which views have no source yet.

## The views

| | Taxonomy | Structure | Connectivity | Processes | States | Sequences | Information | Constraints | Roadmap | Traceability | Summary |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Architecture management** | | | | | | | [Am-If](views/Am-If.md) | | | [Am-Tr](views/Am-Tr.md) | |
| **Summary** | | | | | | | | | | | [Sm-Ov](views/Sm-Ov.md) |
| **Strategic** | [St-Tx](views/St-Tx.md) | | [St-Cn](views/St-Cn.md) | [St-Pr](views/St-Pr.md) | | | | | [St-Rm-P](views/St-Rm-P.md) | | |
| **Operational** | [Op-Tx](views/Op-Tx.md) | [Op-Sr](views/Op-Sr.md) | [Op-Cn](views/Op-Cn.md) | [Op-Pr](views/Op-Pr.md) | [Op-St](views/Op-St.md) | [Op-Sq](views/Op-Sq.md) | [Op-If](views/Op-If.md) | [Op-Ct](views/Op-Ct.md) | | | |
| **Services** | | | [Sv-Cn](views/Sv-Cn.md) | | | | | | | | |
| **Resources** | [Rs-Tx](views/Rs-Tx.md) | [Rs-Sr](views/Rs-Sr.md) | [Rs-Cn](views/Rs-Cn.md) | [Rs-Pr](views/Rs-Pr.md) | [Rs-St](views/Rs-St.md) | [Rs-Sq](views/Rs-Sq.md) | [Rs-If](views/Rs-If.md) | [Rs-Ct](views/Rs-Ct.md) | | [Rs-Tr](views/Rs-Tr.md) | |
| **Security** | | [Sc-Sr](views/Sc-Sr.md) | [Sc-Cn](views/Sc-Cn.md) | [Sc-Pr](views/Sc-Pr.md) | | | | | | | |
| **Standards** | [Sd-Tx](views/Sd-Tx.md) | | | | | | | | | | |

## How to read the marks

Every view has a Sources table with a Decision and an Evidence column. In every view but St-Rm-P, both copy the words of the decision record they cite, with one exception. When the cited record's status line says design only, plan only or nothing built, the Evidence cell says `Status line` and the value is read from the record when the view is rendered ([`tools/marks.py`](tools/marks.py)). So every view that cites a record shows the same Evidence for it, and a change to the status line changes all of them together. The marks were not re-verified against a running system, and a status line can lag the code.

| Decision | Meaning |
|---|---|
| Accepted | The record says accepted, including as amended. |
| Proposed | The record says proposed. |
| Standing | A standing engineering position. |
| Positioning | Accepted, as a statement of what the system is and is not. Nothing follows from it directly. |
| Anticipated | The record names the capability as anticipated, not committed. |
| Decision pending | No decision record decides it yet. The row names what the decision waits on and links its open row. |
| Design note | A design document and not a decision record. |
| Roadmap note | The roadmap note, which says it is not a decision. |
| Generated | Computed when the view is rendered, not written in it. |

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
| Status line | In the view's source only: read from the cited record's status line when the view is rendered, as Design only or Nothing built. |
| Generated | Computed when the view is rendered, not written in it. |

## Models and diagrams

[`model/openddil.sysml`](model/openddil.sysml) holds the structure in SysML v2 textual notation. A view pulls a package in with a `<!-- model: Package -->` marker, and the renderer inlines it. GitHub does not render SysML, so anything meant to be looked at as a picture is Mermaid in the view. On 2026-11-02 the file parsed with every name resolved under OMG's SysML v2 pilot implementation 0.63.1. [`sysml-model.yml`](../../.github/workflows/sysml-model.yml) repeats that parse on any change under `model/`, with the parser pinned, and also requires the parser to refuse a copy with a syntax fault and a copy with an unresolved reference.

## Running the tools

Python 3.10 or later with PyYAML, and `helm` for a real render. Nothing here reaches a cluster.

Generate the data-exchange view from a bundle:

```sh
python docs/arch/tools/data_exchange.py \
  --chart ../openddil-helm/openddil-demo --release openddil \
  --values ../openddil-customer-bundle-example/k8s/tier-node-values.yaml \
  --values ../openddil-customer-bundle-example/k8s/egress-values.yaml \
  --profile dodaf202 --check
```

`--release` is the Helm release the render is made under, and the tools strip it from the names they read. `--chart` needs it. With `--rendered`, it may be left out when every document carries the same `app.kubernetes.io/instance` label.

`--check` fails when a tier, kind or route has no row. `tier-node-values.yaml` declares no kinds, so running it without the twin needs `--allow-no-kinds "<reason>"`. That exception goes red as soon as kinds appear. The example overlay is fiction and exists to exercise the kind rows.

Render a profile, then check the views:

```sh
python docs/arch/tools/render_profile.py --profile naf4
python docs/arch/tools/check_views.py \
  --chart ../openddil-helm/openddil-demo --release openddil \
  --values ../openddil-customer-bundle-example/k8s/tier-node-values.yaml \
  --values ../openddil-customer-bundle-example/k8s/egress-values.yaml \
  --readiness ../openddil-helm/scripts/RECORDING-READINESS.md \
  --barred docs/arch/tools/barred-sample.txt
```

`check_views.py` needs all five inputs (the chart, its values, the release, the readiness doc and the barred list) or `--allow-partial REASON`. Without either it exits 2, because a check that quietly runs fewer rules is the bug it exists to catch. A partial run says what it skipped in its `ok:` line. [`check-views.yml`](../../.github/workflows/check-views.yml) runs it in full.

[`specimen/`](specimen/) holds all three profiles rendered from the public twin, `k8s/egress-values.yaml` in the example bundle. [`tools/test_specimen.py`](tools/test_specimen.py), beside the generator, compares it with a fresh render, and `check-views.yml` runs it. It ignores the `Chart:` line, so a chart version bump alone passes and a content change fails. To refresh it:

```sh
python docs/arch/tools/refresh_specimen.py
```

Check the workload annotations against a render ([ADR-0054](../../decisions/ADR-0054-workload-annotations-declare-broker-use.md)):

```sh
python docs/arch/tools/check_annotations.py \
  --chart ../openddil-helm/openddil-demo --release openddil \
  --values ../openddil-customer-bundle-example/k8s/tier-node-values.yaml \
  --values ../openddil-customer-bundle-example/k8s/egress-values.yaml
```

This needs a chart checkout and `helm`, so `check_views.py` does not run it, and no workflow runs it yet. [`annotation-exceptions.yaml`](annotation-exceptions.yaml) names the rows it does not cover.

Output goes to `docs/arch/out/<profile>/`, which is not committed. To fill slots from a private file, pass `--slots FILE` and keep the output out of this repository.

Run the tests:

```sh
python -m unittest discover -s docs/arch/tools -p "test_*.py"
```

The integration tests need `helm`, and look for the chart and the example bundle beside this repository or under `OPENDDIL_REPOS`. They print why when they skip.

## The HTML export

`render_html.py` writes the views as one self-contained HTML file, from the same source and by the same generator as the markdown profiles: it builds a `render_profile.py` renderer for each profile and takes each view's text from it. The front page is the UAF grid, with the views that are written linked and the ids Appendix A names but nobody has written shown empty. Each view has a page. Mermaid is drawn to inline SVG when the file is built, so the file needs no network to read. The exceptions table is collapsed, there is a search box and a print stylesheet, and the DoDAF and NAF profiles are a toggle that changes names and the grid only. Every page says the chart version, a digest of the values files read, the date and that the contents are declared, not measured.

```sh
cd docs/arch/tools/export && npm ci && cd -
python docs/arch/tools/render_html.py --out out/openddil-architecture.html \
  --chart ../openddil-helm/openddil-demo --release openddil \
  --values ../openddil-customer-bundle-example/k8s/tier-node-values.yaml \
  --values ../openddil-customer-bundle-example/k8s/egress-values.yaml
```

It needs Node 22, Chrome (`PUPPETEER_EXECUTABLE_PATH`) and `markdown-it-py==4.0.0`. All of `--chart`, `--values` and `--release` are required, so there is no partial export. A diagram that does not draw fails the build and names the view.

Check it with `check_export.py --export FILE --barred FILE`: the view count equals `check_views.py`'s, no barred value is in the file, every page carries its provenance, nothing refers to the network, the file is under 16 MB, no link is dead, every Mermaid fence became an SVG, and the exception table is there. `--relabel FILE` (repeatable, on both tools) replaces names in the decision records at export from a list of `PATTERN<TAB>REPLACEMENT` lines (`tools/relabel-sample.txt` shows the format; a deployment supplies its own, in CI the optional secret `ARCH_RELABEL`); the front page says so, and `check_export.py --relabel` fails on any pattern that still matches the export. The records in the repository are not changed. `node tools/export/check_export_browser.mjs FILE --shots DIR` loads it offline and checks the toggle, the search, the print view and the phone width, and it fails on any word wrapped mid-word in the first three columns of a table.

The export also holds a page for each capability and a page for each decision record. A capability page (`#cap-NAME`) gives the description from `capability-record.yaml`, the phase, the evidence the readiness doc records, the decisions the record cites, the views that name it and the open rows; each capability name in CV-2 (St-Tx) and CV-3 (St-Rm-P) links to it. A decision page (`#adr-NNNN`, and `#decision-roadmap` for the roadmap note) is the record's text with every h2 to h4 heading addressable, stamped with the commit and date of the last change to the file. The stamp is read from git, so the build needs full history (CI checks out with `fetch-depth: 0`) and fails on a shallow clone. A decision is cited as `ADR-NNNN §LABEL`, where LABEL is the number a heading starts with (`6`, `1a`, `2.1`) or, for a heading with no number, its GitHub slug (`decision`); a label must match exactly one heading, and `python docs/arch/tools/adr_sections.py ADR-NNNN` lists them. The record, St-Tx links and the generated CV-3 table use that form, `check_views.py` checks the sections resolve, and in the export each citation links to its heading.

CI builds the export from the public twin, checks it and attaches it to the check-views run as the `architecture-export` artifact. The file is not committed. CI runs the check on the public sample list, so a green check is not evidence that any private scan ran.

To build it for a deployment, from the deployment's own bundle, values and capability record, follow [RUNBOOK-generate-for-a-deployment.md](RUNBOOK-generate-for-a-deployment.md). For its CV-3, the deployment's own capability record and readiness doc, follow [RUNBOOK-cv3-for-a-deployment.md](RUNBOOK-cv3-for-a-deployment.md).

## Naming a deployment

Two bundle values set how the generated documents present a deployment. Both sit under `system` in the values files passed with `--values`, and later files win per key, as in Helm.

- `system.name` is the name of the system. It leads every title as `# <name>: <title>`, and it fills the `system-name` slot. Without it the titles are as written. A `system-name` in `--slots` is used when the values give no name, and it is an error when it differs from one that they give.
- `system.attribution` sets the line under the title. Left out, or `true`, it reads `built on OpenDDIL <chart version>`. `false` or an empty string drops the line. Any other string is printed as given.

The framework's name appears in a rendered document only in that attribution line. The views say "this architecture" or use the slot. The one other place is the SysML `package OpenDDIL`.

## Capability phases

[St-Rm-P](views/St-Rm-P.md) holds one row per capability in [St-Tx](views/St-Tx.md), and its phase and evidence are computed from [`capability-record.yaml`](capability-record.yaml).

Copying a record's words is the bug this replaces: a record said "not deployed anywhere" while the chart rendered the gate when enabled, and the mark repeated it. The phase now comes from citations that have to resolve, and evidence only from the readiness doc in `openddil-helm/scripts/`, with a date and a lab, or it reads "not measured". A decision record's wording can't make a capability measured.

The other views' marks still copy words.

`--record` and `--readiness` on `render_profile.py` name the record and the readiness doc. The render needs the readiness doc beside the chart or the flag, and refuses rather than saying "not measured" without it. A readiness line the record cites being edited away fails the render, which is the point.

The render is also a floor. `capability_floor.py` renders the chart in memory and lists its workloads, kinds, enabled flags and routes. The record's `rendered:` section has to claim every one, by section and name. A claim is either a non-empty list of capability names, or `{infrastructure: "<reason>"}` for an item that serves no capability. A capability that claims a rendered item cannot sit below `built unmeasured`, so a missing `built` citation no longer understates a phase quietly. `check_views.py` fails on an item the record does not claim, a claim the render does not show, an unknown section or capability, a malformed claim, and a capability below the floor. It cannot tell a capability that was filed under infrastructure by mistake, and a feature that is off in this render has no floor.

Evidence quotes are scanned against a list of barred values, read from a file `check_views.py` is given. CI gives it [`tools/barred-sample.txt`](tools/barred-sample.txt), a public sample, and uses no secret. A private scan runs before a push, outside this repository. **CI green is not evidence that the private scan ran.** It shows the structural checks passed and that the scan works.

## Profile mapping

[`APPENDIX-A.md`](APPENDIX-A.md) is the mapping from UAF 1.2 Appendix A, formal/22-07-07, Tables 2:1, 2:3 and 2:5, and the only copy of it. `exports` in [`profiles.yaml`](profiles.yaml) selects from it, and `tools/check_views.py` fails on an export the table does not name. The mapping is not one-to-one. A view a profile cannot name is listed in that profile's `NOT-EXPORTED.md` and is not dropped silently.

The security views have no DoDAF 2.02 or NAF 4.0 target. Appendix A maps them only to DNDAF SecV views.

The data-exchange view sits in Resources-Connectivity, where Appendix A names it: SV-6 under DoDAF 2.02, P3 under NAF v4. Resources-Information exports as DIV-3 and P7. Under DoDAF 2.02 the generated table is its own file, SV-6, and SV-3 carries the rest of the view. NAF v4 names one output for the whole view, so P3 holds both.
