#!/usr/bin/env python3
"""render_profile.py - render the architecture views as one output profile.

The content lives once, in docs/arch/views/ under its UAF 1.2 view
specification. A profile (uaf, dodaf202, naf4) only renames and selects, by
profiles.yaml. This tool writes one markdown file per view (uaf) or per
export id (dodaf202, naf4), an INDEX.md, and for the two profiles that
select, a NOT-EXPORTED.md naming every view the profile cannot name.

Usage:
    python docs/arch/tools/render_profile.py --profile uaf|dodaf202|naf4
        [--out DIR] [--slots FILE]
        [--chart PATH --values FILE [--values FILE ...]]
        [--allow-no-kinds REASON] [--release NAME]

--release is the Helm release name; --chart needs it.

Every file starts with `# <system name>: <title>` and a line saying what the
bundle is built on, both read from the bundle values `system.name` and
`system.attribution` (data_exchange.presentation). Without a name from the
values, a `system-name` value in --slots is the name; with neither, the
title is as written in the view.

Transforms on view text: `<!-- model: Pkg -->` becomes a fenced sysml block
holding that package from model/openddil.sysml; `<!-- generated:
data-exchange -->` (data_exchange.home only) becomes the document that
data_exchange.py writes, or a notice when --chart is not given; relative
links are rewritten to resolve from the output directory; `{{slot:name}}`
is replaced from the --slots file (a YAML map of slot name to string).
`{{slot:system-name}}` is filled from the bundle values when they name the
system, and then --slots may not give another name.
Unfilled slots stay as written and are counted.

The default output directory is docs/arch/out/<profile>/, whose *.md files
are cleared first. With --out, DIR must be empty, missing, or hold an
INDEX.md (then its *.md files are cleared), else exit 2.

Exit codes: 0 ok, 1 the data-exchange check failed, 2 bad input. Output is
byte-stable: no timestamps, sorted where profiles.yaml gives no order.
Stdlib and PyYAML only.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_exchange import InputError, presentation  # noqa: E402

EXIT_OK, EXIT_CHECK, EXIT_INPUT = 0, 1, 2
ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
PROFILE_NAMES = ["uaf", "dodaf202", "naf4"]
NOTICE = "Not generated: pass --chart and --values to fill this from a bundle."
GEN_MARKER = "<!-- generated: data-exchange -->"
MODEL_RE = re.compile(r"<!--\s*model:\s*([A-Za-z_][\w]*)\s*-->")
SLOT_RE = re.compile(r"\{\{slot:([A-Za-z0-9_-]+)\}\}")
LINK_RE = re.compile(r"(\[[^\]\n]*\]\()([^)\s]+)(\))")
HEADING_RE = re.compile(r"^(#{1,6})(\s)")


class CheckError(Exception):
    """The data-exchange check failed: exit 1. Carries stderr to pass through."""


# --- SysML scanning ----------------------------------------------------------

def mask_sysml(text: str) -> str:
    """Return text of equal length with comments and string contents blanked.

    Newlines are kept so offsets and lines line up with the original. Braces
    inside `//` and `/* */` comments, and inside "..." or '...' names, are
    replaced by spaces and so cannot confuse brace matching.
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        two = text[i:i + 2]
        if two == "//":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
        elif two == "/*":
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            out.extend(ch if ch == "\n" else " " for ch in text[i:end])
            i = end
        elif c in "\"'":
            quote = c
            out.append(c)
            i += 1
            while i < n and text[i] != quote:
                if text[i] == "\\" and i + 1 < n:
                    out.append(" ")
                    i += 1
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            if i < n:
                out.append(quote)
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def match_brace(masked: str, open_at: int) -> int:
    """Index of the brace closing the one at open_at, in masked text."""
    depth = 0
    for i in range(open_at, len(masked)):
        if masked[i] == "{":
            depth += 1
        elif masked[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise InputError("unbalanced braces in the model")


def package_block(text: str, masked: str, name: str) -> str | None:
    """The dedented source of `package <name> { ... }`, or None."""
    m = re.search(r"\bpackage\s+" + re.escape(name) + r"\s*\{", masked)
    if not m:
        return None
    end = match_brace(masked, m.end() - 1)
    start = text.rfind("\n", 0, m.start()) + 1
    return textwrap.dedent(text[start:end + 1])


def package_depths(masked: str) -> list[tuple[str, int]]:
    """Every (package name, brace depth of its declaration) in the model."""
    found = []
    for m in re.finditer(r"\bpackage\s+(\w+)\s*\{", masked):
        depth = masked.count("{", 0, m.start()) - masked.count("}", 0, m.start())
        found.append((m.group(1), depth))
    return found


# --- loading -----------------------------------------------------------------

def load_yaml(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise InputError(f"cannot read {path}: {e}")


def load_slots_registry(root: Path) -> set[str]:
    reg = load_yaml(root / "slots.yaml") or {}
    return set((reg.get("slots") or {}).keys())


def load_slot_values(path: str | None, registry: set[str]) -> dict[str, str]:
    if not path:
        return {}
    data = load_yaml(Path(path))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise InputError(f"{path}: expected a map of slot name to string")
    for k, v in data.items():
        if k not in registry:
            raise InputError(f"{path}: slot '{k}' is not in slots.yaml")
        if not isinstance(v, str):
            raise InputError(f"{path}: slot '{k}' must be a string")
    return dict(data)


def read_view(root: Path, entry: dict, vid: str) -> tuple[str, str]:
    """Return (H1 line, body text without the H1 and the blank lines after it)."""
    path = root / entry["file"]
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise InputError(f"view {vid}: cannot read {path}: {e}")
    lines = text.split("\n")
    if not lines or not lines[0].startswith("# "):
        raise InputError(f"view {vid}: first line is not an H1")
    body = lines[1:]
    while body and not body[0].strip():
        body.pop(0)
    return lines[0], "\n".join(body)


# --- text transforms ---------------------------------------------------------

def split_fences(text: str) -> list[tuple[bool, str, str]]:
    """Split text into (in_fence, info, line) triples, fences included."""
    out, fence, info = [], False, ""
    for line in text.split("\n"):
        s = line.lstrip()
        if s.startswith("```") or s.startswith("~~~"):
            if not fence:
                fence, info = True, s[3:].strip().lower()
                out.append((True, info, line))
            else:
                out.append((True, info, line))
                fence, info = False, ""
            continue
        out.append((fence, info, line))
    return out


def inline_model(text: str, sysml: str, masked: str) -> str:
    def sub(m: re.Match) -> str:
        block = package_block(sysml, masked, m.group(1))
        if block is None:
            raise InputError(f"model marker names unknown package '{m.group(1)}'")
        return "```sysml\n" + block.rstrip("\n") + "\n```"
    return MODEL_RE.sub(sub, text)


def rewrite_links(text: str, src_dir: Path, out_dir: Path) -> str:
    """Rewrite relative markdown links so they resolve from out_dir."""
    def fix(target: str) -> str:
        if re.match(r"^([a-z][a-z0-9+.-]*:|#|/)", target, re.I):
            return target
        path, hash_, frag = target.partition("#")
        absolute = (src_dir / path).resolve()
        try:
            new = os.path.relpath(absolute, out_dir.resolve()).replace(os.sep, "/")
        except ValueError:
            new = absolute.as_posix()
        if path.endswith("/") and not new.endswith("/"):
            new += "/"
        return new + hash_ + frag

    def line_sub(line: str) -> str:
        return LINK_RE.sub(lambda m: m.group(1) + fix(m.group(2)) + m.group(3), line)

    return "\n".join(line if f else line_sub(line) for f, _, line in split_fences(text))


def fill_slots(text: str, values: dict[str, str]) -> str:
    if not values:
        return text

    def sub_for(mermaid: bool):
        def sub(m: re.Match) -> str:
            v = values.get(m.group(1))
            if v is None:
                return m.group(0)
            if mermaid:
                v = v.replace('"', "'").replace("\n", " ")
            return v
        return sub

    lines = []
    for fence, info, line in split_fences(text):
        lines.append(SLOT_RE.sub(sub_for(fence and info.startswith("mermaid")), line))
    return "\n".join(lines)


def demote(text: str) -> str:
    """Demote every heading one level, outside fences (capped at H6)."""
    return "\n".join(
        line if f else HEADING_RE.sub(lambda m: "#" * min(len(m.group(1)) + 1, 6) + m.group(2), line, count=1)
        for f, _, line in split_fences(text))


def unfilled(text: str) -> set[str]:
    return set(SLOT_RE.findall(text))


# --- data exchange -----------------------------------------------------------

def generate_document(a: argparse.Namespace, profile: str) -> str:
    cmd = [sys.executable, str(TOOLS / "data_exchange.py"), "--chart", a.chart, "--release", a.release,
           "--profile", profile, "--check"]
    for v in a.values:
        cmd += ["--values", v]
    if a.allow_no_kinds:
        cmd += ["--allow-no-kinds", a.allow_no_kinds]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise CheckError(p.stderr.decode("utf-8", "replace"))
    return p.stdout.decode("utf-8").replace("\r\n", "\n")


def drop_h1(doc: str, attribution: str | None) -> str:
    """The document without its H1 and attribution line, so the file that embeds it carries them once."""
    lines = doc.split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines.pop(0)
    text = "\n".join(lines)
    if attribution and text.startswith(attribution):
        text = text[len(attribution):].lstrip("\n")
    return text.rstrip("\n")


# --- rendering ---------------------------------------------------------------

class Renderer:
    def __init__(self, a: argparse.Namespace, out_dir: Path):
        self.a, self.out_dir = a, out_dir
        self.prof = load_yaml(ROOT / "profiles.yaml") or {}
        self.profile = a.profile
        self.label = self.prof["profiles"][self.profile]["label"]
        self.uaf_label = self.prof["profiles"]["uaf"]["label"]
        self.views = self.prof.get("views") or {}
        self.dx = self.prof.get("data_exchange") or {}
        self.home = self.dx.get("home")
        self.dx_id = self.dx[self.profile]["id"]
        sysml_path = ROOT / "model" / "openddil.sysml"
        try:
            self.sysml = sysml_path.read_text(encoding="utf-8")
        except OSError as e:
            raise InputError(f"cannot read {sysml_path}: {e}")
        self.masked = mask_sysml(self.sysml)
        self.slot_values = load_slot_values(a.slots, load_slots_registry(ROOT))
        layers, version = [], None
        if a.chart:
            cdir = Path(a.chart)
            files = [cdir / "values.yaml"] if (cdir / "values.yaml").is_file() else []
            for f in files + [Path(v) for v in a.values]:
                layer = load_yaml(f)
                layers.append(layer if isinstance(layer, dict) else {})
            if (cdir / "Chart.yaml").is_file():
                v = (load_yaml(cdir / "Chart.yaml") or {}).get("version")
                version = str(v) if v is not None else None
        self.name, self.attribution = presentation(layers, version)
        given = self.slot_values.get("system-name")
        if self.name:
            if given is not None and given.strip() != self.name:
                raise InputError(f"--slots system-name '{given}' differs from system.name '{self.name}' "
                                 "in the bundle values")
            self.slot_values["system-name"] = self.name
        elif given is not None and given.strip():
            self.name = given.strip()
        self.doc: str | None = None
        if a.chart:
            self.doc = generate_document(a, self.profile)

    def dx_content(self) -> str:
        """The generated document without its H1, or the notice."""
        if self.doc is None:
            return NOTICE
        return drop_h1(self.doc, self.attribution)

    def head(self, title: str) -> str:
        """The H1 and the attribution line, each followed by a blank line."""
        h1 = "# " + (f"{self.name}: " if self.name else "") + title
        return h1 + "\n\n" + (self.attribution + "\n\n" if self.attribution else "")

    def view_text(self, vid: str, dx_marker: str) -> tuple[str, str]:
        """(H1, body) of a view with every transform applied; dx_marker replaces the data-exchange marker."""
        entry = self.views[vid]
        h1, body = read_view(ROOT, entry, vid)
        if GEN_MARKER in body and vid != self.home:
            raise InputError(f"view {vid}: the data-exchange marker belongs only in {self.home}")
        body = inline_model(body, self.sysml, self.masked)
        body = rewrite_links(body, (ROOT / entry["file"]).parent, self.out_dir)
        body = fill_slots(body, self.slot_values)
        # The generated document is final text: insert it last, slots and links untouched.
        body = body.replace(GEN_MARKER, dx_marker)
        return h1, body

    # uaf ------------------------------------------------------------------
    def render_uaf(self) -> dict[str, str]:
        files: dict[str, str] = {}
        for vid in self.views:
            h1, body = self.view_text(vid, demote(self.dx_content()))
            files[f"{vid}.md"] = self.head(h1[2:]) + body.rstrip("\n") + "\n"
        rows = [self.head("Index (" + self.label + ")") + "| View | Name |", "|---|---|"]
        rows += [f"| [{vid}]({vid}.md) | {e['name']} |" for vid, e in self.views.items()]
        files["INDEX.md"] = "\n".join(rows) + "\n"
        return files

    # dodaf202, naf4 -------------------------------------------------------
    def export_sources(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for vid, e in self.views.items():
            for x in (e.get("exports") or {}).get(self.profile) or []:
                out.setdefault(x, []).append(vid)
        return out

    def title_for(self, export_id: str) -> str:
        if export_id == self.dx_id:
            return self.dx[self.profile]["title"]
        t = ((self.prof.get("export_titles") or {}).get(self.profile) or {}).get(export_id)
        if not t:
            raise InputError(f"export {export_id} has no title for {self.profile}")
        return t

    def source_body(self, export_id: str, vid: str) -> str:
        """One source view's body for one export."""
        if vid == self.home and GEN_MARKER in (ROOT / self.views[vid]["file"]).read_text(encoding="utf-8"):
            if export_id == self.dx_id:
                mine = (self.views[vid].get("exports") or {}).get(self.profile) or []
                if len(mine) > 1:
                    return self.dx_content()
                _, body = self.view_text(vid, demote(self.dx_content()))
                return body.rstrip("\n")
            _, body = self.view_text(vid, f"Exported separately as {self.dx_id}.")
            return body.rstrip("\n")
        _, body = self.view_text(vid, "")
        return body.rstrip("\n")

    def render_export(self, export_id: str, sources: list[str]) -> str:
        lines = [self.head(f"{export_id} {self.title_for(export_id)} ({self.label})").rstrip("\n"), ""]
        lines += [f"From {self.uaf_label} {self.views[v]['name']} ({v})." for v in sources]
        lines.append("")
        if len(sources) == 1:
            lines.append(self.source_body(export_id, sources[0]))
        else:
            for v in sources:
                name = self.views[v]["name"]
                lines += [f"## {name} ({v})", "", demote(self.source_body(export_id, v)), ""]
        return "\n".join(lines).rstrip("\n") + "\n"

    def render_selected(self) -> dict[str, str]:
        files: dict[str, str] = {}
        sources = self.export_sources()
        for x in sorted(sources):
            files[f"{x}.md"] = self.render_export(x, sources[x])
        rows = [self.head(f"Index ({self.label})") + "| Export | Title | Source views |", "|---|---|---|"]
        rows += [f"| [{x}]({x}.md) | {self.title_for(x)} | {', '.join(sources[x])} |" for x in sorted(sources)]
        files["INDEX.md"] = "\n".join(rows) + "\n"
        left = unfilled("\n".join(t for n, t in files.items() if n != "INDEX.md"))
        ne = [self.head(f"Not exported ({self.label})").rstrip("\n"), "",
              f"Views that {self.label} has no view for, with the reason. Nothing is dropped silently.", ""]
        ne += ["| View | Reason |", "|---|---|"]
        for vid, e in self.views.items():
            if (e.get("exports") or {}).get(self.profile):
                continue
            reason = (e.get("no_target") or {}).get(self.profile)
            if not reason:
                raise InputError(f"view {vid} has no exports and no no_target reason for {self.profile}")
            ne.append(f"| {e['name']} ({vid}) | {reason} |")
        ne += ["", f"Unfilled slots in this output: {len(left)}."]
        files["NOT-EXPORTED.md"] = "\n".join(ne) + "\n"
        return files

    def render(self) -> dict[str, str]:
        return self.render_uaf() if self.profile == "uaf" else self.render_selected()


def prepare_out(out: str | None, profile: str) -> Path:
    if out is None:
        return ROOT / "out" / profile
    d = Path(out)
    if d.exists():
        if not d.is_dir():
            raise InputError(f"--out {out} is not a directory")
        if any(d.iterdir()) and not (d / "INDEX.md").is_file():
            raise InputError(f"--out {out} is not empty and holds no INDEX.md")
    return d


def write_files(out_dir: Path, files: dict[str, str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.md"):
        old.unlink()
    for name, text in files.items():
        (out_dir / name).write_text(text, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Render the architecture views as one output profile.")
    ap.add_argument("--profile", required=True, choices=PROFILE_NAMES)
    ap.add_argument("--out")
    ap.add_argument("--slots")
    ap.add_argument("--chart")
    ap.add_argument("--values", action="append", default=[])
    ap.add_argument("--release", help="the Helm release name the chart is rendered under")
    ap.add_argument("--allow-no-kinds", metavar="REASON")
    a = ap.parse_args(argv)
    try:
        if a.values and not a.chart:
            raise InputError("--values needs --chart")
        if a.chart and not a.release:
            raise InputError("--chart needs --release (the Helm release name)")
        out_dir = prepare_out(a.out, a.profile)
        files = Renderer(a, out_dir).render()
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INPUT
    except CheckError as e:
        sys.stderr.write(e.args[0])
        return EXIT_CHECK
    write_files(out_dir, files)
    left = unfilled("\n".join(t for n, t in files.items() if n not in ("INDEX.md", "NOT-EXPORTED.md")))
    print(f"profile: {a.profile}")
    print(f"out: {out_dir.resolve().as_posix()}")
    print(f"files written: {len(files)}")
    print(f"unfilled slots: {len(left)}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
