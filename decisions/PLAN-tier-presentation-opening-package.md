# Plan — tier-parameterized presentation, opening package

**Date:** 2026-09-05 · **Status: PLAN ONLY. Nothing built, nothing
scheduled, go-signal reserved.** · **Method:** state verified by reading and
executing, not inferred from status text or from ADR-0033's own amendment.

The arc is ADR-0033's amendment made real: *one UI, parameterized by tier,
showing that tier's local truth plus its subtree rolled up, served by each
tier node at its own endpoint.* GD-04 tracks it. Slice 1 raised its urgency
three ways — per-tier PEPs, a capstone recording that should show the tier's
instance rather than a tab, and real identity making "which view" a fact
about **where you logged in**.

This package establishes where the arc starts from. As with Arc 2 Slice 1,
that turned out not to match what a reader of the ADR would conclude, and
that is the reason the package exists.

---

## 1. Verified state

Each row was checked directly against the source tree at `openddil-demo`
commit on 2026-09-05.

| Claim a reader would form | **Verified** |
|---|---|
| Three views differ by implementation | **FALSE, and this is good news.** `RegionalApp` and `HqApp` already share the entire rollup panel set — `useRegionFleetSummary`, `useRegionTopFactors`, `useRegionWearTrends`. `MaintainerApp` and `RegionalApp` share `useAllCapabilityState` and `useTacticalEvents`. What actually differs is **scope**, exactly as the amendment says |
| Tier names are hardcoded all over the frontend | **NO.** Literal tier strings appear in **two files**: `Root.tsx` (the tab list) and `components/hq/RegionFleetSummary.tsx` |
| The tier parameter needs a new delivery channel | **NO.** `deployment.ts` already fetches `/deployment/deployment.json` at startup, mounted from the overlay bundle. The channel exists and already carries topology (the `Fob` list with `edge_id` → `region_id`) |
| Scoping to "my subtree" is a frontend concern | **NO — it is a schema concern, and the schema cannot express it.** See §2 |
| The tier node serves its own tier's data | **NO. The env var that would do it is read by nothing.** See §3 |
| Slice 1's enforcement applies at every tier | **NO.** One PEP, at the root, and the NetworkPolicy protects only the root's Electric. See §4 |

---

## 2. The finding that reorders the arc

**The stated acceptance criterion — *a fourth tier renders with no code
change* — is unreachable, and not for any reason in the frontend.**

The two scope hooks are byte-identical but for a column name:

```ts
export function useFleetAssetsForEdge(edgeId) {
  const where = edgeId ? `edge_id = ${sqlLiteral(edgeId)}` : undefined;
  return useTableShape('telemetry_latest_state', mapFleetAsset, { where });
}

export function useFleetAssetsForRegion(regionId) {
  const where = regionId ? `region_id = ${sqlLiteral(regionId)}` : undefined;
  return useTableShape('telemetry_latest_state', mapFleetAsset, { where });
}
```

Two functions, one shape, differing only in **which column encodes the
tier** — and there are exactly two such columns because the schema has
exactly two levels. Checked, not assumed:

```
$ grep -n "tier_id\|tier_path\|depth\|ancestor" openddil-stack/schema/schema.hcl
685:  # edge-buffer depth — messages queued at the edge because...
1012:  #   [{element_id, layer_depth, layer_name, ...
```

Both hits are unrelated (`layer_depth` is element nesting; "edge-buffer
depth" is a queue). **No column anywhere expresses a tier, a path, or a
depth.** Every labelled table carries `edge_id` and `region_id` and nothing
else.

So a fourth tier has no column to be filtered by. The frontend can be
perfectly parameterized and the fourth tier still cannot be scoped, because
`WHERE ??? = 'tier-4'` has no left-hand side.

**This is GD-01, and GD-01 already says so:**

> `edge_id` / `region_id` are named proto fields encoding a two-level
> hierarchy. The generic form is hierarchy-path addressing (node id + parent
> chain), of which these are the two-level projection. **Deepest and most
> expensive to move — appears in proto, schema, projector, aggregators,
> frontend.**

*The generalizable shape, and it is one this project has now met twice:*
**an arc whose acceptance test lives in a layer the arc does not touch.**
Arc 2 Slice 1 had exactly this — P1's schema shipped and could not function
because P0 had not put the labels on the wire, and the §7 gate was
unreachable rather than merely unmet. Here the presentation arc's own
forcing function is the thing it cannot reach.

**Consequence for sequencing.** The arc is not blocked; it **splits**, and
the split is clean:

- everything that removes the mode-confusion hazard, unblocks the capstone
  recording, and makes the UI a tier-node component is reachable **today**,
  at the two depths the schema has;
- the acceptance criterion is reachable only **after GD-01**.

Recording that up front matters more than usual, because the criterion is
the kind that gets quietly restated as *"a fourth tier renders"* → *"the
code has no tier-specific branches"*. The second is achievable now and is
**not the same claim**, and a package that let them blur would hand the arc
a green light it had not earned.

---

## 3. A live defect, found while inventorying — the tier node does not serve its own data

`tier-node.yaml` gives every tier's frontend:

```yaml
env:
  # Targets THIS tier's Electric. No parent-hosted asset on the
  # critical path — the ADR-0032 §e corollary.
  - name: ELECTRIC_URL
    value: "{{ .Release.Name }}-tier-electric-{{ $tier.id }}:3000"
```

**That variable is read by nothing.**

- The application's `ELECTRIC_URL` is a TypeScript module export derived
  from `import.meta.env.VITE_ELECTRIC_URL` — a **Vite build-time** value,
  baked into the bundle by `Dockerfile` (`ARG VITE_ELECTRIC_URL=/electric/v1/shape`).
  A container env var cannot reach it.
- nginx proxies `/electric/` to `__ELECTRIC_UPSTREAM__`, substituted at
  container start from `OPENDDIL_ELECTRIC_UPSTREAM`, **defaulting to
  `electric-sync`** — which is the ROOT's unprefixed alias Service.

So a tier node's UI would read the **root's** store while its own template
comment asserts tier-locality, and the ADR-0032 §e corollary it cites — *no
parent-hosted asset on the critical path* — would be violated by the data
path itself.

**This is worse than the tab hazard, and it is a different hazard.** The
concern that prompted this arc is that an edge's SPA offers HQ and regional
*tabs* which render edge data under an HQ label. The defect here is the
mirror image, one layer lower: **the tier's own tab would render the root's
data under a tier-local label**, and severance would not change what it
showed, because it was never reading the tier's store.

**Live blast radius is zero today** — `tierNode.enabled: false`, so no tier
frontend is deployed. Same shape as the reference specimen that could not
encode: a defect that is real, inert, and waiting for the phase that turns
it on. Phase 3 is that phase.

*Third instance this week of a configuration that is read by nothing.* The
bundle's removed per-edge configs (GD-09's edit trap), the notify path
filters that never fired (VE-9), and now this. The family is worth naming:
**a setting whose consumer does not exist produces no error, and the comment
beside it is the only thing asserting that it works.**

---

## 4. What Slice 1 added, checked rather than assumed

Slice 1 is a **prerequisite the arc gained**, not merely a motivation.

**Enforcement is root-only, by construction.** One `openddil-pep` Deployment;
the NetworkPolicy's `podSelector` names `component: electric-sync` — the
root's Electric. A tier's `tier-electric-<id>` is **not** covered, and the
tier frontend has **no** PEP wiring (`grep -c OPENDDIL_PEP_UPSTREAM` over the
tier-node frontend block returns 0).

So today, a tier node's read path would be unauthenticated and unfiltered —
and per §3 it would be reading the root's store. Those two defects compose
into the worst available combination, which is the argument for fixing them
in the same arc rather than in two.

**What Slice 1 got RIGHT for this arc, and should be preserved:**

- `useSession` fetches `/auth/me` **same-origin**. It is therefore
  tier-correct by construction: whichever tier serves the page answers about
  its own session. Nothing to parameterize.
- The identity badge reads nations from **Topaz**, not from a token claim.
  That is already the role-within-tier axis the arc must keep distinct.
- The PEP takes an issuer URL rather than embedding an identity provider, so
  per-tier instances need configuration, not code.

**The axis separation the arc must not collapse.** Slice 1 makes it concrete
for the first time:

| axis | source | today | what the arc must not do |
|---|---|---|---|
| **which tier** | the node's own config — *where you logged in* | a tab | derive it from the subject |
| **role within tier** | subject attributes via Topaz | not modelled | fold it into the tier parameter |

A maintainer and a commander at the same node are the **same tier instance,
different role**. An edge maintainer and an HQ commander are **different tier
instances**. The current tab list conflates both into one four-item enum, and
that conflation is what makes "which of the three views does a fourth tier
get?" unanswerable — the question is malformed, not merely unanswered.

---

## 5. What is genuinely cheap, and why the estimate is better than GD-04 implies

GD-04 reads as a rewrite. The inventory says otherwise:

- **two files** carry literal tier names;
- the **rollup panel set is already shared** between two of the three views;
- the **config channel already exists** and already carries the edge→region
  topology a subtree resolver would need at the depths that exist;
- the **scope hooks already take a parameter** — they just take two
  differently-named ones.

The expensive part of this arc is **entirely** GD-01. The frontend part is
smaller than its register row suggests, and the register row should probably
say so once this is confirmed by doing it.

---

## 6. Proposed opening sequence — for a go-signal, not for execution

**Step 1 — collapse the two scope hooks into one, parameter-driven.**
`useFleetAssetsForTier(scope)` where `scope` is `{column, value}` resolved
from config rather than chosen by the call site. Purely mechanical, no
behaviour change at either existing depth, and it makes GD-01's blast radius
in the frontend a **single function** instead of a pattern.
*Blocks nothing; makes everything after it smaller.*

**Step 2 — the tier parameter, delivered through `deployment.json`.**
A `tier: { id, depth, parent, children[] }` block beside the existing `fobs`.
Read once at startup by the module that already does this. The panel set
becomes a function of the tier's **shape** — *has children? has a parent?* —
not of its name.

> **Acceptance for step 2 is NOT the fourth tier.** It is: the same bundle,
> given two different `deployment.json` files, renders the maintainer
> instance and the HQ instance with **no tab switcher and no code
> difference**. That is reachable today and is the property the capstone
> recording needs.

**Step 3 — fix §3 before anything ships to a tier node.** Either bake
nothing and drive the upstream entirely from `OPENDDIL_ELECTRIC_UPSTREAM`
(which the Slice 1 nginx change already made possible), or delete the inert
`ELECTRIC_URL` env and its comment. **Deleting the comment is not optional**
— it is currently the only thing asserting a property the deployment does
not have.

**Step 4 — per-tier PEP.** The chart grows `releasability` per tier node
rather than once at the root, and the NetworkPolicy follows the tier's own
Electric. Independent of steps 1–3 and of GD-01; it is Slice 1's own
generalization and arguably belongs to Slice 1's register rather than this
arc's.

**Step 5 — role within tier, from Topaz.** The second axis. Panels become
`(tier shape) × (role)`. Slice 1 built the seam; this consumes it. **Do not
start before step 2**, or the two axes will be modelled as one and the
current conflation will simply move.

**Step 6 — the demo shell becomes a consumer.** If the one-pane
three-tab view is still wanted, it composes tier instances instead of being
them. The amendment already blesses this as *legitimate as a demo shell,
honestly labelled, possibly indefinitely.*

**Step 7 — GATED ON GD-01. The fourth tier.** Hierarchy-path addressing on
the wire and in the schema; the scope hook from step 1 takes a path rather
than a column; the acceptance criterion becomes reachable and is then
tested.

### The one thing to settle before step 1

**Whether this arc owns GD-01 or merely blocks on it.** Both are defensible
and they produce very different plans:

- *Owns it:* the arc is large, spans proto/schema/projector/aggregators/
  frontend, and delivers the stated acceptance criterion.
- *Blocks on it:* the arc delivers steps 1–6, the capstone recording gets
  what it needs, and GD-01 stays a separately-scheduled piece of work whose
  own forcing function is now sharper for having a named consumer.

**Recommendation: block on it, and say so in GD-04.** The presentation work
is worth doing on its own merits — it removes a live mode-confusion hazard,
it is small, and it unblocks a recording that is otherwise not worth making.
Bundling it with the deepest change in the corpus would delay all of that
behind the most expensive thing in the register. But this is a scoping
decision and it sits behind the go-signal like everything else here.

---

## 7. What this package did not establish

Per ADR-0037 clause 6.

- **No tier node was deployed.** `tierNode.enabled: false`, and it was not
  turned on. §3 and §4 are read from the template and from the frontend
  build, not observed on a running tier node. The env-var claim is strong
  (a build-time Vite variable cannot be set by a container env, and the
  nginx default is in the entrypoint script) but it is a reading.
- **Panel-level tier assumptions were not inventoried.** §1 counts hook
  usage and literal tier strings; it does not establish that every panel
  *renders* sensibly at an arbitrary depth. A panel that assumes it has
  children, or assumes it has a parent, would not appear in either count.
  **That inventory is step 2's real work and its cost is not estimated
  here.**
- **The 3D scenes were not examined at all.** They are the largest components
  and the most likely to carry a depth assumption in geometry rather than in
  a hook. Nothing in this package should be read as an estimate that
  includes them.
- **`ControllerApp` was not classified.** It is the DDIL controller, and
  whether it is a tier instance, a cross-tier operator tool, or a demo
  affordance is undecided. It is the one tab that may legitimately not be a
  tier view.
- **GD-01's cost was not re-estimated.** The row's own words are used as-is;
  no attempt was made to size hierarchy-path addressing.
- **Role-within-tier has no modelled vocabulary.** §4 asserts the axis must
  stay distinct and does not propose what roles exist. That is step 5's
  question and it will need the same declared-not-inferred discipline
  ADR-0029 §5 applied to nations.

---

## Related

- **ADR-0033** §Tier-parameterized presentation — the amendment this arc
  implements; the forcing function it names is §2's subject.
- **ADR-0032** §d/§e — the tier node's UI slot, and each node serving its
  own; §3 is that corollary being violated by a variable nobody reads.
- **ADR-0029** — Slice 1; §4's axis table and the role-from-Topaz seam.
- **GD-01** — hierarchy-path addressing. §2 establishes this arc as
  downstream of it.
- **GD-04** — this arc's register row; §5 argues its cost estimate is
  pessimistic and §6 recommends recording the GD-01 dependency in it.
- **`PLAN-arc2-slice1-opening-package.md`** — same method, and §2 is the
  same shape as that package's §2: an arc whose acceptance test lives in a
  layer the arc does not touch.
- **`PRINCIPLES.md`** §*A documented hazard is not a mitigated one* (§3's
  comment is the only thing asserting a property the deployment lacks),
  §*Enter a sweep from the narrow end* (§7's first limit).
