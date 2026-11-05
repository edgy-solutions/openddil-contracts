#!/usr/bin/env python3
"""Tests for marks.py: what a status line fixes, and the fill that reads it."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import marks  # noqa: E402
from data_exchange import InputError  # noqa: E402

TOKEN = marks.STATUS_TOKEN


class FixedEvidence(unittest.TestCase):
    def test_design_only(self):
        self.assertEqual(marks.fixed_evidence("Accepted. Design only. Nothing here is built."), "Design only")

    def test_design_only_is_read_before_nothing_built(self):
        self.assertEqual(marks.fixed_evidence("Nothing built. Design only."), "Design only")

    def test_nothing_built(self):
        self.assertEqual(marks.fixed_evidence("Accepted. **Positioning. Nothing built.**"), "Nothing built")

    def test_plan_only(self):
        self.assertEqual(marks.fixed_evidence("PLAN ONLY. Go-signal reserved."), "Nothing built")

    def test_anything_else_fixes_nothing(self):
        for s in ("Accepted. Built and measured.", "Proposed.", "", None):
            self.assertIsNone(marks.fixed_evidence(s), s)


class Fill(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dec = self.tmp / "decisions"
        self.views = self.tmp / "docs" / "arch" / "views"
        self.dec.mkdir()
        self.views.mkdir(parents=True)
        self.record("DESIGN-x.md", "# X\n\n**Status: PLAN ONLY. Nothing built.**\n")
        self.record("ADR-0001-y.md", "# Y\n\n## Status\n\nAccepted. Design only.\n")
        self.record("ADR-0002-z.md", "# Z\n\n## Status\n\nAccepted. Built.\n")

    def record(self, name, text):
        (self.dec / name).write_text(text, encoding="utf-8")

    def body(self, *rows):
        head = "# V\n\n## Sources\n\n" + marks.SOURCES_HEADER + "\n|---|---|---|---|\n"
        return head + "".join(r + "\n" for r in rows)

    def fill(self, body):
        return marks.fill(body, self.views, self.dec, "V")

    def link(self, name):
        return f"[{name}](../../../decisions/{name})"

    def test_token_takes_the_record_value(self):
        out = self.fill(self.body(f"| a | {self.link('DESIGN-x.md')} | Design note | {TOKEN} |"))
        self.assertIn(f"| a | {self.link('DESIGN-x.md')} | Design note | Nothing built |", out)
        self.assertNotIn(TOKEN, out)

    def test_row_spacing_is_kept(self):
        row = f"|  a |  {self.link('ADR-0001-y.md')}  | Accepted |  {TOKEN}  |"
        out = self.fill(self.body(row))
        self.assertIn(row.replace(TOKEN, "Design only"), out)

    def test_two_records_that_agree(self):
        self.record("ADR-0003-w.md", "# W\n\n## Status\n\nAccepted. Design only.\n")
        out = self.fill(self.body(f"| a | {self.link('ADR-0001-y.md')}, {self.link('ADR-0003-w.md')} | Accepted | {TOKEN} |"))
        self.assertIn("| Accepted | Design only |", out)

    def test_two_records_that_disagree(self):
        with self.assertRaisesRegex(InputError, "disagree"):
            self.fill(self.body(f"| a | {self.link('ADR-0001-y.md')}, {self.link('DESIGN-x.md')} | Accepted | {TOKEN} |"))

    def test_one_record_fixes_and_one_does_not(self):
        out = self.fill(self.body(f"| a | {self.link('ADR-0002-z.md')}, {self.link('DESIGN-x.md')} | Accepted | {TOKEN} |"))
        self.assertIn("| Accepted | Nothing built |", out)

    def test_token_on_a_record_that_fixes_nothing(self):
        with self.assertRaisesRegex(InputError, "fixes the evidence"):
            self.fill(self.body(f"| a | {self.link('ADR-0002-z.md')} | Accepted | {TOKEN} |"))

    def test_token_with_no_record(self):
        with self.assertRaisesRegex(InputError, "cites no record"):
            self.fill(self.body(f"| a | [chart](../chart.yaml) | Declared | {TOKEN} |"))

    def test_missing_record(self):
        with self.assertRaisesRegex(InputError, "does not exist"):
            self.fill(self.body(f"| a | {self.link('ADR-0009-gone.md')} | Accepted | {TOKEN} |"))

    def test_outside_sources_the_token_is_text(self):
        body = "# V\n\n## Notes\n\n| a | b | c | " + TOKEN + " |\n\n```\n| a | b | c | " + TOKEN + " |\n```\n"
        self.assertEqual(self.fill(body), body)

    def test_a_copied_word_is_left_for_check_views(self):
        body = self.body(f"| a | {self.link('DESIGN-x.md')} | Design note | Not stated |")
        self.assertEqual(self.fill(body), body)


if __name__ == "__main__":
    unittest.main()
