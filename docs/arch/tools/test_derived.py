#!/usr/bin/env python3
"""Tests for derived.py: the three tables a view takes from a declared artefact.

Each table is built from the real tree and its rows counted, then each failure
the module names is planted in a small input and has to be refused.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

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

    def test_dictionary_has_one_row_per_declared_term(self):
        rows = body(derived.dictionary(REPO / "ontology"))
        self.assertEqual(len(rows), len(derived.DICTIONARY))


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


if __name__ == "__main__":
    unittest.main()
