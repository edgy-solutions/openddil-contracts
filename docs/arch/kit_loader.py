"""The loader for this repository's architecture record, decisions, registers, roadmap and readiness doc.

The export kit reads none of those files itself. It calls these functions, named in the kit's seam
(arch_kit/tools/seam.py), and reads the record only in the neutral shape load_record returns. The
bodies below are the ones the kit held before the seam, unchanged. The additions are the key mapping
(_to_neutral), its refusal (_refuse_neutral_keys) and KEY_NAMES.

The record on disk keeps its own keys; load_record maps them:
    lanes -> groups, labs -> environments, entries.<key>.lab -> environment,
    capabilities.<name>.severed -> degraded_mode.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from capability_phases import split_row  # the rules use it too, so it stays in the kit
from data_exchange import InputError

# The neutral key to this record's own key, for the kit's messages.
KEY_NAMES = {"groups": "lanes", "environments": "labs", "environment": "lab", "degraded_mode": "severed"}

REGISTER_HEADER = ["ID", "Subject", "Status"]
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
SECTIONS = ("lanes", "labs", "entries", "capabilities")


def _renamed(mapping: dict, old: str, new: str) -> dict:
    """mapping with key `old` called `new`, in the same position."""
    return {(new if k == old else k): v for k, v in mapping.items()}


def _refuse_neutral_keys(path, record: dict) -> None:
    """A record that already holds a neutral key is refused: the mapping would be ambiguous."""
    for top in ("groups", "environments"):
        if top in record:
            raise InputError(f"{path}: '{top}' is a key of the kit's neutral record; this record writes it '{KEY_NAMES[top]}'")
    for name, entry in record["entries"].items():
        if isinstance(entry, dict) and "environment" in entry:
            raise InputError(f"{path}: entry {name} has 'environment', a key of the kit's neutral record; "
                             f"this record writes it '{KEY_NAMES['environment']}'")
    for name, cap in record["capabilities"].items():
        if isinstance(cap, dict) and "degraded_mode" in cap:
            raise InputError(f"{path}: {name} has 'degraded_mode', a key of the kit's neutral record; "
                             f"this record writes it '{KEY_NAMES['degraded_mode']}'")


def _to_neutral(record: dict) -> dict:
    record = _renamed(_renamed(record, "lanes", "groups"), "labs", "environments")
    record["entries"] = {k: (_renamed(v, "lab", "environment") if isinstance(v, dict) else v)
                         for k, v in record["entries"].items()}
    record["capabilities"] = {k: (_renamed(v, "severed", "degraded_mode") if isinstance(v, dict) else v)
                              for k, v in record["capabilities"].items()}
    return record


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
    _refuse_neutral_keys(path, record)
    return _to_neutral(record)


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
    path = adr_file(decisions_dir, adr)
    text = read_text(path) if path else None
    status = adr_status(text) if text is not None else None
    return status.lstrip("* ").lower() if status else None


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


def register_subjects(text: str) -> dict[str, tuple[str, str]]:
    """Row id to (subject, status), for every `| ID | Subject | Status |` register in the text."""
    out: dict[str, tuple[str, str]] = {}
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("|") or split_row(line) != REGISTER_HEADER:
            continue
        for nxt in lines[i + 2:]:
            if not nxt.lstrip().startswith("|"):
                break
            cells = split_row(nxt)
            if len(cells) >= 3:
                out.setdefault(cells[0], (cells[1], cells[-1]))
    return out


def roadmap_rows(text: str) -> list[list[str]]:
    return [split_row(ln) for ln in text.split("\n") if ln.lstrip().startswith("|")]


def index_status(index_text: str, adr: str) -> str | None:
    """The bold status the decisions index gives an ADR, when it begins accepted or proposed."""
    m = re.search(rf"\[{re.escape(adr)}:[^\n]*?\)\s*—\s*\*\*(accepted|proposed)", index_text, re.I)
    return m.group(1).lower() if m else None


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
