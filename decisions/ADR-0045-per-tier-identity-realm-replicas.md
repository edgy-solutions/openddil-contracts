# ADR-0045: A severed tier can sign people in — its own realm at each tier, trust between tiers

## Status

**ACCEPTED (v2) — approved 2026-10-29.** This replaces PROPOSED (2026-10-08) in §2, the
login test, the next increment, the predictions and §"Still open". It adds a
paragraph to §4, a new §6 and a lab2 section. §1, §3 and §5 stand. Decided at
approval: a person's home tier follows the system of record's assignment (§2). Design only: nothing here is
built, and nothing is deployed. Draft 2026-09-29.

v1 put a full realm replica at each tier, with every user and every credential.
**v2 keeps a realm at each tier and adds trust between tiers.** Each tier's realm
holds every person with their pinned id. It holds credentials only for the people
whose home is that tier. Everyone else signs in through the tier's parent, which
the tier trusts as a brokered identity provider. §"Findings first (v2)" says why
the shape changed, and why it did not become trust alone. The file name keeps
v1's words so that links to it hold.
In §1, §3 and §5, which stand, "replica" now means a tier's own Keycloak importing
the realm artefact. It holds credentials only for its home people (§2).

This is identity rung 2. Rung 1 was the per-tier PDP (ADR-0029 §"Per-tier PDP",
2026-09-05): each tier's PEP decides against its own Topaz and its own copy of
the entitlements corpus, so a severed tier still **decides** and **enforces**.
ADR-0029 closes that section with the sentence this ADR exists to change:

> *decides locally, enforces locally, and cannot log anybody new in.*

ADR-0029 also said per-tier identity "rides the same seam as per-tier Topaz — a
Keycloak replica or a local IdP" and should be designed with it. This ADR takes
the replica branch and says why. What it still leaves open is listed with the
reason (§"Still open").

What changed between the draft and v1: the questions the draft marked
**unread** have been read (how a person is keyed, what the decision record
carries), the root Keycloak footprint has been measured, and the claim that every
upgrade rolls the identity pods has been corrected against two measured upgrades.

---

## Findings first (v2) — what the brokering work taught (read 2026-10-29)

"The broker work" is read here as the October identity brokering for the agent
integration. In that work, iagent's Keycloak brokers OpenDDIL's realm as an OIDC
identity provider, and OpenDDIL declares the agent's client in the chart
(`openddil:openddil-helm` 0.1.108, `releasability.keycloak.externalClients`). If
the message-broker work was meant instead, this section is the wrong input, and v2
should be re-read against it.

1. **Trust between tiers alone fails this ADR's one requirement.** In brokering,
   the tier sends the person to the trusted issuer to authenticate. It then redeems
   the code at that issuer's token endpoint. Both steps need the upstream at
   sign-in time. A tier that only trusts its parent can sign nobody in while
   severed, which is today's 0 / 4. So "trust rather than replicas" is not the
   better shape on its own. A local credential is what survives the cut. Trust
   adds reach while the link is up.
2. **The relying party trusts one issuer, and the identity provider joins the
   sources.** iagent's backend trusts one issuer only. A second identity source
   therefore had to become a second brokered alias at their Keycloak, not a second
   trusted issuer at their backend. OpenDDIL's PEP has the same single-issuer
   check (§1). v2 keeps it: trust between tiers is configured in each tier's
   Keycloak, and no PEP ever accepts a second issuer.
3. **Anything Keycloak holds that is not in an artefact is lost.** The bundled
   Keycloak runs in-memory H2 on an emptyDir and imports on start. A client added
   by hand vanished at the next restart. That is why the agent's client became a
   declared chart value, validated at render (`openddil.externalClientsValidate`).
   A tier's identity-provider alias, and the parent's client for each child, must
   be declared the same way, or the first restart removes them.
4. **A brokered person gets a new `sub` unless they are linked.** By default,
   Keycloak's first-broker-login creates a local user with a generated id for a
   person who arrives through a brokered provider. The corpus is keyed on `sub`, so
   that person would be admitted by Keycloak and denied by Topaz. That is the
   same failure §2 refuses for unpinned ids. One of the agent integration's open
   confirmations asks exactly which `sub` lands as the person of record. It is not
   answered yet. v2 links the arriving person to the local user who already holds
   the pinned id (§6).
5. **Nothing on our side has reproduced a brokered sign-in.** Neither lab has a
   brokered identity provider configured today, and the first brokered walk with
   the agent integration is still waiting on the other side. **Every statement
   about brokering in this ADR is a prediction**, and the test below is written so
   that each one can fail.
6. **Credentials everywhere was v1's open cost.** v1 copied every credential to
   every tier (demo realm only) and left the real-realm question open. With trust
   between tiers, an edge needs only its own people's credentials. Everyone else
   is a visitor, whose credential stays at their home tier.

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

### 2. What each tier holds (v2)

The tier's realm carries **authentication only**. ADR-0029: *Keycloak answers who
is this; Topaz answers what may they see*, and entitlements are git-asserted in the
corpus, not held in Keycloak. A realm that is out of date can admit a person; it
cannot widen what they see, because what they see is decided by the tier's Topaz
against the corpus the tier already holds. (Unchanged from v1.)

| content | at each tier? | how |
|---|---|---|
| realm settings (`openddil`, the self-service switches, brute-force policy) | **yes** | the realm artefact, unchanged |
| users, with their **pinned ids** | **yes, all of them** | the realm artefact, unchanged. A visitor is a known user without a local credential, not a stranger |
| user credentials | **only for people homed at this tier**; the root holds all | the realm artefact, filtered at import by each user's `home_tiers` (below) |
| the tier's own confidential client and redirect URI | **yes, this tier's only** | spliced at the tier from the same `openddil.keycloakTierClients` the root uses |
| the tier's trust in its parent: one identity-provider alias | **yes, new in v2** (every tier but the root) | a declared chart value, rendered into the realm at import (§6) |
| at a parent, one client for each child tier | **yes, new in v2** | spliced the same way as the tier clients (§6) |
| other tiers' clients, and the root's `openddil-pep` | **no** | a tier can only mint for its own PEP |
| signing keys | **no** | generated at the tier on first start |
| SSO sessions, brute-force lockout counters, **brokered-identity links** | **no** | tier-local state, never reconciled. A link is rebuilt at the person's next brokered sign-in (§6) |
| admin credentials | **no** | generated per tier into a Secret at the tier |
| entitlements, roles used for decisions | **not in Keycloak at all** | the corpus, already per tier (rung 1) |

**Home tiers (decided at approval, 2026-10-29).** Each user in the artefact
carries `home_tiers`. It follows the system of record's assignment, the ADR-0028
lineage: a person's home is the tier they are assigned to, declared once, so the
entry names that one tier. OpenDDIL never overrides the assignment (ADR-0028). A
person whose assignment moves is one commit to the artefact. A tier's import step
keeps a user's credential only if that tier is the user's home. The root keeps
every credential, so the root is today's Keycloak, unchanged. A user with no
assignment holds a credential at the root only. An unknown tier id in
`home_tiers` refuses the import, with the reason printed. v1's
everyone-everywhere is not offered as a setting: a home that did not follow the
assignment would be a second writer.

**The pinned ids are still what make this cheap.** Every tier imports the same
users with the same ids, so a person has the **same `sub` at every tier**. The
corpus is keyed on `sub`, so it needs no change and no per-tier mapping. The pair
`(iss, sub)` differs per tier, and `sub` alone still names one person everywhere.
v2 leans on this twice: once for the corpus, and once for linking a brokered
person to their local user (§6). It stays an invariant the next increment checks:
**a realm whose users lack pinned ids is refused by the tier's import step**.
Without pinned ids, each tier would mint a different `sub` for the same person,
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

**v2: a visitor's next sign-in is revoked at their home tier.** A visitor signs in
through their home tier, so disabling them there stops their next sign-in at every
linked tier at once, whatever bundle those tiers hold. A visitor who is already
signed in keeps the tier's session until the tier's SSO maximum, because a refresh
at the tier does not call the parent (§6; **a prediction**). A person homed at a
severed tier is bounded by the age of the artefact, as above.

### 5. The bundled demo only; the issuer URL is the contract

Nothing in §1–§4 requires Keycloak. A deployment that already runs an identity
provider brings its own answer to "can a tier authenticate while severed": a
replica or broker of that provider at the tier, or certificate-based sign-in
validated locally against a CA bundle and a cached revocation list. **The chart's
contract is the PEP's issuer URL per tier.** This ADR decides what the bundled
demo identity provider does, and makes a per-tier issuer a supported shape. The
replica carries the root Keycloak's lab-only marking: the same values switch that
says the bundled Keycloak is disqualifying anywhere but a lab covers its replicas.

### 6. Trust between tiers: each tier brokers its parent (new in v2)

* **One alias per tier, pointing up.** Each non-root tier's realm gets one OIDC
  identity provider, alias `parent`. Its issuer is the nearest ancestor tier that
  runs an issuer. Its client is the one that ancestor's realm holds for this
  child. With issuers at every tier, the trust chains: edge-01 trusts region-east,
  and region-east trusts the root. A person homed at the root who signs in at
  edge-01 goes edge-01 → region-east → root and back. Each hop mints its own token
  at its own issuer. No token crosses a tier, and §1 is unchanged.
* **Declared, not clicked.** The alias, its client-secret reference and the
  ancestor's per-child client are chart values, validated at render the way
  `releasability.keycloak.externalClients` is. The render fails on a missing
  issuer, an issuer that is not `https://`, a missing secret reference, or an
  issuer that is not a tier in the tier list. Finding 3 is why. The last rule also
  bounds the auto-link below: a tier trusts only another OpenDDIL tier that
  imports the same artefact.
* **Linking keeps the pinned `sub`.** The alias's first-broker-login flow is set to
  detect the existing local user and link to it with no review page. It is also set
  never to create a user: a person absent from the tier's realm is refused at the
  tier, and the realm keeps its single writer (§3). Keycloak matches an existing
  user by username or email, not by id, so the match key is `preferred_username`.
  To keep the join on `sub`:
  1. an identity-provider mapper stores the parent's `sub` as the user attribute
     `upstream_sub`;
  2. a protocol mapper emits `upstream_sub` in the tier's token;
  3. the tier's PEP refuses a sign-in in which `upstream_sub` is present and
     differs from `sub`, with the reason `identity_link_mismatch` and both values
     in the decision record.

  Every realm carries the same pinned ids, so for a correctly linked person the
  two values are equal. **This is the configuration, not a reading.**
* **What the sign-in page shows.** The local form, for home people, and one
  "sign in through the parent tier" button, for visitors. The scripted sign-in
  (`scripts/oidc_login.py`) gains a brokered path that follows the button.
* **What a cut does.** A tier severed from its parent signs in its home people
  locally. It refuses visitors at the broker step, with the identity provider's
  error page. That is the stated cost of keeping credentials home, not a fault. A
  partial cut (edge-01 linked to region-east, region-east cut from the root) signs
  in edge-01's and region-east's people, and refuses people homed at the root
  only. In the lab, the cut is a NetworkPolicy on the tier's pods
  (`openddil:openddil-helm/scripts/sever-tier.sh`). The browser may therefore
  still reach the parent's sign-in page while the tier's Keycloak cannot reach the
  parent's token endpoint. **Predicted**: the visitor fails after the parent's
  page, at code redemption. In a real DDIL cut, the browser cannot reach the
  parent either. The conntrack caveat in `sever-tier.sh` applies to the tier
  Keycloak's pooled connection to the parent, so the cut proof (test step 3)
  opens a fresh connection from the tier's Keycloak pod.
* **Sessions after sign-in.** A brokered person's session at the tier belongs to
  the tier. A refresh at the tier does not call the parent (Keycloak's default;
  **a prediction**). Cutting the link after a visitor signs in therefore does not
  sign them out. Their session ends at the tier's SSO maximum. This is the same
  interplay between SSO maximum and PEP session already recorded for one tier.
* **One session, partly (roadmap increment 4).** With the link up, take a person
  signed in at an ancestor who then opens a child tier. They pass through the
  child's broker to the ancestor, which already holds their SSO session, and come
  back with no password prompt. That is single sign-on across tiers, which v1 left
  undecided. §6 delivers it at no extra cost, but only for movement down the tree,
  only with the link up, and only while the ancestor's SSO session lives. Moving
  up the tree still means a sign-in at the upper tier. The upper tier holds the
  person's credential (the root holds all), so this is a prompt, not a refusal.

---

## The four-profile login test under a cut (v2)

The acceptance test for the next increment. It reuses the four-profile scripted
sign-in that already gates every deploy (`scripts/oidc_login.py`, one call per
profile, pass = an `openddil_session` cookie after the full code flow), pointed at
a tier's public origin instead of the root's. v2 adds the brokered path.

Profiles: `operator.atlantia`, `operator.borduria`, `operator.regioneast`,
`liaison.coalition`. Control profile: `observer.unlisted`, who is in the realm and
not in the corpus.

**Homes for the run.** In the first increment only edge-01 and the root run an
issuer, so edge-01's alias points at the root. `operator.atlantia`,
`operator.borduria` and `observer.unlisted` are assigned to edge-01, declared as
their assignment in the lab's realm artefact. The other two
profiles hold a credential at the root only: they are edge-01's visitors.

| step | action | pass |
|---|---|---|
| 0 | four-profile sign-in at the **root** origin, link up (the standing pre-cut gate) | 4 / 4 |
| 1 | four-profile sign-in at **edge-01's** origin, link up; record each profile's `role` and `allowed_nations` from its first decision record | 4 / 4: 2 local, 2 brokered. A baseline per profile. For the brokered two, `upstream_sub` equals `sub` |
| 2 | **predict**, then cut edge-01 from its parent (`sever-tier.sh`, `--from-parent`) | policy applied |
| 3 | **prove the cut can fail the test**: from edge-01's PEP pod **and from edge-01's Keycloak pod**, a fresh connect to the root Keycloak Service | refused or timed out from both. If either connects, the cut is not real and the run stops |
| 4 | four-profile sign-in at edge-01's origin, severed | **2 / 4**. The two home profiles sign in, and their `role` and `allowed_nations` equal step 1's: **0 diffs**. The two visitors are refused at the broker step, with no `openddil_session` |
| 5 | `observer.unlisted` at edge-01, severed | signs in; first read **denied** by Topaz. The tier admits; the corpus decides |
| 6 | a root-minted token presented to edge-01's PEP | **refused on `iss`** |
| 7 | four-profile sign-in at the root origin, edge-01 still severed | 4 / 4 (unaffected) |
| 8 | sign in a visitor at edge-01, then cut edge-01 again | the visitor's next read still succeeds: the session is the tier's (§6) |
| 9 | heal. Sign in at the root as `liaison.coalition`, then open edge-01 | edge-01 admits with **no credential form posted** (one session, down the tree) |
| 10 | heal; four-profile sign-in at root and at edge-01 | 4 / 4 each; realm digests: **1** distinct across root and linked tiers |

**The red runs come first.**

* Steps 2–4 against today's chart, with no tier issuer, must read **0 / 4** at
  step 4. If they read anything else, the test cannot tell a tier issuer from
  none, and it is not a test.
* The import step must refuse each of the following, with the reason printed, and
  must not start the tier's Keycloak: a user with a required action, a user with
  no pinned id, and a `home_tiers` entry naming no known tier.
* A link red, on lab2 only, because it needs an altered realm at one tier: a
  brokered sign-in in which the parent's `sub` differs from the local id must be
  refused with `identity_link_mismatch`. If it is admitted, §6's join is not
  enforced.

**The second increment adds the chain.** With a region-east issuer, edge-01's
alias moves to region-east, and `operator.regioneast` is homed there. Two steps are
then added. A partial cut (region-east cut from the root, edge-01 linked) reads
**3 / 4** at edge-01: `liaison.coalition`, homed at the root only, is refused. A
two-hop brokered sign-in for `liaison.coalition` with all links up passes.

The designed-but-objectionable readings, for the reviewer:

* A home user disabled in the artefact, with edge-01 severed before the new bundle
  reached it, **is admitted** at edge-01, and that tier's realm version reads
  older than the root's (§4).
* A visitor who signed in, then was disabled at their home tier, **stays signed
  in** at edge-01 until edge-01's SSO maximum (§4 v2).

---

## The next increment

What the next increment builds, at one tier (edge-01), behind a per-tier value
defaulting to off. Each line is checked by the test above.

1. A tier Keycloak Deployment for a tier with `identity.replica: true`. It uses
   the same Keycloak image and heap cap as the root. It imports the realm from
   the bundle with only that tier's client spliced in, and with credentials
   filtered by `home_tiers`. The admin and account consoles are not routed from
   the tier's public origin.
2. An import step that refuses a realm with unpinned user ids, any required
   action, or an unknown `home_tiers` entry, with the reason printed.
3. The `parent` alias at the tier and the per-child client at the ancestor, as
   declared chart values validated at render (§6). The first-broker-login flow is
   set to detect and auto-link, and never to create a user.
4. The `upstream_sub` mappers, and the PEP's `identity_link_mismatch` refusal.
5. The tier PEP's `OPENDDIL_OIDC_ISSUER` and internal issuer pointed at the tier
   Keycloak when the value is on. Off, the tier is exactly today's: root issuer,
   root client. The root keeps every tier client and every credential, so turning
   the value off is the rollback.
6. `realm_version` and `issuer` in the decision record and on the PEP's status;
   the realm digest as an `extra` input to the tier Keycloak's `policyChecksum`.
7. The drift check (one distinct digest across linked tiers).
8. The brokered path in `scripts/oidc_login.py`.
9. Measure the tier Keycloak's working set under the four-profile sign-in, before
   any decision about every edge running one.

Not in the next increment: issuers at more than one tier (the chain is the second
increment), durable Keycloak storage, any change to Topaz or the corpus.

---

## Still open, and why

* **Credentials at the edge, for a real realm.** v2 narrows this to the tier's own
  people (§2, home tiers), so an edge that is taken costs that edge's
  credentials, not everyone's. It is still a credential at an edge. For a real
  realm, the answer depends on the deployment's authenticator. Certificate
  sign-in is the obvious candidate, and it is named, not chosen. §5 is why this
  does not block the demo.
* **An issuer at every edge, or at regional tiers only.** Root idle footprint is
  572Mi. Three tiers in the lab would add about 1.7Gi working set and 2.3Gi
  requested. v2 adds a reason to choose carefully: an edge without its own issuer
  has no home people, so it is one more tier that cannot sign anyone in while
  severed. Decided from step 9 of the next increment, not from the idle number.
* **Persistent state.** Import-on-start on in-memory H2 makes a restart lossless
  for users and credentials. It loses SSO sessions and brokered-identity links.
  The PEP keeps its own session table, so a restart should not sign anyone out of
  the PEP until that session needs the identity provider again. Links are
  rebuilt automatically at the next brokered sign-in, because linking needs no
  review. **Both are predictions, not readings**, and the next increment measures
  them.
* **Federation across tiers, partly closed.** §6 gives single sign-on down the
  tree while the link is up. Moving up the tree is a fresh sign-in at the upper
  tier. Moving to a severed tier where the person is not homed is a refusal.
  Both are accepted for the demo.
* **Who declares home tiers: decided at approval.** The system of record's
  assignment (§2). Which system of record holds a person's assignment, and how
  it reaches the artefact, is owed by the deployment; the lab declares it in its
  realm artefact by hand.
* **Auto-link trusts the parent's username.** Linking with no review means the
  tier trusts its ancestor to say who a person is. That is acceptable only because
  the ancestor is a declared OpenDDIL tier importing the same artefact, and the
  render refuses any other issuer (§6). Brokering to an issuer outside OpenDDIL is
  out of scope.

## Predictions, to be measured by the next increment

On the lab, with edge-01 given its own issuer and the others unchanged, homes as
in the test:

| reading | predicted |
|---|---|
| four-profile sign-in at edge-01's origin, link up | 4 / 4 (2 local, 2 brokered) |
| brokered sign-ins where `upstream_sub` ≠ `sub` | **0** |
| same four profiles, edge-01 severed from its parent | **2 / 4** (today 0 / 4; v1 predicted 4 / 4: the difference is the visitor cost) |
| where a severed visitor fails | at code redemption, after the parent's page; no `openddil_session` |
| per-profile `role` and `allowed_nations`, home profiles, severed vs link up | 0 diffs |
| `observer.unlisted` at edge-01, severed | signs in, first read denied |
| four-profile sign-in at the root origin, edge-01 severed | 4 / 4 (unaffected) |
| a root-minted token at edge-01's PEP | **refused** on `iss` |
| a home user disabled in the artefact, edge-01 severed before the bundle reached it | **admitted**, realm version older than the root's |
| a visitor signed in, then edge-01 cut | still reads, until edge-01's SSO maximum |
| root sign-in, then edge-01, link up | **0** credential forms posted at edge-01 |
| distinct realm digests, all links up | 1 |
| identity pods rolled by a pinned-bundle upgrade that changes neither realm nor PEP | **0** at the root (measured: revisions 115, 116) and 0 at the tier |
| credentials held by edge-01's realm | **3** (its home people) |
| tier Keycloak working set under the four-profile sign-in | not predicted; measured before sizing |

## Preparing lab2: rung 2 runs on edgy-lab2 first

Rung 2 is built and red-run on edgy-lab2. Nothing in flight there rides on
identity, and the scripted deploy is allowed there. edgy-lab carries live
integration cases and its forwarder route, so it gets a tier issuer only after
lab2 is green, with its own prediction. Before the first lab2 run, these are read,
not assumed:

1. lab2's tier list: whether it runs an edge with a parent, and which.
2. That lab2 enforces NetworkPolicy, using `sever-tier.sh`'s own check. Without
   it, every severed reading is void.
3. The four-profile sign-in at lab2's root origin: 4 / 4, as step 0.
4. The root Keycloak's idle working set on lab2, beside edgy-lab's 572Mi.
5. lab2's chart version against the version carrying the increment. lab2 is
   upgraded to it, with a prediction, before the red run.

Order on lab2: the red run on today's chart (step 4 reads 0 / 4), then the build,
the import reds, the green run, the link red (lab2 only), and the measurement.

## What this does not decide

* A production identity provider, its authenticators, or its federation.
* Any change to how Topaz decides, or to the corpus.
* Whether the egress path (ADR-0043) needs a tier-local identity. Egress subjects
  are system principals, not people, and are out of scope.
