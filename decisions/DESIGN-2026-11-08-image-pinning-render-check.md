# DESIGN 2026-11-08 — every image by digest, every Dockerfile from its lock, and the check that fails on a tag

**Status:** a design, for a row in `FOLLOW-UPS.md`. Nothing built, nothing run. Line numbers are from a read of the chart
at 0.1.161 and the Dockerfiles at their current tips, and move with them. `ADR-0057` lists image pinning as open; this
is that item's design.
**Builds on:** the chart's render guards (`scripts/check-chart-render.sh`, `.github/workflows/chart-checks.yml`) and its
include-only guard pattern (`templates/_algorithms.tpl:70`, `templates/algorithms-guard.yaml:3`).

## What is true today

**The chart.** 33 image blocks render by default, and a 34th (`frontend.terrain.image`) is empty unless set. Every block
has a `digest` field, and no template hard-codes an image.

| | Blocks | Default reference |
|---|---|---|
| By digest | 3 | `topaz` (two blocks), `ghostunnel` |
| OpenDDIL-owned, by tag | 14 | `:latest`, through `global.imageTag` |
| Third-party, by tag | 16 | versions and minor-version tags, such as `postgres:15`, `python:3.11-slim`, `alpine:3.20` |

Deployments reach a digest today only by setting it in their own values.

**The Dockerfiles.** 21 outside the `wt/` worktrees. None has a digest on a `FROM`.

| | Count | Which |
|---|---|---|
| Lock used | 1 | frontend, `npm ci`, which falls back silently to `npm install` |
| Python, lock in context, ignored | 5 | sensor-ingest, logistics-sim, tactical-agents `edge/faust`, `edge/restate`, `hub/projector` |
| Python, no lock reachable | 12 | cm-service, logistics-fusion, projector, asset-registry, dds-ingestor, tactical-agents `edge` and `regional`, egress, tak, simulator, dis-sim, asterix-reference |
| No language dependencies | 3 | bundle, terrain-image, reset-runner (`apk add` only) |

Every `uv` flow runs `uv pip compile pyproject.toml` during the build, so each build re-resolves. `tactical-agents`
`edge/Dockerfile` pins one package with `==` and has `./edge` as its build context; the repository's `uv.lock` is at the
root, out of that context, and was resolved from a dependency set without two of that image's packages. A build-context
change alone does not fix it.

## Four things the design has to get right

1. **A digest silently overrides a tag.** `openddil.image` and `openddil.thirdPartyImage` ignore the tag when `digest` is
   set. Put a digest in a default and a deployment's `electric.image.tag: 1.8.1` keeps rendering the old image, with no
   error. So digests must not sit beside the tag as a second free field. See the pin table below.
2. **`render()` discards stderr.** `check-chart-render.sh:21` is `helm template ... 2>/dev/null`. A template `fail` gives
   empty output, and a check that walks empty output finds no tags and passes. The guard must see helm's exit status and
   refuse a render with no images.
3. **Pod specs are not the only place an image is written.** `exercise-control.yaml:214-215` passes `ELECTRIC_IMAGE` and
   `RESET_RUNNER_IMAGE` as environment values, and builds a Job's pod spec as a dict. A guard reading only
   `containers[].image` misses these.
4. **Pinning must not upgrade anything.** The digest a tag points to today may not be what a cluster is running. Pin to the
   digest each deployment runs (`imageID` on its pods), not to a fresh registry lookup, and predict the roll: changing an
   image string rolls that workload, a broker and a store among them.

## The design

### 1. A pin table, not a second field

Add `global.images.pins`, a map from a full default reference to its digest:

```yaml
global:
  images:
    requireDigest: true
    pins:
      "electricsql/electric:1.6.2": "sha256:..."
```

Both helpers resolve in this order: the block's own `digest`, then `pins[<repository>:<tag>]`, then, with `requireDigest`
on, a `fail` that names the block and the reference. Changing a tag with no matching pin now stops the render instead of
rendering the old image. A deployment on a mirror, whose repository differs from the key, sets the block's `digest` as
`values-artifactory.yaml` does today.

The `digest` field stays as the deployment's override, and the shipped `values.yaml` keeps it empty.

### 2. Owned images: pins written at release

A pin keyed on `:latest` means nothing, so owned images need a real tag. A chart release sets `global.imageTag` to the
release's image tag and writes the 14 owned pins from the digests CI built, into the packaged chart. The git tree keeps
the release step's output in `values-pins.yaml` beside `values.yaml`, so a reader sees what a version pinned.

This depends on the `fix/ci-latest-master-only` workflow row, because `:latest` has already moved to an unmerged
branch's image once, and on the chart-bump signal row.

### 3. The render check

Guard N in `scripts/check-chart-render.sh`, in the numbered style. It runs across the variants guard 21 uses (default,
`tierNode`, releasability, `ephemeralOnUpgrade`, everything on), each with `values-pins.yaml`.

- Calls helm directly and fails on a non-zero exit, unlike `render()`.
- Walks every document with the workflow's existing pyyaml. It collects every `image` key at any depth, every environment
  entry whose name ends in `_IMAGE`, and the same two inside any string that parses as JSON or YAML.
- Fails on any value that does not match `^[^@\s]+@sha256:[0-9a-f]{64}$`, printing kind, name, container and value.
- Fails if a variant collects no images, or fewer than `openddil.renderedImages` lists for it. A guard with nothing to
  read must not pass.
- Fails if any file the chart ships sets `requireDigest: false`.

No exception list. An image that cannot be pinned is a row in this file until it can.

**The in-template layer** is `templates/images-guard.yaml` including `openddil.images.validate`, on the
`algorithms-guard` pattern, looping over `openddil.renderedImages` (`_helpers.tpl:2635`). It is what stops an operator's
`helm install`. It covers what the helpers build, including the environment values above, which is the reason to have
both layers. `frontend.terrain.image`'s own check at `_helpers.tpl:2072` narrows from "tag or digest" to the same rule.

**A red-check step** in `chart-checks.yml`, like the existing ones, plants a real tag in one owned block and one
third-party block and asserts the guard goes red on each, naming the block. Without it, the guard's coverage is a claim.

### 4. Dockerfiles from their lock

Replace `uv pip compile pyproject.toml -o requirements.txt` with:

```
uv export --locked --no-dev --no-emit-project -o requirements.txt
uv pip install --require-hashes -r requirements.txt
```

`--locked` fails the build if `uv.lock` disagrees with `pyproject.toml`. By group:

| Group | Change |
|---|---|
| The 5 with a lock in context | The two lines above |
| cm-service, logistics-fusion, projector, asset-registry, simulator | Add `uv.lock`, then the two lines |
| tactical-agents `edge`, `regional` | Add `pyproject.toml` and `uv.lock` inside each directory, keeping the `./edge` and `./regional` contexts |
| egress | Move the inline ranges to `egress/pyproject.toml`, add a lock |
| tak, dis-sim, asterix-reference | One pinned package each, transitive dependencies float. A small `pyproject.toml` and lock each |
| dds-ingestor | Its build context is unconfirmed. Read it first |
| frontend | Drop the `\|\| npm install` fallback |

**Whether every project locks cleanly is not read.** A dependency on a sibling repository by path needs the lock to
resolve in CI's layout.

**The Dockerfile check** is a script: any `pip install <name>`, `uv pip install <name>` or `uv pip compile` in a Dockerfile
fails it. `npm install` does too. It runs in each repository through one reusable workflow in `openddil-contracts`, so
there is one copy, and each repository's CI calls it. It has its own red test: a planted `pip install` line fails it.

## Order

| Stage | What | Who sees it |
|---|---|---|
| 1 | Pin table and helpers, `requireDigest` off. Third-party pins, each from what the deployments run | A roll for every pinned workload whose reference string changes; predict it, hooks included |
| 2 | The guard and its red-check on third-party references only | CI |
| 3 | Owned pins at release, after the CI row; guard covers all | Next chart release |
| 4 | `requireDigest` on | Any overlay still on a tag fails at render, naming the block |
| 5 | Dockerfiles from their lock, repository by repository; check on | Each image rebuilds from its lock once, and its contents may change: a rebuild to soak, not a formality |

Stage 4 waits until every deployment's values pass. Stage 5's first lock should be resolved from what the current image
holds where that can be read, so that adopting the lock is not itself an upgrade.

## Not in this design

- **`FROM` lines.** The order is the chart's images and the lock. 0 of 21 carry a digest, so the base image still floats
  under a locked dependency set. It needs its own row and the same check shape.
- **`apt-get` and `apk add` versions.**
- **`grpcio-tools` in the contracts CI.** It is installed unpinned, and a newer version's bindings broke an older
  protobuf locally. The fix is one line, tracked in the row.

## Checks

1. A values file with a tag and no pin fails the render, naming the block.
2. Changing a block's tag without changing its pin fails the render.
3. A render in which helm fails makes the guard fail, not pass.
4. A planted tag on an owned block and on a third-party block each turn the guard red.
5. An `_IMAGE` environment value carrying a tag turns the guard red.
6. A shipped file with `requireDigest: false` fails the guard.
7. A Dockerfile with `pip install <name>` fails the Dockerfile check.
8. A `uv.lock` out of step with `pyproject.toml` fails the build.

## Open

1. **Where the pins live for the git tree:** `values-pins.yaml` as here, or only in the packaged chart. Recommended: in
   git, so a version's pins can be read and diffed.
2. **Whether to pin Stage 1's third-party references to the deployments' running digests when deployments differ.** If
   they differ, one of them changes at that roll. Recommended: take the digest that ran longest under load, and declare
   the other's roll.
