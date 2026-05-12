# ADR-0011: Strategic Sustainment Tool Positioning

## Status
Proposed

## Context
The customer is currently using or evaluating commercial off-the-shelf (COTS) strategic sustainment modeling tools for long-term strategic analysis. A clear positioning strategy is needed to define how OpenDDIL relates to these classes of tools in the commercial portfolio, both competitively and architecturally.

## Decision
We officially adopt **Position B (Adjacent / Complementary)** as our positioning strategy.
- OpenDDIL handles the **operational sustainment loop**: real-time anomaly detection, configuration discrepancy alerting, dynamic work order generation, and sub-second decision cycles.
- Commercial strategic tools handle **strategic sustainment analysis**: life cycle cost modeling, sparing optimization, Level of Repair Analysis (LORA), and multi-decade availability simulation.

They operate on fundamentally different time horizons and inform different decision types.

## What OpenDDIL Does NOT Attempt to Replace
We will explicitly state that OpenDDIL does not replace:
- Life cycle cost modeling.
- Parametric availability simulation.
- Sparing level optimization at the program-of-record level.
- Level of Repair Analysis (LORA).
- Design-time supportability analysis.

## What OpenDDIL Provides that Strategic Tools Do Not
- Real-time edge ingestion.
- Streaming anomaly detection.
- Sub-minute decision loops.
- Configuration-aware operational alerts.
- Empirical reliability data feedback loops.

## Future Evolution
As OpenDDIL accumulates empirical reliability data from the field, that data can be fed into strategic modeling analyses as ground truth, replacing parametric estimates. This is a complementary integration vector, not a replacement vector.
- **Data Shape required for Tool Integration**: A periodic export of MTBF (Mean Time Between Failures) and MTTR (Mean Time To Repair) observations categorized per CI (Configuration Item) category.

## Sales & Positioning Guidance
- **Lead Statement**: "OpenDDIL complements your existing investments in strategic sustainment modeling."
- **Directive**: Do not initiate feature comparisons between OpenDDIL and specific commercial strategic tools.
- **Handling Dissatisfaction**: If the customer raises dissatisfaction with the outputs of their existing strategic tools, listen and document their pain points, but do not commit to replacing capabilities we do not currently possess in the core platform.
