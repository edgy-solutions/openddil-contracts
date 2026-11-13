"""Tests for check_views.py.

Run from the worktree root:
    python -m unittest discover -s docs/arch/tools -p "test_*.py"

The real tree is checked once. Each rule is then proved by copying docs/arch
and decisions into a temp tree (keeping their relative distance), breaking
one thing for real, and asserting that rule's FAIL line appears.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCH = HERE.parent
REPO = ARCH.parent.parent
TOOL = HERE / "check_views.py"


def run(root, *extra):
    """check_views on root. The default is partial: quotes and floor need a chart, and have their own tests."""
    args = extra or ("--allow-partial", "test")
    p = subprocess.run([sys.executable, str(TOOL), "--root", str(root), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout, p.stderr


def copy_tree(dest: Path) -> Path:
    """docs/arch, decisions and ontology under dest, same relative distance as in the repo."""
    ignore = shutil.ignore_patterns("__pycache__", "out", "node_modules")
    shutil.copytree(ARCH, dest / "docs" / "arch", ignore=ignore)
    shutil.copytree(REPO / "decisions", dest / "decisions")
    shutil.copytree(REPO / "ontology", dest / "ontology")
    return dest / "docs" / "arch"


def edit(root: Path, rel: str, old: str, new: str, count: int = 1) -> None:
    p = root / rel
    text = p.read_text(encoding="utf-8")
    assert old in text, f"perturbation text not found in {rel}: {old[:60]}"
    p.write_text(text.replace(old, new, count), encoding="utf-8", newline="\n")


class RealTree(unittest.TestCase):
    def test_real_tree_passes(self):
        rc, out, err = run(ARCH)
        self.assertEqual(rc, 0, err)
        self.assertTrue(out.startswith("ok: 15 rules, 29 views"), out)
        self.assertIn("not run: quotes, floor (test)", out)

    def test_bare_invocation_is_bad_input_and_names_the_flags(self):
        rc, out, err = run(ARCH, "--root", str(ARCH))
        self.assertEqual(rc, 2, err)
        for flag in ("--chart", "--values", "--release", "--readiness", "--barred"):
            self.assertIn(flag, err)
        self.assertIn("--allow-partial", err)
        self.assertEqual(out, "")

    def test_allow_partial_with_all_five_is_a_stale_exception(self):
        rc, _, err = run(ARCH, "--chart", "c", "--values", "v", "--release", "r", "--readiness", "x",
                         "--barred", "b", "--allow-partial", "test")
        self.assertEqual(rc, 2, err)
        self.assertIn("stale", err)

    def test_allow_partial_needs_a_reason(self):
        for reason in ("", "  "):
            rc, _, err = run(ARCH, "--allow-partial", reason)
            self.assertEqual(rc, 2, err)

    def test_missing_root_is_bad_input(self):
        rc, _, err = run(ARCH / "nowhere")
        self.assertEqual(rc, 2, err)


class Perturbed(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy_tree(self.tmp)

    def expect(self, rule, *fragments):
        rc, out, err = run(self.root)
        self.assertEqual(rc, 1, f"expected exit 1, got {rc}: {out}{err}")
        lines = [l for l in err.splitlines() if l.startswith(f"FAIL: {rule}:")]
        self.assertTrue(lines, f"no FAIL for {rule} in:\n{err}")
        for frag in fragments:
            self.assertTrue(any(frag in l for l in lines), f"'{frag}' not in {lines}")

    def test_1_exports(self):
        edit(self.root, "profiles.yaml", "exports: {dodaf202: [OV-1], naf4: [L1]}",
             "exports: {dodaf202: [OV-1, ZZ-9], naf4: [L1]}")
        self.expect("exports", "Op-Tx", "ZZ-9")

    def test_1_exports_not_in_appendix(self):
        edit(self.root, "APPENDIX-A.md", "| Resources Connectivity | SV-3, SV-6 |", "| Resources Connectivity | SV-3 |")
        self.expect("exports", "Rs-Cn", "SV-6")

    def test_1_exports_old_mapping_is_wrong(self):
        edit(self.root, "profiles.yaml", "exports: {dodaf202: [DIV-3], naf4: [P7]}",
             "exports: {dodaf202: [DIV-3], naf4: [P7, L7]}")
        self.expect("exports", "Rs-If", "L7")

    def test_2_appendix_a_row_deleted(self):
        p = self.root / "APPENDIX-A.md"
        lines = [l for l in p.read_text(encoding="utf-8").split("\n") if not l.startswith("| Rs-If |")]
        p.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        self.expect("appendix-a", "Rs-If", "no row")

    def test_2_appendix_a_row_duplicated(self):
        row = "| Rs-If | Information: Resources Information | DIV-3 | P7 | - |"
        edit(self.root, "APPENDIX-A.md", row, row + "\n" + row)
        self.expect("appendix-a", "Rs-If", "twice")

    def test_2_appendix_a_header_changed(self):
        edit(self.root, "APPENDIX-A.md", "| View | Name | DoDAF 2.02 | NAF 4.0 | DNDAF |",
             "| View | Name | DoDAF | NAF 4.0 | DNDAF |")
        self.expect("appendix-a", "header")

    def test_2_appendix_a_missing(self):
        (self.root / "APPENDIX-A.md").unlink()
        self.expect("appendix-a", "does not exist")

    def test_2_appendix_a_bad_cell_count(self):
        edit(self.root, "APPENDIX-A.md", "| Rs-If | Information: Resources Information | DIV-3 | P7 | - |",
             "| Rs-If | Information: Resources Information | DIV-3 | P7 |")
        self.expect("appendix-a", "Rs-If", "4 cells")

    def test_2_appendix_a_no_target_reason_is_false(self):
        edit(self.root, "profiles.yaml", "exports: {dodaf202: [DIV-3], naf4: [P7]}",
             'exports: {dodaf202: [DIV-3]}\n    no_target: {naf4: "Nothing."}')
        self.expect("appendix-a", "Rs-If", "naf4")

    def test_2_appendix_a_deviations_key_remains(self):
        p = self.root / "profiles.yaml"
        p.write_text(p.read_text(encoding="utf-8") + "\ndeviations: []\n", encoding="utf-8", newline="\n")
        self.expect("appendix-a", "deviations")

    def test_2_appendix_a_view_key_remains(self):
        edit(self.root, "profiles.yaml", "exports: {dodaf202: [DIV-3], naf4: [P7]}",
             "exports: {dodaf202: [DIV-3], naf4: [P7]}\n    appendix_a: {dodaf202: [DIV-3], naf4: [P7]}")
        self.expect("appendix-a", "Rs-If", "appendix_a")

    def test_3_view_files_bad_first_line(self):
        edit(self.root, "views/Op-Cn.md", "# Operational-Connectivity (Op-Cn)", "# Operational-Connectivity")
        self.expect("view-files", "Op-Cn")

    def test_3_view_files_unlisted_file(self):
        (self.root / "views" / "Zz-Zz.md").write_text("# Extra (Zz-Zz)\n", encoding="utf-8")
        self.expect("view-files", "Zz-Zz.md")

    def test_4_slots_deleted_from_registry(self):
        edit(self.root, "slots.yaml",
             "  system-name:\n    fills: Name of this system in its documents.\n    source: bundle values system.name\n", "")
        self.expect("slots", "system-name is used")

    def test_4_slots_unused_slot_added(self):
        p = self.root / "slots.yaml"
        p.write_text(p.read_text(encoding="utf-8") + "  unused-slot:\n    fills: Nothing.\n    source: none yet\n",
                     encoding="utf-8", newline="\n")
        self.expect("slots", "unused-slot is in slots.yaml and used in no view")

    def test_4_slots_entry_lacks_source(self):
        edit(self.root, "slots.yaml", "    fills: Name of the root tier.\n    source: chart values\n",
             "    fills: Name of the root tier.\n")
        self.expect("slots", "root-node lacks 'source'")

    def test_5_links_broken(self):
        p = self.root / "README.md"
        p.write_text(p.read_text(encoding="utf-8") + "\nSee [gone](views/Nope.md).\n", encoding="utf-8", newline="\n")
        self.expect("links", "README.md", "views/Nope.md")

    def test_5_links_broken_in_appendix(self):
        p = self.root / "APPENDIX-A.md"
        p.write_text(p.read_text(encoding="utf-8") + "\nSee [gone](Nope.md).\n", encoding="utf-8", newline="\n")
        self.expect("links", "APPENDIX-A.md", "Nope.md")

    def test_5_links_broken_in_view(self):
        edit(self.root, "views/Op-Pr.md", "(Rs-Tr.md)", "(Rs-Gone.md)")
        self.expect("links", "Op-Pr.md", "Rs-Gone.md")

    def test_6_sources_table_bad_decision(self):
        edit(self.root, "views/Op-If.md", "| An asset id is opaque inside the system | [ADR-0047](../../../decisions/ADR-0047-asset-id-is-opaque.md) | Accepted |",
             "| An asset id is opaque inside the system | [ADR-0047](../../../decisions/ADR-0047-asset-id-is-opaque.md) | Settled |")
        self.expect("sources-table", "Op-If", "Settled")

    def test_6_sources_table_header(self):
        edit(self.root, "views/Op-If.md", "| Claim | Source | Decision | Evidence |", "| Claim | Source | Decision |")
        self.expect("sources-table", "Op-If", "header")

    def test_6_sources_table_no_link(self):
        edit(self.root, "views/Op-If.md", "[ADR-0047](../../../decisions/ADR-0047-asset-id-is-opaque.md)", "ADR-0047")
        self.expect("sources-table", "Op-If", "no link")

    def test_6_sources_table_no_rows(self):
        p = self.root / "views" / "Sc-Sr.md"
        lines = p.read_text(encoding="utf-8").split("\n")
        i = lines.index("## Sources")
        keep = [l for k, l in enumerate(lines) if k <= i + 3 or not l.startswith("|")]
        p.write_text("\n".join(keep), encoding="utf-8", newline="\n")
        self.expect("sources-table", "Sc-Sr", "no rows")

    def test_7_marks_proposed_flipped_to_accepted(self):
        edit(self.root, "views/Op-If.md", "ADR-0043-egress-gate-one-predicate-two-subjects.md) | Proposed |",
             "ADR-0043-egress-gate-one-predicate-two-subjects.md) | Accepted |")
        self.expect("marks", "ADR-0043")

    def test_7_marks_design_only_flipped_to_built(self):
        edit(self.root, "views/Op-If.md", "ADR-0051-failure-records-for-fracas.md) | Accepted | Status line |",
             "ADR-0051-failure-records-for-fracas.md) | Accepted | Built |")
        self.expect("marks", "ADR-0051", "as Design only", "not Built")

    def test_7_marks_not_stated_on_a_design_record(self):
        # The reader once read ADR- files only, so this row passed against a status line saying Nothing built.
        edit(self.root, "views/Op-Cn.md", "DESIGN-2026-09-06-interface-contracts.md) | Design note | Status line |",
             "DESIGN-2026-09-06-interface-contracts.md) | Design note | Not stated |")
        self.expect("marks", "Op-Cn", "DESIGN-2026-09-06-interface-contracts.md", "as Nothing built", "not Not stated")

    def test_7_marks_copied_word_where_the_token_belongs(self):
        edit(self.root, "views/Op-Cn.md", "DESIGN-2026-09-06-interface-contracts.md) | Design note | Status line |",
             "DESIGN-2026-09-06-interface-contracts.md) | Design note | Nothing built |")
        self.expect("marks", "Op-Cn", "must say Status line, not Nothing built")

    def test_7_marks_token_where_the_status_fixes_nothing(self):
        edit(self.root, "views/Op-If.md", "ADR-0047-asset-id-is-opaque.md) | Accepted | Not stated |",
             "ADR-0047-asset-id-is-opaque.md) | Accepted | Status line |")
        self.expect("marks", "Op-If", "no record it cites fixes the evidence")

    def test_7_marks_token_with_no_record(self):
        edit(self.root, "views/Am-If.md", "(../../../ontology/) | Generated | Generated |",
             "(../../../ontology/) | Generated | Status line |")
        self.expect("marks", "Am-If", "cites no record")

    def test_7_marks_cited_records_disagree(self):
        edit(self.root, "../../decisions/ADR-0042-intent-custody-retention-and-multi-tier-reconciliation.md",
             "Nothing built, and nothing here", "Design only, and nothing here")
        self.expect("marks", "St-Tx", "OfflineIntentReconciliation", "disagree")

    def test_7_marks_a_status_change_reaches_every_citing_row(self):
        edit(self.root, "../../decisions/DESIGN-2026-09-06-interface-contracts.md",
             "PLAN ONLY. Nothing built.", "Approved.")
        rc, out, err = run(self.root)
        self.assertEqual(rc, 1, out + err)
        rows = [l for l in err.splitlines() if l.startswith("FAIL: marks:") and "no record it cites" in l]
        views = sorted({l.split(":")[2].strip() for l in rows})
        self.assertEqual(len(rows), 13, err)
        self.assertEqual(views, ["Op-Cn", "Op-Ct", "Op-Tx", "Rs-Cn", "Rs-If", "Rs-Sr", "Sm-Ov", "Sv-Cn"], err)

    def test_7_marks_accepted_flipped_to_proposed(self):
        edit(self.root, "views/Op-If.md", "ADR-0047-asset-id-is-opaque.md) | Accepted |",
             "ADR-0047-asset-id-is-opaque.md) | Proposed |")
        self.expect("marks", "ADR-0047")

    def test_8_model_package_renamed(self):
        edit(self.root, "model/openddil.sysml", "package Information {", "package InformationModel {")
        self.expect("model", "Information", "InformationModel")

    def test_9_capabilities_row_removed(self):
        p = self.root / "views" / "St-Tx.md"
        lines = [l for l in p.read_text(encoding="utf-8").split("\n") if not l.startswith("| ArrivalDeclaration |")]
        p.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        self.expect("capabilities", "ArrivalDeclaration")

    def test_9_capabilities_name_not_in_model(self):
        edit(self.root, "views/Rs-Tr.md", "| DataAcquisition |", "| DataAcquiring |")
        self.expect("capabilities", "DataAcquiring")

    def test_10_trace_leaf_row_removed(self):
        p = self.root / "views" / "Rs-Tr.md"
        lines = [l for l in p.read_text(encoding="utf-8").split("\n") if not l.startswith("| A1.1 ")]
        p.write_text("\n".join(lines), encoding="utf-8", newline="\n")
        self.expect("trace", "A1.1")

    def test_10_trace_function_missing(self):
        edit(self.root, "views/Rs-Tr.md", "| A1.2 Map semantics | F2 |", "| A1.2 Map semantics | F99 |")
        self.expect("trace", "F99")

    def test_10_trace_activity_not_in_op_pr(self):
        edit(self.root, "views/Rs-Tr.md", "| A1.2 Map semantics |", "| A9.9 Map semantics |")
        self.expect("trace", "A9.9")

    def test_11_outputs_ov1_removed(self):
        edit(self.root, "profiles.yaml", "exports: {dodaf202: [OV-1], naf4: [L1]}", "exports: {naf4: [L1]}")
        self.expect("outputs", "OV-1")

    def test_11_outputs_data_exchange_id_not_exported(self):
        edit(self.root, "profiles.yaml", "exports: {dodaf202: [SV-3, SV-6], naf4: [P3]}",
             "exports: {dodaf202: [SV-3], naf4: [P3]}")
        self.expect("outputs", "SV-6")

    def test_12_generated_twice(self):
        p = self.root / "views" / "Op-If.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n<!-- generated: data-exchange -->\n",
                     encoding="utf-8", newline="\n")
        self.expect("generated", "Op-If")

    def test_12_generated_missing(self):
        edit(self.root, "views/Rs-Cn.md", "<!-- generated: data-exchange -->", "")
        self.expect("generated", "0 times")

    def test_13_phases_capability_missing_from_the_record(self):
        p = self.root / "capability-record.yaml"
        text = p.read_text(encoding="utf-8")
        block = re.search(r"^  TacticalSustainmentCorrelation:\n(?:    .*\n)+", text, re.M)
        assert block, "TacticalSustainmentCorrelation block not found"
        p.write_text(text.replace(block.group(0), ""), encoding="utf-8", newline="\n")
        self.expect("phases", "TacticalSustainmentCorrelation")

    def test_13_phases_capability_with_no_citation(self):
        edit(self.root, "capability-record.yaml", "    adrs: [ADR-0039 §1, ADR-0039 §2]\n    severed: not stated\n    rows: [SV-11]\n", "")
        self.expect("phases", "TacticalSustainmentCorrelation has no phase")

    def test_13_phases_marker_twice(self):
        p = self.root / "views" / "Op-If.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n<!-- generated: capability-phases -->\n",
                     encoding="utf-8", newline="\n")
        self.expect("phases", "Op-If", "2 times")

    def test_13_phases_marker_missing(self):
        edit(self.root, "views/St-Rm-P.md", "<!-- generated: capability-phases -->", "")
        self.expect("phases", "0 times")

    def test_14_derived_marker_missing(self):
        edit(self.root, "views/Rs-Tx.md", "<!-- generated: resource-taxonomy -->", "")
        self.expect("derived", "resource-taxonomy", "0 times", "expected once, in Rs-Tx")

    def test_14_derived_marker_outside_its_view(self):
        edit(self.root, "views/St-Cn.md", "<!-- generated: capability-dependencies -->", "")
        p = self.root / "views" / "Op-Sq.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n<!-- generated: capability-dependencies -->\n",
                     encoding="utf-8", newline="\n")
        self.expect("derived", "1 times, in Op-Sq", "expected once, in St-Cn")

    def test_14_derived_table_cannot_build(self):
        (self.root.parent.parent / "ontology" / "new_terms.yaml").write_text("terms: []\n", encoding="utf-8")
        self.expect("derived", "ontology/new_terms.yaml has no dictionary row")

    def test_14_derived_traceability_real_citation_removed(self):
        import re
        for rel in ("views/St-Tx.md", "capability-record.yaml"):
            p = self.root / rel
            p.write_text(re.sub(r"ADR-0057(?!\d)", "ADR-0000", p.read_text(encoding="utf-8")),
                         encoding="utf-8", newline="\n")
        self.expect("derived", "ADR-0057 (")

    def test_4_slots_inventory_line_removed(self):
        edit(self.root, "INVENTORY.md", "| `increment-dates` |", "| `not-a-slot-line` |")
        self.expect("slots", "increment-dates has no source and no line",
                    "names not-a-slot-line, which slots.yaml does not hold")

    def test_4_slots_inventory_line_for_a_sourced_slot(self):
        edit(self.root, "INVENTORY.md", "| `increment-dates` |", "| `tier-tree` | a | b |\n| `increment-dates` |")
        self.expect("slots", "tier-tree has a source in slots.yaml and still a line")

    def test_4_slots_inventory_table_missing(self):
        edit(self.root, "INVENTORY.md", "| Slot | Declaration that would fill it | Artefact |", "| Slot | Fill | Artefact |")
        self.expect("slots", "0 slot tables")


class DecisionLinks(unittest.TestCase):
    """rule_decision_links, on a tree whose St-Tx links carry a section (the stub the author's content will match)."""

    def setUp(self):
        sys.path.insert(0, str(HERE / "testdata"))
        import stub_content
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        stub_content.stub_tree(self.tmp, repo=False)
        self.root = self.tmp / "docs" / "arch"
        self.tx = (self.root / "views" / "St-Tx.md").read_text(encoding="utf-8")

    def lines(self):
        rc, out, err = run(self.root)
        return rc, [l for l in err.splitlines() if l.startswith("FAIL: decision-links:")]

    def test_the_stub_passes_the_rule(self):
        self.assertEqual(self.lines()[1], [])

    def test_a_link_without_a_section_fails(self):
        import re
        m = re.search(r"\[(ADR-\d{4}) §[^\]]+\]", self.tx)
        edit(self.root, "views/St-Tx.md", m.group(0), f"[{m.group(1)}]")
        rc, got = self.lines()
        self.assertEqual(rc, 1)
        self.assertTrue(any("St-Tx" in l and m.group(1) in l for l in got), got)

    def test_a_section_the_record_lacks_fails(self):
        import re
        m = re.search(r"\[(ADR-\d{4}) §[^\]]+\]", self.tx)
        edit(self.root, "views/St-Tx.md", m.group(0), f"[{m.group(1)} §99]")
        rc, got = self.lines()
        self.assertEqual(rc, 1)
        self.assertTrue(any("99" in l for l in got), got)


class RecordFlag(unittest.TestCase):
    """--record: a deployment's own capability record, read in place of <root>/capability-record.yaml."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = copy_tree(self.tmp / "tree")
        shutil.copytree(REPO / ".github", self.tmp / "tree" / ".github")  # the links rule resolves workflow files
        self.rec = self.tmp / "own-record.yaml"
        shutil.copyfile(ARCH / "capability-record.yaml", self.rec)

    def test_a_copy_outside_the_tree_passes(self):
        rc, out, err = run(self.root, "--record", str(self.rec), "--allow-partial", "test")
        self.assertEqual(rc, 0, err)

    def test_the_flag_is_read_not_the_root_copy(self):
        text = self.rec.read_text(encoding="utf-8")
        self.assertIn("adrs: [ADR-0038", text)
        self.rec.write_text(text.replace("adrs: [ADR-0038", "adrs: [ADR-9999", 1),
                            encoding="utf-8", newline=chr(10))
        rc, out, err = run(self.root, "--record", str(self.rec), "--allow-partial", "test")
        self.assertEqual(rc, 1, err)
        self.assertTrue(any(l.startswith("FAIL: phases:") for l in err.splitlines()), err)
        rc, out, err = run(self.root)
        self.assertEqual(rc, 0, err)

    def test_a_missing_record_is_bad_input_and_names_the_path(self):
        gone = self.tmp / "nowhere.yaml"
        rc, out, err = run(self.root, "--record", str(gone), "--allow-partial", "test")
        self.assertEqual(rc, 2, err)
        self.assertIn(str(gone), err)
        self.assertNotIn("Traceback", err)

    def test_floor_reads_the_given_record(self):
        repos = os.environ.get("OPENDDIL_REPOS")
        bundle = os.environ.get("OPENDDIL_BUNDLE")
        if not repos or not bundle:
            self.skipTest("OPENDDIL_REPOS and OPENDDIL_BUNDLE not set: no chart to render")
        r, b = Path(repos), Path(bundle)
        inputs = ["--chart", str(r / "openddil-helm" / "openddil-demo"),
                  "--values", str(b / "k8s" / "tier-node-values.yaml"),
                  "--values", str(b / "k8s" / "egress-values.yaml"),
                  "--release", "openddil",
                  "--readiness", str(r / "openddil-helm" / "scripts" / "RECORDING-READINESS.md"),
                  "--barred", str(HERE / "barred-sample.txt")]
        NL = chr(10)
        text = self.rec.read_text(encoding="utf-8")
        head, sep, tail = text.partition(NL + "rendered:" + NL + "  workload:" + NL)
        self.assertTrue(sep, "no rendered.workload section")
        lines = tail.splitlines(keepends=True)
        self.assertTrue(lines[0].startswith("    "), lines[0])
        self.rec.write_text(head + sep + "".join(lines[1:]), encoding="utf-8", newline=chr(10))
        rc, out, err = run(self.root, "--record", str(self.rec), *inputs)
        self.assertEqual(rc, 1, err)
        self.assertTrue(any(l.startswith("FAIL: floor:") for l in err.splitlines()), err)


if __name__ == "__main__":
    unittest.main()
