# ADR-0017: UI Mock Components Must Self-Identify

## Status

Accepted — 2026-05-14

## Context

The Phase 4 pre-flight inventory found the OpenDDIL UI had drifted into a
state where it was impossible to tell, by looking at the running app,
which surfaces showed real pipeline data and which were rendering
hardcoded mock data. The "offline-first demo" from Phase 0 turned out to
be demonstrating hardcoded fallback arrays, not real cached state —
because the real data path had never worked end-to-end in that compose
topology, and nothing in the UI made that visible.

This happened because OpenDDIL evolved demo-driven (UI against mocks) and
data-driven (pipeline against real protocols) in parallel, with neither
side aware of the other. A mock with no marker is indistinguishable from
a working integration until someone goes looking — and by then the drift
is large.

Phase 4 is the convergence point: the UI is being wired to the real
pipeline via the projector and ElectricSQL. But not everything wires up
at once. Some components (the 3D maintainer views especially — see
Decision 4 / LtamdsView) are deliberately preserved against synthetic
data, pending a future feed (RTI / Cyber DDS). Those legitimate mocks
must not become invisible drift again.

## Decision

**Every UI component that renders against synthetic, hardcoded, or
otherwise non-pipeline data must self-identify.** Concretely, such a
component has all three of:

1. **A `const DEMO_MOCK = true;`** near the top of the file. A grep for
   `DEMO_MOCK` enumerates every mock surface in the codebase.
2. **A visible banner in the rendered output** — the shared
   `<DemoMockBanner note="..." />` component (a small amber corner
   badge). The `note` says what is mocked and/or what real source it is
   waiting on.
3. **A comment block at the top of the file** explaining what is mocked,
   why it is still a mock, and what real data source it will wire to in a
   future phase.

### The standing rule

Going forward: **no orphan mocks.** A UI component either reads real
pipeline data, or it openly declares itself a mock pending real wiring.
There is no third state. A component that "will be wired up later" with
no marker is a defect, not a deferral.

### Exception: pure react-three-fiber primitives

A component that renders only 3D primitives (`<mesh>`, `<group>`, ...)
with no DOM wrapper cannot host a DOM `<DemoMockBanner>` — a DOM node
cannot live inside a `<Canvas>`. Such components (e.g.
`TacticalMapUnderlay`, `AssetSpawner`) carry requirements (1) and (3) —
the `const` and the comment block — and the comment explicitly states
why the visible banner is absent. The parent component that mounts the
`<Canvas>` is responsible for any view-level banner.

## Consequences

**Pros**

- The running UI is honest. A reviewer, a customer, or a future engineer
  can see at a glance which surfaces are real and which are mock.
- `grep -rn DEMO_MOCK` is a complete, always-current inventory of mock
  surfaces — no separate doc to keep in sync.
- The Phase 0 failure mode (invisible mock drift) cannot recur silently:
  a new mock without the marker is a visible review miss, and a mock
  that gets wired to real data has its marker removed as part of that
  work.

**Cons**

- Small per-component overhead: three things to add, three things to
  remove when a mock becomes real. Mitigated by the shared
  `DemoMockBanner` component (the banner is one line) and by the fact
  that the overhead is exactly proportional to how much mock surface
  exists — which is the incentive we want.
- The amber badge is visible in demos. This is intentional: a demo that
  hides which parts are mock is the problem this ADR exists to prevent.
  If a specific customer demo needs the badges suppressed, that is a
  build-time flag decision, not a reason to drop the markers.

**Rejected alternatives**

- *A central registry / doc of mock components.* Rejected: a doc drifts
  from the code. The marker lives in the component, travels with it, and
  is enforced at review time where the code is read.
- *Console warnings instead of a visible banner.* Rejected: the failure
  mode is a mock looking real to someone watching the UI. A console
  warning does not reach that person. The signal has to be on screen.

## Related

- ADR-0019 — Single Kafka→Postgres Projector. The real data path that
  Phase 4 wires the UI to; everything not yet on it is a DEMO_MOCK.
- ADR-0013 — Physical Quantity Consistency. The Quantity shape the real
  telemetry path delivers; mock components render synthetic numbers
  instead.

## Notes for future maintainers

- The shared banner component is
  `openddil-demo/frontend/src/components/DemoMockBanner.tsx`.
- As of Phase 4b, the marked components are: `LtamdsView`,
  `DiagnosticCanvas`, `BattleView`, `LocalFleetRadar` (DOM banner +
  const + comment), and `TacticalMapUnderlay`, `AssetSpawner` (const +
  comment only — pure-3D primitives).
- The regional and HQ view components (`RegionalApp`, `HqApp`, and their
  children) are still mock as of Phase 4b but are NOT yet marked — they
  are rewired or marked in Phase 4c, per the phase boundary. When 4c
  touches each one, it either wires it to real shapes or applies this
  ADR's marker. A 4c exit check should be `grep -rn DEMO_MOCK` plus a
  confirmation that no regional/hq component renders mock data without
  the marker.
