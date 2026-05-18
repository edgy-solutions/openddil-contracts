# ADR-0025: Build-Pass Deployment Verification Discipline

## Status

Accepted — 2026-05-17 — **Methodology / build-pass discipline.** Captures
the lesson from Phase 6c.1's eye-candy investigation: the §C.1 frontend
rewiring shipped correct code and correct tests, but the user's browser
still showed the pre-§C.1 build because the frontend image was never
rebuilt + the container never recreated. The deployed bundle was stale;
the tests passed because they exercised the Shape API directly,
bypassing the frontend entirely.

The procedural form of this rule is tracked-follow-up #16 (in
`openddil-demo/tests/hero_scenario_v3/README.md`), scoped specifically
to the frontend's static-build deployment. This ADR is the principled
form — the underlying rule that #16 is one instance of.

## Context

OpenDDIL has multiple deployment indirection styles depending on the
service:

- **Dev hot-reload (bind-mount)**: Python services with source mounted
  read-only into `/app/*`. Edit a file on the host, the container's
  next request sees the new code. faust-edge, faust-regional, cm-service,
  fusion-service, projector all follow this pattern.
- **Dev local-build (no mount)**: Static-build services where the
  Dockerfile produces a final artifact that nginx serves. The
  `docker-compose.override.yml` mounts no source — `pull_policy: build`
  builds the image locally but the image is what gets served, NOT the
  host source tree. The frontend follows this pattern (explicit comment
  in `openddil-demo/docker-compose.override.yml`).
- **Registry pull**: production-style, image pulled from
  `ghcr.io/edgy-solutions/...`. Only used when override is absent or
  bypassed.

Phase 6c.1's investigation found that the build-pass discipline that
worked for §A, §B, and the §B follow-ups (bind-mount Python; restart
container; new code is live) silently failed for §C.1 (static-build
frontend; edit source; container still serves the OLD image until
rebuild). The automated verification — `test_47` (dual-sum sanity) and
`test_48` (regional pulldown scope) — both PASSED, because they query
the Electric Shape API via `curl`. The Shape API is unchanged by
frontend code, so it returns the correctly-filtered data regardless
of which frontend bundle the browser loads.

The user caught it by eye-balling the live system: both `?region=
region-east` and `?region=region-west` rendered identical content
("AOR ASSETS (17)" in both, when region-west should have shown 2).
Diagnosis trace ruled out a code bug, ruled out a hook bug, ruled
out a Shape API bug — and landed on "the frontend image wasn't
rebuilt." Rebuild + force-recreate the container, and the live system
matched what the tests said it did.

## Decision

**For any sub-phase that touches code in a deployment-indirected
service, the observable-end-state verification must include BOTH:**

**(a) automated tests passing at the test surface they target, AND**

**(b) confirmation that the live deployment is running the new code.**

The two are complementary. (a) verifies the code path is correct
when exercised. (b) verifies the live deployment exercises that code
path at all. Without (b), (a) is a green light on a code path the
user's browser will never hit until somebody rebuilds the image.

### Operationally

- **Hot-reload services (bind-mount Python)**: A container restart
  (`docker compose restart <service>`) picks up source changes. The
  restart itself is the deployment proof; check service logs to
  confirm the new code's log lines appear.
- **Static-build services (frontend, etc.)**: `docker compose build
  <service>` + `docker compose up -d --force-recreate <service>` is
  mandatory. Then EITHER grep the served bundle for a known-new
  string (`curl http://localhost:.../bundle.js | grep -o "<known-new-symbol>"`)
  OR compare the served bundle's hash to a known-old value. The
  build alone is not deployment proof; force-recreate is what
  swaps the running container.
- **Registry-pull services (production-style)**: deployment proof
  means the new image is pushed AND the deployment pulled it. Not
  typically in dev-loop scope, but the same principle applies.

### Test surface vs deployment surface

A test passes against the surface it targets. The Shape API tests
(test_47, test_48) target the database-through-Electric layer. They
do not — and should not — target the React frontend. The principled
implication is: **the closer a test's surface is to the bottom of
the stack, the more indirection sits between it and what the user
sees, and the more important explicit deployment verification
becomes.**

The mistake to avoid: treating "tests passed" as a proxy for "the
live system shows the user the new behavior." Tests prove
correctness of the path they exercise. Deployment proof is a
separate concern.

## Consequences

**Pros**

- Future sub-phases have explicit guidance for the verification
  step that was implicit (and silently violated) in §C.1.
- The pattern is service-specific (hot-reload vs static-build vs
  registry-pull), so the rule isn't "always rebuild everything" —
  it's "match the verification step to the deployment style of
  the service you touched."
- Makes the eye-candy lesson generalizable. The eye-candy rule
  ("static checks don't substitute for browser walkthroughs on
  visual work") was scoped to visual work; this ADR generalizes
  it to ALL deployment-indirected code: "automated tests don't
  substitute for confirming the deployment got the new code."

**Cons**

- Adds a step to the build-pass checklist for static-build
  services. Marginal cost; large-payoff insurance.
- Cannot be enforced by the test infrastructure alone — it's a
  discipline rule the build pass must follow. Same shape as
  "follow-ups get logged before being forgotten" and other
  discipline rules captured in earlier ADRs.

## Related

- **ADR-0024 — Multi-Cluster Faust Aggregator Pattern.** Same shape
  of artifact — empirical-architecture finding from a phase's build
  pass, captured durably so the lesson is findable from the
  architecture view rather than only from commit logs.
- **`openddil-demo/tests/hero_scenario_v3/README.md` follow-up #16.**
  The procedural form scoped specifically to frontend static builds.
- **`openddil-demo/docker-compose.override.yml`** — the frontend
  block comment that names the no-mount static-build constraint.
  That comment was already there; the §C.1 build pass missed it.
  This ADR makes the rule the comment implies a load-bearing build-
  pass discipline rather than an easy-to-miss readme note.

## Notes for future maintainers

- **When in doubt, grep the served artifact for a known-new symbol.**
  Adding a single distinctive string in the change (a new component
  name, a new tracked-follow-up label, an ADR number reference) makes
  the deployment check a one-liner.
- **The Python services don't have this problem TODAY** because their
  override mounts source bind-mounts. If a future Python service moves
  to a baked-image-no-mount pattern (e.g., production-style demo),
  the rule transfers.
- **`docker compose restart` vs `docker compose up -d --force-recreate`:**
  `restart` re-runs the container with the same image; `--force-recreate`
  destroys and re-creates from the (possibly newly-built) image. For
  static-build services, only the latter picks up rebuilds.
