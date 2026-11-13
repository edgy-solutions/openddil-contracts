"""Tests for adr_sections.py.

Run from the worktree root:
    python -m unittest discover -s docs/arch/tools -p "test_*.py"
"""
import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adr_sections  # noqa: E402

DECISIONS = HERE.parent.parent.parent / "decisions"


def real(adr: str) -> str:
    return sorted(DECISIONS.glob(f"{adr}-*.md"))[0].read_text(encoding="utf-8")


class RealRecords(unittest.TestCase):
    def test_a_number_resolves_to_its_heading(self):
        h = adr_sections.resolve(real("ADR-0045"), "6")
        self.assertTrue(h.text.startswith("6. Trust between tiers"), h.text)
        self.assertEqual(h.number, "6")

    def test_a_number_with_a_letter(self):
        h = adr_sections.resolve(real("ADR-0055"), "1a")
        self.assertEqual(h.number, "1a")

    def test_a_slug_names_an_unnumbered_heading(self):
        h = adr_sections.resolve(real("ADR-0010"), "decision")
        self.assertIsNone(h.number)
        self.assertEqual(h.slug, "decision")

    def test_a_missing_section_raises(self):
        with self.assertRaisesRegex(LookupError, "no section §99"):
            adr_sections.resolve(real("ADR-0045"), "99")

    def test_the_cli_prints_one_line_per_heading(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(adr_sections.main(["ADR-0045"]), 0)
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), len(adr_sections.headings(real("ADR-0045"))))
        self.assertTrue(all(len(ln.split("\t")) == 4 for ln in lines))

    def test_the_cli_exits_2_for_a_record_it_cannot_find(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(adr_sections.main(["ADR-9999"]), 2)


class Parsing(unittest.TestCase):
    def test_an_ambiguous_number_raises(self):
        with self.assertRaisesRegex(LookupError, "ambiguous"):
            adr_sections.resolve("# T\n\n## 2. One\n\n## 2. Two\n", "2")

    def test_an_em_dash_keeps_the_double_hyphen(self):
        h = adr_sections.headings("## Alpha — beta\n")[0]
        self.assertEqual(h.slug, "alpha--beta")

    def test_duplicate_headings_get_a_suffix(self):
        got = [h.slug for h in adr_sections.headings("## Same\n\n### Same\n\n## Same\n")]
        self.assertEqual(got, ["same", "same-1", "same-2"])

    def test_a_heading_inside_a_fence_is_ignored(self):
        text = "## Real\n\n```sh\n## not a heading\n```\n\n~~~\n### nor this\n~~~\n\n## After\n"
        self.assertEqual([h.slug for h in adr_sections.headings(text)], ["real", "after"])

    def test_levels_two_to_four_only(self):
        text = "# Title\n\n## Two\n\n### Three\n\n#### Four\n\n##### Five\n"
        self.assertEqual([h.level for h in adr_sections.headings(text)], [2, 3, 4])

    def test_a_dotted_number_and_its_slug(self):
        h = adr_sections.headings("### 2.1 Trust model\n")[0]
        self.assertEqual((h.number, h.slug), ("2.1", "21-trust-model"))

    def test_a_bare_id_is_not_a_citation(self):
        with self.assertRaises(ValueError):
            adr_sections.parse_citation("ADR-0045")
        self.assertEqual(adr_sections.parse_citation("ADR-0045 §6"), ("ADR-0045", "6"))
        self.assertEqual(adr_sections.parse_citation("ADR-0045 §2.1"), ("ADR-0045", "2.1"))

    def test_the_anchor_is_the_id_and_the_slug(self):
        h = adr_sections.headings("## 6. Trust\n")[0]
        self.assertEqual(adr_sections.anchor_id("ADR-0045", h), "adr-0045-6-trust")


if __name__ == "__main__":
    unittest.main()
