"""Tests for capability_phases.py.

Run from the worktree root:
    python -m unittest discover -s docs/arch/tools -p "test_*.py"

Fixtures are temp directories holding their own model text, record,
decision records, templates and readiness text. The last class reads the
real record against the real sources, and skips, printing why, when the
chart or its readiness doc is not beside this repository.
"""
import copy
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capability_phases as cp  # noqa: E402

ARCH = HERE.parent
REPO = ARCH.parent.parent
SIBLINGS = Path(os.environ.get("OPENDDIL_REPOS", HERE.parents[3]))
CHART = SIBLINGS / "openddil-helm" / "openddil-demo"
READINESS = CHART.parent / "scripts" / "RECORDING-READINESS.md"
MARKER = "ZZMARKER"

MODEL = """\
package Other {
    occurrence def Stray :> Elsewhere;
}
package CapabilityTaxonomy {
    abstract occurrence def Capability;
    abstract occurrence def LaneOne :> Capability;
    occurrence def Alpha :> LaneOne;
    occurrence def Beta :> LaneOne;
    // occurrence def Hidden :> LaneOne;
    occurrence def Gamma :> Capability;
}
"""

READINESS_TEXT = f"""\
# Readiness

## A. First section — words after the dash
{MARKER} intro line
**RUN 2026-09-26 anchor one**
| 1 | alpha | ok |
| 2.1 | beta | fine |
| 3 | twice | x |
| 4 | twice | y |
* **Prose item** runs over
  two lines and then
  ends here. {MARKER} after the stop.
### A sub heading
| 5 | past | the heading |
## B. Second section — redone 2026-10-01
{MARKER} second section line
- dashed line ends at once.
"""

ADR_TEXT = "# {n}\n\n## Status\n\n{s}\n\n## Context\n\nStill open: the thing.\n"

README = """\
- [ADR-0001: one](ADR-0001-one.md) — **accepted** and built.
- [ADR-0002: two](ADR-0002-two.md) — **proposed.**
- [ADR-0003: three](ADR-0003-three.md) — **accepted.**
- [ADR-0005: five](ADR-0005-five.md) — **accepted (v2).**
"""

FOLLOW_UPS = """\
| ID | Subject | Status |
|---|---|---|
| AE-1 | open one | open |
| AE-2 | done one | fixed in abc |

other text

| ID | Subject | Status |
|---|---|---|
| GD-1 | debt one | open |
| GD-2 | debt two | open |
"""

DEBT = "# Debt\n\nGD-1 is here.\n"

ROADMAP = """\
| # | increment | what |
|---|---|---|
| done (not counted) | **Done one** | x |
| 1 | **First one** | y |
"""

TEMPLATE = "kind: Deployment\nname: foo-bar\n"


def base_record() -> dict:
    return {
        "lanes": {"LaneOne": "Lane one", "Capability": "Top"},
        "labs": {"A": "the first lab cluster", "B": "the second lab cluster"},
        "entries": {
            "e1": {"anchor": "RUN 2026-09-26 anchor one", "lab": "A"},
            "e2": {"anchor": "## B. Second section", "lab": "B"},
        },
        "capabilities": {
            "Alpha": {"adrs": ["ADR-0001"], "built": [{"template": "t.yaml", "contains": "foo-bar"}],
                      "measured": [{"entry": "e1", "line": "| 1 | alpha"}]},
            "Beta": {"adrs": ["ADR-0002"], "increment": "**First one**"},
            "Gamma": {"rows": ["AE-1"]},
        },
    }


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dec = self.tmp / "decisions"
        self.tpl = self.tmp / "templates"
        self.dec.mkdir()
        self.tpl.mkdir()
        self.put("ADR-0001-one.md", ADR_TEXT.format(n="ADR-0001", s="Accepted. Built, measured and red-checked."))
        self.put("ADR-0002-two.md", ADR_TEXT.format(n="ADR-0002", s="**Proposed**"))
        self.put("ADR-0003-three.md", ADR_TEXT.format(n="ADR-0003", s="Accepted"))
        self.put("ADR-0004-four.md", ADR_TEXT.format(n="ADR-0004", s="Accepted"))  # not in the index
        self.put("ADR-0005-five.md", ADR_TEXT.format(n="ADR-0005", s="Superseded by something"))
        self.put("README.md", README)
        self.put("FOLLOW-UPS.md", FOLLOW_UPS)
        self.put("GENERALIZATION-DEBT.md", DEBT)
        self.put(cp.ROADMAP, ROADMAP)
        (self.tpl / "t.yaml").write_text(TEMPLATE, encoding="utf-8")
        self.caps = cp.model_capabilities(MODEL)
        self.rec = base_record()

    def put(self, name, text):
        (self.dec / name).write_text(text, encoding="utf-8", newline="\n")

    def check(self, rec=None):
        return cp.check_record(rec or self.rec, self.caps, self.dec)

    def render(self, rec=None, readiness=READINESS_TEXT):
        return cp.render_table(rec or self.rec, self.caps, self.dec, self.tpl, readiness)

    def render_fails(self, rec=None, readiness=READINESS_TEXT) -> str:
        with self.assertRaises(cp.CheckError) as cm:
            self.render(rec, readiness)
        text = cm.exception.args[0]
        self.assertNotIn(MARKER, text)
        return text

    def row(self, table, name):
        return next(ln for ln in table.split("\n") if ln.startswith(f"| {name} |"))

    def cells(self, table, name):
        return [c.strip() for c in re.split(r"(?<!\\)\|", self.row(table, name).strip().strip("|"))]


class Model(Fixture):
    def test_concrete_capabilities_in_order_from_the_taxonomy_only(self):
        self.assertEqual(self.caps, {"Alpha": "LaneOne", "Beta": "LaneOne", "Gamma": "Capability"})

    def test_load_record(self):
        p = self.tmp / "r.yaml"
        p.write_text("lanes: {}\nlabs: {}\nentries: {}\ncapabilities: {}\n", encoding="utf-8")
        self.assertEqual(cp.load_record(p)["lanes"], {})
        for text in ("not: [valid", "- a list\n", "lanes: {}\n"):
            p.write_text(text, encoding="utf-8")
            with self.assertRaises(cp.InputError):
                cp.load_record(p)
        with self.assertRaises(cp.InputError):
            cp.load_record(self.tmp / "missing.yaml")


class Phases(Fixture):
    ST = {"ADR-0001": "accepted", "ADR-0002": "proposed", "ADR-0003": "accepted (v2)"}

    def phase(self, **cap):
        return cp.phase_of(cap, self.ST)

    def test_each_phase(self):
        self.assertEqual(self.phase(adrs=["ADR-0001"], measured=[{"entry": "e1", "line": "x"}]), "measured")
        self.assertEqual(self.phase(built=[{"template": "t", "contains": "c"}]), "built unmeasured")
        self.assertEqual(self.phase(adrs=["ADR-0001"]), "accepted design")
        self.assertEqual(self.phase(adrs=["ADR-0002"]), "proposed")
        self.assertEqual(self.phase(still_open=[{"adr": "ADR-0001", "says": "x"}]), "proposed")
        self.assertEqual(self.phase(rows=["AE-1"]), "row")
        self.assertIsNone(self.phase())

    def test_accepted_beats_proposed(self):
        self.assertEqual(self.phase(adrs=["ADR-0002", "ADR-0001"]), "accepted design")
        self.assertEqual(self.phase(adrs=["ADR-0001"], still_open=[{"adr": "ADR-0002", "says": "x"}]),
                         "accepted design")

    def test_built_beats_accepted_and_measured_beats_built(self):
        built = [{"template": "t", "contains": "c"}]
        self.assertEqual(self.phase(adrs=["ADR-0001"], built=built), "built unmeasured")
        self.assertEqual(self.phase(adrs=["ADR-0001"], built=built, rows=["AE-1"],
                                    measured=[{"entry": "e1", "line": "x"}]), "measured")

    def test_row_is_the_lowest(self):
        self.assertEqual(self.phase(adrs=["ADR-0002"], rows=["AE-1"]), "proposed")

    def test_fixture_phases_come_out_of_the_table(self):
        t = self.render()
        self.assertEqual([self.cells(t, n)[2] for n in ("Alpha", "Beta", "Gamma")],
                         ["measured", "proposed", "row"])


class CheckRecord(Fixture):
    def fails(self, mutate):
        mutate(self.rec)
        return "\n".join(self.check())

    def test_the_base_record_passes(self):
        self.assertEqual(self.check(), [])

    def test_no_citation_has_no_phase(self):
        self.assertIn("Gamma has no phase", self.fails(lambda r: r["capabilities"].update(Gamma={})))
        self.assertIn("Gamma has no phase", self.fails(lambda r: r["capabilities"].update(Gamma={"increment": "**First one**"})))

    def test_a_phase_or_evidence_field_is_an_error(self):
        self.assertIn("'phase'", self.fails(lambda r: r["capabilities"]["Beta"].update(phase="measured")))
        self.assertIn("'evidence'", self.fails(lambda r: r["capabilities"]["Beta"].update(evidence="x")))

    def test_capability_missing_from_the_record(self):
        self.assertIn("Beta is a capability in the model", self.fails(lambda r: r["capabilities"].pop("Beta")))

    def test_record_entry_not_in_the_model(self):
        self.assertIn("Delta is in the record", self.fails(lambda r: r["capabilities"].update(Delta={"rows": ["AE-1"]})))

    def test_hidden_and_abstract_are_not_model_capabilities(self):
        self.assertNotIn("Hidden", self.caps)
        self.assertNotIn("LaneOne", self.caps)

    def test_missing_lane(self):
        self.assertIn("LaneOne has no lanes entry", self.fails(lambda r: r["lanes"].pop("LaneOne")))

    def test_unknown_adr(self):
        out = self.fails(lambda r: r["capabilities"]["Beta"].update(adrs=["ADR-0099"]))
        self.assertIn("Beta: ADR-0099 is not exactly one file", out)

    def test_two_files_for_one_adr(self):
        self.put("ADR-0002-copy.md", ADR_TEXT.format(n="ADR-0002", s="Proposed"))
        self.assertIn("ADR-0002 is not exactly one file", "\n".join(self.check()))

    def test_adr_absent_from_the_index(self):
        out = self.fails(lambda r: r["capabilities"]["Beta"].update(adrs=["ADR-0004"]))
        self.assertIn("Beta: ADR-0004 is not in decisions/README.md", out)

    def test_status_neither_accepted_nor_proposed(self):
        out = self.fails(lambda r: r["capabilities"]["Beta"].update(adrs=["ADR-0005"]))
        self.assertIn("Beta: ADR-0005 has no readable ## Status line beginning accepted or proposed", out)

    def test_unknown_row(self):
        self.assertIn("row AE-9 is not in", self.fails(lambda r: r["capabilities"]["Gamma"].update(rows=["AE-9"])))

    def test_fixed_row(self):
        self.assertIn("row AE-2 is fixed", self.fails(lambda r: r["capabilities"]["Gamma"].update(rows=["AE-2"])))

    def test_gd_row_missing_from_the_debt_file(self):
        self.assertIn("row GD-2 is not in decisions/GENERALIZATION-DEBT.md",
                      self.fails(lambda r: r["capabilities"]["Gamma"].update(rows=["GD-2"])))

    def test_gd_row_present_passes(self):
        self.rec["capabilities"]["Gamma"]["rows"] = ["GD-1"]
        self.assertEqual(self.check(), [])

    def test_still_open_text_absent(self):
        self.rec["capabilities"]["Beta"]["still_open"] = [{"adr": "ADR-0001", "says": "Still open"}]
        self.assertEqual(self.check(), [])
        self.rec["capabilities"]["Beta"]["still_open"] = [{"adr": "ADR-0001", "says": "never written"}]
        self.assertIn("ADR-0001 does not contain 'never written'", "\n".join(self.check()))

    def test_increment_not_on_a_roadmap_row(self):
        self.assertIn("increment **Nope** is not on a table row",
                      self.fails(lambda r: r["capabilities"]["Beta"].update(increment="**Nope**")))

    def test_unknown_entry(self):
        out = self.fails(lambda r: r["capabilities"]["Alpha"]["measured"].append({"entry": "e9", "line": "x"}))
        self.assertIn("Alpha: measured names entry e9", out)

    def test_unknown_lab(self):
        self.assertIn("entry e1 names lab Z", self.fails(lambda r: r["entries"]["e1"].update(lab="Z")))


class RenderFailures(Fixture):
    def test_the_base_record_renders(self):
        self.assertIn("| Alpha |", self.render())

    def test_anchor_not_found(self):
        self.rec["entries"]["e1"]["anchor"] = "no such anchor"
        self.assertIn("entry e1: anchor 'no such anchor' is on 0 readiness lines", self.render_fails())

    def test_anchor_on_two_lines(self):
        self.rec["entries"]["e1"]["anchor"] = "| twice |"
        self.assertIn("anchor '| twice |' is on 2 readiness lines", self.render_fails())

    def test_no_date_on_the_anchor_line(self):
        self.rec["entries"]["e1"]["anchor"] = "intro line"
        self.assertIn("the line of anchor 'intro line' holds no date", self.render_fails())

    def test_measure_line_absent(self):
        self.rec["capabilities"]["Alpha"]["measured"][0]["line"] = "| 9 | nothing"
        self.assertIn("line '| 9 | nothing' is on 0 readiness lines", self.render_fails())

    def test_measure_line_twice(self):
        self.rec["capabilities"]["Alpha"]["measured"][0]["line"] = "| twice |"
        self.assertIn("line '| twice |' is on 2 readiness lines", self.render_fails())

    def test_measure_line_past_the_next_heading(self):
        self.rec["capabilities"]["Alpha"]["measured"][0]["line"] = "| 5 | past"
        self.assertIn("line '| 5 | past' is on 0 readiness lines", self.render_fails())

    def test_template_missing(self):
        self.rec["capabilities"]["Alpha"]["built"][0]["template"] = "gone.yaml"
        self.assertIn("template gone.yaml is not in the chart's templates", self.render_fails())

    def test_contains_absent(self):
        self.rec["capabilities"]["Alpha"]["built"][0]["contains"] = "absent text"
        self.assertIn("template t.yaml does not contain 'absent text'", self.render_fails())

    def test_every_failure_is_reported_together(self):
        self.rec["entries"]["e1"]["anchor"] = "no such anchor"
        self.rec["capabilities"]["Alpha"]["built"][0]["contains"] = "absent text"
        self.rec["capabilities"]["Gamma"] = {}
        text = self.render_fails()
        for want in ("anchor 'no such anchor'", "does not contain 'absent text'", "Gamma has no phase"):
            self.assertIn(want, text)
        self.assertEqual(len(text.strip().split("\n")), 3)

    def test_the_readiness_text_is_not_echoed(self):
        for line in ("| 9 | nothing", "| twice |", "| 5 | past"):
            self.rec = base_record()
            self.rec["capabilities"]["Alpha"]["measured"][0]["line"] = line
            self.render_fails()


class Evidence(Fixture):
    def test_an_adr_saying_measured_without_an_entry_reads_not_measured(self):
        self.rec["capabilities"]["Alpha"] = {"adrs": ["ADR-0001"]}
        t = self.render()
        self.assertEqual(self.cells(t, "Alpha")[2:4], ["accepted design", "not measured"])

    def test_a_table_line_quotes_without_its_number_and_bars(self):
        t = self.render()
        self.assertEqual(self.cells(t, "Alpha")[3], "2026-09-26, lab A, A. First section: alpha: ok")

    def test_a_decimal_first_cell_is_dropped(self):
        self.rec["capabilities"]["Alpha"]["measured"][0]["line"] = "| 2.1 | beta"
        self.assertEqual(self.cells(self.render(), "Alpha")[3], "2026-09-26, lab A, A. First section: beta: fine")

    def test_a_prose_line_runs_to_the_end_of_the_sentence(self):
        self.rec["capabilities"]["Alpha"]["measured"][0]["line"] = "* **Prose item**"
        want = "2026-09-26, lab A, A. First section: Prose item runs over two lines and then ends here."
        self.assertEqual(self.cells(self.render(), "Alpha")[3], want)

    def test_a_dashed_line_that_ends_at_once(self):
        self.rec["capabilities"]["Alpha"]["measured"][0] = {"entry": "e2", "line": "- dashed line"}
        want = "2026-10-01, lab B, B. Second section: dashed line ends at once."
        self.assertEqual(self.cells(self.render(), "Alpha")[3], want)

    def test_a_bar_in_prose_is_escaped(self):
        text = READINESS_TEXT.replace("- dashed line ends at once.", "- dashed a | b ends at once.")
        self.rec["capabilities"]["Alpha"]["measured"][0] = {"entry": "e2", "line": "dashed a"}
        self.assertIn("dashed a \\| b ends", self.render(readiness=text))

    def test_two_citations_join_with_a_semicolon(self):
        self.rec["capabilities"]["Alpha"]["measured"].append({"entry": "e2", "line": "- dashed line"})
        self.assertEqual(self.cells(self.render(), "Alpha")[3],
                         "2026-09-26, lab A, A. First section: alpha: ok; "
                         "2026-10-01, lab B, B. Second section: dashed line ends at once.")

    def test_only_the_labs_used_are_in_the_legend(self):
        self.assertIn("\nLab A is the first lab cluster.\n", self.render())
        self.assertNotIn("lab B", self.render())
        self.rec["capabilities"]["Alpha"]["measured"].append({"entry": "e2", "line": "- dashed line"})
        self.assertIn("\nLab A is the first lab cluster and lab B the second lab cluster.\n", self.render())

    def test_no_measured_entry_means_no_legend(self):
        self.rec["capabilities"]["Alpha"].pop("measured")
        self.assertNotIn("\nLab ", self.render())

    def test_the_other_cells(self):
        t = self.render()
        self.assertEqual(self.cells(t, "Alpha")[4:], ["templates/t.yaml", "ADR-0001", "-"])
        self.assertEqual(self.cells(t, "Beta")[1], "Lane one, 1: First one")
        self.assertEqual(self.cells(t, "Gamma")[1:], ["Top", "row", "not measured", "-", "-", "AE-1"])

    def test_a_done_increment_reads_done(self):
        self.rec["capabilities"]["Beta"]["increment"] = "**Done one**"
        self.assertEqual(self.cells(self.render(), "Beta")[1], "Lane one, done: Done one")

    def test_still_open_reads_as_such(self):
        self.rec["capabilities"]["Gamma"]["still_open"] = [{"adr": "ADR-0001", "says": "Still open"}]
        self.assertEqual(self.cells(self.render(), "Gamma")[5], "ADR-0001 (names it still open)")

    def test_duplicate_templates_are_listed_once(self):
        self.rec["capabilities"]["Alpha"]["built"].append({"template": "t.yaml", "contains": "foo"})
        self.assertEqual(self.cells(self.render(), "Alpha")[4], "templates/t.yaml")


class Decisions(Fixture):
    def test_index_disagreement_is_shown_and_the_file_decides_the_phase(self):
        self.rec["capabilities"]["Beta"]["adrs"] = ["ADR-0003"]
        self.put("README.md", README.replace("ADR-0003: three](ADR-0003-three.md) — **accepted.**",
                                             "ADR-0003: three](ADR-0003-three.md) — **Proposed.**"))
        t = self.render()
        self.assertEqual(self.cells(t, "Beta")[2], "accepted design")
        self.assertEqual(self.cells(t, "Beta")[5], "ADR-0003 (record: accepted; index: proposed)")

    def test_agreement_shows_nothing(self):
        self.assertEqual(self.cells(self.render(), "Beta")[5], "ADR-0002")

    def test_an_index_status_that_is_neither_shows_nothing(self):
        self.put("README.md", README.replace("— **proposed.**", "— **superseded.**"))
        self.assertEqual(self.cells(self.render(), "Beta")[5], "ADR-0002")


class Counts(Fixture):
    def test_the_counts_line_is_computed(self):
        self.assertTrue(self.render().startswith(
            "Phases: 1 measured, 0 built unmeasured, 0 accepted design, 1 proposed, 1 row.\n"))
        self.rec["capabilities"]["Alpha"].pop("measured")
        self.assertTrue(self.render().startswith(
            "Phases: 0 measured, 1 built unmeasured, 0 accepted design, 1 proposed, 1 row.\n"))

    def test_one_row_per_capability_in_model_order(self):
        names = [ln.split("|")[1].strip() for ln in self.render().split("\n")
                 if ln.startswith("| ") and not ln.startswith("| Capability")]
        self.assertEqual(names, ["Alpha", "Beta", "Gamma"])


class Quotes(Fixture):
    def test_evidence_cells_are_what_the_table_prints(self):
        self.assertEqual({k: "; ".join(v) for k, v in cp.evidence_cells(self.rec, READINESS_TEXT).items()},
                         {"Alpha": self.cells(self.render(), "Alpha")[3]})

    def test_two_citations_are_two_strings(self):
        self.rec["capabilities"]["Alpha"]["measured"].append({"entry": "e2", "line": "second section line"})
        cells = cp.evidence_cells(self.rec, READINESS_TEXT)["Alpha"]
        self.assertEqual(len(cells), 2)
        self.assertEqual("; ".join(cells), self.cells(self.render(), "Alpha")[3])

    def test_a_bad_citation_raises_without_the_text(self):
        self.rec["capabilities"]["Alpha"]["measured"][0]["line"] = "| 9 | nothing"
        with self.assertRaises(cp.CheckError) as cm:
            cp.evidence_cells(self.rec, READINESS_TEXT)
        self.assertNotIn(MARKER, cm.exception.args[0])


class Barred(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, text, name="list.txt"):
        p = self.tmp / name
        p.write_text(text, encoding="utf-8", newline="\n")
        return p

    def test_comments_and_blank_lines_are_skipped(self):
        got = cp.load_barred([self.write("# note\n\n  \nzebra\n")])
        self.assertEqual([p.pattern for p in got], ["zebra"])

    def test_the_rsplit_form_drops_the_tail(self):
        got = cp.load_barred([self.write("a|b|reason\nplain\n")])
        self.assertEqual([p.pattern for p in got], ["a|b", "plain"])

    def test_two_files_add_up(self):
        got = cp.load_barred([self.write("one\n", "a.txt"), self.write("two\n", "b.txt")])
        self.assertEqual(len(got), 2)

    def test_a_bad_pattern_names_only_the_file_and_line(self):
        p = self.write("fine\n(unclosed-ZZPAT\n", "mylist.txt")
        with self.assertRaises(cp.CheckError) as cm:
            cp.load_barred([p])
        msg = cm.exception.args[0]
        self.assertEqual(msg, "barred list mylist.txt line 2 does not compile")
        self.assertNotIn("ZZPAT", msg)
        self.assertIsNone(cm.exception.__cause__)

    def test_an_empty_list_raises(self):
        for text in ("", "# only a comment\n\n"):
            with self.assertRaises(cp.CheckError):
                cp.load_barred([self.write(text)])

    def test_an_unreadable_list_raises(self):
        with self.assertRaises(cp.CheckError):
            cp.load_barred([self.tmp / "nowhere.txt"])

    def test_hit_and_miss(self):
        pats = cp.load_barred([self.write("zebra\n")])
        self.assertEqual(cp.scan_barred({"A": ["a zebra here"], "B": ["nothing"]}, pats),
                         ["quotes: A: carries 1 barred value(s)"])
        self.assertEqual(cp.scan_barred({"B": ["nothing"]}, pats), [])

    def test_case_insensitive(self):
        pats = cp.load_barred([self.write("zebra\n")])
        self.assertEqual(len(cp.scan_barred({"A": ["ZeBrA"]}, pats)), 1)

    def test_count_is_over_strings_and_patterns(self):
        pats = cp.load_barred([self.write("zebra\nlion\n")])
        got = cp.scan_barred({"A": ["zebra zebra", "lion and zebra"]}, pats)
        self.assertEqual(got, ["quotes: A: carries 4 barred value(s)"])

    def test_the_output_has_neither_pattern_nor_match(self):
        pats = cp.load_barred([self.write("zeb[a-z]+|why\n")])
        out = "\n".join(cp.scan_barred({"A": ["see zebra now"]}, pats))
        self.assertNotIn("zeb", out)
        self.assertNotIn("why", out)


WHY = None if READINESS.is_file() and (CHART / "templates").is_dir() else \
    f"the chart or its readiness doc is not beside this repository ({CHART})"
if WHY:
    print(f"SKIP real-record tests: {WHY}", file=sys.stderr)


@unittest.skipIf(WHY, WHY or "")
class RealSources(unittest.TestCase):
    """The real record against the real sources. Nothing from the readiness doc is printed."""

    def setUp(self):
        self.record = cp.load_record(ARCH / "capability-record.yaml")
        sysml = (ARCH / "model" / "openddil.sysml").read_text(encoding="utf-8")
        self.caps = cp.model_capabilities(sysml)
        self.readiness = READINESS.read_text(encoding="utf-8")
        self.table = cp.render_table(self.record, self.caps, REPO / "decisions", CHART / "templates", self.readiness)

    def test_evidence_cells_are_what_the_table_prints(self):
        printed = {}
        for ln in self.table.split("\n"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", ln.strip().strip("|"))]
            if ln.startswith("| ") and len(cells) == 7 and cells[0] != "Capability" and cells[3] != "not measured":
                printed[cells[0]] = cells[3]
        got = cp.evidence_cells(self.record, self.readiness)
        self.assertEqual({k: "; ".join(v) for k, v in got.items()}, printed)
        self.assertTrue(printed)

    def test_counts(self):
        self.assertTrue(self.table.startswith(
            "Phases: 7 measured, 9 built unmeasured, 7 accepted design, 5 proposed, 2 row.\n"))

    def test_no_uncited_readiness_line_is_quoted(self):
        lines = self.readiness.replace("\r\n", "\n").split("\n")
        entries, fails = cp.resolve_entries(self.record, lines)
        self.assertEqual(fails, [])
        cited = set()
        for cap in self.record["capabilities"].values():
            for m in (cap or {}).get("measured") or []:
                at = entries[m["entry"]][0]
                for hit in cp.measured_line(lines, at, m["line"]):
                    cited.update(range(hit, hit + 6))
        leaked = [i for i, ln in enumerate(lines)
                  if i not in cited and len(ln.strip()) >= 20 and ln.strip().replace("**", "") in self.table]
        self.assertEqual(leaked, [], f"{len(leaked)} uncited readiness lines are quoted (line numbers only shown)")


if __name__ == "__main__":
    unittest.main()
