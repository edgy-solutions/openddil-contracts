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
import check_views  # noqa: E402
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


def repo_relative(href: str) -> str:
    """The repo-relative path a relative link resolves to from the views directory."""
    path = href.partition("#")[0]
    absolute = (ROOT / "views" / path).resolve()
    try:
        return absolute.relative_to(REPO.resolve()).as_posix() + ("/" if path.endswith("/") else "")
    except ValueError:
        raise InputError(f"link '{href}' resolves outside the repository") from None


class Page:
    """Markdown to html for one view, with the link, slot, table and diagram rules applied."""

    def __init__(self, vid: str, views: dict, diagram: Diagram):
        self.vid, self.views, self.diagram = vid, views, diagram
        self.n = 0
        self.stack: list[tuple[str, str, str]] = []
        self.exceptions = 0
        md = MarkdownIt("commonmark", {"html": False}).enable("table")
        md.renderer.rules["fence"] = self.fence
        md.renderer.rules["text"] = self.text
        md.renderer.rules["link_open"] = self.link_open
        md.renderer.rules["link_close"] = self.link_close
        md.renderer.rules["image"] = self.image
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

    @staticmethod
    def text(tokens, idx, options, env) -> str:
        parts = rp.SLOT_RE.split(tokens[idx].content)
        out = []
        for k, p in enumerate(parts):
            out.append(f'<span class="slot">{{{{slot:{esc(p)}}}}}</span>' if k % 2 else esc(p))
        return "".join(out)

    def link_open(self, tokens, idx, options, env) -> str:
        tok = tokens[idx]
        href = tok.attrGet("href") or ""
        if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):
            self.stack.append(("url", href, tok.markup))
            return ""
        if href.startswith("#") or not href:
            self.stack.append(("ref", "", tok.markup))
            return '<span class="ref">'
        path = href.partition("#")[0]
        target = (ROOT / "views" / path).resolve()
        for vid, e in self.views.items():
            if target == (ROOT / e["file"]).resolve():
                self.stack.append(("view", vid, tok.markup))
                return f'<a href="#view-{esc(vid)}">'
        self.stack.append(("ref", "", tok.markup))
        return f'<span class="ref" title="{esc(repo_relative(href))}">'

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


def style_table(t: str) -> str:
    split = t.find("<tbody")
    rows = list(ROW_RE.finditer(t))
    if not rows:
        return t
    head_starts = {m.start() for m in rows if (m.start() < split if split >= 0 else m is rows[0])}
    grid = [[(c.group(1), c.group(2), c.group(3)) for c in CELL_RE.finditer(m.group(1))] for m in rows]
    ncols = max(len(r) for r in grid)
    head_texts = [plain(c[2]) for c in grid[0]] if rows[0].start() in head_starts else []
    lane_col = head_texts.index("Lane") if "Lane" in head_texts else -1
    phase_col = head_texts.index("Phase") if "Phase" in head_texts else -1
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


def style_tables(body_html: str) -> str:
    """Table styling the CSS cannot do alone: words held whole, column minimums, phase badges, lane rules.
    Call it after apply_header_cells. Text inside svg blocks and in grid tables is left alone."""
    def one(m: re.Match) -> str:
        t = m.group(0)
        return t if "gridtable" in t[: t.index(">")] else style_table(t)
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
.page:target{display:block}
body:not(:has(.page:target)) #front{display:block}
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
nav.views ul{columns:2 280px;padding-left:1.2em}
@page{size:landscape}
@media (max-width:600px){h1{font-size:1.3rem}.bar{gap:6px 8px}}
@media print{
  .bar,#results{display:none!important}
  body{font-size:11pt}
  main{max-width:none;padding:0}
  .page,.page:target,body:not(:has(.page:target)) #front{display:block}
  .page{break-before:page}
  .page:first-of-type{break-before:auto}
  .scroll{overflow:visible}
  table{font-size:8pt;width:100%}
  thead th{background:none;color:inherit;border-bottom:2px solid var(--head)}
  tbody tr:nth-child(even)>*,tbody th,.gridtable td:has(.filled){background:none}
  .badge,.phase-measured,.phase-built-unmeasured,.phase-accepted-design,.phase-proposed,.phase-row{background:none;color:inherit;padding:0;border-radius:0;font-weight:600}
  th:nth-child(n+4){min-width:0!important}
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
        page = Page(vid, views, checked(diagram, vid))
        body_html = page.render(body.rstrip("\n") + "\n")
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

    grids = [grid_uaf(rows, views, names, uaf.uaf_label),
             grid_selected(renderers["dodaf202"], rows, names),
             grid_selected(renderers["naf4"], rows, names)]
    titles = {p: f"{pre}architecture views ({renderers[p].label})" for p in PROFILE_NAMES}
    title_attrs = " ".join(f'data-title-{p}="{esc(t)}"' for p, t in titles.items())
    buttons = "".join(
        f'<button type="button" data-profile-btn="{p}" aria-pressed="{"true" if p == "uaf" else "false"}">'
        f"{esc(renderers[p].label)}</button>" for p in PROFILE_NAMES)
    front = (f'<section id="front" class="page" data-front><h1>{esc(pre)}architecture views</h1>'
             f'{"".join(grids)}<nav class="views"><h2>Views</h2><ul>{"".join(nav)}</ul></nav>{prov}</section>')
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
