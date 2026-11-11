#!/usr/bin/env python3
"""derived.py - the four tables a view takes from a declared artefact instead of writing it.

Each marker below belongs in one view and becomes a markdown table when the
view is rendered (render_profile.Renderer.view_text). check_views.py rule
`derived` fails on a marker that is missing, repeated or outside its view, and
on a table that cannot be built.

  <!-- generated: capability-dependencies -->  St-Cn  the roadmap note's
      `depends on` and `folds into` columns, joined to capability-record.yaml
      by each capability's `increment`
  <!-- generated: resource-taxonomy -->        Rs-Tx  package ResourceKit in
      model/openddil.sysml: what each type specialises, and where it is a part
  <!-- generated: ontology-dictionary -->      Am-If  ontology/*.yaml: each
      declared term with its entry count and field names, never an entry
  <!-- generated: adr-traceability -->        Am-Tr  decisions/ADR-*.md: each
      record with its status and the views that cite it, the accepted or
      proposed records no view cites first, joined to adr-exemptions.yaml

A depends-on cell has to name one increment, by its number or its name, and a
fold-in has to name an increment and cite an ADR that some capability in the
record cites. Anything else is a CheckError, so a roadmap edit cannot drop an
edge without the render failing. The tables carry no links: they are inserted
after links are rewritten. An accepted or proposed record that no view cites
and the exemptions file does not name is a CheckError, as is an exemption for
a record that a view cites or that is not in scope. Stdlib and PyYAML only.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

import capability_phases
import marks
from capability_phases import CheckError
from data_exchange import InputError

DEPENDENCIES_MARKER = "<!-- generated: capability-dependencies -->"
TAXONOMY_MARKER = "<!-- generated: resource-taxonomy -->"
DICTIONARY_MARKER = "<!-- generated: ontology-dictionary -->"
TRACE_MARKER = "<!-- generated: adr-traceability -->"
HOMES = {DEPENDENCIES_MARKER: "St-Cn", TAXONOMY_MARKER: "Rs-Tx", DICTIONARY_MARKER: "Am-If", TRACE_MARKER: "Am-Tr"}

ROADMAP_HEADER = ["#", "increment", "what isolates", "home", "depends on"]
FOLD_HEADER = ["row", "slice", "folds into", "why it costs the increment nothing"]
ADR_RE = re.compile(r"ADR-\d{4}")

# The term each ontology file declares, as a path into the file. Every file
# under ontology/ needs a row here, and every path has to resolve.
DICTIONARY = [
    ("asset_identity_aliases.yaml", "aliases.dis"),
    ("dis_appearance.yaml", "populating_sources"),
    ("dis_appearance.yaml", "appearance"),
    ("dis_condition.yaml", "level_order"),
    ("dis_condition.yaml", "source_order"),
    ("dis_condition.yaml", "appearance"),
    ("dis_condition.yaml", "emission.populating_sources"),
    ("dis_condition.yaml", "emission.baselines"),
    ("dis_condition.yaml", "data_health"),
    ("dis_entity_types.yaml", "mappings"),
    ("platform_reference.yaml", "platforms"),
    ("platform_variant_aliases.yaml", "aliases.dis"),
]


def bare(cell: str) -> str:
    return cell.replace("**", "").replace("`", "").strip()


def tables(text: str) -> list[list[list[str]]]:
    """Every pipe table in text, header row first, separator dropped."""
    out, cur = [], []
    for line in text.split("\n"):
        if line.lstrip().startswith("|"):
            row = capability_phases.split_row(line)
            if not all(re.fullmatch(r":?-+:?", c) for c in row if c):
                cur.append(row)
        elif cur:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def table_with(text: str, header: list[str], what: str) -> list[list[str]]:
    found = [t for t in tables(text) if t and t[0] == header]
    if len(found) != 1:
        raise CheckError(f"derived: the roadmap note has {len(found)} {what} tables, expected one\n")
    return found[0][1:]


# --- St-Cn ---------------------------------------------------------------------

def dependencies(record: dict, roadmap: str) -> str:
    rows = table_with(roadmap, ROADMAP_HEADER, "increment")
    folds = table_with(roadmap, FOLD_HEADER, "fold-in")
    names = [bare(r[1]) for r in rows]
    numbered = {bare(r[0]): bare(r[1]) for r in rows if bare(r[0]).isdigit()}
    caps = {k: (v or {}) for k, v in record["capabilities"].items()}
    by_inc: dict[str, list[str]] = {}
    for name, cap in caps.items():
        if cap.get("increment"):
            by_inc.setdefault(bare(cap["increment"]), []).append(name)
    fails = [f"derived: {c} names increment '{i}', which the roadmap note does not have"
             for i, cs in by_inc.items() if i not in names for c in cs]
    fails += [f"derived: increment '{n}' has no capability in the record" for n in names if n not in by_inc]

    def resolve(cell: str, inc: str) -> str | None:
        c = bare(cell)
        if c in ("—", "-", ""):
            return None
        m = re.match(r"(\d+)[:.]", c)
        if m:
            if m.group(1) not in numbered:
                fails.append(f"derived: '{inc}' depends on increment {m.group(1)}, which the note does not number")
            return numbered.get(m.group(1))
        hits = [n for n in names if n.lower() in c.lower() and n != inc]
        if len(hits) != 1:
            fails.append(f"derived: '{inc}' depends on '{c[:60]}', which names {len(hits)} increments, expected one")
            return None
        return hits[0]

    out = ["| Increment | Capability | Depends on | Relation |", "|---|---|---|---|"]
    for r in rows:
        inc = bare(r[1])
        dep = resolve(r[4], inc)
        cap = ", ".join(by_inc.get(inc, []))
        if dep is None:
            out.append(f"| {inc} | {cap} | none | Done first |" if not bare(r[0]).isdigit()
                       else f"| {inc} | {cap} | none | |")
        else:
            out.append(f"| {inc} | {cap} | {dep}: {', '.join(by_inc.get(dep, []))} | Needs |")
    for r in folds:
        slice_name = re.sub(r"\s*\(.*$", "", bare(r[1]))
        m = re.search(r"increment (\d+)", bare(r[2]))
        adrs = ADR_RE.findall(r[1])
        owners = sorted({n for n, cap in caps.items() if set(adrs) & set(capability_phases.record_adrs(cap))})
        if not m or m.group(1) not in numbered:
            fails.append(f"derived: fold-in {bare(r[0])} names no numbered increment")
            continue
        if not owners:
            fails.append(f"derived: fold-in {bare(r[0])} cites {', '.join(adrs) or 'no ADR'}, which no capability cites")
            continue
        inc = numbered[m.group(1)]
        out.append(f"| {slice_name} (fold-in {bare(r[0])}) | {', '.join(owners)} | {inc}: "
                   f"{', '.join(by_inc.get(inc, []))} | Rides with, not a dependency |")
    if fails:
        raise CheckError("".join(f + "\n" for f in fails))
    return "\n".join(out)


# --- Rs-Tx ---------------------------------------------------------------------

def taxonomy(sysml: str, masked: str) -> str:
    from render_profile import match_brace  # render_profile imports this module
    m = re.search(r"\bpackage\s+ResourceKit\s*\{", masked)
    if not m:
        raise CheckError("derived: the model has no package ResourceKit\n")
    start, end = m.end(), match_brace(masked, m.end() - 1)
    body = masked[start:end]
    defs: dict[str, tuple[bool, str | None]] = {}
    used: dict[str, list[str]] = {}
    for d in re.finditer(r"^\s*(abstract\s+)?part\s+def\s+(\w+)\s*(?::>\s*(\w+))?\s*([;{])", body, re.M):
        defs[d.group(2)] = (bool(d.group(1)), d.group(3))
        if d.group(4) == "{":
            at = d.end() - 1
            inner = body[at + 1:match_brace(body, at)]
            for p in re.finditer(r"^\s*part\s+(\w+)\s*:\s*(\w+)\s*(\[[^\]]*\])?\s*;", inner, re.M):
                used.setdefault(p.group(2), []).append(f"{d.group(2)}.{p.group(1)} {p.group(3) or '(multiplicity not stated)'}")
    if not defs:
        raise CheckError("derived: package ResourceKit defines no part\n")
    fails = [f"derived: {n} specialises {s}, which ResourceKit does not define"
             for n, (_, s) in defs.items() if s and s not in defs]
    fails += [f"derived: a part is typed {t}, which ResourceKit does not define" for t in used if t not in defs]
    if fails:
        raise CheckError("".join(f + "\n" for f in fails))
    out = ["| Type | Kind | Specialises | Is a part of, with multiplicity |", "|---|---|---|---|"]
    for n, (abstract, sup) in defs.items():
        kind = "abstract" if abstract else ("composite" if any(u.startswith(n + ".") for us in used.values() for u in us) else "member")
        out.append(f"| {n} | {kind} | {sup or 'none'} | {'; '.join(used.get(n, [])) or 'none'} |")
    return "\n".join(out)


# --- Am-If ---------------------------------------------------------------------

def dictionary(ontology_dir: Path) -> str:
    try:
        present = sorted(p.name for p in ontology_dir.glob("*.yaml"))
    except OSError as e:
        raise InputError(f"cannot list {ontology_dir}: {e}")
    declared = {f for f, _ in DICTIONARY}
    fails = [f"derived: ontology/{f} has no dictionary row" for f in present if f not in declared]
    fails += [f"derived: the dictionary names ontology/{f}, which does not exist" for f in sorted(declared) if f not in present]
    if fails:
        raise CheckError("".join(f + "\n" for f in fails))
    loaded: dict[str, object] = {}
    out = ["| File | Term | Kind | Entries | Fields |", "|---|---|---|---|---|"]
    for f, path in DICTIONARY:
        if f not in loaded:
            try:
                loaded[f] = yaml.safe_load((ontology_dir / f).read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError) as e:
                raise InputError(f"cannot read ontology/{f}: {e}")
        node = loaded[f]
        for k in path.split("."):
            if not isinstance(node, dict) or k not in node:
                raise CheckError(f"derived: ontology/{f} has no {path}\n")
            node = node[k]
        if node == [] or node == {}:
            kind, count, fields = ("empty list" if node == [] else "empty map"), 0, []
        elif isinstance(node, list):
            dicts = [e for e in node if isinstance(e, dict)]
            if dicts and len(dicts) != len(node):
                raise CheckError(f"derived: ontology/{f} {path} mixes records and values\n")
            kind, count = ("records" if dicts else "values"), len(node)
            fields = sorted({k for e in dicts for k in e})
        elif isinstance(node, dict):
            if node and all(isinstance(v, dict) for v in node.values()):
                kind, count = "map of records", len(node)
                fields = sorted({str(k) for v in node.values() for k in v})
            else:
                kind, count, fields = "record", len(node), [str(k) for k in node]
        else:
            raise CheckError(f"derived: ontology/{f} {path} is a single value, not a term\n")
        fields = [x for x in fields if not x.startswith("_")]
        out.append(f"| {f} | {path} | {kind} | {count} | {', '.join(fields) or 'none'} |")
    return "\n".join(out)


EXEMPT_CATEGORIES = ("rule", "infrastructure", "process", "alignment")
NOT_REQUIRED = ("superseded", "rejected", "deprecated", "withdrawn")
VIEW_ADR_RE = re.compile(r"ADR-(\d{4})(?!\d)")


def cell(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().replace("|", "\\|")


def adr_class(adr: str, text: str) -> str:
    status = marks.adr_status(text)
    norm = (status or "").replace("*", "").strip().lower()
    for word in ("accepted", "proposed") + NOT_REQUIRED:
        if norm.startswith(word):
            return word.capitalize()
    raise CheckError(f"derived: {adr} has no status beginning accepted, proposed, "
                     "superseded, rejected, deprecated or withdrawn\n")


def traceability(decisions: Path, views: Path, record: dict, exemptions: Path) -> str:
    try:
        files = sorted(decisions.glob("ADR-*.md"))
    except OSError as e:
        raise InputError(f"cannot list {decisions}: {e}")
    fails: list[str] = []
    info: dict[str, tuple[str, str]] = {}
    for p in files:
        m = re.match(r"ADR-\d{4}", p.name)
        if not m:
            continue
        adr = m.group(0)
        try:
            text = p.read_text(encoding="utf-8")
        except OSError as e:
            raise InputError(f"cannot read {p}: {e}")
        line = next((l for l in text.split("\n") if l.startswith("# ")), None)
        if line is None:
            fails.append(f"derived: {adr} has no '# ' title line")
            continue
        title = re.sub(r"^ADR-\d{4}", "", line[2:].strip())
        title = re.sub(r"^\s*[:—–-]\s*", "", title).strip()
        # The framework's name appears only in the attribution line, which a
        # deployment can drop, so a title prints it as "the framework".
        title = re.sub(r"\bOpenDDIL\b", "the framework", title)
        try:
            info[adr] = (title, adr_class(adr, text))
        except CheckError as e:
            fails.append(str(e).rstrip("\n"))
    cited: dict[str, set[str]] = {}
    try:
        view_files = sorted(views.glob("*.md"))
    except OSError as e:
        raise InputError(f"cannot list {views}: {e}")
    for v in view_files:
        if v.stem == "Am-Tr":
            continue
        try:
            vt = v.read_text(encoding="utf-8")
        except OSError as e:
            raise InputError(f"cannot read {v}: {e}")
        for n in VIEW_ADR_RE.findall(re.sub(r"<!--.*?-->", "", vt, flags=re.DOTALL)):
            cited.setdefault(f"ADR-{n}", set()).add(v.stem)
    for cap in (record.get("capabilities") or {}).values():
        if not isinstance(cap, dict):
            continue
        for a in cap.get("adrs") or []:
            cited.setdefault(capability_phases.adr_id(a), set()).add("St-Rm-P")
        for o in cap.get("still_open") or []:
            if isinstance(o, dict) and o.get("adr"):
                cited.setdefault(capability_phases.adr_id(o["adr"]), set()).add("St-Rm-P")
    try:
        data = yaml.safe_load(exemptions.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise InputError(f"cannot read {exemptions}: {e}")
    if not isinstance(data, dict):
        raise InputError(f"{exemptions}: expected a map")
    for k in data:
        if k != "exempt":
            fails.append(f"derived: adr-exemptions.yaml has top-level key {k!r}, not 'exempt'")
    exempt = data.get("exempt") or {}
    if not isinstance(exempt, dict):
        raise InputError(f"{exemptions}: 'exempt' is not a map")
    for adr, ent in sorted(exempt.items(), key=lambda kv: str(kv[0])):
        adr = str(adr)
        if not isinstance(ent, dict):
            fails.append(f"derived: exemption {adr} is not a map of category and reason")
            continue
        for k in ent:
            if k not in ("category", "reason"):
                fails.append(f"derived: exemption {adr} has key {k!r}, not category or reason")
        if ent.get("category") not in EXEMPT_CATEGORIES:
            fails.append(f"derived: exemption {adr} has category {ent.get('category')!r}, "
                         f"not one of {', '.join(EXEMPT_CATEGORIES)}")
        if not str(ent.get("reason") or "").strip():
            fails.append(f"derived: exemption {adr} has no reason")
        if adr not in info:
            fails.append(f"derived: exemption {adr} names no decision record")
            continue
        if cited.get(adr):
            fails.append(f"derived: exemption {adr} is stale: it is cited by {', '.join(sorted(cited[adr]))}")
        if info[adr][1] not in ("Accepted", "Proposed"):
            fails.append(f"derived: exemption {adr} is not in scope: its status is {info[adr][1].lower()}")
    for adr, (_, status) in sorted(info.items()):
        if status in ("Accepted", "Proposed") and not cited.get(adr) and adr not in exempt:
            fails.append(f"derived: {adr} ({status}) is cited by no view and is not in adr-exemptions.yaml")
    if fails:
        raise CheckError("".join(f + "\n" for f in fails))
    scope = [a for a, (_, s) in info.items() if s in ("Accepted", "Proposed")]
    out_of = [a for a in sorted(info) if a not in scope]
    n_cited = sum(1 for a in scope if cited.get(a))
    n_ex = len(scope) - n_cited
    out = [f"{len(info)} decision records. {len(scope)} accepted or proposed: {n_cited} cited by a view, "
           f"{n_ex} exempt. {len(out_of)} not required.", "",
           "| Not cited | Status | Category | Reason |", "|---|---|---|---|"]
    for a in sorted(scope):
        if not cited.get(a):
            e = exempt[a]
            out.append(f"| {cell(a + ' ' + info[a][0])} | {info[a][1]} | {cell(e['category'])} | {cell(e['reason'])} |")
    if out_of:
        out += ["", "| Not required | Status | Cited by |", "|---|---|---|"]
        for a in out_of:
            out.append(f"| {cell(a + ' ' + info[a][0])} | {info[a][1]} | {cell(', '.join(sorted(cited.get(a, ()))) or 'none')} |")
    out += ["", "| ADR | Status | Cited by |", "|---|---|---|"]
    for a in sorted(info):
        out.append(f"| {a} | {info[a][1]} | {cell(', '.join(sorted(cited.get(a, ()))) or 'none')} |")
    return "\n".join(out)


def build(marker: str, root: Path, record_path: Path, sysml: str, masked: str) -> str:
    """The table for one marker. root is docs/arch."""
    repo = root.parent.parent
    if marker == DEPENDENCIES_MARKER:
        record = capability_phases.load_record(record_path)
        try:
            roadmap = (repo / "decisions" / capability_phases.ROADMAP).read_text(encoding="utf-8")
        except OSError as e:
            raise InputError(f"cannot read the roadmap note: {e.strerror or e}")
        return dependencies(record, roadmap)
    if marker == TAXONOMY_MARKER:
        return taxonomy(sysml, masked)
    if marker == DICTIONARY_MARKER:
        return dictionary(repo / "ontology")
    if marker == TRACE_MARKER:
        return traceability(repo / "decisions", root / "views",
                            capability_phases.load_record(record_path), root / "adr-exemptions.yaml")
    raise KeyError(marker)
