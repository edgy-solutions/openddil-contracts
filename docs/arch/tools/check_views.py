#!/usr/bin/env python3
"""check_views.py - check the architecture views against the rules that keep them honest.

Reads docs/arch (views, profiles.yaml, slots.yaml, README.md, INVENTORY.md,
the SysML model) and the decision records the views cite. Writes one
`FAIL: <rule>: <what>` line per finding on stderr, and exits 1 if there is
any. When nothing fails it prints an `ok:` count line.

Usage:
    python docs/arch/tools/check_views.py [--root docs/arch]

Rules: exports, appendix-a, view-files, slots, links, sources-table,
marks, model, capabilities, trace, outputs, generated. The vocabularies for
the Decision and Evidence columns are read from README.md, so they live once.
The mapping from UAF views to DoDAF and NAF outputs is read from APPENDIX-A.md,
the only copy: `exports` fails on an export it does not name, and `appendix-a`
fails on a table that is missing, malformed, or out of step with profiles.yaml.

Exit codes: 0 ok, 1 a check failed, 2 bad input (a required file is missing
or does not parse). Stdlib and PyYAML only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from render_profile import mask_sysml, package_depths

EXIT_OK, EXIT_CHECK, EXIT_INPUT = 0, 1, 2
RULES = ["exports", "appendix-a", "view-files", "slots", "links", "sources-table",
         "marks", "model", "capabilities", "trace", "outputs", "generated"]
APPENDIX_HEADER = "| View | Name | DoDAF 2.02 | NAF 4.0 | DNDAF |"
APPENDIX_COLUMNS = {"dodaf202": 2, "naf4": 3}
SOURCES_HEADER = "| Claim | Source | Decision | Evidence |"
GEN_MARKER = "<!-- generated: data-exchange -->"
MODEL_RE = re.compile(r"<!--\s*model:\s*([A-Za-z_]\w*)\s*-->")
SLOT_RE = re.compile(r"\{\{slot:([A-Za-z0-9_-]+)\}\}")
LINK_RE = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)\)")
CODE_SPAN_RE = re.compile(r"`[^`\n]*`")
REQUIRED_DODAF = ["OV-1", "OV-2", "OV-5a", "OV-5b", "SV-1", "SV-2", "SV-4", "SV-6", "StdV-1", "DIV-2", "CV-2"]
REQUIRED_VIEWS = ["Op-Cn", "Rs-Sr", "Rs-If", "Sc-Sr", "Sd-Tx", "St-Rm-P", "Rs-Tr"]


class InputError(Exception):
    """Bad input: exit 2."""


class Tree:
    """Everything the rules read, loaded once."""

    def __init__(self, root: Path):
        self.root = root
        self.profiles = self.yaml(root / "profiles.yaml")
        self.slots = self.yaml(root / "slots.yaml")
        self.views: dict = self.profiles.get("views") or {}
        self.readme = self.text(root / "README.md")
        self.sysml = self.text(root / "model" / "openddil.sysml")
        self.masked = mask_sysml(self.sysml)
        self.view_text = {vid: self.text(root / e["file"]) for vid, e in self.views.items()
                          if (root / e["file"]).is_file()}

    @staticmethod
    def text(p: Path) -> str:
        try:
            return p.read_text(encoding="utf-8")
        except OSError as e:
            raise InputError(f"cannot read {p}: {e}")

    def yaml(self, p: Path) -> dict:
        try:
            d = yaml.safe_load(self.text(p))
        except yaml.YAMLError as e:
            raise InputError(f"cannot parse {p}: {e}")
        if not isinstance(d, dict):
            raise InputError(f"{p} is not a map")
        return d


# --- markdown helpers --------------------------------------------------------

def outside_fences(text: str) -> list[str]:
    out, fence = [], False
    for line in text.split("\n"):
        if line.lstrip().startswith(("```", "~~~")):
            fence = not fence
            continue
        if not fence:
            out.append(line)
    return out


def split_row(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def table_after(lines: list[str], start: int) -> tuple[str, list[list[str]]]:
    """The first table at or after lines[start]: (header line, body rows)."""
    i = start
    while i < len(lines) and not lines[i].lstrip().startswith("|"):
        i += 1
    if i >= len(lines):
        return "", []
    header = lines[i].strip()
    i += 2  # skip the separator
    rows = []
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        rows.append(split_row(lines[i]))
        i += 1
    return header, rows


def first_table(text: str) -> list[list[str]]:
    return table_after(outside_fences(text), 0)[1]


def sources_table(text: str) -> tuple[str, list[list[str]]] | None:
    lines = outside_fences(text)
    for i, line in enumerate(lines):
        if line.strip() == "## Sources":
            return table_after(lines, i + 1)
    return None


def relative_links(text: str) -> list[str]:
    found = []
    for line in outside_fences(text):
        line = CODE_SPAN_RE.sub("", line)
        for t in LINK_RE.findall(line):
            if not re.match(r"^([a-z][a-z0-9+.-]*:|#)", t, re.I):
                found.append(t)
    return found


def vocabulary(readme: str, head: str) -> set[str]:
    lines = outside_fences(readme)
    for i, line in enumerate(lines):
        if line.strip().replace(" ", "") == head.replace(" ", ""):
            return {r[0] for r in table_after(lines, i)[1] if r and r[0]}
    return set()


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


# --- rules -------------------------------------------------------------------

def appendix_parse(root: Path) -> tuple[str, list[list[str]]] | None:
    """(header line, body rows) of the first table of APPENDIX-A.md, or None if the file is missing."""
    try:
        text = (root / "APPENDIX-A.md").read_text(encoding="utf-8")
    except OSError:
        return None
    return table_after(outside_fences(text), 0)


def appendix_table(root: Path) -> list[list[str]]:
    """The rows of the first table of APPENDIX-A.md; empty when the file is missing."""
    got = appendix_parse(root)
    return got[1] if got else []


def appendix_cell(cell: str) -> set[str]:
    return set() if cell.strip() == "-" else {x.strip() for x in cell.split(",") if x.strip()}


def appendix_names(root: Path) -> dict[str, dict[str, set[str]]]:
    """view id -> profile -> the output ids the table names, the union over the view's rows."""
    out: dict[str, dict[str, set[str]]] = {}
    for r in appendix_table(root):
        if len(r) != 5:
            continue
        per = out.setdefault(r[0], {p: set() for p in APPENDIX_COLUMNS})
        for prof, col in APPENDIX_COLUMNS.items():
            per[prof] |= appendix_cell(r[col])
    return out


def rule_exports(t: Tree) -> list[str]:
    names = appendix_names(t.root)
    fails = []
    for vid, e in t.views.items():
        for prof, ids in (e.get("exports") or {}).items():
            allowed = names.get(vid, {}).get(prof, set())
            for x in ids or []:
                if x not in allowed:
                    fails.append(f"exports: {vid} {prof} exports {x}, which APPENDIX-A.md does not name for that view")
    return fails


def rule_appendix(t: Tree) -> list[str]:
    got = appendix_parse(t.root)
    if got is None:
        return ["appendix-a: APPENDIX-A.md does not exist"]
    header, rows = got
    if header != APPENDIX_HEADER:
        return [f"appendix-a: APPENDIX-A.md table header is '{header}', expected '{APPENDIX_HEADER}'"]
    fails, seen = [], set()
    for r in rows:
        if len(r) != 5:
            fails.append(f"appendix-a: row '{(r[0] if r else '')[:40]}' has {len(r)} cells, expected 5")
            continue
        if (r[0], r[1]) in seen:
            fails.append(f"appendix-a: {r[0]} '{r[1]}' appears twice")
        seen.add((r[0], r[1]))
    names = appendix_names(t.root)
    for vid, e in t.views.items():
        if vid not in names:
            fails.append(f"appendix-a: view {vid} has no row in APPENDIX-A.md")
            continue
        for prof, reason in (e.get("no_target") or {}).items():
            if reason and names[vid].get(prof):
                fails.append(f"appendix-a: {vid} has a no_target reason for {prof}, "
                             f"but APPENDIX-A.md names {', '.join(sorted(names[vid][prof]))}")
        if "appendix_a" in e:
            fails.append(f"appendix-a: view {vid} still has appendix_a in profiles.yaml; the mapping lives in APPENDIX-A.md")
    if "deviations" in t.profiles:
        fails.append("appendix-a: profiles.yaml still has deviations; the mapping lives in APPENDIX-A.md")
    return fails


def rule_view_files(t: Tree) -> list[str]:
    fails, listed = [], set()
    for vid, e in t.views.items():
        path = t.root / e["file"]
        listed.add(path.resolve())
        if not path.is_file():
            fails.append(f"view-files: {vid}: file {e['file']} does not exist")
            continue
        first = t.view_text[vid].split("\n", 1)[0].rstrip("\r")
        want = f"# {e['name']} ({vid})"
        if first != want:
            fails.append(f"view-files: {vid}: first line is '{first}', expected '{want}'")
    for p in sorted((t.root / "views").glob("*.md")):
        if p.resolve() not in listed:
            fails.append(f"view-files: {p.name} has no entry in profiles.yaml")
    return fails


def rule_slots(t: Tree) -> list[str]:
    fails = []
    registry = t.slots.get("slots") or {}
    used: dict[str, list[str]] = {}
    for vid, text in t.view_text.items():
        for name in SLOT_RE.findall(text):
            used.setdefault(name, []).append(vid)
    for name in sorted(used):
        if name not in registry:
            fails.append(f"slots: {name} is used in {', '.join(sorted(set(used[name])))} and not in slots.yaml")
    for name in sorted(registry):
        if name not in used:
            fails.append(f"slots: {name} is in slots.yaml and used in no view")
        entry = registry[name] or {}
        for key in ("fills", "source"):
            if not entry.get(key):
                fails.append(f"slots: {name} lacks '{key}' in slots.yaml")
    return fails


def rule_links(t: Tree) -> list[str]:
    fails = []
    files = [(f"views/{Path(e['file']).name}", t.root / e["file"]) for e in t.views.values()]
    files += [(n, t.root / n) for n in ("README.md", "INVENTORY.md", "APPENDIX-A.md")]
    for name, path in files:
        if not path.is_file():
            if not name.startswith("views/"):  # a missing view file is view-files' finding
                fails.append(f"links: {name} does not exist")
            continue
        for target in relative_links(path.read_text(encoding="utf-8")):
            rel = target.split("#", 1)[0]
            if rel and not (path.parent / rel).exists():
                fails.append(f"links: {name}: link {target} does not resolve")
    return fails


def rule_sources_table(t: Tree) -> list[str]:
    fails = []
    decisions = vocabulary(t.readme, "| Decision | Meaning |")
    evidences = vocabulary(t.readme, "| Evidence | Meaning |")
    if not decisions or not evidences:
        fails.append("sources-table: README.md has no Decision or Evidence vocabulary table")
    for vid, text in t.view_text.items():
        got = sources_table(text)
        if got is None:
            fails.append(f"sources-table: {vid}: no '## Sources' section")
            continue
        header, rows = got
        if header != SOURCES_HEADER:
            fails.append(f"sources-table: {vid}: table header is '{header}', expected '{SOURCES_HEADER}'")
            continue
        if not rows:
            fails.append(f"sources-table: {vid}: the Sources table has no rows")
        for r in rows:
            claim = (r[0] if r else "")[:50]
            if len(r) != 4:
                fails.append(f"sources-table: {vid}: row '{claim}' has {len(r)} cells, expected 4")
                continue
            if not LINK_RE.search(r[1]):
                fails.append(f"sources-table: {vid}: row '{claim}' has no link in Source")
            if decisions and r[2] not in decisions:
                fails.append(f"sources-table: {vid}: row '{claim}' Decision '{r[2]}' is not in the README vocabulary")
            if evidences and r[3] not in evidences:
                fails.append(f"sources-table: {vid}: row '{claim}' Evidence '{r[3]}' is not in the README vocabulary")
    return fails


def rule_marks(t: Tree) -> list[str]:
    fails = []
    for vid, text in t.view_text.items():
        got = sources_table(text)
        if got is None or got[0] != SOURCES_HEADER:
            continue
        for r in got[1]:
            if len(r) != 4:
                continue
            claim = r[0][:50]
            m = LINK_RE.search(r[1])
            if not m or not Path(m.group(1)).name.startswith("ADR-"):
                continue
            adr = (t.root / "views" / m.group(1).split("#", 1)[0]).resolve()
            where = f"marks: {vid}: row '{claim}' cites {adr.name}"
            if not adr.is_file():
                fails.append(f"{where}, which does not exist")
                continue
            status = adr_status(adr.read_text(encoding="utf-8"))
            if not status:
                fails.append(f"{where}, which states no status")
                continue
            lead = status.lstrip("*").lstrip().lower()
            if r[2] == "Proposed" and not lead.startswith("proposed"):
                fails.append(f"{where}: row says Proposed, the record's status does not begin with proposed")
            if lead.startswith("proposed") and r[2] != "Proposed":
                fails.append(f"{where}: the record's status begins with proposed, row says {r[2]}")
            low = status.lower()
            if ("nothing built" in low or "design only" in low) and r[3] not in ("Design only", "Nothing built"):
                fails.append(f"{where}: the record says nothing built or design only, row Evidence says {r[3]}")
    return fails


def rule_model(t: Tree) -> list[str]:
    fails = []
    pkgs = package_depths(t.masked)
    names = {n for n, _ in pkgs}
    named = set()
    for vid, text in t.view_text.items():
        for x in MODEL_RE.findall(text):
            named.add(x)
            if x not in names:
                fails.append(f"model: {vid}: marker names package {x}, which the model does not hold")
    for n, depth in pkgs:
        if depth == 1 and n not in named:
            fails.append(f"model: package {n} is named by no view")
    return fails


def capability_defs(t: Tree) -> tuple[set[str], set[str]]:
    """(all occurrence defs, non-abstract ones inside CapabilityTaxonomy)."""
    allp = {m.group(2) for m in re.finditer(r"\b(abstract\s+)?occurrence\s+def\s+(\w+)", t.masked)}
    m = re.search(r"\bpackage\s+CapabilityTaxonomy\s*\{", t.masked)
    concrete: set[str] = set()
    if m:
        depth, i = 0, m.end() - 1
        for i in range(m.end() - 1, len(t.masked)):
            depth += (t.masked[i] == "{") - (t.masked[i] == "}")
            if depth == 0:
                break
        body = t.masked[m.end():i]
        concrete = {c.group(2) for c in re.finditer(r"\b(abstract\s+)?occurrence\s+def\s+(\w+)", body)
                    if not c.group(1)}
    return allp, concrete


def rule_capabilities(t: Tree) -> list[str]:
    fails = []
    allp, concrete = capability_defs(t)
    if "Rs-Tr" not in t.view_text or "St-Tx" not in t.view_text:
        return ["capabilities: Rs-Tr or St-Tx is missing"]
    for r in first_table(t.view_text["Rs-Tr"]):
        if len(r) < 4:
            continue
        for name in (c.strip() for c in r[3].split(",")):
            if name and name not in allp:
                fails.append(f"capabilities: Rs-Tr row '{r[0][:40]}' names capability {name}, which is not an occurrence def in the model")
    got = sources_table(t.view_text["St-Tx"])
    blob = "\n".join(" | ".join(r) for r in got[1]) if got else ""
    for name in sorted(concrete):
        if not re.search(r"\b" + re.escape(name) + r"\b", blob):
            fails.append(f"capabilities: {name} is a capability in the model and appears in no St-Tx Sources row")
    return fails


def rule_trace(t: Tree) -> list[str]:
    fails = []
    for need in ("Rs-Tr", "Op-Pr", "Rs-Pr"):
        if need not in t.view_text:
            return [f"trace: view {need} is missing"]
    trace_rows = first_table(t.view_text["Rs-Tr"])
    in_trace = set()
    for r in trace_rows:
        m = re.match(r"A\d+(?:\.\d+)?\b", r[0]) if r else None
        if m:
            in_trace.add(m.group(0))
    opp = t.view_text["Op-Pr"]
    for aid in sorted(in_trace):
        if not re.search(r"(?<![\w.])" + re.escape(aid) + r"(?![\w]|\.\d)", opp):
            fails.append(f"trace: Rs-Tr names activity {aid}, which Op-Pr does not hold")
    acts = set(re.findall(r'"(A\d+(?:\.\d+)?) ', opp))
    for aid in sorted(acts):
        if not any(o.startswith(aid + ".") for o in acts) and aid not in in_trace:
            fails.append(f"trace: Op-Pr leaf activity {aid} is in no Rs-Tr row")
    funcs = {m.group(0) for r in first_table(t.view_text["Rs-Pr"]) if r
             for m in [re.match(r"F\d+\b", r[0])] if m}
    for r in trace_rows:
        if len(r) < 2:
            continue
        for f in re.findall(r"\bF\d+\b", r[1]):
            if f not in funcs:
                fails.append(f"trace: Rs-Tr row '{r[0][:40]}' names function {f}, which is not a row in Rs-Pr")
    return fails


def rule_outputs(t: Tree) -> list[str]:
    fails = []
    dodaf = {x for e in t.views.values() for x in ((e.get("exports") or {}).get("dodaf202") or [])}
    for x in REQUIRED_DODAF:
        if x not in dodaf:
            fails.append(f"outputs: no view exports {x} under dodaf202")
    for v in REQUIRED_VIEWS:
        if v not in t.views:
            fails.append(f"outputs: view {v} is missing")
    dx = t.profiles.get("data_exchange") or {}
    home = dx.get("home")
    if home not in t.views:
        fails.append(f"outputs: data_exchange.home {home} is not a view")
        return fails
    for prof in ("uaf", "dodaf202", "naf4"):
        ident = (dx.get(prof) or {}).get("id")
        if prof == "uaf":
            if ident not in t.views:
                fails.append(f"outputs: uaf data-exchange id {ident} is not a view")
        elif ident not in ((t.views[home].get("exports") or {}).get(prof) or []):
            fails.append(f"outputs: {prof} data-exchange id {ident} is not in {home}'s exports")
    return fails


def rule_generated(t: Tree) -> list[str]:
    home = (t.profiles.get("data_exchange") or {}).get("home")
    where = {vid: text.count(GEN_MARKER) for vid, text in t.view_text.items() if GEN_MARKER in text}
    total = sum(where.values())
    fails = []
    if total != 1:
        fails.append(f"generated: the data-exchange marker appears {total} times, expected once")
    for vid in sorted(where):
        if vid != home:
            fails.append(f"generated: the data-exchange marker is in {vid}, not in {home}")
    if total == 1 and home not in where:
        fails.append(f"generated: the data-exchange marker is not in {home}")
    return fails


CHECKS = [rule_exports, rule_appendix, rule_view_files, rule_slots, rule_links, rule_sources_table,
          rule_marks, rule_model, rule_capabilities, rule_trace, rule_outputs, rule_generated]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check the architecture views against the rules.")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    a = ap.parse_args(argv)
    try:
        tree = Tree(Path(a.root))
        fails: list[str] = []
        for check in CHECKS:
            fails += check(tree)
    except (InputError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INPUT
    for f in fails:
        print(f"FAIL: {f}", file=sys.stderr)
    if fails:
        return EXIT_CHECK
    print(f"ok: {len(RULES)} rules, {len(tree.views)} views")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
