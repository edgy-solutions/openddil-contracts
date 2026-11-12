# Information-Dictionary (Am-If)

The terms the ontology declares, generated from [`ontology/`](../../../ontology/) when the view is rendered. Each row is one declared term: its file, its path in the file, its shape, how many entries it holds and the field names those entries use. No entry is listed, so the dictionary describes the vocabulary and states nothing a deployment declares. A file with no row, or a row whose term the file does not hold, fails the render.

<!-- generated: ontology-dictionary -->

An entry count of 0 is a term the public ontology declares and leaves empty for a deployment to fill. The platform variants a deployment uses: {{slot:platform-variants}}. [Resources-Information](Rs-If.md) shows the same files on the wire, and [Standards-Taxonomy](Sd-Tx.md) shows the standards they cite.

CI checks every entity type in the ontology against the SISO reference table, by both its number and the name SISO gives it. A permanent red step plants a type that SISO holds under another platform's name and requires the check to refuse it.

## Terms

Terms the decision records use that the ontology does not declare. From [ADR-0059](../../../decisions/ADR-0059-condition-monitoring-bit-and-usage-alignment.md) §6 on, the first two are written out in full, never as "CM".

| Term | Meaning here |
|---|---|
| Configuration management | What an item is built to and what has been done to it: baselines, modifications and their compliance, and status accounting. "CM" survives only inside identifiers that already carry it, such as `cm-service`, and there it means this |
| Condition monitoring | What state an item is in, from what it reports and what is measured: detection, health, prognosis and advice |
| Condition-based maintenance | Maintenance decided from condition monitoring rather than from a fixed interval |
| Built-in test | A test an item runs on itself, reporting a result and a fault. Today it arrives only as free fault-code strings |
| Fault code | A key into a deployment's fault catalog. It is not a failure mode |
| Failure mode | The manner in which a failure occurs (IEC 60812). No record carries one today |
| Episode | One fault on one component of one asset, from open to close, kept after it closes (ADR-0051) |
| Usage meter | A declared, monotonic measure of use per variant, with its unit, such as rounds fired (ADR-0051 §3) |
| Remaining useful life | Remaining time, or use, before health falls below a defined failure threshold (ISO 13381-1). Today's wear value is a percentage of an authored life, not this |
| Sample | A measured value with its unit, entity and time: a SOSA observation. SOSA also has a class named "Sample", whose definition was not read; the shared name is not a mapping |

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| The table | [`ontology/`](../../../ontology/) | Generated | Generated |
| Entity types checked against the SISO reference, with a red check | [ontology-siso.yml](../../../.github/workflows/ontology-siso.yml) | Standing | Built |
| The terms | [ADR-0059](../../../decisions/ADR-0059-condition-monitoring-bit-and-usage-alignment.md) | Proposed | Status line |
