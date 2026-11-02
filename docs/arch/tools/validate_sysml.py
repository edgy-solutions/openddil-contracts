#!/usr/bin/env python3
"""Validate the SysML v2 model with the reference parser, and prove the parser can say no.

A run feeds the parser three inputs: the model, the model with a syntax fault, and
the model with an unresolved reference. The parser exits 0 for all three, so the
verdict comes from its output. The model has to parse clean, and both faulted
copies have to be refused. A parser that accepts everything fails this run.

Usage:
    python validate_sysml.py --jar <kernel-all.jar> --library <sysml.library> [--java java]
    python validate_sysml.py --model <path> ...

Exit 0 when all three cases hold, 1 when one does not, 2 when a case could not run.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

MODEL = Path(__file__).resolve().parents[1] / "model" / "openddil.sysml"
MAIN_CLASS = "org.omg.sysml.interactive.SysMLInteractive"
TIMEOUT_S = 200
OUTPUT_CAP = 2_000_000
NOISE = re.compile(r"^(Reading |log4j|SysML v2 Pilot|\s+at )")

SYNTAX_OLD = "part def EgressGate;"
SYNTAX_NEW = "part def EgressGate"
LINK_OLD = "occurrence def DataAcquisition :> ConditionMonitoring;"
LINK_NEW = "occurrence def DataAcquisition :> NoSuchThing;"


class CaseError(Exception):
    """A case could not run, which is not the same as a case failing."""


def to_stdin(model: str) -> str:
    """The parser reads one statement per line, so the model goes on one line.
    `%exit` ends it. Without that it loops at end of input and writes without limit."""
    lines = [ln.strip() for ln in model.splitlines()]
    kept = [ln for ln in lines if ln and not ln.startswith("//")]
    return " ".join(kept) + "\n%exit\n"


def faulted(model: str, old: str, new: str) -> str:
    if old not in model:
        raise CaseError(f"the fault needs {old!r} in the model, and it is not there")
    return model.replace(old, new, 1)


def cases(model: str) -> list[tuple[str, str]]:
    return [("good", model),
            ("syntax", faulted(model, SYNTAX_OLD, SYNTAX_NEW)),
            ("link", faulted(model, LINK_OLD, LINK_NEW))]


def filter_output(raw: str) -> str:
    return "\n".join(ln for ln in raw.splitlines() if not NOISE.match(ln))


def judge(case: str, output: str) -> str | None:
    """None when the case holds, else what was wrong."""
    errors = [ln for ln in output.splitlines() if "ERROR" in ln]
    if case == "good":
        if errors:
            return f"the model did not parse clean: {errors[0][:200]}"
        if "Package OpenDDIL" not in output:
            return "the parser did not report Package OpenDDIL"
        return None
    if not errors:
        return "the fault was accepted, so this parser run proves nothing"
    if case == "link" and not any("NoSuchThing" in ln for ln in errors):
        return f"refused, but not for the bad reference: {errors[0][:200]}"
    return None


def run_parser(java: str, jar: str, library: str, stdin: str) -> str:
    """The parser's output, capped. Runaway output is a failure to run, not a verdict."""
    cmd = [java, "-cp", jar, MAIN_CLASS, library]
    try:
        proc = subprocess.run(cmd, input=stdin.encode("utf-8"), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise CaseError(f"no result within {TIMEOUT_S} s") from exc
    except OSError as exc:
        raise CaseError(f"could not start {java}: {exc}") from exc
    if len(proc.stdout) > OUTPUT_CAP:
        raise CaseError(f"more than {OUTPUT_CAP} bytes of output")
    return proc.stdout.decode("utf-8", errors="replace")


def validate(model: str, runner: Callable[[str], str]) -> int:
    try:
        planned = cases(model)
    except CaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    misses = 0
    for name, text in planned:
        try:
            output = filter_output(runner(to_stdin(text)))
        except CaseError as exc:
            print(f"error: case {name}: {exc}", file=sys.stderr)
            return 2
        problem = judge(name, output)
        if problem:
            misses += 1
            print(f"FAIL {name}: {problem}")
        else:
            print(f"ok {name}")
    return 1 if misses else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--jar", required=True)
    ap.add_argument("--library", required=True)
    ap.add_argument("--java", default="java")
    ap.add_argument("--model", default=str(MODEL))
    a = ap.parse_args(argv)
    try:
        model = Path(a.model).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return validate(model, lambda stdin: run_parser(a.java, a.jar, a.library, stdin))


if __name__ == "__main__":
    sys.exit(main())
