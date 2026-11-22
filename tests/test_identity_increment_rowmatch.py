"""Offline tests for scripts/identity_increment_rowmatch.py.

Nothing here touches a cluster. The store is a fake runner that answers the
script's queries from an in-memory world and asserts, on every psql call, that
the read-only SET comes first, that there is exactly one SELECT or WITH, and
that the call sits under a remote timeout. DESIGN-2026-11-08 section 4.3.
"""
import copy
import hashlib
import json
import pathlib
import re
import sys
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import identity_increment_rowmatch as rm  # noqa: E402
import migrate_site_declarations as mig  # noqa: E402

SET_SQL = "SET default_transaction_read_only = on"
RPK_OK = """GROUP        projector-decl
COORDINATOR  1
STATE        Stable
BALANCER     range
MEMBERS      1
TOTAL-LAG    0

TOPIC     PARTITION  CURRENT-OFFSET  LOG-START-OFFSET  LOG-END-OFFSET  LAG  MEMBER-ID  CLIENT-ID  HOST
decl      0          10              0                 10              0    m-1        c-1        10.0.0.1
decl      1          7               0                 7               0    m-1        c-1        10.0.0.1
other     0          3               0                 9               6    m-1        c-1        10.0.0.1
"""


# --------------------------------------------------------------------------
# The world and the fake runner
# --------------------------------------------------------------------------

def table(cols, rows, pk=None):
    return {"cols": cols, "rows": rows, "pk": pk or [cols[0]]}


def before_tier():
    return {
        "asset_registry": table(["asset_id", "last_observed_at"], [
            {"asset_id": "A1", "last_observed_at": "2026-11-01T00:00:00Z"},
            {"asset_id": "A2", "last_observed_at": "2026-11-02T00:00:00Z"}]),
        "egress_delivered_events": table(["event_id", "episode_id", "asset_id"], [
            {"event_id": "ev1", "episode_id": "ep1", "asset_id": "A1"},
            {"event_id": "ev2", "episode_id": "ep1", "asset_id": "A1"},
            {"event_id": "ev3", "episode_id": "ep2", "asset_id": "A2"}]),
        "failure_episodes": table(["episode_id", "detected_at", "asset_id"], [
            {"episode_id": "ep1", "detected_at": "2026-11-04T00:00:00Z", "asset_id": "A1"},
            {"episode_id": "ep1", "detected_at": "2026-11-03T00:00:00Z", "asset_id": "A1"}],
            pk=["episode_id", "detected_at"]),
        "asset_cm_state": {"cols": ["asset_id", "discrepancies", "manual_discrepancies"], "pk": ["asset_id"], "rows": [
            {"asset_id": "A1", "discrepancies": [{"discrepancy_id": "d1"}], "manual_discrepancies": [{"discrepancy_id": "m1"}]},
            {"asset_id": "A2", "discrepancies": [{"discrepancy_id": "ep2", "detected_at": "2026-11-05T00:00:00Z"}], "manual_discrepancies": []}]},
        "asset_declaration": table(["asset_id", "serial", "uii"], [
            {"asset_id": "A1", "serial": "S1", "uii": "U1"},
            {"asset_id": "A2", "serial": "S2", "uii": None}]),  # uii column: the exact-prediction case
        "asset_correlation": table(["asset_id", "serial"], [
            {"asset_id": "A1", "serial": "S1"}, {"asset_id": "A2", "serial": "S2"}],
            pk=["asset_id"]),
    }


def after_tier():
    t = before_tier()
    t["asset_identity"] = table(["identity"], [{"identity": "i1"}, {"identity": "i2"}])
    t["alias_scheme"] = table(["scheme"], [{"scheme": s} for s in ("asset_id", "serial", "identity", "uii")])
    t["asset_binding"] = table(["asset_id", "identity"], [
        {"asset_id": "A1", "identity": "i1"}, {"asset_id": "A2", "identity": "i2"}])
    t["asset_alias"] = table(["scheme", "value", "identity"], [
        {"scheme": "asset_id", "value": "A1", "identity": "i1"},
        {"scheme": "serial", "value": "S1", "identity": "i1"},
        {"scheme": "uii", "value": "U1", "identity": "i1"},
        {"scheme": "asset_id", "value": "A2", "identity": "i2"},
        {"scheme": "serial", "value": "S2", "identity": "i2"}], pk=["scheme", "value"])
    t["identity_equivalence"] = table(["merged", "survivor"], [])
    t["identity_conflict"] = table(["declaration", "asset_id", "identities"], [], pk=["declaration"])
    t["__era_fn"] = True
    return t


class World:
    def __init__(self, tmp):
        self.tmp = tmp
        self.tiers = {"tier-a": before_tier()}
        self.rpk = RPK_OK
        self.calls = []          # psql statements, in order
        self.remote = []         # every argv
        self.era = lambda asset, ts: 1

    # -- the runner ---------------------------------------------------------
    def run(self, argv):
        self.remote.append(argv)
        assert argv[:2] == ["kubectl", "--context"]
        i = argv.index("--") + 1
        assert argv[i] == "timeout" and argv[i + 1].isdigit(), "remote command must be under a timeout"
        if argv[i + 2] == "rpk":
            if isinstance(self.rpk, Exception):
                raise self.rpk
            return self.rpk
        assert argv[i + 2] == "psql"
        cs = [argv[k + 1] for k, a in enumerate(argv) if a == "-c"]
        assert len(cs) == 2 and cs[0] == SET_SQL, "the read-only SET must come first"
        sql = cs[1]
        assert re.match(r"(?is)\s*(select|with)\b", sql), sql
        bare = rm._LITERAL.sub("''", sql)
        assert ";" not in bare, "one statement per call"
        for bad in ("insert ", "update ", "delete ", "drop ", "alter ", "truncate ", "create "):
            assert bad not in bare.lower(), sql
        pod = argv[argv.index("exec") + 1]
        self.calls.append(sql)
        return "SET\n" + self.answer(self.tiers[pod.removeprefix("pod-")], sql)

    def answer(self, tier, sql):
        if "to_regprocedure" in sql:
            return "t\n" if tier.get("__era_fn") else "f\n"
        m = re.search(r"to_regclass\('public\.(\w+)'\)", sql)
        if m:
            return "t\n" if m.group(1) in tier else "f\n"
        m = re.search(r"table_name='(\w+)'", sql)
        if m:
            return "".join(c + "\n" for c in tier[m.group(1)]["cols"])
        if "indisprimary" in sql:
            t = re.search(r'public\."(\w+)"', sql).group(1)
            return "".join(c + "\n" for c in tier[t]["pk"])
        if "to_jsonb(ARRAY[" in sql:
            t = re.search(r'FROM "(\w+)"$', sql).group(1)
            cols = re.findall(r'"(\w+)"::text', sql)
            return "".join(json.dumps([str(r[c]) for c in cols]) + "\n" for r in tier[t]["rows"])
        if "jsonb_array_elements" in sql:
            col = re.search(r's\."(\w+)"\)', sql).group(1)
            got = [[r["asset_id"], d.get("discrepancy_id") if isinstance(d, dict) else None,
                    d.get("detected_at") if isinstance(d, dict) else None]
                   for r in tier["asset_cm_state"]["rows"] for d in r[col]]
            return json.dumps(got) + "\n"
        if "HAVING count(DISTINCT" in sql:
            by = {}
            for r in tier["asset_correlation"]["rows"]:
                by.setdefault(r["serial"], set()).add(r["asset_id"])
            return json.dumps([{"serial": s, "asset_ids": sorted(a)} for s, a in by.items() if len(a) > 1]) + "\n"
        if "asset_id_era(a" in sql:
            vals = re.findall(r"\('((?:[^']|'')*)', '((?:[^']|'')*)', '((?:[^']|'')*)'\)", sql)
            return json.dumps([[k, self.era(a, t)] for k, a, t in vals]) + "\n"
        m = re.search(r'jsonb_agg\(to_jsonb\(t\)\).*FROM \(SELECT (.*) FROM "(\w+)"(?: WHERE .*)?\) t$', sql)
        if m:
            cols = re.findall(r'"(\w+)"', m.group(1))
            rows = [{c: r[c] for c in cols} for r in tier[m.group(2)]["rows"]]
            return json.dumps(rows) + "\n"
        raise AssertionError(f"the fake does not know: {sql}")


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(rm, "run_guard", lambda helm: "test-ctx")
    w = World(tmp_path)
    w.out = tmp_path / "out"
    return w


def argv(world, step, phase=None, *extra):
    a = [step]
    if step == "read":
        a += ["--phase", phase, "--helm-dir", str(world.tmp / "helm"), "--context", "test-ctx",
              "-n", "ns", "--store", "tier-a=pod-tier-a/db1"]
    a += ["--out", str(world.out)]
    return a + list(extra)


def go(world, step, phase=None, *extra):
    return rm.main(argv(world, step, phase, *extra), run=world.run)


CONSUMER = ("--broker-pod", "broker-0", "--group", "projector-decl", "--topic", "decl")


def flow(world, after_tier_, consumer=True):
    """before, predict, then the after world, then compare; returns compare's code."""
    assert go(world, "read", "before") == 0
    assert go(world, "predict") == 0
    world.tiers = {"tier-a": after_tier_}
    assert go(world, "read", "after", *(CONSUMER if consumer else ())) == 0
    return go(world, "compare")


def verdict(world):
    return json.loads((world.out / "compare.json").read_text())


def first_diff_class(world):
    md = (world.out / "compare.md").read_text()
    return re.search(r"^## (\w+)", md, re.M).group(1)


# --------------------------------------------------------------------------
# before, predict, hashing
# --------------------------------------------------------------------------

def test_before_reads_every_id_set_and_counts(world):
    assert go(world, "read", "before") == 0
    b = json.loads((world.out / "before.json").read_text())["tiers"]["tier-a"]
    assert sorted(b["asset_registry"]["rows"]) == ["A1", "A2"]
    assert b["egress_delivered_events"]["events"] == {"ev1": "A1", "ev2": "A1", "ev3": "A2"}
    assert b["egress_delivered_events"]["episodes"]["ep1"] == {
        "asset_id": "A1", "detected_at": "2026-11-03T00:00:00Z", "detected_at_source": "failure_episodes"}
    assert b["asset_cm_state"]["discrepancies"] == {"d1": "A1", "ep2": "A2"}
    assert b["asset_cm_state"]["manual_discrepancies"] == {"m1": "A1"}
    assert b["asset_declaration"]["count"] == 2 and len(b["asset_declaration"]["keys"]) == 2
    assert b["asset_correlation"]["count"] == 2
    assert "identity" not in b


def test_absent_table_and_column_are_recorded_not_errors(world):
    t = world.tiers["tier-a"]
    del t["asset_correlation"]
    t["asset_registry"]["cols"].remove("last_observed_at")
    assert go(world, "read", "before") == 0
    b = json.loads((world.out / "before.json").read_text())["tiers"]["tier-a"]
    assert b["asset_correlation"] == {"present": False}
    assert b["asset_registry"]["missing_columns"] == ["last_observed_at"]
    assert go(world, "predict") == 0


def test_prediction_hashes_before_json_and_names_serial_pairs(world):
    world.tiers["tier-a"]["asset_correlation"]["rows"].append({"asset_id": "A3", "serial": "S1"})
    world.tiers["tier-a"]["asset_correlation"]["pk"] = ["asset_id"]
    assert go(world, "read", "before") == 0
    assert go(world, "predict") == 0
    pred = json.loads((world.out / "prediction.json").read_text())
    want = hashlib.sha256((world.out / "before.json").read_bytes()).hexdigest()
    assert pred["before_sha256"] == want
    pairs = pred["identity_conflicts"]["except_serial_pairs"]
    assert pairs == [{"tier": "tier-a", "serial": "S1", "asset_ids": ["A1", "A3"], "pairs": [["A1", "A3"]]}]
    assert pred["era"]["expected"] == 1
    assert "A1 / A3" in (world.out / "prediction.md").read_text()


def episodes_before(world):
    assert go(world, "read", "before") == 0
    b = json.loads((world.out / "before.json").read_text())["tiers"]["tier-a"]
    return b["egress_delivered_events"]["episodes"]


def test_era_time_from_failure_episodes_is_the_minimum(world):
    e = episodes_before(world)["ep1"]
    assert (e["detected_at"], e["detected_at_source"]) == ("2026-11-03T00:00:00Z", "failure_episodes")


def test_era_time_from_a_discrepancy_element(world):
    e = episodes_before(world)["ep2"]
    assert (e["detected_at"], e["detected_at_source"]) == ("2026-11-05T00:00:00Z", "asset_cm_state.discrepancy")


def test_era_time_from_neither_leaves_the_episode_unchecked(world):
    t = world.tiers["tier-a"]
    t["egress_delivered_events"]["rows"].append({"event_id": "ev9", "episode_id": "ep9", "asset_id": "A1"})
    e = episodes_before(world)["ep9"]
    assert e["detected_at"] is None and e["detected_at_source"] is None
    assert go(world, "predict") == 0
    world.tiers = {"tier-a": after_tier()}
    world.tiers["tier-a"]["egress_delivered_events"]["rows"].append(
        {"event_id": "ev9", "episode_id": "ep9", "asset_id": "A1"})
    assert go(world, "read", "after", *CONSUMER) == 0
    assert go(world, "compare") == 4
    assert "1 episodes have no asset_id" in verdict(world)["unchecked"][0]


def test_uii_count_is_not_readable_never_zero(world):
    world.tiers["tier-a"]["asset_declaration"]["cols"].remove("uii")
    for r in world.tiers["tier-a"]["asset_declaration"]["rows"]:
        del r["uii"]
    assert go(world, "read", "before") == 0
    assert go(world, "predict") == 0
    pred = json.loads((world.out / "prediction.json").read_text())
    got = pred["declared_at_before_read"]["tier-a"]
    assert got["uii_aliases"].startswith("not readable from the store") and got["uii_aliases"] != 0
    assert got["serial_aliases"] == 2


def test_after_refuses_without_prediction(world, capsys):
    assert go(world, "read", "before") == 0
    n = len(world.calls)
    assert go(world, "read", "after") == 3
    assert "no prediction.json" in capsys.readouterr().err
    assert len(world.calls) == n and not (world.out / "after.json").exists()


def test_after_refuses_mismatched_before_hash(world, capsys):
    assert go(world, "read", "before") == 0
    assert go(world, "predict") == 0
    bp = world.out / "before.json"
    bp.write_text(bp.read_text() + " ", encoding="utf-8")
    n = len(world.calls)
    assert go(world, "read", "after") == 3
    assert "different before.json" in capsys.readouterr().err
    assert len(world.calls) == n


def test_compare_refuses_mismatched_hash(world, capsys):
    assert flow(world, after_tier()) == 0
    bp = world.out / "before.json"
    bp.write_text(bp.read_text() + " ", encoding="utf-8")
    (world.out / "compare.json").unlink()
    (world.out / "compare.md").unlink()
    assert go(world, "compare") == 3


# --------------------------------------------------------------------------
# compare: a match, then each class
# --------------------------------------------------------------------------

def test_match_exits_0_and_checks_era_through_the_function(world):
    assert flow(world, after_tier()) == 0
    assert verdict(world)["verdict"] == "match"
    assert any("asset_id_era(a, t::timestamptz)" in s for s in world.calls)
    a = json.loads((world.out / "after.json").read_text())
    assert a["tiers"]["tier-a"]["era"]["results"] == {"ep1": 1, "ep2": 1}
    assert a["consumer_position"]["status"] == "checked"


def test_class_missing_id(world):
    t = after_tier()
    t["egress_delivered_events"]["rows"] = [r for r in t["egress_delivered_events"]["rows"] if r["event_id"] != "ev3"]
    assert flow(world, t) == 1
    assert first_diff_class(world) == "missing_id"
    assert {"tier": "tier-a", "kind": "event_id", "id": "ev3"} in verdict(world)["diffs"]["missing_id"]


def test_class_changed_asset_id(world):
    t = after_tier()
    ep2 = {"discrepancy_id": "ep2", "detected_at": "2026-11-05T00:00:00Z"}
    t["asset_cm_state"]["rows"][0]["discrepancies"] = [ep2]
    t["asset_cm_state"]["rows"][1]["discrepancies"] = [{"discrepancy_id": "d1"}]
    assert flow(world, t) == 1
    assert first_diff_class(world) == "changed_asset_id"
    assert verdict(world)["diffs"]["changed_asset_id"][0]["after"] == "A2"


def test_class_projector_count_moved(world):
    t = after_tier()
    t["asset_correlation"]["rows"].append({"asset_id": "A9", "serial": "S9"})
    assert flow(world, t) == 1
    assert first_diff_class(world) == "projector_count_moved"
    d = verdict(world)["diffs"]["projector_count_moved"][0]
    assert (d["table"], d["before"], d["after"]) == ("asset_correlation", 2, 3)


def test_class_declared_without_binding(world):
    t = after_tier()
    t["asset_binding"]["rows"] = t["asset_binding"]["rows"][:1]
    t["asset_identity"]["rows"] = t["asset_identity"]["rows"][:1]
    t["asset_alias"]["rows"] = t["asset_alias"]["rows"][:3]
    assert flow(world, t) == 1
    assert verdict(world)["diffs"]["declared_without_binding"] == [{"tier": "tier-a", "asset_id": "A2"}]


def test_class_identity_without_binding(world):
    t = after_tier()
    t["asset_identity"]["rows"].append({"identity": "i3"})
    assert flow(world, t) == 1
    assert first_diff_class(world) == "identity_without_binding"
    assert verdict(world)["diffs"]["identity_without_binding"] == [{"tier": "tier-a", "identity": "i3"}]


def test_class_alias_row_missing(world):
    t = after_tier()
    t["asset_alias"]["rows"] = [r for r in t["asset_alias"]["rows"] if r["scheme"] != "serial" or r["value"] != "S1"]
    assert flow(world, t) == 1
    d = verdict(world)["diffs"]["alias_rows"][0]
    assert (d["asset_id"], d["alias"], d["rows"]) == ("A1", "serial", 0)


def test_class_unpredicted_conflict(world):
    t = after_tier()
    t["identity_conflict"]["rows"].append({"declaration": "h", "asset_id": "A1", "identities": ["i1", "i2"]})
    assert flow(world, t) == 1
    assert first_diff_class(world) == "conflict_unpredicted"


def test_predicted_conflict_is_not_a_diff(world):
    bt = world.tiers["tier-a"]
    bt["asset_correlation"]["rows"].append({"asset_id": "A3", "serial": "S1"})
    t = after_tier()
    t["asset_correlation"]["rows"].append({"asset_id": "A3", "serial": "S1"})
    t["asset_declaration"]["rows"].append({"asset_id": "A3", "serial": "S1", "uii": None})
    bt["asset_declaration"]["rows"].append({"asset_id": "A3", "serial": "S1", "uii": None})
    t["identity_conflict"]["rows"].append({"declaration": "h", "asset_id": "A3", "identities": ["i1", "i9"]})
    assert flow(world, t) == 0
    assert verdict(world)["predicted_conflicts_seen"][0]["asset_id"] == "A3"


def test_class_era_not_one(world):
    world.era = lambda a, t: 2
    assert flow(world, after_tier()) == 1
    assert first_diff_class(world) == "era_not_one"


def test_era_function_missing_is_a_diff(world):
    t = after_tier()
    del t["__era_fn"]
    assert flow(world, t) == 1
    assert verdict(world)["diffs"]["era_not_one"][0]["reason"] == "asset_id_era does not exist"


def test_identity_table_absent_after_is_a_diff(world):
    t = after_tier()
    del t["identity_equivalence"]
    assert flow(world, t) == 1
    assert {"tier": "tier-a", "table": "identity_equivalence"} in verdict(world)["diffs"]["identity_table_absent"]


def test_diffs_come_first_in_the_report(world):
    t = after_tier()
    t["asset_identity"]["rows"].append({"identity": "i3"})
    t["asset_registry"]["rows"].pop()
    assert flow(world, t, consumer=False) == 1
    assert first_diff_class(world) == "missing_id"
    md = (world.out / "compare.md").read_text()
    assert md.index("## missing_id") < md.index("## identity_without_binding") < md.index("## Unchecked")


def drop_uii(*tiers):
    for x in tiers:
        x["asset_declaration"]["cols"].remove("uii")
        for r in x["asset_declaration"]["rows"]:
            del r["uii"]


def test_no_uii_column_with_uii_alias_rows_matches_and_lists_them(world):
    t = after_tier()
    drop_uii(world.tiers["tier-a"], t)
    assert flow(world, t) == 0
    v = verdict(world)
    assert v["unchecked"] == [] and v["diffs"] == {}
    assert v["not_predicted"][0]["value"] == "U1"
    assert "Not predicted" in (world.out / "compare.md").read_text()


def test_uii_column_present_missing_uii_alias_is_a_diff(world):
    t = after_tier()
    t["asset_alias"]["rows"] = [r for r in t["asset_alias"]["rows"] if r["scheme"] != "uii"]
    assert flow(world, t) == 1
    assert verdict(world)["diffs"]["alias_rows"][0]["alias"] == "uii"


def test_asset_id_scheme_is_matched_by_name_and_unknown_schemes_are_listed(world):
    t = after_tier()
    for r in t["asset_alias"]["rows"]:
        if r["value"] == "A1":
            r["scheme"] = "other_scheme"
    assert flow(world, t) == 1
    d = verdict(world)["diffs"]["alias_rows"][0]
    assert (d["asset_id"], d["alias"], d["rows"]) == ("A1", "asset_id", 0)
    assert verdict(world)["unknown_scheme"][0]["scheme"] == "other_scheme"
    assert "unknown scheme" in (world.out / "compare.md").read_text()


# --------------------------------------------------------------------------
# The consumer position
# --------------------------------------------------------------------------

def test_unchecked_consumer_exits_4_and_says_so(world, capsys):
    assert flow(world, after_tier(), consumer=False) == 4
    assert "consumer position unchecked" in verdict(world)["unchecked"][0]
    assert verdict(world)["verdict"] == "unchecked"
    assert not any("rpk" in a for argv_ in world.remote for a in argv_)


def test_unparseable_rpk_output_is_unchecked(world):
    world.rpk = "unexpected\nbanner\n"
    assert flow(world, after_tier()) == 4
    a = json.loads((world.out / "after.json").read_text())
    assert a["consumer_position"]["status"] == "unchecked"


def test_diff_outranks_unchecked(world):
    t = after_tier()
    t["asset_identity"]["rows"].append({"identity": "i3"})
    assert flow(world, t, consumer=False) == 1


def test_lag_above_zero_refuses_and_writes_no_after(world, capsys):
    world.rpk = RPK_OK.replace("decl      1          7               0                 7               0",
                               "decl      1          7               0                 9               2")
    assert go(world, "read", "before") == 0
    assert go(world, "predict") == 0
    world.tiers = {"tier-a": after_tier()}
    assert go(world, "read", "after", *CONSUMER) == 3
    assert "2 behind" in capsys.readouterr().err
    assert not (world.out / "after.json").exists()


def test_parse_group_lag_reads_the_named_topic_only():
    assert rm.parse_group_lag(RPK_OK, "decl") == 0
    assert rm.parse_group_lag(RPK_OK, "other") == 6
    assert rm.parse_group_lag(RPK_OK, "missing") is None
    assert rm.parse_group_lag("TOPIC PARTITION LAG\nx 0 -\n", "x") is None


def test_consumer_args_go_together(world, capsys):
    assert go(world, "read", "before") == 0
    assert go(world, "predict") == 0
    assert go(world, "read", "after", "--group", "g") == 3


# --------------------------------------------------------------------------
# Guard, exit codes, read only
# --------------------------------------------------------------------------

def test_guard_78_halts(world, monkeypatch):
    monkeypatch.setattr(rm, "run_guard", mig.run_guard)
    helm = world.tmp / "helm" / "scripts" / "lib"
    helm.mkdir(parents=True)
    (helm / "require-cluster.sh").write_text("exit 78\n")
    monkeypatch.setattr(mig.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=78, stdout="", stderr="no cluster named\n"))
    with pytest.raises(SystemExit) as e:
        go(world, "read", "before")
    assert e.value.code == 78
    assert not world.remote


def test_guard_context_must_be_the_one_passed(world, monkeypatch, capsys):
    monkeypatch.setattr(rm, "run_guard", lambda h: "other-ctx")
    assert go(world, "read", "before") == 3
    assert "other-ctx" in capsys.readouterr().err
    assert not world.remote


def test_exit_codes_are_the_migration_scripts():
    assert (rm.EXIT_OK, rm.EXIT_DIFF, rm.EXIT_REFUSED, rm.EXIT_UNCHECKED, rm.EXIT_GUARD) == (0, 1, 3, 4, 78)


def test_every_psql_call_is_read_only_and_there_were_many(world):
    assert flow(world, after_tier()) == 0
    assert len(world.calls) > 30          # the fake asserted the SET and one SELECT on each
    assert all(c.lstrip().upper().startswith(("SELECT", "WITH")) for c in world.calls)


def test_store_refuses_anything_but_one_select():
    st = rm.Store("c", "n", "p", None, None, run=lambda a: "")
    for bad in ("DELETE FROM x", "SELECT 1; DROP TABLE x", "UPDATE x SET a=1", "", "INSERT INTO x VALUES (1)"):
        with pytest.raises(rm.Refusal):
            st.psql(bad)
    st.psql("SELECT ';' AS semicolon_in_a_literal")       # a literal's semicolon is not a second statement
    st.psql("WITH e AS (SELECT 1) SELECT * FROM e")


def test_store_argv_has_timeout_and_the_set_first():
    seen = []
    st = rm.Store("c", "n", "p", "d", "u", run=lambda a: seen.append(a) or "")
    st.psql("SELECT 1")
    a = seen[0]
    assert a[a.index("--") + 1:a.index("--") + 3] == ["timeout", "60"]
    assert a.index("-c") < len(a) and a[a.index("-c") + 1] == SET_SQL
    assert a[-2] == "-c" and a[-1] == "SELECT 1"


@pytest.mark.parametrize("step,phase,make", [
    ("read", "before", None), ("predict", None, None), ("read", "after", None), ("compare", None, None)])
def test_no_step_overwrites_its_files(world, step, phase, make):
    assert go(world, "read", "before") == 0
    assert go(world, "predict") == 0
    world.tiers = {"tier-a": after_tier()}
    assert go(world, "read", "after", *CONSUMER) == 0
    assert go(world, "compare") == 0
    snap = {p.name: p.read_bytes() for p in world.out.iterdir()}
    assert {"before.json", "prediction.json", "prediction.md", "after.json",
            "compare.json", "compare.md"} <= set(snap)
    n = len(world.calls)
    assert go(world, step, phase, *(CONSUMER if phase == "after" else ())) == 3
    assert {p.name: p.read_bytes() for p in world.out.iterdir()} == snap
    if step == "read":
        assert len(world.calls) == n         # refused before any store call


def test_partial_outputs_are_not_left_when_compare_would_overwrite(world):
    assert flow(world, after_tier()) == 0
    (world.out / "compare.md").unlink()
    snap = (world.out / "compare.json").read_bytes()
    assert go(world, "compare") == 3
    assert (world.out / "compare.json").read_bytes() == snap and not (world.out / "compare.md").exists()


def test_files_are_lf_and_the_script_names_no_deployment_value():
    src = (ROOT / "scripts" / "identity_increment_rowmatch.py").read_bytes()
    assert b"\r" not in src
    assert b"\r" not in pathlib.Path(__file__).read_bytes()
