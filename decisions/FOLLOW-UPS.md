# Follow-up index

**Reconciled:** 2026-08-12. **This file is a POINTER, never a source.**
Every row's authority is its home document; if they disagree, the home wins
and this file is the thing that is wrong.

## Why this exists, and why it is shaped this way

Open follow-ups live in **six separate registers** across five documents.
Nobody could answer *"what is outstanding?"* without opening all of them,
and the corpus had already drifted — see §Reconciliation.

ADR-0037 **rejects a traceability matrix as a primary mechanism**, for a
good reason: *a document parallel to the work drifts from it*. That
rejection applies to this file, so it is built to be checkable rather than
trusted:

- rows carry an **ID, a short subject, a home, and a status — never content**.
  Restating a finding here would create a second version to keep in sync,
  which is the failure ADR-0037 names;
- **drift is mechanically detectable** (§How to check), so this file cannot
  silently fall behind the way `README.md` just did;
- it indexes **IDs only**. Follow-ups recorded as prose in audits and plans
  are deliberately out of scope — see §What this index does not cover.

## How to check this index is current

```bash
cd openddil-contracts/decisions
corpus=$(grep -ohE "\b(GD|UD|VE|IH|AE)-[0-9]{1,2}\b" \
           $(ls *.md | grep -v '^FOLLOW-UPS.md$') | sort -u)
rows=$(grep -ohE "^\| (GD|UD|VE|IH|AE)-[0-9]{1,2} " FOLLOW-UPS.md \
         | tr -d '| ' | sort -u)
comm -23 <(echo "$corpus") <(echo "$rows")   # in corpus, missing here
comm -13 <(echo "$corpus") <(echo "$rows")   # here, but nowhere else
```

Both must print nothing. **37 IDs as of this reconciliation.** A mismatch
means the corpus moved and this file did not — which is information, not an
error.

> **Note the `grep -v FOLLOW-UPS.md`, which is load-bearing.** The obvious
> form of this check scans `*.md`, which includes *this file* — so every ID
> written here would appear in its own "corpus" and the second comparison
> **could never fail**. A phantom row, or an ID surviving here after being
> renamed at home, would pass silently. The first draft of this check had
> exactly that flaw.
>
> *A verification that includes its own subject in its evidence is not a
> verification* — the same shape as a guard that has never been seen to
> fail, arriving in the checker written to prevent drift.

*This check is why the file is worth having.* It cannot verify a status is
still accurate — only a human reading the home document can — but it makes
the *cheap* failure (a row that never got added) mechanical, and leaves only
the expensive one to judgement.

---

## Registers

### GD — generalization debt (`GENERALIZATION-DEBT.md`)

| ID | Subject | Status |
|---|---|---|
| GD-01 | `edge_id`/`region_id` encode a two-level hierarchy | open |
| GD-02 | Named-tier components encode three tier kinds | open |
| GD-03 | Intermediate tier has no broker (Phase-6 shortcut) | open |
| GD-04 | Three fixed views rather than a tier-generic view | open |
| GD-05 | `region_top_factors` is non-composable (top-N truncation) | open |
| GD-06 | Tree-only data flow; no lateral peer links | open |
| GD-07 | All three analytics planes hardcoded | open |
| GD-08 | Detection centralized at root, reaching downward | **in-arc (Arc 1)** |
| GD-09 | Bare-name alias Services | **resolved (0.1.40)** |
| GD-10 | Capability-item shape undeclared | open |
| GD-11 | Asset class inferred from one feed's behaviour | open |
| GD-12 | Absence conventions declared only in the consumer | open |

### UD — undetected failure modes (`ADR-0036`)

| ID | Subject | Status |
|---|---|---|
| UD-1 | Severance detector depends on the uplink it detects | open |
| UD-2 | No tolerance classification observed under a real sever | open |
| UD-3 | Egress + overlay components outside every sweep | open |
| UD-4 | Pre-sync zero, instrument-side *(see IH-1)* | open |
| UD-5 | Middleware-participation health has no observable | open |
| UD-6 | **The register itself is unaudited** | open |

### VE — verification-evidence gaps (`ADR-0037`)

| ID | Subject | Status |
|---|---|---|
| VE-1 | No index of evidence | open |
| VE-2 | Suite exits 0/1 — "the suite passed" cites nothing | open |
| VE-3 | Recording retention is "whoever has the file" | open |
| VE-4 | Chart self-description checked by hand | open |
| VE-5 | Single-site evidence behind fleet-shaped claims | open |
| VE-6 | No supersession rule | open |
| VE-7 | Evidence artifacts have no sanitization gate | open |

### IH — information-honesty divergences (`ADR-0035`)

| ID | Subject | Status |
|---|---|---|
| IH-1 | Pre-sync `?? 0` renders a confident zero *(see UD-4)* | open |
| IH-2 | Three of four CM/ops quadrants rendered distinctly | open |
| IH-3 | `tactical_events.severity` mixes two vocabularies | open |
| IH-4 | Tier identity answered by URL, not asserted | open |
| IH-5 | Most-derived value carries weakest provenance | open |
| IH-6 | Horizon renders as a bare duration, no basis | open |

### AE — capability-envelope gaps (`ADR-0038`)

| ID | Subject | Status |
|---|---|---|
| AE-1 | ADR-0011 claimed work-order generation | **resolved 2026-08-12** |
| AE-2 | Machine advisories ship with no provenance | open |
| AE-3 | Supply-only — no demand model | open |
| AE-4 | Horizon exists; uncertainty band does not | open |
| AE-5 | GD-10 is a prerequisite here too | open |
| AE-6 | Diagnosis absent, deliberately not listed | open |

### C — do-not-harden constraints (`ADR-0038` §6)

Not follow-ups: **standing constraints on present work**. Listed so they are
not mistaken for optional. `C4` is the only one with a clock, and it is
**overdue** — its trigger was *"before the first advisory-producing unit"*
and AUDIT-2026-08-12 F1 found advisories already shipping.

---

## Reconciliation — what this pass found

**The corpus is in better shape than expected in one place and worse in
another, and the difference is instructive.**

- **ADR-0038 was already reconciled.** AUDIT-2026-08-12 falsified two of its
  claims, and `AE-2`/`AE-4` had already been rewritten and `C4` already
  moved to overdue. The *findings* propagated correctly.
- **`README.md` had not.** Its ADR-0035 entry still said *"Four divergences
  registered"* and listed IH-1..IH-4; `IH-5` and `IH-6` were added the same
  day from that audit and never reached the index. **Corrected in this
  commit.**

*Both halves of one lesson:* the propagation that happened was into the
**document that owns the finding**, where the author was already reading.
The propagation that failed was into a **summary maintained elsewhere**.
Indexes drift where the work is not; that is the argument for the
mechanical check above, and the reason this file does not restate content.

- **`UD-4` and `IH-1` are the same defect** — the pre-sync `?? 0` — recorded
  independently in two registers, instrument-side and render-side. Not a
  duplicate to merge: the two-layer split is the point, and AUDIT-2026-08-12
  found the same pairing again in `IH-5`/`IH-6`. **The pattern is worth
  naming: a producer-side gap and its render-side consequence get found
  separately, at different times, by different sweeps.** Cross-linked here
  so the pair is visible.
- **AUDIT-2026-08-11 (fallback honesty) is fully closed** — F1–F4 all fixed
  (`ead7903`, `90cbaf6`, `efef7a6`). F5–F9 were clean on inspection. Its one
  surviving item was promoted to `GD-12` rather than left in the audit.
- **AUDIT-2026-08-12 (capability foreclosure) F1–F4 remain open** and are
  the reason `AE-2`, `AE-4`, `IH-5`, `IH-6` and `C4` read as they do.

## What this index does not cover

- **Prose follow-ups in audits and plans** — deliberately. Only ID'd rows
  are indexed, because only they can be checked mechanically. Anything
  worth tracking should therefore *earn an ID in a register*, and this
  boundary is the incentive to give it one.
- **Statuses are not verified here.** The check above proves a row exists,
  not that `open` is still true. A row marked open that was quietly fixed
  will not be caught by any command in this file.
- **`PLAN-*` documents' open steps** — they carry their own sequencing and
  are not follow-ups in the register sense.
- **Anything outside `openddil-contracts/decisions/`.** Follow-ups recorded
  in other repositories' code comments or runbooks are not visible here,
  and no claim is made that this is the complete set of outstanding work.
