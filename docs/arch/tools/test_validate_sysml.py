"""Tests for validate_sysml.py, with the parser replaced by its recorded answers.

The recorded lines are what the parser printed for the model on 2026-11-02. The
parser itself runs in the sysml-model workflow.
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import validate_sysml as v  # noqa: E402

GOOD = "1> Package OpenDDIL (a1b2)\n"
SYNTAX = "ERROR:no viable alternative at input 'part' (1.sysml line : 1 column : 3477)\n"
LINK = "ERROR:Couldn't resolve reference to Classifier 'NoSuchThing'. (1.sysml line : 1 column : 291)\n"
MODEL = f"package OpenDDIL {{\n  // a comment\n  {v.SYNTAX_OLD}\n  {v.LINK_OLD}\n}}\n"


def answers(good=GOOD, syntax=SYNTAX, link=LINK):
    """A runner that answers by what the stdin it was given contains."""
    seen = []

    def runner(stdin):
        seen.append(stdin)
        if "NoSuchThing" in stdin:
            return link
        if v.SYNTAX_OLD not in stdin:
            return syntax
        return good
    runner.seen = seen
    return runner


def run(model=MODEL, runner=None):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = v.validate(model, runner or answers())
    return rc, out.getvalue(), err.getvalue()


class Stdin(unittest.TestCase):
    def test_one_line_then_exit(self):
        text = v.to_stdin(MODEL)
        self.assertTrue(text.endswith("\n%exit\n"))
        self.assertEqual(len(text.splitlines()), 2)
        self.assertNotIn("a comment", text)

    def test_noise_is_dropped(self):
        self.assertEqual(v.filter_output("log4j: x\nReading y\n1> Package OpenDDIL\n   at z"), "1> Package OpenDDIL")


class Verdict(unittest.TestCase):
    def test_recorded_answers_pass(self):
        rc, out, _ = run()
        self.assertEqual(rc, 0, out)
        self.assertEqual(out.split(), ["ok", "good", "ok", "syntax", "ok", "link"])

    def test_three_inputs_differ(self):
        runner = answers()
        run(runner=runner)
        self.assertEqual(len(set(runner.seen)), 3)

    def test_model_with_an_error_fails(self):
        rc, out, _ = run(runner=answers(good=GOOD + SYNTAX))
        self.assertEqual(rc, 1)
        self.assertIn("FAIL good", out)

    def test_silent_parser_fails(self):
        rc, out, _ = run(runner=answers(good=""))
        self.assertEqual(rc, 1)
        self.assertIn("did not report Package OpenDDIL", out)

    def test_parser_that_accepts_a_syntax_fault_fails(self):
        rc, out, _ = run(runner=answers(syntax=GOOD))
        self.assertEqual(rc, 1)
        self.assertIn("FAIL syntax", out)

    def test_parser_that_accepts_a_bad_reference_fails(self):
        rc, out, _ = run(runner=answers(link=GOOD))
        self.assertEqual(rc, 1)
        self.assertIn("FAIL link", out)

    def test_refusal_for_another_reason_fails_the_link_case(self):
        rc, out, _ = run(runner=answers(link=SYNTAX))
        self.assertEqual(rc, 1)
        self.assertIn("not for the bad reference", out)


class WhatTheParserSaid(unittest.TestCase):
    def test_a_failed_case_shows_the_output(self):
        said = "Error: could not start\n"
        _, out, _ = run(runner=answers(good=said))
        self.assertIn(said.strip(), out)

    def test_a_passing_case_shows_nothing_more(self):
        _, out, _ = run()
        self.assertNotIn("Package OpenDDIL", out)

    def test_shown_output_is_bounded(self):
        said = "".join(f"{'x' * 300}{i}\n" for i in range(50))
        _, out, _ = run(runner=answers(good=said))
        shown = [ln for ln in out.splitlines() if ln.startswith("  ")]
        self.assertEqual(len(shown), v.SHOWN_LINES)
        self.assertLessEqual(max(map(len, shown)), v.SHOWN_WIDTH + 2)

    def test_parser_that_never_read_the_model_is_not_called_accepting(self):
        said = "Error: could not start\n"
        _, out, _ = run(runner=lambda _stdin: said)
        self.assertIn("did not read the model", out)
        self.assertNotIn("the fault was accepted", out)


class CouldNotRun(unittest.TestCase):
    def test_model_without_the_fault_site_is_exit_2(self):
        rc, _, err = run(model="package OpenDDIL {}\n")
        self.assertEqual(rc, 2)
        self.assertIn("the fault needs", err)

    def test_runner_failure_is_exit_2(self):
        def broken(_stdin):
            raise v.CaseError("no result within 200 s")
        rc, _, err = run(runner=broken)
        self.assertEqual(rc, 2)
        self.assertIn("case good", err)

    def test_real_model_still_has_both_fault_sites(self):
        self.assertEqual(len(v.cases(v.MODEL.read_text(encoding="utf-8"))), 3)


if __name__ == "__main__":
    unittest.main()
