"""Offline tests for scripts/migrate_site_declarations.py.

Only the pure parts: reading sources out of pod specs, translation, overlap,
the census diff, the prediction and its hash check, the session file. The
cluster and HTTP paths have never run, and nothing here pretends otherwise.
"""
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import migrate_site_declarations as m  # noqa: E402

BOX_A = {"south": 10, "west": 10, "north": 20, "east": 20}
BOX_B = {"south": 15, "west": 15, "north": 25, "east": 25}
BOX_FAR = {"south": 30, "west": 30, "north": 40, "east": 40}


def pod(name, env, mounts=(), phase="Running"):
    return {"metadata": {"name": name}, "status": {"phase": phase},
            "spec": {"containers": [{
                "name": "c", "env": [{"name": k, "value": v} for k, v in env.items()],
                "volumeMounts": [{"mountPath": p} for p in mounts]}]}}


def rules(overrides=None, rules_=None):
    return json.dumps({"overrides": overrides or {}, "rules": rules_ or []})


def src(**kw):
    base = {"edges": ["edge-a"], "ingest": {}, "sim": None, "document": {}}
    base.update(kw)
    return base


class SourcesFromPods(unittest.TestCase):
    def test_reads_ingest_rules_per_edge_and_collapses_replicas(self):
        r = rules(rules_=[{"name": "box", "nation": "ATL", "match": {"geofence": BOX_A}}])
        env = {"OPENDDIL_EDGE_ID": "edge-a", "DIS_NATION_RULES": r}
        got = m.sources_from_pods({"items": [pod("i-1", env), pod("i-2", env)]})
        self.assertEqual(got["ingest"], {"edge-a": r})
        self.assertEqual(got["edges"], ["edge-a"])

    def test_two_different_rule_sets_at_one_edge_refuse(self):
        a = {"OPENDDIL_EDGE_ID": "edge-a", "DIS_NATION_RULES": rules()}
        b = {"OPENDDIL_EDGE_ID": "edge-a", "DIS_NATION_RULES": rules({"dis:1:1:1": "ATL"})}
        with self.assertRaises(m.Refusal):
            m.sources_from_pods({"items": [pod("i-1", a), pod("i-2", b)]})

    def test_value_from_refuses(self):
        p = pod("i-1", {"OPENDDIL_EDGE_ID": "edge-a"})
        p["spec"]["containers"][0]["env"].append(
            {"name": "DIS_NATION_RULES", "valueFrom": {"configMapKeyRef": {}}})
        with self.assertRaises(m.Refusal):
            m.sources_from_pods({"items": [p]})

    def test_not_running_pods_are_ignored(self):
        env = {"OPENDDIL_EDGE_ID": "edge-a", "DIS_NATION_RULES": rules()}
        got = m.sources_from_pods({"items": [pod("i-1", env, phase="Pending")]})
        self.assertEqual(got["ingest"], {})

    def test_finds_ontology_mounts_and_sim(self):
        got = m.sources_from_pods({"items": [
            pod("map", {}, mounts=["/ontology"]),
            pod("sim", {"LOGISTICS_SIM_CONFIG_PATH": "/etc/sim.yaml"})]})
        self.assertEqual(got["ontology_pods"], [("map", "c")])
        self.assertEqual(got["sim"][0]["pod"], "sim")


class SimDefaults(unittest.TestCase):
    def test_env_wins_over_yaml(self):
        d = m.sim_defaults({"LOGISTICS_SIM_RELEASABILITY_EDGE_DEFAULTS": "edge-a=ATL"},
                           {"releasability_edge_defaults": {"edge-a": "BDR"}}, {})
        self.assertEqual(d["edge_defaults"], {"edge-a": "ATL"})

    def test_bad_pair_refuses(self):
        with self.assertRaises(m.Refusal):
            m.sim_defaults({"LOGISTICS_SIM_RELEASABILITY_EDGE_DEFAULTS": "edge-a"}, {}, {})

    def test_sites_carry_their_nation(self):
        d = m.sim_defaults({}, {"parts_availability": {"sites": {"s1": {"nation": "BDR"}}}}, {})
        self.assertEqual(d["sites"], {"s1": "BDR"})


class Translate(unittest.TestCase):
    V = ["ATL", "BDR"]

    def test_rule_becomes_rule_scoped_to_its_edge_and_entity_records(self):
        r = rules(rules_=[{"name": "box", "nation": "ATL", "match": {"geofence": BOX_A}}])
        out = m.translate(src(ingest={"edge-a": r}), self.V)
        (d,) = out["declarations"]
        self.assertEqual(d["kind"], "rule")
        self.assertEqual(d["scope"], {"kind": "edge", "id": "edge-a", "records": ["entity"]})
        self.assertEqual(d["labels"], {"originator_nation": "ATL", "releasable_to": []})

    def test_override_with_nation_is_for_a_person_not_written(self):
        out = m.translate(src(ingest={"edge-a": rules({"dis:1:1:7": "BDR"})}), self.V)
        self.assertEqual(out["declarations"], [])
        self.assertEqual(out["for_person"][0]["asset_id"], "dis:1:1:7")

    def test_override_exempt_becomes_exemption(self):
        out = m.translate(src(ingest={"edge-a": rules({"dis:1:1:7": "exempt"})}), self.V)
        self.assertEqual(out["declarations"][0]["kind"], "exemption")
        self.assertEqual(out["declarations"][0]["asset_id"], "dis:1:1:7")

    def test_override_against_a_different_file_row_refuses(self):
        doc = {"assets": {"dis:1:1:7": {"originator_nation": "ATL"}}}
        with self.assertRaises(m.Refusal):
            m.translate(src(ingest={"edge-a": rules({"dis:1:1:7": "BDR"})}, document=doc), self.V)

    def test_value_outside_vocabulary_refuses(self):
        r = rules(rules_=[{"name": "x", "nation": "ZZZ", "match": {"country": [1]}}])
        with self.assertRaises(m.Refusal):
            m.translate(src(ingest={"edge-a": r}), self.V)

    def test_sim_order_is_edge_default_then_document_then_site_nation(self):
        sim = {"edge_defaults": {"edge-a": "ATL"}, "document_default": "BDR",
               "site_nation": "ATL", "sites": {}}
        out = m.translate(src(edges=["edge-a", "edge-b"], sim=sim), self.V)
        got = {d["scope"]["id"]: (d["labels"]["originator_nation"], d["replaces"])
               for d in out["declarations"]}
        self.assertEqual(got["edge-a"][0], "ATL")
        self.assertEqual(got["edge-b"], ("BDR", "sim document default for edge-b"))
        self.assertTrue(all(d["scope"]["records"] == ["logistics"] for d in out["declarations"]))

    def test_spares_scope_is_the_logistics_site_and_root_door(self):
        sim = {"edge_defaults": {}, "document_default": None, "site_nation": "",
               "sites": {"s1": "BDR", "s2": ""}}
        (d,) = m.translate(src(sim=sim), self.V)["declarations"]
        self.assertEqual(d["scope"], {"kind": "logistics-site", "id": "s1", "records": ["spares"]})
        self.assertIsNone(d["door_edge"])

    def test_edge_default_for_an_edge_nobody_runs_is_owed_not_written(self):
        sim = {"edge_defaults": {"edge-z": "ATL"}, "document_default": None,
               "site_nation": "", "sites": {}}
        out = m.translate(src(sim=sim), self.V)
        self.assertEqual(out["declarations"], [])
        self.assertIn("edge-z", out["owed"][0]["what"])

    def test_undated_file_row_is_owed(self):
        doc = {"assets": {"dis:1:1:7": {"originator_nation": "ATL"},
                          "dis:1:1:8": {"originator_nation": "ATL",
                                        "declared_by": "o", "declared_at": "2026-11-06"}}}
        owed = m.translate(src(document=doc), self.V)["owed"]
        self.assertEqual([o["what"] for o in owed], ["file row dis:1:1:7"])

    def test_mapper_document_default_becomes_entity_site_per_edge(self):
        out = m.translate(src(edges=["edge-a", "edge-b"],
                              document={"default_originator_nation": "ATL"}), self.V)
        self.assertEqual([(d["scope"]["id"], d["scope"]["records"]) for d in out["declarations"]],
                         [("edge-a", ["entity"]), ("edge-b", ["entity"])])


class Overlap(unittest.TestCase):
    def test_boxes(self):
        self.assertTrue(m.boxes_overlap(BOX_A, BOX_B))
        self.assertFalse(m.boxes_overlap(BOX_A, BOX_FAR))

    def test_antimeridian_box(self):
        wrap = {"south": 0, "west": 170, "north": 10, "east": -170}
        self.assertTrue(m.boxes_overlap(wrap, {"south": 5, "west": 175, "north": 6, "east": 176}))
        self.assertTrue(m.boxes_overlap(wrap, {"south": 5, "west": -175, "north": 6, "east": -174}))
        self.assertFalse(m.boxes_overlap(wrap, {"south": 5, "west": 0, "north": 6, "east": 10}))

    def test_marking_and_mixed_kinds_are_undecidable(self):
        self.assertIsNone(m.matches_overlap({"marking": "^A"}, {"marking": "^B"}))
        self.assertIsNone(m.matches_overlap({"geofence": BOX_A}, {"country": [1]}))
        self.assertFalse(m.matches_overlap({"country": [1]}, {"country": [2]}))

    def _rule(self, nation, match, edge="edge-a"):
        return {"kind": "rule", "scope": {"kind": "edge", "id": edge, "records": ["entity"]},
                "match": match, "labels": {"originator_nation": nation, "releasable_to": []},
                "replaces": f"{nation} {json.dumps(match)} {edge}"}

    def test_overlapping_rules_with_different_nations_conflict(self):
        c = m.find_conflicts([self._rule("ATL", {"geofence": BOX_A}),
                              self._rule("BDR", {"geofence": BOX_B})])
        self.assertEqual(len(c), 1)
        self.assertTrue(c[0]["decided"])

    def test_disjoint_or_agreeing_or_other_edge_do_not_conflict(self):
        self.assertEqual(m.find_conflicts([self._rule("ATL", {"geofence": BOX_A}),
                                           self._rule("BDR", {"geofence": BOX_FAR})]), [])
        self.assertEqual(m.find_conflicts([self._rule("ATL", {"geofence": BOX_A}),
                                           self._rule("ATL", {"geofence": BOX_B})]), [])
        self.assertEqual(m.find_conflicts([self._rule("ATL", {"geofence": BOX_A}),
                                           self._rule("BDR", {"geofence": BOX_B}, "edge-b")]), [])

    def test_marking_against_a_different_nation_conflicts_undecided(self):
        c = m.find_conflicts([self._rule("ATL", {"marking": "^A"}),
                              self._rule("BDR", {"country": [3]})])
        self.assertEqual(len(c), 1)
        self.assertFalse(c[0]["decided"])

    def test_entity_site_conflicts_with_a_rule_of_another_nation(self):
        site = m._site("edge", "edge-a", ["entity"], "BDR", "doc default", "edge-a")
        self.assertEqual(len(m.find_conflicts([site, self._rule("ATL", {"country": [1]})])), 1)

    def test_different_record_classes_do_not_conflict(self):
        logi = m._site("edge", "edge-a", ["logistics"], "BDR", "sim default", "edge-a")
        self.assertEqual(m.find_conflicts([logi, self._rule("ATL", {"country": [1]})]), [])


class Census(unittest.TestCase):
    def test_rows_parse_nulls_and_dedupe(self):
        tsv = "a\tATL\t{}\na\tATL\t{}\nb\t\\N\t\\N\n"
        self.assertEqual(m.census_rows(tsv), [["a", "ATL", "{}"], ["b", None, None]])

    def test_malformed_row_refuses(self):
        with self.assertRaises(m.Refusal):
            m.census_rows("a\tATL\n")

    def test_equal_census_has_no_diff(self):
        c = {"pg-hq": {"t": [["a", "ATL", "{}"]]}}
        self.assertEqual(m.census_diff(c, json.loads(json.dumps(c))), [])

    def test_a_row_moving_to_unlabelled_is_one_removed_and_one_added(self):
        before = {"pg-hq": {"t": [["a", "ATL", "{}"]]}}
        after = {"pg-hq": {"t": [["a", None, None]]}}
        self.assertEqual([d["change"] for d in m.census_diff(before, after)], ["removed", "added"])

    def test_a_vanished_store_or_table_is_a_diff_not_a_match(self):
        before = {"pg-hq": {"t": []}, "pg-x": {"t": []}}
        self.assertEqual(len(m.census_diff(before, {"pg-hq": {"t": []}})), 1)
        self.assertEqual(len(m.census_diff({"pg-hq": {"t": []}}, {"pg-hq": {}})), 1)


class Prediction(unittest.TestCase):
    def _plan(self):
        return {"declarations": [{"door": "u1", "already_active": False},
                                 {"door": "u1", "already_active": True},
                                 {"door": "u2", "already_active": False}],
                "for_person": [{"asset_id": "dis:1:1:7", "originator_nation": "BDR",
                                "edge_id": "edge-a", "why": ""}],
                "owed": []}

    def test_counts_skip_already_active(self):
        p = m.build_prediction(self._plan(), "h1", "h2")
        self.assertEqual(p["load"]["declarations_to_post"], 2)
        self.assertEqual(p["load"]["already_active"], 1)
        self.assertEqual(p["load"]["by_door"], {"u1": 1, "u2": 1})
        self.assertIn("dis:1:1:7 moves to unlabelled", p["amend"]["if_not_declared"][0])
        self.assertIn("plan sha256: `h1`", m.prediction_md(p))

    def test_load_refuses_without_or_with_a_stale_prediction(self):
        with tempfile.TemporaryDirectory() as d:
            out = pathlib.Path(d)
            (out / "plan.json").write_text("{}", encoding="utf-8")
            (out / "census-before.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(m.Refusal):
                m.check_prediction(out)
            pred = m.build_prediction({"declarations": [], "for_person": [], "owed": []},
                                      m.sha256_file(out / "plan.json"),
                                      m.sha256_file(out / "census-before.json"))
            (out / "prediction.json").write_text(json.dumps(pred), encoding="utf-8")
            m.check_prediction(out)
            (out / "plan.json").write_text('{"changed": 1}', encoding="utf-8")
            with self.assertRaises(m.Refusal):
                m.check_prediction(out)

    def test_canonical_ignores_owner_date_and_reason(self):
        a = {"kind": "site", "scope": {"kind": "edge", "id": "e", "records": ["entity"]},
             "labels": {"originator_nation": "ATL", "releasable_to": []}}
        b = dict(a, declared_by="x", declared_at="y", reason="z", replaces="w")
        self.assertEqual(m.canonical(a), m.canonical(b))


class Route(unittest.TestCase):
    def _d(self, edge):
        return {"kind": "site", "scope": {"kind": "edge", "id": edge or "s", "records": ["x"]},
                "labels": {}, "replaces": f"r {edge}", "door_edge": edge}

    def test_routes_by_the_peps_own_answers_and_marks_active(self):
        active = dict(self._d("edge-a"), status="active")
        peps = {"u1": {"edges": ["edge-a"], "declarations": [active]},
                "u0": {"root": True, "edges": []}}
        ds = [self._d("edge-a"), self._d(None)]
        m.route(ds, peps)
        self.assertEqual([(d["door"], d["already_active"]) for d in ds],
                         [("u1", True), ("u0", False)])

    def test_unserved_or_doubly_served_edge_refuses(self):
        with self.assertRaises(m.Refusal):
            m.route([self._d("edge-b")], {"u1": {"edges": ["edge-a"]}})
        with self.assertRaises(m.Refusal):
            m.route([], {"u1": {"edges": ["edge-a"]}, "u2": {"edges": ["edge-a"]}})


class SessionFile(unittest.TestCase):
    def test_first_non_empty_line_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "s"
            p.write_text("\n  sid=abc  \nsecond-line\n", encoding="utf-8")
            self.assertEqual(m.first_line(p), "sid=abc")


if __name__ == "__main__":
    unittest.main()
