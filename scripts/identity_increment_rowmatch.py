#!/usr/bin/env python3
"""Row-match acceptance for the asset-identity increment.

DESIGN-2026-11-08-adr0056-first-increment.md section 4. Four steps, each its own
invocation, each writing its files under --out and stopping:

    python scripts/identity_increment_rowmatch.py read --phase before --helm-dir ../openddil-helm --context CTX -n NS --store TIER=POD[/DB] --out DIR
    python scripts/identity_increment_rowmatch.py predict --out DIR
    python scripts/identity_increment_rowmatch.py read --phase after  (same arguments as before) [--broker-pod POD --group GROUP --topic TOPIC] --out DIR
    python scripts/identity_increment_rowmatch.py compare --out DIR

READ ONLY. The only SQL is one SELECT or WITH per call, run in a session that
first sets default_transaction_read_only = on. The only other remote command is
`rpk group describe`. The roll that ships the increment is a person's.

EXIT CODES, as migrate_site_declarations.py: 0 match, 1 diff, 3 refused,
4 unchecked, 78 guard. A refusal names the state and halts the run. No step
overwrites a file an earlier step wrote.

A table or column that does not exist at a tier is recorded as absent, never as
an error. Before the roll the identity tables are absent; after it, an absent
identity table is a diff.

UNTESTED AGAINST A CLUSTER. The pure parts and the faked runner paths are
tested offline (tests/test_identity_increment_rowmatch.py).
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import pathlib
import re
import subprocess
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

# Imported, not copied: the exit codes, the Refusal, the guard, the file hash,
# the first-line reader and the clock are the migration script's.
from migrate_site_declarations import (  # noqa: E402
    EXIT_DIFF, EXIT_GUARD, EXIT_OK, EXIT_REFUSED, EXIT_UNCHECKED,
    Refusal, _now, run_guard, sha256_file,
)

assert EXIT_GUARD == 78

REMOTE_TIMEOUT_S = 60
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
POD_RE = re.compile(r"^[a-z0-9][a-z0-9.-]{0,252}$")
IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")

IDENTITY_TABLES = ("alias_scheme", "asset_identity", "asset_alias",
                   "asset_binding", "identity_equivalence")
CONFLICT_TABLE = "identity_conflict"
PROJECTOR_TABLES = ("asset_declaration", "asset_correlation")
ERA_FN = "public.asset_id_era(text,timestamptz)"
# Alias schemes the carried serial and uii are written under (design 1.1).
SCHEME_OF = {"serial": "serial", "uii": "uii"}
NOT_ASSET_ID_SCHEMES = ("serial", "uii", "identity")
ERA_CHUNK = 200

DIFF_ORDER = (
    "missing_id", "changed_asset_id", "projector_count_moved",
    "declared_without_binding", "identity_without_binding",
    "identity_table_absent", "binding_count", "binding_identity_missing",
    "alias_rows", "conflict_unpredicted", "era_not_one",
)


def jdump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def compact(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def ident(name: str) -> str:
    if not IDENT_RE.match(name):
        raise Refusal(f"{name!r} is not a plain identifier")
    return f'"{name}"'


# --------------------------------------------------------------------------
# Store: one SELECT or WITH per call, in a read-only session
# --------------------------------------------------------------------------

def default_run(argv: list[str]) -> str:
    p = subprocess.run(argv, capture_output=True, text=True)
    if p.returncode != 0:
        raise Refusal(f"{' '.join(argv[:6])}: {p.stderr.strip()}")
    return p.stdout


_LITERAL = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"")


def check_one_select(sql: str) -> None:
    bare = _LITERAL.sub("''", sql).strip()
    head = bare.split(None, 1)[0].upper() if bare else ""
    if head not in ("SELECT", "WITH") or ";" in bare.rstrip(";"):
        raise Refusal("this script only reads: refused a statement that is "
                      f"not one SELECT or WITH: {sql[:60]!r}")


class Store:
    def __init__(self, context: str, namespace: str, pod: str, database: str | None,
                 user: str | None, run=default_run):
        self.pod, self.run = pod, run
        self.argv = ["kubectl", "--context", context, "-n", namespace, "exec", pod,
                     "--", "timeout", str(REMOTE_TIMEOUT_S), "psql"]
        if user:
            self.argv += ["-U", user]
        if database:
            self.argv += ["-d", database]
        self.argv += ["-v", "ON_ERROR_STOP=1", "-tA", "-F", "\t"]

    def psql(self, sql: str) -> str:
        check_one_select(sql)
        # The head check is the script's own rule; the store enforces it too. A
        # WITH can wrap a data-modifying statement, so every query runs in a
        # session whose transactions are read only.
        out = self.run(self.argv + ["-c", "SET default_transaction_read_only = on",
                                    "-c", sql]).splitlines()
        if out and out[0].strip() == "SET":      # the first -c's command tag
            out = out[1:]
        return "\n".join(out)

    def rows(self, sql: str) -> list[list[str]]:
        return [ln.split("\t") for ln in self.psql(sql).splitlines() if ln.strip()]

    def json(self, sql: str):
        text = self.psql(sql).strip()
        return json.loads(text) if text else None


def table_columns(st: Store, table: str) -> set[str] | None:
    """The table's columns, or None when the table does not exist."""
    t = ident(table)[1:-1]
    if st.psql(f"SELECT to_regclass('public.{t}') IS NOT NULL").strip() != "t":
        return None
    return {r[0] for r in st.rows(
        "SELECT column_name FROM information_schema.columns WHERE "
        f"table_schema='public' AND table_name='{t}'")}


def select_rows(st: Store, table: str, cols: list[str], where: str = "") -> list[dict]:
    sel = ", ".join(ident(c) for c in cols)
    w = f" WHERE {where}" if where else ""
    got = st.json("SELECT coalesce(jsonb_agg(to_jsonb(t)), '[]'::jsonb)::text FROM "
                  f"(SELECT {sel} FROM {ident(table)}{w}) t")
    return got or []


def primary_key(st: Store, table: str) -> list[str]:
    pk = [r[0] for r in st.rows(
        "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
        "AND a.attnum = ANY(i.indkey) WHERE i.indisprimary AND "
        f"i.indrelid = 'public.{ident(table)}'::regclass "
        "ORDER BY array_position(i.indkey::int2[], a.attnum)")]
    if not pk:
        raise Refusal(f"{table} at {st.pod} has no primary key")
    for c in pk:
        ident(c)
    return pk


def pk_keys(st: Store, table: str, pk: list[str]) -> list[str]:
    expr = "to_jsonb(ARRAY[" + ", ".join(f"{ident(c)}::text" for c in pk) + "])::text"
    return sorted({compact(json.loads(r[0]))
                   for r in st.rows(f"SELECT {expr} FROM {ident(table)}")})


# --------------------------------------------------------------------------
# The reads, per tier
# --------------------------------------------------------------------------

def absent() -> dict:
    return {"present": False}


def want(cols: set[str] | None, wanted: list[str]) -> tuple[list[str], list[str]]:
    have = [c for c in wanted if c in (cols or set())]
    return have, [c for c in wanted if c not in have]


def read_registry(st: Store) -> dict:
    cols = table_columns(st, "asset_registry")
    if cols is None:
        return absent()
    have, missing = want(cols, ["asset_id", "last_observed_at"])
    if "asset_id" not in have:
        return {"present": True, "missing_columns": missing, "rows": {}}
    rows = select_rows(st, "asset_registry", have)
    return {"present": True, "missing_columns": missing,
            "rows": {r["asset_id"]: r.get("last_observed_at") for r in rows}}


def read_egress(st: Store) -> dict:
    cols = table_columns(st, "egress_delivered_events")
    if cols is None:
        return absent()
    have, missing = want(cols, ["event_id", "episode_id", "asset_id", "detected_at"])
    rows = select_rows(st, "egress_delivered_events", have) if have else []
    events, episodes = {}, {}
    for r in rows:
        if r.get("event_id") is not None:
            events[r["event_id"]] = r.get("asset_id")
        ep = r.get("episode_id")
        if ep is not None:
            cur = episodes.setdefault(ep, {"asset_id": r.get("asset_id"), "detected_at": None})
            d = r.get("detected_at")
            if d is not None and (cur["detected_at"] is None or d < cur["detected_at"]):
                cur["detected_at"] = d
    return {"present": True, "missing_columns": missing, "events": events, "episodes": episodes}


def read_discrepancies(st: Store) -> dict:
    cols = table_columns(st, "asset_cm_state")
    if cols is None:
        return absent()
    out = {"present": True, "missing_columns": [], "without_id": 0}
    for col in ("discrepancies", "manual_discrepancies"):
        if col not in cols or "asset_id" not in cols:
            out["missing_columns"] += [c for c in (col, "asset_id") if c not in cols]
            out[col] = None
            continue
        c = ident(col)
        got = st.json(
            "SELECT coalesce(jsonb_agg(jsonb_build_array(s.asset_id, "
            "CASE WHEN jsonb_typeof(d) = 'object' THEN d->>'discrepancy_id' END)), "
            "'[]'::jsonb)::text FROM " + ident("asset_cm_state") + " s, "
            f"jsonb_array_elements(CASE WHEN jsonb_typeof(s.{c}) = 'array' "
            f"THEN s.{c} ELSE '[]'::jsonb END) d") or []
        out[col] = {did: aid for aid, did in got if did is not None}
        out["without_id"] += sum(1 for _, did in got if did is None)
    out["missing_columns"] = sorted(set(out["missing_columns"]))
    return out


def read_projector_table(st: Store, table: str) -> dict:
    cols = table_columns(st, table)
    if cols is None:
        return absent()
    pk = primary_key(st, table)
    keys = pk_keys(st, table, pk)
    out = {"present": True, "pk": pk, "count": len(keys), "keys": keys,
           "columns": sorted(cols)}
    if table == "asset_declaration":
        have, _ = want(cols, ["asset_id", "serial", "uii"])
        out["rows"] = select_rows(st, table, have) if have else []
    else:
        if {"serial", "asset_id"} <= cols:
            got = st.json(
                "SELECT coalesce(jsonb_agg(jsonb_build_object('serial', serial, "
                "'asset_ids', a)), '[]'::jsonb)::text FROM (SELECT serial, "
                "jsonb_agg(DISTINCT asset_id) a FROM " + ident(table) + " WHERE serial IS NOT NULL "
                "GROUP BY serial HAVING count(DISTINCT asset_id) > 1) c") or []
            out["serial_collisions"] = sorted(
                ({"serial": g["serial"], "asset_ids": sorted(g["asset_ids"])} for g in got),
                key=lambda g: g["serial"])
        else:
            out["serial_collisions"] = "not readable: asset_correlation has no serial or asset_id column"
    return out


def read_identity(st: Store) -> dict:
    out = {}
    for table in IDENTITY_TABLES + (CONFLICT_TABLE,):
        cols = table_columns(st, table)
        if cols is None:
            out[table] = absent()
            continue
        out[table] = {"present": True, "rows": select_rows(st, table, sorted(cols))}
    return out


def read_era(st: Store, episodes: dict) -> dict:
    """asset_id_era(asset_id, detected_at) for each episode read before."""
    fn = st.psql(f"SELECT to_regprocedure('{ERA_FN}') IS NOT NULL").strip() == "t"
    out = {"function_present": fn, "results": {}, "unreadable": []}
    todo = []
    for ep, d in sorted(episodes.items()):
        if d.get("asset_id") is None or d.get("detected_at") is None:
            out["unreadable"].append(ep)
        else:
            todo.append((ep, d["asset_id"], d["detected_at"]))
    if not fn:
        return out
    for i in range(0, len(todo), ERA_CHUNK):
        vals = ", ".join(f"({sql_str(k)}, {sql_str(a)}, {sql_str(t)})"
                         for k, a, t in todo[i:i + ERA_CHUNK])
        got = st.json("WITH e(k, a, t) AS (VALUES " + vals + ") SELECT coalesce(jsonb_agg("
                      "jsonb_build_array(k, asset_id_era(a, t::timestamptz))), '[]'::jsonb)::text FROM e") or []
        out["results"].update({k: v for k, v in got})
    return out


def read_tier(st: Store, phase: str, before_tier: dict | None) -> dict:
    out = {"asset_registry": read_registry(st),
           "egress_delivered_events": read_egress(st),
           "asset_cm_state": read_discrepancies(st)}
    for t in PROJECTOR_TABLES:
        out[t] = read_projector_table(st, t)
    if phase == "after":
        out["identity"] = read_identity(st)
        eps = (before_tier or {}).get("egress_delivered_events", {}).get("episodes", {})
        out["era"] = read_era(st, eps)
    return out


# --------------------------------------------------------------------------
# The consumer position: rpk group describe
# --------------------------------------------------------------------------

def parse_group_lag(text: str, topic: str) -> int | None:
    """Total lag on `topic` from `rpk group describe`, or None if the output
    cannot be parsed. The partition table has a header row naming TOPIC and
    LAG; its columns are found by name, so added columns do not matter."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        head = ln.split()
        if "TOPIC" in head and "LAG" in head:
            ti, li = head.index("TOPIC"), head.index("LAG")
            total, seen = 0, 0
            for row in lines[i + 1:]:
                f = row.split()
                if not f:
                    continue
                if len(f) <= max(ti, li) or f[ti] != topic:
                    continue
                if not re.fullmatch(r"\d+", f[li]):
                    return None
                total += int(f[li])
                seen += 1
            return total if seen else None
    return None


def read_consumer(args, ctx: str, run) -> dict:
    given = [args.broker_pod, args.group, args.topic]
    if not any(given):
        return {"status": "unchecked", "reason": "no --broker-pod, --group and --topic given"}
    if not all(given):
        raise Refusal("--broker-pod, --group and --topic go together")
    for v in given:
        if not POD_RE.match(v) and not NAME_RE.match(v):
            raise Refusal(f"{v!r} is not a plain name")
    argv = ["kubectl", "--context", ctx, "-n", args.namespace, "exec", args.broker_pod,
            "--", "timeout", str(REMOTE_TIMEOUT_S), "rpk", "group", "describe", args.group]
    try:
        text = run(argv)
    except Refusal as r:
        return {"status": "unchecked", "reason": f"rpk did not answer: {r.reason}"}
    lag = parse_group_lag(text, args.topic)
    if lag is None:
        return {"status": "unchecked", "reason": "rpk output could not be parsed for the topic's lag"}
    if lag != 0:
        raise Refusal(f"group {args.group} is {lag} behind on {args.topic}: the declaration "
                      "consumer has not reached the end offset; read again once lag is 0",
                      {"group": args.group, "topic": args.topic, "lag": lag})
    return {"status": "checked", "group": args.group, "topic": args.topic, "lag": 0}


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------

def write_new(out: pathlib.Path, name: str, obj) -> pathlib.Path:
    path = out / name
    if path.exists():
        raise Refusal(f"{path} already exists: a step never overwrites a file; "
                      "use a new --out", {"exists": str(path)})
    text = obj if isinstance(obj, str) else jdump(obj)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {path}")
    return path


def refuse_if_exists(out: pathlib.Path, names: list[str]) -> None:
    for n in names:
        if (out / n).exists():
            raise Refusal(f"{out / n} already exists: a step never overwrites a file; "
                          "use a new --out", {"exists": str(out / n)})


def load(out: pathlib.Path, name: str) -> dict:
    p = out / name
    if not p.is_file():
        raise Refusal(f"no {name} in {out}")
    return json.loads(p.read_text(encoding="utf-8"))


def parse_stores(items: list[str]) -> dict:
    stores = {}
    for it in items:
        m = re.fullmatch(r"([^=/]+)=([^/]+)(?:/(.+))?", it)
        if not m or not NAME_RE.match(m.group(1)) or not POD_RE.match(m.group(2)):
            raise Refusal(f"--store {it!r}: want TIER=POD[/DATABASE]")
        if m.group(3) is not None and not NAME_RE.match(m.group(3)):
            raise Refusal(f"--store {it!r}: database is not a plain name")
        stores[m.group(1)] = (m.group(2), m.group(3))
    if not stores:
        raise Refusal("no --store given")
    return stores


def step_read(args, run=default_run) -> int:
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    refuse_if_exists(out, [f"{args.phase}.json"])
    before = None
    if args.phase == "after":
        pred_p, before_p = out / "prediction.json", out / "before.json"
        if not pred_p.is_file():
            raise Refusal("no prediction.json: predict is a separate step, before read --phase after")
        if not before_p.is_file():
            raise Refusal("no before.json")
        pred = json.loads(pred_p.read_text(encoding="utf-8"))
        if pred.get("before_sha256") != sha256_file(before_p):
            raise Refusal("prediction.json was written for a different before.json")
        before = json.loads(before_p.read_text(encoding="utf-8"))
    stores = parse_stores(args.store)
    if args.phase == "before" and any((args.broker_pod, args.group, args.topic)):
        raise Refusal("the consumer position is read in the after phase only")
    ctx = run_guard(pathlib.Path(args.helm_dir))
    if ctx != args.context:
        raise Refusal(f"the guard asserted {ctx}, this run was told {args.context}")
    if before is not None:
        gone = sorted(set(before["tiers"]) - set(stores))
        if gone:
            raise Refusal("before.json has tiers not passed now: " + ", ".join(gone),
                          {"tiers": gone})
    tiers = {t: read_tier(Store(ctx, args.namespace, pod, db, args.db_user, run), args.phase,
                          (before or {}).get("tiers", {}).get(t))
             for t, (pod, db) in sorted(stores.items())}
    doc = {"phase": args.phase, "at": _now(), "context": ctx, "namespace": args.namespace,
           "tiers": tiers}
    if args.phase == "after":
        doc["consumer_position"] = read_consumer(args, ctx, run)
    write_new(out, f"{args.phase}.json", doc)
    if args.phase == "after" and doc["consumer_position"]["status"] != "checked":
        print("read: consumer_position: unchecked. " + doc["consumer_position"]["reason"]
              + ". compare will exit 4.")
    return EXIT_OK


def collision_pairs(before: dict) -> list[dict]:
    out = []
    for tier, td in sorted(before["tiers"].items()):
        coll = td["asset_correlation"].get("serial_collisions") if td["asset_correlation"].get("present") else None
        if isinstance(coll, list):
            for g in coll:
                out.append({"tier": tier, "serial": g["serial"], "asset_ids": g["asset_ids"],
                            "pairs": [list(p) for p in itertools.combinations(g["asset_ids"], 2)]})
    return out


def declared_counts(td: dict) -> dict:
    d = td["asset_declaration"]
    if not d.get("present"):
        return {"declared_assets": "not readable: no asset_declaration table",
                "serial_aliases": "not readable", "uii_aliases": "not readable"}
    rows = d.get("rows", [])
    return {
        "declared_assets": d["count"],
        "serial_aliases": (sum(1 for r in rows if r.get("serial")) if "serial" in d["columns"]
                           else "not readable: asset_declaration has no serial column"),
        "uii_aliases": (sum(1 for r in rows if r.get("uii")) if "uii" in d["columns"]
                        else "not readable: asset_declaration has no uii column"),
    }


def step_predict(args) -> int:
    out = pathlib.Path(args.out)
    before = load(out, "before.json")
    if before.get("phase") != "before":
        raise Refusal("before.json is not a before-phase file")
    refuse_if_exists(out, ["prediction.json", "prediction.md"])
    pairs = collision_pairs(before)
    episodes = {t: len(td["egress_delivered_events"].get("episodes", {}))
                if td["egress_delivered_events"].get("present") else 0
                for t, td in sorted(before["tiers"].items())}
    pred = {
        "at": _now(), "before_sha256": sha256_file(out / "before.json"),
        "subsets": ("every asset_id, event_id, episode_id and discrepancy_id read before is "
                    "read after, with the same asset_id; asset_declaration and asset_correlation "
                    "keep their count and key set"),
        "per_declared_asset": {
            "bindings": 1, "identities": 1,
            "alias_rows": "one per carried alias: asset_id, and serial and uii where the declaration row has them",
        },
        "declared_at_before_read": {t: declared_counts(td) for t, td in sorted(before["tiers"].items())},
        "identity_conflicts": {"expected": 0, "except_serial_pairs": pairs},
        "era": {"expected": 1, "episodes_by_tier": episodes},
    }
    write_new(out, "prediction.json", pred)
    md = [f"# Prediction (before.json sha256 {pred['before_sha256']})", "",
          "- " + pred["subsets"],
          "- Per declared asset: one binding, one identity, one alias row per carried alias.",
          "- Zero identity_conflict rows, except these serial pairs:", ""]
    md += [f"  - {p['tier']} serial {p['serial']}: " + ", ".join(f"{a} / {b}" for a, b in p["pairs"])
           for p in pairs] or ["  - (none found at the before read)"]
    md += ["", "- asset_id_era is 1 for every episode read before: "
           + ", ".join(f"{t} {n}" for t, n in episodes.items()), "",
           "## Carried aliases declared at the before read", ""]
    md += [f"- {t}: {compact(c)}" for t, c in pred["declared_at_before_read"].items()]
    write_new(out, "prediction.md", "\n".join(md) + "\n")
    return EXIT_OK


def id_blocks(td: dict) -> dict:
    """The id maps at one tier: kind -> {id: asset_id or None}."""
    reg = td["asset_registry"]
    eg = td["egress_delivered_events"]
    cm = td["asset_cm_state"]
    return {
        "asset_id": {k: k for k in reg.get("rows", {})} if reg.get("present") else {},
        "event_id": eg.get("events", {}) if eg.get("present") else {},
        "episode_id": {k: v["asset_id"] for k, v in eg.get("episodes", {}).items()} if eg.get("present") else {},
        "discrepancy_id": (cm.get("discrepancies") or {}) if cm.get("present") else {},
        "manual_discrepancy_id": (cm.get("manual_discrepancies") or {}) if cm.get("present") else {},
    }


def classify(before: dict, after: dict, pred: dict) -> tuple[dict, list[str], list[dict]]:
    """Every difference, by class, the reasons the run is unchecked, and the
    predicted conflicts seen. Pure."""
    c = {k: [] for k in DIFF_ORDER}
    unchecked = []
    cons = after.get("consumer_position") or {"status": "unchecked", "reason": "not recorded"}
    if cons.get("status") != "checked":
        unchecked.append("consumer position unchecked: " + cons.get("reason", ""))
    pair_assets = {a for p in pred["identity_conflicts"]["except_serial_pairs"] for a in p["asset_ids"]}
    predicted_seen = []
    for tier, bt in sorted(before["tiers"].items()):
        at = after["tiers"][tier]
        bb, ab = id_blocks(bt), id_blocks(at)
        for kind in bb:
            for i, aid in sorted(bb[kind].items()):
                if i not in ab[kind]:
                    c["missing_id"].append({"tier": tier, "kind": kind, "id": i})
                elif ab[kind][i] != aid:
                    c["changed_asset_id"].append({"tier": tier, "kind": kind, "id": i,
                                                  "before": aid, "after": ab[kind][i]})
        for t in PROJECTOR_TABLES:
            b, a = bt[t], at[t]
            if not b.get("present"):
                continue
            if not a.get("present"):
                c["projector_count_moved"].append({"tier": tier, "table": t, "before": b["count"],
                                                   "after": "table absent"})
            elif b["count"] != a["count"] or b["keys"] != a["keys"]:
                c["projector_count_moved"].append({
                    "tier": tier, "table": t, "before": b["count"], "after": a["count"],
                    "removed_keys": len(set(b["keys"]) - set(a["keys"])),
                    "added_keys": len(set(a["keys"]) - set(b["keys"]))})
        _identity_checks(tier, at, pair_assets, c, unchecked, predicted_seen)
        era = at["era"]
        if bb["episode_id"] or era["unreadable"]:
            if not era["function_present"]:
                c["era_not_one"].append({"tier": tier, "reason": "asset_id_era does not exist"})
            for ep in sorted(era["results"]):
                if era["results"][ep] != 1:
                    c["era_not_one"].append({"tier": tier, "episode_id": ep, "era": era["results"][ep]})
            if era["unreadable"]:
                unchecked.append(f"{tier}: {len(era['unreadable'])} episodes have no asset_id or "
                                 "detected_at at the before read, so asset_id_era was not called")
    return c, sorted(set(unchecked)), predicted_seen


def _identity_checks(tier, at, pair_assets, c, unchecked, predicted_seen) -> None:
    ident_ = at["identity"]
    for t in IDENTITY_TABLES + (CONFLICT_TABLE,):
        if not ident_[t].get("present"):
            c["identity_table_absent"].append({"tier": tier, "table": t})
    rows = lambda t: ident_[t].get("rows", [])  # noqa: E731
    bindings: dict[str, list] = {}
    for r in rows("asset_binding"):
        bindings.setdefault(r["asset_id"], []).append(r["identity"])
    identities = {r["identity"] for r in rows("asset_identity")}
    conflict_assets = {r["asset_id"] for r in rows(CONFLICT_TABLE)}
    for r in rows(CONFLICT_TABLE):
        if r["asset_id"] in pair_assets:
            predicted_seen.append({"tier": tier, "asset_id": r["asset_id"],
                                   "declaration": r.get("declaration")})
        else:
            c["conflict_unpredicted"].append({"tier": tier, "asset_id": r["asset_id"],
                                              "declaration": r.get("declaration")})
    decl = at["asset_declaration"]
    declared = sorted({r["asset_id"] for r in decl.get("rows", []) if r.get("asset_id") is not None})
    if decl.get("present") and "uii" not in decl["columns"]:
        unchecked.append(f"{tier}: uii count not readable, asset_declaration has no uii column")
    alias_by = {}
    for r in rows("asset_alias"):
        alias_by.setdefault((r["identity"], r["value"]), []).append(r["scheme"])
    declared_rows = {r["asset_id"]: r for r in decl.get("rows", []) if r.get("asset_id") is not None}
    for a in declared:
        bound = bindings.get(a, [])
        if not bound:
            if a not in conflict_assets:
                c["declared_without_binding"].append({"tier": tier, "asset_id": a})
            continue
        if len(bound) != 1:
            c["binding_count"].append({"tier": tier, "asset_id": a, "bindings": len(bound)})
            continue
        ident_id = bound[0]
        if ident_id not in identities:
            c["binding_identity_missing"].append({"tier": tier, "asset_id": a, "identity": ident_id})
        carried = {"asset_id": a}
        for kind in SCHEME_OF:
            if declared_rows[a].get(kind):
                carried[kind] = declared_rows[a][kind]
        for kind, value in sorted(carried.items()):
            schemes = alias_by.get((ident_id, value), [])
            n = sum(1 for s in schemes if (s == SCHEME_OF[kind] if kind in SCHEME_OF
                                           else s not in NOT_ASSET_ID_SCHEMES))
            if n != 1:
                c["alias_rows"].append({"tier": tier, "asset_id": a, "alias": kind,
                                        "value": value, "rows": n})
    bound_identities = {i for v in bindings.values() for i in v}
    for i in sorted(identities - bound_identities):
        c["identity_without_binding"].append({"tier": tier, "identity": i})


def step_compare(args) -> int:
    out = pathlib.Path(args.out)
    before, after = load(out, "before.json"), load(out, "after.json")
    pred = load(out, "prediction.json")
    if pred["before_sha256"] != sha256_file(out / "before.json"):
        raise Refusal("prediction.json was written for a different before.json")
    if before.get("phase") != "before" or after.get("phase") != "after":
        raise Refusal("before.json or after.json is in the wrong phase")
    gone = sorted(set(before["tiers"]) - set(after["tiers"]))
    if gone:
        raise Refusal("after.json lacks tiers read before: " + ", ".join(gone), {"tiers": gone})
    refuse_if_exists(out, ["compare.json", "compare.md"])
    c, unchecked, predicted_conflicts = classify(before, after, pred)
    diffs = {k: c[k] for k in DIFF_ORDER if c[k]}
    verdict = "diff" if diffs else ("unchecked" if unchecked else "match")
    report = {"at": _now(), "verdict": verdict, "diffs": diffs, "unchecked": unchecked,
              "predicted_conflicts_seen": predicted_conflicts}
    write_new(out, "compare.json", report)
    md = [f"# Verdict: {verdict}", ""]
    for k in DIFF_ORDER:
        if c[k]:
            md += [f"## {k} ({len(c[k])})", ""] + [f"- {compact(x)}" for x in c[k]] + [""]
    if unchecked:
        md += ["## Unchecked (this is not a pass)", ""] + [f"- {u}" for u in unchecked] + [""]
    if predicted_conflicts:
        md += ["## Predicted conflicts seen", ""] + [f"- {compact(x)}" for x in predicted_conflicts] + [""]
    write_new(out, "compare.md", "\n".join(md) + "\n")
    print(f"compare: {verdict}")
    return EXIT_DIFF if diffs else (EXIT_UNCHECKED if unchecked else EXIT_OK)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="step", required=True)
    rd = sub.add_parser("read")
    rd.add_argument("--phase", required=True, choices=("before", "after"))
    rd.add_argument("--helm-dir", required=True)
    rd.add_argument("--context", required=True)
    rd.add_argument("-n", "--namespace", required=True)
    rd.add_argument("--store", action="append", default=[], help="TIER=POD[/DATABASE]")
    rd.add_argument("--db-user", help="psql -U; omitted, the pod's own default applies")
    rd.add_argument("--broker-pod")
    rd.add_argument("--group")
    rd.add_argument("--topic")
    rd.add_argument("--out", required=True)
    pr = sub.add_parser("predict")
    pr.add_argument("--out", required=True)
    cp = sub.add_parser("compare")
    cp.add_argument("--out", required=True)
    return ap


def main(argv: list[str] | None = None, run=default_run) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.step == "read":
            return step_read(args, run)
        return {"predict": step_predict, "compare": step_compare}[args.step](args)
    except Refusal as r:
        print(f"REFUSED: {r.reason}", file=sys.stderr)
        if r.state:
            print(jdump(r.state), file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
