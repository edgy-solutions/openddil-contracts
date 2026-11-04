"""Tests for render_html.py.

Run from the worktree root:
    python -m unittest discover -s docs/arch/tools -p "test_*.py"

The page is built in process with a fake diagram renderer, so no browser is
needed. The build tests need helm and the sibling chart and bundle, the same
as test_render_profile.py; they skip, printing why, when either is missing.
The unit tests need only the tree.
"""
import argparse
import html
import os
import re
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_views  # noqa: E402
import render_html  # noqa: E402
from capability_phases import CheckError  # noqa: E402
from data_exchange import InputError  # noqa: E402

ARCH = HERE.parent
PROFILES = yaml.safe_load((ARCH / "profiles.yaml").read_text(encoding="utf-8"))
SIBLINGS = Path(os.environ.get("OPENDDIL_REPOS", HERE.parents[3]))
CHART = SIBLINGS / "openddil-helm" / "openddil-demo"
BUNDLE_ROOT = Path(os.environ.get("OPENDDIL_BUNDLE", SIBLINGS / "openddil-customer-bundle-example"))
BUNDLE = BUNDLE_ROOT / "k8s" / "tier-node-values.yaml"
OVERLAY = BUNDLE_ROOT / "k8s" / "egress-values.yaml"
READINESS = CHART.parent / "scripts" / "RECORDING-READINESS.md"
HAVE_BUILD = (shutil.which("helm") is not None and CHART.is_dir() and BUNDLE.is_file() and OVERLAY.is_file()
              and render_html.MarkdownIt is not None)
SKIP_WHY = ("build tests skipped: need helm on PATH, markdown-it-py, the chart at " + str(CHART)
            + ", and the twin values at " + str(OVERLAY.parent))
if not HAVE_BUILD:
    print(SKIP_WHY, file=sys.stderr)

DATE = "2026-01-02"
FILLED_RE = re.compile(r'<span class="filled">(.*?)</span>(?=\s|<)', re.S)


def fake(source, svg_id):
    return f'<svg id="{svg_id}" xmlns="http://www.w3.org/2000/svg"><text>diagram</text></svg>'


def args():
    return argparse.Namespace(chart=str(CHART), values=[str(BUNDLE), str(OVERLAY)], release="openddil",
                              readiness=str(READINESS), record=str(ARCH / "capability-record.yaml"),
                              slots=None, allow_no_kinds=None)


def plain(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", fragment))).strip()


def section(doc, vid):
    m = re.search(rf'<section id="view-{re.escape(vid)}".*?</section>', doc, re.S)
    return m.group(0)


def grid(doc, profile):
    return re.search(rf'<div class="grid" id="grid-{profile}".*?</div></div>', doc, re.S).group(0)


class Grids(unittest.TestCase):
    rows = render_html.appendix_ids(ARCH)

    def test_every_uaf_id_is_placed_once(self):
        cells = render_html.uaf_cells(self.rows)
        placed = [i for v in cells.values() for i in v]
        self.assertEqual(len(placed), len(set(placed)))
        self.assertEqual(set(placed), {r[0] for r in self.rows})

    def test_every_dodaf_and_naf_id_is_placed_once(self):
        for col, fn in ((2, render_html.dodaf_cells), (3, render_html.naf_cells)):
            ids = render_html.named_ids(self.rows, col)
            placed = [i for v in fn(ids).values() for i in v]
            self.assertEqual(sorted(placed), sorted(ids))
            self.assertEqual(len(placed), len(set(placed)))

    def test_natural_sort_in_a_cell(self):
        self.assertEqual(sorted(["OV-10", "OV-5b", "OV-5a", "OV-2"], key=render_html.natural_key),
                         ["OV-2", "OV-5a", "OV-5b", "OV-10"])

    def test_compound_naf_id_sits_in_its_first_part(self):
        cells = render_html.naf_cells(["L2-L3", "L4-P4", "C1-S1", "Ar"])
        self.assertEqual(cells[("L", "2")], ["L2-L3"])
        self.assertEqual(cells[("L", "4")], ["L4-P4"])
        self.assertEqual(cells[("C", "1")], ["C1-S1"])
        self.assertEqual(cells[("A", "r")], ["Ar"])

    def test_repeated_uaf_id_is_one_entry_and_rm_cell_is_shared(self):
        rows = [["Ps-Ct", "a", "-", "-", "-"], ["Ps-Ct", "b", "-", "-", "-"],
                ["St-Rm-P", "c", "-", "-", "-"], ["St-Rm-Dm", "d", "-", "-", "-"]]
        cells = render_html.uaf_cells(rows)
        self.assertEqual(cells[("Ps", "Ct")], ["Ps-Ct"])
        self.assertEqual(cells[("St", "Rm")], ["St-Rm-Dm", "St-Rm-P"])

    def test_unknown_prefix_or_shape_is_an_input_error(self):
        with self.assertRaises(InputError):
            render_html.uaf_cells([["Zz-Cn", "x", "-", "-", "-"]])
        with self.assertRaises(InputError):
            render_html.uaf_cells([["Op-Zz", "x", "-", "-", "-"]])
        with self.assertRaises(InputError):
            render_html.dodaf_cells(["QV-1"])
        with self.assertRaises(InputError):
            render_html.naf_cells(["Q1"])
        with self.assertRaises(InputError):
            render_html.naf_cells(["L9"])

    def test_filled_cell_links_every_source_and_empty_cell_does_not(self):
        names = {"Op-Sr": "Operational-Structure", "Op-Cn": "Operational-Connectivity"}
        one = render_html.cell_html("X-1", ["Op-Sr"], names)
        self.assertIn('<a href="#view-Op-Sr" title="Operational-Structure">X-1</a>', one)
        two = render_html.cell_html("OV-2", ["Op-Sr", "Op-Cn"], names)
        self.assertEqual(two.count("<a "), 2)
        none = render_html.cell_html("Y-2", [], names)
        self.assertNotIn("<a", none)
        self.assertIn('class="empty"', none)


class Dx(unittest.TestCase):
    base = "intro\n\n| A | B | C |\n|---|---|---|\n| 1 | 2 | 3 |\n\nend"

    def docs(self, **over):
        d = {"uaf": self.base, "dodaf202": self.base.replace("| B |", "| Bd |"),
             "naf4": self.base.replace("| C |", "| Cn |")}
        d.update(over)
        return d

    def test_header_row_differences_become_markers(self):
        text, cells = render_html.dx_variants(self.docs())
        self.assertIn("zzpname0zz", text)
        self.assertIn("zzpname1zz", text)
        self.assertEqual(len(cells), 2)
        self.assertEqual(cells[0], {"uaf": "B", "dodaf202": "Bd", "naf4": "B"})
        self.assertEqual(cells[1], {"uaf": "C", "dodaf202": "C", "naf4": "Cn"})
        self.assertEqual(text.split("\n")[0], "intro")
        self.assertEqual(text.split("\n")[4], "| 1 | 2 | 3 |")

    def test_a_planted_difference_on_another_line_raises(self):
        for line, edit in ((0, "intro changed"), (4, "| 1 | 9 | 3 |"), (6, "end changed")):
            other = self.base.split("\n")
            other[line] = edit
            with self.assertRaises(CheckError) as cm:
                render_html.dx_variants(self.docs(dodaf202="\n".join(other)))
            self.assertIn(f"line {line + 1}", cm.exception.args[0])
            self.assertIn("dodaf202", cm.exception.args[0])

    def test_a_body_row_that_looks_like_a_header_still_raises(self):
        other = self.base.replace("| 1 | 2 | 3 |", "| 1 | 2 | 4 |")
        with self.assertRaises(CheckError):
            render_html.dx_variants(self.docs(naf4=other))

    def test_a_different_line_count_raises(self):
        with self.assertRaises(CheckError):
            render_html.dx_variants(self.docs(naf4=self.base + "\nmore"))


class Markdown(unittest.TestCase):
    views = {"Rs-Sr": {"file": "views/Rs-Sr.md", "name": "Resources-Structure"}}

    def page(self, text, diagram=fake):
        return render_html.Page("Rs-Cn", self.views, diagram).render(text)

    def test_comments_are_removed_outside_fences_only(self):
        out = self.page("a <!-- gone --> b\n\n<!-- also\ngone -->\n\n```text\n<!-- kept -->\n```\n")
        self.assertNotIn("gone", out)
        self.assertIn("&lt;!-- kept --&gt;", out)

    def test_links(self):
        out = self.page("[v](Rs-Sr.md#x) [t](../tools/data_exchange.py) [w](https://example.org/a) "
                        "<https://example.org/b>")
        self.assertIn('<a href="#view-Rs-Sr">v</a>', out)
        self.assertIn('<span class="ref" title="docs/arch/tools/data_exchange.py">t</span>', out)
        self.assertIn("w (https://example.org/a)", out)
        self.assertNotIn('href="https', out)
        self.assertEqual(out.count("https://example.org/b"), 1)
        self.assertNotIn("href=\"../", out)

    def test_slot_outside_a_fence_is_a_span_and_inside_stays_in_the_diagram_source(self):
        seen = []

        def spy(source, svg_id):
            seen.append(source)
            return fake(source, svg_id)
        out = self.page("x {{slot:feeds}} y\n\n```mermaid\nflowchart TB\n  a[\"{{slot:feeds}}\"]\n```\n", spy)
        self.assertIn('<span class="slot">{{slot:feeds}}</span>', out)
        self.assertIn("{{slot:feeds}}", seen[0])
        self.assertEqual(out.count('class="slot"'), 1)

    def test_diagram_and_other_fences(self):
        out = self.page("```mermaid\nflowchart TB\n```\n\n```sysml\npackage P {}\n```\n")
        self.assertIn('<figure class="diagram" data-diagram="1"><svg id="mmd-Rs-Cn-1"', out)
        self.assertNotIn("language-mermaid", out)
        self.assertIn('<pre><code class="language-sysml">package P {}', out)

    def test_exception_table_goes_in_a_closed_details(self):
        p = render_html.Page("Rs-Cn", self.views, fake)
        out = p.render("### Exceptions\n\n| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n\n### Other\n\n| A |\n|---|\n| 1 |\n")
        self.assertEqual(p.exceptions, 1)
        self.assertEqual(out.count("<details"), 1)
        self.assertNotIn("<details open", out)
        self.assertIn("<summary>Exceptions: 2 rows</summary>", out)

    def test_raw_html_is_escaped(self):
        out = self.page("<script>alert(1)</script>\n\ntext <b>x</b>\n")
        self.assertNotIn("<script", out)
        self.assertNotIn("<b>", out)

    def test_diagram_results_are_screened(self):
        for bad in ('<svg><script>x</script></svg>', '<svg><style>@import "a";</style></svg>',
                    '<svg><style>a{background:url(https://x)}</style></svg>',
                    '<svg><text>Syntax error in text</text></svg>',
                    '<svg><image href="https://x/y.png"/></svg>', '<div>not svg</div>'):
            with self.assertRaises(CheckError, msg=bad):
                render_html.clean_svg(bad)
        self.assertEqual(render_html.clean_svg('<?xml version="1.0"?>\n<svg a="b"></svg>'), '<svg a="b"></svg>')

    def test_a_failed_diagram_names_the_view_and_number(self):
        def boom(source, svg_id):
            if svg_id.endswith("-2"):
                raise CheckError("mermaid-cli exit 1: bad")
            return fake(source, svg_id)
        page = render_html.Page("Op-Pr", self.views, render_html.checked(boom, "Op-Pr"))
        with self.assertRaises(CheckError) as cm:
            page.render("```mermaid\na\n```\n\n```mermaid\nb\n```\n")
        self.assertIn("view Op-Pr diagram 2", cm.exception.args[0])

    def test_missing_mmdc_is_an_input_error(self):
        with self.assertRaises(InputError):
            render_html.make_mmdc(str(HERE / "no-such-mmdc"), None)


class Args(unittest.TestCase):
    def test_chart_values_release_and_out_are_required(self):
        base = ["--out", "x.html", "--chart", "c", "--values", "v", "--release", "r"]
        for drop in ("--out", "--chart", "--values", "--release"):
            argv = list(base)
            i = argv.index(drop)
            del argv[i:i + 2]
            with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as cm:
                render_html.main(argv)
            self.assertEqual(cm.exception.code, 2, drop)

    def test_bad_date_is_exit_2(self):
        with mock.patch("sys.stderr"):
            rc = render_html.main(["--out", "x.html", "--chart", "c", "--values", "v", "--release", "r",
                                   "--date", "yesterday"])
        self.assertEqual(rc, 2)

    def test_values_digest_normalises_line_ends(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a" / "v.yaml", Path(d) / "b" / "v.yaml"
            a.parent.mkdir()
            b.parent.mkdir()
            a.write_bytes(b"x: 1\r\ny: 2\r\n")
            b.write_bytes(b"x: 1\ny: 2\n")
            self.assertEqual(render_html.values_digest([str(a)]), render_html.values_digest([str(b)]))
            b.write_bytes(b"x: 1\ny: 3\n")
            self.assertNotEqual(render_html.values_digest([str(a)]), render_html.values_digest([str(b)]))


@unittest.skipUnless(HAVE_BUILD, SKIP_WHY)
class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = render_html.build(args(), fake, DATE)
        cls.tree = check_views.Tree(ARCH)

    def test_one_section_per_view_in_profile_order(self):
        got = re.findall(r'<section id="view-([^"]+)" class="page view" data-view="\1"', self.doc)
        self.assertEqual(got, list(PROFILES["views"]))
        self.assertEqual(got, list(self.tree.views))

    def test_same_inputs_and_date_give_identical_bytes(self):
        again = render_html.build(args(), fake, DATE)
        self.assertEqual(again.encode("utf-8"), self.doc.encode("utf-8"))
        other = render_html.build(args(), fake, "2026-01-03")
        self.assertNotEqual(other, self.doc)

    def test_filled_set_equals_profiles_yaml_and_filled_cells_link(self):
        uaf = grid(self.doc, "uaf")
        linked = set(re.findall(r'<a href="#view-([^"]+)"', uaf))
        self.assertEqual(linked, set(PROFILES["views"]))
        for prof in ("dodaf202", "naf4"):
            g = grid(self.doc, prof)
            ids = {x for e in PROFILES["views"].values() for x in (e.get("exports") or {}).get(prof) or []}
            filled = set(re.findall(r'<a href="#view-[^"]+" title="[^"]*">([^<]+)</a>', g))
            self.assertEqual(filled, ids, prof)
            empties = re.findall(r'<span class="empty">(.*?)</span>', g)
            self.assertTrue(empties)
            self.assertFalse(set(empties) & ids, prof)
        self.assertNotIn("<a", " ".join(re.findall(r'<span class="empty">.*?</span>', self.doc)))

    def test_empty_uaf_cells_are_muted_and_unlinked(self):
        uaf = grid(self.doc, "uaf")
        self.assertRegex(uaf, r'<span class="empty"[^>]*>Am-Cn</span>')
        self.assertIn(f"{len(PROFILES['views'])} of ", uaf)

    def test_multi_source_export_has_a_link_per_source(self):
        g = grid(self.doc, "dodaf202")
        sources = [v for v, e in PROFILES["views"].items() if "OV-2" in (e.get("exports") or {}).get("dodaf202", [])]
        self.assertGreater(len(sources), 1)
        for v in sources:
            self.assertRegex(g, rf'<a href="#view-{v}" title="[^"]*">OV-2</a>')

    def test_not_exported_table_under_the_selecting_grids(self):
        for prof in ("dodaf202", "naf4"):
            g = grid(self.doc, prof)
            self.assertIn("Not exported in", g)
            for v in ("Sc-Sr", "Sc-Cn", "Sc-Pr"):
                self.assertIn(f"({v})", g, prof)
        self.assertNotIn("Not exported in", grid(self.doc, "uaf"))

    def test_no_dndaf(self):
        self.assertNotIn("grid-dndaf", self.doc.lower())
        self.assertNotIn("data-profile-btn=\"dndaf", self.doc.lower())

    def test_every_page_has_all_four_provenance_parts_alike(self):
        blocks = re.findall(r'<div class="provenance" data-provenance>(.*?)</div>', self.doc, re.S)
        self.assertEqual(len(blocks), len(PROFILES["views"]) + 1)
        self.assertEqual(len(set(blocks)), 1)
        text = plain(blocks[0])
        self.assertRegex(text, r"Chart: \S+ \S+ Bundle digest: sha256:[0-9a-f]{64} of the values files read")
        self.assertIn("Generated: " + DATE, text)
        self.assertIn(render_html.DECLARED, text)

    def test_no_href_but_fragments_and_no_network(self):
        hrefs = re.findall(r'(?<![\w.-])href="([^"]*)"', self.doc)
        self.assertTrue(hrefs)
        self.assertTrue(all(h.startswith("#") for h in hrefs))
        self.assertNotIn(" src=", self.doc)
        self.assertIn("Content-Security-Policy", self.doc)

    def test_exception_table_is_in_a_closed_details(self):
        self.assertEqual(self.doc.count('<details class="exceptions">'), 1)
        self.assertNotIn("<details open", self.doc)

    def test_data_exchange_headers_are_pname(self):
        rs = section(self.doc, "Rs-Cn")
        ths = re.findall(r'<th class="pname" data-uaf="([^"]*)" data-dodaf202="([^"]*)" data-naf4="([^"]*)">', rs)
        self.assertEqual(len(ths), 3)
        self.assertIn(("Topic", "Resource flow", "Information flow"), ths)
        self.assertIn(("Writer", "Sending resource", "Producer"), ths)
        self.assertNotIn("zzpname", self.doc)

    def test_titles_per_profile(self):
        h1 = re.search(r'<section id="view-Rs-Cn".*?<h1 class="pname" data-uaf="([^"]*)" data-dodaf202="([^"]*)" '
                       r'data-naf4="([^"]*)"', self.doc, re.S).groups()
        self.assertTrue(h1[0].endswith("(Rs-Cn)"))
        self.assertIn("SV-3", h1[1])
        self.assertTrue(h1[1].endswith("(DoDAF 2.02)"))
        self.assertIn("P3 Resource Connectivity", h1[2])
        sc = re.search(r'<section id="view-Sc-Sr".*?<h1 class="pname" data-uaf="([^"]*)" data-dodaf202="([^"]*)"',
                       self.doc, re.S).groups()
        self.assertIn("Not exported in DoDAF 2.02: ", sc[1])
        self.assertIn('data-profile-only data-for="dodaf202"', section(self.doc, "Sc-Sr"))
        self.assertNotIn("data-profile-only", section(self.doc, "Rs-Cn"))

    def test_body_holds_the_generators_paragraphs(self):
        uaf_args = argparse.Namespace(**{**vars(args()), "profile": "uaf"})
        r = render_html.rp.Renderer(uaf_args, ARCH / "views")
        checked = 0
        for vid in ("Rs-Cn", "Sm-Ov"):
            _, body = r.view_text(vid, render_html.rp.demote(r.dx_content()))
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", "", section(self.doc, vid))))
            for para in re.split(r"\n\s*\n", body):
                para = para.strip()
                if not para or para[0] in "|#`-<*>" or para[0].isdigit() or "(" in para or "[" in para:
                    continue
                want = re.sub(r"\s+", " ", para.replace("`", "").replace("**", ""))
                self.assertIn(want, text, f"{vid}: {want[:60]}")
                checked += 1
        self.assertGreater(checked, 3)

    def test_unfilled_slots_are_spans(self):
        self.assertIn('<span class="slot">{{slot:', self.doc)
        self.assertNotIn("{{slot:", re.sub(r'<span class="slot">.*?</span>', "", self.doc).split("<style>")[0])

    def test_build_fails_when_no_exception_table_renders(self):
        with mock.patch.object(render_html.Page, "render", lambda self, t: "<p>x</p>"):
            with self.assertRaises(CheckError) as cm:
                render_html.build(args(), fake, DATE)
        self.assertIn("exception", cm.exception.args[0])

    def test_a_failing_diagram_fails_the_build_naming_view_and_number(self):
        def boom(source, svg_id):
            raise CheckError("mermaid-cli exit 1: bad")
        with self.assertRaises(CheckError) as cm:
            render_html.build(args(), boom, DATE)
        self.assertRegex(cm.exception.args[0], r"view \S+ diagram 1")


def tbl(head, rows, extra=""):
    h = "".join(f"<th>{c}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table>\n<thead>\n<tr>{h}</tr>\n</thead>\n<tbody>\n{b}\n</tbody>\n</table>{extra}"


def text_of(h):
    return html.unescape(re.sub(r"<[^>]*>", "", h))


class StyleTables(unittest.TestCase):
    st = staticmethod(render_html.style_tables)

    def test_hyphen_and_slash_tokens_are_wrapped_and_text_is_unchanged(self):
        src = tbl(["A"], [["see a-b and c/d now"]])
        out = self.st(src)
        self.assertIn('<span class="nb">a-b</span>', out)
        self.assertIn('<span class="nb">c/d</span>', out)
        self.assertEqual(text_of(out), text_of(src))

    def test_plain_words_are_not_wrapped(self):
        out = self.st(tbl(["A"], [["plain words, with_under. and (parens) x"]]))
        self.assertNotIn('class="nb"', out)

    def test_tags_and_attributes_are_untouched(self):
        out = self.st(tbl(["A"], [['<a href="x/y-z" title="a-b">go-on</a> <code>k-v</code>']]))
        self.assertIn('<a href="x/y-z" title="a-b"><span class="nb">go-on</span></a>', out)
        self.assertIn('<code><span class="nb">k-v</span></code>', out)

    def test_an_entity_stays_whole(self):
        out = self.st(tbl(["A"], [["x&amp;y &lt;b&gt; a &amp; b"]]))
        self.assertIn('<span class="nb">x&amp;y</span>', out)
        self.assertIn('<span class="nb">&lt;b&gt;</span>', out)
        self.assertNotIn('<span class="nb">&amp;</span>', out)

    def test_an_svg_block_is_unchanged(self):
        svg = "<svg><text>a-b c/d</text><table><tr><td>a-b</td></tr></table></svg>"
        self.assertEqual(self.st(svg), svg)
        out = self.st(svg + tbl(["A"], [["a-b"]]))
        self.assertTrue(out.startswith(svg))
        self.assertIn('<span class="nb">a-b</span>', out[len(svg):])

    def test_a_grid_table_is_unchanged(self):
        g = '<table class="gridtable"><thead><tr><th>a-b</th></tr></thead><tbody><tr><td>c/d</td></tr></tbody></table>'
        self.assertEqual(self.st(g), g)

    def test_minimum_short_cell_prose_and_long_word(self):
        out = self.st(tbl(["Short", "Prose", "Long"], [
            ["ab", "word " * 20, "x" * 40],
            ["abc", "more", "y"]]))
        self.assertIn('<th style="min-width:5ch">Short</th>', out)
        self.assertIn('<th style="min-width:20ch">Prose</th>', out)
        self.assertIn('<th style="min-width:40ch">Long</th>', out)

    def test_a_pname_header_and_an_empty_header_get_no_minimum(self):
        src = ('<table><thead><tr><th class="pname" data-uaf="Writer">Writer</th><th></th></tr></thead>'
               '<tbody><tr><td>a</td><td>b</td></tr></tbody></table>')
        out = self.st(src)
        self.assertNotIn("min-width", out)
        self.assertIn('<th class="pname" data-uaf="Writer">Writer</th>', out)

    def test_an_unknown_phase_raises(self):
        with self.assertRaises(CheckError) as cm:
            self.st(tbl(["Phase"], [["measured"], ["almost"]]))
        self.assertIn("almost", cm.exception.args[0])

    def test_each_phase_gets_its_badge_class(self):
        for ph in ("measured", "built unmeasured", "accepted design", "proposed", "row"):
            out = self.st(tbl(["Phase"], [[ph]]))
            cls = "phase-" + ph.replace(" ", "-")
            self.assertIn(f'<span class="badge {cls}">{ph}</span>', out)

    def test_lane_start_on_changes_and_not_on_the_first_row(self):
        out = self.st(tbl(["Lane", "X"], [["a", "1"], ["a", "2"], ["b", "3"], ["b", "4"], ["a", "5"]]))
        self.assertEqual(out.count('<tr class="lane-start">'), 2)
        self.assertEqual(out.count("<tr>"), 4)  # header row and three body rows
        first = out.index("<td>", out.index("<tbody"))
        self.assertNotIn("lane-start", out[:first])

    def test_no_lane_column_adds_no_class(self):
        self.assertNotIn("lane-start", self.st(tbl(["Name"], [["a"], ["b"]])))

    def test_pname_th_is_untouched(self):
        src = '<table><thead><tr><th class="pname" data-uaf="a-b">a-b</th></tr></thead><tbody><tr><td>x</td></tr></tbody></table>'
        self.assertIn('<th class="pname" data-uaf="a-b">a-b</th>', self.st(src))


class Css(unittest.TestCase):
    def test_print_block_holds_the_table_rules(self):
        css = render_html.CSS
        self.assertIn("@page", css)
        printed = css[css.index("@media print"):]
        self.assertIn(".badge", printed)
        self.assertNotIn("word-break:break-word", css)

    def test_screen_td_th_have_no_overflow_wrap_anywhere(self):
        css = render_html.CSS
        screen = css[:css.index("@media print")]
        for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", screen):
            if "overflow-wrap:anywhere" in m.group(2):
                self.assertNotRegex(m.group(1), r"(^|,)\s*(td|th)\s*(,|$)")


if __name__ == "__main__":
    unittest.main()
