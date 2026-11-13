# Runbook: generate the architecture export for a deployment

This produces one self-contained HTML file of the architecture views, rendered from a deployment's own bundle. It runs
on the deployment's machine and reaches no cluster. The tools are described in [README.md](README.md#the-html-export).

## 1. Clone and install

You need Python 3.10 or later, `helm` 3 (CI pins v3.16.2), Node 22 and Chrome.

```sh
mkdir arch-export && cd arch-export
git clone https://github.com/edgy-solutions/openddil-contracts.git
git clone https://github.com/edgy-solutions/openddil-helm.git
git -C openddil-helm checkout <commit>   # the commit whose openddil-demo/Chart.yaml is your deployment's chart version
python -m pip install pyyaml markdown-it-py==4.0.0
(cd openddil-contracts/docs/arch/tools/export && PUPPETEER_SKIP_DOWNLOAD=true npm ci)
export PUPPETEER_EXECUTABLE_PATH=/path/to/chrome
```

Put the deployment's bundle checkout beside them as `<bundle>`. To try the runbook first, use the public example bundle
in its place: `git clone https://github.com/edgy-solutions/openddil-customer-bundle-example.git`.

## 2. The deployment's own files

Keep these in a directory of the deployment's own, `<deployment>`, outside all three clones.

`<deployment>/system-values.yaml` names the system:

```yaml
system:
  name: "<the system's name>"   # leads every title, and fills the system-name slot
  attribution: true             # "built on OpenDDIL <chart version>"; false drops the line; a string is printed as given
```

`<deployment>/slots.yaml` fills the increment dates. The roadmap note gives the increments an order and no dates. Take
their names from [the roadmap note](../../decisions/ROADMAP-2026-10-29-isolation-increments.md):

```yaml
increment-dates: "Increment 1, identity per tier: <date>. Increment 2, maintenance chain per tier: <date>. Increment 3, workflow per tier: <date>. Increment 4, one session: <date>."
```

The same file can fill any other slot in [slots.yaml](slots.yaml), one string each. A name that is not in that file is
exit 2. A `system-name` that differs from `system.name` is also exit 2. A slot that is not filled stays in the page as
written. The export's "For a deployment" page lists every slot.

`<deployment>/capability-record.yaml` and `<deployment>/readiness.md` are covered in §5.

## 3. Run

```sh
cd openddil-contracts
B=../<bundle>; D=../<deployment>
python docs/arch/tools/render_html.py --out "$D/out/architecture.html" \
  --chart ../openddil-helm/openddil-demo --release <release name> \
  --values "$B/k8s/tier-node-values.yaml" --values "$B/k8s/egress-values.yaml" \
  --values "$D/system-values.yaml" --slots "$D/slots.yaml" \
  --record "$D/capability-record.yaml" --readiness "$D/readiness.md"
python docs/arch/tools/check_export.py --export "$D/out/architecture.html" \
  --barred docs/arch/tools/barred-sample.txt --barred "$D/barred.txt"
(cd docs/arch/tools/export && node check_export_browser.mjs "../../../../$D/out/architecture.html" --shots "../../../../$D/shots")
```

- **`--values`:** the files the deployment installs with, in the same order. Put `system-values.yaml` last, because
  later files win per key.
- **`--release`:** the Helm release name the deployment installs under.
- **`$D/barred.txt`:** the deployment's own list of values that must never appear in the file. `check_export.py`
  fails on any of them.
- **Sandboxed runners:** where Chrome needs `--no-sandbox`, pass `--puppeteer-config` to both `render_html.py` and the
  browser check.

The file lands at the `--out` path, and the script prints `out:` and `bytes:`. The exit codes are 0 ok, 1 a check
failed (it names the view), and 2 bad input.

## 4. Which views read the framework's record, and which read the deployment's

| Read from | Views |
|---|---|
| The deployment's chart and values | Rs-Cn's data-exchange table (SV-6, P3). Every page's title (`system.name`), attribution line, chart version and values digest. |
| The deployment's capability record and readiness doc | St-Rm-P (CV-3, Cr): each capability's phase and evidence. St-Cn (CV-4, C3): its dependency table, joined through the record's increments. |
| The deployment's slots file | Every `{{slot:…}}` in any view, St-Rm-P's increment dates among them. |
| The framework's record, in this repository | Every other view, and the same for every deployment. The text and Sources tables come from `decisions/`, Rs-Tx from `model/openddil.sysml`, Am-If from `ontology/`, and the grid from `APPENDIX-A.md`. |

Without `--record` and `--readiness`, CV-3 shows the framework's own phases and the framework's lab evidence, not the
deployment's.

## 5. CV-3's evidence: the deployment's own capability record

Copy [capability-record.yaml](capability-record.yaml) to `<deployment>/capability-record.yaml`, then:

1. **`labs`:** replace them with the deployment's own letters, each with a description.
2. **`entries`:** replace them with the deployment's own. Each has an `anchor` and a `lab` letter declared in `labs`.
   The anchor is text found on exactly one line of `<deployment>/readiness.md`. That line holds the entry's date and
   sits under a `##` heading.
3. **`measured`:** delete every `measured` citation of the framework's entries, because those cite its labs. Then cite
   the deployment's own: `{entry: <key>, line: "<text found once between that anchor and the next heading>"}`.
4. **`adrs`, `built` and `rows`:** keep them unless the deployment differs. They cite the decision records and the
   chart's templates, and `built` resolves against the chart passed with `--chart`.

The phase is computed from these citations, and the evidence comes only from the readiness doc. A capability with a
`measured` citation reads `measured`. One with `built` and no `measured` reads `built unmeasured`. A citation that does
not resolve fails the render with exit 1.

Check the record with `check_views.py --record` before rendering. That also checks that it claims every workload,
kind, flag and route the deployment's render shows. [RUNBOOK-cv3-for-a-deployment.md](RUNBOOK-cv3-for-a-deployment.md)
walks through the record, the readiness doc, the check and CV-3 on its own.

## 6. The output stays on the deployment's side

The export, the screenshots, and every file in `<deployment>` stay on the deployment's side. None of them is committed
to these repositories, attached to an issue, or sent upstream.

*Tested 2026-11-11 by running §1 to §3 as written, from fresh clones of the three public repositories (contracts
aca24eb, helm 8bbcb9a, example bundle 63f2f43). The example bundle stood in for the deployment, with its own system
values, slots, record, readiness doc and barred list. The run was on Windows (Git Bash). The render exited 0,
`check_export.py` was ok (28 views, 23 diagrams, nothing barred), and the browser check passed 66 of 66. Compared with
an export of the bundle alone, and with the name, attribution and digest set aside, only two views differed: St-Rm-P
(the record, readiness doc and slots) and Rs-Cn (its list of values files).*
