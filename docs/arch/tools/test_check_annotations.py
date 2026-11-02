"""Tests for check_annotations.py.

Run from the worktree root:
    python -m unittest docs/arch/tools/test_check_annotations.py

The unit tests build rendered YAML inline and pass it with --rendered. The
integration test renders the chart with the bundle's tier-node values and
egress twin and checks it against the committed ledger; it skips, printing
why, when helm, the chart or the twin is absent.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
TOOL = HERE / "check_annotations.py"
LEDGER = HERE.parent / "annotation-exceptions.yaml"
ROOT = Path(os.environ.get("OPENDDIL_REPOS", HERE.parents[3]))
CHART = ROOT / "openddil-helm" / "openddil-demo"
BUNDLE_ROOT = Path(os.environ.get("OPENDDIL_BUNDLE", ROOT / "openddil-customer-bundle-example"))
TIER_NODE = BUNDLE_ROOT / "k8s" / "tier-node-values.yaml"
TWIN = BUNDLE_ROOT / "k8s" / "egress-values.yaml"

PRODUCES = "openddil.io/produces-topics"
GROUPS = "openddil.io/consumer-groups"
CLASSES = ("writer-not-annotated", "workload-no-declaration", "group-without-topic")


def run(*args):
    p = subprocess.run([sys.executable, str(TOOL), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


def broker(bid):
    return {"apiVersion": "apps/v1", "kind": "StatefulSet",
            "metadata": {"name": f"openddil-redpanda-{bid}"}, "spec": {"template": {}}}


def workload(name, own=None, tmpl=None, kind="Deployment"):
    meta = {"name": f"openddil-{name}"}
    if own:
        meta["annotations"] = dict(own)
    pod = {"spec": {"containers": [{"name": "c", "image": "x"}]}}
    if tmpl:
        pod["metadata"] = {"annotations": dict(tmpl)}
    spec = {"jobTemplate": {"spec": {"template": pod}}} if kind == "CronJob" else {"template": pod}
    return {"apiVersion": "apps/v1", "kind": kind, "metadata": meta, "spec": spec}


def good_docs():
    return [
        broker("hq"), broker("edge-a"),
        workload("writer-a", own={PRODUCES: "hq/topic-one hq/topic.two"}),
        workload("reader-a", own={GROUPS: "hq/group-a"}),
    ]


def empty_ledger():
    return {c: {"reason": f"reason for {c}", "rows": []} for c in CLASSES}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def check(self, docs, ledger=None, ledger_text=None):
        r = self.tmp / "rendered.yaml"
        r.write_text(yaml.safe_dump_all(docs), encoding="utf-8")
        led = self.tmp / "ledger.yaml"
        led.write_text(ledger_text if ledger_text is not None else yaml.safe_dump(ledger or {}),
                       encoding="utf-8")
        return run("--rendered", r, "--exceptions", led)

    def rows(self, docs):
        """The model's current rows for these docs, as a ledger body."""
        r = self.tmp / "rows-in.yaml"
        r.write_text(yaml.safe_dump_all(docs), encoding="utf-8")
        rc, out, err = run("--rendered", r, "--print-rows")
        self.assertEqual(rc, 0, err)
        return yaml.safe_load(out)

    def red(self, docs, rule, ledger=None):
        rc, out, err = self.check(docs, ledger if ledger is not None else self.rows(docs))
        self.assertEqual(rc, 1, out + err)
        self.assertIn(f"FAIL: {rule}:", out)
        return out


class Green(Base):
    def test_clean_render_passes(self):
        docs = good_docs()
        rc, out, err = self.check(docs, self.rows(docs))
        self.assertEqual(rc, 0, out + err)
        self.assertTrue(out.startswith("ok:"), out)

    def test_two_producers_of_one_topic_pass(self):
        docs = good_docs() + [workload("writer-b", own={PRODUCES: "hq/topic-one"})]
        rc, out, err = self.check(docs, self.rows(docs))
        self.assertEqual(rc, 0, out + err)

    def test_cronjob_own_annotation_passes(self):
        docs = good_docs() + [workload("job-a", own={PRODUCES: "hq/topic-three"}, kind="CronJob")]
        rc, out, err = self.check(docs, self.rows(docs))
        self.assertEqual(rc, 0, out + err)


class Grammar(Base):
    def test_token_with_no_slash(self):
        docs = good_docs() + [workload("bad", own={PRODUCES: "topic-one"})]
        out = self.red(docs, "grammar")
        self.assertIn("'topic-one'", out)

    def test_token_with_two_slashes(self):
        docs = good_docs() + [workload("bad", own={PRODUCES: "hq/a/b"})]
        self.red(docs, "grammar")

    def test_bad_broker_id(self):
        docs = good_docs() + [workload("bad", own={PRODUCES: "HQ/topic-one"})]
        self.red(docs, "grammar")

    def test_bad_topic_name(self):
        docs = good_docs() + [workload("bad", own={PRODUCES: "hq/-topic"})]
        self.red(docs, "grammar")

    def test_repeated_token(self):
        docs = good_docs() + [workload("bad", own={PRODUCES: "hq/topic-one hq/topic-one"})]
        out = self.red(docs, "grammar")
        self.assertIn("repeated", out)


class Placement(Base):
    def test_annotation_in_pod_template(self):
        docs = good_docs() + [workload("rolled", tmpl={PRODUCES: "hq/topic-one"})]
        out = self.red(docs, "placement")
        self.assertIn("rolled", out)

    def test_annotation_in_cronjob_template(self):
        docs = good_docs() + [workload("job-b", tmpl={GROUPS: "hq/group-z"}, kind="CronJob")]
        self.red(docs, "placement")


class Broker(Base):
    def test_unknown_broker(self):
        docs = good_docs() + [workload("lost", own={PRODUCES: "edge-zz/topic-one"})]
        out = self.red(docs, "broker")
        self.assertIn("edge-zz", out)


class Owner(Base):
    def test_same_group_on_two_workloads(self):
        docs = good_docs() + [workload("reader-b", own={GROUPS: "hq/group-a"})]
        out = self.red(docs, "owner")
        self.assertIn("reader-a", out)
        self.assertIn("reader-b", out)


class Ledger(Base):
    def test_new_row(self):
        docs = good_docs() + [workload("undeclared")]
        out = self.red(docs, "ledger", ledger=self.rows(good_docs()))
        self.assertIn("new workload-no-declaration", out)
        self.assertIn("undeclared", out)

    def test_stale_row(self):
        docs = good_docs()
        ledger = self.rows(docs)
        ledger["workload-no-declaration"]["rows"].append("long-gone")
        out = self.red(docs, "ledger", ledger=ledger)
        self.assertIn("stale workload-no-declaration", out)

    def test_empty_reason(self):
        docs = good_docs()
        ledger = self.rows(docs)
        ledger["group-without-topic"]["reason"] = "  "
        self.red(docs, "ledger", ledger=ledger)

    def test_missing_class(self):
        docs = good_docs()
        ledger = self.rows(docs)
        del ledger["writer-not-annotated"]
        out = self.red(docs, "ledger", ledger=ledger)
        self.assertIn("writer-not-annotated is missing", out)

    def test_unknown_class(self):
        docs = good_docs()
        ledger = self.rows(docs)
        ledger["invented-class"] = {"reason": "x", "rows": []}
        self.red(docs, "ledger", ledger=ledger)

    def test_unreadable_ledger_is_exit_2(self):
        rc, out, err = self.check(good_docs(), ledger_text="key: [unclosed\n")
        self.assertEqual(rc, 2, out + err)

    def test_absent_ledger_is_exit_2(self):
        r = self.tmp / "rendered.yaml"
        r.write_text(yaml.safe_dump_all(good_docs()), encoding="utf-8")
        rc, out, err = run("--rendered", r, "--exceptions", self.tmp / "nope.yaml")
        self.assertEqual(rc, 2, out + err)


def _why_no_integration():
    if shutil.which("helm") is None:
        return "helm is not on PATH"
    for label, p in (("chart", CHART), ("tier-node values", TIER_NODE), ("egress twin", TWIN)):
        if not p.exists():
            return f"{label} missing at {p}"
    return None


class Integration(unittest.TestCase):
    def test_twin_render_matches_the_committed_ledger(self):
        why = _why_no_integration()
        if why:
            print(f"SKIP integration: {why}", file=sys.stderr)
            self.skipTest(why)
        rc, out, err = run("--chart", CHART, "--values", TIER_NODE, "--values", TWIN,
                           "--exceptions", LEDGER)
        self.assertEqual(rc, 0, out + err)
        self.assertTrue(out.startswith("ok:"), out)


if __name__ == "__main__":
    unittest.main()
