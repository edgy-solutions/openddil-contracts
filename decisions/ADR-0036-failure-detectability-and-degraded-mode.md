# ADR-0036: Failure detectability and degraded-mode behaviour

## Status

Accepted — 2026-08-11. **Standing engineering position.** Like ADR-0035,
this consolidates behaviour the system already has and states the rule
that produced it. Unlike ADR-0035, it also carries a **register of
failure modes with no detection story**, which is new and is the point.

## Context

The most expensive class of defect in this project has not been a wrong
answer. It has been a **failure that looks exactly like success**.

`PRINCIPLES.md` records the family; four instances, all found the hard
way:

| | looks like | actually is |
|---|---|---|
| DDS QoS mismatch | a quiet topic | no subscription match |
| a site with no feed | a broken deployment | a site with no feed |
| the edge→HQ buffer probe | a caught-up link | a consumer group that never existed |
| a chart template's header | a rendered component set | two components described and never built |

Each pair is byte-identical from the observer's position. The shape
recurs because *"nothing arrived"* is the natural rendering of both
success and failure, and because the innocent reading is always the
comfortable one.

The buffer probe is the sharpest instance and the reason this ADR
exists. `edge_buffer_monitor.py` queried consumer group `bridge-group`;
the bridges commit under `bridge-group-<edge_id>`. The probe's own
documented contract was *"returns 0 if the group has not committed any
offsets yet."* So it returned **0 on every cluster, for months**, while
the DDIL buffering it was measuring worked correctly the entire time.
Nothing errored. Nothing warned — probe failures logged at DEBUG, which
is invisible at the default level. And `0` was always plausible.

The consequence is worse than a wrong number: **the buffering claim was
unverifiable rather than wrong.** An unverifiable claim cannot be argued
with, and it had been quietly load-bearing for the arc's central
demonstration.

A second, inverse instance arrived the same week. Extra "what did the
policy actually see?" rules were added to a Rego policy *specifically to
avoid a silent-absence trap* — so a `false` decision could be told apart
from a policy that never received input. Those rules returned strings and
arrays; the authorizer's `Is` API errors the entire query if any
requested decision is non-boolean. Every query failed with `undefined
results`, for six iterations, while the bundle had loaded and the policy
was working correctly the whole time. **The anti-silent-absence machinery
produced a loud failure that masked a success** — the mirror image, and
the reason clause 6 below exists.

Separately, ADR-0022 stated severance tolerance for the data plane. Three
other planes were later found non-tolerant — presentation (ADR-0032),
detection (ADR-0034), and a third instance (`cm-service`) surfaced by
[AUDIT-2026-08-08](AUDIT-2026-08-08-severance-tolerance-inventory.md).
All three were found *by accident, from unrelated investigations*. Those
are the same disease as the probe: a property that is claimed, not
implemented, and whose absence produces no signal.

## Decision

**A failure mode is either detectable or registered as undetected. There
is no third state.**

Six clauses, each earned.

### 1. A probe fails distinguishably from its own zero

An instrument whose failure mode is indistinguishable from its healthy
reading is not an instrument. Absence, misconfiguration, and
nothing-to-report must produce different outputs.

Implementation contract, as shipped in `edge_buffer_monitor.py`:

- **Raise on absence rather than returning a value.**
  `BridgeGroupAbsent` is raised when the configured group has committed
  nothing on the bridge topics — and the exception message names the
  likely cause (`the bridge commits under 'bridge-group-<edge_id>'`), so
  the log line is a diagnosis rather than a symptom.
- **Write a sentinel the consumer cannot mistake for data.**
  `LAG_UNKNOWN = -1`, deliberately negative, with `probe_healthy = False`
  written alongside. *A UI showing `-1` prompts a question; a UI showing
  `0` ends one.* Rendering that sentinel legibly is ADR-0035 class 2.
- **Warn at WARNING, deduplicated.** A signal suppressed by default is
  not a signal; and a permanent error emitted 30×/min trains readers to
  filter it exactly as a permanent `0` trained them to trust it.
  `_warn_once` keyed per failure cause.
- **A genuinely healthy zero must still travel the normal path.** A
  caught-up bridge *has* committed offsets and returns `0` through
  `_probe_bridge_lag`'s ordinary return — so the two cases are
  distinguishable at the source and must stay distinguishable at every
  hop above it.

### 2. Absence is never rendered as nominal

The presentation-side rule is ADR-0035's; it is restated here as an
obligation on the *producer*, because a sentinel that no consumer honours
is decoration. A probe that writes a not-a-reading value owns a
consumer-side check that the value is rendered as not-a-reading.

### 3. Fail closed where authorization or labelling is involved

Where a decision gates access, an error is a deny. Where enforcement
depends on data completeness, **label first, enforce second — never the
reverse** (`PRINCIPLES.md` §Ordering; ADR-0029 §7): turning on
enforcement against partially-labelled data silently blanks legitimate
results, and an operator cannot tell that screen from correct
enforcement. Completeness is a hard gate before enforcement, not a
parallel workstream.

Current state, stated plainly rather than aspirationally: Arc 1 runs
**open-access** with the policy sidecar deployed and deciding nothing
(ADR-0032). Deny-unlabeled is designed, fenced, and **not enabled**. This
clause is a rule governing how it lands, not a description of a control
that is live.

### 4. Severance is a degraded mode, not an error

A tier that presents, decides, or detects must be able to do so from what
it locally holds (`PRINCIPLES.md` §Locality). Under severance the
expected behaviour is *continued local operation plus an honest statement
of what is unreachable* — not an error state, not a blank screen, and not
a frozen last-known view presenting as current.

The corollary for new work: when adding any capability, ask which tier it
must work at when the link above is cut, and whether its inputs are
there. **"It reads from the parent" is the failure, whatever the plane is
called.**

[AUDIT-2026-08-08](AUDIT-2026-08-08-severance-tolerance-inventory.md) is
this clause's annex — every service, its tier, its reads and writes, its
external runtime dependencies, and its tolerance classification
(`TBC` / `TBB` / `NT`). Its own scope limits stand: the table is derived
from charts and source, **not from observed behaviour under an actual
sever**, and egress/overlay components are out of its scope. The
per-tier resolution for the four `NT` rows is GD-08 (in-arc).

### 5. Every failure mode has a detection story, or a register row

The methodology claim in the audit — *"three lucky finds is not an audit
methodology"* — generalizes. A failure mode is documented with **how it
would be noticed**, in one sentence, naming the signal. If no such
sentence can be written, the mode goes in the register below, which is
the honest outcome and a schedulable one.

A note that identifies a hazard and ships anyway is a confession, not a
control (`PRINCIPLES.md` §A documented hazard is not a mitigated one).
One of three must accompany it: change the default, open a tracked row
naming the replacement and the trigger, or add a pre-flight check that
fails with the real reason.

### 6. Observability is part of the system and inherits its verification burden

A diagnostic that has not been seen to produce a **correct** reading is
not yet a diagnostic. A guard that has not been seen to **fail** is not
yet evidence — both replacement checks after the YAML-separator defect
were run against the unfixed artifact and confirmed red before being
trusted (`PRINCIPLES.md` §Match structure, not prose).

This clause is not symmetric decoration on clause 1. It is the lesson of
the Rego instance: hardening added to avoid a silent failure is new code,
and new code fails. The buffer-monitor fix itself was verified against a
real cluster before/after — `0 0 0 0 0` versus `30 65 97 130 165` against
a broker-confirmed `32 66 99 132 165` — which is the standard, not an
unusual level of rigour.

## Register — failure modes with no detection story

Open rows. Each is a mode that would currently pass unnoticed, or whose
detection is weaker than the claim it supports.

`Status: open`

**UD-1 — The severance detector depends on the uplink whose loss it
detects.** `edge_buffer_monitor._probe_hq_link_severed` reads the
toxiproxy API at a **root-tier** service. Its companion lag probe reads
the tier's own broker and works while severed; the link probe does not.
Observed in rehearsal on a pre-0.1.42 build: the link-down flag appeared
correctly at +20s and **flapped back to `false` at +80s**. The buffer
count is the load-bearing signal and it is locally sourced, so the
severance proof holds — but the flag beside it is a clause-4 violation
inside the very mechanism that demonstrates clause 4. Recorded in
`PILOT-RUNBOOK.md` §5 as a caveat operators must report on; recorded here
as an open failure mode. *Fix shape: derive the severed state from local
observables (bridge produce failures, lag derivative) rather than from a
remote control-plane read.*

`Status: open`

**UD-2 — No classification in the severance inventory has been observed
under an actual sever.** The `TBC`/`TBB`/`NT` table is a reading of
charts and source. It is almost certainly right and it is not evidence.
The pilot runbook's rung (iii) produces the first real observation, for
**one** service set at **one** site. *Closing shape: fleet rollout
re-runs the ladder per site; until then the table's status is "derived",
and it says so.*

`Status: open`

**UD-3 — Egress and overlay components are outside every tolerance
sweep.** Deployment-overlay components are not core chart, were excluded
from the 2026-08-08 audit by scope, and have no equivalent inventory.
Whether a customer egress connector degrades honestly under severance is
currently unknown rather than known-good. *Closing shape: the same table,
run over the overlay's component classes via the public manifest, so the
sweep is expressible without naming private material.*

`Status: open`

**UD-4 — A pre-sync zero on the buffer tile.** ADR-0035 IH-1, restated
here because its *cause* is instrument-side: the surface has no way to
distinguish "no reading yet" from "a reading of zero" because nothing
distinguishes them in what it receives before the first shape sync.

`Status: open`

**UD-5 — Middleware-participation health has no observable yet.**
ADR-0030 records the DDS class's characteristic trap as an architectural
requirement: **QoS mismatch fails silently** — no match, no data, no
error — so discovery/matching state must be a first-class observable and
data flow alone is not a health signal. The requirement is recorded; the
observable does not exist, because the participation sidecar does not
exist. Registered so the sidecar cannot ship without it and call the
silence nominal.

`Status: open`

**UD-7 — A resource failure can manifest on a component that did not cause
it.** *(Found 2026-08-12; the chart instance is fixed, the class is not.)*

The NFS escape hatch swapped a PVC for an `emptyDir` and, in doing so,
dropped the size bound the PVC path carried — the branches rendered
`emptyDir: {}` while `persistence.redpandaSize` / `restateSize` bounded the
`volumeClaimTemplates` they replaced.

**The detectability problem is not the missing field; it is where the
failure surfaces.** An unbounded `emptyDir` is charged against the *node's*
ephemeral storage with no cap. A broker filling that disk triggers kubelet
eviction **across the whole node**, and eviction selects victims by usage —
so the pods killed are frequently **not** the pod that caused it. The
operator sees unrelated components dying on a node where nothing local looks
wrong, and the component actually at fault may survive.

Every clause-1 instinct fails here, because they all assume the failing
component is the one to instrument. **The signal has to be sought at the
node, not at the victim**, and nothing in this system currently looks there.

*Detection story, as required by clause 5 — partial, which is why this is a
register row and not a closed item.* `sizeLimit` (chart 0.1.46) converts the
node-wide, misattributed failure into a **pod-local, correctly-attributed**
one: the offending pod alone is evicted, for a legible reason. That is a
real improvement and it is **not detection** — nothing yet *reports* node
ephemeral-storage pressure, and the other 21 `emptyDir` volumes in the chart
are bounded by construction rather than by policy, which is an argument, not
an observable.

*The generalizable half, which outlives this chart:* **an escape hatch that
silently drops a constraint is a second failure mode hiding inside a
workaround for the first.** The hatch was added to fix `ENOLCK`
CrashLoopBackOff on NFS clusters and it does that correctly; nobody noticed
it also removed a bound, because **the removal is invisible in the diff that
adds the branch** — the new code is all additions, and the constraint that
disappeared lived in the path not taken. Any conditional that substitutes
one mechanism for another should be read for *what the replaced path was
carrying*, not only for what the new path does.

`Status: open`

**UD-6 — Undetected-failure coverage is itself unaudited.** This register
was assembled from known findings, not from a systematic pass over the
component set. It is a starting inventory. *Per `PRINCIPLES.md`
§"Not found" is not "cleared": the absence of a row is not evidence that
a component has no undetected failure modes.*

## Consequences

**Pros**

- The silent-absence family gets one name, one rule, and one place to
  look — instead of being re-derived after each instance.
- The register converts *"we haven't thought about it"* into *"we have,
  and it is open"*, which is schedulable and which stops a narrow
  finding being received as a broad all-clear.
- Clause 1's contract is concrete enough to copy. The four bullets are
  the actual shipped shape, not a paraphrase — a new probe author has a
  reference implementation.

**Cons**

- Clause 5 is a discipline rule; nothing enforces it mechanically. It
  costs a sentence per documented failure mode and will be skipped under
  pressure, exactly like the follow-up-logging rule it resembles.
- Sentinels and dedup add code to every probe, and clause 6 says that
  code must itself be exercised. The buffer monitor's hardening is
  roughly a third of the file. That is the correct ratio for an
  instrument and it is not free.
- The register will look worse over time before it looks better, because
  a thorough pass (UD-6) adds rows. That is the mechanism working.

**Rejected alternatives**

- *Return `None`/null instead of a negative sentinel.* Rejected at the
  wire layer: the value crosses Postgres → Electric → React, and every
  hop has its own null-coalescing idiom. IH-1 is precisely a `?? 0`
  coalescing a null into a plausible reading. A value that is *wrong on
  its face* survives careless handling in a way that null does not.
- *A generic health-check framework covering all probes.* Rejected for
  now: there are few enough probes that the per-probe contract is
  cheaper than the abstraction, and a framework would have inherited the
  same wrong default in every consumer — see the copied-default
  corollary: **structural similarity carries defects with the authority
  of having shipped.**
- *Treating the severance-tolerance table as verification.* Rejected
  explicitly; it is UD-2.

## Related

- **ADR-0022** — severance tolerance for the data plane; the invariant
  the other planes inherited in claim only.
- **ADR-0032 / ADR-0034** — the presentation-plane and detection-plane
  reachback findings; clause 4's two discovered instances.
- **ADR-0029** — per-tier local authorizers with policy as bundles; the
  pre-empted third instance, and clause 3's ordering gate.
- **ADR-0030** — QoS mismatch as an architectural requirement (UD-5).
- **ADR-0035** — information honesty; the consumer-side companion to
  clauses 1 and 2.
- **ADR-0037** — verification evidence; how clause 6's "seen to fail" is
  recorded rather than remembered.
- **[AUDIT-2026-08-08](AUDIT-2026-08-08-severance-tolerance-inventory.md)**
  — clause 4's annex.
- **`PRINCIPLES.md`** §A probe must fail distinguishably from its own
  zero · §Locality · §Ordering · §A documented hazard is not a mitigated
  one · §Match structure, not prose · §"Not found" is not "cleared".
- **GD-08** (`GENERALIZATION-DEBT.md`) — per-tier detection; the
  in-arc resolution for the `NT` rows.
