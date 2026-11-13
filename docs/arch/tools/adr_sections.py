#!/usr/bin/env python3
"""adr_sections.py - the sections of a decision record, and the citations that name them.

A citation is `ADR-NNNN §LABEL`. LABEL is the number a heading starts with
(`6`, `1a`, `2.1`) or, for a heading with no number, its GitHub slug
(`decision`). A label must match exactly one heading of the record.

    py -3 docs/arch/tools/adr_sections.py ADR-0045

prints one line per heading: number-or-dash, slug, level, text, separated by
tabs. It exits 2 unless it finds exactly one decisions/ADR-0045-*.md.

Stdlib only.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

CITATION_RE = re.compile(r"^(ADR-\d{4}) §([0-9A-Za-z](?:[\w-]|\.(?=\w))*)$")
CITATION_IN_TEXT_RE = re.compile(r"(?<![\w-])(ADR-\d{4}) §([0-9A-Za-z](?:[\w-]|\.(?=\w))*)")
HEADING_RE = re.compile(r"^ {0,3}(#{2,4})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
NUMBER_RE = re.compile(r"^(\d+[a-z]?(?:\.\d+)*)(?=[.\s])")
DECISIONS = Path(__file__).resolve().parent.parent.parent.parent / "decisions"


@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    number: str | None
    slug: str


def parse_citation(s: str) -> tuple[str, str]:
    """(adr id, label) of `ADR-NNNN §LABEL`; ValueError on anything else, a bare id included."""
    m = CITATION_RE.match(str(s).strip())
    if not m:
        raise ValueError(f"{str(s)!r} is not a citation of the form ADR-NNNN §LABEL")
    return m.group(1), m.group(2)


def base_slug(text: str) -> str:
    kept = "".join(c for c in text.lower() if c.isalnum() or c in " -_")
    return kept.replace(" ", "-")


def headings(text: str) -> list[Heading]:
    """The ATX headings of levels 2 to 4, outside fenced code, with GitHub's duplicate numbering."""
    out: list[Heading] = []
    seen: dict[str, int] = {}
    fence = None
    for line in text.replace("\r\n", "\n").split("\n"):
        f = FENCE_RE.match(line)
        if fence is None and f:
            fence = f.group(1)
            continue
        if fence is not None:
            if f and f.group(1)[0] == fence[0] and len(f.group(1)) >= len(fence) and not line.strip().strip(fence[0]):
                fence = None
            continue
        m = HEADING_RE.match(line)
        if not m:
            continue
        raw = m.group(2).strip()
        base = base_slug(raw)
        n = seen.get(base, 0)
        seen[base] = n + 1
        num = NUMBER_RE.match(raw)
        out.append(Heading(len(m.group(1)), raw, num.group(1) if num else None, base if n == 0 else f"{base}-{n}"))
    return out


def resolve(text: str, label: str) -> Heading:
    """The one heading LABEL names. LookupError when none does, or when more than one does."""
    hits = [h for h in headings(text) if label == h.number or label == h.slug]
    if not hits:
        raise LookupError(f"no section §{label}")
    if len(hits) > 1:
        raise LookupError(f"§{label} is ambiguous: {', '.join(h.slug for h in hits)}")
    return hits[0]


def anchor_id(adr_id: str, heading: Heading) -> str:
    return f"{adr_id.lower()}-{heading.slug}"


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: adr_sections.py ADR-NNNN", file=sys.stderr)
        return 2
    found = sorted(DECISIONS.glob(f"{argv[0]}-*.md"))
    if len(found) != 1:
        print(f"error: {argv[0]} is {len(found)} files in {DECISIONS}, expected one", file=sys.stderr)
        return 2
    for h in headings(found[0].read_text(encoding="utf-8")):
        print(f"{h.number or '-'}\t{h.slug}\t{h.level}\t{h.text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
