"""Tests for capability_floor.py.

Run from the worktree root:
    python -m unittest discover -s docs/arch/tools -p "test_*.py"

Synthetic documents, models and records. No helm, no chart.
"""
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capability_floor as cf  # noqa: E402
import capability_phases as cp  # noqa: E402


def deploy(name, labels=None, kind="Deployment"):
    meta = {"name": name}
    if labels:
        meta["labels"] = labels
    return {"kind": kind, "metadata": meta}


def model(tiers=("edge-01", "edge-02", "hq"), kinds=(), routes=()):
    return SimpleNamespace(tiers=sorted(tiers), kinds={k: None for k in kinds},
                           routes=[{"name": r} for r in routes])


def workloads(docs, tiers=("edge-01", "edge-02", "hq", "01")):
    return cf.rendered_items(docs, model(tiers), [], "rel")["workload"]


class Workloads(unittest.TestCase):
    def test_release_prefix_and_tier_suffix_go(self):
        self.assertEqual(workloads([deploy("rel-intake-edge-01")]), {"intake"})

    def test_a_name_without_either_is_kept(self):
        self.assertEqual(workloads([deploy("bff")]), {"bff"})

    def test_label_order(self):
        labels = {"app": "c", "component": "b", "app.kubernetes.io/component": "a"}
        self.assertEqual(workloads([deploy("x", labels)]), {"a"})
        del labels["app.kubernetes.io/component"]
        self.assertEqual(workloads([deploy("x", labels)]), {"b"})
        del labels["component"]
        self.assertEqual(workloads([deploy("x", labels)]), {"c"})

    def test_unlabelled_falls_back_to_the_name(self):
        self.assertEqual(workloads([deploy("rel-thing")]), {"thing"})

    def test_longest_tier_id_first(self):
        # "01" and "edge-01" both end the name; the longer one is the tier.
        self.assertEqual(workloads([deploy("rel-intake-edge-01")], ("01", "edge-01")), {"intake"})

    def test_only_one_suffix_is_stripped(self):
        self.assertEqual(workloads([deploy("rel-a-hq-hq")]), {"a-hq"})

    def test_empty_after_stripping_keeps_the_unstripped_name(self):
        self.assertEqual(workloads([deploy("hq", {"app": "-hq"})], ("hq",)), {"-hq"})

    def test_other_kinds_stay_out(self):
        self.assertEqual(workloads([deploy("rel-t", kind="Pod"), deploy("rel-s", kind="StatefulSet"),
                                    deploy("rel-c", kind="ConfigMap")]), {"s"})

    def test_release_comes_from_the_instance_label_by_default(self):
        d = deploy("zz-intake", {"app.kubernetes.io/instance": "zz"})
        self.assertEqual(cf.rendered_items([d], model(), [])["workload"], {"intake"})


class Flags(unittest.TestCase):
    def flags(self, *layers):
        return cf.rendered_items([deploy("rel-a")], model(), list(layers), "rel")["flag"]

    def test_enabled_true_gives_the_dotted_path(self):
        self.assertEqual(self.flags({"egress": {"tak": {"enabled": True}}}), {"egress.tak"})

    def test_a_later_layer_overrides(self):
        on, off = {"a": {"enabled": True, "b": {"enabled": True}}}, {"a": {"b": {"enabled": False}}}
        self.assertEqual(self.flags(on, off), {"a"})
        self.assertEqual(self.flags(off, on), {"a", "a.b"})

    def test_enabled_false_and_other_values_are_out(self):
        self.assertEqual(self.flags({"a": {"enabled": False}, "b": {"enabled": "true"}, "c": {"enabled": 1}}), set())

    def test_lists_are_not_walked(self):
        self.assertEqual(self.flags({"edges": [{"enabled": True}]}), set())

    def test_a_dict_that_replaces_a_scalar(self):
        self.assertEqual(self.flags({"a": 1}, {"a": {"enabled": True}}), {"a"})

    def test_layers_are_not_mutated(self):
        layer = {"a": {"enabled": True}}
        before = copy.deepcopy(layer)
        self.flags(layer, {"a": {"x": 1}})
        self.assertEqual(layer, before)


class Routes(unittest.TestCase):
    def test_model_routes_and_ingress_paths(self):
        ing = {"kind": "Ingress", "metadata": {"name": "i"},
               "spec": {"rules": [{"http": {"paths": [{"path": "/a"}, {"path": "/b"}]}}, {}]}}
        got = cf.rendered_items([deploy("rel-a"), ing], model(routes=("r1", "r2")), [], "rel")["route"]
        self.assertEqual(got, {"r1", "r2", "ingress /a", "ingress /b"})

    def test_kinds_are_the_models(self):
        got = cf.rendered_items([deploy("rel-a")], model(kinds=("K1", "K2")), [], "rel")["kind"]
        self.assertEqual(got, {"K1", "K2"})


CAPS = {"Built": "Lane", "Design": "Lane", "Measured": "Lane", "Bare": "Lane"}
STATUSES = {"ADR-1": "accepted"}
BUILT = [{"template": "t.yaml", "contains": "x"}]


def record(rendered):
    return {"capabilities": {
        "Built": {"built": BUILT},
        "Design": {"adrs": ["ADR-1"]},
        "Measured": {"measured": [{"entry": "e", "line": "l"}], "built": BUILT},
        "Bare": {},
    }, "rendered": rendered}


def items(**kw):
    return {s: set(kw.get(s, ())) for s in cf.SECTIONS}


class Failures(unittest.TestCase):
    def check(self, rendered, have):
        return cf.check_floor(record(rendered), CAPS, STATUSES, have)

    def test_a_good_claim_passes(self):
        got = self.check({"workload": {"w": ["Built"], "v": {"infrastructure": "the broker"}},
                          "kind": {"K": ["Measured", "Built"]}},
                         items(workload=("w", "v"), kind=("K",)))
        self.assertEqual(got, [])

    def test_1_no_rendered_section(self):
        rec = record({})
        del rec["rendered"]
        self.assertEqual(cf.check_floor(rec, CAPS, STATUSES, items(workload=("w",))),
                         ["floor: the record has no rendered section"])

    def test_2_unknown_section(self):
        got = self.check({"workload": {"w": ["Built"]}, "pods": {}}, items(workload=("w",)))
        self.assertEqual(got, ["floor: rendered has an unknown section pods"])

    def test_3_unclaimed_item(self):
        got = self.check({"workload": {"w": ["Built"]}}, items(workload=("w", "v")))
        self.assertEqual(got, ["floor: workload v is in the render and the record does not claim it"])

    def test_4_stale_claim(self):
        got = self.check({"workload": {"w": ["Built"], "gone": ["Built"]}}, items(workload=("w",)))
        self.assertEqual(got, ["floor: workload gone is claimed but the render does not show it"])

    def test_5_unknown_capability(self):
        got = self.check({"workload": {"w": ["Nope"]}}, items(workload=("w",)))
        self.assertEqual(len(got), 1)
        self.assertIn("Nope", got[0])
        self.assertTrue(got[0].startswith("floor: "))

    def test_6_malformed_claims(self):
        for bad in ([], {"infrastructure": ""}, {"infrastructure": "  "}, {}, {"other": "x"}, "Built", None, [1]):
            got = self.check({"workload": {"w": bad}}, items(workload=("w",)))
            self.assertEqual(got, ["floor: workload w has a malformed claim"], repr(bad))

    def test_7_below_the_floor(self):
        got = self.check({"flag": {"f": ["Design", "Bare"]}}, items(flag=("f",)))
        self.assertEqual(got, [
            "floor: Design is accepted design, but the render shows flag f, so it cannot be below built unmeasured",
            "floor: Bare is no phase, but the render shows flag f, so it cannot be below built unmeasured"])

    def test_infrastructure_has_no_floor(self):
        self.assertEqual(self.check({"route": {"r": {"infrastructure": "x"}}}, items(route=("r",))), [])

    def test_arrival_declaration_red_case(self):
        caps = {"ArrivalDeclaration": "Lane"}
        rec = {"capabilities": {"ArrivalDeclaration": {"adrs": ["ADR-1"]}},
               "rendered": {"workload": {"tier-declaration-intake": ["ArrivalDeclaration"]}}}
        have = items(workload=("tier-declaration-intake",))
        got = cf.check_floor(rec, caps, STATUSES, have)
        self.assertEqual(len(got), 1)
        self.assertIn("ArrivalDeclaration", got[0])
        self.assertIn("cannot be below built unmeasured", got[0])
        rec["capabilities"]["ArrivalDeclaration"]["built"] = BUILT
        self.assertEqual(cf.check_floor(rec, caps, STATUSES, have), [])

    def test_empty_items_raise(self):
        with self.assertRaises(cp.CheckError):
            self.check({"workload": {}}, items())


if __name__ == "__main__":
    unittest.main()
