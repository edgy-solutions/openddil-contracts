# ADR-0033 — The tier hierarchy is unbounded and recursive (framework invariant)

## Status

Accepted (2026-08-07) as a statement of design intent and as a set of
constraints binding current work. The **generalization work** it implies
is deferred and phased (§Generalization backlog) — this ADR records the
invariant so that work built before generalization does not harden
against it.

Relationship to ADR-0022: that ADR established hierarchical aggregation
as the architecture and phased its restoration across three tiers. This
ADR states the property that ADR-0022's three-tier instantiation is *an
instance of*. It does not supersede ADR-0022; it removes an assumption
that ADR-0022's implementation left implicit.

## Context

### Why this is being written now

OpenDDIL's tier hierarchy has always been intended as unbounded. That
intent has never been recorded anywhere a reader could find it, and the
consequence surfaced in ADR-0032's first draft: the deployed
intermediate tier (`faust-regional`) has no broker of its own, and the
draft read that as a property of intermediate tiers — concluding
categorically that "regions get no store." It is not a property of
anything. It is a Phase-6 implementation shortcut: the aggregator was
built to consume child brokers directly and produce to the parent's
broker, which was sufficient because no intermediate presentation was
then required.

That is a deployment artifact mistaken for design, and it is a recurring
failure mode rather than a one-off. The defence against it is not more
care during review; it is **writing the intent down** so a future reader
— human or otherwise — is corrected by the document rather than by the
one person who holds the original design in their head.

This ADR is that document.

### The failure mode it prevents

Reasoning from the current deployment and generalizing to framework law.
Concretely, statements of the form "regions don't do X" or "the edge
tier is where Y happens" — which are true of a three-deep instantiation
with one particular component layout, and false as claims about tiers as
a kind.

## Decision

### The invariant

> **The tier hierarchy is unbounded and recursive. Every tier is the
> same self-similar node: it manages the tier below it, rolls up its
> subtree, and passes that rollup to its parent if it has one. Tier
> count and tier names are deployment configuration, not framework
> structure.**

Consequences of the invariant, stated so they are not re-derived:

- **"HQ" is not a kind.** It is the node with no parent (the root).
- **"Edge" is not a kind.** It is the node whose children are assets
  rather than nodes (a leaf).
- **"Region" is not a kind.** It is any node with both a parent and
  node-children (an intermediate).
- A deployment may run `edge→region→HQ`; another
  `edge→region→province→country`; another may add a cross-national tier
  above that. The framework must not know the difference.
- Depth is not bounded by the framework. Two-deep and six-deep are both
  valid configurations.

### The node kit

A tier node is a set of **optional components**:

```
{ broker?, aggregator, projector?, store?, presentation?, policy-sidecar? }
```

Only the aggregator is universal (a node that manages nothing below it
is not a tier). Which of the rest a given tier receives is deployment
configuration, subject to the dependency rules below.

**Dependency rules (framework-level, depth-independent):**

1. **A severance-tolerant presentation at tier N requires tier N's own
   broker.** Without a local topic set there is nothing local to project
   from, so the store is fed across the very links whose severance it
   exists to survive (ADR-0032 §a — this is the rule that ADR discovered
   and it survives the correction intact).
2. **A store requires a projector**, and the projector reads that tier's
   own topics. One projection path, one store shape, every tier
   (ADR-0032 §d).
3. **A presentation requires a store** at the same tier — the read
   contract is relational and tier-independent (ADR-0031 §2.2,
   ADR-0032 §b).

The **tier presentation node** defined in ADR-0032 §d — postgres +
schema-init + projector + Electric + UI + passive policy sidecar — is
this kit's presentation subset, built once and instantiated at any
broker-bearing tier at any depth.

### What each tier presents

A tier's presentation shows exactly two things:

1. **its local truth** — what it directly manages, and
2. **its subtree, rolled up.**

Neither is tier-kind-specific. A leaf's "local truth" happens to be
assets; an intermediate's happens to be child-node rollups. The
presentation is the same shape parameterized by depth, which is why
ADR-0032 §b insists on identical DDL at every store: a tier-independent
read contract is what makes a tier-independent presentation possible.

### Rollups must compose

Unbounded depth requires that **tier N aggregates tier N−1's rollups,
not the leaves.** An aggregation that secretly assumes it is reading raw
leaf streams works at depth 2 and silently breaks at depth 3.

Counts, worst-of severities, and latest-state upserts compose naturally.
Anything else in ADR-0024's aggregation set must be checked. That check
is a tracked audit item (§Generalization backlog), not an assumption —
"unbounded depth is rollup-of-rollups or it is nothing."

## Constraints binding current work

In the spirit of ADR-0022's "do not harden the flat assumption"
constraints, and binding until the generalization backlog is worked:

1. **Do not state tier-kind laws.** A decision about which tiers get a
   component is deployment configuration and must be written as such,
   with the framework-level *rule* stated separately from the
   *instantiation*. ADR-0032 §a is the worked example of the correct
   form.
2. **Do not add new named-tier components.** New work extends the
   recursive node kit or is parameterized by tier; it does not
   introduce a fourth tier-kind-specific service alongside
   `faust-regional` et al.
3. **Do not deepen the `edge_id`/`region_id` assumption.** New schema,
   proto, or code that needs hierarchy position should be reviewed
   against §Hierarchy-path addressing rather than adding a third named
   level.
4. **Do not assume leaf-stream inputs in new aggregations.** Write
   rollups that compose over child rollups.

These constrain *how* work is written, not *whether* it ships. Arc 1
proceeds unchanged under them — see §Effect on Arc 1.

## Generalization backlog

Named, not resolved here. Each is real work with its own sizing.

### Hierarchy-path addressing

`edge_id` / `region_id` (ADR-0023) are named proto fields encoding a
two-level hierarchy into the schema. The generic form is a node
identifier plus parent chain — e.g. a materialized path
(`nato/nld/north/site-04`) or an equivalent adjacency representation —
of which `edge_id`/`region_id` is the two-level projection.

This is the **deepest hardcoding and the most expensive to move**: it
appears in proto, schema, projector, aggregators, and the frontend.

**Assessed for the Arc 1 Phase 1 schema train — recommendation: do not
board it.** Reasoning:

- Phase 1's train exists for the releasability labels, which carry a
  *correctness gate* (deny-unlabeled requires zero NULL
  `originator_nation`). That gate is what makes "one migration, not N"
  urgent for them.
- Hierarchy-path has no such gate. A nullable column with no backfill
  requirement is a cheap additive migration whenever it lands.
- Addressing is the one piece here worth designing carefully, and
  designing it under schedule pressure to catch a train is how a
  regretted shape gets locked in — precisely the mistake this ADR
  exists to prevent, committed at the schema layer.

**Counter-argument, recorded honestly:** post-Arc-1 that migration runs
at N+1 sites rather than 1. That cost is real but small for a nullable
column requiring no backfill, and it is the correct price for not
guessing at addressing now.

### Recursive node templating

Helm's `edge`/`region`/`hq` structure and the named-tier components
become one templated node kind instantiated per configured tier, with
the kit's optional components selected by configuration.

### Broker-bearing intermediate tiers

Remove the Phase-6 shortcut: an intermediate tier that a deployment
wants to carry presentation or buffering gets its own broker, and its
aggregator consumes its children's brokers and produces to its own.

### Parameterized presentation

The three fixed views (maintainer / regional / HQ) become one
presentation parameterized by "my tier + my subtree." The role views
remain as *presets over* that parameterization, not as distinct
implementations.

### Aggregation composability audit

Audit ADR-0024's aggregation set: verify each rollup composes over
child-tier rollups rather than over raw leaf streams. Fix or document
each. This is a correctness prerequisite for any depth beyond three,
and it is cheap to do now versus discovering it at depth.

## Effect on Arc 1

**Arc 1's work is unchanged; Arc 1's claims are corrected.**

The tier presentation node being built in Arc 1 Phase 3 is the generic
recursive node's presentation kit. Building it once, defined
tier-agnostically, and deploying it in this deployment at the leaf tiers
and the root — because those are the tiers this deployment configured
with brokers and staffed with operators — is exactly what the generic
model wants. The pilot is the first instantiation of the generic unit,
not an edge-specific artifact.

Nothing in Arc 1 Phases 1–6 is wasted or redirected. What changed is
that the documents no longer claim a deployment's configuration as
framework law.

## Consequences

### Positive

- The design intent leaves one person's head and becomes citable. A
  future reader — including a future contributor with no access to the
  original design conversations — is corrected by this document.
- The Arc 1 deliverable becomes *more* valuable, not less: one reusable
  tier presentation node instead of an edge-specific stack.
- Deployment flexibility becomes a stated property rather than an
  accident: a customer running four or six tiers is a configuration, not
  a fork.
- The four constraints prevent new work from deepening debt that already
  exists.

### Negative

- Names a substantial backlog that is not funded or scheduled here.
  Written-down debt is better than invisible debt, but it is still debt,
  and hierarchy-path addressing in particular will be expensive whenever
  it is taken.
- Creates a standing review obligation: every tier-related decision now
  has to separate rule from instantiation, which is more work per
  decision than stating the outcome.
- Some current code is provably 3-tier-shaped. Until the backlog is
  worked, this ADR describes an intent the implementation does not yet
  meet — the same honesty gap ADR-0022 carried between statement and
  restoration.

### Neutral / acknowledged

- The current three-deep instantiation is entirely valid under this
  invariant. Nothing deployed is wrong; it is one configuration of many.
- ADR-0032's broker rule survives the correction unchanged. It was the
  right discovery stated at the wrong scope; here it is stated at
  framework scope, depth-independent.
- Tier *names* (edge/region/HQ) remain useful shorthand for this
  deployment and are not being renamed in code by this ADR. The
  invariant constrains new work and generalization, not vocabulary in
  existing services.

## Related

- ADR-0022 — hierarchical aggregation is the architecture; this ADR
  states the unbounded property its three-tier restoration instantiates.
- ADR-0023 — hierarchy restoration topology; source of the
  `edge_id`/`region_id` two-level encoding.
- ADR-0024 — multi-cluster aggregator pattern; subject of the
  composability audit.
- ADR-0031 — converged edge node; its tier-independent read contract is
  what makes parameterized presentation possible.
- ADR-0032 — tier-local presentation; the broker rule, the tier
  presentation node, and the worked example of separating rule from
  instantiation.
