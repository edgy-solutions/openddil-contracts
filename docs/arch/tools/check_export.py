#!/usr/bin/env python3
"""check_export.py - check the single-file HTML export of the architecture views.

Usage:
    python docs/arch/tools/check_export.py --export FILE [--root docs/arch]
        --barred FILE [--barred FILE ...]

Reads the file written by render_html.py and docs/arch (through
check_views.Tree) and writes one `FAIL: <check>: <what>` line per finding on
stderr, exiting 1 if there is any. When nothing fails it prints one `ok:` line.

Checks: views (the data-view sections equal the views check_views reads, in
number and ids), barred (no barred value in the raw file, in its text with
tags stripped and entities unescaped, with each tag read as nothing or as a
space, or in that text with whitespace removed, so a value split across SVG
text runs or escaped is still caught; a finding never says which value or
where), provenance (every page carries the
four parts and the pages agree), network (a Content-Security-Policy, and no
src, import, link, frame, object, embed, remote url() or href that does not
start with #), size (under 16,000,000 bytes), links (every # href has an id),
diagrams (no Mermaid source left; one SVG per Mermaid fence in the views),
exceptions (at least one details.exceptions).

Exit codes: 0 ok, 1 a check failed, 2 bad input. Stdlib and PyYAML only.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_views  # noqa: E402
import render_profile as rp  # noqa: E402
from capability_phases import CheckError, load_barred, scan_barred  # noqa: E402

EXIT_OK, EXIT_CHECK, EXIT_INPUT = 0, 1, 2
MAX_BYTES = 16_000_000
PARTS = {
    "chart": re.compile(r"^Chart: \S+ \S+$"),
    "digest": re.compile(r"^Bundle digest: sha256:[0-9a-f]{64} of the values files read"),
    "date": re.compile(r"^Generated: \d{4}-\d{2}-\d{2}$"),
    "declared": re.compile(r"^Declared, not measured: "),
}
PAGE_RE = re.compile(r'<section id="([^"]+)" class="page[^"]*"[^>]*>(.*?)</section>', re.S)
PART_RE = re.compile(r'<p data-prov="(\w+)">(.*?)</p>', re.S)
ATTR_RE = re.compile(r"""(?<![\w.-])(href|src)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
SRC_BARE_RE = re.compile(r"(?<![\w.-])src\s*=", re.I)
NETWORK = [("@import", "an @import"), ("url(http", "a remote url()"), ("<link", "a <link>"),
           ("<iframe", "an <iframe>"), ("<object", "an <object>"), ("<embed", "an <embed>")]


class InputError(Exception):
    """Bad input: exit 2."""


def plain(raw: str) -> str:
    """Text with tags stripped, entities unescaped and whitespace collapsed to one space."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", raw))).strip()


def fence_count(text: str) -> int:
    n, fence = 0, False
    for in_fence, info, line in rp.split_fences(text):
        if in_fence and not fence:
            fence = True
            if info.startswith("mermaid"):
                n += 1
        elif not in_fence:
            fence = False
    return n


def check_views_equal(raw: str, tree: check_views.Tree) -> list[str]:
    got = re.findall(r'<section id="view-[^"]*" class="page view" data-view="([^"]+)"', raw)
    want = list(tree.views)
    if got == want:
        return []
    return [f"views: the export has {len(got)} view sections, check_views reads {len(want)}"
            + ("" if sorted(got) != sorted(want) else " (same ids, different order)")
            + "".join(f"; missing {v}" for v in want if v not in got)
            + "".join(f"; extra {v}" for v in got if v not in want)]


def check_barred(raw: str, barred) -> list[str]:
    text = plain(raw)
    spaced = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", raw)))
    fails = scan_barred({"the export": [raw, text, spaced, re.sub(r"\s+", "", text)]}, barred)
    return [f.replace("quotes: ", "barred: ", 1) for f in fails]


def check_provenance(raw: str) -> list[str]:
    pages = PAGE_RE.findall(raw)
    fails: list[str] = []
    if not any(pid == "front" for pid, _ in pages):
        fails.append("provenance: there is no front page")
    seen: dict[str, set[str]] = {k: set() for k in PARTS}
    for pid, body in pages:
        if 'data-provenance' not in body:
            fails.append(f"provenance: page {pid} has no provenance block")
            continue
        block = body[body.index("data-provenance"):]
        found = {k: plain(v) for k, v in PART_RE.findall(block)}
        for k, pat in PARTS.items():
            if k not in found:
                fails.append(f"provenance: page {pid} lacks the {k} part")
            elif not pat.match(found[k]):
                fails.append(f"provenance: page {pid} has a malformed {k} part")
            else:
                seen[k].add(found[k])
    for k, vals in seen.items():
        if len(vals) > 1:
            fails.append(f"provenance: pages disagree on the {k} part ({len(vals)} different values)")
    return fails


def check_network(raw: str) -> list[str]:
    fails: list[str] = []
    if not re.search(r'<meta http-equiv="Content-Security-Policy" content="[^"]*default-src \'none\'', raw):
        fails.append("network: no Content-Security-Policy with default-src 'none'")
    low = raw.lower()
    for needle, what in NETWORK:
        if needle in low:
            fails.append(f"network: the export holds {what}")
    if SRC_BARE_RE.search(raw):
        fails.append("network: the export holds a src attribute")
    bad = [m for m in ATTR_RE.finditer(raw) if m.group(1).lower() == "href" and not (m.group(2) or m.group(3) or "").startswith("#")]
    if bad:
        fails.append(f"network: {len(bad)} href(s) do not start with #")
    return fails


def check_size(size: int) -> list[str]:
    return [f"size: {size} bytes, limit {MAX_BYTES}"] if size >= MAX_BYTES else []


def check_links(raw: str) -> list[str]:
    ids = set(re.findall(r'(?<![\w-])id="([^"]*)"', raw))
    dead = sorted({(m.group(2) if m.group(2) is not None else m.group(3))[1:] for m in ATTR_RE.finditer(raw)
                   if m.group(1).lower() == "href" and (m.group(2) or m.group(3) or "").startswith("#")
                   and (m.group(2) if m.group(2) is not None else m.group(3))[1:] not in ids})
    return [f"links: {len(dead)} # link(s) with no matching id: {', '.join(repr(d) for d in dead[:5])}"] if dead else []


def diagram_count(raw: str) -> int:
    return len(re.findall(r'<figure class="diagram"[^>]*>\s*<svg\b', raw))


def check_diagrams(raw: str, tree: check_views.Tree) -> list[str]:
    fails: list[str] = []
    if "language-mermaid" in raw:
        fails.append("diagrams: a Mermaid source block is still in the export")
    want = sum(fence_count(t) for t in tree.view_text.values())
    got = diagram_count(raw)
    if got != want:
        fails.append(f"diagrams: {got} SVG diagrams, {want} Mermaid fences in the views")
    return fails


def check_exceptions(raw: str) -> list[str]:
    return [] if '<details class="exceptions"' in raw else ["exceptions: no details.exceptions in the export"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check the HTML export of the architecture views.")
    ap.add_argument("--export", required=True)
    ap.add_argument("--root", default=str(rp.ROOT))
    ap.add_argument("--barred", action="append", default=[], required=True)
    a = ap.parse_args(argv)
    try:
        try:
            data = Path(a.export).read_bytes()
        except OSError as e:
            raise InputError(f"cannot read {a.export}: {e.strerror or e}")
        raw = data.decode("utf-8", "replace")
        tree = check_views.Tree(Path(a.root))
        try:
            barred = load_barred(a.barred)
        except CheckError as e:
            raise InputError(e.args[0])
    except (InputError, check_views.InputError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INPUT
    fails = (check_views_equal(raw, tree) + check_barred(raw, barred) + check_provenance(raw)
             + check_network(raw) + check_size(len(data)) + check_links(raw)
             + check_diagrams(raw, tree) + check_exceptions(raw))
    for f in fails:
        print(f"FAIL: {f}", file=sys.stderr)
    if fails:
        return EXIT_CHECK
    print(f"ok: export: {len(tree.views)} views, equal to check_views; {diagram_count(raw)} diagrams; "
          f"{len(data)} bytes; barred: 0 on {len(barred)} entries of "
          f"{', '.join(Path(p).name for p in a.barred)}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
