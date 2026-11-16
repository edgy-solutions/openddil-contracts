"""Tests for relabel.py. All values are made up.

Run from the worktree root:
    python -m unittest discover -s docs/arch/tools -p "test_*.py"
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import relabel  # noqa: E402
from data_exchange import InputError  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def rules(self, text, name="list.txt"):
        p = self.tmp / name
        p.write_text(text, encoding="utf-8", newline="\n")
        return relabel.load([p])

    def run_one(self, text, replacement="the lab", pattern=r"zebra-host-9"):
        out, n = relabel.apply(text, self.rules(f"{pattern}\t{replacement}\n"))
        return out, n


class Load(Base):
    def test_comments_and_blanks_are_skipped(self):
        r = self.rules("# a comment\n\nzebra-host-9\tthe lab\n")
        self.assertEqual(len(r), 1)
        self.assertEqual((r[0].file, r[0].line, r[0].replacement), ("list.txt", 3, "the lab"))

    def test_pattern_is_case_insensitive(self):
        self.assertEqual(self.run_one("see ZEBRA-host-9 here")[1], 1)

    def test_a_line_without_a_tab_names_the_line_and_not_its_content(self):
        with self.assertRaises(InputError) as cm:
            self.rules("# c\nzebra-host-9 the lab\n", name="mine.txt")
        msg = str(cm.exception)
        self.assertIn("mine.txt", msg)
        self.assertIn("line 2", msg)
        self.assertNotIn("zebra", msg)

    def test_a_pattern_that_does_not_compile_names_the_line_and_not_its_content(self):
        with self.assertRaises(InputError) as cm:
            self.rules("zebra-(host\tthe lab\n", name="mine.txt")
        msg = str(cm.exception)
        self.assertIn("line 1", msg)
        self.assertNotIn("zebra", msg)

    def test_an_unreadable_file(self):
        with self.assertRaises(InputError):
            relabel.load([self.tmp / "missing.txt"])


class Apply(Base):
    def test_substitution_and_count(self):
        out, n = self.run_one("one zebra-host-9 and two zebra-host-9 end")
        self.assertEqual((out, n), ("one the lab and two the lab end", 2))

    def test_rules_apply_in_file_order(self):
        r = self.rules("alpha\tbeta\nbeta\tgamma\n")
        self.assertEqual(relabel.apply("x alpha", r), ("x gamma", 2))

    def test_no_match_counts_zero(self):
        self.assertEqual(self.run_one("nothing here"), ("nothing here", 0))

    def test_all_uppercase_match_uppercases_the_replacement(self):
        self.assertEqual(self.run_one("on ZEBRA-HOST-9 link")[0], "on THE LAB link")
        self.assertEqual(self.run_one("on the ZEBRA-HOST-9 link")[0], "on the LAB link")

    def test_one_letter_match_is_not_uppercase(self):
        self.assertEqual(self.run_one("x A y", replacement="the lab", pattern="A")[0], "x the lab y")

    def test_sentence_start_capitalises(self):
        for text, want in [("zebra-host-9 is down", "The lab is down"),
                           ("# zebra-host-9 notes", "# The lab notes"),
                           ("- zebra-host-9 item", "- The lab item"),
                           ("4. zebra-host-9 item", "4. The lab item"),
                           ("> **zebra-host-9** item", "> **The lab** item"),
                           ("| `zebra-host-9` | x |", "| `The lab` | x |"),
                           ("It ended. zebra-host-9 began.", "It ended. The lab began."),
                           ("Note: **zebra-host-9** began", "Note: **The lab** began"),
                           ("two\nzebra-host-9 starts a line", "two\nThe lab starts a line")]:
            self.assertEqual(self.run_one(text)[0], want, text)

    def test_mid_sentence_is_left_alone(self):
        self.assertEqual(self.run_one("it ran on zebra-host-9 today")[0], "it ran on the lab today")

    def test_article_rule_drops_the(self):
        for word in ("the", "a", "an", "first", "this", "that", "each", "every", "The", "EACH"):
            self.assertEqual(self.run_one(f"on {word} zebra-host-9 now")[0], f"on {word} lab now", word)
        self.assertEqual(self.run_one("on the zebra-host-9 now", replacement="The Lab")[0], "on the Lab now")

    def test_article_rule_needs_a_determiner_on_the_same_line(self):
        self.assertEqual(self.run_one("see the\nzebra-host-9 now")[0], "see the\nThe lab now")
        self.assertEqual(self.run_one("on of zebra-host-9 now")[0], "on of the lab now")

    def test_article_rule_applies_only_to_a_the_replacement(self):
        self.assertEqual(self.run_one("on the zebra-host-9 now", replacement="lab")[0], "on the lab now")

    def test_survivors(self):
        r = self.rules("zebra-host-9\tthe lab\nPat Example\tthe owner\n")
        got = relabel.survivors("a Zebra-host-9 b zebra-host-9\nnone\nPAT EXAMPLE", r)
        self.assertEqual(got, [(0, 1, 2), (1, 3, 1)])
        self.assertEqual(relabel.survivors(relabel.apply("a zebra-host-9", r)[0], r), [])


if __name__ == "__main__":
    unittest.main()
