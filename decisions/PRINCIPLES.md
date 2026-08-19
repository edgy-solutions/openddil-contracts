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

## The sentence that reads most virtuous gets read least critically

**A change that cites the rule it is violating is safer from review than one
that cites nothing.** A reviewer who sees the citation checks the
*reasoning* — and the reasoning is usually fine. What goes unchecked is
whether the **data** the reasoning assumes is actually there.

*Earned 2026-08-19, and only by a measurement that could have been skipped.*
A DIS appearance-bits mapping was designed against ADR-0026's absence
convention, correctly, and would have been committed quoting that
amendment as its authority. The generator hardcodes the appearance field to
zero, and bits 3–4 of zero decode as *damage: none* → `NOMINAL`. So the
change would have **manufactured a positive health claim out of a field
nobody populates — the exact defect the quoted amendment forbids** — and it
would have arrived wearing the amendment's own words.

**Design correctness and data readiness are independent**, and a citation
speaks only to the first. The commit message would have been true in every
sentence and the change still wrong.

*This is the proximity rule inverted.* There, nearness to a claim dulls
scrutiny of it; here **righteousness** does. Both work by making a reader
feel the checking has already happened.

*Enforcement:* when a change cites a principle, audit the **inputs** the
principle assumes, not the argument connecting them. The argument is the
part the author already checked — it is why they wrote the citation.
*Related:* §*Narrate what you aligned to, never what you removed* — the kin
rule, and the reason this one is easy to miss: we already train ourselves to
write the virtuous-sounding sentence, so we have made the camouflage
standard practice.

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
- **A verification that includes its own subject in its evidence is not a
  verification.** The limiting case of the rule above: where a check cannot
  be seen red *by construction*, "see it red first" is not unsatisfied, it
  is unsatisfiable. *Earned inside the anti-drift tooling itself* — the
  follow-up index's checker scanned `*.md`, which includes the index, so
  every ID written there appeared in its own "corpus" and the phantom-row
  direction could never report anything. Half the check was decorative and
  looked identical to the half that worked. Not *"the instrument reads zero
  when broken"* but *"the instrument is inside what it measures"*, and no
  amount of running it would have shown this, because running it is what it
  does successfully. **When a check's scope is a pattern — a glob, a
  directory, a selector — ask whether the checker is inside the set the
  pattern selects**, and if so exclude it explicitly and say why at the
  exclusion, since that line looks like noise and is the only thing making
  the check real.

*Corollary:* when a check and the thing it checks share an author and a
vocabulary, the check inherits the author's blind spot. Prefer a second check
written against a **different representation** — parse vs. text, count vs.
presence — over a more careful version of the same one. The 19-objects /
18-separators arithmetic found the defect that the name-matching could not.

### Generalized 2026-08-12 — the shared signature is *the assertion is weaker than it reads*

The two instances above are both string-shaped, and the family is not. A
third arrived in a different type system entirely, which is what earns the
wider statement:

**Instance 3 — enum truthiness.** The IH-5 guard asserts that the mtbf
projection stamps its provenance. Written as `assert factor.origin`, it
reads as *"origin is set"* and means *"origin is not zero"* — and
`ORIGIN_UNSPECIFIED` **is** zero while every other value is truthy. So the
check passes for `ORIGIN_MEASURED`, which is the wrong answer, and fails only
for the unstamped case it happens to catch by coincidence of encoding. Had
the bug been *"stamped, but stamped MEASURED"* — a claim that the projection
was observed rather than computed — the assertion would have been green. It
is written `== tel.ORIGIN_DERIVED`.

*The signature all three share:* **an assertion that appears to test the
right property while being satisfiable by the wrong one.** It is not
specifically about strings; strings were just where we met it first.

| layer | the check | what it actually asked |
|---|---|---|
| string containment | `'CHANGED' in stdout` | do these bytes appear anywhere |
| document structure | `f"{c}-{tier}" in rendered` | do these bytes appear anywhere |
| test medium | a JSON→JSON golden suite | does the mapping round-trip *in JSON* |
| enum encoding | `assert factor.origin` | is the value non-zero |

*The portable question, asked of any assertion before trusting it:* **what
else would satisfy this?** If the answer includes a state you would consider
a defect, the assertion is weaker than it reads. Sentinel-vs-substring,
document-vs-bytes, medium-vs-production, identity-vs-truthiness are four
instances of one habit — and the habit is cheap, because the question takes
one sentence to ask and does not require knowing the bug in advance.

*Related, and not the same thing:* ADR-0037 §1's *named limits* covers checks
that ran, passed, and proved **less than the reader assumes** — schema
inspection proving a schema and not a producer, a suite proving its own
medium. That family is about **scope**; this one is about **satisfiability**.
They meet in the golden-suite case, which is both.

---

## The prose was accurate; the tense was inferred

**A comment can be a true historical record and a false present-tense claim
at the same time. Read the tense, then verify the state.**

*Earned:* a cross-project read quoted a config comment describing an
authorization fail-open — `ALLOW_MOCK_AUTH` converting every authorizer
exception into allow-by-default — and reported it as the neighbouring
system's **current** posture. The comment was entirely accurate. It was
recording a defect that had been **found and removed in the same arc**, and
said so three lines further down. The finding was filed as a live security
hazard, escalated into a punchlist action, and was neither.

*Why it is the sharpest member of the comment-as-claim family:* the other
instances fail because the comment is wrong (a template header listing
components it does not render; a hazard note on a default nobody changed).
This one fails while the comment is **right**. Nothing in the text is false;
the reader supplied a tense the text never claimed. There is no wrong
statement to catch — only an unstated one.

*Enforcement:* a comment describing system behaviour dates the behaviour or
it describes nothing checkable. When reading someone else's comment as
evidence: **grep for the thing it describes before believing it is still
there.** In this case `ALLOW_MOCK_AUTH` appeared only inside comments —
thirty seconds of checking against hours of consequence.

*Corollary:* the same applies to our own comments. Every "X is broken" or
"X does not work" note in this repo is a claim with an implicit `as of`, and
the reader who finds it later has no way to recover the date from the prose.

*The write-side rule that prevents it:* **a hazard or defect note names its
anchor** — a date, a commit, a gate, or a tracking ID. This project already
half-practices it (gate findings cite their gates, the re-baseline notice
cites its commit, debt rows carry their owning ADR); stating it makes the
tense recoverable **by construction** rather than by luck.

The grep rule governs *reading* someone else's old comment. The anchor rule
governs *writing* one that will be read later. Together they close the loop
at both ends: an anchored note cannot be misread as present-tense, because
the reader can see exactly when it was true.

---

## Two claims that cannot both be true are a stop signal

**Mutually exclusive statements inside one report are a re-read gate before
publication, not a curiosity to resolve later.**

*Earned:* the same report asserted, in one message, that a neighbouring
gateway had been fail-open *"the whole time"* and that its implementation
was fail-closed *"verbatim — every non-200 and every exception is a hard
deny"*. Both quoted the same file. They cannot describe one system at one
time, and the contradiction was the fastest available route to the error.

*What makes it worth a rule:* it is **mechanical**. It requires no domain
knowledge, no repository access and no judgement — only reading two claims
next to each other and asking whether both can hold. Every other check in
this file needs context; this one needs attention.

*Who caught it, and why that matters:* not the author, and not the reviewer
who had already endorsed the report. A third reader, cold, with no stake in
the report being right. **Proximity to a claim degrades scrutiny of it** —
the same mechanism that makes a repo read outrank a confident recollection,
one level up. Cold reads by someone who did not produce or bless the work
are cheap and occasionally decisive.

*Enforcement:* before publishing a report that makes several claims about
one system, read the claims as a set and check for pairs that cannot
co-exist. If one is found, neither is trustworthy until the source is
re-read.

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

*The inverse instance, same week — unverified observability masking a
SUCCESS.* Testing the Topaz seat, extra "what did the policy actually see?"
rules were added to a Rego policy precisely to avoid a silent-absence trap:
so that a `false` decision could be told apart from a policy that never
received its input. Those rules returned strings and arrays. Topaz's `Is`
API returns **boolean** decisions and errors the **entire query** if any
requested decision is undefined or non-boolean — so every query failed with
`undefined results`, for six iterations, while the bundle had in fact loaded
and the policy was working correctly the whole time.

The anti-silent-absence machinery produced a **loud failure that masked a
success**, which is the mirror image of a silent failure masking a fault.
The rule that covers it already exists — *hardening never run is new code* —
and this is its second instance in one week, arriving from the opposite
direction. **Observability added to a system is part of that system and
inherits its verification burden.** A diagnostic you have not seen produce a
correct reading is not yet a diagnostic.

---

## A fallback answers only where it can name the class it answers for

**A fallback that manufactures a value is indistinguishable from a successful
lookup.** Nothing downstream can separate *"we recognised this"* from *"we
made something up"*, because both arrive as data of the same shape. The
mapping-layer twin of the probe rule above.

Two constructions share one syntax — `_ =>`, `.or(…)` — and only one is
legitimate:

- a **residual class** says *"everything else is X"*, where X is a real
  category chosen deliberately. Fine.
- an **unrecognised input** must refuse: `UNSPECIFIED`, `null`, absent, or
  pass the source value through for a drift check to flag.

*The distinguishing question:* can you **name what falls into the branch**?
If the answer is "anything, including values that do not exist yet", it is
not a residual class.

*Earned:* `AUDIT-2026-08-11-fallback-honesty` — four confabulating fallbacks
across nine surfaces. The reference specimen ADR-0030 points adapter authors
at resolved an unrecognised sensor mode to `POWER_ON / ACTIVE / NOMINAL`: the
system asserting an asset is **healthy on the basis of not understanding
it**, a safety-relevant false negative, reproducing into every mapping
written from the specimen.

*The fix shape, and why it is cheap:* the catch-alls were not removed, they
were **emptied**. Every value the source schema declares is enumerated
explicitly and resolves exactly as before; only genuinely unrecognised input
reaches the final branch. Behaviour for known input is provably unchanged —
the six existing goldens were re-blessed and came back byte-identical — so
the objection "this will change what we see" is answerable with evidence
rather than argument.

*Where the type offers no refusal, omit rather than choose.* A bool has no
`UNSPECIFIED`, and `false` is not a refusal — it asserts *"not receiving"*,
as unfounded as `true` for an input never seen. Delete the field. Where
proto3 gives a scalar no optionality (absent decodes as `0`, the very value
at issue), find the level that **can** express absence: a map key can be
dropped even when its uint32 fields cannot.

**Corollary — filling an absence upstream destroys a downstream's ability to
detect it.** A mapping that defaults is making a judgement on behalf of every
consumer that will ever read the field, *including consumers that had
explicitly handled the absent case*. In the earned instance, fusion declines
to judge fuel it considers unset and detects unset as `not unit and value ==
0.0` — **both**, since the empty unit is proto3's only available
discriminator. The mapping set the unit unconditionally, making that check
unreachable. An asset whose feed omitted fuel was presented as an asset with
an **empty tank**.

That is worse than neither side handling absence, because the code reads as
though absence is handled: the correct check sits right there, and is dead.

**Corollary — a mostly-honest structure is the better hiding place.** The DIS
`_default` declared ignorance correctly in six of seven fields — two
`UNKNOWN`, three `null`, a nomenclature saying *"Unrecognized … requires
ontology curation"* — and carried one invented schema name. The honesty of
the siblings is exactly what made the outlier read as deliberate. Two
`.or(0)` calls one line apart looked identical and were not: one was the
downstream's declared "not evaluable" sentinel, the other a confabulation.
**Audit the surrounding population, never the flagged item alone** — and
expect the worst instance to sit among correct ones rather than among other
defects, since a field surrounded by obvious sloppiness gets re-read, and one
surrounded by care does not.

**Corollary — a sweep names surfaces; only reading each one names findings.**
The audit that produced this principle got its own results wrong in both
directions, and the error had one cause: surfaces were classified from their
*shape* rather than from their *effect*.

- It **missed** a surface — two activity booleans with the same construction,
  found later only because fixing the block forced every branch to be read.
- It **over-called** one. Two `.or(0)` calls **one line apart**, in the same
  fold, on adjacent fields of the same message, carried **opposite**
  semantics: `quantity_remaining`'s default was the confabulation;
  `quantity_capacity`'s zero *is* the consumer's declared not-evaluable
  sentinel and is load-bearing. A mechanical fix for "defaults" would have
  removed the one that made absence work.

So the residual-vs-unrecognised distinction recurs **inside the audit's own
results**, one layer down. *Adjacent identical syntax can carry opposite
semantics*, and no amount of pattern-matching separates them — only reading
what each one does to its consumer does.

*Enforcement:* a base rate produced by sweeping is quoted as a **floor**, not
a count. And a finding is not actionable until the consumer's use of the
field has been read; the audit that names a surface has done the cheap half.

*Direction note, for the count that moves:* fixing these **lowers** the
constraining-factor count, where the three earlier instrument fixes raised
theirs. The reading is identical in both directions — the factors that
disappear were never observations, they were **the absence of observations
wearing the shape of one**. Say so before anyone sees the number move; a
count that drops after a correctness fix reads as a regression, and the
reasonable response to an apparent regression is to revert the fix.

*Related:* *A probe must fail distinguishably from its own zero* — same rule
at the instrument layer. `DESIGN-2026-08-11-declared-asset-class` — the same
disease in the ontology layer, where absence of a declared property let one
feed's behaviour become the model.

---

## A check tuned until it passes is a check whose green means nothing

**When a check's accuracy depends on a parameter you are free to adjust,
adjusting it until the output looks right is not calibration — it is
choosing the answer.** The check still runs, still prints green, and now
certifies whatever the parameter was set to.

*Earned 2026-08-12, and the reason to trust it is that the failure is
structural rather than a tuning miss.* An attempt to detect **status** drift
— rows marked `open` in the index whose home document says `FIXED` — was
built, tested, and **deliberately not shipped**:

- windowing from any *mention* of an ID → **false positives**. A summary
  file mentions `AE-2` and `VE-7` a few lines from a `RESOLVED 2026-08-12`
  belonging to `AE-1`.
- tightening to definition sites with a 16-line window → **false
  negatives**. It caught `IH-6` and missed `IH-5`, whose `FIXED` marker sits
  25 lines under its heading.

**There is no correct window, because register blocks vary in length.** No
value of the parameter is right; each merely relocates the error. A version
tuned until the output matched what was already known would have been
*fitted to the answer*, and its green would have meant "the window happens
to suit today's documents" — indistinguishable, on screen, from "no drift
exists".

*The test:* ask what the check would report **if the thing it looks for were
somewhere it usually is not**. If the honest answer is "depends where", the
check measures its own configuration.

*The fix is never a better regex — it is to make the property explicit at
the source.* Status is currently prose, so it is being *reconstructed
downstream from a correlate that mostly works*. Declared, it becomes an
exact comparison and the heuristic disappears (`PLAN-register-status-
tokens.md`).

*Note where this one appeared.* It is the **fourth** instance of the
declared-vs-inferred family — after class inferred from publishing
behaviour (**GD-11**), absence inferred from a zero (**GD-12**), and
national origin inferred from a naming habit (**X-4**) — and the first
inside *this project's own tooling*, written by the people who named the
disease. That is evidence it is structural rather than a run of oversights:
**at the moment of writing, inference is always cheaper than declaration,
and it usually works.**

*Related:* *a guard is not evidence until it has been seen to fail*, and its
limiting case *a verification that includes its own subject in its evidence
is not a verification*. Three ways a check can be green and empty — never
exercised, self-satisfying, or fitted.

---

## Indexes drift where the work is not

**Propagation succeeds toward attention and fails away from it. An index is
by definition the place attention is not, so it is the first thing to go
stale and the last thing anyone notices.**

*Earned 2026-08-12, from a clean contrast in one corpus on one day.* An
audit falsified two claims in the ADR that commissioned it. The **ADR was
updated correctly** — its rows rewritten, a constraint moved from pending to
overdue — because the author was already reading that file. The **README
was not**: it still announced *"four divergences registered"* after two more
had been added the same day, from that same audit.

Nobody was careless. The update happened where the work was, and did not
happen where the work was not.

A wider check the same afternoon found **eleven documents missing from the
index entirely**, including `PRINCIPLES.md` and `GENERALIZATION-DEBT.md` —
the two most-cited files in the corpus — and three of five audits. The
project that most values written-down state had not indexed the documents it
cites most.

*The conclusion is mechanical checking, not more diligence.* Diligence is
precisely the resource that is unevenly distributed here — it concentrates
where someone is already looking, which is the one place drift does not
occur. A rule of the form *"remember to update the index"* asks for more of
the thing whose distribution is the problem. Two commands, each under a
second, cover both drift classes: **does every ID have a row, and does every
document have an entry.** Neither needs judgement, which is exactly why they
belong in CI rather than in a habit.

*Related:* **VE-1** (`ADR-0037`) registers *no index of evidence* as a gap —
the same mechanism one layer over. An index nobody is standing in front of
does not maintain itself, whether its subject is findings or evidence.

*Corollary — the check must not be able to satisfy itself.* See *a
verification that includes its own subject in its evidence is not a
verification*: the first draft of the ID check scanned a glob that included
the index it was checking. The anti-drift tooling and the self-reference
trap were earned in the same hour, from the same file.

---

## Measure the fix, not the fix's worst imaginable form

**The cost of a change and the cost of the change's worst plausible version
are different numbers, and deferral decisions routinely quote the second
while believing they quoted the first.**

*Earned:* the specimen-mapping fix was deferred with the note *"not changed
here — it alters fixture behaviour and the golden files that pin it."* Every
clause was true of the *imagined* fix (replace the catch-alls) and none was
true of the *actual* one (empty them: enumerate the declared values, leave
only unrecognised input falling through). Re-blessing all seven cases left
the six pre-existing goldens **byte-identical**. The measured churn was zero;
the quoted churn had never been measured, only pictured.

*Why the error is systematic rather than careless:* at deferral time the fix
is unwritten, so the only version available to cost is the first one that
comes to mind — and the first one to come to mind is the blunt one. The
estimate is honest and the number is still wrong. This is the same failure as
reasoning from a deployment to a framework law, one tense earlier: reasoning
from an *imagined* implementation to a *general* cost.

*Enforcement:* when cost is the stated reason for deferring, spend the few
minutes to produce the cheapest correct version and measure **that**. If the
measurement is genuinely expensive, defer on the honest ground — *"cost
unmeasured"* — rather than on a number nobody produced. **A deferral quoting
an unmeasured cost is a decision presented as an observation**, which is this
file's oldest theme arriving at the planning layer.

*Corollary — the cheapest correct version is usually additive.* The blunt fix
replaces; the cheap fix **narrows what the existing behaviour applies to**,
leaving every known case provably untouched. That framing also answers the
objection deferral was protecting against, since "will this change what we
see?" becomes a question with evidence rather than an argument.

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

## "Not found" is not "cleared"

**A report states what it did not establish, or its silence gets read as
absence of the thing.** The negative-space section is what stops a narrow
finding from being received as a broad all-clear.

*Earned:* a long-parked audit asked a binary question — *is this schema a
mirror of a source system's field hierarchy?* The answer was **no**. Stopping
there would have closed the item clean and wrong, because the reason was not
"we modelled it ourselves" but **"no declared model exists at all"** — a third
state nobody had named, and a more consequential one than the fear. It
appeared only because the reading went past the question to what the code
actually does, and it survived into the record only because the audit had a
section for *what this did not establish*.

*The general shape:* a parked question is usually a **binary** framed from
the outside. Reality answers *"no, and…"* far more often than *"no"*. The
"and" is the finding; the question was only the reason to go looking.

*Enforcement:* every audit or investigation ends with an explicit
did-not-establish section — what was out of scope, what was read from a copy
rather than a source, which judgements are first-pass rather than
exhaustive. Without it the next reader inherits a stronger claim than the
reading supports, and inherits it *silently*, which is the whole
silent-absence family arriving at the report layer.

*Related:* the same reflex as recording what a change deliberately did **not**
do, and why a bounded task reports what it left out rather than letting scope
appear complete.

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

## Stage paths, not everything

**`git add <path>`, never `git add -A`. A file being edited in one
session is not committed by another.**

A commit message describes the diff its author *intended*. A broad add
silently falsifies that: the content is fine, the message is fine, and
the two now describe different changes. Nothing breaks, which is why it
goes unnoticed — and it erodes exactly the property this project invests
most in, since commit messages here are where findings, reasoning and
corrections live durably.

The downstream cost is an anchoring failure. *Findings are anchored* so
their tense is recoverable (ADR-0037 §7) — and a register row whose
anchor commit is about something else has an anchor that misleads
rather than one that is merely absent.

*Earned, and the base rate is the point:* two concurrent sessions worked
`decisions/` on 2026-08-11. **Both** commits made while the other session
had uncommitted work in that directory swept it in — three ADRs into a
commit about a confabulating `_default`, and a register row about
evidence sanitization into a commit about fallback honesty. Two windows
of exposure, two sweeps. **Not an occasional accident — the default
outcome**, because `-A` is the reflex and the working tree is shared.

Both were pushed before they were noticed, so neither is fixable: the
content is correct and permanently filed under the wrong description.
Same asymmetry as the commit-message leak — the record is the thing you
cannot amend after it travels.

*Enforcement, both sides:*

- **Stage explicitly.** `git add <path>` for every file you intend to
  commit. `git status` before staging is the thirty-second check.
- **Ownership until committed.** A file another session is editing is
  theirs until it lands. If it appears in your `git status` and you did
  not write it, it is not yours to commit — ask or wait.
- **Commit promptly.** The exposure window is the time your work sits
  uncommitted, so the cheapest mitigation on the *writing* side is not
  leaving finished work in the tree. Both sweeps happened inside windows
  that lasted minutes.

*Corollary:* this generalizes past agents to any shared working tree —
pair sessions, a colleague on the same box, a background process that
writes generated files. The rule is about the tree being shared, not
about who is sharing it.

---

## Enter a sweep from the narrow end

**Trace backward from the identifier, not forward from the producer.
Forward tracing terminates at attention; backward tracing terminates at
the field.**

A forward sweep follows the data — producer, then persistence, then the
consumers you find. Every consumer it finds is real, so it never feels
wrong. It ends when the author stops finding new ones, and that is a fact
about how long they kept looking, not about the consumer set. A backward
sweep greps the identifier and enumerates readers: exhaustive,
mechanical, and usually a minute's work.

*Earned twice, both times a sweep under-reporting because of how it was
entered rather than what it looked for:*

- The capability-foreclosure audit traced forward from the discrepancy
  analyzer and reported **two** advisory surfaces. There are three — a
  regional roll-up was never opened. Found later by grepping
  `recommended_action`.
- Earlier, the same shape at the commit layer: reasoning forward from
  what a change *was about* rather than backward from what the diff
  *touched*.

*Corollary — it is also the cheaper direction to state a limit in.* A
backward sweep can say *"these are all the readers of this field"* and
mean it. A forward sweep can only honestly say *"these are the readers I
found"*, which is the sentence that should appear in any report that had
to trace forward — and its presence is a good signal that the wrong
direction was used.

*Related:* `PRINCIPLES.md` §"Not found" is not "cleared" governs what a
sweep says about its gaps; this governs whether it has them.

---

## How to use this file

- Add a principle when a *specific near-miss* produces a rule that would
  have prevented it, and the rule is portable beyond the decision that
  earned it.
- Keep each to a sentence plus its earning context. If it needs
  paragraphs of qualification, it is an ADR, not a principle.
- Principles do not override ADRs; they are the heuristics that make
  ADRs less necessary.
