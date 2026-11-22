#!/usr/bin/env python3
"""Row-match acceptance for the label_key compatibility slice.

DESIGN-2026-11-06-adr0055-compatibility-slice.md section 4. ADR-0055 section 4.
Four steps, each its own invocation, each writing its files under --out and
stopping:

    python scripts/label_key_rowmatch.py read --phase before --helm-dir ../openddil-helm --context CTX -n NS --store TIER=POD[/DB] --viewer NAME --session FILE --nations ATL,BDR --route NAME=PATH --pep URL [--metrics-url URL --gate-metric NAME] --out DIR
    python scripts/label_key_rowmatch.py predict --out DIR [--plant-author ATL --plant-release BDR,CYM]
    python scripts/label_key_rowmatch.py read --phase after  (same arguments as before) --out DIR
    python scripts/label_key_rowmatch.py compare --out DIR

READ ONLY. The only SQL is SELECT (refused in Store.psql otherwise); the only
HTTP is GET. The switch flip, the backfill, the label_policy row and every
declaration are a person's. Nothing is written to any store; compare writes
owed-declarations.json for a person to act on.

EXIT CODES, as migrate_site_declarations.py: 0 match, 1 diff, 3 refused,
4 unchecked, 78 guard. A refusal names the state and halts the run. No step
overwrites a file an earlier step wrote.

THE ONE DECLARED EXCEPTION (Finding 5, ruled 2026-11-07): a row with NULL
originator_nation and a non-empty releasable_to is served today and withheld
under the key. Reason `no_originator`. Each is listed by row and owed a
declaration. Every other difference is a diff.

UNTESTED AGAINST A CLUSTER. The pure parts and the faked runner/HTTP paths are
tested offline (tests/test_label_key_rowmatch.py).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "lib" / "python"))

# Imported, not copied: the exit codes, the Refusal, the guard, the session-file
# reader, the file hash and the clock are the migration script's, so the two
# scripts cannot drift. Its `canonical` is declaration-specific and is not used.
from migrate_site_declarations import (  # noqa: E402
    EXIT_DIFF, EXIT_GUARD, EXIT_OK, EXIT_REFUSED, EXIT_UNCHECKED,
    Refusal, _now, first_line, run_guard, sha256_file,
)
from openddil_labels import lk1  # noqa: E402

assert EXIT_GUARD == 78

# DESIGN-2026-11-06-adr0055-compatibility-slice.md, Finding 1: the seventeen
# tables that carry originator_nation and releasable_to. One list; a change to
# the spec's list is a change here.
TABLES = (
    "inventory_items", "asset_cm_state", "asset_logistics_status",
    "telemetry_latest_state", "tactical_events", "asset_telemetry_windows",
    "parts_availability", "asset_capability_state", "asset_element_telemetry",
    "asset_element_state", "intake_records", "effector_launch",
    "effector_resupply", "munition_track", "asset_declaration",
    "asset_correlation", "asset_fielding",
)
assert len(TABLES) == 17

NATION_RE = re.compile(r"^[A-Z]{3}$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
IDENT_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
REASON = "no_originator"
MAX_REQUESTS = 50


def jdump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def compact(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Pure: the predicate, admission per label, the key reference
# --------------------------------------------------------------------------

def check_nations(nations: list[str]) -> list[str]:
    for n in nations:
        if not NATION_RE.match(n):
            raise Refusal(f"nation {n!r} is not three capital letters")
    return sorted(set(nations))


def sql_str(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def predicate_sql(nations: list[str]) -> str:
    """Finding 4's predicate, as pep.py policy_predicate() renders it."""
    if not nations:
        return "false"
    lst = ", ".join(sql_str(n) for n in nations)
    arr = "ARRAY[" + ", ".join(sql_str(n) for n in nations) + "]::text[]"
    return ("(originator_nation IS NOT NULL AND originator_nation IN (" + lst + "))"
            " OR "
            "(releasable_to IS NOT NULL AND releasable_to && " + arr + ")")


def predicate_admits(originator, release, nations) -> bool:
    """Finding 4's predicate, evaluated on one row's two columns."""
    ns = set(nations)
    if not ns:
        return False
    if originator is not None and originator in ns:
        return True
    return release is not None and bool(set(release) & ns)


def label_admits(body: dict, nations) -> bool:
    """Section 2.3: the predicate on the label body. author in N, or release
    not null and release meeting N."""
    try:
        nation = body["dims"]["nation"]
        return predicate_admits(nation["author"], nation["release"], nations)
    except (KeyError, TypeError):
        return False


def key_of(policy_id, originator, release):
    """The lk1 key for the two columns, or None. The Python reference."""
    got = lk1.compile_lk1(policy_id, originator, release)
    return None if got is None else got[0]


def admitted_keys(registry: list[dict], nations) -> list[str]:
    """Keys the registry admits for a viewer, sorted in C order (section 2.3)."""
    return sorted(r["label_key"] for r in registry if label_admits(r["label"], nations))


# --------------------------------------------------------------------------
# Store: SELECTs on postgres, through a runner that can be faked
# --------------------------------------------------------------------------

def default_run(argv: list[str]) -> str:
    p = subprocess.run(argv, capture_output=True, text=True)
    if p.returncode != 0:
        raise Refusal(f"{' '.join(argv[:6])}: {p.stderr.strip()}")
    return p.stdout


class Store:
    def __init__(self, context: str, namespace: str, pod: str, database: str,
                 user: str, run=default_run):
        self.pod, self.run = pod, run
        self.argv = ["kubectl", "--context", context, "-n", namespace, "exec", pod,
                     "--", "psql", "-U", user, "-d", database,
                     "-v", "ON_ERROR_STOP=1", "-tA", "-F", "\t"]

    def psql(self, sql: str) -> str:
        head = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
        if head not in ("SELECT", "WITH") or ";" in sql.rstrip().rstrip(";"):
            raise Refusal("this script only reads: refused a statement that is "
                          f"not one SELECT: {sql[:60]!r}")
        # The head check above is the script's own rule; the store enforces it
        # too. A WITH can wrap a data-modifying statement, so every query runs
        # in a session whose transactions are read only.
        return self.run(self.argv + ["-c", "SET default_transaction_read_only = on",
                                     "-c", sql])

    def rows(self, sql: str) -> list[list[str]]:
        return [ln.split("\t") for ln in self.psql(sql).splitlines() if ln.strip()]


def pk_expr(cols: list[str]) -> str:
    return "to_jsonb(ARRAY[" + ", ".join(f'"{c}"::text' for c in cols) + "])::text"


def norm_pk(text: str) -> str:
    return compact(json.loads(text))


def pk_id(table: str, values: list) -> str:
    return f"{table}:{compact([str(v) for v in values])}"


def table_sql(table: str) -> str:
    if table not in TABLES:
        raise Refusal(f"{table} is not one of the seventeen tables")
    return f'"{table}"'


def read_policy(st: Store) -> dict:
    for rel in ("label_policy", "label_registry"):
        if st.psql(f"SELECT to_regclass('public.{rel}') IS NOT NULL").strip() != "t":
            raise Refusal(f"migration not applied: no {rel} table at {st.pod}")
    rows = st.rows("SELECT policy_id FROM label_policy")
    return {"present": bool(rows), "policy_id": rows[0][0] if rows else None}


def read_table_shape(st: Store, table: str) -> list[str]:
    cols = {r[0] for r in st.rows(
        "SELECT column_name FROM information_schema.columns WHERE table_schema='public' "
        f"AND table_name='{table}'")}
    need = {"originator_nation", "releasable_to", "label_key", "label"}
    if not need <= cols:
        raise Refusal(f"migration not applied: {table} at {st.pod} lacks "
                      + ", ".join(sorted(need - cols)))
    pk = [r[0] for r in st.rows(
        "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
        "AND a.attnum = ANY(i.indkey) WHERE i.indisprimary AND "
        f"i.indrelid = 'public.\"{table}\"'::regclass "
        "ORDER BY array_position(i.indkey::int2[], a.attnum)")]
    if not pk:
        raise Refusal(f"{table} at {st.pod} has no primary key")
    for c in pk:
        if not IDENT_RE.match(c):
            raise Refusal(f"{table}: primary key column {c!r} is not a plain name")
    return pk


NO_ORIG = "(originator_nation IS NULL OR originator_nation = '')"
F5 = "(originator_nation IS NULL AND releasable_to IS NOT NULL AND cardinality(releasable_to) > 0)"


def read_counts(st: Store, table: str) -> dict:
    t = table_sql(table)
    pol = "(SELECT count(*) FROM label_policy) > 0"
    sql = (
        "SELECT count(*), "
        "count(*) FILTER (WHERE label_key IS NOT NULL), "
        "count(*) FILTER (WHERE label_key IS NULL), "
        f"count(*) FILTER (WHERE label_key IS NULL AND {NO_ORIG}), "
        f"count(*) FILTER (WHERE label_key IS NULL AND NOT {NO_ORIG} AND NOT {pol}), "
        f"count(*) FILTER (WHERE label_key IS NULL AND NOT {NO_ORIG} AND {pol}), "
        f"count(*) FILTER (WHERE {F5}) FROM {t}")
    r = [int(x) for x in st.rows(sql)[0]]
    return {"total": r[0], "keyed": r[1], "keyless": r[2],
            "keyless_reasons": {"no_originator": r[3], "no_policy": r[4], "format": r[5]},
            "finding5": r[6]}


def key_filter_sql(nations: list[str]) -> str:
    """Rows admitted by the key against label_registry, computed on postgres."""
    if not nations:
        return "false"
    lst = ", ".join(sql_str(n) for n in nations)
    arr = "ARRAY[" + ", ".join(sql_str(n) for n in nations) + "]::text[]"
    return (
        "label_key IN (SELECT label_key FROM label_registry WHERE "
        f"(label->'dims'->'nation'->>'author') IN ({lst}) OR "
        "(jsonb_typeof(label->'dims'->'nation'->'release') = 'array' AND "
        "EXISTS (SELECT 1 FROM jsonb_array_elements_text(label->'dims'->'nation'->'release') r "
        f"WHERE r = ANY({arr}))))")


def pks(st: Store, table: str, pk: list[str], where: str) -> list[str]:
    sql = f"SELECT {pk_expr(pk)} FROM {table_sql(table)} WHERE {where}"
    return sorted({norm_pk(r[0]) for r in st.rows(sql)})


def read_viewer_table(st: Store, table: str, pk: list[str], nations: list[str]) -> dict:
    pred = predicate_sql(nations)
    return {
        "by_predicate": pks(st, table, pk, f"({pred})"),
        "by_key": pks(st, table, pk, key_filter_sql(nations)),
        "keyless_admitted": pks(st, table, pk, f"label_key IS NULL AND ({pred})"),
        "finding5_admitted": pks(st, table, pk, f"{F5} AND ({pred})"),
    }


def read_registry(st: Store) -> dict:
    reg = [{"label_key": k, "label": json.loads(b)}
           for k, b in st.rows("SELECT label_key, label::text FROM label_registry ORDER BY 1")]
    bad = [r["label_key"] for r in reg if not lk1.verify(r["label_key"], r["label"])]
    return {"rows": reg, "n": len(reg), "disagree_with_lk1": bad}


def read_store(st: Store, viewers: dict[str, list[str]]) -> dict:
    policy = read_policy(st)
    reg = read_registry(st)
    tables, pkcols, f5rows = {}, {}, []
    for t in TABLES:
        pk = read_table_shape(st, t)
        pkcols[t] = pk
        tables[t] = read_counts(st, t)
        for r in st.rows(f"SELECT {pk_expr(pk)}, releasable_to::text FROM {table_sql(t)} WHERE {F5} "
                         "ORDER BY 1"):
            f5rows.append({"table": t, "pk": norm_pk(r[0]), "releasable_to": r[1]})
    out_v = {}
    for name, nations in viewers.items():
        keys = admitted_keys(reg["rows"], nations)
        out_v[name] = {
            "nations": nations,
            "admitted_keys": {"count": len(keys), "sha256": sha256_text("\n".join(keys))},
            "tables": {t: read_viewer_table(st, t, pkcols[t], nations) for t in TABLES},
        }
    return {"policy": policy, "tables": tables, "pk_cols": pkcols,
            "no_originator_rows": f5rows, "viewers": out_v,
            "registry": {"n": reg["n"], "disagree_with_lk1": reg["disagree_with_lk1"]}}


# --------------------------------------------------------------------------
# PEP and metrics: HTTP GET only
# --------------------------------------------------------------------------

def http_get(url: str, headers: dict, ca: str | None = None) -> tuple[int, dict, bytes]:
    ctx = ssl.create_default_context(cafile=ca) if ca else None
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=60) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read() or b""


_KEY_TABLE = re.compile(r'^"[^"]*"\."([^"]+)"')


def row_id(key: str | None, value: dict, pk_cols: dict) -> str:
    m = _KEY_TABLE.match(key or "")
    if m and m.group(1) in pk_cols and all(c in value for c in pk_cols[m.group(1)]):
        return pk_id(m.group(1), [value[c] for c in pk_cols[m.group(1)]])
    return f"key:{key}"


def read_shape(get, base: str, path: str, cookie: str, pk_cols: dict) -> dict:
    """Follow one route to up-to-date: a snapshot, then the log by the returned
    handle and offset. Never live=true. Never one offset=-1 GET alone."""
    sep = "&" if "?" in path else "?"
    handle, offset, rows, nbytes, restarted = None, "-1", {}, 0, False
    for _ in range(MAX_REQUESTS):
        q = f"{sep}offset={offset}" + (f"&handle={urllib.parse.quote(handle)}" if handle else "")
        status, hdr, body = get(base + path + q, {"Cookie": cookie})
        if status == 409 and not restarted:
            restarted, handle, offset, rows, nbytes = True, None, "-1", {}, 0
            continue
        if status != 200:
            raise Refusal(f"{base}{path}: answered {status}",
                          {"handle": handle, "offset": offset})
        nbytes += len(body)
        up = False
        for msg in json.loads(body or b"[]"):
            h = msg.get("headers") or {}
            if h.get("control") == "up-to-date":
                up = True
                continue
            if h.get("control") == "must-refetch":
                raise Refusal(f"{path}: must-refetch", {"handle": handle, "offset": offset})
            value = msg.get("value")
            if not isinstance(value, dict) and h.get("operation") != "delete":
                continue
            rid = row_id(msg.get("key"), value or {}, pk_cols)
            if h.get("operation") == "delete":
                rows.pop(rid, None)
            else:
                rows[rid] = True
        new_h = hdr.get("electric-handle") or hdr.get("electric-shape-id")
        new_o = hdr.get("electric-offset")
        if not new_h or new_o is None:
            raise Refusal(f"{path}: response missing handle or offset header",
                          {"handle": handle, "offset": offset})
        used = offset
        handle, offset = new_h, new_o
        if up and used != "-1":
            return {"ids": sorted(rows), "handle": handle, "offset": offset,
                    "up_to_date": True, "bytes": nbytes}
    raise Refusal(f"{path}: did not reach up-to-date in {MAX_REQUESTS} requests",
                  {"handle": handle, "offset": offset})


def read_metric(get, url: str, name: str) -> dict:
    status, _, body = get(url, {})
    if status != 200:
        raise Refusal(f"{url}: answered {status}")
    out = {}
    for m in re.finditer(rf"^{re.escape(name)}(\{{[^}}]*\}})? (\S+)$", body.decode(), re.M):
        out[m.group(1) or ""] = float(m.group(2))
    if not out:
        raise Refusal(f"{url}: no series named {name}")
    return out


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


def load(out: pathlib.Path, name: str) -> dict:
    p = out / name
    if not p.is_file():
        raise Refusal(f"no {name} in {out}")
    return json.loads(p.read_text(encoding="utf-8"))


def parse_stores(items: list[str]) -> dict:
    stores = {}
    for it in items:
        m = re.fullmatch(r"([^=/]+)=([^/]+)(?:/(.+))?", it)
        if not m:
            raise Refusal(f"--store {it!r}: want TIER=POD[/DATABASE]")
        stores[m.group(1)] = (m.group(2), m.group(3) or "openddil")
    if not stores:
        raise Refusal("no --store given")
    return stores


def parse_viewers(args) -> dict:
    if not (len(args.viewer) == len(args.session) == len(args.nations)) or not args.viewer:
        raise Refusal("each --viewer needs its own --session and --nations")
    for v in args.viewer:
        if not NAME_RE.match(v):
            raise Refusal(f"viewer name {v!r} is not a plain name")
    return {v: check_nations([n for n in ns.split(",") if n])
            for v, ns in zip(args.viewer, args.nations)}


def parse_routes(items: list[str]) -> dict:
    routes = {}
    for it in items:
        name, _, path = it.partition("=")
        if not name or not path.startswith("/"):
            raise Refusal(f"--route {it!r}: want NAME=/path?query")
        routes[name] = path
    if not routes:
        raise Refusal("no --route given")
    return routes


def step_read(args, run=default_run, get=http_get) -> int:
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.phase == "after":
        before_p = out / "before.json"
        pred_p = out / "prediction.json"
        if not pred_p.is_file():
            raise Refusal("no prediction.json: predict is a separate step, before read --phase after")
        if not before_p.is_file():
            raise Refusal("no before.json")
        pred = json.loads(pred_p.read_text(encoding="utf-8"))
        if pred.get("before_sha256") != sha256_file(before_p):
            raise Refusal("prediction.json was written for a different before.json")
    viewers = parse_viewers(args)
    routes = parse_routes(args.route)
    stores = parse_stores(args.store)
    sessions = {v: first_line(pathlib.Path(s)) for v, s in zip(args.viewer, args.session)}
    if bool(args.metrics_url) != bool(args.gate_metric):
        raise Refusal("--metrics-url and --gate-metric go together: the metric name is "
                      "the forwarder's and is not built in")
    ctx = run_guard(pathlib.Path(args.helm_dir))
    if ctx != args.context:
        raise Refusal(f"the guard asserted {ctx}, this run was told {args.context}")
    tiers = {t: read_store(Store(ctx, args.namespace, pod, db, args.db_user, run), viewers)
             for t, (pod, db) in sorted(stores.items())}
    pk_cols = {}
    for t in tiers.values():
        pk_cols.update(t["pk_cols"])
    pep = {}
    for v in viewers:
        pep[v] = {r: read_shape(get, args.pep.rstrip("/"), p, sessions[v], pk_cols)
                  for r, p in sorted(routes.items())}
    doc = {"phase": args.phase, "at": _now(), "context": ctx, "namespace": args.namespace,
           "pep": pep, "tiers": tiers, "gate": None, "gate_checked": False,
           "shape_census": shape_census(viewers, pep)}
    if args.metrics_url:
        doc["gate"] = {u: read_metric(get, u, args.gate_metric) for u in args.metrics_url}
        doc["gate_checked"] = True
    write_new(out, f"{args.phase}.json", doc)
    if not doc["gate_checked"]:
        print("read: UNCHECKED. No --metrics-url, so the gate's decision counts were not "
              "read. This is not a pass.")
        return EXIT_UNCHECKED
    return EXIT_OK


def shape_census(viewers: dict, pep: dict) -> dict:
    """Shapes and bytes per admitted set. CHOICE: the spec says 'Electric's own
    figures' and names no source, so this is what the PEP reads returned: one
    shape per (nation set, route), bytes as the log bytes read."""
    sets = {}
    for v, ns in viewers.items():
        k = ",".join(ns)
        for r, d in pep[v].items():
            e = sets.setdefault(k, {}).setdefault(r, {"handles": [], "bytes": d["bytes"]})
            e["handles"].append(d["handle"])
    return {"source": "pep-read", "by_nation_set": sets}


def f5_ids(before: dict) -> dict:
    """Per viewer, the ids of the Finding 5 rows the predicate admits."""
    out = {}
    for tier in before["tiers"].values():
        for v, d in tier["viewers"].items():
            s = out.setdefault(v, set())
            for t, x in d["tables"].items():
                s.update(pk_id(t, json.loads(p)) for p in x["finding5_admitted"])
    return {v: sorted(s) for v, s in out.items()}


def no_policy_tiers(doc: dict) -> list[str]:
    return sorted(t for t, d in doc["tiers"].items() if not d["policy"]["present"])


def step_predict(args) -> int:
    out = pathlib.Path(args.out)
    before = load(out, "before.json")
    if before.get("phase") != "before":
        raise Refusal("before.json is not a before-phase file")
    missing = no_policy_tiers(before)
    if missing:
        raise Refusal("no label_policy row at " + ", ".join(missing)
                      + ": every key is NULL, and the switch is not safe to call", {"tiers": missing})
    ex_ids = f5_ids(before)
    exc_rows = [dict(r, tier=t) for t, d in sorted(before["tiers"].items())
                for r in d["no_originator_rows"]]
    expected = {v: {r: sorted(set(d["ids"]) - set(ex_ids.get(v, [])))
                    for r, d in routes.items()} for v, routes in before["pep"].items()}
    sets = {}
    for v, routes in before["pep"].items():
        ns = ",".join(next(iter(before["tiers"].values()))["viewers"][v]["nations"])
        for r, d in routes.items():
            sets.setdefault(ns, {})[r] = {"shapes_minted": 1, "bytes": d["bytes"]}
    plant = None
    if args.plant_author:
        author = check_nations([args.plant_author])[0]
        rel = check_nations([x for x in (args.plant_release or "").split(",") if x])
        body = {"dims": {"nation": {"author": author, "release": rel}}}
        replaced = {ns: {"admits": label_admits(body, ns.split(",")),
                         "shapes_replaced": len(r), "old_bytes": sum(x["bytes"] for x in r.values())}
                    for ns, r in sets.items()}
        for d in replaced.values():
            if not d["admits"]:
                d["shapes_replaced"], d["old_bytes"] = 0, 0
        plant = {"author": author, "release": rel, "by_nation_set": replaced,
                 "made_by": "a person, through a real path; never an INSERT"}
    pred = {"at": _now(), "before_sha256": sha256_file(out / "before.json"),
            "reason": REASON, "exception_rows": exc_rows, "exception_ids": ex_ids,
            "expected_after_ids": expected, "shapes_when_on": sets,
            "planted_arrival": plant if plant else "not predicted: no --plant-author given",
            "gate_unchanged": True}
    write_new(out, "prediction.json", pred)
    md = [f"# Prediction (before.json sha256 {pred['before_sha256']})", "",
          f"Declared exception: matches to the row, except {len(exc_rows)} rows, reason `{REASON}`.", ""]
    md += [f"- {r['tier']} {r['table']} {r['pk']} releasable_to {r['releasable_to']}" for r in exc_rows]
    md += ["", "For each viewer and route the after set equals the before set minus the "
           "exception rows that viewer is served today, by id.", "", "## Shapes minted when the switch is on", ""]
    md += [f"- {ns} / {r}: {d['shapes_minted']} shape, about {d['bytes']} bytes"
           for ns, rr in sorted(sets.items()) for r, d in sorted(rr.items())]
    md += ["", "## Planted key arrival", "", compact(pred["planted_arrival"]) if plant else pred["planted_arrival"], ""]
    write_new(out, "prediction.md", "\n".join(md) + "\n")
    return EXIT_OK


def classify(before: dict, after: dict, pred: dict) -> dict:
    """Every difference, by class. Pure."""
    c = {"keyless_bypass": [], "registry_disagrees": [], "extra_id": [],
         "missing_non_exception_id": [], "unpredicted_no_originator_row": [],
         "gate_count_moved": [], "predicted_exception": [], "ok": []}
    predicted = {compact([r["tier"], r["table"], r["pk"]]) for r in pred["exception_rows"]}
    for phase, doc in (("before", before), ("after", after)):
        for tier, td in sorted(doc["tiers"].items()):
            for v, vd in sorted(td["viewers"].items()):
                for t, x in sorted(vd["tables"].items()):
                    bypass = sorted(set(x["keyless_admitted"]) - set(x["finding5_admitted"]))
                    if bypass:
                        c["keyless_bypass"].append({"phase": phase, "tier": tier, "viewer": v,
                                                    "table": t, "pks": bypass})
            if td["registry"]["disagree_with_lk1"]:
                c["registry_disagrees"].append({"phase": phase, "tier": tier,
                                                "keys": td["registry"]["disagree_with_lk1"]})
    for tier, td in sorted(after["tiers"].items()):
        for r in td["no_originator_rows"]:
            if compact([tier, r["table"], r["pk"]]) not in predicted:
                c["unpredicted_no_originator_row"].append(dict(r, tier=tier))
        for v, vd in sorted(td["viewers"].items()):
            for t, x in sorted(vd["tables"].items()):
                want = set(x["by_predicate"]) - set(x["finding5_admitted"])
                got = set(x["by_key"])
                for p in sorted(got - want):
                    c["extra_id"].append({"where": "store", "tier": tier, "viewer": v, "id": pk_id(t, json.loads(p))})
                for p in sorted(set(x["finding5_admitted"]) & set(x["by_predicate"]) - got):
                    c["predicted_exception"].append({"where": "store", "tier": tier, "viewer": v,
                                                     "id": pk_id(t, json.loads(p))})
                for p in sorted((set(x["by_predicate"]) - set(x["finding5_admitted"])) - got):
                    c["missing_non_exception_id"].append({"where": "store", "tier": tier, "viewer": v,
                                                          "id": pk_id(t, json.loads(p))})
    for v, routes in after["pep"].items():
        for r, d in routes.items():
            exp = set(pred["expected_after_ids"].get(v, {}).get(r, []))
            got = set(d["ids"])
            was = set(before["pep"][v][r]["ids"])
            for i in sorted(got - exp):
                c["extra_id"].append({"where": "pep", "viewer": v, "route": r, "id": i})
            for i in sorted(exp - got):
                c["missing_non_exception_id"].append({"where": "pep", "viewer": v, "route": r, "id": i})
            for i in sorted((was - got) & set(pred["exception_ids"].get(v, []))):
                c["predicted_exception"].append({"where": "pep", "viewer": v, "route": r, "id": i})
    if before["gate_checked"] and after["gate_checked"] and before["gate"] != after["gate"]:
        c["gate_count_moved"].append({"before": before["gate"], "after": after["gate"]})
    return c


DIFF_ORDER = ("keyless_bypass", "registry_disagrees", "extra_id", "missing_non_exception_id",
              "unpredicted_no_originator_row", "gate_count_moved")


def step_compare(args) -> int:
    out = pathlib.Path(args.out)
    before, after = load(out, "before.json"), load(out, "after.json")
    pred = load(out, "prediction.json")
    if pred["before_sha256"] != sha256_file(out / "before.json"):
        raise Refusal("prediction.json was written for a different before.json")
    if before.get("phase") != "before" or after.get("phase") != "after":
        raise Refusal("before.json or after.json is in the wrong phase")
    missing = no_policy_tiers(after)
    if missing:
        raise Refusal("no label_policy row at " + ", ".join(missing)
                      + " in the after phase: the switch is not safe to call", {"tiers": missing})
    c = classify(before, after, pred)
    diffs = {k: c[k] for k in DIFF_ORDER if c[k]}
    unchecked = not (before["gate_checked"] and after["gate_checked"])
    rows = pred["exception_rows"]
    report = {"at": _now(), "exception": {"reason": REASON, "rows": rows}, "diffs": diffs,
              "predicted_exception": c["predicted_exception"], "gate_checked": not unchecked,
              "verdict": "diff" if diffs else ("unchecked" if unchecked else "match")}
    write_new(out, "compare.json", report)
    md = [f"Matches to the row, except {len(rows)} rows, reason `{REASON}`:", ""]
    md += [f"- {r['tier']} {r['table']} {r['pk']} releasable_to {r['releasable_to']}" for r in rows]
    md += ["", f"# Verdict: {report['verdict']}", ""]
    for k in DIFF_ORDER:
        if c[k]:
            md += [f"## {k} ({len(c[k])})", ""] + [f"- {compact(x)}" for x in c[k]] + [""]
    if unchecked:
        md += ["The gate's decision counts were not read in both phases. This is not a pass.", ""]
    write_new(out, "compare.md", "\n".join(md) + "\n")
    write_new(out, "owed-declarations.json",
              [{"tier": r["tier"], "table": r["table"], "pk": r["pk"], "releasable_to": r["releasable_to"],
                "reason": REASON, "owed": "a declaration (ADR-0055 section 4)"} for r in rows])
    print(f"compare: {report['verdict']}")
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
    rd.add_argument("--db-user", default="openddil")
    rd.add_argument("--viewer", action="append", default=[])
    rd.add_argument("--session", action="append", default=[])
    rd.add_argument("--nations", action="append", default=[], help="ATL,BDR for the preceding --viewer")
    rd.add_argument("--route", action="append", default=[], help="NAME=/path?query")
    rd.add_argument("--pep", required=True)
    rd.add_argument("--ca-file")
    rd.add_argument("--metrics-url", action="append", default=[])
    rd.add_argument("--gate-metric")
    rd.add_argument("--out", required=True)
    pr = sub.add_parser("predict")
    pr.add_argument("--plant-author")
    pr.add_argument("--plant-release")
    pr.add_argument("--out", required=True)
    cp = sub.add_parser("compare")
    cp.add_argument("--out", required=True)
    return ap


def main(argv: list[str] | None = None, run=default_run, get=http_get) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.step == "read":
            if args.ca_file:
                inner = get
                get = lambda u, h, _i=inner: _i(u, h, args.ca_file)  # noqa: E731
            return step_read(args, run, get)
        return {"predict": step_predict, "compare": step_compare}[args.step](args)
    except Refusal as r:
        print(f"REFUSED: {r.reason}", file=sys.stderr)
        if r.state:
            print(jdump(r.state), file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
