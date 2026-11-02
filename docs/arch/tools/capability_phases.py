#!/usr/bin/env python3
"""capability_phases.py - the phase and evidence of every St-Tx capability, from the record.

Reads docs/arch/capability-record.yaml, which says for each capability in the
model's CapabilityTaxonomy what it cites: decision records, chart templates,
register rows, readiness entries. Nothing in the record states a phase or
evidence; both are computed here, and every citation has to resolve against
the file it names or the render fails.

Phases, highest first:
    measured          cites a readiness entry under `measured`
    built unmeasured  cites a chart template under `built`, and no readiness entry
    accepted design   cites an ADR whose Status begins with accepted
    proposed          cites an ADR whose Status begins with proposed, or a
                      `still_open` citation
    row               cites only rows in a register
A capability that cites none of these has no phase, and that is a failure.

Evidence comes from the readiness doc only: an entry is an anchor line that
holds a date, and a quote is the cited line. A decision record's wording is
never read for evidence, only its Status line. A message names the record's
own text (capability, entry, anchor, line); it never echoes a readiness line.

Used by render_profile.py (the St-Rm-P marker) and check_views.py (the
`phases` rule). This module writes no file. Stdlib and PyYAML only.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from data_exchange import InputError

PHASES = ["measured", "built unmeasured", "accepted design", "proposed", "row"]
NOT_MEASURED = "not measured"
FOLLOW_UPS = "FOLLOW-UPS.md"
DEBT = "GENERALIZATION-DEBT.md"
ROADMAP = "ROADMAP-2026-10-29-isolation-increments.md"
REGISTER_HEADER = ["ID", "Subject", "Status"]
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
OUTPUT_FIELDS = ("phase", "evidence")
SECTIONS = ("lanes", "labs", "entries", "capabilities")


class CheckError(Exception):
    """A citation did not resolve: exit 1. Carries stderr to pass through."""


# --- record and model ---------------------------------------------------------

def load_record(path) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            record = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise InputError(f"cannot read {path}: {e}")
    if not isinstance(record, dict):
        raise InputError(f"{path}: expected a map")
    for key in SECTIONS:
        if not isinstance(record.get(key), dict):
            raise InputError(f"{path}: '{key}' is missing or is not a map")
    return record


def model_capabilities(sysml_text: str) -> dict[str, str]:
    """Concrete capability name to its direct parent, in model order, from CapabilityTaxonomy."""
    from render_profile import mask_sysml, match_brace  # render_profile imports this module
    masked = mask_sysml(sysml_text)
    m = re.search(r"\bpackage\s+CapabilityTaxonomy\s*\{", masked)
    if not m:
        raise InputError("the model has no package CapabilityTaxonomy")
    body = masked[m.end():match_brace(masked, m.end() - 1)]
    return {c.group(1): c.group(2)
            for c in re.finditer(r"^\s*occurrence\s+def\s+(\w+)\s*:>\s*(\w+)\s*;", body, re.M)}


# --- reading the decisions ----------------------------------------------------

def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def adr_file(decisions_dir: Path, adr: str) -> Path | None:
    found = sorted(Path(decisions_dir).glob(f"{adr}-*.md"))
    return found[0] if len(found) == 1 else None


def adr_lead(decisions_dir: Path, adr: str) -> str | None:
    """The file's status, lowercased, leading `*` and space stripped; None if there is no file or status."""
    from check_views import adr_status  # check_views imports render_profile, which imports this module
    path = adr_file(decisions_dir, adr)
    text = read_text(path) if path else None
    status = adr_status(text) if text is not None else None
    return status.lstrip("* ").lower() if status else None


def record_adrs(cap: dict) -> list[str]:
    return list(cap.get("adrs") or [])


def still_open(cap: dict) -> list[dict]:
    return list(cap.get("still_open") or [])


def statuses_of(record: dict, decisions_dir) -> dict[str, str | None]:
    """ADR id to the file's lead status, for every ADR the record cites."""
    ids = set()
    for cap in record["capabilities"].values():
        cap = cap or {}
        ids.update(record_adrs(cap))
        ids.update(s.get("adr") for s in still_open(cap) if isinstance(s, dict))
    return {i: adr_lead(Path(decisions_dir), i) for i in sorted(i for i in ids if i)}


def split_row(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def register_rows(text: str) -> dict[str, str]:
    """Row id to status, for every `| ID | Subject | Status |` register in the text."""
    out: dict[str, str] = {}
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|") or split_row(line) != REGISTER_HEADER:
            continue
        for nxt in lines[i + 2:]:
            if not nxt.lstrip().startswith("|"):
                break
            cells = split_row(nxt)
            if len(cells) >= 3:
                out.setdefault(cells[0], cells[-1])
    return out


def roadmap_rows(text: str) -> list[list[str]]:
    return [split_row(ln) for ln in text.split("\n") if ln.lstrip().startswith("|")]


def roadmap_row(rows: list[list[str]], increment: str) -> list[str] | None:
    exact = [r for r in rows if len(r) > 1 and r[1] == increment]
    return (exact or [r for r in rows if any(increment in c for c in r)] or [None])[0]


def index_status(index_text: str, adr: str) -> str | None:
    """The bold status the decisions index gives an ADR, when it begins accepted or proposed."""
    m = re.search(rf"\[{re.escape(adr)}:[^\n]*?\)\s*—\s*\*\*(accepted|proposed)", index_text, re.I)
    return m.group(1).lower() if m else None


# --- the record against the decisions -----------------------------------------

def check_record(record: dict, capabilities: dict[str, str], decisions_dir) -> list[str]:
    """Every failure, one line each. Needs no chart and no readiness doc."""
    decisions_dir = Path(decisions_dir)
    fails: list[str] = []
    caps = {k: (v or {}) for k, v in record["capabilities"].items()}
    for name in capabilities:
        if name not in caps:
            fails.append(f"{name} is a capability in the model and has no entry in the record")
    for name in caps:
        if name not in capabilities:
            fails.append(f"{name} is in the record and is not a capability in the model")
    for parent in dict.fromkeys(capabilities.values()):
        if parent not in record["lanes"]:
            fails.append(f"{parent} has no lanes entry in the record")
    for key, entry in record["entries"].items():
        entry = entry or {}
        if entry.get("lab") not in record["labs"]:
            fails.append(f"entry {key} names lab {entry.get('lab')}, which labs does not declare")
        for f in OUTPUT_FIELDS:
            if f in entry:
                fails.append(f"entry {key} has a field '{f}': phase and evidence are computed, not recorded")

    index_text = read_text(decisions_dir / "README.md")
    follow = read_text(decisions_dir / FOLLOW_UPS)
    debt = read_text(decisions_dir / DEBT)
    road = read_text(decisions_dir / ROADMAP)
    registers = register_rows(follow) if follow is not None else {}
    road_rows = roadmap_rows(road) if road is not None else []
    for label, text in ((f"decisions/{FOLLOW_UPS}", follow), (f"decisions/{DEBT}", debt),
                        (f"decisions/{ROADMAP}", road), ("decisions/README.md", index_text)):
        if text is None:
            fails.append(f"{label} cannot be read")

    seen_adrs: set[str] = set()

    def check_adr(name: str, adr: str) -> str | None:
        path = adr_file(decisions_dir, adr)
        if path is None:
            if adr not in seen_adrs:
                fails.append(f"{name}: {adr} is not exactly one file in decisions/")
            seen_adrs.add(adr)
            return None
        lead = adr_lead(decisions_dir, adr)
        if adr not in seen_adrs:
            if index_text is not None and f"[{adr}:" not in index_text:
                fails.append(f"{name}: {adr} is not in decisions/README.md")
            if not lead or not lead.startswith(("accepted", "proposed")):
                fails.append(f"{name}: {adr} has no readable ## Status line beginning accepted or proposed")
        seen_adrs.add(adr)
        return lead

    for name, cap in caps.items():
        for f in OUTPUT_FIELDS:
            if f in cap:
                fails.append(f"{name} has a field '{f}': phase and evidence are computed, not recorded")
        if not any(cap.get(k) for k in ("adrs", "built", "measured", "still_open", "rows")):
            fails.append(f"{name} has no phase")
        for adr in record_adrs(cap):
            check_adr(name, adr)
        for item in still_open(cap):
            adr, says = (item or {}).get("adr"), (item or {}).get("says")
            if not adr or not says:
                fails.append(f"{name}: a still_open citation needs adr and says")
                continue
            check_adr(name, adr)
            path = adr_file(decisions_dir, adr)
            text = read_text(path) if path else None
            if text is not None and says not in text:
                fails.append(f"{name}: {adr} does not contain {says!r}")
        for row in cap.get("rows") or []:
            status = registers.get(row)
            if follow is not None and status is None:
                fails.append(f"{name}: row {row} is not in a | ID | Subject | Status | register in decisions/{FOLLOW_UPS}")
            elif status is not None and status.lstrip("* ").lower().startswith("fixed"):
                fails.append(f"{name}: row {row} is {status}, not open")
            if row.startswith("GD-") and debt is not None and not re.search(
                    rf"(?<![\w-]){re.escape(row)}(?![\w-])", debt):
                fails.append(f"{name}: row {row} is not in decisions/{DEBT}")
        increment = cap.get("increment")
        if increment and road is not None and roadmap_row(road_rows, increment) is None:
            fails.append(f"{name}: increment {increment} is not on a table row of decisions/{ROADMAP}")
        for m in cap.get("measured") or []:
            if (m or {}).get("entry") not in record["entries"]:
                fails.append(f"{name}: measured names entry {(m or {}).get('entry')}, which entries does not declare")
    return fails


def phase_of(cap: dict, statuses: dict[str, str | None]) -> str | None:
    """The highest phase the capability's citations give. `statuses` is from statuses_of."""
    cap = cap or {}
    leads = [(statuses.get(a) or "") for a in record_adrs(cap)]
    if cap.get("measured"):
        return "measured"
    if cap.get("built"):
        return "built unmeasured"
    if any(s.startswith("accepted") for s in leads):
        return "accepted design"
    if any(s.startswith("proposed") for s in leads) or still_open(cap):
        return "proposed"
    if cap.get("rows"):
        return "row"
    return None


# --- the document -------------------------------------------------------------

def quote_of(lines: list[str], at: int) -> str:
    """The cited readiness line, as a short quote."""
    first = lines[at].strip()
    if first.startswith("|"):
        cells = [c for c in split_row(first) if c]
        if cells and re.match(r"^\d+(\.\d+)?$", cells[0]):
            cells = cells[1:]
        text = ": ".join(cells)
    else:
        parts: list[str] = []
        for j, raw in enumerate(lines[at:at + 6]):
            s = raw.strip()
            if j == 0:
                s = re.sub(r"^[*-] ", "", s)
            if ". " in s:
                parts.append(s[:s.index(". ") + 1])
                break
            if s.endswith("."):
                parts.append(s)
                break
            parts.append(s)
        text = " ".join(parts)
    return text.replace("**", "").replace("|", "\\|")


def resolve_entries(record: dict, readiness_lines: list[str]) -> tuple[dict, list[str]]:
    """Entry name to (anchor line index, date, section), and the failures."""
    found, fails = {}, []
    for key, entry in record["entries"].items():
        anchor = (entry or {}).get("anchor")
        if not anchor:
            fails.append(f"entry {key} has no anchor")
            continue
        hits = [i for i, ln in enumerate(readiness_lines) if anchor in ln]
        if len(hits) != 1:
            fails.append(f"entry {key}: anchor {anchor!r} is on {len(hits)} readiness lines, expected one")
            continue
        at = hits[0]
        date = DATE_RE.search(readiness_lines[at])
        if not date:
            fails.append(f"entry {key}: the line of anchor {anchor!r} holds no date")
            continue
        head = next((j for j in range(at, -1, -1) if readiness_lines[j].startswith("## ")), None)
        if head is None:
            fails.append(f"entry {key}: anchor {anchor!r} has no ## heading above it")
            continue
        found[key] = (at, date.group(0), readiness_lines[head][3:].split(" — ")[0].strip())
    return found, fails


def measured_line(readiness_lines: list[str], at: int, text: str) -> list[int]:
    """Indexes of the lines holding text, from the anchor to the next ## or ### heading."""
    hits = []
    for i in range(at, len(readiness_lines)):
        ln = readiness_lines[i]
        if i > at and ln.startswith(("## ", "### ")):
            break
        if text in ln:
            hits.append(i)
    return hits


def lab_sentence(labs: dict, used: list[str]) -> str:
    parts = [f"{'Lab' if i == 0 else 'lab'} {k}{' is' if i == 0 else ''} {labs[k]}"
             for i, k in enumerate(used)]
    if len(parts) > 1:
        parts = [", ".join(parts[:-1]) + " and " + parts[-1]] if len(parts) > 2 else [" and ".join(parts)]
    return parts[0] + "." if parts else ""


def resolve_quotes(record: dict, readiness: list[str], entries: dict | None = None) -> tuple[dict, list[str]]:
    """(capability, index of its measured citation) to the cited readiness quote, and the failures.

    `readiness` is the document's lines. `entries` is from resolve_entries; given, its failures
    are the caller's already.
    """
    fails: list[str] = []
    if entries is None:
        entries, fails = resolve_entries(record, readiness)
    quotes: dict[tuple[str, int], str] = {}
    for name, cap in record["capabilities"].items():
        for k, m in enumerate((cap or {}).get("measured") or []):
            entry, line = (m or {}).get("entry"), (m or {}).get("line")
            if entry not in entries or not line:
                continue  # an unknown entry or an unresolved anchor is already a failure
            hits = measured_line(readiness, entries[entry][0], line)
            if len(hits) != 1:
                fails.append(f"{name}: entry {entry} line {line!r} is on {len(hits)} readiness lines "
                             "from the anchor to the next heading, expected one")
            else:
                quotes[(name, k)] = quote_of(readiness, hits[0])
    return quotes, fails


def evidence_item(record: dict, entries: dict, measured: dict, quote: str) -> str:
    """One piece of evidence, as the Evidence column prints it."""
    _, date, section = entries[measured["entry"]]
    return f"{date}, lab {record['entries'][measured['entry']]['lab']}, {section}: {quote}"


def evidence_cells(record: dict, readiness_text: str) -> dict[str, list[str]]:
    """Capability to the evidence strings render_table prints for it, joined by '; '. Raises CheckError."""
    readiness = readiness_text.replace("\r\n", "\n").split("\n")
    entries, fails = resolve_entries(record, readiness)
    quotes, quote_fails = resolve_quotes(record, readiness, entries)
    fails += quote_fails
    if fails:
        raise CheckError("".join(f"phases: {f}\n" for f in fails))
    return {name: [evidence_item(record, entries, m, quotes[(name, k)]) for k, m in enumerate(cap["measured"])]
            for name, cap in ((n, c or {}) for n, c in record["capabilities"].items())
            if cap.get("measured")}


def render_table(record: dict, capabilities: dict[str, str], decisions_dir, templates_dir,
                 readiness_text: str) -> str:
    """The phases document text. Raises CheckError listing every failure."""
    decisions_dir, templates_dir = Path(decisions_dir), Path(templates_dir)
    fails = check_record(record, capabilities, decisions_dir)
    readiness = readiness_text.replace("\r\n", "\n").split("\n")
    entries, entry_fails = resolve_entries(record, readiness)
    fails += entry_fails
    caps = {k: (v or {}) for k, v in record["capabilities"].items()}

    for name, cap in caps.items():
        for b in cap.get("built") or []:
            tpl, contains = (b or {}).get("template"), (b or {}).get("contains")
            text = read_text(templates_dir / tpl) if tpl else None
            if text is None:
                fails.append(f"{name}: template {tpl} is not in the chart's templates")
            elif not contains or contains not in text:
                fails.append(f"{name}: template {tpl} does not contain {contains!r}")
    quotes, quote_fails = resolve_quotes(record, readiness, entries)
    fails += quote_fails
    if fails:
        raise CheckError("".join(f"phases: {f}\n" for f in fails))

    statuses = statuses_of(record, decisions_dir)
    index_text = read_text(decisions_dir / "README.md") or ""
    road_rows = roadmap_rows(read_text(decisions_dir / ROADMAP) or "")
    rows, counts, used = [], dict.fromkeys(PHASES, 0), set()
    for name, parent in capabilities.items():
        cap = caps[name]
        phase = phase_of(cap, statuses)
        counts[phase] += 1
        lane = str(record["lanes"][parent])
        if cap.get("increment"):
            first = roadmap_row(road_rows, cap["increment"])[0]
            number = "done" if first.startswith("done") else first
            lane += f", {number}: {cap['increment'].replace('**', '')}"
        evidence = NOT_MEASURED
        if phase == "measured":
            used.update(record["entries"][m["entry"]]["lab"] for m in cap["measured"])
            evidence = "; ".join(evidence_item(record, entries, m, quotes[(name, k)])
                                 for k, m in enumerate(cap["measured"]))
        built = list(dict.fromkeys(f"templates/{b['template']}" for b in cap.get("built") or []))
        decisions = []
        for adr in record_adrs(cap):
            theirs = index_status(index_text, adr)
            mine = "accepted" if statuses[adr].startswith("accepted") else "proposed"
            note = f" (record: {mine}; index: {theirs})" if theirs and mine != theirs else ""
            decisions.append(adr + note)
        decisions += [f"{s['adr']} (names it still open)" for s in still_open(cap)]
        rows.append(f"| {name} | {lane} | {phase} | {evidence} | {', '.join(built) or '-'} | "
                    f"{', '.join(decisions) or '-'} | {', '.join(cap.get('rows') or []) or '-'} |")

    out = ["Phases: " + ", ".join(f"{counts[p]} {p}" for p in PHASES) + ".", "",
           "| Capability | Lane | Phase | Evidence | Built | Decisions | Rows |",
           "|---|---|---|---|---|---|---|", *rows, ""]
    if used:
        out += [lab_sentence(record["labs"], sorted(used)), ""]
    out += ['An entry is the last time the readiness doc records that check. It ran against the chart of that '
            'date, which can be older than the chart this document was rendered from. "Not measured" means '
            'the readiness doc has no entry for the capability, and says nothing about measurements recorded '
            'elsewhere.']
    return "\n".join(out)


# --- the barred list ----------------------------------------------------------

def load_barred(paths) -> list[re.Pattern]:
    """Compile the barred list: a pattern per line, `#` comments, an optional `|reason` tail."""
    patterns: list[re.Pattern] = []
    for path in paths:
        name = Path(path).name
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError:
            raise CheckError(f"barred list {name} cannot be read") from None
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            if "|" in line:
                line = line.rsplit("|", 1)[0]
            try:
                patterns.append(re.compile(line, re.IGNORECASE))
            except re.error:
                raise CheckError(f"barred list {name} line {n} does not compile") from None
    if not patterns:
        raise CheckError("the barred list is empty")
    return patterns


def scan_barred(texts: dict[str, list[str]], barred) -> list[str]:
    """One failure per name that carries a barred value. It never says which, or what matched."""
    fails = []
    for name, strings in texts.items():
        n = sum(len(p.findall(s)) for s in strings for p in barred)
        if n:
            fails.append(f"quotes: {name}: carries {n} barred value(s)")
    return fails
