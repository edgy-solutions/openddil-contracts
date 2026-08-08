# Generalization-debt registry

**Single authoritative home for "what is currently hardcoded that the
framework says should be configurable."**

## Why this file exists

The same debt items had begun appearing in two ADRs' framework-vs-
instantiation tables (ADR-0032 and ADR-0033), in slightly different
words. That is the **two-truths pattern in documentation form** — the
same disease this project has killed on sight at the data layer (two
authz corpora), the read layer (two read paths), and the policy layer.
The fix shape is the one that works every time: **one authoritative
home, everything else points.**

It also fixes a real discovery problem: "which ADR holds the row about
the three fixed UI views?" had no answer without grepping. Now there is
one place to look.

## Rules

1. **New debt rows land here only.** ADRs cite a row by ID; they do not
   restate it. Effective immediately, regardless of how much migration
   has happened.
2. **Migrate opportunistically, not ceremonially.** An existing
   duplicated row moves here the next time its ADR is touched for
   another reason. No dedicated migration pass.
3. **A row is closed by the work that generalizes it**, and the closing
   change updates the row rather than deleting it — the record of what
   *was* hardcoded is useful.
4. **Status vocabulary:** `open` · `in-arc` (scheduled in a named arc) ·
   `closed`.

## Registry

| ID | Statement | Owning ADR | Status |
|---|---|---|---|
| **GD-01** | `edge_id` / `region_id` are named proto fields encoding a two-level hierarchy. The generic form is hierarchy-path addressing (node id + parent chain), of which these are the two-level projection. Deepest and most expensive to move — appears in proto, schema, projector, aggregators, frontend. | ADR-0033 | open |
| **GD-02** | Named-tier components (`faust-regional`, projector tier parameters, helm's edge/region/hq structure) encode three tier *kinds* rather than one recursive kind. | ADR-0033 | open |
| **GD-03** | The intermediate tier has no broker of its own — a Phase-6 implementation shortcut, not a property of intermediate tiers. A deployment wanting presentation or buffering at an intermediate tier gives it a broker. | ADR-0033 | open |
| **GD-04** | Three fixed UI views (maintainer / regional / HQ) rather than one presentation parameterized by "my tier + my subtree". Framework statement recorded 2026-08-08; the current SPA is the demo instantiation and ships **interim** in the tier node's UI slot. | ADR-0033 §Tier-parameterized presentation | open |
| **GD-05** | Aggregations assume raw leaf-stream inputs rather than composing over child-tier rollups. **Audited 2026-08-07:** two of three are plumbing away from composing; `region_top_factors` is genuinely non-composable (top-N truncation is lossy and compounds per tier). Gate: resolve before any fourth tier or any rollup-consuming-rollup. | ADR-0024 / AUDIT-2026-08-07 | open |
| **GD-06** | Tree-only data flow (parent↔child). Framework topology is a tree **plus** deployment-configured lateral peer links. Mechanisms are already direction-agnostic; only configuration is tree-shaped, which is why constraint 5 costs nothing today. | ADR-0033 §Lateral peer topology | open |
| **GD-07** | All three analytics planes — collection, aggregation, detection — are hardcoded. Collection is partially configurable (the projector's topic-set axis, first exercised in Arc 1). Aggregation and detection are entirely hardcoded (three `region_*` rollups; the fusion evaluators). | ADR-0034 | open |
| **GD-08** | Detection runs centralized at the root tier reaching *downward* into child brokers, so a severed tier computes no severity or CM state. Resolved in deployment terms by per-tier Restate + fusion + cm-service (ADR-0032 §d); the *configurability* half remains open under GD-07. | ADR-0034 / ADR-0032 §d | in-arc (Arc 1) |

## Not tracked here

- **Product backlog** — features not yet built. This registry is only
  for cases where the framework has *stated* a general position and the
  implementation is narrower than the statement.
- **Bugs.** A defect is not generalization debt.
- **Fenced future arcs** (the process plane, the analytics engine, DDS
  egress). Those are scoped work with ADR homes, not debt — unless a
  specific hardcoding blocks them, in which case that hardcoding gets a
  row.

## Related

- ADR-0033 — the recursive-tier invariant most of these rows are debt
  against.
- ADR-0032 §Framework vs. instantiation — cites rows by ID.
- ADR-0034 — analytics configurability.
- `PRINCIPLES.md` §Framework vs. instantiation — the tell that produces
  most of these rows.
