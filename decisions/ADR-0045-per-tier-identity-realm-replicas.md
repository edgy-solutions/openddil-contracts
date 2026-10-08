# ADR-0045: A severed tier can sign people in — a realm replica at each tier

## Status

**PROPOSED — 2026-10-08.** Draft 2026-09-29. Design only: nothing here is built,
and nothing is deployed. It is written for the next increment, which builds one
replica at one tier (§"The next increment").

This is identity rung 2. Rung 1 was the per-tier PDP (ADR-0029 §"Per-tier PDP",
2026-09-05): each tier's PEP decides against its own Topaz and its own copy of
the entitlements corpus, so a severed tier still **decides** and **enforces**.
ADR-0029 closes that section with the sentence this ADR exists to change:

> *decides locally, enforces locally, and cannot log anybody new in.*

ADR-0029 also said per-tier identity "rides the same seam as per-tier Topaz — a
Keycloak replica or a local IdP" and should be designed with it. This ADR takes
the replica branch and says why. What it still leaves open is listed with the
reason (§"Still open").

What changed between the draft and this proposal: the questions the draft marked
**unread** have been read (how a person is keyed, what the decision record
carries), the root Keycloak footprint has been measured, and the claim that every
upgrade rolls the identity pods has been corrected against two measured upgrades.

---

## Context — what is true today (read 2026-10-08)

* **One Keycloak, at the root.** `releasability.keycloak` in
  `openddil-helm/openddil-demo/values.yaml`: start-dev, in-memory H2, published
  passwords, no TLS, and a comment that it is **disqualifying anywhere but a lab**.
  A real deployment points `releasability.oidc` at the identity provider it
  already runs.
* **One realm artefact.** `openddil-demo/policy/realm-openddil.json`: realm
  `openddil`, five users with **pinned ids**, password credentials, the root PEP's
  client `openddil-pep`, and a `__TIER_CLIENTS__` splice point the chart fills with
  one confidential client per tier that has a public origin. The realm already
  forbids every self-service write: `registrationAllowed`, `resetPasswordAllowed`
  and `editUsernameAllowed` are false. `bruteForceProtected` is true.
* **A person is keyed on `sub`.** `openddil-demo/policy/users.yaml` states it
  ("THE KEY IS THE OIDC `sub`, AND NOT THE USERNAME OR THE EMAIL"). The PEP takes
  `subject = claims["sub"]` (`gateway/oidc.py`) and sends only that to Topaz
  (`gateway/pep.py`, `ask_topaz`).
* **The PEP trusts exactly one issuer.** `gateway/oidc.py` refuses a token whose
  `iss` is not `OPENDDIL_OIDC_ISSUER`, and one whose `aud` does not contain the
  PEP's own client id. Every tier PEP is given the **root's** issuer
  (`templates/tier-node.yaml`).
* **The decision record has no issuer.** `record_decision(...)` in
  `gateway/pep.py` writes subject, policy version, corpus version, role, allowed
  nations, predicate and shape handle. It does not write `iss`.
* **A cut takes sign-in away.** `scripts/sever-tier.sh` applies a default-deny
  NetworkPolicy whose egress allows only same-site pods and DNS, so a severed
  tier cannot reach the root's Keycloak. Its usage text says so: an existing
  cookie keeps working for its TTL, a fresh login does not.
* **Identity pods roll on content, not on revision, when the bundle is pinned.**
  `openddil.policyChecksum` (`templates/_helpers.tpl`) folds
  `.Release.Revision` into the Keycloak, PEP and Topaz checksums **only** when
  `bundle.image.digest` is empty. Measured on the lab, two upgrades on chart
  0.1.93 with a pinned bundle (revisions 115 and 116) rolled 11 pods each and
  **no** Keycloak, PEP or Topaz pod. The draft's "every upgrade signs everyone
  out" (measured 2026-09-29, revision 56 → 57) describes an unpinned install,
  and it is still true of one.
* **Footprint, measured 2026-10-08.** Root Keycloak, idle, one realm: **572Mi**
  working set, 2m CPU. Requests 768Mi / 100m, limit 3Gi / 1 (raised after
  OOMKills at 1Gi and 2Gi before the heap cap). Each PEP: 22–26Mi.

**The gap in one sentence:** an operator who arrives at a severed edge after the
link went down cannot use the edge's UI at all, though the edge holds the data,
the policy, and the decision point to serve them.

---

## Decision

### 1. Each tier runs its own issuer, with its own signing keys

A tier's replica is a **separate issuer** (`<tier public origin>/idp/realms/openddil`)
with **keys generated at the tier**, and the tier's PEP trusts only its own issuer.
No private signing key is distributed anywhere.

Why a separate issuer rather than a replica of the root's: the browser holds no
token (ADR-0029, backend-for-frontend), so a token never needs to be accepted by a
tier other than the one that minted it. Sharing keys would buy cross-tier token
acceptance that nothing uses, at the price of putting the root's signing key on
every edge. A key compromised at an edge then compromises one edge.

The PEP's existing single-issuer check is the enforcement: a tier PEP pointed at
its own issuer refuses a root-minted token on `iss` with no new code.

### 2. What is replicated, and what is not

The replica carries **authentication only**. ADR-0029: *Keycloak answers who is
this; Topaz answers what may they see*, and entitlements are git-asserted in the
corpus, not held in Keycloak. A replica that is out of date can admit a person; it
cannot widen what they see, because what they see is decided by the tier's Topaz
against the corpus the tier already holds.

| content | replicated? | how |
|---|---|---|
| realm settings (`openddil`, the self-service switches, brute-force policy) | **yes** | the realm artefact, unchanged |
| users, with their **pinned ids** | **yes** | the realm artefact, unchanged |
| user credentials | **yes** (demo realm only) | the realm artefact; see §"Still open" for a real realm |
| the tier's own confidential client and redirect URI | **yes, this tier's only** | spliced at the tier from the same `openddil.keycloakTierClients` the root uses |
| other tiers' clients, and the root's `openddil-pep` | **no** | a replica can only mint for its own PEP |
| signing keys | **no** | generated at the tier on first start |
| SSO sessions, brute-force lockout counters | **no** | tier-local state, never reconciled |
| admin credentials | **no** | generated per tier into a Secret at the tier |
| entitlements, roles used for decisions | **not in Keycloak at all** | the corpus, already per tier (rung 1) |

**The pinned ids are what make this cheap.** Because every replica imports the
same users with the same ids, a person has the **same `sub` at every tier**. The
corpus is keyed on `sub`, so it needs no change and no per-tier mapping. The pair
`(iss, sub)` differs per tier; `sub` alone still names one person everywhere.
That is a property of the demo realm, and an invariant the next increment checks:
**a realm whose users lack pinned ids is refused by the replica's import step**,
because without them each tier would mint a different `sub` for the same person
and the corpus would admit nobody.

### 3. How a tier's realm stays consistent with the root

The root is **not** the source the tiers copy from. The **realm artefact** is.
The root's Keycloak and every replica import the same `realm-openddil.json` from
the same runtime bundle, beside the policy and the corpus (ADR-0029 §6's model).
"Consistent with the root" therefore means one testable thing: **the tier's realm
digest equals the root's**.

* **One writer.** The realm changes only by a commit to the artefact. No Keycloak,
  root or tier, holds a change that is not in the artefact: the realm already
  forbids registration, password reset and username edits, and a replica runs with
  the account console and admin console unreachable from the tier's public
  origin. A credential written at a tier would be a fork; none can be written.
  (The root's admin console is in-memory H2 today, so an edit there is already
  lost on restart. This ADR makes that the rule rather than an accident.)
* **Required actions are refused at import.** A user carrying a required action
  (say `UPDATE_PASSWORD`) would change their credential at whichever tier they
  first signed in, and fork the realm. The replica's import step refuses a realm
  in which any user has a required action.
* **Updates ride the bundle, and roll on content.** A replica rolls when the realm
  artefact's digest changes, through the same `openddil.policyChecksum` the root
  Keycloak uses, with the realm digest as an `extra` input. With a pinned bundle,
  an upgrade that does not change the realm rolls no replica (measured today for
  the root: §Context).
* **The digest is visible.** The replica's realm digest is stamped where the
  policy and corpus versions already are: on the PEP's status and in every
  decision record (`realm_version`). A drift check compares the digest across the
  root and every linked tier: with all links up, **one** distinct digest is
  expected. More than one, with the links up, is drift and is reported as such.
  With a tier severed, its older digest is the expected reading, not a fault.
* **The decision record gains `issuer`.** Today it records `subject` only. With
  per-tier issuers, the record must carry `iss` beside `sub`, so the audit trail
  says where a person signed in. Joining across tiers stays on `sub` (§2).

### 4. Revocation is bounded by the link, and that is stated, not hidden

A person disabled at the root (removed from, or disabled in, the artefact) can
still sign in at a tier that has not received the new bundle: severed, or not yet
rolled. The bound is **the age of the tier's realm artefact**, shown to the
operator beside the policy and corpus versions.

This is the property the corpus already has: an entitlement removed at the root
is still honoured by a severed tier's Topaz until the bundle arrives. This ADR does
not introduce stale identity; it makes stale identity the same shape as stale
policy, with one version stamp to read for both. And because authorization stays
in the corpus, the faster lever for a revocation is the corpus entry, which takes
away what the person can see at every tier the new corpus reaches.

### 5. The bundled demo only; the issuer URL is the contract

Nothing in §1–§4 requires Keycloak. A deployment that already runs an identity
provider brings its own answer to "can a tier authenticate while severed": a
replica or broker of that provider at the tier, or certificate-based sign-in
validated locally against a CA bundle and a cached revocation list. **The chart's
contract is the PEP's issuer URL per tier.** This ADR decides what the bundled
demo identity provider does, and makes a per-tier issuer a supported shape. The
replica carries the root Keycloak's lab-only marking: the same values switch that
says the bundled Keycloak is disqualifying anywhere but a lab covers its replicas.

---

## The four-profile login test under a cut

The acceptance test for the next increment. It reuses the four-profile scripted
sign-in that already gates every deploy (`scripts/oidc_login.py`, one call per
profile, pass = an `openddil_session` cookie after the full code flow), pointed at
a tier's public origin instead of the root's.

Profiles: `operator.atlantia`, `operator.borduria`, `operator.regioneast`,
`liaison.coalition`. Control profile: `observer.unlisted`, who is in the realm and
not in the corpus.

| step | action | pass |
|---|---|---|
| 0 | four-profile sign-in at the **root** origin, link up (the standing pre-cut gate) | 4 / 4 |
| 1 | four-profile sign-in at **edge-01's** origin, link up; record each profile's `role` and `allowed_nations` from its first decision record | 4 / 4, and a baseline per profile |
| 2 | **predict**, then cut edge-01 from its parent (`sever-tier.sh`, `--from-parent`) | policy applied |
| 3 | **prove the cut can fail the test**: from edge-01's PEP pod, a connect to the root Keycloak Service | refused or timed out. If it connects, the cut is not real and the run stops |
| 4 | four-profile sign-in at edge-01's origin, severed | **4 / 4**, and each profile's `role` and `allowed_nations` equal step 1's: **0 diffs** |
| 5 | `observer.unlisted` at edge-01, severed | signs in; first read **denied** by Topaz. The replica admits; the corpus decides |
| 6 | a root-minted token presented to edge-01's PEP | **refused on `iss`** |
| 7 | four-profile sign-in at the root origin, edge-01 still severed | 4 / 4 (unaffected) |
| 8 | heal; four-profile sign-in at root and at edge-01 | 4 / 4 each; realm digests: **1** distinct across root and linked tiers |

**The red run comes first.** Steps 2–4 against today's chart, with no replica,
must read **0 / 4** at step 4. If they read anything else, the test cannot tell a
replica from no replica, and it is not a test. A second red: a realm in which a
user has a required action, or lacks a pinned id, must be refused by the import
step with the reason printed, and must not start a replica.

The designed-but-objectionable reading, for the reviewer: a user disabled in the
artefact, with edge-01 severed before the new bundle reached it, **is admitted**
at edge-01, and that tier's realm version reads older than the root's (§4).

---

## The next increment

What the next increment builds, at one tier (edge-01), behind a per-tier value
defaulting to off. Each line is checked by the test above.

1. A replica Deployment for a tier with `identity.replica: true`: the same
   Keycloak image and heap cap as the root, importing the realm from the bundle
   with only that tier's client spliced in, admin and account consoles not routed
   from the tier's public origin.
2. An import step that refuses a realm with unpinned user ids or any required
   action, with the reason printed (the second red).
3. The tier PEP's `OPENDDIL_OIDC_ISSUER` and internal issuer pointed at the
   replica when the value is on. Off, the tier is exactly today's: root issuer,
   root client. The root keeps every tier client, so turning a replica off is the
   rollback.
4. `realm_version` and `issuer` in the decision record and on the PEP's status;
   the realm digest as an `extra` input to the replica's `policyChecksum`.
5. The drift check (one distinct digest across linked tiers).
6. Measure the replica's working set under the four-profile sign-in, before any
   decision about every edge running one.

Not in the next increment: replicas at more than one tier, durable Keycloak
storage, any change to Topaz or the corpus.

---

## Still open, and why

* **Credentials at the edge, for a real realm.** The demo realm's passwords are
  published, so carrying them in the bundle costs nothing. For a real realm it is
  the whole question, and the answer depends on the deployment's authenticator.
  Certificate sign-in is the obvious candidate and is named, not chosen. §5 is why
  this does not block the demo.
* **A replica at every edge, or at regional tiers only.** Root idle footprint is
  572Mi. Three tiers in the lab would add about 1.7Gi working set and 2.3Gi
  requested. Whether edges run a replica or sign in through their region is
  decided from step 6 of the next increment, not from the idle number.
* **Persistent state.** Import-on-start on in-memory H2 makes a replica restart
  lossless for users and credentials, and loses SSO sessions. The PEP keeps its own
  session table, so a replica restart should not sign anyone out of the PEP until
  that session needs the IdP again. **That is a prediction, not a reading**, and
  the next increment measures it.
* **Federation across tiers.** A person who moves from one tier to another signs
  in again at the new tier. No single sign-on spans tiers. That is accepted for the
  demo, and it is what §1's "no token crosses tiers" costs.

## Predictions, to be measured by the next increment

On the lab, with edge-01 given a replica and the others unchanged:

| reading | predicted |
|---|---|
| four-profile sign-in at edge-01's origin, link up | 4 / 4 |
| same, edge-01 severed from its parent | **4 / 4** (today: 0 / 4) |
| per-profile `role` and `allowed_nations`, severed vs link up | 0 diffs |
| `observer.unlisted` at edge-01, severed | signs in, first read denied |
| four-profile sign-in at the root origin, edge-01 severed | 4 / 4 (unaffected) |
| a root-minted token at edge-01's PEP | **refused** on `iss` |
| a user disabled in the artefact, edge-01 severed before the bundle reached it | **admitted**, realm version older than the root's |
| distinct realm digests, all links up | 1 |
| identity pods rolled by a pinned-bundle upgrade that changes neither realm nor PEP | **0** at the root (measured: revisions 115, 116) and 0 at the replica |
| replica working set under the four-profile sign-in | not predicted; measured before sizing |

## What this does not decide

* A production identity provider, its authenticators, or its federation.
* Any change to how Topaz decides, or to the corpus.
* Whether the egress path (ADR-0043) needs a tier-local identity. Egress subjects
  are system principals, not people, and are out of scope.
