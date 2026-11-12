# Architecture-Traceability (Am-Tr)

Every decision record against the views that cite it, generated from [`decisions/`](../../../decisions/) and the view sources when the view is rendered. A record counts as cited by a view when its number appears in that view's text. Strategic-Roadmap-Phasing (St-Rm-P) also cites each record that the capability record lists for a capability.

The findings come first: each accepted or proposed record that no view cites, with its category and the reason, read from [adr-exemptions.yaml](../adr-exemptions.yaml). A record that is neither cited nor listed there fails the render. So does an entry for a record that a view now cites, an entry with no reason, or a category outside the four. A record whose status is neither accepted nor proposed, such as a superseded one, is listed and is not required.

<!-- generated: adr-traceability -->

The categories: a rule is a rule on how code is written, kept by review, with nothing the running system does that [Operational-Constraints](Op-Ct.md) could state; infrastructure is a store or a setting under a capability that a view already cites; process is how the work is done and checked; alignment is how the system is placed, restated by a record that a view cites.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| The table, its findings and their reasons | [`decisions/`](../../../decisions/), the views, [adr-exemptions.yaml](../adr-exemptions.yaml) | Generated | Generated |
