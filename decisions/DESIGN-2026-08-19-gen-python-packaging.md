# Design — the generated protobuf bindings should be a package

**Date:** 2026-08-19 · **Design only; no build.** GD-13. The cross-repo
change rides a day block; this is the survey and the shape.

## 1. It is not three mechanisms. It is five.

GD-13 was written as *"three services, three invented answers."* Surveying
properly found two more, and the extra ones matter because they are the ones
that reach production:

| # | consumer | mechanism |
|---|---|---|
| 1 | `cm-service` tests | `sys.path.insert` repeated **at the top of every test module** |
| 2 | `fusion` tests | `sys.path.insert` in `conftest.py` (added 2026-08-15) |
| 3 | `projector` tests | `sys.path.insert` in `conftest.py` (added 2026-08-15) |
| 4 | **every container at runtime** | `ENV PYTHONPATH=/proto:…`, where `/proto` is **copied out of the bundle image** by an init container at pod start |
| 5 | **CI** | sibling-repo checkout at a path the conftest expects (added 2026-08-15) |

**Not one of the five declares a dependency.** Each is a different way of
arranging for a directory to be on a path, and none of them names a
*version*.

*The count matters more than it looks.* Three mechanisms is a tidiness
problem. Five — spanning tests, CI and runtime, with the runtime one riding
a separate image-build pipeline — is a **contract with no interface**: the
generated code crosses four repository boundaries and its only specification
is a filesystem layout each consumer restates.

## 2. What the current arrangement cannot express

**A version.** `gen/python` is whatever the contracts repo happened to
contain when the bundle was last built. A service cannot say *"I was built
against these bindings"*, and nothing can detect that it is running against
different ones.

That is not hypothetical — it is the recurring **schema-versus-projector
drift**: the bundle image's Atlas migrations lag the projector code, and the
symptom is a runtime `column X does not exist`. The same shape appeared this
week in the labelled-table set differing between `schema.hcl` and the
deployed schema. **Both are one defect: the generated artifacts and the code
that consumes them have no declared relationship**, so they drift silently
and are discovered at runtime by a query that fails.

**A failure at the right time.** Mechanism 4 fails at *pod start*;
mechanisms 1–3 fail at *collection*, which is how a suite stayed dead for two
months (VE-8). A declared dependency fails at *install*, which is the only
one of the three that happens while someone is looking.

## 3. The three candidate shapes

| | what it is | fixes | leaves |
|---|---|---|---|
| **(a) installable distribution** | `gen/python` gains packaging metadata and is published as `openddil-contracts-gen==<version>`; consumers `pip install` it | mechanisms 1, 2, 3, 5 — and gives the version a name | mechanism 4 unless the image installs it too (it can) |
| **(b) editable install via each repo's bootstrap** | `pip install -e ../openddil-contracts/gen/python` in a setup step | the same four, **without** publishing | keeps the sibling-checkout layout assumption — the thing that made CI fragile |
| **(c) declare path injection once per repo** | what exists today, tidied | nothing structural | every problem in §2 |

**Recommendation: (a), and the argument is version rather than tidiness.**
(b) and (c) both make the current arrangement neater; only (a) makes the
proto version a **declared, resolvable dependency** — which is what turns
drift from a runtime surprise into an install-time conflict.

*(c) is not a strawman:* it is the current state after this week's fixes, it
works, and it costs nothing. It is rejected because it cannot answer *"which
bindings is this service built against?"* — and that question is the one
behind two recurring defect families.

**Version scheme:** date-based, matching the migration convention already in
use (`20260807000000`), rather than semver. The bindings are generated
artifacts of a schema whose compatibility story is proto3's, not a library
with an API contract to promise. A semver on generated code would imply a
guarantee nobody is making.

## 4. Migration plan, per repo

Ordered so nothing breaks mid-flight. **Every step is additive until the
last**, and the last is deletion of what is by then unused.

**Step 1 — contracts publishes.** Add packaging metadata under `gen/python`
and a `make package` target beside the existing `make python`. Publish to
the same registry the images use. *Nothing consumes it yet.*

**Step 2 — services declare it**, one repo at a time, in this order:
`projector` → `fusion` → `cm-service` (fewest sys.path sites first, so the
last migration is the one with the most prior art). Each adds the dependency
to `pyproject.toml` **alongside** the existing conftest injection. Both
paths resolve to the same modules; the injection wins only if the package is
absent, so a half-migrated tree still runs.

**Step 3 — CI drops the sibling checkout.** Once a repo declares the
dependency, `python-checks.yml` no longer needs to check out contracts at a
specific path. *This is the step that proves the migration for that repo:*
if the suite passes without the sibling repo, the package is genuinely
supplying the bindings.

**Step 4 — images install rather than mount.** Dockerfiles `pip install` the
pinned version; the init-container copy of `contracts/gen/python` into
`/proto` is removed from the chart. **This is the step that changes
deployment behaviour**, and it is last for that reason. It also makes each
image's binding version visible in its own build.

**Step 5 — delete the injections.** Only after 3 and 4 pass everywhere.

## 5. What must be checked before step 4

**The bundle image carries more than the bindings.** `/proto` is one of
several subtrees the init container copies (ontology, connect configs).
Step 4 removes *one* of them and must not disturb the others — the mount
mechanism stays, with one fewer tenant.

**And the ontology has the same problem**, unexamined here: it is read from
`/ontology` by fusion, by the DIS appearance decoder, and by Bloblang
mappings via absolute paths, with no version anywhere. If step 4 succeeds
for the bindings, the identical argument applies to the ontology, and it
should be taken up deliberately rather than by analogy.

## 6. What this did not establish

- **No packaging was written or tested.** The metadata shape, the registry
  choice, and whether the generated tree imports cleanly as an installed
  package rather than a path entry are all unverified.
- **The C#/other generated outputs were not surveyed.** `make all` produces
  `csharp` too; whether it has the same problem is unknown.
- **No consumer outside these four repos was checked.** Anything else
  importing `openddil.*` would be a sixth mechanism.
- **Cost is estimated, not measured.** "A day block" is the standing
  estimate; nothing here validates it.
