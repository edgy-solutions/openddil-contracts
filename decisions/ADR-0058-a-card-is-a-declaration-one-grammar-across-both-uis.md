# ADR-0058 — A card is a declaration: one grammar across cortex-ui and the OpenDDIL UI

## Status

**PROPOSED — 2026-11-08. Design only. Nothing here is built, nothing is deployed, and nothing has been measured.**
- Drafted on Chris's order of 2026-11-08 from the brief of 2026-11-06 ("cards as declarations"). The brief was
  addressed to the UI owner. This record proposes answers. The four questions it put stay the UI owner's until they
  are answered there (see Questions).
- The number is provisional until the record is accepted.
- The findings were read from the code on 2026-11-08: the OpenDDIL frontend and PEP at their working trees, cortex-ui
  at `08fa897`, and the chart's realm helper. They are reads, not runs.

## Findings first

1. **The frontend has three pages and no router.** `TierApp.tsx:57-65` picks the Maintainer, Regional or HQ page by
   tier shape. A second entry, `sources-main.tsx`, builds the sources pane alone.
2. **Every card reads one of two ways.** An Electric shape, through `useTableShape` (`hooks/electric.ts:88`) or
   `useShape` directly (`Inventory.tsx:112`). Or a PEP JSON route, by `fetch`.
3. **"PEP-filtered" holds only with enforcement on.** nginx proxies `/electric/` to the PEP when enforcement is on, and
   to Electric directly when it is off (`frontend/nginx.conf:288-302`). Nothing in the frontend checks which.
4. **Some drawn fields come from no filtered read at all.**
   - `deployment.json`, a static file fetched at start (`deployment.ts:1138`). It supplies the declared munitions
     load (`MunitionsLoadoutCard`, `MunitionsInventory`), the move standards (`MovePanel.tsx:203`), the edge
     attachment (`EdgeAttribution`), and the cortex link base (`CortexApprovalLink`).
   - `/figures/...`, served by nginx as static files (`FigureView.tsx:59`, `nginx.conf:198`).
   - The client clock: contact tiers (`hooks/useFleetTiers.ts:71`) and the overdue chip (`ArrivalsPanel.tsx:213`).
   - Local state only: `TacticalRuleBuilder` (`DEMO_MOCK = true`, `:13`).
5. **The UI computes values in eight places.**

   | Where | What it computes | Kind |
   | --- | --- | --- |
   | `LogisticsStatusCard` via `lib/opStateBackfill.ts:36` | a severity marked "(inferred)" from health and power state, when fusion's is absent | inference |
   | `TheaterReadinessPosture.tsx:209-249` | severity mapped to ready, degraded, offline or unknown, then counted per class | label map and count |
   | `lib/munitionsLedger.ts:108-136` | loaded and remaining rounds, from the static declared load plus launch and resupply rows | arithmetic across sources |
   | `HqApp.tsx:151` (`sumFleetBuckets`) | bucket counts summed across regions | sum of a server aggregate |
   | `lib/fleetAggregates.ts:121` with thresholds 0.9 and 0.5 at `HqApp.tsx:248` | a compliance rate and its colour | arithmetic and a threshold in code |
   | `WeaponsCapabilityCard.tsx:28-29`, `:61-67` | LOW and DEPLETED colours against defaults of 5 and 0 | a threshold in code |
   | `RegionalHeader.tsx:115` (`worstTone`) | the worst of the link tones | rollup |
   | `hooks/useFleetTiers.ts:71` | ACTIVE to LOST from sample age | clock |

6. **The sources pane is the one card built to have no combined value.** It reads the PEP route `/cm/sources`
   (`pep.py:2186`). The bands are computed in the PEP (`_source_band`, `:1394`). The UI computes only the three pair
   marks: agree, bands differ, no band (`SourcesPane.tsx:12`). The rule "nothing reduces the three marks or the three
   bands to one value" is a code comment (`:5-6`). It is not rendered, and no test holds it.
7. **The PEP has no OpenAPI.** It is a stdlib `http.server`. Routes are `if` branches on the path: `do_GET` at
   `pep.py:4047-4081` (11 paths and a shape prefix) and `do_POST` at `:3550-3568` (6). A search of the demo and
   contracts repos finds no OpenAPI document. The frontend holds hand-written types for nine routes, in `lib/` and
   `hooks/`. `lib/sources.ts:4` says it must "mirror pep.py `_handle_cm_sources` exactly". Nothing checks that it does.
8. **cortex's schema is a document, not yet a published contract.** `docs/specs/card-declaration.schema.json` at
   cortex-ui `08fa897`:
   - Its description says "This is a DOCUMENT, not code: nothing in cortex-ui loads or enforces this file."
   - Its `$id` is a GitHub blob URL. It has no version keyword. Its only version is `x-cortex-provenance`, a commit
     pin.
   - Its census says 29 contracts and 10 archetype packages. A count at HEAD finds 30 and 11. The count was a grep and
     was not run through cortex's tests.
   - It is closed: `additionalProperties: false` on the root and every definition. There is no `sources` array and no
     extension point. An unknown contract key is refused.
   - It requires no status, severity or score. A card under it is never forced to carry a combined value.
9. **cortex renders the task shapes.** `SemanticInterpreter.tsx:224` switches on the archetype. `APPROVAL_TASK`
   (`:313`), `TRIAGE_TASK` (`:318`) and `WORKFLOW_CASE` (`:567`) are among about 38 cases. A `SOURCE_LEDGER` case
   exists (`:467`). Its contract was not read for this record.
10. **The realm version is coarse.** `openddil.realmVersion` (`_helpers.tpl:979-986`) is the first 16 hex of a
    SHA-256 over the bundle image reference and the users overlay. With no bundle digest, the release revision is
    folded in. It moves whenever the realm can have moved, and sometimes when it did not: "a false roll, never a false
    match". The bundle copies the policy as one directory (`bundle/Dockerfile:92`). So no per-file digest exists.
11. **Two components have no mount.** The default export of `ArrivalsPanel.tsx` (`:398`) and `AccessDenied.tsx`.
    `EffectorTracksCard` is mounted on the Regional page only (`AssetDeepDive.tsx:72`).

## Decision

### 1. Declarations ride the bundle, versioned like the realm

- **A card's declaration is a file in the bundle**, beside the policy. The frontend reads the declarations it is
  served, and draws only declared cards.
- **Each declaration carries the realm version it was served under** (finding 10). A card whose declaration's version
  differs from the deployment's `openddil.io/realm-version` is not drawn. It shows a named absence: "declaration from
  another realm version".
- **The coarse version is accepted for now (proposed answer to question 1).** It gives a false roll, never a false
  match. A false roll costs a reload. A false match would draw a card under a declaration that no longer holds. The
  per-file digest stays the follow-up, and the declarations move to it when it exists.

### 2. The two constraints

#### 2a. Every drawn field comes from a declared read

- **A declaration names its reads.** Each read is either a shape (table and where clause) or a PEP route. Each field
  names the read it comes from.
- **The card declares its read, never the filter.** The filter is the PEP's (`policy_predicate`, `pep.py:1462`;
  `egress_view.py:71`). The card does not repeat it. When ADR-0055's `label_key` lands, the PEP's filter changes and no
  declaration does.
- **A read outside the PEP is declared as such, with a reason.** That covers `deployment.json`, a static figure and the
  clock (finding 4).
  - **It is refused for any field about an asset.** The declared munitions load is the case today: it is asset data,
    read from a static file, beside filtered rows. Under this record that field is owed to a filtered read before its
    card can be declared.
  - Configuration that names no asset, such as a link base or a standard, may stay static. It is declared with its
    reason.
- **A withheld input is a declared absence.** A card draws "withheld" where the PEP withholds. It never draws an empty
  value that could be read as zero. `egress_view.py:109-118` already counts withholds for the egress pane.
- **The filter holds only under enforcement (finding 3).** A declaration cannot make an unenforced read filtered. That
  is a deployment fact, and the check for it is owed (§7).

#### 2b. Rows with more than one provenance, and no computable rollup

- **A card with several sources declares each as its own cell.** The grammar has no field for a combined value of
  sources with different provenance.
- **A relation between cells is not a value.** The sources pane's pair marks (agree, bands differ, no band) say how two
  cells relate. They are declared as relations, and nothing reduces them.
- **The sources pane is the test case.** The grammar passes only if the sources pane can be written in it with no
  combined field (Check 3).
- **What a card may compute.** Allowed, when declared: a label map from a stored value, a sort, a count of the rows the
  viewer can see, and time formatting. Refused: inference, arithmetic across sources, and a threshold written in code.
  Applied to finding 5:
  - **Allowed:** the readiness label map and count; the bucket sum, since it sums one server aggregate; the worst link
    tone, as a declared ordering of one field.
  - **Refused, owed upstream:** the inferred severity (an unstamped finding made in the UI); the munitions ledger
    (arithmetic across a filtered and a static source); the compliance colours and the ammunition threshold, until
    the thresholds are declared in the bundle rather than written in code.
  - **The clock tiers** are a declared read of the clock. Their thresholds are declared like any other.

### 3. Shape ownership is split

- **cortex owns task and approval:** `APPROVAL_TASK`, `TRIAGE_TASK` and `WORKFLOW_CASE` (finding 9).
- **OpenDDIL owns record, finding and indicator.**
  - A **record** draws one stored row's fields, with no judgment of its own.
  - A **finding** draws a judgment about a thing, with its producer and time.
  - An **indicator** draws one current state, with its time.
- **The owner writes the declaration.** The other UI may render it, but never redefines it.
- **The proposed mapping (answer to question 2):**

  | Panel | Shape | Note |
  | --- | --- | --- |
  | `CmStateCard` | record | the label map is allowed |
  | `WeaponsCapabilityCard` | record | its threshold is owed to the bundle |
  | `EffectorTracksCard` | record | Regional page only |
  | `Inventory` | record | |
  | `AlertFeed` | record | |
  | `LogisticsStatusCard` | finding | fusion's severity, DERIVED; the inferred fallback is refused |
  | `BitDiscrepancyCard` | finding | |
  | `PostureCard` | indicator | |
  | `GroundDiagnosticsCard` | indicator | three axes, three indicators, never one |
  | `LostContactBanner` | indicator | a declared clock read |
  | `SourcesPane` | finding, several sources | the test case (§2b) |
  | `MunitionsLoadoutCard`, `MunitionsInventory` | not declarable yet | the ledger and the static load (§2a, §2b) |
  | `TheaterReadinessPosture`, `RegionFleetSummary`, `HqApp` fleet and configuration panels | indicator over a count | label map and count only |
  | `CortexApprovalLink` | not a shape | a link to a cortex case |

  The 3D scenes (`RegionalSustainmentPosture`, `HqDigitalTwin`, `DiagnosticCanvas`) were read by summary only and are
  not mapped here.

### 4. A typed client from a written OpenAPI, with a drift seal

- **The PEP has no OpenAPI today (finding 7). Writing one is the prerequisite row for this section.**
- **The document is written, not generated.** Nothing in the PEP can emit it. It covers the PEP's JSON routes. Shapes
  are typed from the store's schema, separately.
- **The client is generated from the document.** The nine hand-written type files are replaced by it, one route at a
  time.
- **The seal.** It follows iagent's pattern (`docs/api/ingest-v1.shapes.lock`): one `<version> <sha256>` row per API
  version, append-only, written by a script.
- **A seal counts only when a named workflow runs it,** as `decision-indexes.yml` does for the decision index. It
  checks two things:
  - the PEP's dispatched paths, read from `do_GET` and `do_POST`, against the document's paths;
  - the generated client against the committed one.

### 5. The shared grammar is a profile of cortex's card schema

- **The profile is cortex's schema cut to the shapes the two UIs render today.** It pins one version of the schema. It
  restricts `archetype` to the shared set. It adds nothing the schema does not allow.
- **Publishing the schema comes first (finding 8).** That means a versioned `$id`, a release, and a census that a test
  keeps true. A profile cannot pin a document that moves without a version.
- **The cut is the union** of cortex's task and approval shapes and OpenDDIL's panels in §3. OpenDDIL's panels have no
  declarations yet, so they are written as part of the profile. Each is declared under an existing cortex archetype
  where one fits. A panel with no fitting archetype stays outside the profile until cortex adds one.
- **The sources pane needs an extension point the schema does not have (finding 8; answer to question 4, as far as the
  code goes).** The schema is closed and has no `sources` array. Either cortex adds a way to declare several sources
  with no combined value, or the profile stops at the sources pane. `SOURCE_LEDGER` may already be that shape. Its
  contract is the first thing to read.

### 6. What this record does not change

- How the PEP filters.
- Any cortex-ui file.
- Any card's behaviour, until its declaration exists.

### 7. Owed rows (not built)

- The PEP's OpenAPI, the generated client and the seal workflow (§4).
- cortex's schema published with a versioned `$id` and a census test (§5). That one is cortex's.
- The per-file realm digest (§1).
- The declared munitions load moved to a filtered read, and the ledger computed upstream with a producer stamp
  (§2a, §2b).
- The inferred severity moved to a producer, or removed (§2b).
- The two thresholds declared in the bundle (§2b).
- A deployment check that declared cards are served under enforcement (§2a).
- The two unmounted components removed (finding 11). That is housekeeping, not part of the grammar.

## Check

Each check is a test or a script that a named workflow runs. A check that nothing runs does not count.

1. **Every drawn card is declared.** The set of mounted card components equals the set of declarations, less the
   cards listed as not declarable, each with its reason.
2. **No field without a declared read.** Every declared field names a read, and every read is a shape, a PEP route, or
   a declared static source with a reason. No static source supplies a field about an asset.
3. **The sources pane has no combined field.** Its declaration validates against the profile, and the profile has no
   field that holds a value combined across its cells. If it cannot be written, the check reports that the profile
   stops at the sources pane, and fails until that is ruled.
4. **Paths match.** The PEP's dispatched paths equal the OpenAPI document's paths.
5. **The client matches.** The generated client equals the committed one, and the lock's last row matches the
   document's hash.
6. **The profile pins a published version.** Every declaration validates against the pinned version of cortex's schema.
7. **The realm version gates drawing.** A declaration served under another realm version is not drawn, and its absence
   is named.

## Questions

The brief put four questions to the UI owner. This record proposes an answer to each. None is ruled.

1. **Coarse realm version or per-file digest?** Proposed: coarse now, per-file when it exists (§1).
2. **Which panel is a record, a finding or an indicator?** Proposed: the table in §3.
3. **Can cortex's schema be published with a versioned `$id` first, and who keeps its census true?** Proposed: yes,
   and cortex-ui owns the census test. It is cortex's to decide.
4. **Does the schema have an extension point for several sources with no combined value?** It has none today (finding
   8). Whether to add one, or to stop the profile at the sources pane, is cortex's.

## What this does not establish

- Nothing is built: no declaration, no profile, no OpenAPI, no client and no seal.
- The census counts in finding 8 are greps, not test runs.
- The 3D scenes were read by summary only.
- It decides nothing for cortex-ui.

## Related

- [ADR-0055](ADR-0055-a-label-is-a-set-of-declared-dimensions.md): the label key a declaration never repeats (§2a).
- [ADR-0056](ADR-0056-one-identity-per-thing-every-other-id-is-an-alias.md): one identity per thing, which a card
  names by its `asset_id` alias.
- cortex-ui `docs/specs/card-declaration.schema.json` at `08fa897`: the schema the profile cuts.
- iagent `docs/api/ingest-v1.shapes.lock`: the seal's pattern.
