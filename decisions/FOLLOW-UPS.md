# Follow-up index

**Reconciled:** 2026-08-12. **This file is a POINTER, never a source.**
Every row's authority is its home document; if they disagree, the home wins
and this file is the thing that is wrong.

## RESOLVED 2026-09-17 — the derive stage completes, for the first time

Five defects, stacked so each one's fix was blocked by the next, and the whole
stack invisible because every instrument was green. Full operator account in
`openddil-helm/scripts/RUNBOOK-2026-09-17-unwedge.md`.

| # | defect | state |
|---|---|---|
| 1 | Restate OOMKilled at 1Gi (~1600 restarts) | fixed, 2Gi, 0 restarts |
| 2 | zstd on Restate-subscribed topics | fixed, `lz4` applied and confirmed |
| 3 | comment inside a line continuation → whole `topic-init` script unparseable | fixed + guard 4 |
| 4 | release wedged `pending-upgrade` 8h behind the failed hook | cleared |
| 5 | `hook-restate-wipe` covered 1 Restate of 4 | fixed, `wipe_one` over all |

**The measurement that had never once been non-zero** (`check-derive-stage.sh`,
90s window, after the repair):

| tier | asset-cm-state | asset-logistics-status |
|---|---|---|
| edge-01 | +148 | +24 |
| edge-02 | +112 | +18 |
| region-east | +262 | +51 |

Registrations restored: 2 deployments / 7 subscriptions at each edge, 2 / 4 at
region-east. Zero restarts across all four Restates.

### NEW, and only visible because the pipeline now runs

**`tactical_events` produces unlabelled rows.** The table was empty for the
whole period the gate was green, so this branch had never executed against
real data. Two producers, two different wrong behaviours:

* `cm-service` (3 rows): stamps **neither** `originator_nation` nor
  `releasable_to` — the 6 unlabelled values the gate now names;
* `logistics-fusion` (2 rows): stamps `originator_nation` but leaves
  `releasable_to` an **empty array**, which under the ADR-0029 §4 disjunction
  is not a denial but a silent narrowing to the originator alone.

Gate FAILS, correctly, and now names the subjects. **This is the next code
fix.** It is a labelling gap in the producers, not in the gate.

**The gate could not name what it failed on.** It deduplicated by `asset_id`;
`tactical_events` keys on `subject` and the rollups on `region_id`, and an
earlier fix had SKIPPED those tables to stop psql errors printing into the
findings section. Result: `GATE FAILS: 6 unlabelled value(s)` followed by an
empty list. Fixed — key column resolved per table, subjects table-qualified.

And the first version of that fix **accused the three `region_*` rollups**,
because its predicate was a second implementation of the counting rule and
disagreed with it: an aggregate with a NULL originator is *correct*. The
predicate is now derived from the same `is_aggregate()` the counter uses.
*A second implementation of a rule is a second rule.*

### ROOT CAUSE of the OOMs — Restate budgets RocksDB at 100% of the limit

The memory limit was never the variable. Restate reads the cgroup limit, sets
`rocksdb-total-memory-size` to ALL of it, and **prints an ERROR about itself at
every startup**:

    'rocksdb-total-memory-size' parameter is set to 2.0 GiB, more than 90% of
    the process memory limit of 2.0 GiB. This risks an OOM under load; keep it
    under 50% of process memory

At the old 1Gi limit that is a 1 GiB budget inside a 1 GiB cap — not a tuning
problem, an arithmetic one. **That is what drove the ~1600 kills on edge-01 and
1124 on region-east**, and it was in the logs at every one of those starts.

**Raising the limit to 2Gi did not fix it, it re-scaled it.** The budget became
2 GiB of a 2 GiB cap; region-east then peaked at **1656 Mi of 2048** (81%) —
still climbing toward the same wall, just more slowly. 2Gi bought time and
looked like a fix because the restart counter stopped.

FIXED: `RESTATE_ROCKSDB_TOTAL_MEMORY_SIZE` set to 50% of the container limit,
computed by `openddil.halfMemoryBytes` from the SAME value that sets the limit
so the two cannot drift. Applied to the root and all five tiers (6 render
sites). Emitted in bytes because the env override rejects unit strings the TOML
field accepts, and a rejected value is silently ignored.

Verified on region-east 2026-09-17: startup ERROR gone, partition budget
810.3 MiB -> 405.2 MiB, peak 1656 Mi -> steady ~1014 Mi, zero restarts, derive
stage still completing at the same rates.

| node | pre-fix peak | post-fix | limit |
|---|---|---|---|
| root `restate-server` | 510 Mi | 517 Mi | 2Gi |
| `tier-restate-edge-01` | 638 Mi | 558 Mi | 2Gi |
| `tier-restate-edge-02` | 337 Mi | 342 Mi | 2Gi |
| `tier-restate-region-east` | **1656 Mi** | 1014 Mi | 2Gi |

**ACCIDENTAL CONTROLLED COMPARISON, and it is the strongest evidence here.**
The fix was applied to region-east alone at 12:24 while a memory watch was
already running. That left three unfixed nodes under identical load for the
next 52 minutes:

| node | budget | 12:18 -> 13:10 |
|---|---|---|
| region-east | **1 GiB (fixed)** | 1656 peak -> oscillates **1087-1185, no trend** |
| edge-01 | 2 GiB (= cap) | 589 -> 638, sawtooth to 288, then 288 -> 614 climbing |
| edge-02 | 2 GiB (= cap) | **279 -> 617 monotonic**, ~6.5 MiB/min |
| root | 2 GiB (= cap) | 466 -> 642, climbing |

The only node that went flat is the only node that was fixed. edge-02's slope
put it at the 2Gi cap in roughly 3.5 hours; the sawtooth on edge-01 is RocksDB
releasing on compaction and refilling toward the same ceiling. So "2Gi is
stable" was an artefact of not having watched long enough -- the restart
counter stopping is not the same measurement as the memory plateauing.

Applied to the remaining three at 13:14 by `kubectl set env` rather than a
helm upgrade, deliberately: an upgrade fires the wipe hook on all four
Restates, and discarding the state that had just started working to deliver a
memory fix would have been a poor trade. The chart renders the identical value,
so the next upgrade reconciles rather than reverts. After the restarts: zero
warnings on all four, partition budget 810.3 -> 405.2 MiB everywhere, derive
stage completing at unchanged rates, zero restarts.

**The 167 MiB baseline is retired as a sizing input.** It was measured on an
idle Restate and it measured the PARTITION budget, which is a different number
from the one that kills the process. The sizing record should be written
against the RocksDB budget, not against observed RSS.

*The lesson, and it is the batch's theme again:* the component was reporting
its own misconfiguration, in its own logs, as an ERROR, roughly 1600 times.
Every instrument outside it was green, so nobody read the one instrument that
was not. **A component's self-report is an instrument too, and the cheapest one
in the system.** Read the logs of the thing that is restarting before tuning
the thing it is restarting against.

### Reliability finding, independent of what caused the kills

**~1600 OOM kills corrupted a single-node Restate's cluster metadata past
self-recovery.** `POST /query` answered `node N1:1645 was shut down or
removed`; the node could neither create nor enumerate an invocation, while
every pod read `1/1 Running`. Not "invocations failing", not "invocations
absent" — a third state in which the substrate cannot answer questions about
itself, and which no liveness or readiness probe in the system detects.
Recovery was a wipe. Worth a durability row on its own merits.

### Guards landed

* **guard 4** in `check-chart-render.sh` — parses every rendered shell script
  with `sh -n`, across **three variants** (`default` 35, `tiernode` 62,
  `releasability` 38). The first version rendered defaults only and so never
  parsed any of the 27 scripts in `tier-node.yaml`; it also missed
  ConfigMap-shipped shell (`relay-stall-probe.sh`, 4.6 KB). Both were the same
  covers-one-of-N shape as defect 5, arriving inside the fix for defect 3.
* **`check-derive-stage.sh`** — dispatch item (2). Three terms: consumed,
  completed, deployment reachable. Its first draft reported `0` for eight
  watermarks including one known to be 1,436,481, because it did not export
  `KUBECONFIG`, `2>/dev/null` ate the error and `s+0` manufactured a zero. It
  now refuses to report a number it did not read, and asserts the cluster.

### Next, in order

1. Fix `cm-service` / `logistics-fusion` tactical-event labelling; gate to zero.
2. ~~Sizing record~~ **CLOSED 2026-09-17.** Written into values.yaml against
   the RocksDB budget. 90-minute watch, all four nodes under a 1 GiB budget
   with the derive stage running: root 265-407Mi, edge-01 165-374Mi, edge-02
   148-375Mi, region-east 989-1192Mi -- all sawtoothing, no trend, peak 58%
   of 2Gi. region-east runs ~3x an edge (two children plus own ingest); size
   the regional tier from that ratio, not from an edge measurement.
3. Parsers for the other embedded languages — Bloblang in the three
   `connect.yaml` ConfigMaps (`rpk connect lint`, binary already in the
   redpanda image), TOML and JSON (stdlib, free). Survey done; none checked.
4. Nightly cron for `check-advancing` + `check-derive-stage` + the gate.
5. `ADR-0042` custody: `wipe_one` must refuse to wipe a Restate holding intent
   custody. Constraint recorded in the hook's design note while it is still
   safe; the refusal lands with custody.

---

## OPEN 2026-09-17 — Restate consumes, the services never produce (edge-01)

Two defects found tonight. The first is fixed and the second is not, and they
were stacked so the first hid the second.

### FIXED — Restate OOMKilled at 1Gi

`tier-restate-edge-01` at **1600 restarts**, `region-east` at **1124**, all
`OOMKilled` (exit 137) roughly every 17 seconds: start, catch up partitions in
~16s, die. Restate drives fusion, so nothing downstream could run. Raised to
2Gi; all three now stable with zero restarts.

**Do not record 2Gi as SIZING yet.** The 2026-08-08 note measured 167 MiB RSS
idle and concluded "the cost is BASELINE, not data". A consumer task dying and
restarting every 17 seconds for eight days is a plausible driver of the
975 MiB the survivor showed. Measure against the baseline once the pipeline
is healthy; the note may still be right and 2Gi merely margin.

### FIXED — zstd on Restate-subscribed topics

Restate's Kafka ingress is built on a librdkafka **without zstd**. One zstd
batch kills the consumer task (`Decompression (codec 0x4) ... Not
implemented`); Restate restarts it from its stored position, hits the same
batch, dies again, forever.

**The obvious suspect was wrong.** The chart does set `compression.type=zstd`
— on four `ingress-*-raw` topics, and **Restate subscribes to none of them**.
The real cause is `compression.type=producer`, the default the subscribed
topics carried, which means *store whatever codec the CLIENT chose* — and one
client chooses zstd. Evidence came from HQ's broker, never altered by hand,
showing `producer (DEFAULT_CONFIG)` rather than zstd.

Chart now sets explicit `lz4` on all six subscribed topics. **This reaches the
work cluster on upgrade: P0.1 gate.** Also worth checking whether a current
Restate image ships zstd, which would retire the constraint instead of
documenting it.

### OPEN — the services are invoked by nothing

After both fixes, at edge-01:

* `raw-sensor-stream` advancing (+98/60s) — input present
* `cm-service-silver-edge-01` **Stable, lag 7** — Restate IS consuming
* zstd errors **0**
* all seven subscriptions registered, sinks correct
* `asset-cm-state` **+0** and `asset-logistics-status` **+0** — the services
  produce nothing
* fusion's log shows only `GET /discover` — **zero invocations**, ever

Restarting both services changed nothing. So Restate consumes the messages
and the invocation does not reach the service, or reaches it and produces no
output and no log line.

**Next, in order:** query Restate's invocation status via the admin API
(`/invocations`) to see whether invocations exist and are failing, rather than
inferring from the absence of output; check whether the registered service
DEPLOYMENT in Restate points at the current pod revision; and check whether
the services' own Kafka publisher can connect — fusion logs "Kafka publisher
installed" at startup but nothing proves it produced since.

**Instrument gap this exposes.** `check-advancing` watches BROKER topics and
was green throughout, because ingest and the mapper were fine. It does not
watch the derive stage's OUTPUT relative to its input. The feed check watches
consumer groups, which were Stable. Neither instrument asks the question that
would have caught this: *this service consumed N and emitted 0.*


## OPEN 2026-09-16 — tactical_events: HQ prunes, the tiers never do

The completeness gate refused `tactical_events` as empty-and-undeclared at
HQ. It is right to refuse, and the cause turned out to be two facts that only
look like a fault together:

* **HQ's mapping carries `retention_hours: 24`** and a background pruner
  drops rows older than that. **The tier projector mappings carry no
  retention at all.**
* **Every tactical event in the system is 8 days 21-22 hours old.** Fusion
  emits only on an UPWARD transition into an alerting severity, and the fleet
  has been stable since. So nothing new has been produced for eight days.

HQ's zero is therefore **correct behaviour**, not a stalled producer — and
the region's 18,562 rows are the same events that HQ correctly aged out.

### Do NOT declare tactical_events expected-empty

`expected-empty.yaml` wants *"a dated claim that a named producer is absent
for a named reason."* The producer here is not absent; it is **quiescent**. A
declaration would suppress exactly the signal the gate exists to raise: a
genuinely broken fusion looks identical to a stable fleet from the table, and
the difference is the whole reason the check asks.

**The resolution before a recording is to GENERATE an event, not to declare
the table empty** — which the demo's injection beat does anyway, and which
also proves the path rather than excusing it.

### The asymmetry is the real finding

**The tier stores have unbounded tactical-event retention.** region-east holds
18,562 rows nine days old and will hold them indefinitely; HQ holds 24 hours.
Nothing decided that — HQ's mapping was configured and the tier mappings were
copied without the field.

Two things to settle:

* **Which way should it go?** An edge is the tier with the least storage and
  the most reason to keep local history through a long severance; HQ has the
  most storage and the least need for raw event history. The current
  configuration is the opposite of that argument in both directions, which
  suggests it was inherited rather than chosen.
* **Unbounded growth at a tier store is a DDIL hazard**, not just untidiness:
  the store that must survive a severance is the one with no bound on this
  table.

Recorded rather than fixed, because picking a retention is a deployment
decision and a number invented here would read as a requirement.


## RETRACTED 2026-09-09 — "a broker restart wedges its clients" is not true

I reported that as the night's root pattern. It does not reproduce.

**Two deliberate reproductions on edge-01's broker:** a 6-second pod delete,
and a 150-second full scale-to-zero. In both, every client — sensor-ingest,
the DIS mapper, faust-edge, the bridge, the tier projector — reconnected on
its own, and the advancing pre-flight read green within 100 seconds. Nothing
wedged.

So the 21:29–21:44 event that killed four clients **remains unexplained.**
The correlation with a broker roll was real; the causation was mine.

**And it strengthens the case for the mechanisms rather than weakening it.**
A known trigger could be fixed at the trigger. An unexplained wedge can only
be defended against where it shows: a component that cannot do its job must
die, and a component whose output has stopped must go unready. Those convert
an unknown cause into a visible restart, which is the property that matters
when the cause is unknown.

### And a second retraction, from the same block

I wrote that `kafka_errors` counts produce ATTEMPTS rather than deliveries,
citing edge-02 reporting zero errors while its topic was frozen. **Reading the
code shows the delivery callback does increment on error**, and re-measuring
shows edge-02's ingest was never broken: its output topic `ingress-dis-raw`
was advancing normally. The frozen topic I compared against was
`raw-sensor-stream`, which is the DIS MAPPER's output, not the ingest's.

**I diagnosed a component by watching a topic it does not write.** That is the
same mislabelling the pre-flight's own probe carried until it was corrected,
committed twice in one session — once in the tool, once in the reasoning.

What survives from that block, verified: edge-01's ingest DID enter a fatal
producer state and log at WARNING forever, and that is now fixed by exiting
non-zero.


## OPEN 2026-09-09 — two components that wedge at 1/1 Running, found before a severance

Pre-cut baseline for the two-dimension severance found the pipeline **dead
for three and a half hours**, in two unrelated ways, both invisible to every
liveness probe:

**1. Both edge bridges stopped consuming at 21:29-21:31.** edge-01 logged
`kafka: error while consuming telemetry-latest-state/1: the provided member
is not known in the current generation` — a consumer-group rebalance error —
then went silent. edge-02 logged "Input type kafka is now active" and then
nothing. Both pods stayed `1/1 Running`; lag climbed to **106,249** and
**79,726** and neither restarted.

**2. edge-01's sensor-ingest entered a FATAL librdkafka producer state at
00:51:04** — `KafkaError{code=_FATAL, val=-150, "Unable to produce message:
Local: Fatal error"}`. A fatal producer state is unrecoverable by design: the
client will never produce again without being recreated. The pod stayed
`1/1 Running, restarts=0` and kept RECEIVING and DECODING (460,181 decoded,
21,264 kafka_errors and climbing) — so every counter except the one that
mattered looked healthy.

Both are the same shape this corpus keeps recording, now on the WRITE and
RELAY sides rather than the read side: **a process that is up, probed
healthy, and doing nothing.** The read-side instances were the reachback, the
unfed consumer and the wedged Faust table; these are their producers.

**What would have caught them, and did not.** The edge buffer monitor tracks
exactly this — `bridge_group_lag` climbing to 106k is the signal — and it was
recording it. Nothing ESCALATED it. The number was on a panel nobody was
looking at, which is the difference between an instrument and an alarm.

**Why it matters beyond the outage:** severing a tier whose inbound is
already frozen measures nothing, exactly as severing a tier whose link probe
is already down measures nothing. The pre-cut baseline is what caught it, and
it caught it because the baseline asked whether numbers ADVANCE rather than
whether they exist.

**Restart cleared both.** Region inbound resumed (frozen at 199,883, moved on
restart) and ingest re-bound its UDP socket.

**To decide:**

* A liveness or readiness probe that fails on a fatal producer state, rather
  than one that only checks the process is alive. The ingest knows: it counts
  `kafka_errors`, and a nonzero-and-climbing rate with a fatal code is
  self-diagnosing.
* A bridge probe on consumer progress, not process liveness — committed
  offset advancing, not "the container is up".
* An escalation path for `bridge_group_lag` beyond rendering it. A threshold
  that turns the existing instrument into an alarm.
* **For the recording:** these two wedge. Check `bridge_group_lag` and the
  ingest's `kafka_errors` immediately before recording, because both fail
  silently and the demo would show a frozen fleet with every pod green.


## OPEN 2026-09-08 — a new consumer group replays history into a schema that has since changed

Giving region-east its own `region_*` projectors created three NEW consumer
groups, which started at offset 0 and replayed the topic's whole history —
including messages emitted BEFORE the rollups were partitioned by
releasability class.

A pre-partition message carried no `releasable_to`, so it decodes as the
**empty class**, and it carried the WHOLE region's counts. The result was a
phantom partial: `class='' assets=14 releasable_to={}` sitting alongside the
three real ones.

**It cannot be fixed by decoding.** A pre-partition message and a legitimate
empty-audience partial — a class whose contributors are releasable to nobody
— are byte-identical. There is no field that distinguishes "this producer
predates the concept" from "this producer computed an empty set".

**Why it was not visible.** `releasable_to={}` denies everyone under the §4
predicate, so the phantom row renders on no screen. It is wrong data that no
subject can see, which is the most patient kind.

**Cleaned by hand this once** (three rows at the region, plus a stale
`id='edge'` buffer row left behind when the buffer key became the tier id —
same shape: *a key change does not delete the old key's row*).

**What to decide, before the next tier is added:**

* Whether new tier consumer groups should start at `latest` rather than
  `earliest`. That avoids the replay and loses legitimate history — a real
  trade, not an obvious win.
* Or whether the aggregate handler should reject a message whose provenance
  carries no `releasable_to` KEY at all, distinct from one carrying an empty
  list. proto3 erases that distinction on the wire (recorded already), so
  this would need a producer-side marker — which is the same conclusion the
  composed-vs-uncomposed branch reached, and was abandoned for the same
  reason.
* Or accept the phantom and have the completeness gate name it: a partial
  whose class is empty AND whose asset_count equals the region total is a
  legacy row, and that conjunction is checkable even though neither half is.

The third is the cheapest and the most honest: it does not pretend the wire
carries something it does not, and it turns an invisible wrong row into a
named finding.


## PROMOTED 2026-09-08 — asset-registry-service must stamp its own writes

**Was:** deferred, behind the bridge. **Now:** behind the region, before any
recording.

**Why the cost changed.** The service still does not stamp releasability on
rows it writes; 20260906010000 backfilled what existed, so the gate reads
zero unlabelled today. That was survivable when an unstamped row hid ONE
asset.

Regional rollups are now labelled by **intersection**, and an unlabelled
contributor takes the intersection to empty. So a single row the service adds
after the backfill no longer hides an asset — **it blanks the regional
screen, for everyone, including the fully-entitled liaison.**

That is deny-unlabeled propagating correctly through aggregation, and it is
the right behaviour. The blast radius is what changed, not the correctness:
one unstamped write now costs a region's whole rollup rather than one row.

**Test when it lands:** add an asset through the service and confirm the
regional rollups keep their composed audience rather than going empty.


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
./scripts/check-decision-indexes.sh      # exit 0 = clean
```

**Run in CI** on every change to `decisions/` — `.github/workflows/
decision-indexes.yml`. **44 IDs as of 2026-09-05.**

*The commands are not repeated here on purpose.* A copy in this file and a
copy in the workflow are two things to keep in sync, and keeping two copies
of a drift-detector in sync is the drift it was written to detect. The
script is the single copy; this section points at it.

It runs **four** checks:

1. every register ID has a row here, and every row is a real ID;
2. every document in `decisions/` is referenced by `README.md`;
3. every row's status **matches its home document's declared token**, by
   exact string;
4. every row's home **has** a token — so a missing one fails loudly instead
   of dropping out of check 3.

Failure prints the specific IDs or filenames. A mismatch means the corpus
moved and this file did not, which is information, not an error.

*All four were verified by being made to fail* — a deleted row, an unindexed
document, a phantom ID, a disagreeing status in each register shape, and a
deleted token each produce the expected message and exit 1. A check never
seen red proves nothing about what it would catch.

> **The script's `grep -v FOLLOW-UPS.md` is load-bearing, not tidiness.**
> The obvious form scans `*.md`, which includes *this file* — so every ID
> written here would appear in its own "corpus", every row would vouch for
> itself, and the phantom-row direction **could never fail**. A renamed or
> deleted ID would pass silently. The first draft had exactly that flaw.
>
> *A verification that includes its own subject in its evidence is not a
> verification* — the same shape as a guard that has never been seen to
> fail, arriving in the checker written to prevent drift.

*This check is why the file is worth having.* It cannot verify a status is
still accurate — only a human reading the home document can — but it makes
the *cheap* failure (a row that never got added) mechanical, and leaves only
the expensive one to judgement.

### The second check exists because the first is blind to it

An entire document can go unlisted without affecting any ID. When first run
on 2026-08-12 that check found **eleven**, including **`PRINCIPLES.md` and
`GENERALIZATION-DEBT.md`** — the two most-cited documents in the corpus —
and three of five audits. All are now listed.

**Both are in CI, which was the actual conclusion.** Neither requires
judgement, both run in under a second, and both failed silently for weeks
under a team that is demonstrably careful about exactly this class of error.
See `PRINCIPLES.md` §*Indexes drift where the work is not*.

### Checks 3 and 4 — status, and why they took a detour

**Status drift is now checked exactly**, because status is **declared**
rather than inferred. Every row carries a token — the Status *column* in the
`GD` table, a `` `Status: …` `` line above the heading in the prose registers
— and the script compares index against home by exact string. Check 4 exists
so a row with **no** token cannot drop out of that comparison silently;
absence answering as agreement is the disease this tooling exists to fight,
and it would have been an ignominious way to reintroduce it.

**A green status check means the index AGREES with the home. It does not
mean either is true.** The script prints that line itself, every run, so the
distinction survives being read by someone in a hurry.

The route here is the part worth keeping, because the first two attempts
both *looked* like they worked:

This file shipped 2026-08-12 marking `IH-5` and `IH-6` **open**. Both had
been **fixed the same day**, in a parallel session, and the index was built
from a snapshot that predated it. The limitation documented below —
*"a row marked open that was quietly fixed will not be caught by any command
in this file"* — fired **within three days of being written**, which is the
strongest possible argument that it was not a theoretical caveat.

A heuristic was attempted and **deliberately not shipped**, because it does
not work:

- windowing from *any mention* of an ID gave **false positives** — `README`'s
  dense summaries mention `AE-2` and `VE-7` within a few lines of an
  unrelated *"RESOLVED 2026-08-12"* belonging to `AE-1`;
- tightening to definition sites with a 16-line window then gave a **false
  negative** — it caught `IH-6` and missed `IH-5`, whose `FIXED` marker sits
  25 lines under its heading.

**There was no correct window**, because register blocks vary in length. A
check tuned until it passes is a check whose green means nothing — the
decorative-guard failure, arriving in the third checker in three days. So
the heuristic was **rejected rather than improved**, and the property it was
trying to reconstruct was declared instead.

*Note what the detour was:* inferring status by pattern-matching prose is
the **same disease as inferring asset class from publishing behaviour**
(**GD-11**) or absence from a zero (**GD-12**) — a property nothing
declares, reconstructed downstream from a correlate that mostly works. It is
the family's fourth instance and its first inside this project's own
tooling. The fix is the one those rows also demand: **declare the property.**

*One implementation note that nearly went wrong.* The tokens were first
inserted *after* each row's bolded heading, which split sentences wherever
prose continued on the heading's closing line — the anchor was structurally
wrong, not merely misplaced. They now sit on their own line **above** the
heading, where nothing can be split. Verified by diffing: the change is
**purely additive**, no existing line altered.

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
| GD-08 | Detection centralized at root, reaching downward | in-arc Arc 1 |
| GD-09 | Bare-name alias Services | fixed 2026-08-08 |
| GD-10 | Capability-item shape undeclared | open |
| GD-11 | Asset class inferred from one feed's behaviour | open |
| GD-12 | Absence conventions declared only in the consumer | open |
| GD-13 | Generated protos are not a package; every consumer invents a path | open |
| GD-14 | Wear axis applicability: type-level manifest FIXED; asset-level as-maintained state open | narrowed — type-level fixed, asset-level open |

### UD — undetected failure modes (`ADR-0036`)

| ID | Subject | Status |
|---|---|---|
| UD-1 | Severance detector depends on the uplink it detects | open |
| UD-2 | No tolerance classification observed under a real sever | open |
| UD-3 | Egress + overlay components outside every sweep | open |
| UD-4 | Pre-sync zero, instrument-side *(see IH-1)* | open |
| UD-5 | Middleware-participation health has no observable | open |
| UD-6 | **The register itself is unaudited** | open |
| UD-7 | Resource failure manifests on a component that did not cause it | open |
| UD-8 | Field-by-field message copy drops what it was not told to carry | open |
| UD-9 | A configuration setting whose consumer does not exist fails silently | open |
| UD-10 | Tier and root share consumer groups; the tier goes silent looking healthy | open |
| UD-11 | The detection cutover retired the subscription and left the projector reaching down | fixed 2026-09-05 |
| UD-12 | Subscription bootstrap creates and never reconciles; a wipe hook hid it at the root | fixed 2026-09-05 |
| UD-13 | Fusion skipped DIS telemetry on an expired premise — guard deleted, admission by content | fixed 2026-09-07 |
| UD-14 | Four clients wedged at 1/1 Running for 3.5h — broker restart exonerated by test, helm rollout untested | remedy landed, cause OPEN |

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
| VE-8 | No CI job runs any Python test suite | open |
| VE-9 | A deploy reports success while running the previous artifact | open |

### IH — information-honesty divergences (`ADR-0035`)

| ID | Subject | Status |
|---|---|---|
| IH-1 | Pre-sync `?? 0` renders a confident zero *(see UD-4)* | open |
| IH-2 | Three of four CM/ops quadrants rendered distinctly | open |
| IH-3 | `tactical_events.severity` mixes two vocabularies | open |
| IH-4 | Tier identity answered by URL, not asserted | open |
| IH-5 | Most-derived value carries weakest provenance | fixed 2026-08-12 |
| IH-6 | Horizon renders as a bare duration, no basis | fixed 2026-08-12 |

### AE — capability-envelope gaps (`ADR-0038`)

| ID | Subject | Status |
|---|---|---|
| AE-1 | ADR-0011 claimed work-order generation | fixed 2026-08-12 |
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

## Reconciliation — 2026-08-19

A week of closures, checked against the registers rather than recalled.

**Statuses that moved**, all verified in their home documents:

| row | now | by |
|---|---|---|
| `IH-5`, `IH-6` | fixed 2026-08-12 | caught by *this file being wrong*, three days after the caveat was written |
| `AE-1` | fixed 2026-08-12 | ADR-0011 amended |
| `GD-09` | fixed 2026-08-08 | chart 0.1.40 |

**New rows this week:** `UD-7` (resource failure manifests away from its
cause), `GD-12` (absence conventions undeclared), `GD-13` (generated protos
are not a package), `VE-8` (no CI ran any Python suite), `IH-5`/`IH-6`.
**Six rows added, three closed** — the register grew, which is what a week
of looking produces and not a sign of decay.

**Rows whose scope changed without their status changing:**

- **`VE-4`** — split. The rendered-object half is **built and in CI**
  (`openddil-helm` `2ceee1b`); the header self-description half is **closed
  as unbuildable in its stated form**, with the structural alternative
  recorded. The row is smaller than it was, not closer to done.
- **`GD-12`** — surveyed (`AUDIT-2026-08-15`), and its fourth instance found
  in our own tooling. Still open; the *convention* is now stated in
  `telemetry.proto` for the operational axes only.
- **`GD-13`** — design landed (`DESIGN-2026-08-19-gen-python-packaging`),
  and the survey found **five** mechanisms rather than the three the row
  claims. Row text is now an undercount.

**What did not move, and should be read as deliberate:** `VE-1` (no index of
evidence), `VE-2`, `VE-3`, `VE-5`, `VE-6`, `VE-7`, `UD-1`..`UD-6`,
`GD-01`..`GD-08`, `GD-10`, `GD-11`, `IH-1`..`IH-4`, `AE-2`..`AE-6`. None was
worked; none is blocked on anything a night can fix.

*One honest note about this pass:* it reconciles **statuses and scope**, not
**truth**. Check 3 proves the index agrees with each home document; nobody
re-derived whether the homes are still right. A row that quietly became
irrelevant would survive this reconciliation intact.

## What this index does not cover

- **Prose follow-ups in audits and plans** — deliberately. Only ID'd rows
  are indexed, because only they can be checked mechanically. Anything
  worth tracking should therefore *earn an ID in a register*, and this
  boundary is the incentive to give it one.
- **Statuses are not verified here.** The checks prove a row exists, not
  that `open` is still true. A row marked open that was quietly fixed will
  not be caught by any command in this file — **and this has already
  happened once, to `IH-5`/`IH-6`, three days after the caveat was
  written.** See §*The third check does not exist*.
- **`PLAN-*` documents' open steps** — they carry their own sequencing and
  are not follow-ups in the register sense.
- **Anything outside `openddil-contracts/decisions/`.** Follow-ups recorded
  in other repositories' code comments or runbooks are not visible here,
  and no claim is made that this is the complete set of outstanding work.
