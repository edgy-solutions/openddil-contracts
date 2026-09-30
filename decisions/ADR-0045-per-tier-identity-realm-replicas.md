# ADR-0045: A severed tier can sign people in — a realm replica at each tier

## Status

**DRAFT — 2026-09-29. Not proposed for acceptance yet; nothing here is built.**

This is identity rung 2. Rung 1 was the per-tier PDP (ADR-0029 §"Per-tier PDP",
2026-09-05): each tier's PEP decides against its own Topaz and its own copy of
the entitlements corpus, so a severed tier still **decides** and **enforces**.
ADR-0029 closes that section with the sentence this draft exists to change:

> *decides locally, enforces locally, and cannot log anybody new in.*

ADR-0029 also said per-tier identity "rides the same seam as per-tier Topaz — a
Keycloak replica or a local IdP" and should be designed with it. This draft takes
the replica branch and says why, and it leaves several things open on purpose
(§"Open, and why it is open").

---

## Context — what is true today (read from the chart 2026-09-29)

* **One Keycloak, at the root.** `releasability.keycloak` in
  `openddil-helm/openddil-demo/values.yaml` (~1245): start-dev, in-memory H2,
  published passwords, no TLS, and a comment that it is **disqualifying anywhere
  but a lab**. A real deployment points `releasability.oidc` at the identity
  provider it already runs.
* **Every tier PEP names the root's issuer.** `templates/tier-node.yaml` (~899):
  `OPENDDIL_OIDC_ISSUER` is `openddil.keycloakIssuer` of the root, and the
  internal issuer is the root's `-keycloak` Service. Each tier has its **own
  confidential client** and its own exact redirect URI (chart delta item 4 of
  `PLAN-tier-presentation-opening-package.md`), so the client split is already
  done; only the issuer is shared.
* **What survives severance today** (ADR-0029 §Authentication): existing sessions,
  because the PEP holds a local session table and a JWKS cache that refreshes only
  on an unknown key id. **What does not**: a new sign-in, because the code
  exchange is a live call to the root's token endpoint.
* **Every upgrade signs everyone out, severed or not.** Measured 2026-09-29,
  revision 56 → 57 (FOLLOW-UPS, "the identity pods roll on every helm upgrade"):
  Keycloak and the PEPs carry the release revision as a pod annotation, Keycloak
  holds its state in in-memory H2, and the PEP holds sessions in memory. A tier
  replica built the same way would multiply that cost by the number of tiers.

**The gap in one sentence:** an operator who arrives at a severed edge after the
link went down cannot use the edge's UI at all, though the edge holds the data,
the policy, and the decision point to serve them.

---

## Decision (draft)

### 1. Each tier runs its own issuer, with its own signing keys

A tier's replica is a **separate issuer** (`<tier public origin>/idp/realms/<realm>`)
with **keys generated at the tier**, and the tier's PEP trusts only its own issuer.
No private signing key is distributed anywhere.

Why a separate issuer rather than a replica of the root's: the browser holds no
token (ADR-0029, backend-for-frontend), so a token never needs to be accepted by a
tier other than the one that minted it. Sharing keys would buy cross-tier token
acceptance that nothing uses, at the price of putting the root's signing key on
every edge. A key compromised at an edge then compromises one edge.

The PEP already validates `iss` and `aud` exactly (ADR-0029's table of what
`verify_aud: False` and a missing `issuer=` would admit). A tier PEP pointed at its
own issuer rejects a root-minted token by that same check. That is the property to
test first (§Predictions).

### 2. The replica carries authentication only; authorization stays in the corpus

ADR-0029: *Keycloak answers who is this; Topaz answers what may they see*, and
entitlements are git-asserted in the corpus, not held as Keycloak groups. That is
what makes a replica safe to run stale: **a replica that is out of date can admit a
person, but it cannot widen what they see**, because what they see is decided by
the tier's Topaz against the corpus the tier already holds.

So the replica's content is: the realm, the users, their credentials, and the
tier's own client. Nothing in it is an entitlement.

### 3. The realm reaches a tier the way the corpus does: in the runtime bundle

The realm import is distributed as a versioned artefact in the runtime bundle,
beside the policy and the corpus, pulled at pod start (ADR-0029 §6's model). A
severed link stops realm **updates**, not sign-ins. Each tier's replica imports
the realm on start, with the tier's own client and redirect URI substituted.

The import is keyed by content: the replica rolls when the realm artefact's digest
changes and **not** on the release revision (the FOLLOW-UPS row above). Without
that, this ADR turns one sign-out per upgrade into one per tier per upgrade.

### 4. Revocation is bounded by the link, and that is stated, not hidden

A person disabled at the root can still sign in at a tier that has not received
the updated realm: severed, or not yet restarted. The bound is **the age of the
tier's realm artefact**, and it is shown to the operator, as policy and corpus
versions already are (every PEP decision records them).

This is the same property the corpus already has: an entitlement removed at the
root is still honoured by a severed tier's Topaz until the bundle arrives. The
draft does not introduce stale identity; it makes stale identity the same shape as
stale policy, with one version stamp to read for both.

---

## What a deployment with a real identity provider does

Nothing in §1–§4 requires Keycloak. A deployment that already runs an identity
provider brings its own answer to "can a tier authenticate while severed". The
likely answers are a replica or broker of that provider at the tier, or
certificate-based sign-in validated locally against a CA bundle and a cached
revocation list. **The chart's contract is the PEP's issuer URL per tier**, which
exists today. This ADR decides only what the **bundled demo** identity provider
does, and that the per-tier issuer is a supported shape.

---

## Open, and why it is open

* **Credentials at the edge.** A replica holding password hashes puts them on every
  tier. For the demo realm (published passwords) that costs nothing; for a real
  realm it is the whole question, and the answer depends on the deployment's
  authenticator. **Not decided here.** Certificate sign-in is the obvious
  candidate and is named, not chosen.
* **Keycloak at every edge, or at regional tiers only.** Keycloak was OOMKilled at
  1Gi and 2Gi before the heap cap (values.yaml ~1262). An edge with one Keycloak per
  tier pays roughly 768Mi requested each. Whether edges run a replica or sign in
  through their region is a sizing decision to make from a measured footprint.
  **The footprint has not been measured.**
* **Persistent state.** An import-on-start replica on in-memory H2 loses its user
  sessions on restart. The PEP's own session table is also in memory. Whether both
  move to durable storage is a separate decision, and it touches ADR-0029's
  "multi-replica PEP needs shared shape-handle storage".
* **The pinned user ids.** ADR-0029 pins demo user ids so that the same person is
  the same subject across re-imports. Across per-tier issuers the pairing is
  `(iss, sub)`, so the same person is a different subject at each tier. The corpus
  is keyed on what, exactly, needs reading before this is accepted. **Unread.**
* **The audit trail's subject.** Once the issuer differs per tier, an audit record
  must carry the issuer beside the subject, or two tiers' records for one person
  cannot be joined. Whether the gateway record already does is **unread**.

---

## Predictions, to be measured before this is accepted

On the lab, with one tier (edge-01) given a replica and the others unchanged:

| reading | predicted |
|---|---|
| four-profile scripted sign-in at the edge-01 host, link up | 4 / 4 sessions |
| same, with edge-01's uplink severed | **4 / 4** (today: 0 / 4) |
| same, at the root host, edge-01 severed | 4 / 4 (unaffected) |
| a root-minted token presented to edge-01's PEP | **refused** on `iss` |
| a user disabled at the root, edge-01 severed, signing in at edge-01 | **admitted**, with the realm version shown as older than the root's |
| pods rolled by an upgrade that changes neither the realm nor the PEP | **0** identity pods (today: 6) |

The fifth row is the one to watch. It is the designed behaviour, and it is also
the one a reviewer should be able to object to before any code exists.

## What this does not decide

* A production identity provider, its authenticators, or its federation.
* Any change to how Topaz decides, or to the corpus.
* Whether the egress path (ADR-0043) needs a tier-local identity. Egress subjects
  are system principals, not people, and are out of scope.
