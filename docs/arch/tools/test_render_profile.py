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
TOOL = HERE / "render_profile.py"
PROFILES = yaml.safe_load((ARCH / "profiles.yaml").read_text(encoding="utf-8"))
SIBLINGS = Path(os.environ.get("OPENDDIL_REPOS", HERE.parents[3]))
CHART = SIBLINGS / "openddil-helm" / "openddil-demo"
BUNDLE = SIBLINGS / "openddil-customer-bundle-example" / "k8s" / "tier-node-values.yaml"
OVERLAY = HERE / "testdata" / "example-overlay.yaml"
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

    def test_l7_has_op_if_and_the_notice(self):
        t = read(self.out["naf4"], "L7.md")
        self.assertIn("## Operational-Information (Op-If)", t)
        self.assertIn("## Resources-Information: data exchange (Rs-If)", t)
        self.assertIn("Not generated: pass --chart and --values to fill this from a bundle.", t)

    def test_sv6_holds_the_notice_and_div3_points_to_it(self):
        sv6 = read(self.out["dodaf202"], "SV-6.md")
        self.assertIn("Not generated: pass --chart and --values to fill this from a bundle.", sv6)
        self.assertIn("Exported separately as SV-6.", read(self.out["dodaf202"], "DIV-3.md"))
        self.assertNotIn("Not generated", read(self.out["dodaf202"], "DIV-3.md"))
        self.assertIn("Exported separately as L7.", read(self.out["naf4"], "P7.md"))

    def test_uaf_home_view_holds_notice_under_demoted_flow(self):
        t = read(self.out["uaf"], "Rs-If.md")
        self.assertIn("Not generated", t)
        self.assertTrue(t.startswith("# Resources-Information (Rs-If)\n"))

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
        self.assertIn("{{slot:deployment-name}}", "".join(read(d, f.name) for f in d.glob("*.md")))

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
        shutil.copytree(ARCH, self.arch, ignore=shutil.ignore_patterns("__pycache__", "out"))
        self.tool = self.arch / "tools" / "render_profile.py"

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


HAVE_INTEGRATION = shutil.which("helm") is not None and CHART.is_dir() and BUNDLE.is_file()
SKIP_WHY = "integration skipped: needs helm on PATH, and the sibling chart and bundle under " + str(SIBLINGS)
if not HAVE_INTEGRATION:
    print(SKIP_WHY, file=sys.stderr)


@unittest.skipUnless(HAVE_INTEGRATION, SKIP_WHY)
class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def render(self, prof):
        d = self.tmp / prof
        rc, _, err = run(TOOL, "--profile", prof, "--out", d, "--chart", CHART,
                         "--values", BUNDLE, "--values", OVERLAY)
        self.assertEqual(rc, 0, err)
        return d

    def test_dodaf202_sv6_has_the_kind_row(self):
        d = self.render("dodaf202")
        self.assertIn("| FaultEvent |", read(d, "SV-6.md"))
        self.assertNotIn("Not generated", read(d, "SV-6.md"))
        self.assertIn("Exported separately as SV-6.", read(d, "DIV-3.md"))

    def test_naf4_l7_has_the_kind_row(self):
        d = self.render("naf4")
        self.assertIn("| FaultEvent |", read(d, "L7.md"))
        self.assertIn("## Operational-Information (Op-If)", read(d, "L7.md"))

    def test_failing_check_is_exit_1_and_writes_nothing(self):
        d = self.tmp / "none"
        rc, _, err = run(TOOL, "--profile", "dodaf202", "--out", d, "--chart", CHART, "--values", BUNDLE)
        self.assertEqual(rc, 1, err)
        self.assertIn("FAIL", err)
        self.assertFalse(d.exists())


if __name__ == "__main__":
    unittest.main()
