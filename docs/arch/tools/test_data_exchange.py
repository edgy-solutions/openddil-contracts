"""Tests for data_exchange.py.

Run from the worktree root:
    python -m unittest docs/arch/tools/test_data_exchange.py

Fixtures under testdata/ are handwritten fiction (tiers edge-atl, edge-bdr,
hq). The integration tests need helm and the sibling chart and bundle; they
skip, printing why, when either is missing.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import yaml

HERE = Path(__file__).resolve().parent
TOOL = HERE / "data_exchange.py"
DATA = HERE / "testdata"
BASIC = DATA / "rendered-basic.yaml"
ROOT = Path(os.environ.get("OPENDDIL_REPOS", HERE.parents[3]))
CHART = ROOT / "openddil-helm" / "openddil-demo"
BUNDLE_ROOT = Path(os.environ.get("OPENDDIL_BUNDLE", ROOT / "openddil-customer-bundle-example"))
BUNDLE = BUNDLE_ROOT / "k8s" / "tier-node-values.yaml"
OVERLAY = BUNDLE_ROOT / "k8s" / "egress-values.yaml"


def run_raw(*args):
    p = subprocess.run([sys.executable, str(TOOL), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


def run(*args):
    """run_raw, with --release openddil for a --rendered fixture that carries no labels."""
    args = list(map(str, args))
    if "--rendered" in args and "--release" not in args:
        args += ["--release", "openddil"]
    return run_raw(*args)


def docs():
    return list(yaml.safe_load_all(BASIC.read_text(encoding="utf-8")))


def find(ds, kind, name):
    for d in ds:
        if d.get("kind") == kind and d["metadata"]["name"] == name:
            return d
    raise KeyError(name)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, name, ds):
        p = self.tmp / name
        p.write_text(yaml.safe_dump_all(ds), encoding="utf-8")
        return p

    def no_kinds_docs(self):
        ds = [d for d in docs() if d["metadata"]["name"] != "openddil-egress-kinds"]
        routes = find(ds, "ConfigMap", "openddil-egress-routes")
        routes["data"]["routes.json"] = (
            '[{"name": "r1", "source_topic": "fault-feed", '
            '"destination": "system:depot-ledger", "sink_topic": "egress-sink"}]')
        dest = find(ds, "ConfigMap", "openddil-destinations-deployment")
        dest["data"]["data.yaml"] = dest["data"]["data.yaml"].replace(
            "accepts: [FaultEvent]", "accepts: []")
        return ds

    def exchanges(self, text):
        out, on = [], False
        for line in text.splitlines():
            if line.startswith("## "):
                on = line == "## Exchanges"
            elif on and line.startswith("|") and not line.startswith("|---"):
                out.append(line)
        return out  # header first


class Checks(Base):
    def test_basic_passes(self):
        rc, out, err = run("--rendered", BASIC, "--check")
        self.assertEqual(rc, 0, err)

    def test_orphan_kind_with_no_route_fails(self):
        ds = docs()
        k = find(ds, "ConfigMap", "openddil-egress-kinds")
        k["data"]["OrphanKind.schema.json"] = '{"x-openddil": {"key": "/a", "label": "/b"}}'
        rc, _, err = run("--rendered", self.write("o.yaml", ds), "--check")
        self.assertEqual(rc, 1)
        self.assertIn("FAIL: kind OrphanKind is not in the Kind column", err)

    def test_kind_without_schema_fails(self):
        ds = docs()
        r = find(ds, "ConfigMap", "openddil-egress-routes")
        r["data"]["routes.json"] = r["data"]["routes.json"].replace("FaultEvent", "NoSchemaKind")
        rc, out, err = run("--rendered", self.write("n.yaml", ds), "--check")
        self.assertEqual(rc, 1)
        self.assertIn("named without a schema", err)
        self.assertIn("kind-without-schema", out)

    def test_tier_with_no_workload_fails(self):
        vals = self.tmp / "v.yaml"
        vals.write_text("edges:\n  - id: edge-zzz\nregions: []\n", encoding="utf-8")
        rc, _, err = run("--rendered", BASIC, "--values", vals, "--check")
        self.assertEqual(rc, 1)
        self.assertIn("FAIL: tier edge-zzz is in neither", err)

    def test_deleted_row_fails_check_file(self):
        _, out, _ = run("--rendered", BASIC)
        rows = self.exchanges(out)[1:]
        for needle, expect in (("edge-bdr", "tier edge-bdr"),
                               ("FaultEvent", "kind FaultEvent"),
                               ("system:depot-ledger", "no row carries destination")):
            kept = [l for l in out.splitlines() if not (l in rows and needle in l)]
            f = self.tmp / "doc.md"
            f.write_text("\n".join(kept) + "\n", encoding="utf-8")
            rc, _, err = run("--rendered", BASIC, "--check-file", f)
            self.assertEqual(rc, 1, needle)
            self.assertIn(expect, err)

    def test_zero_rows_fails(self):
        _, out, _ = run("--rendered", BASIC)
        rows = self.exchanges(out)[1:]
        f = self.tmp / "doc.md"
        f.write_text("\n".join(l for l in out.splitlines() if l not in rows) + "\n", encoding="utf-8")
        rc, _, err = run("--rendered", BASIC, "--check-file", f)
        self.assertEqual(rc, 1)
        self.assertIn("FAIL: zero exchange rows", err)

    def test_empty_render_exits_2(self):
        empty = self.tmp / "e.yaml"
        empty.write_text("", encoding="utf-8")
        self.assertEqual(run("--rendered", empty)[0], 2)

    def test_zero_tiers_exits_2(self):
        ds = [{"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "x"}, "data": {}}]
        self.assertEqual(run("--rendered", self.write("z.yaml", ds))[0], 2)

    def test_no_kinds_without_flag_fails(self):
        p = self.write("nk.yaml", self.no_kinds_docs())
        rc, out, err = run("--rendered", p, "--check")
        self.assertEqual(rc, 1)
        self.assertIn("--allow-no-kinds not given", err)
        self.assertIn("None declared by this bundle.", out)

    def test_no_kinds_with_flag_passes_and_states_reason(self):
        p = self.write("nk.yaml", self.no_kinds_docs())
        rc, out, err = run("--rendered", p, "--check", "--allow-no-kinds", "fixture has none")
        self.assertEqual(rc, 0, err)
        self.assertIn("fixture has none", out)

    def test_stale_flag_fails(self):
        rc, _, err = run("--rendered", BASIC, "--check", "--allow-no-kinds", "old reason")
        self.assertEqual(rc, 1)
        self.assertIn("stale", err)

    def test_route_to_unregistered_destination(self):
        ds = docs()
        r = find(ds, "ConfigMap", "openddil-egress-routes")
        r["data"]["routes.json"] = r["data"]["routes.json"].replace(
            '"destination": "system:depot-ledger"', '"destination": "system:nowhere"')
        rc, out, err = run("--rendered", self.write("r.yaml", ds), "--check")
        self.assertEqual(rc, 0, err)  # a row carries the destination
        self.assertIn("none in this bundle", out)
        self.assertIn("destination-without-entry", out)


class Content(Base):
    def test_route_to_destination(self):
        _, out, _ = run("--rendered", BASIC)
        self.assertIn("| system:depot-ledger | Depot ledger | ATL, BDR | FaultEvent "
                      "| fixture-registry | 2026-01-01 | r1 |", out)
        row = [l for l in self.exchanges(out) if "| fault-feed |" in l][0]
        self.assertIn("system:depot-ledger", row)
        self.assertIn("egress-gate-c2", row)
        self.assertIn("kind label /label", row)

    def test_profiles_rename_and_check_by_position(self):
        prof = yaml.safe_load((HERE.parent / "profiles.yaml").read_text(encoding="utf-8"))
        for name, head in (("uaf", "# Rs-Cn "), ("dodaf202", "# SV-6 "), ("naf4", "# P3 ")):
            rc, out, err = run("--rendered", BASIC, "--profile", name, "--check")
            self.assertEqual(rc, 0, f"{name}: {err}")
            self.assertTrue(out.startswith(head), name)
            header = self.exchanges(out)[0]
            for col in prof["data_exchange"]["columns"][name].values():
                self.assertIn(f" {col} ", header)
            self.assertNotIn("Decision open", out, name)
        _, out, _ = run("--rendered", BASIC, "--profile", "dodaf202")
        self.assertIn("Receiving resources", out)

    def test_sentinels_never_appear(self):
        _, out, err = run("--rendered", BASIC, "--check")
        for s in ("SENTINEL", "https://", "trust_on_behalf_of", "tokenSecret", "envelope"):
            self.assertNotIn(s, out + err)

    def test_secret_dropped_at_parse(self):
        secret = dict(apiVersion="v1", kind="Secret", metadata={"name": "fixture"},
                      stringData={"password": "SENTINEL-SECRET-DATA"})
        sys.path.insert(0, str(HERE))
        self.addCleanup(sys.path.remove, str(HERE))
        import data_exchange
        kept = data_exchange.load_docs(yaml.safe_dump_all([secret] + docs()))
        self.assertEqual([d for d in kept if d.get("kind") == "Secret"], [])
        self.assertEqual(len(kept), len(docs()))

    def test_byte_stable(self):
        a = run("--rendered", BASIC)[1]
        self.assertEqual(a, run("--rendered", BASIC)[1])
        self.assertNotIn("\r", a)

    def test_group_without_topic_is_exception_no_row(self):
        _, out, _ = run("--rendered", BASIC)
        self.assertIn("group-without-topic | 2 | edge-bdr/lonely-group-name-raw (lonely-edge-bdr)", out)
        for l in self.exchanges(out):
            self.assertNotIn("lonely", l)

    def test_env_binding_and_none_declared(self):
        ds = docs()
        w = find(ds, "Deployment", "openddil-lonely-edge-bdr")
        w["spec"]["template"]["spec"]["containers"][0]["env"] = [
            {"name": "X_INPUT_TOPICS", "value": "ghost,raw"}]
        _, out, _ = run("--rendered", self.write("env.yaml", ds))
        self.assertIn("| edge-bdr | edge-bdr | ghost | none declared |", out)
        self.assertIn("consumer-without-writer", out)
        self.assertNotIn("lonely-group-name-raw (", out)

    def raw_ingest_docs(self, reader_topics=None):
        ds = docs()
        w = find(ds, "Deployment", "openddil-sensor-edge-bdr")
        w["metadata"]["annotations"]["openddil.io/produces-topics"] += " edge-bdr/ingress-dis-raw"
        if reader_topics:
            r = find(ds, "Deployment", "openddil-lonely-edge-bdr")
            r["spec"]["template"]["spec"]["containers"][0]["env"] = [
                {"name": "X_INPUT_TOPICS", "value": reader_topics}]
        return ds

    def test_a_raw_ingest_topic_with_no_reader_passes(self):
        rc, out, err = run("--rendered", self.write("raw.yaml", self.raw_ingest_docs()), "--check")
        self.assertEqual(rc, 0, err)
        self.assertIn("| ingress-dis-raw | sensor-edge-bdr | annotation | none declared |", out)

    def test_a_raw_ingest_topic_read_by_anything_but_the_mapper_fails(self):
        rc, out, err = run("--rendered", self.write("raw.yaml", self.raw_ingest_docs("ingress-dis-raw")), "--check")
        self.assertEqual(rc, 1, err)
        self.assertIn("FAIL: raw ingest topic edge-bdr/ingress-dis-raw is read by lonely-edge-bdr; "
                      "only the mapper may read it", err)

    def test_a_reader_named_as_the_mapper_passes(self):
        sys.path.insert(0, str(HERE))
        self.addCleanup(sys.path.remove, str(HERE))
        import data_exchange
        doc = run("--rendered", self.write("raw.yaml", self.raw_ingest_docs("ingress-dis-raw")))[1]
        model = types.SimpleNamespace(tiers=[], kind_universe=[], kinds={}, routes=[])
        self.assertTrue([f for f in data_exchange.check_document(doc, model, "x") if "raw ingest" in f])
        with mock.patch.object(data_exchange, "RAW_INGEST_READERS", frozenset({"lonely-edge-bdr"})):
            self.assertEqual([f for f in data_exchange.check_document(doc, model, "x") if "raw ingest" in f], [])

    def test_writer_without_consumer(self):
        ds = docs()
        w = find(ds, "Deployment", "openddil-sensor-edge-atl")
        w["metadata"]["annotations"]["openddil.io/produces-topics"] += " edge-atl/unread"
        _, out, _ = run("--rendered", self.write("w.yaml", ds))
        self.assertIn("| unread | sensor-edge-atl | annotation | none declared |", out)
        self.assertIn("writer-without-consumer | 1 |", out)

    def test_values_stamp_basename_only(self):
        vals = self.tmp / "sub" / "myvals.yaml"
        vals.parent.mkdir()
        vals.write_text("releasability:\n  enabled: false\n", encoding="utf-8")
        _, out, _ = run("--rendered", BASIC, "--values", vals)
        self.assertIn("Values: myvals.yaml", out)
        self.assertNotIn(str(self.tmp), out)
        self.assertIn("releasability-disabled", out)


class Naming(Base):
    def chart(self, values=None, version="1.2.3"):
        d = self.tmp / "chart"
        d.mkdir(exist_ok=True)
        (d / "Chart.yaml").write_text(f"name: demo\nversion: {version}\n" if version else "name: demo\n",
                                      encoding="utf-8")
        (d / "values.yaml").write_text(yaml.safe_dump(values or {}), encoding="utf-8")
        return d

    def vals(self, name, body):
        p = self.tmp / name
        p.write_text(yaml.safe_dump(body), encoding="utf-8")
        return p

    def labelled(self, name, instance):
        ds = docs()
        for d in ds:
            d["metadata"].setdefault("labels", {})["app.kubernetes.io/instance"] = instance
        return self.write(name, ds)

    def head(self, *args):
        rc, out, err = run("--rendered", BASIC, "--chart", self.chart(), *args)
        self.assertEqual(rc, 0, err)
        return out.split("\n")

    def test_label_is_read_without_release(self):
        p = self.labelled("l.yaml", "openddil")
        rc, out, err = run_raw("--rendered", p, "--check")
        self.assertEqual(rc, 0, err)
        self.assertEqual(out, run("--rendered", BASIC)[1])

    def test_release_disagreeing_with_labels_exits_2(self):
        rc, _, err = run_raw("--rendered", self.labelled("l.yaml", "openddil"), "--release", "other")
        self.assertEqual(rc, 2, err)

    def test_release_with_no_labels_is_taken_as_given(self):
        self.assertEqual(run_raw("--rendered", BASIC, "--release", "openddil")[0], 0)

    def test_no_labels_and_no_release_exits_2(self):
        rc, _, err = run_raw("--rendered", BASIC)
        self.assertEqual(rc, 2)
        self.assertIn("--release", err)

    def test_several_labels_exit_2(self):
        ds = docs()
        ds[0]["metadata"]["labels"] = {"app.kubernetes.io/instance": "a"}
        ds[1]["metadata"]["labels"] = {"app.kubernetes.io/instance": "b"}
        rc, _, err = run_raw("--rendered", self.write("s.yaml", ds))
        self.assertEqual(rc, 2)
        self.assertIn("--release", err)

    def test_chart_without_release_exits_2(self):
        rc, _, err = run_raw("--chart", self.chart())
        self.assertEqual(rc, 2)
        self.assertIn("--release", err)

    def test_name_in_title(self):
        plain = self.head()
        named = self.head("--values", self.vals("v.yaml", {"system": {"name": "Sys One"}}))
        self.assertTrue(plain[0].startswith("# ") and not plain[0].startswith("# Sys One"))
        self.assertEqual(named[0], "# Sys One: " + plain[0][2:])

    def test_no_name_leaves_title_unchanged(self):
        _, out, _ = run("--rendered", BASIC)
        self.assertTrue(out.startswith("# "))
        _, blank, _ = run("--rendered", BASIC, "--chart", self.chart(),
                          "--values", self.vals("b.yaml", {"system": {"name": "  "}}))
        self.assertEqual(blank.split("\n")[0], out.split("\n")[0])

    def test_default_attribution_carries_chart_version(self):
        lines = self.head()
        self.assertEqual(lines[1:3], ["", "built on OpenDDIL 1.2.3"])
        self.assertEqual(lines[3], "")

    def test_default_attribution_without_chart_version(self):
        _, out, _ = run("--rendered", BASIC)
        self.assertEqual(out.split("\n")[2], "built on OpenDDIL")

    def test_attribution_true_and_null_are_the_default(self):
        for v in (True, None):
            lines = self.head("--values", self.vals("t.yaml", {"system": {"attribution": v}}))
            self.assertEqual(lines[2], "built on OpenDDIL 1.2.3")

    def test_attribution_false_or_empty_drops_the_line(self):
        for v in (False, ""):
            lines = self.head("--values", self.vals("f.yaml", {"system": {"attribution": v}}))
            self.assertNotIn("built on OpenDDIL 1.2.3", lines)
            self.assertEqual(lines[1], "")
            self.assertTrue(lines[2].startswith("Chart: demo 1.2.3"), lines[2])

    def test_custom_attribution_kept_as_given(self):
        lines = self.head("--values", self.vals("c.yaml", {"system": {"attribution": "Run by  Ops, v2"}}))
        self.assertEqual(lines[2], "Run by  Ops, v2")

    def test_bad_types_exit_2(self):
        for body in ({"system": ["a"]}, {"system": {"name": 5}}, {"system": {"attribution": 5}},
                     {"system": {"attribution": ["x"]}}):
            rc, _, err = run("--rendered", BASIC, "--values", self.vals("x.yaml", body))
            self.assertEqual(rc, 2, str(body) + err)

    def test_later_layer_overrides_one_key_and_keeps_the_other(self):
        a = self.vals("a.yaml", {"system": {"name": "First", "attribution": "by A"}})
        b = self.vals("b.yaml", {"system": {"name": "Second"}})
        lines = self.head("--values", a, "--values", b)
        self.assertTrue(lines[0].startswith("# Second: "), lines[0])
        self.assertEqual(lines[2], "by A")

    def test_chart_values_are_the_first_layer(self):
        d = self.chart({"system": {"name": "FromChart"}})
        rc, out, err = run("--rendered", BASIC, "--chart", d)
        self.assertEqual(rc, 0, err)
        self.assertTrue(out.startswith("# FromChart: "))


def _why_no_integration(need_twin=False):
    if shutil.which("helm") is None:
        return "helm is not on PATH"
    if not CHART.is_dir():
        return f"chart missing at {CHART}"
    if not BUNDLE.is_file():
        return f"tier-node values missing at {BUNDLE}"
    if need_twin and not OVERLAY.is_file():
        return f"egress twin missing at {OVERLAY}"
    return None


class Integration(unittest.TestCase):
    def setUp(self):
        why = _why_no_integration(need_twin=self._testMethodName in (
            "test_public_bundle_with_egress_twin", "test_release_name_is_not_in_the_output"))
        if why:
            print(f"SKIP integration: {why}", file=sys.stderr)
            self.skipTest(why)

    def test_public_bundle_no_kinds(self):
        rc, out, err = run("--chart", CHART, "--release", "openddil", "--values", BUNDLE, "--check",
                           "--allow-no-kinds", "public bundle declares no egress kinds")
        self.assertEqual(rc, 0, err)
        for t in ("edge-north", "edge-south", "region-north", "region-south", "hq"):
            self.assertIn(f"| {t} |", out)
        raw = [ln for ln in out.splitlines() if "| ingress-dis-raw |" in ln]
        self.assertTrue(raw)
        self.assertTrue(all("| none declared |" in ln for ln in raw), raw)

    def test_public_bundle_with_egress_twin(self):
        rc, out, err = run("--chart", CHART, "--release", "openddil", "--values", BUNDLE,
                           "--values", OVERLAY, "--check")
        self.assertEqual(rc, 0, err)
        self.assertIn("| FaultEvent |", out)
        self.assertIn("system:depot-ledger", out)
        self.assertIn("| RepairOrder |", out)
        self.assertIn("system:c2-stand-in-atl", out)
        sys.path.insert(0, str(HERE))
        self.addCleanup(sys.path.remove, str(HERE))
        from data_exchange import table_after
        exc = [r[0] for r in table_after(out, "Exceptions")]
        self.assertNotIn("destination-without-entry", exc)
        rows = [line for line in out.splitlines() if line.startswith("| hq | hq | ")]
        sink = next(line for line in rows if "| egress-depot-sink |" in line)
        self.assertIn("egress-forwarder", sink)
        trigger = [line for line in out.splitlines() if "| asset-cm-state |" in line and "egress-assembler" in line]
        self.assertTrue(trigger, "the assembler's trigger topic should bind its group")
        self.assertNotIn("hq/egress-assembler (egress-assembler)", out)

    def test_release_name_is_not_in_the_output(self):
        args = ("--chart", CHART, "--values", BUNDLE, "--values", OVERLAY)
        rc1, out1, err1 = run(*args, "--release", "openddil")
        rc2, out2, err2 = run(*args, "--release", "acme")
        self.assertEqual((rc1, rc2), (0, 0), err1 + err2)
        self.assertEqual(out1, out2)

    def test_no_kinds_under_another_release_still_fails_closed(self):
        args = ("--chart", CHART, "--release", "acme", "--values", BUNDLE, "--check")
        rc, _, err = run(*args)
        self.assertEqual(rc, 1, err)
        self.assertIn("no kinds declared", err)
        rc, _, err = run(*args, "--allow-no-kinds", "public bundle declares no egress kinds")
        self.assertEqual(rc, 0, err)


if __name__ == "__main__":
    unittest.main()
