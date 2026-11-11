"""Tests for check_export.py.

Run from the worktree root:
    python -m unittest discover -s docs/arch/tools -p "test_*.py"

The export under test is a small page built here from the real view ids, so
these tests need neither helm nor a browser. Each of the nine checks has a
test that makes it fail, and the barred scan has one for a value split across
tags and one for a value escaped.
"""
import io
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_export  # noqa: E402
import capability_phases  # noqa: E402
import check_views  # noqa: E402
import render_profile as rp  # noqa: E402

ARCH = HERE.parent
TREE = check_views.Tree(ARCH)
FENCES = sum(check_export.fence_count(t) for t in TREE.view_text.values())
CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
       "img-src data:; font-src data:")
PROV = ('<div class="provenance" data-provenance><p data-prov="chart">Chart: demo 1.2.3</p>'
        '<p data-prov="digest">Bundle digest: sha256:' + "ab" * 32 + ' <span>of the values files read, in order: a.yaml</span></p>'
        '<p data-prov="date">Generated: 2026-01-02</p>'
        '<p data-prov="declared">Declared, not measured: this export reads the views.</p></div>')
SVG = '<figure class="diagram"><svg id="d" xmlns="http://www.w3.org/2000/svg"><text>a</text></svg></figure>'
BARRED = "zebra-[0-9]{3}\nstriped horse\n"
_INV = check_views.outside_fences(TREE.text(ARCH / "INVENTORY.md"))
SLOTS = [r[0].strip("` ") for r in check_views.table_after(
    _INV, _INV.index(check_views.SLOT_INVENTORY_HEADER))[1] if r]


def declarations(slots=SLOTS, prov=PROV):
    rows = "".join(f'<tr><td><code><span class="nb">{s}</span></code></td><td>f</td></tr>' for s in slots)
    return (f'<section id="declarations" class="page" data-declarations><h1>d</h1>'
            f'<table><tr><th>Slot</th><th>What it fills</th></tr>{rows}</table>{prov}</section>')


CAPS = list(capability_phases.model_capabilities(TREE.sysml))
DECISIONS = sorted(f.name for f in (ARCH.parent.parent / "decisions").glob("ADR-*.md"))
STAMP = "Commit abc1234, 2026-01-02: decisions/{}"


def capability_page(name, prov=PROV, what="A description."):
    return (f'<section id="cap-{name}" class="page capability"><h1>{name}</h1>'
            f'<h2>What it is</h2><p data-what>{what}</p><p data-derived>From ADR-0038 s1.</p>{prov}</section>')


def decision_page(pid, stamp, prov=PROV):
    return (f'<section id="{pid}" class="page decision"><h1>{pid}</h1>'
            f'<p class="stamp" data-stamp>{stamp}</p>{prov}</section>')


def extra_pages(prov=PROV):
    pages = [capability_page(c, prov) for c in CAPS]
    pages += [decision_page(f[:8].lower(), STAMP.format(f), prov) for f in DECISIONS]
    pages.append(decision_page("decision-roadmap", "Commit abc1234, 2026-01-02: decisions/ROADMAP.md", prov))
    return pages


def good(views=None, diagrams=FENCES, prov=PROV, decl=None):
    views = list(TREE.views) if views is None else views
    pages = [f'<section id="front" class="page" data-front><h1>x</h1><a href="#view-{views[0]}">v</a>{prov}</section>']
    for i, v in enumerate(views):
        body = SVG * (diagrams if i == 0 else 0)
        if i == 0:
            body += '<details class="exceptions"><summary>Exceptions: 1 row</summary></details>'
        pages.append(f'<section id="view-{v}" class="page view" data-view="{v}"><h1>{v}</h1>{body}{prov}</section>')
    pages.append(declarations(prov=prov) if decl is None else decl)
    pages += extra_pages(prov)
    return ('<!doctype html><html><head>'
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}"></head><body>'
            + "".join(pages) + "</body></html>")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, True))
        (self.tmp / "barred.txt").write_text(BARRED, encoding="utf-8")

    def run_check(self, doc, barred=None):
        f = self.tmp / "e.html"
        f.write_bytes(doc.encode("utf-8") if isinstance(doc, str) else doc)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = check_export.main(["--export", str(f), "--root", str(ARCH),
                                    "--barred", str(barred or self.tmp / "barred.txt")])
        return rc, out.getvalue(), err.getvalue()

    def fails(self, doc, word):
        rc, out, err = self.run_check(doc)
        self.assertEqual(rc, 1, err)
        self.assertIn(f"FAIL: {word}:", err)
        return err


class Green(Base):
    def test_a_good_export_passes_with_the_ok_line(self):
        doc = good()
        rc, out, err = self.run_check(doc)
        self.assertEqual(rc, 0, err)
        self.assertEqual(out.strip(), f"ok: export: {len(TREE.views) + 2 + len(CAPS) + len(DECISIONS) + 1} pages, {len(TREE.views)} views, equal to check_views; "
                                      f"{FENCES} diagrams; {len(doc.encode())} bytes; barred: 0 on 2 entries of barred.txt")


class Red(Base):
    def test_capability_page_without_description_fails(self):
        doc = good().replace("<p data-what>A description.</p>", "<p data-what> </p>", 1)
        err = self.fails(doc, "capabilities")
        self.assertIn(f"cap-{CAPS[0]}", err)

    def test_missing_capability_page_fails(self):
        doc = re.sub(rf'<section id="cap-{CAPS[0]}".*?</section>', "", good(), count=1, flags=re.S)
        err = self.fails(doc, "capabilities")
        self.assertIn(f"missing {CAPS[0]}", err)

    def test_decision_page_without_stamp_fails(self):
        doc = re.sub(r'<p class="stamp" data-stamp>.*?</p>', "", good(), count=1, flags=re.S)
        self.fails(doc, "decisions")

    def test_decision_page_with_a_malformed_stamp_fails(self):
        doc = good().replace(STAMP.format(DECISIONS[0]), "decisions/x", 1)
        self.fails(doc, "decisions")

    def test_missing_decision_page_fails(self):
        doc = re.sub(r'<section id="decision-roadmap".*?</section>', "", good(), count=1, flags=re.S)
        err = self.fails(doc, "decisions")
        self.assertIn("missing decision-roadmap", err)

    def test_a_relative_decision_href_fails_and_is_named(self):
        err = self.fails(good().replace("<h1>x</h1>", '<h1>x</h1><a href="decisions/x.md">d</a>'), "network")
        self.assertIn("'decisions/x.md'", err)

    def test_1_view_count_and_ids(self):
        views = list(TREE.views)
        self.fails(good(views[:-1]), "views")
        self.fails(good(views + ["Zz-Zz"]), "views")
        err = self.fails(good(views[:-1] + ["Zz-Zz"]), "views")
        self.assertIn("missing " + views[-1], err)

    def test_2_barred_value_raw(self):
        err = self.fails(good().replace("<h1>x</h1>", "<h1>zebra-123</h1>"), "barred")
        self.assertNotIn("zebra", err)

    def test_2_barred_value_split_across_tags(self):
        err = self.fails(good().replace("<h1>x</h1>", "<h1>zeb<tspan>ra-1</tspan>23</h1>"), "barred")
        self.assertNotIn("zebra", err)

    def test_2_barred_value_split_by_whitespace(self):
        self.fails(good().replace("<h1>x</h1>", "<h1>zebra-<tspan>1</tspan> <tspan>2</tspan>\n<tspan>3</tspan></h1>"),
                   "barred")

    def test_2_a_two_word_value_split_across_tags(self):
        err = self.fails(good().replace("<h1>x</h1>", "<h1><tspan>striped</tspan><tspan>horse</tspan></h1>"), "barred")
        self.assertNotIn("striped", err)

    def test_2_barred_value_in_another_case(self):
        self.fails(good().replace("<h1>x</h1>", "<h1>ZEBRA-123</h1>"), "barred")

    def test_2_barred_value_escaped(self):
        self.fails(good().replace("<h1>x</h1>", "<h1>&#122;ebra&#45;123</h1>"), "barred")
        self.fails(good().replace("<h1>x</h1>", "<h1>zebra&#x2d;123</h1>"), "barred")

    def test_2_a_list_that_cannot_be_read_is_exit_2(self):
        rc, _, err = self.run_check(good(), barred=self.tmp / "missing.txt")
        self.assertEqual(rc, 2, err)

    def test_3_provenance_missing_block_part_or_disagreement(self):
        self.fails(good().replace(PROV, "", 1), "provenance")
        for part in ("chart", "digest", "date", "declared"):
            doc = re.sub(rf'<p data-prov="{part}">.*?</p>', "", good(), count=1)
            err = self.fails(doc, "provenance")
            self.assertIn(f"lacks the {part} part", err)
        self.fails(good().replace("2026-01-02", "2026-01-03", 1), "provenance")
        self.fails(good().replace("Bundle digest: sha256:" + "ab" * 32, "Bundle digest: sha256:xyz", 1), "provenance")
        self.fails(good().replace('<section id="front"', '<section id="home"', 1), "provenance")

    def test_4_network(self):
        marks = ['<link rel="stylesheet" href="#x">', '<iframe></iframe>', '<object></object>', '<embed>',
                 '<img src="data:x">', '<style>@import "a";</style>', '<style>@IMPORT "a";</style>', '<style>a{b:url(https://x)}</style>',
                 '<a href="https://example.org">x</a>', '<a href="docs/x.md">x</a>',
                 '<svg><use xlink:href="https://x/y"/></svg>']
        for m in marks:
            self.fails(good().replace("<h1>x</h1>", "<h1>x</h1>" + m), "network")
        self.fails(good().replace('<meta http-equiv="Content-Security-Policy"', '<meta name="x"'), "network")

    def test_4_svg_namespace_declarations_are_allowed(self):
        doc = good().replace("<h1>x</h1>", '<h1>x</h1><svg xmlns="http://www.w3.org/2000/svg" '
                             'xmlns:xlink="http://www.w3.org/1999/xlink"></svg>')
        rc, _, err = self.run_check(doc)
        self.assertEqual(rc, 0, err)

    def test_5_size(self):
        pad = "x" * (check_export.MAX_BYTES - len(good().encode()) + 1)
        self.fails(good().replace("</body>", f"<!--{pad}--></body>"), "size")
        under = "x" * (check_export.MAX_BYTES - len(good().encode()) - 100)
        rc, _, err = self.run_check(good().replace("</body>", f"<!--{under}--></body>"))
        self.assertEqual(rc, 0, err)

    def test_6_dead_link(self):
        err = self.fails(good().replace("<h1>x</h1>", '<h1>x</h1><a href="#view-Nope">n</a>'), "links")
        self.assertIn("Nope", err)
        self.fails(good().replace("<h1>x</h1>", '<h1>x</h1><a href="#">n</a>'), "links")

    def test_7_diagrams(self):
        self.fails(good().replace("<h1>x</h1>", '<h1>x</h1><pre><code class="language-mermaid">a</code></pre>'),
                   "diagrams")
        self.fails(good(diagrams=FENCES - 1), "diagrams")
        self.fails(good(diagrams=FENCES + 1), "diagrams")

    def test_8_exceptions(self):
        self.fails(good().replace('<details class="exceptions">', "<details>"), "exceptions")

    def test_9_declarations(self):
        self.assertEqual(len(SLOTS), 13)
        self.fails(good(decl=""), "declarations")
        self.fails(good(decl=declarations() + declarations()), "declarations")
        err = self.fails(good(decl=declarations(SLOTS[:-1])), "declarations")
        self.assertIn("lists 12 slots, INVENTORY.md's slot table 13", err)
        self.fails(good(decl=declarations([SLOTS[1], SLOTS[0]] + SLOTS[2:])), "declarations")
        self.fails(good(decl=declarations(SLOTS[:-1] + ["spare-slot"])), "declarations")


class Input(Base):
    def test_missing_export_is_exit_2(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = check_export.main(["--export", str(self.tmp / "none.html"), "--root", str(ARCH),
                                    "--barred", str(self.tmp / "barred.txt")])
        self.assertEqual(rc, 2)

    def test_a_missing_root_is_exit_2(self):
        (self.tmp / "e.html").write_text(good(), encoding="utf-8")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = check_export.main(["--export", str(self.tmp / "e.html"), "--root", str(self.tmp / "nope"),
                                   "--barred", str(self.tmp / "barred.txt")])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
