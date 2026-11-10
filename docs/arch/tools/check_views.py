#!/usr/bin/env python3
"""check_views.py - check the architecture views against the rules that keep them honest.

Reads docs/arch (views, profiles.yaml, slots.yaml, README.md, INVENTORY.md,
the SysML model) and the decision records the views cite. Writes one
`FAIL: <rule>: <what>` line per finding on stderr, and exits 1 if there is
any. When nothing fails it prints an `ok:` count line.

Usage:
    python docs/arch/tools/check_views.py [--root docs/arch] \
        --chart DIR --values FILE [--values FILE ...] --release NAME \
        --readiness FILE --barred FILE [--barred FILE ...]
    python docs/arch/tools/check_views.py [--root docs/arch] --allow-partial REASON

Rules: exports, appendix-a, view-files, slots, links, sources-table,
marks, model, capabilities, trace, outputs, generated, phases, derived,
quotes, floor.
`quotes` and `floor` need the chart, its values, the release name, the
readiness doc and the barred list, so a call that omits any of the five
exits 2. A check that quietly does less is the bug it exists to catch.
--allow-partial REASON runs the first fourteen and says so in its ok line.
`slots` also fails on a `none yet` slot with no line in INVENTORY.md's slot
table, and on a line there for a slot that has a source.
`marks` reads the status line of every record in decisions/ that a Sources row
cites (marks.py). Where the status line fixes the Evidence, the cell must say
`Status line` and the render fills it in, so no two views read one record two ways.
The vocabularies for
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

import capability_floor
import capability_phases
import data_exchange
import derived
import marks
from marks import adr_status
from render_profile import mask_sysml, package_depths

EXIT_OK, EXIT_CHECK, EXIT_INPUT = 0, 1, 2
RULES = ["exports", "appendix-a", "view-files", "slots", "links", "sources-table",
         "marks", "model", "capabilities", "trace", "outputs", "generated", "phases", "derived", "quotes", "floor"]
APPENDIX_HEADER = "| View | Name | DoDAF 2.02 | NAF 4.0 | DNDAF |"
APPENDIX_COLUMNS = {"dodaf202": 2, "naf4": 3}
SOURCES_HEADER = "| Claim | Source | Decision | Evidence |"
SLOT_INVENTORY_HEADER = "| Slot | Declaration that would fill it | Artefact |"
GEN_MARKER = "<!-- generated: data-exchange -->"
PHASES_MARKER = "<!-- generated: capability-phases -->"
PHASES_HOME = "St-Rm-P"
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
    inventory = t.text(t.root / "INVENTORY.md").split("\n")
    at = [i for i, ln in enumerate(inventory) if ln.strip() == SLOT_INVENTORY_HEADER]
    if len(at) != 1:
        return fails + [f"slots: INVENTORY.md has {len(at)} slot tables, expected one"]
    _, rows = table_after(inventory, at[0])
    lined = {r[0].strip("` ") for r in rows if r}
    for name in sorted(registry):
        none_yet = str((registry[name] or {}).get("source") or "").startswith("none yet")
        if none_yet and name not in lined:
            fails.append(f"slots: {name} has no source and no line in INVENTORY.md saying what would fill it")
        if not none_yet and name in lined:
            fails.append(f"slots: {name} has a source in slots.yaml and still a line in INVENTORY.md's slot table")
    for name in sorted(lined - set(registry)):
        fails.append(f"slots: INVENTORY.md's slot table names {name}, which slots.yaml does not hold")
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
    decisions = t.root.parent.parent / "decisions"
    for vid, text in t.view_text.items():
        got = sources_table(text)
        if got is None or got[0] != SOURCES_HEADER:
            continue
        for r in got[1]:
            if len(r) != 4:
                continue
            claim = r[0][:50]
            records = marks.cited_records(r[1], t.root / "views", decisions)
            if not records:
                if r[3] == marks.STATUS_TOKEN:
                    fails.append(f"marks: {vid}: row '{claim}' says {marks.STATUS_TOKEN} and cites no record")
                continue
            first = records[0]
            where = f"marks: {vid}: row '{claim}' cites {first.name}"
            if not first.is_file():
                fails.append(f"{where}, which does not exist")
                continue
            status = adr_status(first.read_text(encoding="utf-8"))
            if not status:
                fails.append(f"{where}, which states no status")
                continue
            lead = status.lstrip("*").lstrip().lower()
            if r[2] == "Proposed" and not lead.startswith("proposed"):
                fails.append(f"{where}: row says Proposed, the record's status does not begin with proposed")
            if lead.startswith("proposed") and r[2] != "Proposed":
                fails.append(f"{where}: the record's status begins with proposed, row says {r[2]}")
            try:
                value, each = marks.row_evidence(r[1], t.root / "views", decisions)
            except marks.InputError as e:
                fails.append(f"marks: {vid}: row '{claim}' {e}")
                continue
            fixing = ", ".join(n for n, v in each if v)
            if value and r[3] != marks.STATUS_TOKEN:
                fails.append(f"marks: {vid}: row '{claim}': the status line of {fixing} fixes the Evidence "
                             f"as {value}, so the cell must say {marks.STATUS_TOKEN}, not {r[3]}")
            if not value and r[3] == marks.STATUS_TOKEN:
                fails.append(f"marks: {vid}: row '{claim}' says {marks.STATUS_TOKEN} and no record it cites "
                             f"fixes the evidence")
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
    for activity in sorted(in_trace):
        if not re.search(r"(?<![\w.])" + re.escape(activity) + r"(?![\w]|\.\d)", opp):
            fails.append(f"trace: Rs-Tr names activity {activity}, which Op-Pr does not hold")
    acts = set(re.findall(r'"(A\d+(?:\.\d+)?) ', opp))
    for activity in sorted(acts):
        if not any(o.startswith(activity + ".") for o in acts) and activity not in in_trace:
            fails.append(f"trace: Op-Pr leaf activity {activity} is in no Rs-Tr row")
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


def rule_phases(t: Tree) -> list[str]:
    where = {vid: text.count(PHASES_MARKER) for vid, text in t.view_text.items() if PHASES_MARKER in text}
    total = sum(where.values())
    fails = []
    if total != 1:
        fails.append(f"phases: the capability-phases marker appears {total} times, expected once")
    for vid in sorted(where):
        if vid != PHASES_HOME:
            fails.append(f"phases: the capability-phases marker is in {vid}, not in {PHASES_HOME}")
    if total == 1 and PHASES_HOME not in where:
        fails.append(f"phases: the capability-phases marker is not in {PHASES_HOME}")
    try:
        record = capability_phases.load_record(t.root / "capability-record.yaml")
        capabilities = capability_phases.model_capabilities(t.sysml)
    except capability_phases.InputError as e:
        raise InputError(str(e))
    decisions = t.root.parent.parent / "decisions"
    return fails + [f"phases: {f}" for f in capability_phases.check_record(record, capabilities, decisions)]


def rule_derived(t: Tree) -> list[str]:
    """Each derived.py marker is in its own view once, and its table builds."""
    fails = []
    for mk, home in derived.HOMES.items():
        where = {vid: text.count(mk) for vid, text in t.view_text.items() if mk in text}
        if sum(where.values()) != 1 or home not in where:
            fails.append(f"derived: {mk} appears {sum(where.values())} times, in "
                         f"{', '.join(sorted(where)) or 'no view'}; expected once, in {home}")
        try:
            derived.build(mk, t.root, t.root / "capability-record.yaml", t.sysml, t.masked)
        except capability_phases.CheckError as e:
            fails += [f for f in str(e).splitlines() if f]
        except data_exchange.InputError as e:
            raise InputError(str(e))
    return fails


def rule_quotes(t: Tree, a: argparse.Namespace) -> list[str]:
    """The evidence the table prints, and the record's own text, carry no barred value."""
    try:
        record = capability_phases.load_record(t.root / "capability-record.yaml")
        capabilities = capability_phases.model_capabilities(t.sysml)
        decisions = t.root.parent.parent / "decisions"
        readiness = t.text(Path(a.readiness))
        try:
            capability_phases.render_table(record, capabilities, decisions, Path(a.chart) / "templates", readiness)
            cells = capability_phases.evidence_cells(record, readiness)
        except capability_phases.CheckError as e:
            return [f for f in str(e).splitlines() if f]
        barred = capability_phases.load_barred(a.barred)
    except capability_phases.InputError as e:
        raise InputError(str(e))
    except capability_phases.CheckError as e:
        raise InputError(str(e))
    cells["the record"] = [t.text(t.root / "capability-record.yaml")]
    return capability_phases.scan_barred(cells, barred)


def rule_floor(t: Tree, a: argparse.Namespace) -> list[str]:
    """The render's workloads, kinds, flags and routes are claimed, and what claims them is built."""
    try:
        record = capability_phases.load_record(t.root / "capability-record.yaml")
        capabilities = capability_phases.model_capabilities(t.sysml)
        statuses = capability_phases.statuses_of(record, t.root.parent.parent / "decisions")
        items, _ = capability_floor.render_inputs(a.chart, a.values, a.release)
    except data_exchange.InputError as e:
        raise InputError(str(e))
    try:
        return capability_floor.check_floor(record, capabilities, statuses, items)
    except capability_phases.CheckError as e:
        return [str(e)]


CHECKS = [rule_exports, rule_appendix, rule_view_files, rule_slots, rule_links, rule_sources_table,
          rule_marks, rule_model, rule_capabilities, rule_trace, rule_outputs, rule_generated, rule_phases,
          rule_derived]


PARTIAL_FLAGS = [("--chart", "chart"), ("--values", "values"), ("--release", "release"),
                 ("--readiness", "readiness"), ("--barred", "barred")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check the architecture views against the rules.")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument("--chart", help="the chart directory the floor renders and the table reads templates from")
    ap.add_argument("--values", action="append", default=[], help="a values file, in order (repeatable)")
    ap.add_argument("--release", help="the Helm release name")
    ap.add_argument("--readiness", help="the readiness document the evidence quotes come from")
    ap.add_argument("--barred", action="append", default=[], help="a barred list file (repeatable)")
    ap.add_argument("--allow-partial", metavar="REASON", help="run without quotes and floor, and say why")
    a = ap.parse_args(argv)
    missing = [flag for flag, dest in PARTIAL_FLAGS if not getattr(a, dest)]
    if a.allow_partial is not None and not a.allow_partial.strip():
        print("error: --allow-partial needs a reason", file=sys.stderr)
        return EXIT_INPUT
    if a.allow_partial is not None and not missing:
        print("error: --allow-partial given but all five inputs are too (stale exception)", file=sys.stderr)
        return EXIT_INPUT
    if missing and a.allow_partial is None:
        print(f"error: {', '.join(missing)} not given; give them, or --allow-partial REASON", file=sys.stderr)
        return EXIT_INPUT
    try:
        tree = Tree(Path(a.root))
        fails: list[str] = []
        for check in CHECKS:
            fails += check(tree)
        if not missing:
            fails += rule_quotes(tree, a)
            fails += rule_floor(tree, a)
    except (InputError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INPUT
    for f in fails:
        print(f"FAIL: {f}", file=sys.stderr)
    if fails:
        return EXIT_CHECK
    if missing:
        print(f"ok: {len(CHECKS)} rules, {len(tree.views)} views; not run: quotes, floor ({a.allow_partial})")
    else:
        print(f"ok: {len(RULES)} rules, {len(tree.views)} views")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
