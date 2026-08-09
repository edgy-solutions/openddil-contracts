# Principles — the portable one-liners

Not architecture. Not decisions. These are the short, reusable rules
extracted from moments where the *wrong default almost shipped* — each
one earned by a specific near-miss, each one cheap to recall under
schedule pressure.

They live here because the alternative is that they live only in
conversation history, and conversation history is exactly where the
recursive-tier intent (ADR-0033) nearly died: an intent nobody wrote
down is an intent that has to be re-derived, or re-corrected, by the one
person who still holds it.

An ADR records *what we decided and why*. A principle records *the
shape of the mistake we keep almost making*. The second is shorter,
travels further, and applies to decisions that haven't been made yet.

---

## Ordering

**Label first, enforce second — never the reverse.**

Turning on enforcement against partially-labelled data silently blanks
legitimate results, and the failure is indistinguishable from correct
enforcement: an operator sees an empty screen either way. Completeness
is a hard gate before enforcement, not a parallel workstream.

*Earned:* ADR-0029 §7 — deny-unlabeled releasability. Generalizes to any
"validate/filter/gate on a new attribute" rollout.

---

## Provenance of authority

**Sync tooling transports asserted, PR-reviewed content into the
runtime; it never derives entitlements from a directory or any other
source.**

"No directory sync" is a statement about **derivation**, not about
**transport**. A directory may seed a *draft* for a human to review; the
PR approval is what makes it an entitlement. Confusing the two either
blocks normal deployment automation or quietly launders inference as
assertion.

*Earned:* ADR-0029 §5 / ADR-0031 §(b), reconciling OpenDDIL's
asserted-entitlements stance with the agent-side `policy/sync/` tooling.

---

## Schema change scheduling

**Schema changes board early trains when they carry a correctness gate;
they take later trains when they don't.**

The releasability labels boarded Arc 1's step-zero migration because
they carry a gate — deny-unlabeled requires zero NULLs, so incomplete
labelling is a correctness failure. Hierarchy-path addressing did *not*
board, because it carries no gate: a nullable, no-backfill column is a
cheap additive migration whenever it lands, and designing an addressing
scheme under train pressure locks a regretted shape into the most
permanent layer.

The counter-cost (a later migration runs at N+1 sites instead of 1) is
real and is usually small for a nullable column with no backfill.

*Earned:* ADR-0033 §Generalization backlog, assessed against Arc 1
Phase 1.

---

## Claims vs. sources

**A component must claim only what its data source supports.**

A CM-records-derived status must not render in functional-capability
language. A browser-session accumulator must not present as a durable
record. A mock must self-identify. Same rule, three layers: mocks,
labels, derived metrics.

*Earned:* ADR-0017 (mocks self-identify), extended by ADR-0029's CM
label rename, extended again by the session-scoped munitions
`expended` qualifier.

---

## Locality

**A tier that presents, decides, or detects must be able to do so from
what it locally holds. Reachback is the same bug wearing different
planes.**

ADR-0022 stated severance tolerance for the **data** plane and it was
implemented there. Every other plane inherited the *claim* without the
*property*, and each violation was discovered separately, by accident,
from an unrelated investigation:

- **Presentation** — the maintainer UI served from and reading the root
  tier; the persona closest to the equipment had the stalest view
  (ADR-0032, found via the mini-agent read-seam work).
- **Detection** — logistics-fusion deployed once at the root, reaching
  *down* into child brokers; a severed tier gets no severity computed at
  all (ADR-0034, found via the analytics-configurability work).
- **Authorization** — pre-empted rather than discovered: ADR-0029's
  per-tier local authorizers with policy as bundles exist precisely so a
  severed tier still decides.

*Corollary:* when adding any capability, ask which tier it must work at
when the link above is cut, and whether its inputs are there. "It reads
from the parent" is the failure, whatever the plane is called.

*Earned three times before it was written down, which is two more than
it should have taken.*

---

## Provenance pays twice

**Record what produced a value, not just the value. Provenance fields
keep turning out to be load-bearing for purposes nobody designed them
for.**

They are written for honesty — *where did this come from, how many
samples back it, what decided it* — and then something structural turns
out to need exactly that field.

*Earned, twice:*

- `ComponentWearTrend.asset_count` was recorded as honesty about sample
  size. It turns out to be precisely the sufficient statistic that makes
  a mean compose across tiers — so that aggregation's **wire format was
  already composition-ready** with no change required
  ([AUDIT-2026-08-07](AUDIT-2026-08-07-aggregation-composability.md) §3).
- `Provenance.classification` was carried as a free-text descriptive
  field, and became the hook that lets classification ride the same ABAC
  mechanism as nation releasability without a second design
  (ADR-0029 §Classification).

- **Third instance — process-as-provenance.** Workflow step executions
  stamp `{workflow_def_hash, step, actor, access_decision}`, so *"which
  version of whose procedure, executed by whom, under what
  authorisation"* is answerable after the fact (ADR-0034 §The two
  planes; the version-hash-in-decision-record pattern inherited from
  `invincible-agent`). It completes a family: **decision**-as-provenance
  (ADR-0031), **detection**-as-provenance (ADR-0034),
  **process**-as-provenance.

*Corollary:* the reverse also holds — a value with no provenance is a
value that cannot later be composed, filtered, or explained. Hence the
mandatory stamps on analytics outputs (ADR-0034), including
`model_artifact_hash`, because *"which weights produced this alert"* is
unanswerable retroactively.

---

## Framework vs. instantiation

**State the rule and the instantiation separately. A decision about
which tiers/nodes/deployments get a component is configuration; the
rule that governs it is framework.**

Reasoning from the current deployment and generalizing to framework law
is this project's most repeated failure. The tell is a categorical
sentence about a *kind* ("regions get no store") where the evidence only
supports a sentence about a *configuration* ("this deployment's
intermediate tier has no broker, and the rule requires one").

*Earned:* ADR-0032 §(a), corrected by ADR-0033. Also: a deployment
overlay long assumed to be "single-edge by intent" — it was demo
legacy.

---

## Narrate what you aligned to, never what you removed

**Public artifacts state the standard adopted, not the thing displaced.
A removal narrative is a pointer at the removed thing.**

Renames, generalizations and cleanups are described by their
destination — *"aligned to DIS / AFSim / Link 16 conventions"*,
*"generalized to a canonical Silver shape"* — never by their origin.
This applies to code, comments, commit messages, ADRs, and PR
descriptions equally, because all of them are public and permanent.

*Earned the hard way:* a commit message describing a cleanup **became
the leak**. The artifact was clean; the sentence explaining why it had
been cleaned disclosed that something proprietary had been displaced —
which invites the question "displaced from what?" and points a reader
at exactly the thing the work existed to remove. It required a history
rewrite (amending both file content and commit message) and a
force-push to remove.

*Corollary — the expensive one:* **the cleanup is the highest-risk
moment, not the safest.** Attention is on the artifact being cleaned,
so the narrative describing the cleaning goes unexamined. Sweep the
commit message with the same discipline as the diff.

*Second corollary:* a "before → after" framing is a removal narrative
wearing a table. State the after.

---

## Similarity is a code claim, not a deployment claim

**Structural similarity verifies at the code layer. Deployment surfaces
verify one at a time.**

Two services can be genuine twins — same shape, same mechanism, zero code
difference between how they run — and still diverge in what they need to
*start*: mounts, env, config files, credentials, sidecars.

*Earned:* `cm-service` was classified as `logistics-fusion`'s structural
twin by a reading-level sweep, and that classification was **correct**.
Both ran unmodified against tier-scoped infrastructure. But cm-service
additionally required a proto mount plus `PYTHONPATH`, and a baselines
mount without which its output is meaningless — neither of which the
twin claim predicted, because the twin claim was never about deployment.

*Corollary:* "structurally identical, therefore fine" is a valid
inference about behaviour and an invalid one about packaging. Run the
second one anyway; it is usually twenty minutes.

---

## Public twin, declared by manifest

**Any artifact class a deployment overlay carries must have a sanitized
twin in the public sample overlay. Structure mirrors; content is
fictional.**

The seam that lets closed-world material meet an open core is only
credible if the *mechanism* is publicly exercisable. Without a public
twin: CI cannot test the overlay seam, worked-example pedagogy points at
things its audience cannot open, and test harnesses invent throwaway
fixtures per run.

Make the rule checkable **without reference to any private material**:
declare the artifact classes in a **public manifest**, and let the check
be `sample overlay ⊇ manifest`. That runs anywhere, including CI, where
private overlays do not exist and must not be named.

Two properties follow, and both are the point:

- The manifest becomes the citable public contract for *what a
  deployment overlay consists of* — documentation deployers need
  regardless.
- Parity is verified structurally. **Content parity is neither possible
  nor desired**; the twin's content is invented by design.

*Earned:* the requirement to state the rule without reference to private
material produced a manifest formulation better than the diff it
replaced. Third instance of that pattern: standardizing capability
naming on DoD sim/C2 conventions produced a cleaner generic Silver
model; a deployment-overlay seam produced the public twin; a
declare-don't-compare rule produced the manifest. **Designing for
generality keeps producing the better architecture.**

---

## A deliverable's self-description is a claim

**Verify the rendered artifact against its own header. Exit-zero proves
the render ran, not that it rendered what the header promises.**

The narrowest possible gap between claim and reality — an artifact's own
documentation of itself, written by the same author, minutes apart — and
it still opens.

*Earned:* a chart template's header block listed
`postgres + schema-init + projector + restate + fusion + cm-service +
electric + frontend + topaz`. It rendered cleanly, `helm lint` passed,
and **fusion and cm-service were absent** — described and never built.
Every automated signal was green because every automated signal was
answering a different question: *did this render?*, not *did it render
what it says it contains?*

*Enforcement:* diff **rendered object names** against the template's
stated inventory. Standing practice for chart changes.

*What made the catch possible:* the work checklist had *named*
fusion+cm as a box, so there was something concrete to audit against.
**Unnamed intentions cannot be caught missing** — which is the checklist
discipline and the verification discipline reinforcing each other rather
than duplicating.

---

## Match structure, not prose

**Assert against parsed structure or exact equality. When a sentinel is
needed, choose one no substring of which can match its own negation.**

*Earned twice in one day* — which is why it stands on its own rather than
sitting as a footnote to the principle above.

**Instance 1 — the enforcement had the weakness inside it.** The acceptance
suite for the tier-node template *is* the mechanism enforcing "a
deliverable's self-description is a claim". It asserted
`f"{component}-{tier}" in rendered`. A missing `---` at a loop boundary
merged each tier's topaz Deployment into the next tier's first object, where
last-wins silently discarded it — and **the discarded object's text remained
fully present in the render**. Every substring assertion passed while three
tiers received a Service with no endpoints, i.e. no local authorizer. The
seventeen checks caught their own inadequacy only when a genuinely missing
Deployment walked through the gap.

**Instance 2 — a sentinel containing its own negation.** A provisioning task
reporting whether it had rewritten a config used
`changed_when: "'CHANGED' in stdout"`. `'CHANGED' in 'UNCHANGED'` is true, so
a converged, correct task reported `changed` forever — training the reader to
ignore the one run that would have mattered.

*Why they are one disease:* both **matched prose where structure was meant**.
A substring test answers *do these bytes appear somewhere?* when the question
was *does this exist as a unit the consumer will act on?* For YAML the
consuming unit is the document, not the byte range; for a status sentinel it
is the whole token, not a fragment. In both cases the artifact was wrong and
the bytes were right.

*Enforcement:*

- Assertions about what a system will **receive** are made against parsed
  objects, never against rendered text.
- Status sentinels are compared by **equality**, and chosen so no value is a
  substring of another: `CHANGED` / `NOCHANGE`, never `CHANGED` /
  `UNCHANGED`. Pick the pair so a careless rewrite cannot resurrect the bug.
- **A guard is not evidence until it has been seen to fail.** Both
  replacement checks were run against the unfixed artifact and confirmed to
  fail before being trusted. A green test that has never been red proves
  nothing about what it would catch.

*Corollary:* when a check and the thing it checks share an author and a
vocabulary, the check inherits the author's blind spot. Prefer a second check
written against a **different representation** — parse vs. text, count vs.
presence — over a more careful version of the same one. The 19-objects /
18-separators arithmetic found the defect that the name-matching could not.

---

## A probe must fail distinguishably from its own zero

**An instrument whose failure mode is indistinguishable from its healthy
reading is not an instrument.** Absence, misconfiguration and "nothing to
report" must produce different outputs.

*Earned:* the edge→HQ buffer counter read **0 on every cluster, for months**.
`edge_buffer_monitor.py` queried consumer group `bridge-group`; the bridges
commit under `bridge-group-<edge_id>`. The probe was looking up a group that
had never existed — and its own contract was *"returns 0 if the group has not
committed any offsets yet."* A broken lookup and a healthy, caught-up link
produced the identical number. Nothing errored, nothing warned (probe
failures logged at DEBUG, invisible at the default level), and 0 was always
plausible.

The DDIL buffering worked the entire time. Only the instrument was blind, and
**the buffering claim was therefore unverifiable rather than wrong** — which
is worse, because it cannot be argued with.

*This is the family's third instance:*

| | looks like | actually is |
|---|---|---|
| DDS QoS mismatch | a quiet topic | no subscription match |
| a site with no feed | a broken deployment | a site with no feed |
| the buffer probe | a caught-up link | a group that never existed |

Each pair is byte-identical from the observer's position. The shape recurs
because "nothing arrived" is the natural rendering of both success and
failure, and the innocent reading is always the comfortable one.

*Enforcement:* a probe distinguishes **absent** from **zero**. In practice —
raise on absence rather than returning a value; write a sentinel the UI
cannot mistake for data (a negative lag prompts a question, a `0` ends one);
warn at WARNING, not DEBUG, because a signal suppressed by default is not a
signal; and deduplicate the warning, since a permanent error emitted 30×/min
trains readers to filter it exactly as a permanent 0 trained them to trust it.

*Corollary — a copied default inherits the bug and adds the copier's
endorsement.* Three call sites carried this wrong group name in two different
ways: two never passed the variable at all (silently taking the broken
default), and one passed the broken default **explicitly**, written this week
by copying the existing value. Precedent reads as verification. The newest
code in the stack acquired the oldest bug because it was copied from
something that appeared to work — the deployment-surface lesson wearing a
different hat: **structural similarity carries defects with the authority of
having shipped.**

*What made the catch possible:* it could not be seen without a data source.
No traffic → no buffer → 0 is genuinely correct → the bug is invisible. It
took a real cluster, real DIS traffic and a deliberate severance to expose
one wrong string.

---

## A documented hazard is not a mitigated one

**A hazard note ships with a mitigation or a tracked vehicle. A bare comment
on a broken default is a confession, not a control.**

*Earned:* the chart's restate-wipe hook pointed at
`docker.io/bitnami/kubectl:1.30`, above a comment stating that Bitnami's
catalog restructure had made those tags "hard to obtain reliably" and listing
alternatives an operator might prefer. The hazard was correctly identified,
written down — **and shipped as the default anyway**. The tag was later
withdrawn entirely (`:1.30` and `:1.31` both 404). Nothing in the chart
changed; the registry did.

*Why it cost more than it should have:* the failure surfaced as
`Error: failed pre-install: 1 error occurred: timed out waiting for the
condition`, which names no image, no pull, and no registry. The comment that
predicted the problem sat three files away from the error that expressed it.
Someone had already done the hard part — noticing — and the noticing was
stored where it could not act.

*Enforcement:* when a comment says a dependency is unreliable, one of these
must accompany it before the change lands —
- **change the default** to the reliable thing, or
- **open a tracked row** (debt registry / follow-up) naming the replacement
  and the trigger, or
- **add a pre-flight check** that fails with the real reason.

If none of the three is affordable right now, that is worth saying out loud,
because it is a decision rather than an oversight.

*Corollary — verify the replacement, don't infer it.* Choosing the successor
image looked obvious and was not: `registry.k8s.io/kubectl` and
`rancher/kubectl` both exist, are both the "modern correct" answer, and both
fail here because they are distroless and the hook runs a POSIX shell
(`exec: "sh": executable file not found in $PATH`). Running all three
candidates on a real cluster took minutes and made the fix right the first
time. Reasoning about base images would have swapped one broken default for
another.

---

## Verification

**Verify before multiplying.** A cheap pre-question before an expensive
multiplication — a blast-radius check before a one-line change, a
compose run before helm templating, a schema question before a rollout —
has repeatedly cost minutes and saved days.

**Automated tests prove the code path, not the deployment.** Confirm the
running artifact is the new one before concluding a fix didn't work.

*Earned:* ADR-0025 (build-pass discipline). The multiply-guard was
earned three separate times in one session: a blast-radius check that
found a second ADR-0026 violation at the regional tier; a seam
investigation that found the reachback finding; a thirty-second schema
question that found the stockpile accumulator.

---

## How to use this file

- Add a principle when a *specific near-miss* produces a rule that would
  have prevented it, and the rule is portable beyond the decision that
  earned it.
- Keep each to a sentence plus its earning context. If it needs
  paragraphs of qualification, it is an ADR, not a principle.
- Principles do not override ADRs; they are the heuristics that make
  ADRs less necessary.
