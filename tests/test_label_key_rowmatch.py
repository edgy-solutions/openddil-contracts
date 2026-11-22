"""Offline tests for scripts/label_key_rowmatch.py.

Nothing here touches a cluster or a host. The store is a fake runner that
refuses any statement that is not a SELECT; the PEP and the metrics endpoint
are a fake GET. DESIGN-2026-11-06-adr0055-compatibility-slice.md section 4.3.

The fake store's trigger is the Python key reference (lk1), standing in for the
SQL function. The SQL function itself is tested against the same vector table
in the stack's migration test, against a real postgres.
"""
import json
import pathlib
import re
import sys
import urllib.request
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "lib" / "python"))

import label_key_rowmatch as rm  # noqa: E402
import migrate_site_declarations as mig  # noqa: E402
from openddil_labels import canonical_lk1, compile_lk1  # noqa: E402

POLICY = "example.policy"
VECTORS = ROOT / "lib" / "python" / "openddil_labels" / "vectors" / "lk1.json"


# --------------------------------------------------------------------------
# The key: fixed vectors
# --------------------------------------------------------------------------

def test_vectors_match_the_shared_table():
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert len(vectors) >= 18
    for v in vectors:
        assert rm.key_of(v["policy_id"], v["originator_nation"], v["releasable_to"]) == v["label_key"], v["name"]
        assert canonical_lk1(v["policy_id"], v["originator_nation"], v["releasable_to"]) == v["canonical"]


def test_the_brief_vectors():
    k = rm.key_of
    assert k(POLICY, "ATL", []) != k(POLICY, "ATL", None)          # {ATL}/{} vs {ATL}/NULL
    assert k(POLICY, "ATL", ["BDR", "ATL"]) == k(POLICY, "ATL", ["ATL", "BDR", "ATL"])
    assert k(POLICY, None, ["BDR"]) is None                          # NULL originator
    assert k(POLICY, None, None) is None
    assert k(POLICY, "AT", None) is None                             # two-letter originator
    assert k(POLICY, "ATL", ["BD"]) is None                          # two-letter release value
    assert k(None, "ATL", None) is None                              # no policy row


def test_vector_names_cover_the_brief():
    names = {v["name"] for v in json.loads(VECTORS.read_text(encoding="utf-8"))}
    assert {"atl_absent", "atl_empty", "atl_bdr_atl", "atl_atl_bdr_atl", "no_originator_absent"} <= names


# --------------------------------------------------------------------------
# Admission per label against the predicate's truth table
# --------------------------------------------------------------------------

FINDING4 = ("(originator_nation IS NOT NULL AND originator_nation IN ('ATL', 'BDR'))"
            " OR (releasable_to IS NOT NULL AND releasable_to && ARRAY['ATL', 'BDR']::text[])")


def test_predicate_text_is_findings_4():
    assert rm.predicate_sql(["ATL", "BDR"]) == FINDING4
    assert rm.predicate_sql([]) == "false"
    assert "O'x" not in rm.predicate_sql(["ATL"])
    assert rm.sql_str("O'x") == "'O''x'"


TRUTH = [  # originator, release, nations, admitted by today's predicate
    ("ATL", None, ["ATL"], True),
    ("ATL", None, ["BDR"], False),
    ("ATL", [], ["BDR"], False),
    ("ATL", ["BDR"], ["BDR"], True),
    ("BDR", ["ATL"], ["ATL", "CYM"], True),
    (None, ["BDR"], ["BDR"], True),        # Finding 5: served today
    (None, None, ["BDR"], False),
    ("ATL", ["BDR"], [], False),
]


@pytest.mark.parametrize("orig,rel,nations,want", TRUTH)
def test_predicate_truth_table(orig, rel, nations, want):
    assert rm.predicate_admits(orig, rel, nations) is want


@pytest.mark.parametrize("orig,rel,nations,want", TRUTH)
def test_label_admits_matches_predicate_where_a_key_exists(orig, rel, nations, want):
    got = compile_lk1(POLICY, orig, rel)
    if got is None:
        # No originator: no key, so no label to admit. The one exception.
        assert orig is None
        return
    assert rm.label_admits(got[1], nations) is want


def test_label_admits_never_raises_and_admitted_keys_are_sorted():
    assert rm.label_admits({}, ["ATL"]) is False
    reg = [{"label_key": k, "label": b} for k, b in
           (compile_lk1(POLICY, o, r) for o, r in (("ATL", None), ("BDR", ["ATL"]), ("CYM", [])))]
    keys = rm.admitted_keys(reg, ["ATL"])
    assert keys == sorted(keys) and len(keys) == 2
    assert rm.admitted_keys(reg, ["ATL"]) == rm.admitted_keys(reg, ["ATL"])


def test_nations_are_checked_and_sorted():
    assert rm.check_nations(["BDR", "ATL", "ATL"]) == ["ATL", "BDR"]
    with pytest.raises(rm.Refusal):
        rm.check_nations(["AT"])
    with pytest.raises(rm.Refusal):
        rm.check_nations(["ATL'; DROP TABLE x;--"])


def test_seventeen_tables_once():
    assert len(rm.TABLES) == 17 == len(set(rm.TABLES))


# --------------------------------------------------------------------------
# A fake world: a store that only answers SELECT, a PEP that only answers GET
# --------------------------------------------------------------------------

class World:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.policy = POLICY
        self.on = False
        self.rows = {t: [] for t in rm.TABLES}
        self.rows["inventory_items"] = [
            {"id": "r1", "orig": "ATL", "rel": ["BDR"]},
            {"id": "r2", "orig": "BDR", "rel": None},
            {"id": "r3", "orig": "ATL", "rel": []},
            {"id": "r4", "orig": None, "rel": ["BDR"]},      # Finding 5
            {"id": "r5", "orig": None, "rel": None},
        ]
        self.pep_add, self.pep_drop = {}, {}
        self.reg_override = None
        self.gate = 10
        self.sql, self.urls = [], []
        self.nations = {"cookie-a": ["ATL"], "cookie-b": ["BDR", "CYM"]}
        for name, cookie in (("a", "cookie-a"), ("b", "cookie-b")):
            (tmp_path / f"s-{name}").write_text(f"\n  {cookie}  \nsecond line never read\n")

    # the trigger, standing in for the SQL function
    def key(self, r):
        if r.get("bypass") or not self.policy:
            return None
        return rm.key_of(self.policy, r["orig"], r["rel"])

    def registry(self):
        if self.reg_override is not None:
            return self.reg_override
        seen = {}
        for rows in self.rows.values():
            for r in rows:
                k = self.key(r)
                if k:
                    seen[k] = compile_lk1(self.policy, r["orig"], r["rel"])[1]
        return seen

    # ---- psql
    def run(self, argv):
        assert argv[0] == "kubectl" and argv[argv.index("--context") + 1] == "test-ctx"
        sql = argv[-1]
        # every query runs after the session is made read only, in the same psql
        assert argv[-4:-1] == ["-c", "SET default_transaction_read_only = on", "-c"], argv
        self.sql.append(sql)
        assert sql.lstrip().upper().startswith(("SELECT", "WITH")), sql
        if "to_regclass" in sql:
            return "t\n"
        if sql.startswith("SELECT policy_id FROM label_policy"):
            return f"{self.policy}\n" if self.policy else ""
        if "information_schema.columns" in sql:
            return "originator_nation\nreleasable_to\nlabel_key\nlabel\nid\n"
        if "pg_index" in sql:
            return "id\n"
        if sql.startswith("SELECT label_key, label::text FROM label_registry"):
            return "".join(f"{k}\t{json.dumps(b)}\n" for k, b in sorted(self.registry().items()))
        table = re.search(r'FROM "(\w+)"', sql)
        rows = self.rows[table.group(1)] if table else []
        if sql.startswith("SELECT count(*), "):
            keyed = [r for r in rows if self.key(r)]
            keyless = [r for r in rows if not self.key(r)]
            noorig = [r for r in keyless if not r["orig"]]
            rest = [r for r in keyless if r["orig"]]
            f5 = [r for r in rows if r["orig"] is None and r["rel"]]
            nopol = len(rest) if not self.policy else 0
            vals = [len(rows), len(keyed), len(keyless), len(noorig), nopol, len(rest) - nopol, len(f5)]
            return "\t".join(map(str, vals)) + "\n"
        where = sql.split(" WHERE ", 1)[1]
        if "releasable_to::text FROM" in sql:
            return "".join(f'["{r["id"]}"]\t{{{",".join(r["rel"])}}}\n' for r in rows
                           if r["orig"] is None and r["rel"])
        m = re.search(r"IN \(((?:'[A-Z]+'(?:, )?)+)\)", where)
        ns = re.findall(r"[A-Z]+", m.group(1)) if m else []
        pred = lambda r: rm.predicate_admits(r["orig"], r["rel"], ns)  # noqa: E731
        reg = self.registry()
        if where.startswith("label_key IN (SELECT"):
            ok = {k for k, b in reg.items() if rm.label_admits(b, ns)}
            sel = [r for r in rows if self.key(r) in ok]
        elif where.startswith("label_key IS NULL AND"):
            sel = [r for r in rows if not self.key(r) and pred(r)]
        elif where.startswith("(originator_nation IS NULL AND releasable_to IS NOT NULL"):
            sel = [r for r in rows if r["orig"] is None and r["rel"] and pred(r)]
        else:
            sel = [r for r in rows if pred(r)]
        return "".join(f'["{r["id"]}"]\n' for r in sel)

    # ---- HTTP
    def get(self, url, headers):
        self.urls.append(url)
        if url.startswith("http://metrics"):
            return 200, {}, f'egress_decisions_total{{decision="allow"}} {self.gate}\n'.encode()
        q = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
        cookie = headers["Cookie"]
        ns = self.nations[cookie]
        hdr = {"electric-handle": "h1", "electric-offset": "9_0"}
        if q["offset"] != "-1":
            return 200, hdr, json.dumps([{"headers": {"control": "up-to-date"}}]).encode()
        ids = set()
        reg = self.registry()
        for r in self.rows[q["table"]]:
            k = self.key(r)
            if self.on:
                ok = k is not None and rm.label_admits(reg.get(k, {}), ns)
            else:
                ok = rm.predicate_admits(r["orig"], r["rel"], ns)
            if ok:
                ids.add(r["id"])
        ids |= self.pep_add.get((cookie, q["table"]), set())
        ids -= self.pep_drop.get((cookie, q["table"]), set())
        msgs = [{"key": f'"public"."{q["table"]}"/"{i}"', "value": {"id": i},
                 "headers": {"operation": "insert"}} for i in sorted(ids)]
        return 200, {"electric-handle": "h1", "electric-offset": "0_0"}, json.dumps(msgs).encode()


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(rm, "run_guard", lambda helm: "test-ctx")
    return World(tmp_path)


def argv(w, step, phase=None, metrics=True, extra=()):
    out = ["read", "--phase", phase] if step == "read" else [step]
    if step == "read":
        out += ["--helm-dir", "helm", "--context", "test-ctx", "-n", "ns", "--store", "hq=pod-0/db",
                "--viewer", "viewer-a", "--session", str(w.tmp / "s-a"), "--nations", "ATL",
                "--viewer", "viewer-b", "--session", str(w.tmp / "s-b"), "--nations", "BDR,CYM",
                "--route", "assets=/v1/shape?table=inventory_items", "--pep", "http://pep"]
        if metrics:
            out += ["--metrics-url", "http://metrics/m", "--gate-metric", "egress_decisions_total"]
    out += list(extra) + ["--out", str(w.tmp / "out")]
    return out


def go(w, *a, **kw):
    return rm.main(argv(w, *a, **kw), run=w.run, get=w.get)


def full_run(w, after_edit=None, metrics=True, plant=()):
    assert go(w, "read", "before", metrics) == (0 if metrics else 4)
    assert go(w, "predict", extra=plant) == 0
    w.on = True
    if after_edit:
        after_edit(w)
    return go(w, "read", "after", metrics), go(w, "compare")


def out_file(w, name):
    return json.loads((w.tmp / "out" / name).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Read-only
# --------------------------------------------------------------------------

def test_store_refuses_anything_but_one_select():
    st = rm.Store("c", "n", "pod", "db", "u", run=lambda a: "")
    for bad in ("INSERT INTO x VALUES (1)", "UPDATE x SET a=1", "DELETE FROM x", "DROP TABLE x",
                "SELECT 1; DROP TABLE x", "COPY x TO STDOUT", ""):
        with pytest.raises(rm.Refusal):
            st.psql(bad)
    assert st.psql("SELECT 1") == ""


def test_every_statement_in_a_full_run_is_a_select(world):
    full_run(world)
    assert world.sql
    assert all(s.lstrip().upper().startswith(("SELECT", "WITH")) for s in world.sql)
    assert not any(re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE)\b", s)
                   for s in world.sql)


def test_http_get_sends_get_only(monkeypatch):
    seen = []

    class R:
        status = 200
        headers = {"A": "b"}

        def read(self):
            return b"x"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen", lambda req, **k: seen.append(req) or R())
    rm.http_get("http://x/y", {"Cookie": "c"})
    assert [r.get_method() for r in seen] == ["GET"] and seen[0].data is None


def test_source_names_no_write_verb():
    src = (ROOT / "scripts" / "label_key_rowmatch.py").read_text(encoding="utf-8")
    assert re.findall(r"method=\"(\w+)\"", src) == ["GET"]
    assert "\r" not in src


# --------------------------------------------------------------------------
# The PEP read
# --------------------------------------------------------------------------

def test_pep_read_follows_past_the_snapshot_and_records_handle_and_offset(world):
    got = rm.read_shape(world.get, "http://pep", "/v1/shape?table=inventory_items", "cookie-a",
                        {"inventory_items": ["id"]})
    assert got["up_to_date"] and got["handle"] == "h1" and got["offset"] == "9_0"
    assert got["ids"] == ['inventory_items:["r1"]', 'inventory_items:["r3"]']
    assert len(world.urls) == 2 and "offset=-1" in world.urls[0] and "offset=0_0" in world.urls[1]
    assert not any("live=true" in u for u in world.urls)


def test_pep_read_refuses_when_up_to_date_never_comes():
    def get(url, headers):
        return 200, {"electric-handle": "h", "electric-offset": "1_0"}, b"[]"
    with pytest.raises(rm.Refusal) as e:
        rm.read_shape(get, "http://pep", "/p", "c", {})
    assert e.value.state["handle"] == "h"


def test_pep_read_refuses_on_non_200():
    with pytest.raises(rm.Refusal):
        rm.read_shape(lambda u, h: (500, {}, b""), "http://pep", "/p", "c", {})


def test_session_file_first_line_only(world):
    assert mig.first_line(world.tmp / "s-a") == "cookie-a"


# --------------------------------------------------------------------------
# Steps: prediction hashing, refusals, the classes
# --------------------------------------------------------------------------

def test_match_run_exits_0_and_names_the_exception_first(world):
    a, c = full_run(world)
    assert (a, c) == (0, 0)
    md = (world.tmp / "out" / "compare.md").read_text(encoding="utf-8")
    assert md.startswith("Matches to the row, except 1 rows, reason `no_originator`:")
    assert 'inventory_items ["r4"]' in md.splitlines()[2]
    rep = out_file(world, "compare.json")
    assert rep["verdict"] == "match" and rep["diffs"] == {}
    assert [x["id"] for x in rep["predicted_exception"] if x["where"] == "pep"] == ['inventory_items:["r4"]']
    owed = out_file(world, "owed-declarations.json")
    assert [(o["table"], o["pk"], o["reason"]) for o in owed] == [("inventory_items", '["r4"]', "no_originator")]


def test_before_file_has_the_counts_and_the_viewer_sets(world):
    go(world, "read", "before")
    b = out_file(world, "before.json")
    t = b["tiers"]["hq"]["tables"]["inventory_items"]
    assert t["total"] == 5 and t["keyed"] == 3 and t["keyless"] == 2 and t["finding5"] == 1
    assert t["keyless_reasons"] == {"no_originator": 2, "no_policy": 0, "format": 0}
    v = b["tiers"]["hq"]["viewers"]["viewer-b"]["tables"]["inventory_items"]
    assert v["by_predicate"] == ['["r1"]', '["r2"]', '["r4"]']
    assert v["by_key"] == ['["r1"]', '["r2"]']
    assert b["tiers"]["hq"]["no_originator_rows"] == [
        {"table": "inventory_items", "pk": '["r4"]', "releasable_to": "{BDR}"}]
    assert b["pep"]["viewer-a"]["assets"]["handle"] == "h1"
    assert len(b["tiers"]["hq"]["tables"]) == 17


def test_prediction_carries_the_before_hash_and_the_rows(world):
    go(world, "read", "before")
    go(world, "predict", extra=["--plant-author", "ATL", "--plant-release", "BDR"])
    p = out_file(world, "prediction.json")
    assert p["before_sha256"] == rm.sha256_file(world.tmp / "out" / "before.json")
    assert p["exception_rows"][0]["pk"] == '["r4"]'
    assert p["expected_after_ids"]["viewer-b"]["assets"] == ['inventory_items:["r1"]', 'inventory_items:["r2"]']
    assert p["shapes_when_on"]["BDR,CYM"]["assets"]["shapes_minted"] == 1
    assert p["planted_arrival"]["by_nation_set"]["ATL"]["shapes_replaced"] == 1
    assert (world.tmp / "out" / "prediction.md").is_file()


def test_after_phase_refuses_without_a_prediction(world, capsys):
    go(world, "read", "before")
    world.on = True
    assert go(world, "read", "after") == 3
    assert "no prediction.json" in capsys.readouterr().err
    assert not (world.tmp / "out" / "after.json").exists()


def test_after_phase_refuses_when_before_changed(world, capsys):
    go(world, "read", "before")
    go(world, "predict")
    bp = world.tmp / "out" / "before.json"
    bp.write_text(bp.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert go(world, "read", "after") == 3
    assert "different before.json" in capsys.readouterr().err


def test_a_step_never_overwrites(world, capsys):
    go(world, "read", "before")
    assert go(world, "read", "before") == 3
    assert "already exists" in capsys.readouterr().err


def test_predict_refuses_with_no_policy_row(world, capsys):
    world.policy = None
    go(world, "read", "before")
    assert go(world, "predict") == 3
    assert "no label_policy row" in capsys.readouterr().err


def test_no_metrics_url_is_exit_4_unchecked_and_says_so(world, capsys):
    a, c = full_run(world, metrics=False)
    assert (a, c) == (4, 4)
    out = capsys.readouterr().out
    assert "UNCHECKED" in out and "not a pass" in out
    assert out_file(world, "compare.json")["verdict"] == "unchecked"


def test_metrics_url_needs_its_metric_name(world, capsys):
    a = argv(world, "read", "before")
    a.remove("--gate-metric")
    a.remove("egress_decisions_total")
    assert rm.main(a, run=world.run, get=world.get) == 3


def test_extra_id_is_a_diff(world):
    a, c = full_run(world, lambda w: w.pep_add.update({("cookie-a", "inventory_items"): {"r9"}}))
    assert c == 1
    d = out_file(world, "compare.json")["diffs"]
    assert {"where": "pep", "viewer": "viewer-a", "route": "assets", "id": 'inventory_items:["r9"]'} in d["extra_id"]


def test_missing_non_exception_id_is_a_diff(world):
    a, c = full_run(world, lambda w: w.pep_drop.update({("cookie-b", "inventory_items"): {"r2"}}))
    assert c == 1
    d = out_file(world, "compare.json")["diffs"]
    assert [x["id"] for x in d["missing_non_exception_id"]] == ['inventory_items:["r2"]']


def test_keyless_bypass_is_named_first(world):
    # the bypass row exists from the start, so before sees it too
    world.rows["inventory_items"].append({"id": "r6", "orig": "", "rel": ["BDR"]})
    a, c = full_run(world)
    assert c == 1
    rep = out_file(world, "compare.json")
    assert rep["diffs"]["keyless_bypass"][0]["pks"] == ['["r6"]']
    md = (world.tmp / "out" / "compare.md").read_text(encoding="utf-8")
    heads = re.findall(r"^## (\w+)", md, re.M)
    assert heads[0] == "keyless_bypass"
    # a row that is Finding 5's class is not a bypass
    assert all('["r4"]' not in x["pks"] for x in rep["diffs"]["keyless_bypass"])


def test_row_the_trigger_missed_is_a_bypass(world):
    world.rows["inventory_items"].append({"id": "r7", "orig": "ATL", "rel": None, "bypass": True})
    a, c = full_run(world)
    assert c == 1
    assert out_file(world, "compare.json")["diffs"]["keyless_bypass"][0]["pks"] == ['["r7"]']


def test_gate_count_moved_is_a_diff(world):
    a, c = full_run(world, lambda w: setattr(w, "gate", 11))
    assert c == 1
    assert "gate_count_moved" in out_file(world, "compare.json")["diffs"]


def test_a_new_no_originator_row_is_a_diff(world):
    def add(w):
        w.rows["asset_cm_state"].append({"id": "n1", "orig": None, "rel": ["CYM"]})
    a, c = full_run(world, add)
    assert c == 1
    assert out_file(world, "compare.json")["diffs"]["unpredicted_no_originator_row"][0]["table"] == "asset_cm_state"


def test_registry_disagreeing_with_lk1_is_a_diff(world):
    def corrupt(w):
        reg = dict(w.registry())
        k = sorted(reg)[0]
        reg[k] = dict(reg[k], policy="other.policy")
        w.reg_override = reg
    a, c = full_run(world, corrupt)
    assert c == 1
    assert "registry_disagrees" in out_file(world, "compare.json")["diffs"]


def test_store_strong_check_flags_a_missing_key_row(world):
    def lose(w):
        w.reg_override = {k: b for k, b in w.registry().items() if b["dims"]["nation"]["author"] != "BDR"}
    a, c = full_run(world, lose)
    assert c == 1
    d = out_file(world, "compare.json")["diffs"]
    assert any(x["where"] == "store" for x in d["missing_non_exception_id"])


# --------------------------------------------------------------------------
# Guard and exit codes
# --------------------------------------------------------------------------

def test_guard_78_halts(world, monkeypatch):
    monkeypatch.setattr(rm, "run_guard", mig.run_guard)
    helm = world.tmp / "helm" / "scripts" / "lib"
    helm.mkdir(parents=True)
    (helm / "require-cluster.sh").write_text("exit 78\n")
    monkeypatch.setattr(mig.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=78, stdout="", stderr="no cluster named\n"))
    a = argv(world, "read", "before")
    a[a.index("--helm-dir") + 1] = str(world.tmp / "helm")
    with pytest.raises(SystemExit) as e:
        rm.main(a, run=world.run, get=world.get)
    assert e.value.code == 78
    assert not world.sql and not world.urls


def test_guard_context_must_be_the_one_passed(world, monkeypatch, capsys):
    monkeypatch.setattr(rm, "run_guard", lambda h: "other-ctx")
    assert go(world, "read", "before") == 3
    assert "other-ctx" in capsys.readouterr().err
    assert not world.sql


def test_exit_codes_are_the_migration_scripts():
    assert (rm.EXIT_OK, rm.EXIT_DIFF, rm.EXIT_REFUSED, rm.EXIT_UNCHECKED, rm.EXIT_GUARD) == (0, 1, 3, 4, 78)


def test_migration_not_applied_is_a_refusal_naming_the_state(world, capsys):
    orig = world.run
    world.run = lambda a: "f\n" if "to_regclass" in a[-1] else orig(a)
    assert rm.main(argv(world, "read", "before"), run=world.run, get=world.get) == 3
    assert "migration not applied" in capsys.readouterr().err


def test_viewer_without_session_is_refused(world):
    a = argv(world, "read", "before")
    i = a.index("--nations")
    del a[i:i + 2]
    assert rm.main(a, run=world.run, get=world.get) == 3
