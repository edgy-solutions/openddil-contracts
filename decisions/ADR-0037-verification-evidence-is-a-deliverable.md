# ADR-0037: Verification evidence is a deliverable

## Status

Accepted — 2026-08-11. **Standing engineering position.** States the rule
behind practices this project already has (the decisions/ audit series,
the runbook's expected-output form, the recording-as-proof-artifact
framing) and registers, honestly, the places where evidence is still
produced and then lost.

## Context

ADR-0025 established that **automated tests prove the code path, not the
deployment**: `test_47` and `test_48` passed against the Shape API while
the operator's browser served a pre-change frontend bundle, because the
image was never rebuilt. Every automated signal was green because every
automated signal was answering a different question.

That lesson has since recurred in a different shape often enough to
generalize past deployment. `PRINCIPLES.md` §*A deliverable's
self-description is a claim* records a chart template whose header block
listed nine components and rendered seven — `helm lint` passed, the
render exited zero, and **fusion and cm-service were described and never
built**. Same structure: a green signal answering *did this run?* when
the question was *did it produce what it says it produced?*

The pattern behind both: **the artifact of a verification is usually a
transient** — an exit code, a console summary, a terminal scrollback, a
person's recollection of having looked. Transients cannot be re-read,
cannot be cited by a later claim, and cannot be checked against the claim
they are supposed to support. So the claim outlives its evidence, and by
the time someone needs the evidence it exists only as confidence.

This project already fights that in three places, without having named
the rule:

- **The decisions/ series carries findings, not conclusions.**
  `AUDIT-2026-08-07` (aggregation composability), `AUDIT-2026-08-08`
  (severance tolerance), `AUDIT-2026-08-09` (schema provenance),
  `BRIEF-2026-08-08`, `DESIGN-2026-08-11` — each is a durable record of
  what was read, what was concluded, and what was **not** established.
- **`GENERALIZATION-DEBT.md` closes rows rather than deleting them**,
  because the record of what *was* hardcoded is useful. GD-09 goes
  further and carries its own mid-row correction, so a wrong claim and
  its retraction are both readable.
- **`PILOT-RUNBOOK.md` treats a recording as the deliverable**, not a
  byproduct — *"Step 5 is the reason the whole arc exists; it produces a
  recording, and the recording is a deliverable"* — and gives every step
  an **expect** clause plus a stop-and-report branch.

Naming the rule turns three good habits into one checkable standard, and
makes the gaps visible as gaps.

## Decision

**A verification claim cites a durable artifact. Where no artifact
exists, the claim is stated as unverified.**

### 1. The four evidence forms

Each has a form, a home, and a thing it is competent to prove.

| Form | Home | Proves |
|---|---|---|
| **Finding document** — audit / brief / design, with scope and did-not-establish sections | `openddil-contracts/decisions/` | What a reading of the system established, and what it did not |
| **Executed procedure** — steps with *expect* clauses, stop-and-report branches, and captured outputs | Runbook in the owning repo; captured outputs returned with the report | That a specific deployment behaves as described, at a named site, on a named chart version |
| **Test run** — asserting parsed structure or exact equality | Test suite in the owning repo | That a code path is correct when exercised |
| **Measured pair** — before/after readings from the real system | The change's record (ADR, row, or runbook note) | That an instrument or fix changed the observable it claims to change |

The forms are not interchangeable. A test run cannot prove a deployment;
an executed procedure at one site cannot prove a fleet; a finding
document derived from source cannot prove runtime behaviour. **A claim
inherits the competence of its evidence form**, and where it reaches past
that, it says so — the severance-tolerance table is derived from charts
and source and states this in its own scope limits.

#### Named limits — evidence that looks stronger than it is

Added as they are earned. Each is a case where a check *ran, passed, and
proved less than the reader would assume*, which is more dangerous than a
check that was skipped.

- **Schema inspection proves a schema, never a producer.** `\d`,
  `information_schema`, a migration that applied cleanly — all confirm a
  column exists. **None of them distinguish a column that is written from
  one that nothing has ever written**, because the observable is
  identical in both cases. A phase whose deliverable is schema therefore
  reports complete on evidence that cannot see its own most likely
  failure. *Earned 2026-08-12:* ADR-0029's releasability columns shipped
  correctly typed and indexed across five tables, and were verified as
  present. A later query found **42 populated rows, zero labelled** —
  nothing writes them, and nothing could, since the fields are in no
  `.proto`. To claim a column is *populated*, count non-nulls over a
  table with rows; a count over an empty table is vacuous and must not be
  reported as evidence.
  See `PLAN-arc2-slice1-opening-package.md` §2.

- **A test proves the layer it operates at, and silently exempts the
  layers below it.** *Earned the same day:* a golden-file suite running
  JSON → mapping → JSON passed on seven cases that pin two fields the
  canonical proto does not declare — the encoder rejects them outright.
  Green suite, unencodable mapping, no contradiction, because the suite
  never encodes. **When a test's medium differs from production's medium,
  the difference is an untested seam**, and it will not announce itself:
  every case passes. State the medium a suite exercises next to its pass
  count.

- **A suite you have not watched START is not a suite.** Clause 3 says a
  guard is not evidence until it has been seen to *fail*. This is the
  weaker precondition it assumed: seen to **run**. *Earned 2026-08-15:*
  `openddil-cm-service/src/tests/test_baselines.py` declared
  `def test_customer-overlay_...`. A hyphen is illegal in a Python
  identifier, so the module raised `SyntaxError` **at collection** — and
  pytest **aborts the entire run** on a collection error rather than
  skipping the file. Committed 2026-06-04, found only because C4(a)
  required running the suite to verify a change.
  **Scope, established rather than assumed:** all **four** files under
  `src/tests` (`test_analyzer`, `test_asset_cm`, `test_baselines`,
  `test_persistence_model`) had not executed via the documented command —
  `pytest` from the repo root, per that repo's own `AGENTS.md` — for over
  two months. Not one file: the suite. **And no CI job invokes them.**
  cm-service's only workflow is a 57-line build-and-publish
  (`docker-build.yml`: checkout, buildx, login, tags, build), the
  Dockerfile has no test stage, and the two sibling Python services carry
  the same single workflow. Sibling suites collect cleanly, so the defect
  was local; the *exposure* was not.
  **The precise failure mode is worth separating from the obvious one.**
  There was no false green — there was **no signal at all**. Nothing was
  relying on a passing CI run of a suite that could not start, because
  nothing ran it. The failure was that the only thing standing between a
  dead suite and a human was a human doing the documented thing and
  reading an unfamiliar collection error as environmental. *Enforcement:
  a suite's pass count is part of its result — "67 passed" is evidence,
  "tests pass" is not, because the second is equally true of zero tests.*

- **A green mutation run proves nothing about the guard.** The fourth way
  a check reads green and is empty, and the only one where the emptiness
  is in the *verification of the verification*. The three above are
  checks that ran and proved less than assumed; this is a **red-check
  that failed to be a check**, and it is more dangerous because it is
  performed by someone deliberately being rigorous. *Earned 2026-08-15:*
  a mutation intended to break an integer-enum decoder left all 18 tests
  green, because the mutated form fell through the lookup to `null` —
  the right answer for the wrong reason. Full case and the enforcement
  rule in **clause 3**, which this entry points at rather than restates.

- **A mutation review cannot tell a verification gap from a coverage gap.**
  Asking *"was this guard red-checked?"* has three possible answers and the
  instrument returns two: yes, and *no evidence found*. **A guard that was
  never red-checked and a thing that was never a guard both answer the
  second**, and they need opposite responses — one is closed by running a
  mutation, the other by writing the test the mutation would have needed.
  *Earned 2026-08-15:* `munitionType.ts` was carried through a whole review
  as *red-check unknown* when in fact **nothing tests it at all**, while
  four operator-facing components import it. *Enforcement: before recording
  a guard as unverified, confirm it exists.*

*The shared shape is this ADR's own thesis turned on verification
itself:* both are instruments whose failure reading is indistinguishable
from their success reading, which is why they belong here rather than in
a test-hygiene note. Cf. `PRINCIPLES.md` §*A probe must fail
distinguishably from its own zero* — the same family, arriving at the
evidence layer.

### 2. Deployment proof is separate from test proof

ADR-0025's rule stands unchanged and is restated as a clause of this one:
observable-end-state verification requires **both** (a) automated tests
passing at the surface they target and (b) confirmation the live
deployment is running the new code. Hot-reload services prove (b) by
restart plus a new log line; static-build services require `build` +
`up -d --force-recreate` plus grepping the served artifact for a
known-new symbol; registry-pull services require the push *and* the pull.

The generalized form: **the closer a test's surface is to the bottom of
the stack, the more indirection sits between it and what the operator
sees, and the more important explicit deployment proof becomes.**

### 3. A guard is not evidence until it has been seen to fail

A green check that has never been red proves nothing about what it would
catch. Replacement checks are run against the **unfixed** artifact and
confirmed to fail before being trusted. Where a check and the thing it
checks share an author and a vocabulary, the check inherits the author's
blind spot — so prefer a second check written against a **different
representation** (parse vs. text, count vs. presence) over a more careful
version of the same one.

**The rule as stated is incomplete, and the missing half is the injected
fault.** *"Run it red"* silently assumes the failure you inject is the
failure you fear. It often is not, and then **a green run is evidence
about the mutation before it is evidence about the guard.** Stated as a
rule: a red run proves something only if the injected fault *models the
defect*; a green run means either the guard is weak **or the mutation was
wrong**, and those are not distinguishable without looking.

*Earned 2026-08-15, applying this very clause.* The C4(b) guard asserts
that a badge decodes an **integer** enum, because the JSON path carries
`basis: 1` while the protobuf path carries string names — comparing the
two is silently falsy and the badge would vanish for every real row. To
red-check it, the guard clause was swapped for a truthiness test. **All
18 tests stayed green** — not because the guard was weak, but because a
string key misses the lookup table and falls through to `null` anyway:
*right answer, wrong reason*. The mutation that actually models the
defect is keying the lookup table by string names, and against that
**six tests fail.**

Had the first result been accepted, the conclusion would have been
"verified" and the reasoning would have been backwards.

*Enforcement:* name the defect first, then write the mutation that
produces it, then check the mutation actually produces it. A mutation
that leaves everything green has failed to be a test of the guard and
must be replaced before any conclusion is drawn from it. **A green
mutation run is not a weak signal about the guard; it is no signal.**

**The limiting case — a verification that includes its own subject in its
evidence is not a verification.** Where the check *cannot* be seen red by
construction, the rule above is not merely unsatisfied, it is
unsatisfiable, and the check will read green forever.

*Earned 2026-08-12, inside the tooling written to prevent drift.* The
follow-up index ships with a command that compares the IDs in the corpus
against the rows in the index, in both directions. Its obvious form scans
`*.md` — **which includes the index itself.** Every ID written in the
index therefore appears in its own "corpus", so the second comparison,
the one that catches a phantom row or an ID renamed at home, **could
never report anything.** Half the check was decorative and looked
identical to the working half.

This is the silent-absence family turned reflexive: not *"the instrument
reads zero when it is broken"* but *"the instrument is inside what it
measures."* No amount of running it would have revealed this, because
running it is what it does successfully.

*Enforcement:* when a check's scope is defined by a pattern — a glob, a
directory, a label selector, a namespace — **ask whether the checker
itself is inside the set the pattern selects.** If it is, exclude it
explicitly and say why at the exclusion, because the line looks like
noise to the next reader and is the only thing making the check real.

### 4. Assertions are made against structure

Assertions about what a system will **receive** are made against parsed
objects, never against rendered text; status sentinels are compared by
equality and chosen so no value is a substring of another. This is a
verification-quality rule, not a style preference: seventeen substring
checks passed while three tiers received a Service with no endpoints,
because the discarded YAML document's text remained fully present in the
render.

### 5. A rehearsal declares its substitutions

Where a procedure is rehearsed somewhere other than where it will run,
the rehearsal and the real run are **one document with declared
translations**, not two procedures. `PILOT-RUNBOOK.md`'s substitution
table is the reference form: four named divergences, each with a note on
whether it affects the mechanism or only the data realism, and an
explicit statement of what the rehearsal proves at full strength
(genuine Kubernetes; the same severance mechanism) versus what it cannot
(that the numbers mean anything).

This is what keeps a rehearsal from being quietly promoted into the
official proof, and it is why the runbook can say plainly that the
work-cluster recording remains the official artifact while the rehearsal
recording is internal validation and a serviceable backup.

### 6. Every investigation states what it did not establish

A report states what it did not establish, or its silence gets read as
absence of the thing. The did-not-establish section is what stops a
narrow finding being received as a broad all-clear — and it is what let
the schema-provenance audit surface a third state (*no declared model
exists at all*) that was more consequential than the binary question it
was commissioned to answer.

### 7. Findings are anchored

A hazard or defect note names its anchor — a date, a chart version, a
commit, a gate, or a tracking ID — so its tense is recoverable by
construction rather than by luck. A comment can be an accurate historical
record and a false present-tense claim at the same time; anchoring is the
write-side rule that prevents the misread.

## Registered gaps

Where the position above is not yet the practice.

`Status: open`

**VE-1 — There is no index of evidence.** Findings live in
`decisions/`, procedures in the helm repo, test suites per service,
measured pairs inline in whatever document happened to record them, and
recordings with the operator who made them. Nothing enumerates what has
been verified, when, at what version, and where the artifact is. Answering
*"what do we actually have evidence for?"* today requires knowing where
to look — which is the same discovery problem `GENERALIZATION-DEBT.md`
was created to solve one layer over. *Fix shape: one index in
`decisions/`, one row per artifact, pointing outward — not a copy of the
evidence.*

`Status: open`

**VE-2 — The test suite produces no durable artifact.**
`tests/hero_scenario_v3/run_all.py` invokes each test as a subprocess,
prints a summary, and exits 0/1. There is no written report: no per-test
status, no timestamp, no version stamp, no record of which tests SKIPped
for want of a Playwright binary. A passing run is therefore evidence only
to the person who watched it, and *"the suite passed"* in a later
document cites nothing. *Fix shape: emit a structured run record —
per-test outcome, duration, skip reason, chart/image versions — as a file
the run's report can point at.*

`Status: open`

**VE-3 — Recordings have no declared home.** The pilot runbook makes the
rung (iii) recording a deliverable and §6 asks the operator to return it,
but nothing states where it lives afterwards, how it is named, or what it
is indexed against. The arc's central proof artifact currently has a
retention policy of "whoever has the file". *Fix shape: name the location
and the naming convention in the runbook itself, so the step that
produces the artifact also places it.*

`Status: open`

**VE-4 — Chart self-description is checked by hand.** The enforcement
`PRINCIPLES.md` names — diff **rendered object names** against the
template's stated inventory — is standing practice and is manual. It
caught two missing components once; nothing prevents the next omission
except someone remembering to run the diff. *Fix shape: the diff as a
check that fails loudly, which is also the cheapest instance of clause 3
(it can be seen red against the known-bad template).*

**RE-SCOPED 2026-08-19 — half built, half closed, and the closed half is a
decision rather than a deferral.** The row conflated two checks with very
different feasibility.

**Built** (`openddil-helm` `2ceee1b`): render integrity as a persisted
guard, in CI. Parsed-document count against `kind:` occurrences catches an
object swallowed by a missing loop-boundary separator; a second check
catches duplicate or unnamed object identities from a different
representation. Both red-checked against mutations modelling the original
defect. **The demonstration worth keeping: under a deleted separator,
`helm lint` reports "0 chart(s) failed" and `helm template` exits 0 while
an object has vanished from the release** — which is why this sits beside
lint rather than inside it.

**Closed as unbuildable in its stated form:** diffing rendered objects
against *the template header's stated inventory*. Template headers are
prose bullets — *"One redpanda-edge StatefulSet + Service per entry in
`.Values.edges`"* — so any check would match names out of English. That is
fuzzy matching, and its threshold would be tuned until it passed, which
makes its green meaningless (`PRINCIPLES.md` §*A check tuned until it
passes*). **A check that cannot fail for the right reason is worse than the
manual practice it replaces, because it also retires the human who was
doing it.**

**The one buildable form, recorded and not built:** make the claim
machine-readable — headers declare their inventory as a structured list the
guard compares exactly. That is a *form change across every template*, the
same shape as the register status tokens, and it converts the check from
fuzzy to exact by fixing the input rather than the matcher. Worth doing when
templates are next touched wholesale; not worth a dedicated pass.

*The distinction the original row missed:* "checked by hand" implied one
gap. There were two — one mechanisable, one requiring a convention change
first — and only the second was ever hard.

`Status: open`

**VE-5 — Single-site evidence, fleet-shaped claims.** The severance
ladder proves one site's behaviour on one chart version. Rollout claims
covering other sites will, until each has run the ladder, rest on
structural similarity — and *structural similarity is a code claim, not
a deployment claim*: two genuine twins can differ in mounts, env,
credentials, and sidecars, which is exactly how cm-service diverged from
its correctly-identified twin. *Fix shape: the ladder is per-site and its
per-site records are the evidence; the fleet claim is the conjunction of
them, not an inference from one.*

`Status: open`

**VE-6 — No stated retention or supersession rule.** Findings accumulate;
none has been superseded yet. When the first one is, there is no
convention for whether it is amended in place (as ADR-0032 and GD-09
were) or replaced. The amend-in-place precedent is good and is currently
a habit rather than a rule.

`Status: open`

**VE-7 — Evidence artifacts have no sanitization gate.** This is the row
the Consequences section below gestures at, and it is the one gap this
ADR *creates* rather than inherits.

Two of the four evidence forms are sensitive-bearing by construction.
Captured procedure outputs carry namespaces, release names, service
hostnames, site names, chart and image versions, and — wherever a query
returns rows — asset identifiers, positions, and ORBAT-derived
organisational structure. A screen recording carries all of that plus
whatever else was on the display for the duration. The measured-pair form
is smaller but not clean: a before/after reading is a broker name, a
consumer group, and a site name in one line. **Evidence is the
highest-volume class of sensitive-bearing artifact this project produces,
and this ADR increases the volume deliberately.**

There is no gate. Nothing stands between an artifact being produced and
it being pasted into a document, attached to a report, or handed to a
reader outside the workspace.

*Why this specific gap deserves a row rather than a mention:* the
recurring failure here is not that sensitive material leaks from the
places it obviously lives. It is that **the apparatus built to manage
sensitive material becomes the exposure**, because attention sits on the
artifact being protected rather than on the protecting. The instances
share one shape — *the control describes what it protects*:

- A commit message explaining why a cleanup happened disclosed that
  something proprietary had been displaced, and pointed a reader at
  exactly the thing the work existed to remove. The artifact was clean;
  the sentence about the artifact was the leak
  (`PRINCIPLES.md` §Narrate what you aligned to, never what you removed).
- A guard's encoded pattern list is a public enumeration of the strings
  it exists to catch.
- A pinned-values file naming an internal mirror publishes internal
  infrastructure in the course of making a deployment reproducible.

Evidence artifacts are the fourth candidate and the largest.

*Fix shape — a pre-share check at egress, not a post-hoc sweep.* The
distinction is load-bearing and is the reason this cannot be deferred to
review:

- **A recording cannot be redacted after delivery.** There is no
  equivalent of an amended commit.
- **Rewriting history does not undo a leak** — a force-push leaves
  unreachable commits retrievable for a period measured in weeks.
- **An external reader's copy is beyond recall entirely.** Once evidence
  has served its purpose, it is out of the project's control by
  definition, because being read by someone else *is* its purpose.

So the check binds at the moment an artifact **leaves the workspace**,
and it is a step in the procedure that produces the artifact rather than
a separate discipline someone remembers. This pairs with VE-3: the
runbook step that names where a recording goes is the same step that
states what must be true before it goes.

*Where the check lives.* With the existing hygiene tooling, outside the
public tree. **What is OSS-visible is the rule, not the pattern list** —
publishing an enumeration of what a sanitizer matches is the second
instance above, repeated knowingly. The public artifact is a statement
that evidence is sanitized before it is shared and at which step; the
patterns stay private, following the same declare-don't-compare shape as
the overlay manifest.

*What this row does not cover:* the sanitization discipline itself is
established and predates this ADR. The gap is the absence of a **gate** —
a named point where it is applied to this artifact class — not the
absence of the rule.

`Status: open`

**VE-8 — No CI job runs any Python test suite.** *(Logged 2026-08-15,
the condition behind the dead-suite named limit above. Not fixed — it
touches three repos' CI and sits outside C4's box.)*

The four dead files in cm-service were the **symptom**; the missing test
step is the **condition**. All three Python service repos —
`openddil-cm-service`, `openddil-logistics-fusion-service`,
`openddil-projector` — carry exactly one workflow, `docker-build.yml`
(56–58 lines: checkout, buildx, login, compute tags, build). No test
step, and no test stage in any of the three Dockerfiles. Their suites run
only when a human runs them.

**The sharp part is that the pattern already exists in this project.**
This is not a repo-wide absence of CI discipline that would need
inventing:

| Repo | Checks workflow | Runs |
|---|---|---|
| `openddil-demo` | `frontend-checks.yml` | `tsc --noEmit`, `npm test`, `npm run lint` in separate jobs |
| `openddil-demo` | `playwright-integration.yml` | integration suite |
| `openddil-contracts` | `contract-injection.yml`, `decision-indexes.yml` | contract + index checks |
| `openddil-stack` | `schema-checks.yml` | schema checks |

So the frontend cannot merge a type error or a failing unit test, and the
Python services — which hold the fusion evaluators, the CM analyzer, and
the projector handlers — can. **Three repos were never brought into a
discipline the project already practises**, which is a narrower and more
fixable statement than "the project lacks CI tests."

*Consequence, stated precisely:* today this produces **no false green** —
nothing claims those suites pass, because nothing runs them. The exposure
is that a collection error, a broken import, or a genuinely failing test
in any of the three is invisible until a human happens to run pytest, and
the cm-service instance shows that gap can stay open for **two months**.
Sibling suites collect cleanly today (projector 63 collected, fusion 76
passing), so this is a latent exposure rather than a live defect.

*Fix shape:* a `python-checks.yml` per service mirroring
`frontend-checks.yml` — `pytest` with the pass count visible in the log,
plus whatever lint the repo already declares. A test stage in the
Dockerfile is the alternative and is worse for this purpose: it couples
test results to image builds and hides the pass count inside build
output. Each repo needs its `PYTHONPATH` for the generated contracts
stubs, which is the only non-trivial part and is already solved in the
services' own docs.

*Related:* VE-2 (the suite emits no durable artifact) is the same
material one step further on — even once CI runs these, a passing run
still produces only console output. Fixing VE-8 without VE-2 gives a
signal that exists but cannot be cited.

## Consequences

**Pros**

- A later reader can check a claim rather than trusting it, which is the
  only mechanism that scales past the people who were present.
- The evidence-form table makes over-reach visible at the moment of
  writing: a claim about a fleet, supported by one site's ladder, is
  legible as over-reach without needing a reviewer to catch it.
- The gaps above are individually small and individually schedulable.
  VE-2 and VE-4 in particular are hours, not arcs, and both convert an
  existing manual practice into a durable one.

**Cons**

- Evidence production has real cost, and clause 3 doubles it for guards
  (run red, then run green). The cost is justified for load-bearing
  claims and is overhead for everything else; this ADR does not draw
  that line and cannot draw it generically. Judgement stays with the
  author, informed by whether a later claim will cite the result.
- An index (VE-1) is a document that drifts. Mitigated by keeping it a
  pointer list — the same reason ADR-0017 rejected a central mock
  registry in favour of a grep-able marker. If the index can be
  generated, it should be.
- Written evidence is discoverable by people the author did not
  anticipate. Everything produced under this ADR is subject to the
  sovereignty and sanitization disciplines without exception: captured
  console output, recordings, and run records carry live deployment
  detail and are sanitized before they enter any public artifact.
  **Evidence-as-deliverable increases the surface that discipline has to
  cover** — and the increase is not yet gated anywhere, which is **VE-7**
  above. This is the cost of the ADR, stated as a row rather than as a
  caution, because a caution is what the third instance in that row
  already was.

**Rejected alternatives**

- *CI as the single source of verification truth.* Rejected: the claims
  that matter most here are about **deployed behaviour under severance
  at a real site**, which CI cannot produce. CI is one evidence
  producer among four, and treating it as the standard would quietly
  demote the only form competent to prove the arc's central claim.
- *A formal test-plan / traceability-matrix document.* Rejected as the
  primary mechanism for the reason ADR-0017 rejected a mock registry: a
  document parallel to the work drifts from it. Evidence lives next to
  what produced it and is pointed at; the index is a pointer list, not a
  second copy.
- *Retrofitting artifacts for past verifications.* Rejected. Claims
  already made without durable evidence are marked unverified where they
  matter (UD-2 in ADR-0036 is exactly this) rather than back-filled with
  reconstructed evidence, which would be indistinguishable from evidence
  and is not.

## Related

- **ADR-0025** — build-pass deployment verification discipline; clause 2
  is its restatement, and this ADR is the general form it was one
  instance of.
- **ADR-0036** — failure detectability; clause 3 is where its "seen to
  fail" requirement becomes a recorded artifact rather than a memory.
- **ADR-0035** — information honesty; the same claims-vs-support rule
  applied to a screen instead of a report.
- **`PILOT-RUNBOOK.md`** (openddil-helm) — the reference form for clauses
  1 (executed procedure), 5 (declared substitutions), and 7 (anchored
  findings: every fix in its version table names the rung that breaks
  without it).
- **`AUDIT-2026-08-07` / `AUDIT-2026-08-08` / `AUDIT-2026-08-09`** — the
  finding-document form, including scope limits and did-not-establish
  sections.
- **`GENERALIZATION-DEBT.md`** — rows closed rather than deleted;
  GD-09's in-row correction is the supersession precedent VE-6 has not
  yet made a rule.
- **`PRINCIPLES.md`** §A deliverable's self-description is a claim ·
  §Match structure, not prose · §"Not found" is not "cleared" ·
  §Similarity is a code claim, not a deployment claim · §The prose was
  accurate; the tense was inferred · §Verification.
- **`PRINCIPLES.md` §Narrate what you aligned to, never what you
  removed** — VE-7's governing rule, and the first instance of a control
  becoming the exposure. Its corollary applies directly to evidence:
  **the moment of cleaning is the highest-risk moment, not the safest**,
  because attention is on the artifact and not on the narrative about it.
- **`PRINCIPLES.md` §Public twin, declared by manifest** /
  `openddil-customer-bundle-example/overlay-manifest.yaml` — the
  declare-don't-compare shape VE-7's public statement follows: the rule
  is expressible without reference to the private material it governs,
  which is precisely why the pattern list stays private and the rule does
  not.
