"""Tests for check_views.py.

Run from the worktree root:
    python -m unittest discover -s docs/arch/tools -p "test_*.py"

The real tree is checked once. Each rule is then proved by copying docs/arch
and decisions into a temp tree (keeping their relative distance), breaking
one thing for real, and asserting that rule's FAIL line appears.
"""
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
        self.assertTrue(out.startswith("ok: 14 rules"), out)
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
        edit(self.root, "views/Op-If.md", "ADR-0051-failure-records-for-fracas.md) | Accepted | Design only |",
             "ADR-0051-failure-records-for-fracas.md) | Accepted | Built |")
        self.expect("marks", "ADR-0051", "design only")

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
        edit(self.root, "capability-record.yaml", "  TacticalSustainmentCorrelation:\n    adrs: [ADR-0039]\n", "")
        self.expect("phases", "TacticalSustainmentCorrelation")

    def test_13_phases_capability_with_no_citation(self):
        edit(self.root, "capability-record.yaml", "  TacticalSustainmentCorrelation:\n    adrs: [ADR-0039]\n",
             "  TacticalSustainmentCorrelation: {}\n")
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


if __name__ == "__main__":
    unittest.main()
