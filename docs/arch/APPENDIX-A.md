# UAF 1.2 Appendix A mapping

Which DoDAF 2.02, NAF 4.0 and DNDAF security views UAF 1.2 names for each UAF view specification. Source: UAF 1.2 Appendix A, Traceability, OMG formal/22-07-07, Table 2:1 (DoDAF 2.02), Table 2:3 (NAF 4.0) and Table 2:5 (DNDAF security views). Looked up on 2026-11-02.

This table is the only copy of the mapping. `exports` in [`profiles.yaml`](profiles.yaml) is the selection this repository makes from it, and [`tools/check_views.py`](tools/check_views.py) fails on an export this table does not name. The appendix states that the mapping is not one-to-one, so one view can name several outputs and one output can come from several views.

A dash means the table gives that view no output. Several rows can share an identifier, where the appendix splits one view specification by aspect.

| View | Name | DoDAF 2.02 | NAF 4.0 | DNDAF |
|---|---|---|---|---|
| Am-Cn | Architecture References | - | - | - |
| Am-Ct | Architecture Constraints | - | A7 | - |
| Am-If | Information: Dictionary | AV-2 | A1 | - |
| Am-Mv | Architecture Principles | - | - | - |
| Am-Pm | Architecture Parameters | - | - | - |
| Am-Pr | Architecture Development Method | - | A4 | - |
| Am-Rm | Architecture Roadmap | - | Ar, A6 | - |
| Am-Sr | Architecture Views | - | A2 | - |
| Am-St | Architecture Status | - | A5 | - |
| Am-Tr | Architecture Traceability | - | - | - |
| Am-Tx | Architecture Extensions | - | A1 | - |
| Ar-Cn | Actual Resources Connectivity | OV-4, SV-1, SV-2 | - | - |
| Ar-Sr | Actual Resources Structure | OV-4 | P2 | - |
| En-Pm | Parameters: Environment | - | - | - |
| Me-Pm | Parameters: Measurements | SV-7, SvcV-7 | C7, S7 | - |
| Op-Cn | Operational Connectivity | OV-2, OV-3 | L3, L2-L3 | - |
| Op-Ct | Operational Constraints | OV-6a | L8 | - |
| Op-If | Information: Operational Information | DIV-2 | L7 | - |
| Op-Pr | Operational Processes | OV-5a, OV-5b | L4 | - |
| Op-Sq | Operational Sequences | OV-6c | L6 | - |
| Op-Sr | Operational Structure | OV-2 | L2, L2-L3 | - |
| Op-St | Operational States | OV-6b | L5 | - |
| Op-Tr | Operational Traceability | CV-6 | - | - |
| Op-Tx | Operational Taxonomy | OV-1, OV-2 | L1 | - |
| Pj-Cn | Projects Connectivity | PV-2 | - | - |
| Pj-Pr | Projects Processes | - | - | - |
| Pj-Rm | Projects Roadmap | PV-2 | Lr | - |
| Pj-Sr | Projects Structure | PV-1 | - | - |
| Pj-Tr | Projects Traceability | PV-3 | - | - |
| Pj-Tx | Projects Taxonomy | PV-1 | - | - |
| Ps-Cn | Personnel Connectivity | SV-3, SV-6 | P3 | - |
| Ps-Ct | Personnel Constraints: Competence | OV-4 | - | - |
| Ps-Ct | Personnel Constraints: Drivers | SV-10a | - | - |
| Ps-Ct | Personnel Constraints: Performance | SV-7 | - | - |
| Ps-Pr | Personnel Processes | SV-4 | P4 | - |
| Ps-Rm-A | Personnel Roadmap: Availability | - | P8 | - |
| Ps-Rm-E | Personnel Roadmap: Evolution | SV-8 | P8 | - |
| Ps-Rm-F | Personnel Roadmap: Forecast | SV-9 | P8 | - |
| Ps-Sq | Personnel Sequences | SV-10c | P6 | - |
| Ps-Sr | Personnel Structure | OV-4 | P2 | - |
| Ps-St | Personnel States | SV-10b | P5 | - |
| Ps-Tr | Personnel Traceability | SV-5a, SV-5b | L4-P4 | - |
| Ps-Tx | Personnel Taxonomy | OV-4 | P1 | - |
| Rk-Pm | Parameters: Risks | - | - | - |
| Rq-Mv | Motivation: Requirements | - | - | - |
| Rs-Cn | Resources Connectivity | SV-3, SV-6 | P3 | - |
| Rs-Ct | Resources Constraints | SV-10a | P8 | - |
| Rs-If | Information: Resources Information | DIV-3 | P7 | - |
| Rs-Pr | Resources Processes | SV-4 | P4 | - |
| Rs-Rm | Resources Roadmap: Evolution | SV-8 | Pr | - |
| Rs-Rm | Resources Roadmap: Forecast | SV-9 | Pr | - |
| Rs-Sq | Resources Sequences | SV-10c | P6 | - |
| Rs-Sr | Resources Structure | SV-1, SV-2 | P2 | - |
| Rs-St | Resources States | SV-10b | P5 | - |
| Rs-Tr | Resources Traceability | SV-5a, SV-5b | L4-P4 | - |
| Rs-Tx | Resources Taxonomy | SV-1, SV-2 | P1 | - |
| Sc-Cn | Security Connectivity | - | - | SecV-2, SecV-3 |
| Sc-Ct | Security Constraints | - | - | SecV-1 |
| Sc-Mv | Security Controls | - | - | - |
| Sc-Pr | Security Processes | - | - | SecV-1 |
| Sc-Sr | Security Structure | - | - | - |
| Sc-Tr | Security Traceability | - | - | - |
| Sc-Tx | Security Taxonomy | - | - | - |
| Sd-Rm | Standards Roadmap | StdV-2 | A8 | - |
| Sd-Sr | Standards Structure | StdV-1 | - | - |
| Sd-Tr | Standards Traceability | StdV-1 | A8 | - |
| Sd-Tx | Standards Taxonomy | StdV-1 | A8 | - |
| Sm-Ov | Summary & Overview | AV-1 | - | - |
| St-Cn | Strategic Connectivity | CV-4 | C3 | - |
| St-Ct | Strategic Constraints | - | C8 | - |
| St-If | Information: Strategic Information | DIV-1 | - | - |
| St-Mv | Strategic Motivation | - | - | - |
| St-Pr | Strategic Processes | CV-1 | C2 | - |
| St-Rm-Dm | Strategic Roadmap: Deployment | CV-5 | Cr | - |
| St-Rm-P | Strategic Roadmap: Phasing | CV-3 | Cr | - |
| St-Sr | Strategic Structure | CV-2 | C1 | - |
| St-St | Strategic States | - | C5 | - |
| St-Tr | Strategic Traceability | - | - | - |
| St-Tx | Strategic Taxonomy | CV-2 | C1 | - |
| Sv-Cn | Services Connectivity | SvcV-3a, SvcV-3b, SvcV-6 | S3 | - |
| Sv-Ct | Services Constraints | SvcV-10a | S8 | - |
| Sv-Pr | Services Processes | SvcV-4 | S4 | - |
| Sv-Rm | Services Roadmap: Evolution | SvcV-8, SvcV-9 | Sr | - |
| Sv-Sq | Services Sequences | SvcV-10c | S6 | - |
| Sv-Sr | Services Structure | SvcV-1, SvcV-2 | S2 | - |
| Sv-St | Services States | SvcV-10b | S5 | - |
| Sv-Tr | Services Traceability | CV-7, SvcV-5 | C1-S1 | - |
| Sv-Tx | Services Taxonomy | SvcV-1 | S1 | - |

## Where this table differs from the printed appendix

The appendix's identifiers and names disagree in some rows. This table keys each row by the name of the view specification and uses the identifier the view specifications use.

| Printed | Table | Read here as |
|---|---|---|
| Op-St, Operational Structure | 2:1 | Op-Sr |
| Rs-sr, Resources Structure | 2:1 | Rs-Sr |
| Rs-St, Resources Structure | 2:3 | Rs-Sr |
| AM-Pr, Architecture Development Method | 2:1, 2:3 | Am-Pr |
| Ps-Sr, Personnel States | 2:3 | Ps-St |
| Ps-St, Personnel Structure | 2:3 | Ps-Sr |
| Ps-Tr, Personnel Taxonomy | 2:3 | Ps-Tx |
| Ps-Tx, Personnel Traceability | 2:3 | Ps-Tr |
| Sc-Tr, Security Taxonomy | 2:3, 2:5 | Sc-Tx |
| Sc-Tx, Security Traceability | 2:3, 2:5 | Sc-Tr |
| Ps-Sq, Personnel Scenarios | 2:1 | Personnel Sequences, the name Table 2:3 prints |
| Sv-Sq, Services Sequences Interaction Scenarios | 2:3 | Services Sequences, the name Table 2:1 prints |
