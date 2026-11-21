#!/usr/bin/env python3
"""Print the arch-kit commit that a workflow file pins.

usage: kit_pin.py FILE

Every full sha that follows `edgy-solutions/arch-kit@` is collected, and so is every `ref:` sha in a step
whose `repository:` is `edgy-solutions/arch-kit`. When all of them are equal, the sha is printed and the
exit code is 0. When they differ, or there are none, the exit code is 1 and the shas found are named.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SHA = r"[0-9a-f]{40}"
USES = re.compile(r"edgy-solutions/arch-kit@(" + SHA + r")(?![0-9a-zA-Z])")
REPO = re.compile(r"^(\s*)(?:-\s+)?repository:\s*['\"]?edgy-solutions/arch-kit['\"]?\s*(?:#.*)?$")
REF = re.compile(r"^(\s*)(?:-\s+)?ref:\s*['\"]?(" + SHA + r")['\"]?\s*(?:#.*)?$")


def indent(line: str) -> int:
    """The column of a key, counting a `- ` list marker as part of the indent."""
    stripped = line.lstrip()
    n = len(line) - len(stripped)
    if stripped.startswith("- "):
        n += 2 + len(stripped[2:]) - len(stripped[2:].lstrip())
    return n


def pins(text: str) -> list[str]:
    found = USES.findall(text)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not REPO.match(line):
            continue
        col = indent(line)
        # The keys of the same mapping: neighbouring lines at the same column, until a shallower line.
        for back, rng in ((True, range(i - 1, -1, -1)), (False, range(i + 1, len(lines)))):
            for j in rng:
                other = lines[j]
                if not other.strip() or other.lstrip().startswith("#"):
                    continue
                c = indent(other)
                dash = c == col and other.lstrip().startswith("- ")
                if dash and not back:
                    break  # the next item's first key
                m = REF.match(other) if c == col else None
                if m:
                    found.append(m.group(2))
                if c < col or dash:
                    break
    return found


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: kit_pin.py FILE", file=sys.stderr)
        return 2
    found = pins(Path(argv[1]).read_text(encoding="utf-8"))
    distinct = sorted(set(found))
    if len(distinct) == 1:
        print(distinct[0])
        return 0
    if not distinct:
        print(f"kit_pin: no arch-kit pin in {argv[1]}", file=sys.stderr)
    else:
        print(f"kit_pin: the arch-kit pins in {argv[1]} differ: {', '.join(distinct)}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
