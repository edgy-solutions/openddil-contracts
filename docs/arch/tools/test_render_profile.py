"""Tests for render_profile.py.

Run from the worktree root:
    python -m unittest discover -s docs/arch/tools -p "test_*.py"

The profiles render against the real tree into temp directories. Tests that
change the tree copy docs/arch into a temp dir and run the copied tool. The
integration tests need helm and the sibling chart and bundle; they skip,
printing why, when either is missing.
"""
import filecmp
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ARCH = HERE.parent
REPO = ARCH.parent.parent
TOOL = HERE / "render_profile.py"
PROFILES = yaml.safe_load((ARCH / "profiles.yaml").read_text(encoding="utf-8"))
SIBLINGS = Path(os.environ.get("OPENDDIL_REPOS", HERE.parents[3]))
CHART = SIBLINGS / "openddil-helm" / "openddil-demo"
BUNDLE_ROOT = Path(os.environ.get("OPENDDIL_BUNDLE", SIBLINGS / "openddil-customer-bundle-example"))
BUNDLE = BUNDLE_ROOT / "k8s" / "tier-node-values.yaml"
OVERLAY = BUNDLE_ROOT / "k8s" / "egress-values.yaml"
NOTICE = "Not generated: pass --chart and --values to fill this from a bundle."
PHASES_NOTICE = "Not generated: pass --chart to read the phases from the record, the readiness doc and the chart."
PHASES_MARKER = "<!-- generated: capability-phases -->"
PHASES_FILES = (("uaf", "St-Rm-P.md"), ("dodaf202", "CV-3.md"), ("naf4", "Cr.md"))
STRIPPED = "  TacticalSustainmentCorrelation:\n    adrs: [ADR-0039]\n"
LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")


def run(tool, *args):
    p = subprocess.run([sys.executable, str(tool), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


def expected_files(profile):
    if profile == "uaf":
        return {f"{v}.md" for v in PROFILES["views"]} | {"INDEX.md"}
    ids = {x for e in PROFILES["views"].values() for x in (e.get("exports") or {}).get(profile) or []}
    return {f"{x}.md" for x in ids} | {"INDEX.md", "NOT-EXPORTED.md"}


def read(d, name):
    return (Path(d) / name).read_text(encoding="utf-8")


def relative_links(text):
    out, fence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
        elif not fence:
            out += [t for t in LINK.findall(re.sub(r"`[^`\n]*`", "", line))
                    if not re.match(r"^([a-z][a-z0-9+.-]*:|#)", t, re.I)]
    return out


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.out = {}
        for p in ("uaf", "dodaf202", "naf4"):
            cls.out[p] = cls.tmp / p
            rc, _, err = run(TOOL, "--profile", p, "--out", cls.out[p])
            assert rc == 0, err

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)


class RealTree(Base):
    def test_phases_notice_without_a_chart(self):
        for prof, name in PHASES_FILES:
            text = read(self.out[prof], name)
            self.assertIn(PHASES_NOTICE, text, f"{prof}/{name}")
            self.assertNotIn(PHASES_MARKER, text, f"{prof}/{name}")

    def test_every_expected_file_and_no_others(self):
        for p in ("uaf", "dodaf202", "naf4"):
            got = {f.name for f in self.out[p].iterdir()}
            self.assertEqual(got, expected_files(p), p)

    def test_byte_stable(self):
        for p in ("uaf", "dodaf202", "naf4"):
            again = self.tmp / f"{p}-again"
            self.assertEqual(run(TOOL, "--profile", p, "--out", again)[0], 0)
            names = sorted(f.name for f in self.out[p].iterdir())
            match, mismatch, errors = filecmp.cmpfiles(self.out[p], again, names, shallow=False)
            self.assertEqual((mismatch, errors), ([], []), p)

    def test_rerun_into_same_dir_clears_old_md(self):
        d = self.tmp / "reuse"
        self.assertEqual(run(TOOL, "--profile", "naf4", "--out", d)[0], 0)
        (d / "STALE.md").write_text("old", encoding="utf-8")
        self.assertEqual(run(TOOL, "--profile", "naf4", "--out", d)[0], 0)
        self.assertFalse((d / "STALE.md").exists())

    def test_out_dir_not_empty_without_index_is_exit_2(self):
        d = self.tmp / "occupied"
        d.mkdir()
        (d / "keep.txt").write_text("mine", encoding="utf-8")
        rc, _, err = run(TOOL, "--profile", "naf4", "--out", d)
        self.assertEqual(rc, 2, err)
        self.assertTrue((d / "keep.txt").exists())

    def test_ov2_has_both_sources(self):
        t = read(self.out["dodaf202"], "OV-2.md")
        self.assertIn("From UAF 1.2 Operational-Structure (Op-Sr).", t)
        self.assertIn("From UAF 1.2 Operational-Connectivity (Op-Cn).", t)
        self.assertIn("## Operational-Structure (Op-Sr)", t)
        self.assertIn("## Operational-Connectivity (Op-Cn)", t)
        self.assertNotIn("\n## Sources", t)  # demoted one level

    def test_single_source_keeps_headings(self):
        self.assertIn("\n## Sources", read(self.out["dodaf202"], "OV-1.md"))

    def test_sv6_holds_the_notice_and_sv3_points_to_it(self):
        d = self.out["dodaf202"]
        sv6 = read(d, "SV-6.md")
        self.assertIn(NOTICE, sv6)
        self.assertIn("From UAF 1.2 Resources-Connectivity (Rs-Cn).", sv6)
        self.assertIn("Exported separately as SV-6.", read(d, "SV-3.md"))
        div3 = read(d, "DIV-3.md")
        self.assertNotIn(NOTICE, div3)
        self.assertNotIn("Exported separately", div3)

    def test_p3_holds_the_view_and_the_notice(self):
        d = self.out["naf4"]
        p3 = read(d, "P3.md")
        self.assertIn("## Boundary interfaces", p3)
        self.assertIn(NOTICE, p3)
        self.assertNotIn("Exported separately", p3)
        l7 = read(d, "L7.md")
        self.assertIn("## Sources", l7)
        self.assertNotIn(NOTICE, l7)
        self.assertNotIn("Exported separately", l7)
        p7 = read(d, "P7.md")
        self.assertNotIn(NOTICE, p7)
        self.assertNotIn("Exported separately", p7)

    def test_l7_is_op_if_only(self):
        t = read(self.out["naf4"], "L7.md")
        self.assertIn("From UAF 1.2 Operational-Information (Op-If).", t)
        self.assertNotIn("(Rs-", t)

    def test_uaf_home_view_holds_notice_under_demoted_flow(self):
        t = read(self.out["uaf"], "Rs-Cn.md")
        self.assertIn(NOTICE, t)
        self.assertTrue(t.startswith("# Resources-Connectivity (Rs-Cn)\n"))
        self.assertNotIn(NOTICE, read(self.out["uaf"], "Rs-If.md"))

    def test_not_exported_lists_security_views(self):
        for p in ("dodaf202", "naf4"):
            t = read(self.out[p], "NOT-EXPORTED.md")
            for v in ("Sc-Sr", "Sc-Cn", "Sc-Pr"):
                self.assertIn(f"({v})", t, p)
            self.assertRegex(t, r"Unfilled slots in this output: \d+\.")
        self.assertFalse((self.out["uaf"] / "NOT-EXPORTED.md").exists())

    def test_every_relative_link_resolves(self):
        checked = 0
        for p in ("uaf", "dodaf202", "naf4"):
            for f in self.out[p].glob("*.md"):
                for target in relative_links(f.read_text(encoding="utf-8")):
                    rel = target.split("#", 1)[0]
                    if rel:
                        checked += 1
                        self.assertTrue((f.parent / rel).exists(), f"{p}/{f.name}: {target}")
        self.assertGreater(checked, 50)

    def test_model_marker_becomes_the_right_package_only(self):
        t = read(self.out["dodaf202"], "CV-2.md")
        self.assertNotIn("<!-- model:", t)
        block = re.search(r"```sysml\n(.*?)\n```", t, re.S)
        self.assertIsNotNone(block)
        self.assertTrue(block.group(1).startswith("package CapabilityTaxonomy {"))
        self.assertTrue(block.group(1).endswith("}"))
        self.assertNotIn("package Information", block.group(1))
        self.assertNotIn("package OperationalNodes", block.group(1))
        self.assertEqual(len(re.findall(r"```sysml", t)), 1)

    def test_model_block_ignores_braces_in_comments(self):
        t = read(self.out["naf4"], "L7.md")
        block = re.search(r"```sysml\n(.*?)\n```", t, re.S).group(1)
        self.assertTrue(block.startswith("package Information {"))
        self.assertNotIn("package SecurityStructure", block)

    def test_unfilled_slots_stay_and_are_counted(self):
        rc, out, _ = run(TOOL, "--profile", "naf4", "--out", self.tmp / "count")
        n = int(re.search(r"unfilled slots: (\d+)", out).group(1))
        names = set()
        for f in (self.tmp / "naf4").glob("*.md"):
            if f.name not in ("INDEX.md", "NOT-EXPORTED.md"):
                names |= set(re.findall(r"\{\{slot:([a-z0-9-]+)\}\}", f.read_text(encoding="utf-8")))
        self.assertEqual(n, len(names))
        self.assertGreater(n, 0)

    def test_slot_fill_in_text_and_in_a_mermaid_label(self):
        slots = self.tmp / "slots.yaml"
        slots.write_text('ingest-formats: \'binary "alpha" feed\'\ntier-tree: "one root, two edges"\n',
                         encoding="utf-8")
        d = self.tmp / "filled"
        rc, _, err = run(TOOL, "--profile", "uaf", "--out", d, "--slots", slots)
        self.assertEqual(rc, 0, err)
        flow = read(d, "Op-Pr.md")
        self.assertIn("F[\"binary 'alpha' feed\"]", flow)  # in a Mermaid label, quote swapped
        self.assertNotIn("{{slot:ingest-formats}}", flow)
        sr = read(d, "Op-Sr.md")
        self.assertIn("one root, two edges", sr)
        self.assertNotIn("{{slot:tier-tree}}", sr)
        self.assertIn("{{slot:system-name}}", "".join(read(d, f.name) for f in d.glob("*.md")))

    def test_slots_name_titles_every_file_and_carries_the_default_attribution_once(self):
        slots = self.tmp / "name-slots.yaml"
        slots.write_text("system-name: Slot Named\n", encoding="utf-8")
        for prof in ("uaf", "naf4"):
            d = self.tmp / f"named-{prof}"
            rc, _, err = run(TOOL, "--profile", prof, "--out", d, "--slots", slots)
            self.assertEqual(rc, 0, err)
            for f in d.glob("*.md"):
                lines = f.read_text(encoding="utf-8").split("\n")
                self.assertTrue(lines[0].startswith("# Slot Named: "), f"{prof}/{f.name}: {lines[0]}")
                self.assertEqual(lines.count("built on OpenDDIL"), 1, f"{prof}/{f.name}")
        self.assertIn("Slot Named reads a fleet", read(self.tmp / "named-uaf", "Sm-Ov.md"))

    def test_no_name_leaves_titles_and_slot_alone(self):
        for f in self.out["uaf"].glob("*.md"):
            self.assertFalse(f.read_text(encoding="utf-8").startswith("# : "), f.name)
        self.assertEqual(read(self.out["uaf"], "Sm-Ov.md").split("\n")[0], "# Summary-Overview (Sm-Ov)")
        self.assertIn("{{slot:system-name}} reads a fleet", read(self.out["uaf"], "Sm-Ov.md"))

    def test_chart_without_release_is_exit_2(self):
        rc, _, err = run(TOOL, "--profile", "uaf", "--out", self.tmp / "norel", "--chart", CHART)
        self.assertEqual(rc, 2, err)
        self.assertIn("--release", err)
        self.assertFalse((self.tmp / "norel").exists())

    def test_unknown_slot_key_is_exit_2(self):
        slots = self.tmp / "bad-slots.yaml"
        slots.write_text("not-a-slot: x\n", encoding="utf-8")
        rc, _, err = run(TOOL, "--profile", "uaf", "--out", self.tmp / "bad", "--slots", slots)
        self.assertEqual(rc, 2, err)
        self.assertIn("not-a-slot", err)
        self.assertFalse((self.tmp / "bad").exists())


class TempTree(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.arch = self.tmp / "docs" / "arch"
        shutil.copytree(ARCH, self.arch, ignore=shutil.ignore_patterns("__pycache__", "out", "node_modules"))
        shutil.copytree(REPO / "decisions", self.tmp / "decisions")
        self.tool = self.arch / "tools" / "render_profile.py"

    def strip_a_capability(self) -> Path:
        p = self.arch / "capability-record.yaml"
        text = p.read_text(encoding="utf-8")
        self.assertIn(STRIPPED, text)
        p.write_text(text.replace(STRIPPED, "  TacticalSustainmentCorrelation: {}\n"), encoding="utf-8", newline="\n")
        return p

    def test_a_capability_with_no_phase_is_exit_1_without_a_chart(self):
        self.strip_a_capability()
        rc, _, err = run(self.tool, "--profile", "uaf", "--out", self.tmp / "o")
        self.assertEqual(rc, 1, err)
        self.assertIn("TacticalSustainmentCorrelation has no phase", err)
        self.assertFalse((self.tmp / "o").exists())

    def test_record_flag_names_the_record(self):
        p = self.strip_a_capability()
        rc, _, err = run(TOOL, "--profile", "uaf", "--out", self.tmp / "o", "--record", p)
        self.assertEqual(rc, 1, err)
        self.assertIn("TacticalSustainmentCorrelation has no phase", err)

    def test_unreadable_record_is_exit_2(self):
        rc, _, err = run(self.tool, "--profile", "uaf", "--out", self.tmp / "o", "--record", self.tmp / "none.yaml")
        self.assertEqual(rc, 2, err)

    def test_phases_marker_outside_st_rm_p_is_exit_2(self):
        p = self.arch / "views" / "Op-If.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n" + PHASES_MARKER + "\n", encoding="utf-8", newline="\n")
        rc, _, err = run(self.tool, "--profile", "uaf", "--out", self.tmp / "o")
        self.assertEqual(rc, 2, err)
        self.assertIn("capability-phases", err)

    def test_unknown_model_package_is_exit_2(self):
        p = self.arch / "views" / "St-Tx.md"
        p.write_text(p.read_text(encoding="utf-8").replace("model: CapabilityTaxonomy", "model: NoSuchPackage"),
                     encoding="utf-8", newline="\n")
        rc, _, err = run(self.tool, "--profile", "uaf", "--out", self.tmp / "o")
        self.assertEqual(rc, 2, err)
        self.assertIn("NoSuchPackage", err)

    def test_unused_slot_value_does_not_appear(self):
        s = self.arch / "slots.yaml"
        s.write_text(s.read_text(encoding="utf-8") + "  spare-slot:\n    fills: Unused.\n    source: none yet\n",
                     encoding="utf-8", newline="\n")
        vals = self.tmp / "vals.yaml"
        vals.write_text("spare-slot: SENTINEL-SPARE-9231\n", encoding="utf-8")
        for prof in ("uaf", "dodaf202", "naf4"):
            d = self.tmp / f"o-{prof}"
            rc, _, err = run(self.tool, "--profile", prof, "--out", d, "--slots", vals)
            self.assertEqual(rc, 0, err)
            for f in d.glob("*.md"):
                self.assertNotIn("SENTINEL-SPARE-9231", f.read_text(encoding="utf-8"), f"{prof}/{f.name}")

    def test_view_without_exports_or_reason_is_exit_2(self):
        edit = self.arch / "profiles.yaml"
        text = edit.read_text(encoding="utf-8")
        old = '      naf4: "Table 2:5 maps Security Processes to DNDAF SecV-1 only; Table 2:3 gives no NAF 4.0 view."'
        self.assertIn(old, text)
        edit.write_text(text.replace(old, "      dodaf202x: x"), encoding="utf-8", newline="\n")
        rc, _, err = run(self.tool, "--profile", "naf4", "--out", self.tmp / "o")
        self.assertEqual(rc, 2, err)
        self.assertIn("Sc-Pr", err)

    def test_export_without_a_title_is_exit_2(self):
        edit = self.arch / "profiles.yaml"
        text = edit.read_text(encoding="utf-8")
        self.assertIn("    A8: Standards\n", text)
        edit.write_text(text.replace("    A8: Standards\n", ""), encoding="utf-8", newline="\n")
        rc, _, err = run(self.tool, "--profile", "naf4", "--out", self.tmp / "o")
        self.assertEqual(rc, 2, err)
        self.assertIn("A8", err)

    def test_marker_outside_home_is_exit_2(self):
        p = self.arch / "views" / "Op-If.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n<!-- generated: data-exchange -->\n",
                     encoding="utf-8", newline="\n")
        rc, _, err = run(self.tool, "--profile", "uaf", "--out", self.tmp / "o")
        self.assertEqual(rc, 2, err)

    def test_model_braces_in_comments_do_not_confuse_matching(self):
        m = self.arch / "model" / "openddil.sysml"
        text = m.read_text(encoding="utf-8")
        text = text.replace("package Information {",
                            "package Information {\n        // a stray { in a line comment\n"
                            "        /* and a } in a block comment */\n        doc /* \"{\" */", 1)
        m.write_text(text, encoding="utf-8", newline="\n")
        d = self.tmp / "o"
        rc, _, err = run(self.tool, "--profile", "naf4", "--out", d)
        self.assertEqual(rc, 0, err)
        block = re.search(r"```sysml\n(.*?)\n```", (d / "L7.md").read_text(encoding="utf-8"), re.S).group(1)
        self.assertIn("a stray { in a line comment", block)
        self.assertNotIn("package SecurityStructure", block)
        self.assertTrue(block.rstrip().endswith("}"))


HAVE_INTEGRATION = (shutil.which("helm") is not None and CHART.is_dir()
                    and BUNDLE.is_file() and OVERLAY.is_file())
SKIP_WHY = ("integration skipped: needs helm on PATH, the chart at " + str(CHART)
            + ", and the tier-node and egress twin values at " + str(OVERLAY.parent))
if not HAVE_INTEGRATION:
    print(SKIP_WHY, file=sys.stderr)


@unittest.skipUnless(HAVE_INTEGRATION, SKIP_WHY)
class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def render(self, prof, *extra):
        d = self.tmp / prof
        rc, _, err = run(TOOL, "--profile", prof, "--out", d, "--chart", CHART, "--release", "openddil",
                         "--values", BUNDLE, "--values", OVERLAY, *extra)
        self.assertEqual(rc, 0, err)
        return d

    def values(self, body):
        p = self.tmp / "system-values.yaml"
        p.write_text(yaml.safe_dump(body), encoding="utf-8")
        return p

    def chart_version(self):
        return str(yaml.safe_load((CHART / "Chart.yaml").read_text(encoding="utf-8"))["version"])

    def test_name_leads_every_file_and_attribution_is_there_once(self):
        v = self.values({"system": {"name": "Sys One"}})
        line = f"built on OpenDDIL {self.chart_version()}"
        for prof in ("uaf", "dodaf202", "naf4"):
            d = self.render(prof, "--values", v)
            names = {f.name for f in d.glob("*.md")}
            self.assertEqual(names, expected_files(prof))
            for n in sorted(names):
                lines = read(d, n).split("\n")
                self.assertTrue(lines[0].startswith("# Sys One: "), f"{prof}/{n}: {lines[0]}")
                self.assertEqual(lines[1:3], ["", line], f"{prof}/{n}")
                self.assertEqual(lines.count(line), 1, f"{prof}/{n}")
        uaf = self.tmp / "uaf"
        self.assertIn("Sys One reads a fleet", read(uaf, "Sm-Ov.md"))
        self.assertNotIn("{{slot:system-name}}", "".join(read(uaf, f.name) for f in uaf.glob("*.md")))
        self.assertIn("| FaultEvent |", read(uaf, "Rs-Cn.md"))

    def test_attribution_false_leaves_none(self):
        v = self.values({"system": {"name": "Sys One", "attribution": False}})
        for prof in ("uaf", "naf4"):
            d = self.render(prof, "--values", v)
            for f in d.glob("*.md"):
                text = f.read_text(encoding="utf-8")
                self.assertNotIn("built on OpenDDIL", text, f"{prof}/{f.name}")
                self.assertTrue(text.startswith("# Sys One: "), f"{prof}/{f.name}")

    def test_conflicting_slots_name_is_exit_2_and_the_same_is_fine(self):
        v = self.values({"system": {"name": "Sys One"}})
        slots = self.tmp / "slots-name.yaml"
        slots.write_text("system-name: Other\n", encoding="utf-8")
        d = self.tmp / "conflict"
        rc, _, err = run(TOOL, "--profile", "uaf", "--out", d, "--chart", CHART, "--release", "openddil",
                         "--values", BUNDLE, "--values", v, "--slots", slots)
        self.assertEqual(rc, 2, err)
        self.assertIn("system-name", err)
        self.assertFalse(d.exists())
        slots.write_text("system-name: Sys One\n", encoding="utf-8")
        rc, _, err = run(TOOL, "--profile", "uaf", "--out", d, "--chart", CHART, "--release", "openddil",
                         "--values", BUNDLE, "--values", OVERLAY, "--values", v, "--slots", slots)
        self.assertEqual(rc, 0, err)

    def test_dodaf202_sv6_has_the_kind_row(self):
        d = self.render("dodaf202")
        self.assertIn("| FaultEvent |", read(d, "SV-6.md"))
        self.assertNotIn("Not generated", read(d, "SV-6.md"))
        self.assertIn("Exported separately as SV-6.", read(d, "SV-3.md"))

    def test_naf4_p3_has_the_kind_row(self):
        d = self.render("naf4")
        self.assertIn("| FaultEvent |", read(d, "P3.md"))
        self.assertNotIn("| FaultEvent |", read(d, "L7.md"))

    def test_phases_are_generated_from_the_record(self):
        for prof, name in PHASES_FILES:
            text = read(self.render(prof), name)
            self.assertNotIn(PHASES_NOTICE, text, f"{prof}/{name}")
            self.assertNotIn(PHASES_MARKER, text, f"{prof}/{name}")
            self.assertRegex(text, r"Phases: \d+ measured, \d+ built unmeasured, \d+ accepted design, "
                                   r"\d+ proposed, \d+ row\.")

    def test_a_capability_with_no_phase_is_exit_1_with_a_chart(self):
        record = (ARCH / "capability-record.yaml").read_text(encoding="utf-8")
        self.assertIn(STRIPPED, record)
        p = self.tmp / "record.yaml"
        p.write_text(record.replace(STRIPPED, "  TacticalSustainmentCorrelation: {}\n"), encoding="utf-8", newline="\n")
        d = self.tmp / "none-phase"
        rc, _, err = run(TOOL, "--profile", "uaf", "--out", d, "--chart", CHART, "--release", "openddil",
                         "--values", BUNDLE, "--values", OVERLAY, "--record", p)
        self.assertEqual(rc, 1, err)
        self.assertIn("TacticalSustainmentCorrelation has no phase", err)
        self.assertFalse(d.exists())

    def test_a_missing_readiness_doc_is_exit_2_and_never_not_measured(self):
        d = self.tmp / "no-readiness"
        rc, _, err = run(TOOL, "--profile", "uaf", "--out", d, "--chart", CHART, "--release", "openddil",
                         "--values", BUNDLE, "--values", OVERLAY, "--readiness", self.tmp / "none.md")
        self.assertEqual(rc, 2, err)
        self.assertIn("--readiness", err)
        self.assertFalse(d.exists())

    def test_failing_check_is_exit_1_and_writes_nothing(self):
        d = self.tmp / "none"
        rc, _, err = run(TOOL, "--profile", "dodaf202", "--out", d, "--chart", CHART, "--release", "openddil",
                         "--values", BUNDLE)
        self.assertEqual(rc, 1, err)
        self.assertIn("FAIL", err)
        self.assertFalse(d.exists())


if __name__ == "__main__":
    unittest.main()
