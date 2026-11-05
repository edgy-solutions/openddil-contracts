#!/usr/bin/env python3
"""marks.py - the Evidence a Sources row takes from its record's status line.

A Sources row that cites a record in decisions/ whose status line fixes the
evidence carries the token `Status line` in its Evidence cell, never a copied
word. The token is replaced when the view is rendered
(render_profile.Renderer.view_text), so every view that cites a record changes
together when the record's status line changes, and no two views can read one
record two ways. check_views.py rule `marks` fails on a copied word where the
token belongs, on a token whose records fix nothing, and on a row whose records
disagree.

What a status line fixes, checked in this order:

  says "design only"                    Design only
  says "nothing built" or "plan only"   Nothing built
  anything else                         nothing: the row states its own Evidence

The status line is the record's `## Status` section, else its `Status:` line,
else the first paragraph under its title. Stdlib only.
"""
from __future__ import annotations

import re
from pathlib import Path

from data_exchange import InputError

STATUS_TOKEN = "Status line"
SOURCES_HEADER = "| Claim | Source | Decision | Evidence |"
LINK_RE = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")


def adr_status(text: str) -> str | None:
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if re.match(r"^##\s+Status\s*$", line):
            body = []
            for nxt in lines[i + 1:]:
                if nxt.startswith("#"):
                    break
                body.append(nxt)
            s = "\n".join(body).strip()
            return s or None
    for line in lines:
        m = re.match(r"^\**Status\**\s*[:\-]?\s*\**\s*(.+)$", line)
        if m:
            return m.group(1).strip()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            para = []
            for nxt in lines[i + 1:]:
                if nxt.strip():
                    para.append(nxt.strip())
                elif para:
                    break
            return " ".join(para) or None
    return None


def fixed_evidence(status: str | None) -> str | None:
    """The Evidence a status line fixes, or None when it fixes nothing."""
    low = (status or "").lower()
    if "design only" in low:
        return "Design only"
    if "nothing built" in low or "plan only" in low:
        return "Nothing built"
    return None


def cited_records(cell: str, view_dir: Path, decisions: Path) -> list[Path]:
    """The records in decisions/ that a Source cell links to, in order, each once."""
    out: list[Path] = []
    top = decisions.resolve()
    for target in LINK_RE.findall(cell):
        p = (view_dir / target.split("#", 1)[0]).resolve()
        if p.parent == top and p.suffix == ".md" and p not in out:
            out.append(p)
    return out


def row_evidence(cell: str, view_dir: Path, decisions: Path) -> tuple[str | None, list[tuple[str, str | None]]]:
    """(the one Evidence the cited records fix, or None; each record's name and what it fixes).

    A cited record that does not exist, or whose fixed values disagree with
    another's, raises InputError: the row cannot be read either way."""
    each = []
    for p in cited_records(cell, view_dir, decisions):
        if not p.is_file():
            raise InputError(f"cites {p.name}, which does not exist")
        each.append((p.name, fixed_evidence(adr_status(p.read_text(encoding="utf-8")))))
    values = sorted({v for _, v in each if v})
    if len(values) > 1:
        named = ", ".join(f"{n} {v or 'fixes nothing'}" for n, v in each)
        raise InputError(f"cites records whose status lines disagree: {named}")
    return (values[0] if values else None), each


def split_row(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def fill(body: str, view_dir: Path, decisions: Path, vid: str) -> str:
    """body with each Sources row's Evidence token replaced by what its records' status lines fix."""
    lines = body.split("\n")
    fence = False
    in_sources = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        if fence:
            continue
        if line.startswith("#"):
            in_sources = line.strip() == "## Sources"
            continue
        if not in_sources or not line.lstrip().startswith("|"):
            continue
        cells = split_row(line)
        if len(cells) != 4 or cells[3] != STATUS_TOKEN:
            continue
        claim = cells[0][:50]
        try:
            value, each = row_evidence(cells[1], view_dir, decisions)
        except InputError as e:
            raise InputError(f"view {vid}: row '{claim}' {e}") from None
        if not each:
            raise InputError(f"view {vid}: row '{claim}' says {STATUS_TOKEN} and cites no record")
        if value is None:
            raise InputError(f"view {vid}: row '{claim}' says {STATUS_TOKEN} and no record it cites fixes the evidence")
        at = line.rindex(STATUS_TOKEN)  # the last cell, so the row keeps its own spacing
        lines[i] = line[:at] + value + line[at + len(STATUS_TOKEN):]
    return "\n".join(lines)
