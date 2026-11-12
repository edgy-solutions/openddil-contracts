#!/usr/bin/env python3
"""render_html.py - the architecture views as one self-contained HTML file.

The page is generated from the same source by the same generator as the
markdown profiles: it builds a render_profile.Renderer for each of uaf,
dodaf202 and naf4, takes each view's body from the uaf Renderer's view_text,
and takes names from the others (export_sources, title_for, label, no_target).
It writes no text of its own for a view. The profile toggle in the page changes
names and the grid only.

Usage:
    python docs/arch/tools/render_html.py --out FILE
        --chart PATH --values FILE [--values FILE ...] --release NAME
        [--readiness FILE] [--record FILE] [--slots FILE]
        [--date YYYY-MM-DD] [--mmdc PATH] [--puppeteer-config FILE]
        [--relabel FILE ...]

--chart, --values and --release are required: there is no partial export.
Mermaid diagrams are rendered to inline SVG at build time by mermaid-cli
(--mmdc, default docs/arch/tools/export/node_modules/.bin/mmdc, installed by
`npm ci` in docs/arch/tools/export). --puppeteer-config is handed to it, for a
runner that needs --no-sandbox; Chrome comes from PUPPETEER_EXECUTABLE_PATH.
A diagram that does not render, or whose SVG holds a script, an import or a
remote reference, is exit 1 naming the view and the diagram. The source is
never shown in its place.

Every page carries the chart name and version, a digest of the values files
read, the generation date (--date, default today UTC) and the line that says
this is declared, not measured. The grids are built from APPENDIX-A.md,
parsed as check_views parses it. Markdown goes through markdown-it-py with
raw html off.

The three profiles' data-exchange documents must be equal except for table
header rows; those header cells are the only names the toggle changes in a
view body. Any other difference is exit 1, naming the line.

Exit codes: 0 ok, 1 a check failed, 2 bad input. With the same inputs and
--date, and the same diagram output, the file is byte-stable.
Stdlib, PyYAML and markdown-it-py only (mermaid-cli for the diagrams).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import html
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

import yaml

try:
    from markdown_it import MarkdownIt
except ImportError:  # reported as an input error by main
    MarkdownIt = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adr_sections  # noqa: E402
import capability_phases  # noqa: E402
import check_views  # noqa: E402
import relabel  # noqa: E402
import render_profile as rp  # noqa: E402
from capability_phases import PHASES, CheckError  # noqa: E402
from data_exchange import InputError  # noqa: E402

EXIT_OK, EXIT_CHECK, EXIT_INPUT = 0, 1, 2
ROOT = rp.ROOT
REPO = ROOT.parent.parent
PROFILE_NAMES = rp.PROFILE_NAMES
DECLARED = ("Declared, not measured: this export reads the views, the model and a chart render, "
            "and read no running system.")
CSP = "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; font-src data:"
UAF_ROWS = ["Am", "St", "Op", "Sv", "Ps", "Rs", "Sc", "Pj", "Sd", "Ar", "En", "Me", "Rk", "Rq", "Sm"]
UAF_COLS = ["Mv", "Tx", "Sr", "Cn", "Pr", "St", "Sq", "If", "Pm", "Ct", "Rm", "Tr", "Ov"]
DODAF_ROWS = ["AV", "CV", "DIV", "OV", "PV", "SV", "SvcV", "StdV"]
NAF_ROWS = ["A", "C", "L", "P", "S"]
NAF_COLS = ["1", "2", "3", "4", "5", "6", "7", "8", "r"]
UAF_ID = re.compile(r"^([A-Z][a-z])-([A-Z][a-z])(?:-[A-Za-z]+)?$")
DODAF_ID = re.compile(r"^([A-Za-z]+)-\w+$")
NAF_ID = re.compile(r"^([A-Z])([1-8]|r)(?:-[A-Z](?:[1-8]|r))?$")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|$")
SENTINEL_RE = re.compile(r"<th>zzpname(\d+)zz</th>")
BAD_SVG = [("<script", "a script"), ("@import", "an @import"), ("url(http", "a remote url()"),
           ("Syntax error in text", "a Mermaid syntax error")]
REMOTE_REF_RE = re.compile(r"""\b(?:href|src)\s*=\s*["']?\s*https?:""", re.I)
PROLOG_RE = re.compile(r"^\s*(?:<\?xml[^>]*\?>\s*)?(?:<!DOCTYPE[^>]*>\s*)?", re.I)

Diagram = Callable[[str, str], str]


# --- small helpers -----------------------------------------------------------

def natural_key(s: str) -> list:
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", s)]


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def appendix_ids(root: Path) -> list[list[str]]:
    """Appendix A's rows; a missing or empty table is an input error."""
    got = check_views.appendix_parse(root)
    rows = got[1] if got else []
    rows = [r for r in rows if len(r) == 5]
    if not rows:
        raise InputError("APPENDIX-A.md holds no mapping table")
    return rows


# --- grids -------------------------------------------------------------------

def uaf_cells(rows: list[list[str]]) -> dict[tuple[str, str], list[str]]:
    """(row prefix, column aspect) -> the ids in that cell. Every id is placed or it is an input error."""
    cells: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        ident = r[0].strip()
        m = UAF_ID.match(ident)
        if not m or m.group(1) not in UAF_ROWS or m.group(2) not in UAF_COLS:
            raise InputError(f"Appendix A id '{ident}' has no place in the UAF grid")
        entry = cells.setdefault((m.group(1), m.group(2)), [])
        if ident not in entry:
            entry.append(ident)
    return {k: sorted(v, key=natural_key) for k, v in cells.items()}


def named_ids(rows: list[list[str]], col: int) -> list[str]:
    out: list[str] = []
    for r in rows:
        for x in check_views.appendix_cell(r[col]):
            if x not in out:
                out.append(x)
    return sorted(out, key=natural_key)


def dodaf_cells(ids: list[str]) -> dict[str, list[str]]:
    cells: dict[str, list[str]] = {}
    for x in ids:
        m = DODAF_ID.match(x)
        if not m or m.group(1) not in DODAF_ROWS:
            raise InputError(f"DoDAF id '{x}' has no place in the DoDAF grid")
        cells.setdefault(m.group(1), []).append(x)
    return cells


def naf_cells(ids: list[str]) -> dict[tuple[str, str], list[str]]:
    cells: dict[tuple[str, str], list[str]] = {}
    for x in ids:
        m = NAF_ID.match(x)
        if not m or m.group(1) not in NAF_ROWS:
            raise InputError(f"NAF id '{x}' has no place in the NAF grid")
        cells.setdefault((m.group(1), m.group(2)), []).append(x)
    return cells


def cell_html(ident: str, targets: list[str], names: dict[str, str]) -> str:
    """One id: linked once per source view when filled, muted text when not."""
    if not targets:
        return f'<span class="empty">{esc(ident)}</span>'
    links = []
    for t in targets:
        a = f'<a href="#view-{esc(t)}" title="{esc(names[t])}">{esc(ident)}</a>'
        links.append(a + (f'<small>({esc(t)})</small>' if len(targets) > 1 else ""))
    return '<span class="filled">' + " ".join(links) + "</span>"


def td(items: list[str], ident_to_targets: dict[str, list[str]], names: dict[str, str]) -> str:
    return "<td>" + " ".join(cell_html(i, ident_to_targets.get(i, []), names) for i in items) + "</td>"


def grid_uaf(rows, views: dict, names: dict[str, str], label: str) -> str:
    cells = uaf_cells(rows)
    ids = [i for v in cells.values() for i in v]
    targets = {i: [i] if i in views else [] for i in ids}
    head = "".join(f"<th scope=\"col\">{c}</th>" for c in UAF_COLS)
    body = []
    for rw in UAF_ROWS:
        row = [f'<th scope="row">{rw}</th>']
        for c in UAF_COLS:
            row.append(td(cells[(rw, c)], targets, names) if (rw, c) in cells else "<td></td>")
        body.append("<tr>" + "".join(row) + "</tr>")
    filled = sum(1 for i in ids if targets[i])
    legend = (f"{filled} of {len(ids)} {label} views written. A linked id has a page; "
              "a muted id is named by Appendix A and not written.")
    return grid_wrap("uaf", legend, f"<thead><tr><th></th>{head}</tr></thead><tbody>{''.join(body)}</tbody>")


def grid_wrap(profile: str, legend: str, table: str, extra: str = "") -> str:
    return (f'<div class="grid" id="grid-{profile}" data-grid="{profile}">'
            f'<p class="legend">{esc(legend)}</p><div class="scroll"><table class="gridtable">{table}</table></div>'
            f"{extra}</div>")


def not_exported(r: "rp.Renderer", names: dict[str, str]) -> str:
    rows = []
    for vid, e in r.views.items():
        if (e.get("exports") or {}).get(r.profile):
            continue
        reason = (e.get("no_target") or {}).get(r.profile)
        if not reason:
            raise InputError(f"view {vid} has no exports and no no_target reason for {r.profile}")
        rows.append(f"<tr><td>{esc(e['name'])} ({esc(vid)})</td><td>{esc(reason)}</td></tr>")
    if not rows:
        return ""
    return (f'<h2>Not exported in {esc(r.label)}</h2><div class="scroll"><table><thead><tr><th>View</th>'
            f"<th>Reason</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>")


def grid_selected(r: "rp.Renderer", rows, names: dict[str, str]) -> str:
    sources = r.export_sources()
    col = check_views.APPENDIX_COLUMNS[r.profile]
    ids = named_ids(rows, col)
    for x in sources:
        if x not in ids:
            raise InputError(f"export {x} of {r.profile} is not named in Appendix A")
    if r.profile == "dodaf202":
        cells = dodaf_cells(ids)
        body = "".join(f'<tr><th scope="row">{rw}</th>{td(cells[rw], sources, names)}</tr>'
                       for rw in DODAF_ROWS if rw in cells)
        table = f"<tbody>{body}</tbody>"
    else:
        cells = naf_cells(ids)
        head = "".join(f'<th scope="col">{c}</th>' for c in NAF_COLS)
        body = []
        for rw in NAF_ROWS:
            row = [f'<th scope="row">{rw}</th>']
            for c in NAF_COLS:
                row.append(td(sorted(cells[(rw, c)], key=natural_key), sources, names)
                           if (rw, c) in cells else "<td></td>")
            body.append("<tr>" + "".join(row) + "</tr>")
        table = f"<thead><tr><th></th>{head}</tr></thead><tbody>{''.join(body)}</tbody>"
    filled = sum(1 for i in ids if i in sources)
    legend = (f"{filled} of {len(ids)} {r.label} views written. A linked id is exported from the UAF view "
              "it links to; a muted id is named by Appendix A and not written.")
    return grid_wrap(r.profile, legend, table, style_tables(not_exported(r, names)))


# --- the data-exchange header rows -------------------------------------------

def split_cells(line: str) -> list[str]:
    return check_views.split_row(line)


def join_cells(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def dx_variants(contents: dict[str, str]) -> tuple[str, dict[int, dict[str, str]]]:
    """The uaf document with its profile-varying header cells replaced by markers, and the names behind them.

    The three documents must be equal line for line except table header rows.
    Any other difference is a CheckError naming the line and the profile.
    """
    base = contents["uaf"].split("\n")
    out = list(base)
    cells: dict[int, dict[str, str]] = {}
    index: dict[tuple[int, int], int] = {}
    for prof, text in contents.items():
        if prof == "uaf":
            continue
        other = text.split("\n")
        if len(other) != len(base):
            raise CheckError(f"data exchange: {prof} has {len(other)} lines, uaf has {len(base)}\n")
        for i, (a, b) in enumerate(zip(base, other)):
            if a == b:
                continue
            ok = (a.startswith("|") and b.startswith("|") and i + 1 < len(base)
                  and SEPARATOR_RE.match(base[i + 1].strip()) and other[i + 1] == base[i + 1])
            ca, cb = split_cells(a), split_cells(b)
            if not ok or len(ca) != len(cb):
                raise CheckError(f"data exchange: line {i + 1} differs in {prof} and is not a table header row\n")
            for j, (x, y) in enumerate(zip(ca, cb)):
                if x == y:
                    continue
                k = index.setdefault((i, j), len(index))
                cells.setdefault(k, {"uaf": x})[prof] = y
    for i in sorted({i for (i, _) in index}):
        row = split_cells(base[i])
        for (ii, j), k in index.items():
            if ii == i:
                row[j] = f"zzpname{k}zz"
        out[i] = join_cells(row)
    for k, v in cells.items():
        for prof in contents:
            v.setdefault(prof, v["uaf"])
    return "\n".join(out), cells


def apply_header_cells(body_html: str, cells: dict[int, dict[str, str]]) -> str:
    def sub(m: re.Match) -> str:
        v = cells[int(m.group(1))]
        attrs = " ".join(f'data-{p}="{esc(v[p])}"' for p in PROFILE_NAMES)
        return f'<th class="pname" {attrs}>{esc(v["uaf"])}</th>'
    return SENTINEL_RE.sub(sub, body_html)


# --- markdown ----------------------------------------------------------------

def strip_comments(text: str) -> str:
    """Remove HTML comments outside fences."""
    out: list[str] = []
    run: list[str] = []
    for fence, _, line in rp.split_fences(text):
        if fence:
            if run:
                out.append(COMMENT_RE.sub("", "\n".join(run)))
                run = []
            out.append(line)
        else:
            run.append(line)
    if run:
        out.append(COMMENT_RE.sub("", "\n".join(run)))
    return "\n".join(out)


def repo_relative(href: str, base: Path | None = None) -> str:
    """The repo-relative path a relative link resolves to from `base` (default: the views directory)."""
    path = href.partition("#")[0]
    absolute = ((base or ROOT / "views") / path).resolve()
    try:
        return absolute.relative_to(REPO.resolve()).as_posix() + ("/" if path.endswith("/") else "")
    except ValueError:
        raise InputError(f"link '{href}' resolves outside the repository") from None


ROADMAP_KEY = "roadmap"
ROADMAP_PAGE = "decision-roadmap"


class Decisions:
    """The decision records the export holds a page for: every decisions/ADR-*.md, then the roadmap note."""

    def __init__(self, directory: Path, rules=()):
        self.dir = Path(directory)
        self.rules = list(rules)
        self.replaced = 0
        self.files: dict[str, Path] = {}
        for f in sorted(self.dir.glob("ADR-*.md")):
            m = re.match(r"ADR-\d{4}", f.name)
            if not m:
                continue
            if m.group(0) in self.files:
                raise InputError(f"decisions/ has two files for {m.group(0)}")
            self.files[m.group(0)] = f
        road = self.dir / capability_phases.ROADMAP
        if not road.is_file():
            raise InputError(f"decisions/{capability_phases.ROADMAP} does not exist")
        self.files[ROADMAP_KEY] = road
        self.resolved = {k: f.resolve() for k, f in self.files.items()}
        self.raw = {k: f.read_text(encoding="utf-8").replace("\r\n", "\n") for k, f in self.files.items()}
        self.texts = {}
        for k, t in self.raw.items():
            self.texts[k], n = relabel.apply(t, self.rules)
            self.replaced += n
        self.heads = {k: adr_sections.headings(t) for k, t in self.texts.items()}

    def relabelled(self, text: str, count: bool = False) -> str:
        """Text read from decisions/, with the relabel rules applied; `count` adds the replacements to the total."""
        text, n = relabel.apply(text, self.rules)
        if count:
            self.replaced += n
        return text

    def pick(self, key: str, label: str) -> "adr_sections.Heading":
        """The heading LABEL names in the record as written, as it reads after relabelling."""
        try:
            raw = adr_sections.resolve(self.raw[key], label)
        except LookupError:
            return adr_sections.resolve(self.texts[key], label)  # a label already relabelled
        return self.heads[key][adr_sections.headings(self.raw[key]).index(raw)]

    def shown(self, adr: str, label: str) -> str:
        """The label as the export prints it: a number as it is, a slug as it reads after relabelling."""
        h = self.pick(adr, label)
        return label if label == h.number else h.slug
    def keys(self) -> list[str]:
        return list(self.files)

    @staticmethod
    def page_id(key: str) -> str:
        return ROADMAP_PAGE if key == ROADMAP_KEY else key.lower()

    def key_of(self, target: Path) -> str | None:
        for k, r in self.resolved.items():
            if r == target:
                return k
        return None

    def anchor(self, key: str, heading: "adr_sections.Heading") -> str:
        return adr_sections.anchor_id(self.page_id(key), heading)

    def cite(self, adr: str, label: str) -> str:
        """The anchor id `ADR-NNNN §LABEL` names. LookupError when the record or the section is not there."""
        if adr not in self.files:
            raise LookupError(f"{adr} is not a decision record")
        return self.anchor(adr, self.pick(adr, label))

    def heading(self, adr: str, label: str) -> "adr_sections.Heading":
        return self.pick(adr, label)

    def target(self, key: str, fragment: str) -> str:
        """A link's anchor: the heading its fragment names, else the page. The roadmap note is the page."""
        if key != ROADMAP_KEY:
            for h in self.heads[key]:
                if fragment and h.slug == fragment:
                    return self.anchor(key, h)
        return self.page_id(key)


class Page:
    """Markdown to html for one view, with the link, slot, table and diagram rules applied."""

    def __init__(self, vid: str, views: dict, diagram: Diagram, dec: Decisions | None = None):
        self.vid, self.views, self.diagram, self.dec = vid, views, diagram, dec
        self.base = ROOT / "views"
        self.n = 0
        self.stack: list[tuple[str, str, str]] = []
        self.exceptions = 0
        self.in_h1 = False
        md = MarkdownIt("commonmark", {"html": False}).enable("table")
        md.renderer.rules["fence"] = self.fence
        md.renderer.rules["text"] = self.text
        md.renderer.rules["link_open"] = self.link_open
        md.renderer.rules["link_close"] = self.link_close
        md.renderer.rules["image"] = self.image
        md.renderer.rules["heading_open"] = self.heading_open
        md.renderer.rules["heading_close"] = self.heading_close
        md.renderer.rules["table_open"] = lambda t, i, o, e: '<div class="scroll"><table>\n'
        md.renderer.rules["table_close"] = lambda t, i, o, e: "</table></div>\n"
        self.md = md

    def fence(self, tokens, idx, options, env) -> str:
        tok = tokens[idx]
        lang = tok.info.strip().split(None, 1)[0].lower() if tok.info.strip() else ""
        if lang == "mermaid":
            self.n += 1
            svg = self.diagram(tok.content, f"mmd-{self.vid}-{self.n}")
            return f'<figure class="diagram" data-diagram="{self.n}">{svg}</figure>\n'
        cls = f' class="language-{esc(lang)}"' if lang else ""
        return f'<div class="scroll"><pre><code{cls}>{esc(tok.content)}</code></pre></div>\n'

    def heading_open(self, tokens, idx, options, env) -> str:
        self.in_h1 = tokens[idx].tag == "h1"
        return self.md.renderer.renderToken(tokens, idx, options, env)

    def heading_close(self, tokens, idx, options, env) -> str:
        self.in_h1 = False
        return self.md.renderer.renderToken(tokens, idx, options, env)

    def text(self, tokens, idx, options, env) -> str:
        parts = rp.SLOT_RE.split(tokens[idx].content)
        out = []
        for k, p in enumerate(parts):
            out.append(f'<span class="slot">{{{{slot:{esc(p)}}}}}</span>' if k % 2 else self.cited(p))
        return "".join(out)

    def cited(self, text: str) -> str:
        """Escaped text, with each `ADR-NNNN §LABEL` a link to its section. Not inside a link or an h1."""
        if self.dec is None or self.stack or self.in_h1:
            return esc(text)
        out, at = [], 0
        for m in adr_sections.CITATION_IN_TEXT_RE.finditer(text):
            out.append(esc(text[at:m.start()]))
            try:
                anchor = self.dec.cite(m.group(1), m.group(2))
            except LookupError as e:
                raise CheckError(f"{self.vid}: {m.group(0)}: {e.args[0]}\n") from None
            out.append(f'<a href="#{esc(anchor)}">{esc(m.group(1))} §{esc(self.dec.shown(m.group(1), m.group(2)))}</a>')
            at = m.end()
        out.append(esc(text[at:]))
        return "".join(out)

    @staticmethod
    def link_text(tokens, idx) -> str:
        parts = []
        for t in tokens[idx + 1:]:
            if t.type == "link_close":
                break
            if t.type in ("text", "code_inline"):
                parts.append(t.content)
        return "".join(parts).strip()

    def decision_link(self, key: str, fragment: str, text: str) -> str:
        """The anchor a link to decision record `key` becomes."""
        if key == ROADMAP_KEY:
            return ROADMAP_PAGE
        m = adr_sections.CITATION_RE.match(text)
        if m:
            if m.group(1) != key:
                raise CheckError(f"{self.vid}: the link text {text!r} cites {m.group(1)} and links {key}\n")
            try:
                return self.dec.cite(key, m.group(2))
            except LookupError as e:
                raise CheckError(f"{self.vid}: {text}: {e.args[0]}\n") from None
        return self.dec.target(key, fragment)

    def link_open(self, tokens, idx, options, env) -> str:
        tok = tokens[idx]
        href = tok.attrGet("href") or ""
        if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):
            self.stack.append(("url", href, tok.markup))
            return ""
        if href.startswith("#") or not href:
            self.stack.append(("ref", "", tok.markup))
            return '<span class="ref">'
        path, _, fragment = href.partition("#")
        target = (self.base / path).resolve()
        for vid, e in self.views.items():
            if target == (ROOT / e["file"]).resolve():
                self.stack.append(("view", vid, tok.markup))
                return f'<a href="#view-{esc(vid)}">'
        key = self.dec.key_of(target) if self.dec else None
        if key:
            anchor = self.decision_link(key, fragment, self.link_text(tokens, idx))
            self.stack.append(("view", key, tok.markup))
            return f'<a href="#{esc(anchor)}">'
        self.stack.append(("ref", "", tok.markup))
        return f'<span class="ref" title="{esc(repo_relative(href, self.base))}">'

    def link_close(self, tokens, idx, options, env) -> str:
        kind, value, markup = self.stack.pop()
        if kind == "view":
            return "</a>"
        if kind == "ref":
            return "</span>"
        return "" if markup == "autolink" else f" ({esc(value)})"

    @staticmethod
    def image(tokens, idx, options, env) -> str:
        return esc(tokens[idx].content)

    def render(self, text: str) -> str:
        tokens = self.md.parse(strip_comments(text), {})
        out: list = []
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if (t.type == "heading_close" and i + 1 < len(tokens) and tokens[i + 1].type == "table_open"
                    and tokens[i - 1].content.startswith("Exception")):
                j = i + 1
                while tokens[j].type != "table_close":
                    j += 1
                rows = sum(1 for k in tokens[i + 1:j] if k.type == "tr_open") - 1
                from markdown_it.token import Token
                opener = Token("html_block", "", 0)
                opener.content = (f'<details class="exceptions"><summary>{esc(tokens[i - 1].content)}: '
                                  f"{rows} row{'s' if rows != 1 else ''}</summary>\n")
                closer = Token("html_block", "", 0)
                closer.content = "</details>\n"
                out += [t, opener] + tokens[i + 1:j + 1] + [closer]
                self.exceptions += 1
                i = j + 1
                continue
            out.append(t)
            i += 1
        return self.md.renderer.render(out, self.md.options, {})


class DecisionPage(Page):
    """One decision record's body: links to the other records and the views, a heading id per h2 to h4."""

    def __init__(self, key: str, views: dict, dec: Decisions):
        super().__init__(key, views, lambda source, svg_id: "", dec)
        self.key = key
        self.base = dec.dir
        self.ids = [dec.anchor(key, h) for h in dec.heads[key]]
        self.seen = 0

    def fence(self, tokens, idx, options, env) -> str:
        tok = tokens[idx]
        lang = tok.info.strip().split(None, 1)[0].lower() if tok.info.strip() else ""
        cls = f' class="language-{esc(lang)}"' if lang and lang != "mermaid" else ""
        return f'<div class="scroll"><pre><code{cls}>{esc(tok.content)}</code></pre></div>\n'

    def heading_open(self, tokens, idx, options, env) -> str:
        tag = tokens[idx].tag
        if tag in ("h2", "h3", "h4"):
            if self.seen >= len(self.ids):
                raise CheckError(f"{self.key}: the page has more h2 to h4 headings than adr_sections reads\n")
            anchor = self.ids[self.seen]
            self.seen += 1
            return f'<{tag} id="{esc(anchor)}">'
        return f"<{tag}>"

    def heading_close(self, tokens, idx, options, env) -> str:
        return f"</{tokens[idx].tag}>\n"

    def cited(self, text: str) -> str:
        return esc(text)

    def link_open(self, tokens, idx, options, env) -> str:
        tok = tokens[idx]
        href = tok.attrGet("href") or ""
        if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):
            self.stack.append(("url", href, tok.markup))
            return ""
        if href.startswith("#") or not href:
            self.stack.append(("ref", "", tok.markup))
            return '<span class="ref">'
        path, _, fragment = href.partition("#")
        target = (self.base / path).resolve()
        key = self.dec.key_of(target)
        if key:
            self.stack.append(("view", key, tok.markup))
            return f'<a href="#{esc(self.dec.target(key, fragment))}">'
        for vid, e in self.views.items():
            if target == (ROOT / e["file"]).resolve():
                self.stack.append(("view", vid, tok.markup))
                return f'<a href="#view-{esc(vid)}">'
        self.stack.append(("ref", "", tok.markup))
        return f'<span class="ref" title="{esc(repo_relative(href, self.base))}">'

    def render(self, text: str) -> str:
        html_text = self.md.renderer.render(self.md.parse(strip_comments(text), {}), self.md.options, {})
        if self.seen != len(self.ids):
            raise CheckError(f"{self.key}: the page has {self.seen} h2 to h4 headings, adr_sections reads "
                             f"{len(self.ids)}\n")
        return html_text


# --- diagrams ----------------------------------------------------------------

def default_mmdc() -> str:
    name = "mmdc.cmd" if sys.platform == "win32" else "mmdc"
    return str(rp.TOOLS / "export" / "node_modules" / ".bin" / name)


def make_mmdc(mmdc: str, puppeteer_config: str | None) -> Diagram:
    """A Diagram that runs mermaid-cli. A missing binary is an input error; a failed run is a CheckError."""
    if not Path(mmdc).is_file():
        raise InputError(f"mermaid-cli not found at {mmdc}; run `npm ci` in docs/arch/tools/export or pass --mmdc")
    if puppeteer_config and not Path(puppeteer_config).is_file():
        raise InputError(f"cannot read {puppeteer_config}")

    def run(source: str, svg_id: str) -> str:
        with tempfile.TemporaryDirectory() as d:
            src, out, cfg = Path(d) / "in.mmd", Path(d) / "out.svg", Path(d) / "mermaid.json"
            src.write_text(source, encoding="utf-8", newline="\n")
            cfg.write_text(json.dumps({"theme": "neutral", "securityLevel": "strict"}), encoding="utf-8")
            cmd = [mmdc, "-i", str(src), "-o", str(out), "--svgId", svg_id, "-b", "transparent", "-c", str(cfg)]
            if puppeteer_config:
                cmd += ["-p", puppeteer_config]
            try:
                p = subprocess.run(cmd, capture_output=True, timeout=180)
            except (OSError, subprocess.TimeoutExpired) as e:
                raise CheckError(f"mermaid-cli did not run: {e}") from None
            if p.returncode != 0 or not out.is_file():
                tail = (p.stderr or p.stdout).decode("utf-8", "replace").strip().splitlines()[-1:]
                raise CheckError(f"mermaid-cli exit {p.returncode}: {' '.join(tail)}")
            return out.read_text(encoding="utf-8")
    return run


def clean_svg(svg: str) -> str:
    svg = PROLOG_RE.sub("", svg).strip()
    if not svg.startswith("<svg"):
        raise CheckError("the diagram result is not an svg")
    for needle, what in BAD_SVG:
        if needle in svg:
            raise CheckError(f"the diagram result holds {what}")
    if REMOTE_REF_RE.search(svg):
        raise CheckError("the diagram result holds a remote href or src")
    return svg


def checked(diagram: Diagram, vid: str) -> Diagram:
    n = [0]

    def run(source: str, svg_id: str) -> str:
        n[0] += 1
        try:
            return clean_svg(diagram(source, svg_id))
        except CheckError as e:
            raise CheckError(f"view {vid} diagram {n[0]}: {e.args[0].rstrip()}\n") from None
    return run


# --- the declarations page ---------------------------------------------------

DECLARATIONS_TITLE = "What your deployment declares to fill these views"


def declarations_md(views: dict) -> str:
    """The declarations page as markdown, built from INVENTORY.md's slot table and slots.yaml.

    One row per slot that no declared artefact fills yet: what it fills, the
    declaration and the artefact INVENTORY names for it, and the views that show it."""
    lines = check_views.outside_fences((ROOT / "INVENTORY.md").read_text(encoding="utf-8"))
    at = [i for i, ln in enumerate(lines) if ln.strip() == check_views.SLOT_INVENTORY_HEADER]
    if len(at) != 1:
        raise InputError(f"INVENTORY.md has {len(at)} slot tables, expected one")
    _, rows = check_views.table_after(lines, at[0])
    registry = (rp.load_yaml(ROOT / "slots.yaml") or {}).get("slots") or {}
    shown: dict[str, list[str]] = {}
    for vid, e in views.items():
        for name in rp.SLOT_RE.findall((ROOT / e["file"]).read_text(encoding="utf-8")):
            if vid not in shown.setdefault(name, []):
                shown[name].append(vid)
    body = []
    for r in rows:
        if len(r) != 3:
            raise InputError(f"INVENTORY.md's slot table has a row of {len(r)} cells, expected 3")
        name = r[0].strip("` ")
        if name not in registry:
            raise InputError(f"INVENTORY.md's slot table names {name}, which slots.yaml does not hold")
        if not shown.get(name):
            raise InputError(f"INVENTORY.md's slot table names {name}, which no view shows")
        fills = str((registry[name] or {}).get("fills") or "").strip()
        where = ", ".join(f"[{v}]({Path(views[v]['file']).name})" for v in shown[name])
        body.append(f"| `{name}` | {fills} | {r[1]} | {r[2]} | {where} |")
    if not body:
        raise InputError("INVENTORY.md's slot table has no rows")
    return "\n".join([
        f"These views mark {len(body)} facts about a deployment with a slot that no declared artefact fills yet. "
        "The framework cannot know them. Each row names the declaration a deployment would write, the artefact "
        "it would live in, and the views that show the slot. Until it is written, the slot stays marked in "
        "each of those views. None of these declarations exists yet.",
        "",
        "| Slot | What it fills | Declaration that would fill it | Artefact | Shown in |",
        "|---|---|---|---|---|",
        *body,
        "",
        "Built from [INVENTORY.md](../INVENTORY.md) and [slots.yaml](../slots.yaml) when the export is rendered.",
        "",
    ])


# --- provenance --------------------------------------------------------------

def values_digest(values: list[str]) -> str:
    h = hashlib.sha256()
    for v in values:
        p = Path(v)
        try:
            data = p.read_bytes()
        except OSError as e:
            raise InputError(f"cannot read {v}: {e}")
        h.update(p.name.encode("utf-8") + b"\0" + data.replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def provenance(a: argparse.Namespace, date: str) -> str:
    chart = rp.load_yaml(Path(a.chart) / "Chart.yaml") or {}
    name, version = chart.get("name"), chart.get("version")
    if not name or version is None:
        raise InputError(f"{a.chart}/Chart.yaml names no chart name and version")
    files = ", ".join(Path(v).name for v in a.values)
    return ('<div class="provenance" data-provenance>'
            f'<p data-prov="chart">Chart: {esc(str(name))} {esc(str(version))}</p>'
            f'<p data-prov="digest">Bundle digest: sha256:{values_digest(a.values)} '
            f'<span class="note">of the values files read, in order: {esc(files)}</span></p>'
            f'<p data-prov="date">Generated: {esc(date)}</p>'
            f'<p data-prov="declared">{esc(DECLARED)}</p></div>')


PROSE_MIN_CH = 20
NB_PLAIN = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.,:;'()")
SVG_RE = re.compile(r"(<svg\b.*?</svg>)", re.S)
TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", re.S)
ROW_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<(th|td)\b([^>]*)>(.*?)</\1>", re.S)
TAG_RE = re.compile(r"(<[^>]*>)")


def plain(cell: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", "", cell)).split())


def hold_words(content: str) -> str:
    """Wrap each token with a hyphen, slash or similar in a nowrap span; the text is unchanged."""
    def tok(m: re.Match) -> str:
        t = html.unescape(m.group(0))
        if len(t) > 1 and any(c not in NB_PLAIN for c in t):
            return f'<span class="nb">{m.group(0)}</span>'
        return m.group(0)
    parts = TAG_RE.split(content)
    return "".join(p if i % 2 else re.sub(r"\S+", tok, p) for i, p in enumerate(parts))


def style_table(t: str, view: bool = True) -> str:
    split = t.find("<tbody")
    rows = list(ROW_RE.finditer(t))
    if not rows:
        return t
    head_starts = {m.start() for m in rows if (m.start() < split if split >= 0 else m is rows[0])}
    grid = [[(c.group(1), c.group(2), c.group(3)) for c in CELL_RE.finditer(m.group(1))] for m in rows]
    ncols = max(len(r) for r in grid)
    head_texts = [plain(c[2]) for c in grid[0]] if rows[0].start() in head_starts else []
    lane_col = head_texts.index("Lane") if view and "Lane" in head_texts else -1
    phase_col = head_texts.index("Phase") if view and "Phase" in head_texts else -1
    mins: dict[int, int] = {}
    for col in range(ncols):
        words, cell = 0, 0
        for r in grid:
            if col < len(r):
                text = plain(r[col][2])
                cell = max(cell, len(text))
                words = max([words] + [len(w) for w in text.split()])
        mins[col] = min(cell, max(words, PROSE_MIN_CH))
    state = {"row": -1, "prev": None, "body": 0}

    def do_row(m: re.Match) -> str:
        state["row"] += 1
        cells = grid[state["row"]]
        is_head = m.start() in head_starts
        out = []
        for col, (tag, attrs, content) in enumerate(cells):
            pname = "pname" in attrs
            text = plain(content)
            badge = False
            if is_head:
                if not pname and text:
                    attrs += f' style="min-width:{mins[col]}ch"'
            elif col == phase_col:
                if text not in PHASES:
                    raise CheckError(f"phase column: {text!r} is not one of {', '.join(PHASES)}\n")
                content = f'<span class="badge phase-{text.replace(" ", "-")}">{text}</span>'
                badge = True
            if not pname and not badge:
                content = hold_words(content)
            out.append(f"<{tag}{attrs}>{content}</{tag}>")
        cls = ""
        if not is_head:
            if lane_col >= 0 and lane_col < len(cells):
                lane = plain(cells[lane_col][2])
                if state["body"] > 0 and lane != state["prev"]:
                    cls = ' class="lane-start"'
                state["prev"] = lane
            state["body"] += 1
        tr_open = m.group(0)[: m.group(0).index(">") + 1]
        if cls:
            tr_open = tr_open[:-1] + cls + ">"
        return tr_open + "".join(out) + "</tr>"

    return ROW_RE.sub(do_row, t)


def style_tables(body_html: str, view: bool = True) -> str:
    """Table styling the CSS cannot do alone: words held whole, column minimums, phase badges, lane rules.
    Call it after apply_header_cells. A decision page passes view=False: no phase badge or lane rule. Text inside svg blocks and in grid tables is left alone."""
    def one(m: re.Match) -> str:
        t = m.group(0)
        return t if "gridtable" in t[: t.index(">")] else style_table(t, view)
    parts = SVG_RE.split(body_html)
    return "".join(p if i % 2 else TABLE_RE.sub(one, p) for i, p in enumerate(parts))


# --- the page ----------------------------------------------------------------

CSS = """
:root{--fg:#1d2430;--muted:#6b7480;--line:#d5dae1;--bg:#fff;--soft:#f3f5f8;--accent:#0b5cad;
--head:#1f3a5f;--zebra:#f3f5f8;--filled:#d9e8fb;
--m-bg:#d6f0e0;--m-fg:#0f5132;--b-bg:#d9e8fb;--b-fg:#0b4080;--a-bg:#fdecc8;--a-fg:#7a4d00;
--p-bg:#f0e1f7;--p-fg:#5b2a78;--r-bg:#e6e8eb;--r-fg:#3a424d}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--fg);background:var(--bg)}
a{color:var(--accent)}
.bar{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;padding:8px 16px;background:var(--soft);border-bottom:1px solid var(--line)}
.bar .sys{font-weight:600}
.bar .profiles{display:flex;gap:4px}
.bar button{font:inherit;padding:4px 10px;border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:4px;cursor:pointer}
.bar button[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#fff}
.bar input{font:inherit;padding:4px 8px;border:1px solid var(--line);border-radius:4px;min-width:0;flex:1 1 160px}
#results{padding:8px 16px;background:var(--soft);border-bottom:1px solid var(--line)}
#results[hidden]{display:none}
#results li{margin:6px 0}
#results .snip{color:var(--muted);display:block;font-size:14px}
main{padding:0 16px 48px}
main p,main ul,main ol,main h1,main h2,main h3,main nav{max-width:1100px}
.page{display:none}
.page:target,.page:has(:target){display:block}
body:not(:has(.page:target,.page :target)) #front{display:block}
h1{font-size:1.5rem;line-height:1.25;overflow-wrap:anywhere}
h2{font-size:1.25rem;margin-top:2rem}
h3{font-size:1.1rem}
p,li,summary{overflow-wrap:anywhere}
.scroll{overflow-x:auto;max-width:100%;margin:1em 0}
.scroll table{width:100%}
.nb,th.pname{white-space:nowrap}
table{border-collapse:collapse;font-size:14px}
th,td{border:1px solid var(--line);padding:4px 8px;vertical-align:top;text-align:left}
thead th{background:var(--head);color:#fff}
tbody th{background:var(--soft)}
tbody tr:nth-child(even)>*{background:var(--zebra)}
tr.lane-start>*{border-top:2px solid var(--head)}
.pending{display:inline-block;margin-left:8px;padding:0 8px;border:1px dashed currentColor;border-radius:10px;font-size:13px;font-weight:600}
.badge{display:inline-block;white-space:nowrap;padding:0 8px;border-radius:10px;font-size:13px;font-weight:600}
.phase-measured{background:var(--m-bg);color:var(--m-fg)}
.phase-built-unmeasured{background:var(--b-bg);color:var(--b-fg)}
.phase-accepted-design{background:var(--a-bg);color:var(--a-fg)}
.phase-proposed{background:var(--p-bg);color:var(--p-fg)}
.phase-row{background:var(--r-bg);color:var(--r-fg)}
pre{margin:0;padding:12px;background:var(--soft);font-size:13px;line-height:1.4}
code{font-family:ui-monospace,Consolas,monospace;font-size:.92em}
figure.diagram{margin:1em 0;padding:8px;border:1px solid var(--line);overflow-x:auto;background:#fff}
figure.diagram svg{max-width:100%;height:auto}
details.exceptions{margin:1em 0}
details.exceptions summary{cursor:pointer;font-weight:600}
.slot,.empty{color:var(--muted)}
.slot{font-family:ui-monospace,Consolas,monospace;font-size:.92em}
.ref{border-bottom:1px dotted var(--muted)}
.grid{display:none}
html[data-profile="uaf"] #grid-uaf,html[data-profile="dodaf202"] #grid-dodaf202,html[data-profile="naf4"] #grid-naf4{display:block}
.gridtable td{min-width:3.5em}
.gridtable tbody tr>*{border-top:2px solid var(--head)}
.gridtable td:has(.filled){background:var(--filled)}
.gridtable td span{white-space:nowrap;margin-right:6px}
.gridtable small{color:var(--muted);margin-left:2px}
.legend{color:var(--muted);font-size:14px}
.profile-only{display:none;color:var(--muted)}
html[data-profile="dodaf202"] .profile-only[data-for="dodaf202"],html[data-profile="naf4"] .profile-only[data-for="naf4"]{display:block}
.attribution{color:var(--muted);margin-top:0}
.provenance{margin-top:2.5rem;padding-top:8px;border-top:1px solid var(--line);font-size:13px;color:var(--muted)}
.provenance p{margin:2px 0}
.provenance .note{display:block}
nav.views ul,nav.capabilities ul,nav.decisions ul{columns:2 280px;padding-left:1.2em}
.stamp,.derived,.cap-group,.cap-increment,.relabel{color:var(--muted);margin:4px 0}
.stamp{font-size:13px}
@page{size:landscape}
@media (max-width:600px){h1{font-size:1.3rem}.bar{gap:6px 8px}}
@media print{
  .bar,#results{display:none!important}
  body{font-size:11pt}
  main{max-width:none;padding:0}
  .page,.page:target,.page:has(:target),body:not(:has(.page:target,.page :target)) #front{display:block}
  .page{break-before:page}
  .page:first-of-type{break-before:auto}
  .scroll{overflow:visible}
  table{font-size:8pt;width:100%}
  thead th{background:none;color:inherit;border-bottom:2px solid var(--head)}
  tbody tr:nth-child(even)>*,tbody th,.gridtable td:has(.filled){background:none}
  .badge,.phase-measured,.phase-built-unmeasured,.phase-accepted-design,.phase-proposed,.phase-row{background:none;color:inherit;padding:0;border-radius:0;font-weight:600}
  th:nth-child(n+4){min-width:0!important}
  .decision th{min-width:0!important}
  .decision td:nth-child(n+4),.decision th:nth-child(n+4){overflow-wrap:anywhere}
  .decision td:nth-child(n+4) .nb{white-space:normal}
  table:has(thead th:nth-child(8)) td:nth-child(n+4),table:has(thead th:nth-child(8)) th:nth-child(n+4){overflow-wrap:anywhere}
  table:has(thead th:nth-child(8)) td:nth-child(n+4) .nb,table:has(thead th:nth-child(8)) th:nth-child(n+4) .nb{white-space:normal}
  pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:8.5pt}
  figure.diagram{overflow:visible;break-inside:avoid}
  svg{max-width:100%;height:auto}
  a{color:inherit;text-decoration:none}
}
""".strip()

JS = """
(function () {
  var root = document.documentElement;
  var KEY = {uaf: "uaf", dodaf202: "dodaf202", naf4: "naf4"};
  function setProfile(p) {
    if (!KEY[p]) return;
    root.setAttribute("data-profile", p);
    document.querySelectorAll(".pname").forEach(function (e) {
      var v = e.getAttribute("data-" + p);
      if (v !== null) e.textContent = v;
    });
    document.title = root.getAttribute("data-title-" + p) || document.title;
    document.querySelectorAll("[data-profile-btn]").forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-profile-btn") === p ? "true" : "false");
    });
  }
  document.querySelectorAll("[data-profile-btn]").forEach(function (b) {
    b.addEventListener("click", function () { setProfile(b.getAttribute("data-profile-btn")); });
  });

  var input = document.getElementById("q");
  var panel = document.getElementById("results");
  function pageText(page) {
    var c = page.cloneNode(true);
    var p = root.getAttribute("data-profile");
    c.querySelectorAll("style,script,.profile-only").forEach(function (e) { e.remove(); });
    c.querySelectorAll(".grid").forEach(function (g) { if (g.getAttribute("data-grid") !== p) g.remove(); });
    return c.textContent.replace(/\\s+/g, " ");
  }
  function pageName(page) {
    var h = page.querySelector("h1");
    return h ? h.textContent : page.id;
  }
  function clearSearch() {
    input.value = "";
    panel.hidden = true;
    panel.textContent = "";
  }
  function search() {
    var q = input.value.trim().toLowerCase();
    panel.textContent = "";
    if (q.length < 2) { panel.hidden = true; return; }
    var list = document.createElement("ul");
    var total = 0;
    document.querySelectorAll(".page").forEach(function (page) {
      var text = pageText(page), low = text.toLowerCase();
      var at = low.indexOf(q), n = 0;
      if (at < 0) return;
      var first = at;
      while (at >= 0) { n++; at = low.indexOf(q, at + q.length); }
      total++;
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = "#" + page.id;
      a.textContent = pageName(page);
      var count = document.createElement("span");
      count.textContent = " (" + n + (n === 1 ? " match)" : " matches)");
      var snip = document.createElement("span");
      snip.className = "snip";
      snip.textContent = (first > 40 ? "\\u2026" : "") + text.slice(Math.max(0, first - 40), first + q.length + 80);
      li.appendChild(a); li.appendChild(count); li.appendChild(snip);
      list.appendChild(li);
    });
    var head = document.createElement("p");
    head.textContent = total + (total === 1 ? " page matches" : " pages match");
    panel.appendChild(head);
    panel.appendChild(list);
    panel.hidden = false;
  }
  input.addEventListener("input", search);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") clearSearch(); });
  panel.addEventListener("click", function (e) { if (e.target.tagName === "A") clearSearch(); });

  var saved = [];
  window.addEventListener("beforeprint", function () {
    saved = [];
    document.querySelectorAll("details").forEach(function (d) { saved.push([d, d.open]); d.open = true; });
  });
  window.addEventListener("afterprint", function () {
    saved.forEach(function (s) { s[0].open = s[1]; });
    saved = [];
  });
})();
""".strip()


# --- capability and decision pages -------------------------------------------

CAP_NAME_VIEWS = ("St-Tx", "St-Rm-P")
STAMP_DIRTY = " (working tree differs from this commit)"
SHALLOW_MESSAGE = "the repository is a shallow clone: decision stamps need full history (fetch-depth: 0)"


def git_out(*args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, encoding="utf-8")
    except OSError as e:
        raise InputError(f"git cannot run: {e.strerror or e}") from None
    if r.returncode != 0:
        raise InputError(f"git {' '.join(args)} failed: {r.stderr.strip() or r.returncode}")
    return r.stdout


def check_history() -> None:
    if git_out("rev-parse", "--is-shallow-repository").strip() == "true":
        raise InputError(SHALLOW_MESSAGE)


def decision_stamp(path: Path) -> str:
    """`Commit SHORT7, YYYY-MM-DD: decisions/FILE`, from the last commit that touched the file."""
    rel = Path(path).resolve().relative_to(REPO.resolve()).as_posix()
    line = git_out("log", "-1", "--format=%h%x09%cs", "--", rel).strip()
    sha, _, day = line.partition("\t")
    if not sha or not day:
        raise InputError(f"git has no commit that touched {rel}")
    dirty = STAMP_DIRTY if git_out("status", "--porcelain", "--", rel).strip() else ""
    return f"Commit {sha[:7]}, {day}: decisions/{Path(path).name}{dirty}"


def split_title(text: str) -> tuple[str | None, str]:
    """The first `# ` line outside fences, and the text without it."""
    lines = text.split("\n")
    for i, (fence, _, line) in enumerate(rp.split_fences(text)):
        if not fence and line.startswith("# "):
            return line[2:].strip(), "\n".join(lines[:i] + lines[i + 1:])
    return None, text


def link_capability_names(vid: str, body_html: str, cap_names: list[str]) -> str:
    """Wrap each capability name in the first cell of each body row of every table in a link to its page."""
    pat = re.compile(r"\b(" + "|".join(sorted((re.escape(n) for n in cap_names), key=len, reverse=True)) + r")\b")
    linked: set[str] = set()

    def sub(m: re.Match) -> str:
        linked.add(m.group(1))
        return f'<a href="#cap-{m.group(1)}">{m.group(1)}</a>'

    def cell(m: re.Match) -> str:
        depth, out = 0, []
        for i, part in enumerate(TAG_RE.split(m.group(3))):
            if i % 2:
                if re.match(r"<a\b", part):
                    depth += 1
                elif part.startswith("</a"):
                    depth -= 1
                out.append(part)
            else:
                out.append(part if depth else pat.sub(sub, part))
        return f"<{m.group(1)}{m.group(2)}>{''.join(out)}</{m.group(1)}>"

    def row(m: re.Match) -> str:
        first = CELL_RE.search(m.group(0))
        return m.group(0) if not first else m.group(0)[:first.start()] + cell(first) + m.group(0)[first.end():]

    def table(m: re.Match) -> str:
        t = m.group(0)
        split = t.find("<tbody")
        return t if split < 0 else t[:split] + ROW_RE.sub(row, t[split:])

    out = TABLE_RE.sub(table, body_html)
    missing = [n for n in cap_names if n not in linked]
    if missing:
        raise CheckError(f"view {vid}: no table row links {', '.join(missing)} to its capability page\n")
    return out


def status_word(lead: str | None) -> str:
    if not lead:
        return "no status"
    for w in ("accepted", "proposed"):
        if lead.startswith(w):
            return w.capitalize()
    return lead.split()[0].capitalize()


def capability_pages(a: argparse.Namespace, uaf: "rp.Renderer", views: dict, names: dict, dec: Decisions,
                     prov: str) -> tuple[list[str], list[str]]:
    """(page sections, nav items): one page per capability in the model, in model order."""
    record = capability_phases.load_record(getattr(a, "record", None) or ROOT / "capability-record.yaml")
    cmap = capability_phases.model_capabilities(uaf.sysml)
    ddir = dec.dir
    cdir = Path(a.chart)
    rpath = Path(a.readiness) if getattr(a, "readiness", None) else cdir.parent / "scripts" / "RECORDING-READINESS.md"
    try:
        readiness = rpath.read_text(encoding="utf-8")
    except OSError as e:
        raise InputError(f"cannot read the readiness doc {rpath}: {e.strerror or e}; pass --readiness")
    evidence = capability_phases.evidence_cells(record, readiness)
    statuses = capability_phases.statuses_of(record, ddir)
    road_rows = capability_phases.roadmap_rows(dec.relabelled(capability_phases.read_text(ddir / capability_phases.ROADMAP) or ""))
    register: dict[str, tuple[str, str]] = {}
    for f in (capability_phases.FOLLOW_UPS, capability_phases.DEBT):
        text = dec.relabelled(capability_phases.read_text(ddir / f) or "", count=True)
        for k, v in capability_phases.register_subjects(text).items():
            register.setdefault(k, v)
    sources = {vid: strip_comments((ROOT / e["file"]).read_text(encoding="utf-8")) for vid, e in views.items()}

    def link(name: str, adr: str, label: str) -> str:
        try:
            return f'<a href="#{esc(dec.cite(adr, label))}">{esc(adr)} §{esc(dec.shown(adr, label))}</a>'
        except LookupError as e:
            raise CheckError(f"{name}: {adr} §{label}: {e.args[0]}\n") from None

    sections, nav = [], []
    for name in cmap:
        cap = record["capabilities"].get(name) or {}
        phase = capability_phases.phase_of(cap, statuses)
        if phase is None:
            raise CheckError(f"{name}: the record gives it no phase\n")
        label = capability_phases.increment_label(cap, road_rows)
        lane = str(record["lanes"][cmap[name]])
        head = f'<h1>{esc(name)}</h1><p class="cap-group">Group: {esc(lane)}</p>'
        if label:
            head += f'<p class="cap-increment">Increment: {esc(label)}</p>'
        source = capability_phases.derived_citations(cap) or capability_phases.record_citations(cap)
        written = ", ".join(link(name, adr, lab) for adr, lab in source)
        if source:
            line = f"Written from {written}. The decision records are the authority; this description is not their text."
        else:
            line = ("Written from the pending sources below. No decision record decides it yet; "
                    "this description is not their text.")
        what = (f'<h2>What it is</h2><p data-what>{esc(" ".join(str(cap.get("description") or "").split()))}</p>'
                f'<p class="derived" data-derived>{line}</p>')
        ev = evidence.get(name)
        ev_html = ("<ul>" + "".join(f"<li>{esc(x)}</li>" for x in ev) + "</ul>" if ev else
                   "<p>Not measured: the readiness doc has no entry for this capability.</p>")
        built = list(dict.fromkeys(f"templates/{b['template']}" for b in cap.get("built") or []))
        pend = ' <span class="pending" data-pending>decision pending</span>' if cap.get("pending") else ""
        evid = (f'<h2>Phase</h2><p><span class="badge phase-{phase.replace(" ", "-")}">{esc(phase)}</span>{pend}</p>'
                f'<h2>Evidence</h2>{ev_html}<p>Built: {esc(", ".join(built) or "-")}</p>')
        items = []
        for adr, lab in capability_phases.record_citations(cap):
            h = dec.heading(adr, lab)
            items.append(f"<li>{link(name, adr, lab)} {esc(h.text)} ({esc(status_word(statuses.get(adr)))})</li>")
        for s in capability_phases.still_open(cap):
            adr, lab = adr_sections.parse_citation(s["adr"])
            items.append(f"<li>{link(name, adr, lab)} names it still open: {esc(str(s['says']))}</li>")
        for text in cap.get("pending") or []:
            items.append(f"<li>Decision pending: {esc(str(text))}</li>")
        decs = f'<h2>Decisions</h2><ul>{"".join(items) or "<li>-</li>"}</ul>'
        sev = cap.get("severed")
        if sev and sev != capability_phases.NOT_STATED:
            sadr, slab = adr_sections.parse_citation(sev)
            sev_html = (f'<p data-severed>Stated in {link(name, sadr, slab)} '
                        f'{esc(dec.heading(sadr, slab).text)}.</p>')
        else:
            sv = [r for r in cap.get("rows") or [] if str(r).startswith("SV-")]
            subj = register.get(sv[0], ("", ""))[0] if sv else ""
            sev_html = ('<p data-severed>Not stated by a decision record. Open row: '
                        f'{esc(sv[0]) if sv else "-"}{f" ({esc(subj)})" if subj else ""}.</p>')
        pat = re.compile(rf"\b{re.escape(name)}\b")
        cited = sorted({v for v, t in sources.items() if pat.search(t)} | {"St-Rm-P"} & set(views))
        cites = "".join(f'<li><a href="#view-{esc(v)}">{esc(names[v])} ({esc(v)})</a></li>' for v in cited)
        rows = []
        for rid in cap.get("rows") or []:
            subject, status = register.get(rid, ("", ""))
            rows.append(f"<li>{esc(rid)}: {esc(subject)} ({esc(status)})</li>" if subject else f"<li>{esc(rid)}</li>")
        sections.append(
            f'<section id="cap-{esc(name)}" class="page capability" data-capability="{esc(name)}">{head}'
            f'<p><a href="#front">Front page</a></p>{what}{evid}<h2>Severed behaviour</h2>{sev_html}{decs}'
            f'<h2>Cited by</h2><ul>{cites}</ul>'
            f'<h2>Open rows</h2>{"<ul>" + "".join(rows) + "</ul>" if rows else "<p>-</p>"}{prov}</section>')
        nav.append(f'<li><a href="#cap-{esc(name)}">{esc(name)}</a></li>')
    return sections, nav


def decision_pages(views: dict, dec: Decisions, prov: str) -> tuple[list[str], list[str]]:
    check_history()
    sections, nav = [], []
    for key in dec.keys():
        title, rest = split_title(dec.texts[key])
        if title is None:
            raise InputError(f"decisions/{dec.files[key].name} has no '# ' title line")
        body = style_tables(DecisionPage(key, views, dec).render(rest), view=False)
        pid = dec.page_id(key)
        label = "" if key == ROADMAP_KEY else key
        sections.append(
            f'<section id="{pid}" class="page decision" data-decision="{esc(label or "roadmap")}">'
            f'<h1>{esc(title)}</h1><p class="stamp" data-stamp>{esc(decision_stamp(dec.files[key]))}</p>'
            f'<p><a href="#front">Front page</a></p><div class="body">{body}</div>{prov}</section>')
        shown = title if key == ROADMAP_KEY or title.startswith(key) else f"{key} {title}"
        nav.append(f'<li><a href="#{pid}">{esc(shown)}</a></li>')
    return sections, nav


def build(a: argparse.Namespace, diagram: Diagram, date: str) -> str:
    """The whole file as text. a holds chart, values, release, readiness, record, slots."""
    if MarkdownIt is None:
        raise InputError("markdown-it-py is not installed: pip install markdown-it-py==4.0.0")
    renderers: dict[str, rp.Renderer] = {}
    for p in PROFILE_NAMES:
        ns = argparse.Namespace(**{**vars(a), "profile": p, "allow_no_kinds": getattr(a, "allow_no_kinds", None)})
        renderers[p] = rp.Renderer(ns, ROOT / "views")
    uaf = renderers["uaf"]
    views, system = uaf.views, uaf.name
    names = {v: e["name"] for v, e in views.items()}
    pre = f"{system}: " if system else ""
    rows = appendix_ids(ROOT)
    prov = provenance(a, date)
    rules = relabel.load(getattr(a, "relabel", None) or [])
    dec = Decisions(REPO / "decisions", rules)

    dx_text, dx_cells = dx_variants({p: r.dx_content() for p, r in renderers.items()})

    # names that change, per view
    sources = {p: renderers[p].export_sources() for p in ("dodaf202", "naf4")}
    sections = []
    nav = []
    total_exceptions = 0
    for vid, e in views.items():
        h1 = {"uaf": f"{pre}{e['name']} ({vid})"}
        only = []
        for p in ("dodaf202", "naf4"):
            r = renderers[p]
            mine = (e.get("exports") or {}).get(p) or []
            if mine:
                h1[p] = f"{pre}" + "; ".join(f"{x} {r.title_for(x)}" for x in mine) + f" ({r.label})"
            else:
                reason = (e.get("no_target") or {}).get(p)
                if not reason:
                    raise InputError(f"view {vid} has no exports and no no_target reason for {p}")
                h1[p] = f"{pre}Not exported in {r.label}: {e['name']} ({vid})"
                only.append(f'<p class="profile-only" data-profile-only data-for="{p}">{esc(reason)}</p>')
        attrs = " ".join(f'data-{p}="{esc(h1[p])}"' for p in PROFILE_NAMES)
        _, body = uaf.view_text(vid, rp.demote(dx_text))
        page = Page(vid, views, checked(diagram, vid), dec)
        body_html = page.render(body.rstrip("\n") + "\n")
        if vid in CAP_NAME_VIEWS:
            body_html = link_capability_names(vid, body_html, list(capability_phases.model_capabilities(uaf.sysml)))
        if vid == uaf.home:
            body_html = apply_header_cells(body_html, dx_cells)
            if "zzpname" in body_html:
                raise CheckError(f"view {vid}: a data-exchange header marker was not placed\n")
        body_html = style_tables(body_html)
        total_exceptions += page.exceptions
        attribution = f'<p class="attribution">{esc(uaf.attribution)}</p>' if uaf.attribution else ""
        sections.append(
            f'<section id="view-{esc(vid)}" class="page view" data-view="{esc(vid)}">'
            f'<h1 class="pname" {attrs}>{esc(h1["uaf"])}</h1>{"".join(only)}{attribution}'
            f'<p><a href="#front">Front page</a></p>'
            f'<div class="body">{body_html}</div>{prov}</section>')
        nav.append(f'<li><a class="pname" href="#view-{esc(vid)}" {attrs}>{esc(h1["uaf"])}</a></li>')
    if total_exceptions == 0:
        raise CheckError("no exception table found: no heading starting with 'Exception' is directly "
                         "followed by a table\n")
    decl_html = style_tables(Page("declarations", views, checked(diagram, "declarations"), dec).render(declarations_md(views)))
    sections.append(
        f'<section id="declarations" class="page" data-declarations>'
        f'<h1>{esc(pre)}{esc(DECLARATIONS_TITLE)}</h1>'
        f'<p><a href="#front">Front page</a></p>'
        f'<div class="body">{decl_html}</div>{prov}</section>')

    cap_sections, cap_nav = capability_pages(a, uaf, views, names, dec, prov)
    dec_sections, dec_nav = decision_pages(views, dec, prov)
    sections += cap_sections + dec_sections

    shown = (f"Decision records are shown with {dec.replaced} names replaced by neutral labels at export "
             f"({len(rules)} rules). The records in the repository are unchanged." if rules
             else "Decision records are shown verbatim.")
    grids = [grid_uaf(rows, views, names, uaf.uaf_label),
             grid_selected(renderers["dodaf202"], rows, names),
             grid_selected(renderers["naf4"], rows, names)]
    titles = {p: f"{pre}architecture views ({renderers[p].label})" for p in PROFILE_NAMES}
    title_attrs = " ".join(f'data-title-{p}="{esc(t)}"' for p, t in titles.items())
    buttons = "".join(
        f'<button type="button" data-profile-btn="{p}" aria-pressed="{"true" if p == "uaf" else "false"}">'
        f"{esc(renderers[p].label)}</button>" for p in PROFILE_NAMES)
    front = (f'<section id="front" class="page" data-front><h1>{esc(pre)}architecture views</h1>'
             f'{"".join(grids)}<p class="relabel" data-relabel>{esc(shown)}</p><nav class="views"><h2>Views</h2><ul>{"".join(nav)}</ul></nav>'
             f'<nav class="capabilities"><h2>Capabilities</h2><ul>{"".join(cap_nav)}</ul></nav>'
             f'<nav class="decisions"><h2>Decision records</h2><ul>{"".join(dec_nav)}</ul></nav>'
             f'<nav class="declarations"><h2>For a deployment</h2><ul><li><a href="#declarations">'
             f'{esc(DECLARATIONS_TITLE)}</a></li></ul></nav>{prov}</section>')
    return (f'<!doctype html>\n<html lang="en" data-profile="uaf" {title_attrs}>\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<meta http-equiv="Content-Security-Policy" content="{CSP}">\n'
            f'<title>{esc(titles["uaf"])}</title>\n<style>\n{CSS}\n</style>\n</head>\n<body>\n'
            f'<header class="bar"><span class="sys">{esc(system or "Architecture")}</span>'
            f'<a href="#front">Front page</a><span class="profiles" role="group" aria-label="Profile">{buttons}</span>'
            f'<input id="q" type="search" placeholder="Search" aria-label="Search the views" autocomplete="off"></header>\n'
            f'<div id="results" hidden></div>\n<main>\n{front}\n' + "\n".join(sections) +
            f'\n</main>\n<script>\n{JS}\n</script>\n</body>\n</html>\n')


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render the architecture views as one HTML file.")
    ap.add_argument("--out", required=True, help="the file to write")
    ap.add_argument("--chart", required=True)
    ap.add_argument("--values", action="append", default=[], required=True)
    ap.add_argument("--release", required=True, help="the Helm release name the chart is rendered under")
    ap.add_argument("--readiness", help="the readiness doc (default: <chart>/../scripts/RECORDING-READINESS.md)")
    ap.add_argument("--record", default=str(ROOT / "capability-record.yaml"))
    ap.add_argument("--slots")
    ap.add_argument("--relabel", action="append", default=[],
                    help="a list of PATTERN<TAB>REPLACEMENT lines applied to the decision records at export")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today, UTC)")
    ap.add_argument("--mmdc", help="the mermaid-cli binary (default: docs/arch/tools/export/node_modules/.bin/mmdc)")
    ap.add_argument("--puppeteer-config", help="a puppeteer config file for mermaid-cli")
    a = ap.parse_args(argv)
    try:
        date = a.date or datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise InputError("--date must be YYYY-MM-DD")
        diagram = make_mmdc(a.mmdc or default_mmdc(), a.puppeteer_config)
        text = build(a, diagram, date)
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INPUT
    except check_views.InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INPUT
    except CheckError as e:
        sys.stderr.write(e.args[0])
        return EXIT_CHECK
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"out: {out.resolve().as_posix()}")
    print(f"bytes: {out.stat().st_size}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
