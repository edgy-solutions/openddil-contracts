#!/usr/bin/env python3
"""Tests for derived.py: the four tables a view takes from a declared artefact.

Each table is built from the real tree and its rows counted, then each failure
the module names is planted in a small input and has to be refused.
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capability_phases as cp  # noqa: E402
import derived  # noqa: E402
from render_profile import mask_sysml  # noqa: E402

ARCH = HERE.parent
REPO = ARCH.parent.parent

ROADMAP = """\
| # | increment | what isolates | home | depends on |
|---|---|---|---|---|
| 0 | **Base** | a | b | — |
| 1 | **Gate** | a | b | 0: base |
| 2 | **Bridge** | a | b | the Gate |

| row | slice | folds into | why it costs the increment nothing |
|---|---|---|---|
| A | Labels (ADR-0001) | increment 1 | it rides |
"""

RECORD = {"capabilities": {
    "C-Base": {"increment": "Base", "adrs": ["ADR-0001"]},
    "C-Gate": {"increment": "Gate"},
    "C-Bridge": {"increment": "Bridge"},
}}

MODEL = """\
package ResourceKit {
    abstract part def Member;
    part def Broker :> Member;
    part def Node {
        part broker : Broker [1];
        part spare : Broker;
    }
}
"""


def body_after_head(text: str) -> str:
    """The table of a text that opens with a line and a blank line."""
    return text.split("\n\n", 1)[1]


def body(table: str) -> list[str]:
    return table.split("\n")[2:]


class RealTree(unittest.TestCase):
    def test_dependencies_builds_one_row_per_increment_and_fold_in(self):
        roadmap = (REPO / "decisions" / cp.ROADMAP).read_text(encoding="utf-8")
        record = cp.load_record(ARCH / "capability-record.yaml")
        rows = body(derived.dependencies(record, roadmap))
        increments = derived.table_with(roadmap, derived.ROADMAP_HEADER, "increment")
        folds = derived.table_with(roadmap, derived.FOLD_HEADER, "fold-in")
        self.assertEqual(len(rows), len(increments) + len(folds))

    def test_taxonomy_lists_every_resource_kit_type(self):
        sysml = (ARCH / "model" / "openddil.sysml").read_text(encoding="utf-8")
        rows = body(derived.taxonomy(sysml, mask_sysml(sysml)))
        self.assertGreater(len(rows), 0)
        self.assertTrue(any("| KitMember | abstract |" in r for r in rows), rows)

    def test_severed_behaviour_has_one_row_per_capability_in_model_order(self):
        sysml = (ARCH / "model" / "openddil.sysml").read_text(encoding="utf-8")
        record = cp.load_record(ARCH / "capability-record.yaml")
        out = derived.severed(record, sysml)
        names = list(cp.model_capabilities(sysml))
        rows = body(body_after_head(out))
        self.assertEqual([r.split(" | ")[0].lstrip("| ") for r in rows], names)
        stated = sum(1 for n in names if record["capabilities"][n]["severed"] != "not stated")
        self.assertTrue(out.startswith(f"Severed behaviour: {stated} of {len(names)} capabilities have it stated "
                                       f"in a decision record; {len(names) - stated} do not.\n\n"
                                       "| Capability |"))

    def test_dictionary_has_one_row_per_declared_term(self):
        rows = body(derived.dictionary(REPO / "ontology"))
        self.assertEqual(len(rows), len(derived.DICTIONARY))


SEVERED_MODEL = """\
package CapabilityTaxonomy {
    abstract occurrence def Capability;
    occurrence def Alpha :> Capability;
    occurrence def Beta :> Capability;
}
"""


class Severed(unittest.TestCase):
    def rec(self, **caps):
        return {"capabilities": {k: dict(v) for k, v in caps.items()}}

    def test_the_table_the_spec_shows(self):
        out = derived.severed(self.rec(Alpha={"severed": "ADR-0029 §6"},
                                       Beta={"severed": "not stated", "rows": ["AE-1", "SV-1", "SV-3"]}),
                              SEVERED_MODEL)
        self.assertEqual(out, "Severed behaviour: 1 of 2 capabilities have it stated in a decision record; 1 do not.\n\n"
                              "| Capability | Severed behaviour | Row |\n|---|---|---|\n"
                              "| Alpha | stated in ADR-0029 §6 | - |\n"
                              "| Beta | not stated | SV-1, SV-3 |")

    def test_a_capability_without_the_key_is_refused(self):
        with self.assertRaises(cp.CheckError) as cm:
            derived.severed(self.rec(Alpha={"severed": "not stated", "rows": ["SV-1"]}, Beta={}), SEVERED_MODEL)
        self.assertIn("Beta has no severed entry", cm.exception.args[0])

    def test_the_marker_belongs_to_st_tx(self):
        self.assertEqual(derived.HOMES[derived.SEVERED_MARKER], "St-Tx")
        self.assertEqual(derived.SEVERED_MARKER, "<!-- generated: severed-behaviour -->")


class Dependencies(unittest.TestCase):
    def test_small_input_builds(self):
        rows = body(derived.dependencies(RECORD, ROADMAP))
        self.assertEqual(rows, [
            "| Base | C-Base | none | |",
            "| Gate | C-Gate | Base: C-Base | Needs |",
            "| Bridge | C-Bridge | Gate: C-Gate | Needs |",
            "| Labels (fold-in A) | C-Base | Gate: C-Gate | Rides with, not a dependency |",
        ])

    def test_cell_naming_no_increment_is_refused(self):
        with self.assertRaisesRegex(cp.CheckError, "names 0 increments"):
            derived.dependencies(RECORD, ROADMAP.replace("the Gate", "the uplink"))

    def test_cell_naming_two_increments_is_refused(self):
        with self.assertRaisesRegex(cp.CheckError, "names 2 increments"):
            derived.dependencies(RECORD, ROADMAP.replace("the Gate", "the Gate and the Base"))

    def test_unnumbered_increment_is_refused(self):
        with self.assertRaisesRegex(cp.CheckError, "increment 7, which the note does not number"):
            derived.dependencies(RECORD, ROADMAP.replace("0: base", "7: base"))

    def test_increment_with_no_capability_is_refused(self):
        record = {"capabilities": {k: v for k, v in RECORD["capabilities"].items() if k != "C-Bridge"}}
        with self.assertRaisesRegex(cp.CheckError, "increment 'Bridge' has no capability"):
            derived.dependencies(record, ROADMAP)

    def test_capability_naming_a_missing_increment_is_refused(self):
        record = {"capabilities": dict(RECORD["capabilities"], **{"C-Lost": {"increment": "Lost"}})}
        with self.assertRaisesRegex(cp.CheckError, "C-Lost names increment 'Lost'"):
            derived.dependencies(record, ROADMAP)

    def test_fold_in_citing_an_uncited_adr_is_refused(self):
        with self.assertRaisesRegex(cp.CheckError, "fold-in A cites ADR-0009, which no capability cites"):
            derived.dependencies(RECORD, ROADMAP.replace("ADR-0001", "ADR-0009"))

    def test_fold_in_naming_no_increment_is_refused(self):
        with self.assertRaisesRegex(cp.CheckError, "fold-in A names no numbered increment"):
            derived.dependencies(RECORD, ROADMAP.replace("increment 1 |", "the gate |"))

    def test_missing_table_is_refused(self):
        with self.assertRaisesRegex(cp.CheckError, "0 fold-in tables"):
            derived.dependencies(RECORD, ROADMAP.split("\n\n")[0])


class Taxonomy(unittest.TestCase):
    def test_small_model_builds(self):
        rows = body(derived.taxonomy(MODEL, mask_sysml(MODEL)))
        self.assertEqual(rows, [
            "| Member | abstract | none | none |",
            "| Broker | member | Member | Node.broker [1]; Node.spare (multiplicity not stated) |",
            "| Node | composite | none | none |",
        ])

    def test_unknown_supertype_is_refused(self):
        model = MODEL.replace(":> Member", ":> Thing")
        with self.assertRaisesRegex(cp.CheckError, "Broker specialises Thing"):
            derived.taxonomy(model, mask_sysml(model))

    def test_unknown_part_type_is_refused(self):
        model = MODEL.replace("spare : Broker", "spare : Relay")
        with self.assertRaisesRegex(cp.CheckError, "a part is typed Relay"):
            derived.taxonomy(model, mask_sysml(model))

    def test_missing_package_is_refused(self):
        model = MODEL.replace("ResourceKit", "OtherKit")
        with self.assertRaisesRegex(cp.CheckError, "no package ResourceKit"):
            derived.taxonomy(model, mask_sysml(model))


class Dictionary(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.onto = self.tmp / "ontology"
        shutil.copytree(REPO / "ontology", self.onto)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_file_with_no_row_is_refused(self):
        (self.onto / "new_terms.yaml").write_text("terms: []\n", encoding="utf-8")
        with self.assertRaisesRegex(cp.CheckError, "ontology/new_terms.yaml has no dictionary row"):
            derived.dictionary(self.onto)

    def test_missing_file_is_refused(self):
        name = derived.DICTIONARY[0][0]
        (self.onto / name).unlink()
        with self.assertRaisesRegex(cp.CheckError, f"names ontology/{name}, which does not exist"):
            derived.dictionary(self.onto)

    def test_missing_term_is_refused(self):
        name, path = "platform_reference.yaml", "platforms"
        (self.onto / name).write_text("other: []\n", encoding="utf-8")
        with self.assertRaisesRegex(cp.CheckError, f"ontology/{name} has no {path}"):
            derived.dictionary(self.onto)

    def test_empty_term_counts_zero(self):
        (self.onto / "platform_reference.yaml").write_text("platforms: []\n", encoding="utf-8")
        rows = body(derived.dictionary(self.onto))
        self.assertIn("| platform_reference.yaml | platforms | empty list | 0 | none |", rows)

    def test_single_value_is_refused(self):
        (self.onto / "platform_reference.yaml").write_text("platforms: 3\n", encoding="utf-8")
        with self.assertRaisesRegex(cp.CheckError, "is a single value, not a term"):
            derived.dictionary(self.onto)

    def test_no_entry_value_reaches_the_table(self):
        (self.onto / "platform_reference.yaml").write_text(
            "platforms:\n  - name: PLANTED-ENTRY-VALUE\n    code: 7\n", encoding="utf-8")
        table = derived.dictionary(self.onto)
        self.assertIn("| platform_reference.yaml | platforms | records | 1 | code, name |", table)
        self.assertNotIn("PLANTED-ENTRY-VALUE", table)


class Traceability(unittest.TestCase):
    """The real tree builds; then one real thing is changed per case on a temp copy."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dec = self.tmp / "decisions"
        self.views = self.tmp / "views"
        self.record = self.tmp / "capability-record.yaml"
        self.ex = self.tmp / "adr-exemptions.yaml"
        shutil.copytree(REPO / "decisions", self.dec)
        shutil.copytree(ARCH / "views", self.views)
        shutil.copy(ARCH / "capability-record.yaml", self.record)
        shutil.copy(ARCH / "adr-exemptions.yaml", self.ex)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self) -> str:
        return derived.traceability(self.dec, self.views, cp.load_record(self.record), self.ex)

    def refused(self, *needles: str) -> str:
        with self.assertRaises(cp.CheckError) as c:
            self.build()
        for n in needles:
            self.assertIn(n, str(c.exception))
        return str(c.exception)

    def set_exempt(self, change) -> None:
        data = yaml.safe_load(self.ex.read_text(encoding="utf-8"))
        change(data["exempt"])
        self.ex.write_text(yaml.safe_dump(data), encoding="utf-8")

    def new_adr(self, status: str) -> None:
        (self.dec / "ADR-0099-x.md").write_text(f"# ADR-0099: Planted\n\n## Status\n\n{status}\n", encoding="utf-8")

    def test_real_tree_builds(self):
        out = self.build()
        blocks = out.split("\n\n")
        self.assertRegex(blocks[0], r"^\d+ decision records\. \d+ accepted or proposed: \d+ cited by a view, 4 exempt\. \d+ not required\.$")
        self.assertTrue(blocks[1].startswith("| Not cited |"))
        findings = [r.split(" ")[1] for r in blocks[1].split("\n")[2:]]
        self.assertEqual([r[2:10] for r in blocks[1].split("\n")[2:]], ["ADR-0011", "ADR-0025", "ADR-0027", "ADR-0028"])
        self.assertTrue(blocks[2].startswith("| Not required |"))
        self.assertIn("| ADR-0015 ", blocks[2])
        files = list(self.dec.glob("ADR-*.md"))
        matrix = blocks[3].split("\n")
        self.assertEqual(matrix[0], "| ADR | Status | Cited by |")
        self.assertEqual(len(matrix) - 2, len(files))
        row = next(r for r in matrix if r.startswith("| ADR-0057 |"))
        self.assertIn("St-Rm-P", row)
        self.assertIn("St-Tx", row)

    def test_real_citation_removed_is_named(self):
        p = self.views / "St-Tx.md"
        p.write_text(re.sub(r"ADR-0057(?!\d)", "the decision", p.read_text(encoding="utf-8")), encoding="utf-8")
        rec = yaml.safe_load(self.record.read_text(encoding="utf-8"))
        for cap in rec["capabilities"].values():
            if "adrs" in cap:
                cap["adrs"] = [a for a in cap["adrs"] if a.split()[0] != "ADR-0057"]
            if "still_open" in cap:
                cap["still_open"] = [o for o in cap["still_open"] if o.get("adr", "").split()[:1] != ["ADR-0057"]]
        self.record.write_text(yaml.safe_dump(rec, sort_keys=False), encoding="utf-8")
        self.refused("ADR-0057")

    def test_real_exemption_removed_is_named(self):
        self.set_exempt(lambda e: e.pop("ADR-0011"))
        self.refused("ADR-0011", "is cited by no view")

    def test_stale_exemption_is_named(self):
        self.set_exempt(lambda e: e.update({"ADR-0029": {"category": "rule", "reason": "planted"}}))
        self.refused("ADR-0029", "cited by")

    def test_unknown_category_fails(self):
        self.set_exempt(lambda e: e["ADR-0011"].update({"category": "planted"}))
        self.refused("ADR-0011", "category")

    def test_empty_and_missing_reason_fail(self):
        self.set_exempt(lambda e: e["ADR-0011"].update({"reason": ""}))
        self.refused("ADR-0011", "no reason")
        self.set_exempt(lambda e: e["ADR-0011"].pop("reason"))
        self.refused("ADR-0011", "no reason")

    def test_unknown_key_fails(self):
        self.set_exempt(lambda e: e["ADR-0011"].update({"note": "x"}))
        self.refused("ADR-0011", "'note'")

    def test_out_of_scope_and_fileless_exemptions_fail(self):
        self.set_exempt(lambda e: e.update({"ADR-0015": {"category": "rule", "reason": "planted"}}))
        self.refused("ADR-0015", "superseded")
        self.set_exempt(lambda e: (e.pop("ADR-0015"), e.update({"ADR-9999": {"category": "rule", "reason": "planted"}})))
        self.refused("ADR-9999", "no decision record")

    def test_new_decision_files(self):
        self.new_adr("Accepted")
        self.refused("ADR-0099", "is cited by no view")
        self.new_adr("Superseded by ADR-0010")
        out = self.build()
        not_required = out.split("\n\n")[2]
        self.assertTrue(not_required.startswith("| Not required |"))
        self.assertIn("| ADR-0099 ", not_required)
        self.new_adr("Draft")
        self.refused("ADR-0099 has no status beginning")

    def test_missing_exemptions_file_is_an_input_error(self):
        self.ex.unlink()
        with self.assertRaises(derived.InputError):
            self.build()

    def test_pipe_in_a_title_is_escaped(self):
        (self.dec / "ADR-0099-x.md").write_text("# ADR-0099: A | B\n\nStatus: Rejected\n", encoding="utf-8")
        self.assertIn("A \| B", self.build())

    def test_the_framework_name_in_a_title_is_not_printed(self):
        (self.dec / "ADR-0099-x.md").write_text("# ADR-0099: OpenDDIL Is Planted\n\nStatus: Rejected\n", encoding="utf-8")
        out = self.build()
        self.assertIn("ADR-0099 the framework Is Planted", out)
        self.assertNotIn("OpenDDIL", out)


if __name__ == "__main__":
    unittest.main()
