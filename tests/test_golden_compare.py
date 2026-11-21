"""scripts/golden_compare.py: identical, allowed, and the three ways to fail."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "scripts" / "golden_compare.py"


P1 = "1" * 40
P2 = "2" * 40


def page(pid, body):
    return f'<section id="{pid}"><p>{body}</p></section>\n'


def export(front="a", other="b", date="d1"):
    return (f"<html><body>{date}\n" + page("front", front) + page("view-A", other)
            + "</body></html>\n").encode()


class Compare(unittest.TestCase):
    def run_tool(self, old, new, allow, pins=None):
        d = Path(tempfile.mkdtemp())
        (d / "old.html").write_bytes(old)
        (d / "new.html").write_bytes(new)
        (d / "allow.txt").write_text(allow, encoding="utf-8")
        p = subprocess.run([sys.executable, str(TOOL), str(d / "old.html"), str(d / "new.html"),
                            str(d / "allow.txt"), "--out", str(d / "out")] + (["--pins", *pins] if pins else []),
                           capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr

    def test_no_allowance_needs_no_pins_line(self):
        rc, out, err = self.run_tool(export(), export(), "", pins=(P1, P2))
        self.assertEqual(rc, 0, err)

    def test_allowances_with_the_matching_pins_line_pass(self):
        rc, out, err = self.run_tool(export(other="b"), export(other="c"),
                                     f"# pins: {P1} {P2}\nview-A: reworded on purpose\n", pins=(P1, P2))
        self.assertEqual(rc, 0, err)
        self.assertIn("allowed:   view-A", out)

    def test_allowances_without_a_pins_line_fail(self):
        rc, out, err = self.run_tool(export(other="b"), export(other="c"), "view-A: reworded\n", pins=(P1, P2))
        self.assertEqual(rc, 1)
        self.assertIn(f"golden_compare: the allowances are for no pins line, this comparison is {P1} {P2}", err)

    def test_allowances_for_another_pair_fail(self):
        rc, out, err = self.run_tool(export(other="b"), export(other="c"),
                                     f"# pins: {P1} {P1}\nview-A: reworded\n", pins=(P1, P2))
        self.assertEqual(rc, 1)
        self.assertIn(f"golden_compare: the allowances are for {P1} {P1}, this comparison is {P1} {P2}", err)

    def test_identical_needs_no_allowance(self):
        rc, out, err = self.run_tool(export(), export(), "")
        self.assertEqual(rc, 0, err)
        self.assertIn("identical 4", out)

    def test_a_named_page_is_allowed(self):
        rc, out, err = self.run_tool(export(other="b"), export(other="c"), "view-A: reworded on purpose\n")
        self.assertEqual(rc, 0, err)
        self.assertIn("allowed:   view-A", out)

    def test_an_unnamed_difference_fails(self):
        rc, out, err = self.run_tool(export(other="b"), export(other="c"), "")
        self.assertEqual(rc, 1)
        self.assertIn("view-A: differs and is not in the allowlist", err)

    def test_a_stale_allowance_fails(self):
        rc, out, err = self.run_tool(export(), export(), "view-A: no longer differs\n")
        self.assertEqual(rc, 1)
        self.assertIn("matches nothing: view-A", err)

    def test_an_element_is_removed_and_the_rest_must_match(self):
        old = export(front='<p class="relabel" data-relabel>x</p>')
        new = export(front='<p class="relabel" data-relabel>y</p>')
        rc, out, err = self.run_tool(old, new, "front data-relabel: the sentence names the export\n")
        self.assertEqual(rc, 0, err)
        rc, out, err = self.run_tool(old, export(front='<p class="relabel" data-relabel>y</p> more'),
                                     "front data-relabel: the sentence names the export\n")
        self.assertEqual(rc, 1)
        self.assertIn("differs outside data-relabel", err)

    def test_a_difference_outside_the_pages_fails(self):
        rc, out, err = self.run_tool(export(date="d1"), export(date="d2"), "")
        self.assertEqual(rc, 1)
        self.assertIn("prelude: differs", err)


if __name__ == "__main__":
    unittest.main()
