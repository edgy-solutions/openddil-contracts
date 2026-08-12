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

**VE-2 — The test suite produces no durable artifact.**
`tests/hero_scenario_v3/run_all.py` invokes each test as a subprocess,
prints a summary, and exits 0/1. There is no written report: no per-test
status, no timestamp, no version stamp, no record of which tests SKIPped
for want of a Playwright binary. A passing run is therefore evidence only
to the person who watched it, and *"the suite passed"* in a later
document cites nothing. *Fix shape: emit a structured run record —
per-test outcome, duration, skip reason, chart/image versions — as a file
the run's report can point at.*

**VE-3 — Recordings have no declared home.** The pilot runbook makes the
rung (iii) recording a deliverable and §6 asks the operator to return it,
but nothing states where it lives afterwards, how it is named, or what it
is indexed against. The arc's central proof artifact currently has a
retention policy of "whoever has the file". *Fix shape: name the location
and the naming convention in the runbook itself, so the step that
produces the artifact also places it.*

**VE-4 — Chart self-description is checked by hand.** The enforcement
`PRINCIPLES.md` names — diff **rendered object names** against the
template's stated inventory — is standing practice and is manual. It
caught two missing components once; nothing prevents the next omission
except someone remembering to run the diff. *Fix shape: the diff as a
check that fails loudly, which is also the cheapest instance of clause 3
(it can be seen red against the known-bad template).*

**VE-5 — Single-site evidence, fleet-shaped claims.** The severance
ladder proves one site's behaviour on one chart version. Rollout claims
covering other sites will, until each has run the ladder, rest on
structural similarity — and *structural similarity is a code claim, not
a deployment claim*: two genuine twins can differ in mounts, env,
credentials, and sidecars, which is exactly how cm-service diverged from
its correctly-identified twin. *Fix shape: the ladder is per-site and its
per-site records are the evidence; the fleet claim is the conjunction of
them, not an inference from one.*

**VE-6 — No stated retention or supersession rule.** Findings accumulate;
none has been superseded yet. When the first one is, there is no
convention for whether it is amended in place (as ADR-0032 and GD-09
were) or replaced. The amend-in-place precedent is good and is currently
a habit rather than a rule.

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
