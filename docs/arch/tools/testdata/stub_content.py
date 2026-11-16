"""Stub content for tests: a copy of the tree whose record and St-Tx carry what the real ones will.

The real capability-record.yaml and views/St-Tx.md are written by the documentation author:
descriptions, and a section on every decision citation. Until that lands, and in any test that
needs a tree it can change, stub_tree() copies docs/arch, decisions and ontology into a temp
directory and adds stub descriptions and a section to every citation. The stubs say nothing
about any capability; they only make the shape valid.

    root = stub_tree(Path(tempfile.mkdtemp()))     # root/docs/arch is the tree to render
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parent.parent
ARCH = TOOLS.parent
REPO = ARCH.parent.parent
sys.path.insert(0, str(TOOLS))
import adr_sections  # noqa: E402

STUB_DESCRIPTION = ("A stub description of {name}. It says what the capability is in one sentence. "
                    "It repeats no decision text.")
ST_TX_LINK_RE = re.compile(r"\[(ADR-\d{4})\]\((\.\./[^)]*decisions/ADR-\d{4}-[^)]*)\)")


def first_label(decisions: Path, adr: str) -> str:
    """The first heading of the record that a citation can name on its own."""
    path = sorted(decisions.glob(f"{adr}-*.md"))[0]
    text = path.read_text(encoding="utf-8")
    for h in adr_sections.headings(text):
        label = h.number or h.slug
        try:
            adr_sections.resolve(text, label)
        except LookupError:
            continue
        return label
    raise ValueError(f"{adr} has no heading a citation can name")


def cite(decisions: Path, item: str) -> str:
    item = str(item).strip()
    if "§" in item or not re.fullmatch(r"ADR-\d{4}", item):
        return item
    return f"{item} §{first_label(decisions, item)}"


def stub_record(record: dict, decisions: Path) -> dict:
    anchor = "ADR-0038" if list(decisions.glob("ADR-0038-*.md")) else sorted(decisions.glob("ADR-*.md"))[0].name[:8]
    for name, cap in record["capabilities"].items():
        cap = record["capabilities"][name] = cap or {}
        cap.setdefault("description", STUB_DESCRIPTION.format(name=name))
        if cap.get("adrs"):
            cap["adrs"] = [cite(decisions, a) for a in cap["adrs"]]
        elif not cap.get("derived_from"):
            cap["derived_from"] = [cite(decisions, anchor)]
        for s in cap.get("still_open") or []:
            s["adr"] = cite(decisions, s["adr"])
    return record


def stub_st_tx(text: str, decisions: Path) -> str:
    def sub(m: re.Match) -> str:
        return f"[{m.group(1)} §{first_label(decisions, m.group(1))}]({m.group(2)})"
    return ST_TX_LINK_RE.sub(sub, text)


def git(root: Path, *args: str) -> None:
    r = subprocess.run(["git", "-C", str(root), "-c", "user.name=stub", "-c", "user.email=stub@example.invalid",
                        "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")


def make_repo(root: Path) -> None:
    """A git repository at root with decisions/ committed, so each decision has a stamp."""
    git(root, "init", "-q")
    git(root, "add", "decisions")
    git(root, "commit", "-q", "-m", "decisions")


def stub_tree(dest: Path, *, repo: bool = True) -> Path:
    """Copy docs/arch, decisions and ontology under dest and stub the record and St-Tx there. Returns dest."""
    ignore = shutil.ignore_patterns("node_modules", "__pycache__", ".git")
    for part in ("docs/arch", "decisions", "ontology"):
        if (REPO / part).is_dir():
            shutil.copytree(REPO / part, dest / part, ignore=ignore)
    decisions = dest / "decisions"
    rec = dest / "docs" / "arch" / "capability-record.yaml"
    record = yaml.safe_load(rec.read_text(encoding="utf-8"))
    rec.write_text(yaml.safe_dump(stub_record(record, decisions), sort_keys=False, allow_unicode=True),
                   encoding="utf-8")
    tx = dest / "docs" / "arch" / "views" / "St-Tx.md"
    tx.write_text(stub_st_tx(tx.read_text(encoding="utf-8"), decisions), encoding="utf-8", newline="\n")
    if repo:
        make_repo(dest)
    return dest


if __name__ == "__main__":
    out = stub_tree(Path(sys.argv[1]))
    print(out)
