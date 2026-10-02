# DESIGN 2026-10-01 — Contract A to Cursor on Target: the first thin connector

**Status:** built and measured in the demo stack, then deployed with chart 0.1.70 (`egress.tak.enabled`) and
measured on a cluster: the TAK server's picture holds 8 uids, exactly the 8 admitted records, and 0 for the refused
ones. A reader pod without the readers-only label cannot connect. The adapter logged 0 skips and 0 fatals. The
bundled TAK server has no web UI, so nothing is routed behind the PEP for it; the picture is read over the CoT stream.
**Builds on:** DESIGN-2026-09-06-interface-contracts.md §1 (the thin egress connector), ADR-0043
(the C2 egress gate), ADR-0029 (labels as authorship claims), ADR-0044 (lifecycle columns).

## What was built

`openddil-demo/egress/cot_adapter.py` reads the ADR-0043 gate's **sink** topic (`egress-c2-status`)
and writes one Cursor on Target event per record over TCP to a TAK server. In compose, the stand-in
C2 is `tak-server` (taky, an open-source CoT server). Both services are compose scaffolding under
ledger row LR-0043-C, like `egress-gate-c2`.

There is one connector, and it consumes only the gate's sink. This is how the connector stays within
the two rules interface-contracts §1 sets for it:

1. **It translates; it does not decide.** Releasability is decided once, by the gate, before the
   record reaches the sink. The adapter never consults `releasable_to` against the destination. It
   carries the labels it is given.

   The adapter has one fence: a record with no label produces no event (`COT_SKIP`), and nothing
   else happens. The fence is not a second authorization point. The gate already refuses unlabelled
   records, so the fence is only reachable if someone points the adapter at the wrong topic.
   Translating a record without a label would turn "no label" into "no restriction" in the C2.
   ADR-0029 §1 forbids that inference anywhere.
2. **It is per-consumer and disposable.** Its configuration names one TAK endpoint and one consumer
   group. A second CoT consumer gets a second gate destination and a second adapter, not a fan-out
   inside this one.

## What the event carries

```xml
<event version="2.0" uid="{asset_id}" type="a-u-G" how="m-f"
       time="…" start="…" stale="time + 300s">
  <point lat="0.0" lon="0.0" hae="9999999.0" ce="9999999.0" le="9999999.0"/>
  <detail>
    <contact callsign="{asset_id}"/>
    <openddil_release originator_nation="ATL">
      <releasable_to nation="BDR"/>            <!-- one child per entry; zero children is meaningful -->
    </openddil_release>
    <openddil_status asset_id="…" platform_variant="…" overall_severity="…"
                     computed_at="…" status_revision="…"/>
  </detail>
</event>
```

Each field below lists where its value comes from, and whether that value is a claim, a convention
or a default:

| CoT field | value | source | kind |
|---|---|---|---|
| `uid` | asset id | Kafka key, else `status.asset_id` | claim (identity, carried) |
| `type` | `a-u-G` (configurable) | adapter default | **default.** Contract A carries no affiliation or dimension; "unknown, ground" is the honest value |
| `how` | `m-f` | adapter default | **default.** It marks the event as machine-produced, by fusion. It is not a measurement statement |
| `point` | 0,0 with 9999999 hae/ce/le | adapter | **convention.** Contract A carries no position, so the CoT "unknown point" error values are used. The C2 must not plot this as a location |
| `time`/`start`/`stale` | send time; +300 s | adapter clock | **local.** Stale is a connector parameter, not a freshness claim from upstream |
| `detail/contact@callsign` | asset id | as `uid` | display convenience |
| `detail/openddil_release@originator_nation` | the record's label | `provenance.originator_nation` | **claim** (ADR-0029: authorship, carried unchanged) |
| `detail/openddil_release/releasable_to@nation` | each entry, in record order | `provenance.releasable_to` | **claim**, carried unchanged; an empty list is an element with no children, never an omission |
| `detail/openddil_status@*` | severity, variant, computed_at, revision | Contract A `status.*` | **claim**, carried unchanged |

The label is carried in its own detail element, not in a standard CoT element. This is deliberate.
CoT's base schema has no releasability element, and the open marking vocabularies (below) are not
CoT. Inventing a CoT-looking element would make the label look standard when it is not. A TAK server
or client that does not understand `openddil_release` keeps it in the detail block and ignores it.
That is the extension mechanism CoT's `detail` exists for.

## Alignment declared (ADR-0038 C1 intake)

Each concept is listed with the rung it actually stands on.

| concept on the wire | aligned to | rung |
|---|---|---|
| `releasable_to` (nation list) | IC ISM `releasableTo`: the countries or organisations to which information may be released, per the originator's determination | **verified citation** (CITATIONS-2026-09-08, IC ISM attribute semantics). The ISM.XML DES version is not verified |
| `originator_nation` | IC ISM `ownerProducer` (trigraph of the owner/producer) | **verified citation for the IC ISM concept.** Our field is narrower: one nation, the authoring claim (ADR-0029), not a list |
| the `originator_nation` / `releasable_to` pair | STANAG 4774/4778 confidentiality-label concepts | **declared intent**, inherited unchanged from Slice 1 (ADR-0043 §Alignment). Not re-verified here |
| nation codes | ISO 3166-1 alpha-3 | as Slice 1. The demo fleet's `ATL` / `BDR` are fictional codes in that shape |
| `uid` = asset | JC3IEDM object-item identity | **declared intent only** |
| `overall_severity` | JC3IEDM object-item operational status | **declared intent only.** Severity is a readiness projection, which is not the same thing as JC3IEDM's operational status. The ADR-0044 operational-status column is the closer match, and Contract A does not carry it yet (see below) |
| `computed_at` | JC3IEDM reporting-data timing (the "as of" of a report) | **declared intent only** |
| `openddil_release`, `openddil_status` element names; `status_revision` | nothing published | **OpenDDIL-local** |
| `type`, `how`, `point`, `stale` | CoT base event schema | **not in CITATIONS.** These are written from the CoT event schema as commonly published. The values `a-u-G`, `m-f` and the 9999999 unknown-point convention must be checked against a fetched schema before this connector serves a real C2 |

**JC3IEDM attribute names and code values are deliberately not stated.** CITATIONS-2026-09-08 lists
JC3IEDM / MIP as *not fetched*. Writing attribute names here would produce the artefact this corpus
keeps catching: something that reads like a standards citation but is a reconstruction. The
alignment is declared at the model level only, the same rung ADR-0044 uses. Binding a CoT detail
attribute to a named JC3IEDM attribute is still owed, and it is a precondition for freezing any of
the `openddil_*` attribute names.

## What Contract A does not give the connector

These are gaps in Contract A, not in the connector. They should be fixed there and not worked around
here (interface-contracts §1: connectors that accumulate logic are a finding about the contract).

- **Position.** Without one, every event is an unknown-point event. A C2 that drops unplaced events
  shows nothing.
- **Affiliation and dimension.** Without them, `type` is always the configured default.
- **Operational status (ADR-0044).** A destroyed asset currently reaches CoT only as its severity.
  The ADR-0044 column belongs in Contract A before CoT gets a `destroyed` rendering. The connector
  must not derive one.

## Measured

The prediction was written as literals in the test before the bridge ran
(`tests/hero_scenario_v3/test_51_egress_cot_counts.py`):
- 8 CoT events, one per admitted asset;
- 0 events for the 6 assets the gate refuses for `no_nation_overlap`;
- 0 events for the 2 red-check records.

There were also two cross-checks. The uid set at the TAK server must equal the set the gate logged as
`admit` in the same run; these are two independent observations of one decision. Every event's
`openddil_release` must equal the declaration in `ontology/releasability.yaml`.

Records are isolated per run by a `status_revision` nonce, because the compacted sink also holds
earlier records for the same asset ids.

| run | predicted | measured |
|---|---|---|
| unit tests (event builder) | pass | 13 passed |
| test_51, green | 8 / 0 / 0, uid set = gate admit set, 8/8 labels | **PASS**, every line |
| test_51, adapter pointed at the gate's **source** topic (red check) | FAIL, 14 or more uids | **FAIL**: 15 uids. That is all 8 admitted, all 6 refused, and the classified red-check record; uid set ≠ admit set |
| test_51, green again | as the first green run | **PASS** |
| test_50 (the gate itself), after | unchanged: 8/14 admitted, 6 `no_nation_overlap` | unchanged |

The red check shows the connector's only safeguard is the topic it reads. Read before the gate, the
adapter carries every labelled record, including one the gate refuses for classification, because its
fence rejects only records that carry no label. That is the intended division of labour (it
translates, it does not decide). It also means the source-topic setting is the one configuration line
a reviewer of this connector must read.

Three findings from building it:

- **The TAK stand-in does not separate audiences.** taky 0.10 adds every socket to its broadcast set
  on accept, before the client identifies itself (`taky/cot/router.py`, `COTRouter.broadcast`). Every
  connected client receives every event. So releasability ends at the gate destination: **one gate
  destination feeds one TAK server (or one channel that is restricted to one audience)**. A TAK
  server shared across nations, or one that federates onward, would re-release what the gate
  admitted to whoever is connected. This is a property of the C2 side, and the connector cannot
  repair it. It belongs in the deployment conditions of any real CoT consumer.
- **Importing the gate's `main.py` configures logging at module scope.** The adapter reuses `decode`
  from it and has to override that configuration (`basicConfig(force=True)`). It works, but it couples
  the two. If a second connector needs `decode`, moving `decode` into a module with no side effects is
  the right fix.
- **The first version of test_51 wrote phantom rows.** It put the nonce in `status.asset_id` as well
  as in `status_revision`. The HQ projector keys `asset_logistics_status` by `status.asset_id`, so
  each run created one row for a non-existent asset. The test was fixed (only `status_revision` carries
  the nonce), the re-run passed with no new row, and the 3 rows were removed from the compose store.
