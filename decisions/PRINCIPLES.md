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
