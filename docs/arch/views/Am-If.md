# Information-Dictionary (Am-If)

The terms the ontology declares, generated from [`ontology/`](../../../ontology/) when the view is rendered. Each row is one declared term: its file, its path in the file, its shape, how many entries it holds and the field names those entries use. No entry is listed, so the dictionary describes the vocabulary and states nothing a deployment declares. A file with no row, or a row whose term the file does not hold, fails the render.

<!-- generated: ontology-dictionary -->

An entry count of 0 is a term the public ontology declares and leaves empty for a deployment to fill. The platform variants a deployment uses: {{slot:platform-variants}}. [Resources-Information](Rs-If.md) shows the same files on the wire, and [Standards-Taxonomy](Sd-Tx.md) shows the standards they cite.

CI checks every entity type in the ontology against the SISO reference table, by both its number and the name SISO gives it. A permanent red step plants a type that SISO holds under another platform's name and requires the check to refuse it.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| The table | [`ontology/`](../../../ontology/) | Generated | Generated |
| Entity types checked against the SISO reference, with a red check | [ontology-siso.yml](../../../.github/workflows/ontology-siso.yml) | Standing | Built |
