# Runbook: a deployment's CV-3 from its own record

CV-3 (Capability Phasing; St-Rm-P in UAF) shows where each capability stands, and the evidence for it. The phase is
computed from a capability record and the evidence is quoted from a readiness doc. A deployment's CV-3 reads the
deployment's own record and readiness doc, not the framework's, so its phases and dates are the deployment's own.

This page builds the record, checks it, renders CV-3 on its own to read, and then puts it in the export. It runs on
the deployment's machine and reaches no cluster. Set up first with §1 and §2 of
[RUNBOOK-generate-for-a-deployment.md](RUNBOOK-generate-for-a-deployment.md). The commands below use the names set
there:

```sh
cd openddil-contracts
B=../<bundle>; D=../<deployment>; H=../openddil-helm/openddil-demo
V="--values $B/k8s/tier-node-values.yaml --values $B/k8s/egress-values.yaml"
```

`$V` holds the files the deployment installs with, in its own order.

## 1. Write the readiness doc

`<deployment>/readiness.md` is where the deployment records what it ran and what it saw. CV-3 quotes it and nothing
else, so a capability is `measured` only if this file says so. Each check is an anchor line under a `##` heading,
then the lines it measured:

```markdown
## S. Severance — rehearsed 2027-01-15

### SEVERED 2027-01-15 on site 1
| 1 | rollup 2 partials / 6 assets | held through the cut |
```

- **The anchor line** holds the date as `YYYY-MM-DD`. Its text is found on exactly one line of the file.
- **The `##` heading** above it is printed in the evidence cell.
- **A measured line** sits between its anchor and the next heading, and its quoted text is found there once.

## 2. Make the record the deployment's

Copy [capability-record.yaml](capability-record.yaml) to `<deployment>/capability-record.yaml`. Then:

1. **`labs`:** replace them with the deployment's own letters, each with one line saying what it is. CV-3 prints
   that line under the table.
2. **`entries`:** replace them with the deployment's own. Each has a key, an `anchor` (the anchor line's text) and a
   `lab` letter declared in `labs`.
3. **`measured`:** delete every `measured` citation, because they cite the framework's entries. Then cite the
   deployment's own, under the capability they measure:
   `measured: [{entry: <key>, line: "<the measured line's text>"}]`.
4. **`adrs`, `built` and `rows`:** keep them unless the deployment differs. They cite the decision records in this
   repository and the chart's templates. `built` resolves against the chart passed with `--chart`.
5. **`rendered`:** claim what the deployment's render shows. Its values can switch on a workload, kind, flag or route
   the framework's defaults leave off, or switch one off. §3 lists every difference.

## 3. Check the record

```sh
python docs/arch/tools/check_views.py --chart "$H" $V --release <release name> \
  --record "$D/capability-record.yaml" --readiness "$D/readiness.md" \
  --barred docs/arch/tools/barred-sample.txt --barred "$D/barred.txt"
```

It prints `ok: 17 rules, 29 views`, or a `FAIL:` line for each problem and exit 1. For the record it checks:

- **Phases:** every citation resolves and every capability has a phase.
- **Quotes:** no value in a barred list appears in the evidence CV-3 prints, or anywhere in the record.
- **Floor:** every workload, kind, flag and route the deployment's render shows is claimed under `rendered`, and every
  claim is still in the render. A capability that claims a rendered item cannot read below `built unmeasured`.

The floor sees an item nobody claimed. It does not see one claimed by the wrong capability, or filed under
`infrastructure` to keep it out of CV-3, so someone still reads `rendered` once.

What a failure says, and what to change:

| The line says | Change |
|---|---|
| `entry site1-sever names lab Q, which labs does not declare` | Declare the letter under `labs`, or fix the entry. |
| `anchor '…' is on 0 readiness lines, expected one` (or 2) | Make the anchor's text appear on exactly one line. |
| `the line of anchor '…' holds no date` | Put the date in the anchor line, as `YYYY-MM-DD`. |
| `anchor '…' has no ## heading above it` | Put the check under a `##` heading. |
| `entry … line '…' is on 0 readiness lines from the anchor to the next heading` | Quote text that sits under that anchor. |
| `template edge.yaml does not contain '…'` | Fix the `built` citation, or check that `--chart` is the deployment's chart. |
| `floor: workload … is in the render and the record does not claim it` | Claim it under `rendered`. |
| `floor: workload … is claimed but the render does not show it` | Remove the claim. The deployment does not run it. |

## 4. Render CV-3 on its own

```sh
python docs/arch/tools/render_profile.py --profile dodaf202 --out "$D/out/dodaf202" \
  --chart "$H" $V --values "$D/system-values.yaml" --release <release name> \
  --slots "$D/slots.yaml" --record "$D/capability-record.yaml" --readiness "$D/readiness.md"
```

It writes every DoDAF 2.02 view to `$D/out/dodaf202/`. CV-3 is `CV-3.md`. Read it for:

- **The title:** it starts with `system.name`.
- **The phase count:** for example, `Phases: 2 measured, 14 built unmeasured, …`. A capability the deployment
  measured that reads `built unmeasured` has no `measured` citation.
- **The evidence column:** each `measured` row reads `<date>, lab <letter>, <heading>: <the measured line>`. All of
  it comes from `readiness.md`.
- **The labs line** under the table, from `labs`.
- **The increment dates**, from `slots.yaml`.
- **The record it names:** "`capability-record.yaml`, the deployment's own", in the opening paragraph and in Sources.

The Markdown's links point back into the contracts clone, so it is for reading on this machine only. The export is the
file to hand over.

## 5. Put it in the export

Run §3 of [RUNBOOK-generate-for-a-deployment.md](RUNBOOK-generate-for-a-deployment.md) with the same `--record` and
`--readiness`. CV-3 is the St-Rm-P page in the file.

The export, the Markdown, and every file in `<deployment>` stay on the deployment's side. None of them is committed to
these repositories, attached to an issue, or sent upstream.

*Tested 2026-11-12 on the public example bundle (example bundle 63f2f43, helm 8bbcb9a, chart 0.1.161), on Windows (Git
Bash). The example deployment's record was made from this repository's record by §2: one lab, two entries, and two
`measured` citations.
§3 printed `ok: 17 rules, 29 views`. §4 rendered CV-3 with `Phases: 2 measured, 14 built unmeasured, 7 accepted
design, 6 proposed, 2 row`, both evidence cells quoted from the readiness doc, and the record named as the
deployment's own. §5's export passed `check_export.py` (29 views, 23 diagrams, nothing barred) and the browser check
(73 of 73). Each line in §3's table is the message a deliberately broken copy of the record or readiness doc
printed.*
