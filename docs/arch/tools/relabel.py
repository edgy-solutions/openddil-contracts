#!/usr/bin/env python3
"""relabel.py - replace names in the decision records at export, leaving the sources alone.

A list file holds one rule per line: PATTERN<TAB>REPLACEMENT. Blank lines and lines
starting `#` are skipped. A pattern is a regular expression, compiled case-insensitively.
The list is supplied by the deployment; nothing in the repository names a value to replace.

apply() runs the rules in file order. Per match:
    a match of two or more letters, all uppercase, is replaced by the uppercased replacement;
    a match at the start of a sentence gets a replacement with a capital first letter;
    a replacement that starts with `the ` drops it when the word before the match is an
    article or a determiner (the, a, an, first, this, that, each, every).
A message about a bad line names the file and the line number, never the line.
Stdlib only.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from data_exchange import InputError

DETERMINERS = {"the", "a", "an", "first", "this", "that", "each", "every"}
LEADING = re.compile(r"(?:\s|[#\-*>|`]|\d+\.(?=\s))*")
AFTER_STOP = re.compile(r"[.!?:]\s+(?:\*\*|`)?$")
WORD_BEFORE = re.compile(r"(\w+) +$")


class Rule(NamedTuple):
    pattern: re.Pattern
    replacement: str
    file: str
    line: int


def load(paths) -> list[Rule]:
    rules: list[Rule] = []
    for path in paths:
        name = Path(path).name
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError:
            raise InputError(f"relabel list {name} cannot be read") from None
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            pattern, tab, replacement = line.partition("\t")
            if not tab:
                raise InputError(f"relabel list {name} line {n} has no tab")
            try:
                rules.append(Rule(re.compile(pattern, re.IGNORECASE), replacement, name, n))
            except re.error:
                raise InputError(f"relabel list {name} line {n} does not compile") from None
    return rules


def sentence_start(prefix: str) -> bool:
    """The text before a match on its line: only markers, or a sentence stop."""
    return bool(LEADING.fullmatch(prefix) or AFTER_STOP.search(prefix))


def replacement_for(m: re.Match, replacement: str) -> str:
    text = m.string
    prefix = text[text.rfind("\n", 0, m.start()) + 1:m.start()]
    word = WORD_BEFORE.search(prefix)
    if replacement[:4].lower() == "the " and word and word.group(1).lower() in DETERMINERS:
        replacement = replacement[4:]
    letters = [c for c in m.group(0) if c.isalpha()]
    if len(letters) >= 2 and all(c.isupper() for c in letters):
        return replacement.upper()
    if replacement and sentence_start(prefix):
        return replacement[0].upper() + replacement[1:]
    return replacement


def apply(text: str, rules) -> tuple[str, int]:
    total = 0
    for rule in rules:
        text, n = rule.pattern.subn(lambda m, r=rule.replacement: replacement_for(m, r), text)
        total += n
    return text, total


def survivors(text: str, rules) -> list[tuple[int, int, int]]:
    """(rule index, line number, matches) for every line of text a pattern still matches."""
    out = []
    for i, rule in enumerate(rules):
        for n, line in enumerate(text.split("\n"), 1):
            hits = len(rule.pattern.findall(line))
            if hits:
                out.append((i, n, hits))
    return out
