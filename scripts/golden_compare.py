#!/usr/bin/env python3
"""Compare two architecture exports element by element, and name every allowed difference.

usage: golden_compare.py OLD.html NEW.html ALLOW.txt [--out DIR]

An export is cut into elements: the text before the first page, each `<section id="ID"...>` page, and the
text after the last one. For each element the result is `identical`, `allowed` (it differs, and ALLOW names
it) or `DIFFERENT`.

ALLOW lines are `ID: reason`, or `ID ELEMENT: reason` for one element of a page. ELEMENT is `data-relabel`
(the front page's sentence about relabelling) or `break-hints`. `ID` is a page id, or `prelude` / `postlude`. Blank lines and
lines starting with `#` are ignored.

`ID break-hints: reason` lets the page differ by break hints, by how the nowrap spans split a token, and by header widths
only: on both sides every `<wbr>` is removed, each `<span class="nb">TEXT</span>` whose TEXT has no `<` becomes
TEXT, and inside each `<th ...>` start tag `min-width:<digits>ch` becomes `min-width:Nch`. The page must then
be byte-equal. When a page has both kinds, the element is removed first, then the break hints are normalised. A
`break-hints` line is used only when the page differs before normalising and the normalising changed a side. When a
page differs, no line names it, and normalising would make it equal, the failure says `(break-hints would cover it)`.

The allowed elements are removed from both sides, the rest is written to DIR/old.reduced and DIR/new.reduced,
and the two files are compared byte for byte. The exit code is 1 when:
  - an element differs and ALLOW does not name it;
  - an ALLOW line matches nothing (the element is identical, or does not exist): a stale allowance;
  - the reduced files differ.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SECTION = re.compile(rb'<section id="([^"]*)"')
ELEMENTS = {"data-relabel": re.compile(rb"<p[^>]*\bdata-relabel\b[^>]*>.*?</p>", re.S)}


BREAK_HINTS = "break-hints"
KINDS = [*ELEMENTS, BREAK_HINTS]
WBR = b"<wbr>"
TH_START = re.compile(rb"<th\b[^>]*>")
NOWRAP = re.compile(rb'<span class="nb">([^<]*)</span>')
MIN_WIDTH = re.compile(rb"min-width:\d+ch")


def normalise(data: bytes) -> bytes:
    """Remove every <wbr>, unwrap the nowrap spans, and make the min-width of each <th> start tag `Nch`."""
    data = NOWRAP.sub(rb"\1", data.replace(WBR, b""))
    return TH_START.sub(lambda m: MIN_WIDTH.sub(b"min-width:Nch", m.group(0)), data)


def cut(data: bytes) -> dict[str, bytes]:
    """The export's elements by id, in order. `prelude` is the text before the first page."""
    marks = list(SECTION.finditer(data))
    if not marks:
        raise SystemExit("golden_compare: no <section id=...> in the export")
    out = {"prelude": data[:marks[0].start()]}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(data)
        pid = m.group(1).decode("utf-8")
        if pid in out:
            raise SystemExit(f"golden_compare: page id {pid} appears twice")
        out[pid] = data[m.start():end]
    # The last page runs to the end of the file; the closing text of the document is part of it. Split it off at
    # the last </section>.
    last = list(out)[-1]
    body = out[last]
    k = body.rfind(b"</section>") + len(b"</section>")
    out["postlude"] = body[k:]
    out[last] = body[:k]
    return out


def read_allow(path: Path) -> list[tuple[str, str | None, str]]:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, reason = line.partition(": ")
        if not sep or not reason.strip():
            raise SystemExit(f"{path}:{n}: expected `ID: reason` or `ID ELEMENT: reason`")
        parts = key.split()
        if len(parts) not in (1, 2) or (len(parts) == 2 and parts[1] not in KINDS):
            raise SystemExit(f"{path}:{n}: unknown element in `{key}` (known: {', '.join(KINDS)})")
        rows.append((parts[0], parts[1] if len(parts) == 2 else None, reason.strip()))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("old")
    ap.add_argument("new")
    ap.add_argument("allow")
    ap.add_argument("--out", default=".")
    a = ap.parse_args(argv)
    old_raw, new_raw = Path(a.old).read_bytes(), Path(a.new).read_bytes()
    old, new = cut(old_raw), cut(new_raw)
    allow = read_allow(Path(a.allow))
    fails: list[str] = []
    if list(old) != list(new):
        only_old = [k for k in old if k not in new]
        only_new = [k for k in new if k not in old]
        fails.append(f"the pages differ: only in old {only_old[:5]}, only in new {only_new[:5]}")
    ids = [k for k in old if k in new]
    names = {(i, e) for i, e, _ in allow}
    used: set[tuple[str, str | None]] = set()
    identical = allowed = 0
    for pid in ids:
        if old[pid] == new[pid]:
            identical += 1
            continue
        if (pid, None) in names:
            used.add((pid, None))
            allowed += 1
            print(f"allowed:   {pid}  {next(r for i, e, r in allow if (i, e) == (pid, None))}")
            old[pid] = new[pid] = b""
            continue
        hit = [e for (i, e) in names if i == pid and e]
        for e in hit:
            if e == BREAK_HINTS:
                continue
            pat = ELEMENTS[e]
            o, n = pat.search(old[pid]), pat.search(new[pid])
            if not o or not n:
                continue
            used.add((pid, e))
            old[pid] = old[pid][:o.start()] + old[pid][o.end():]
            new[pid] = new[pid][:n.start()] + new[pid][n.end():]
        if BREAK_HINTS in hit and old[pid] != new[pid]:
            no, nn = normalise(old[pid]), normalise(new[pid])
            if no != old[pid] or nn != new[pid]:
                used.add((pid, BREAK_HINTS))
                old[pid], new[pid] = no, nn
        if hit and old[pid] == new[pid]:
            allowed += 1
            for e in hit:
                if (pid, e) in used:
                    print(f"allowed:   {pid} {e}  {next(r for i, el, r in allow if (i, el) == (pid, e))}")
        elif hit:
            fails.append(f"{pid}: differs outside {', '.join(hit)}")
        else:
            hint = " (break-hints would cover it)" if normalise(old[pid]) == normalise(new[pid]) else ""
            fails.append(f"{pid}: differs and is not in the allowlist{hint}")
    for i, e, _ in allow:
        if (i, e) not in used:
            fails.append(f"allowlist line matches nothing: {i}{' ' + e if e else ''}")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ro, rn = b"".join(old[k] for k in ids), b"".join(new[k] for k in ids)
    (out / "old.reduced").write_bytes(ro)
    (out / "new.reduced").write_bytes(rn)
    if ro != rn and not fails:
        fails.append("the reduced files differ")
    print(f"elements: {len(ids)}; identical {identical}; allowed {allowed}; "
          f"bytes old {len(old_raw)}, new {len(new_raw)}; reduced old {len(ro)}, new {len(rn)}")
    for f in fails:
        print(f"FAIL: {f}", file=sys.stderr)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
