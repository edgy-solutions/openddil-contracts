# Sample Fleet System: Architecture-Traceability (Am-Tr)

built on OpenDDIL 0.1.161

Every decision record against the views that cite it, generated from [`decisions/`](../../../../decisions/) and the view sources when the view is rendered. A record counts as cited by a view when its number appears in that view's text. Strategic-Roadmap-Phasing (St-Rm-P) also cites each record that the capability record lists for a capability.

The findings come first: each accepted or proposed record that no view cites, with its category and the reason, read from [adr-exemptions.yaml](../../adr-exemptions.yaml). A record that is neither cited nor listed there fails the render. So does an entry for a record that a view now cites, an entry with no reason, or a category outside the four. A record whose status is neither accepted nor proposed, such as a superseded one, is listed and is not required.

49 decision records. 48 accepted or proposed: 44 cited by a view, 4 exempt. 1 not required.

| Not cited | Status | Category | Reason |
|---|---|---|---|
| ADR-0011 Strategic Sustainment Tool Positioning | Accepted | alignment | Positions the system beside strategic sustainment tools. ADR-0039 restates the positioning, and Strategic-Taxonomy cites ADR-0039 for TacticalSustainmentCorrelation. |
| ADR-0025 Build-Pass Deployment Verification Discipline | Accepted | process | A change is verified by its tests and by confirming the deployment runs the new code. It is how work is checked, not something the system does. |
| ADR-0027 Runtime-configurable tunables via shared settings table | Proposed | infrastructure | One table for operator-tunable settings. Proposed, and its implementation is deferred. No capability depends on it. |
| ADR-0028 Centralized asset_registry for edge/region lineage | Proposed | infrastructure | One table, with one writer, for which edge and region each asset belongs to. It is the lineage store under HierarchicalAggregation, which Strategic-Taxonomy cites through ADR-0022. |

| Not required | Status | Cited by |
|---|---|---|
| ADR-0015 Identity Resolution Asymmetry — DIS Feed Bypasses Alias Rewrite | Superseded | none |

| ADR | Status | Cited by |
|---|---|---|
| ADR-0009 | Accepted | Op-If, Op-Pr, Rs-Pr, Sd-Tx, St-Rm-P, St-Tx |
| ADR-0010 | Accepted | St-Rm-P, St-Tx |
| ADR-0011 | Accepted | none |
| ADR-0013 | Accepted | Op-Ct |
| ADR-0014 | Accepted | Rs-Sr |
| ADR-0015 | Superseded | none |
| ADR-0016 | Accepted | Rs-Sr |
| ADR-0017 | Accepted | Op-Ct |
| ADR-0018 | Accepted | Rs-If |
| ADR-0019 | Accepted | Rs-Sr |
| ADR-0020 | Accepted | St-Rm-P |
| ADR-0021 | Accepted | Op-Cn, Op-Sr, Rs-Cn, Rs-Sr, Sm-Ov |
| ADR-0022 | Accepted | Op-Pr, Op-Sr, Rs-Pr, Sm-Ov, St-Rm-P, St-Tx |
| ADR-0023 | Accepted | Op-Sr, Op-Tx, Rs-Pr |
| ADR-0024 | Accepted | Rs-Sr |
| ADR-0025 | Accepted | none |
| ADR-0026 | Accepted | Op-If, Op-Pr, Op-St, Rs-Pr, Rs-St |
| ADR-0027 | Proposed | none |
| ADR-0028 | Proposed | none |
| ADR-0029 | Accepted | Op-Cn, Op-Ct, Op-If, Op-Pr, Rs-If, Rs-Pr, Rs-Sq, Rs-Sr, Sc-Cn, Sc-Sr, Sd-Tx, St-Rm-P, St-Tx |
| ADR-0030 | Accepted | Op-Cn, Op-Pr, Rs-Cn, Rs-Pr, Rs-Sr |
| ADR-0031 | Accepted | Rs-Sr, St-Rm-P, St-Tx |
| ADR-0032 | Accepted | Op-Cn, Op-Sr, Rs-Sr |
| ADR-0033 | Accepted | Op-Cn, Op-Ct, Op-Sr, Op-Tx, Rs-Cn, Rs-Ct, Rs-Sr, Rs-Tx, Sm-Ov |
| ADR-0034 | Accepted | Rs-Sr, St-Rm-P, St-Tx |
| ADR-0035 | Accepted | Sm-Ov |
| ADR-0036 | Accepted | Sc-Pr |
| ADR-0037 | Accepted | Rs-Tr, Sm-Ov |
| ADR-0038 | Accepted | Op-Ct, Rs-Pr, Sd-Tx, St-Pr, St-Rm-P, St-Tx |
| ADR-0039 | Accepted | Sm-Ov, St-Pr, St-Rm-P, St-Tx |
| ADR-0040 | Accepted | Op-If, Op-Pr, Rs-Tr, St-Pr, St-Rm-P, St-Tx |
| ADR-0041 | Accepted | Op-If, Rs-Sr, Sv-Cn |
| ADR-0042 | Proposed | Op-Cn, St-Rm-P, St-Tx |
| ADR-0043 | Proposed | Op-Cn, Op-If, Op-Pr, Op-Sq, Rs-Pr, Rs-Sq, Sc-Cn, Sc-Pr, Sc-Sr, St-Rm-P, St-Tx, Sv-Cn |
| ADR-0044 | Proposed | Op-Cn, Op-Ct, Op-If, Op-Pr, Op-St, Rs-Pr, Rs-St, Sd-Tx |
| ADR-0045 | Accepted | Op-Cn, Sc-Cn, Sc-Sr, St-Rm-P, St-Tx |
| ADR-0046 | Accepted | Op-Cn, Op-If, Op-Pr, Op-Sq, Op-Tx, Rs-Cn, Rs-Ct, Rs-If, Rs-Pr, Rs-Sq, Rs-Sr, Rs-Tx, Sc-Cn, Sc-Pr, Sd-Tx, St-Rm-P, St-Tx, Sv-Cn |
| ADR-0047 | Accepted | Op-If, Rs-Sr |
| ADR-0048 | Accepted | Op-If, Op-Pr, Sd-Tx |
| ADR-0049 | Accepted | Op-If, Op-Pr |
| ADR-0050 | Proposed | Op-Cn, Op-Ct, Op-If, Op-Pr, Op-St, Sd-Tx, St-Rm-P, St-Tx |
| ADR-0051 | Accepted | Op-If, Rs-Pr, Sd-Tx, St-Rm-P, St-Tx |
| ADR-0052 | Accepted | Op-Pr, Rs-Tr, Sc-Pr, Sd-Tx, St-Rm-P, St-Tx |
| ADR-0053 | Accepted | Op-Pr, Rs-Pr, Sc-Pr, Sd-Tx, St-Rm-P, St-Tx |
| ADR-0054 | Accepted | Rs-Cn, Rs-Sr |
| ADR-0055 | Proposed | St-Rm-P, St-Tx |
| ADR-0056 | Proposed | Op-If, Rs-If, Sd-Tx, St-Rm-P, St-Tx |
| ADR-0057 | Proposed | St-Rm-P, St-Tx |
| ADR-0058 | Proposed | St-Rm-P, St-Tx |

The categories: a rule is a rule on how code is written, kept by review, with nothing the running system does that [Operational-Constraints](../../views/Op-Ct.md) could state; infrastructure is a store or a setting under a capability that a view already cites; process is how the work is done and checked; alignment is how the system is placed, restated by a record that a view cites.

## Sources

| Claim | Source | Decision | Evidence |
|---|---|---|---|
| The table, its findings and their reasons | [`decisions/`](../../../../decisions/), the views, [adr-exemptions.yaml](../../adr-exemptions.yaml) | Generated | Generated |
