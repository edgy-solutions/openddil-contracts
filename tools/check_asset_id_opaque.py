#!/usr/bin/env python3
"""
check_asset_id_opaque.py -- CI check for ADR-0047 (asset_id is opaque).

WHAT THIS CHECKS
  Interior code may compare, key, store and display `asset_id`. It may not
  parse it: split it, regex it, check its prefix/suffix, slice it, or
  LIKE-query it. The only allowed sites are boundary mappers that construct
  an id, and charset/length validation at a trust boundary -- both listed in
  a per-repo allowlist file with a reason.

  This is a line-based textual check, not an AST parse. It looks for an
  "id-bearing" name (one that names an asset id) immediately combined with
  a parsing operation, per pattern below. --list-patterns shows the pattern
  ids and a short description of each.

ID-BEARING NAME
  Case-insensitive, the name contains `asset_?id` (asset_id, assetId,
  selectedAssetId, munitionAssetId) or is bare `aid`. A name that looks
  plural -- ends in `s`, `_list` or `_set` -- is treated as a collection,
  not a single id, and is excluded (`assetIds.includes(x)`, `x in
  asset_ids`). This single rule is what keeps `.includes(`/`.indexOf(`
  from flagging a membership test against a list of ids.

ALLOWLIST FORMAT
  One entry per line in the allowlist file, tab-separated:
    <repo-relative path>\t<substring that must appear on the line>\t<reason>
  `#` comments and blank lines are ignored. An entry matches a finding when
  the path is equal and the substring appears in that finding's source
  line. The reason must start with `mapper:`, `validation:`, `source-sim:`
  or `pending:`; anything else is a usage error. Allowlist entries that
  match no finding are stale and must be removed -- the allowlist only
  shrinks. There is no inline escape hatch; the allowlist file is the only
  way to exempt a line, so every exception lives in one place.

EXIT CODES (precedence 3 > 1 > 2)
  3  usage error (bad allowlist reason, bad CLI args), or zero files
     scanned -- an empty scan is not a pass.
  1  at least one unallowlisted finding.
  2  at least one stale allowlist entry (and no usage error, no new
     finding).
  0  otherwise.
  The last line of output is always:
    asset-id-opaque: files=N findings=F allowlisted=A new=X stale=S pending=P
  (pending = allowlist entries whose reason starts with `pending:`.)

KNOWN BLIND SPOTS (documented, not fixed, per spec instruction)
  - Generic id-ish names that do not say "asset": `id.split(`,
    `key.split(`, `sensor_id.split(`, `capability_id.split(`. Catching
    every name that merely ends in `_id` would flag unrelated identifiers
    (request ids, correlation ids, capability ids) constantly; the signal
    would drown. We only catch names that say "asset" (or bare `aid`),
    and accept that a parse of a differently-named asset-id alias (a
    mapper-local rename without "asset" in it) is a miss.
  - A name like `assetIdentity` contains the substring `assetid` and is
    treated as id-bearing even though it is a type/concept name, not a
    value. Rare enough in practice not to special-case.
  - A single-letter or generic loop variable holding an asset id value
    (`k.startswith("dis:3:")` for a `key` iterated out of a dict) is not
    id-bearing by name and is missed, same trade-off as `id.split(` above.
  - `in_substring` only recognizes a quoted string literal on the left of
    `in`; `str(entity) in evt.asset.asset_id` (a computed needle, not a
    literal) is a miss by the same rule the spec wrote the pattern with.
  - `.blobl` bloblang methods (`has_prefix`, `trim_suffix`, ...) and the
    generic method list overlap on `.split(` / `.slice(`: a single line
    can produce two findings, one per pattern id, when both an
    id-bearing name and those shared method names are present. This is
    treated as a feature (each pattern is an independent rule), not a
    bug to de-duplicate.
  - `--json` mode does not have a fixed, versioned schema; it is a
    convenience dump of the same fields as the text report, not a
    contract for downstream tooling yet.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Scan scope
# --------------------------------------------------------------------------

SCAN_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".cs", ".go", ".sh", ".sql",
    ".yaml", ".yml", ".hcl", ".tpl", ".blobl",
}

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "out", "wt", ".venv", "venv",
    "__pycache__", "generated", "gen", "bin", "obj",
}

SKIP_FILE_SUFFIXES = (".min.js", "_pb2.py", ".pb.go", ".g.cs")

LOCKFILE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
    "cargo.lock", "go.sum", "poetry.lock", "pipfile.lock", "composer.lock",
}

MAX_BYTES = 1_000_000

VALID_REASON_PREFIXES = ("mapper:", "validation:", "source-sim:", "pending:")


def _is_skipped_file(name: str) -> bool:
    low = name.lower()
    if low in LOCKFILE_NAMES:
        return True
    return any(low.endswith(suf) for suf in SKIP_FILE_SUFFIXES)


# The checker and its tests spell out every pattern by construction. When a
# scan root contains them (this repo's own CI), these two files -- by their
# resolved path, not by name, so a copy elsewhere is still scanned -- are
# skipped.
_SELF = pathlib.Path(__file__).resolve()
SELF_FILES = {_SELF, _SELF.with_name("test_" + _SELF.name)}


def iter_files(root: pathlib.Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = pathlib.Path(dirpath) / fn
            if p.resolve() in SELF_FILES:
                continue
            if p.suffix.lower() not in SCAN_EXTS:
                continue
            if _is_skipped_file(fn):
                continue
            try:
                if p.stat().st_size > MAX_BYTES:
                    continue
            except OSError:
                continue
            yield p


# --------------------------------------------------------------------------
# Id-bearing names
# --------------------------------------------------------------------------

_ASSET_ID_RE = re.compile(r"asset_?id", re.I)


def is_id_bearing(name: str) -> bool:
    if not name:
        return False
    low = name.lower()
    if low.endswith("_list") or low.endswith("_set") or low.endswith("s"):
        return False
    if low == "aid":
        return True
    return bool(_ASSET_ID_RE.search(low))


def _line_has_id_bearing(line: str) -> bool:
    return any(is_id_bearing(t) for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", line))


# --------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------

_METHODS = [
    "split", "rsplit", "partition", "rpartition", "startswith", "endswith",
    "startsWith", "endsWith", "includes", "indexOf", "lastIndexOf", "slice",
    "substring", "substr", "match", "matchAll", "search", "replace",
    "replaceAll", "Split", "StartsWith", "EndsWith", "Contains", "Substring",
    "IndexOf",
]
_METHOD_ALT = "|".join(sorted(set(_METHODS), key=len, reverse=True))
_METHOD_PARSE_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*(?:" + _METHOD_ALT + r")\s*\("
)
_METHOD_PARSE_BRACKET_RE = re.compile(
    r"""\[\s*["']([A-Za-z_][A-Za-z0-9_]*)["']\s*\]\s*\.\s*(?:""" + _METHOD_ALT + r")\s*\("
)


def _method_parse(line: str) -> bool:
    for m in _METHOD_PARSE_RE.finditer(line):
        if is_id_bearing(m.group(1)):
            return True
    for m in _METHOD_PARSE_BRACKET_RE.finditer(line):
        if is_id_bearing(m.group(1)):
            return True
    return False


_BLOB_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s*\.\s*"
    r"(split|has_prefix|has_suffix|contains|re_match|re_find\w*|slice|"
    r"trim_prefix|trim_suffix)\s*\("
)


def _bloblang_parse(line: str) -> bool:
    for m in _BLOB_RE.finditer(line):
        if is_id_bearing(m.group(1)):
            return True
    return False


_PY_SLICE_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\[([^\]]*:[^\]]*)\]")


def _py_slice(line: str) -> bool:
    for m in _PY_SLICE_RE.finditer(line):
        if is_id_bearing(m.group(1)):
            return True
    return False


_PY_REGEX_CALL_RE = re.compile(r"re\.(?:match|fullmatch|search|split|findall|sub)\(")
_JS_REGEX_CALL_RE = re.compile(
    r"(?:([A-Za-z_][A-Za-z0-9_]*)\s*)?\.(?:test|exec)\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)"
)


def _regex_call(line: str) -> bool:
    if _PY_REGEX_CALL_RE.search(line) and _line_has_id_bearing(line):
        return True
    for m in _JS_REGEX_CALL_RE.finditer(line):
        # either side can carry the signal: a bare regex literal receiver
        # (`/^dis:/.test(assetId)`) leaves group(1) empty and the argument
        # carries it; a named pattern receiver (`ASSET_ID_PATTERN.test(x)`)
        # carries it on the other side instead.
        receiver = m.group(1)
        if (receiver and is_id_bearing(receiver)) or is_id_bearing(m.group(2)):
            return True
    return False


_IN_SUBSTRING_RE = re.compile(
    r"""(['"])(?:[^'"\\]|\\.)*?\1\s+in\s+"""
    r"""([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)(?:\.lower\(\))?"""
)


def _in_substring(line: str) -> bool:
    for m in _IN_SUBSTRING_RE.finditer(line):
        # a dotted chain (evt.asset.asset_id) is id-bearing if its last
        # segment is -- the leading `ctx.`/`evt.asset.` is just access, same
        # as the method_parse / py_slice patterns already treat it.
        last_segment = m.group(2).rsplit(".", 1)[-1]
        if is_id_bearing(last_segment):
            return True
    return False


_SQL_OP_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s+(?:LIKE|ILIKE|SIMILAR\s+TO|~\*?)\s", re.I
)
_SQL_FUNC_RE = re.compile(
    r"(?:split_part|substr|substring|left|right)\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)",
    re.I,
)
_SQL_POSITION_RE = re.compile(
    r"position\s*\([^)]*\bin\s+([A-Za-z_][A-Za-z0-9_]*)", re.I
)


def _sql_like(line: str) -> bool:
    for rx in (_SQL_OP_RE, _SQL_FUNC_RE, _SQL_POSITION_RE):
        for m in rx.finditer(line):
            if is_id_bearing(m.group(1)):
                return True
    return False


_SCHEME_WILDCARD_RE = re.compile(r"dis:%")
_SCHEME_REGEXCHAR_RE = re.compile(r"dis:(?:\\d|\[0-9\])")
_SCHEME_LITERAL_EXACT_RE = re.compile(r"""(['"])dis:\1""")
_SCHEME_STARTSWITH_CALL_RE = re.compile(r"\.(?:startswith|startsWith)\(")
_GREP_RE = re.compile(r"\bgrep\b")
_GREP_DIS_DIGIT_RE = re.compile(r"""(['"])dis:(?:\\d|\[0-9\]|\d+:)""")


def _scheme_literal(line: str) -> bool:
    if _SCHEME_WILDCARD_RE.search(line):
        return True
    if _SCHEME_REGEXCHAR_RE.search(line):
        return True
    if _SCHEME_LITERAL_EXACT_RE.search(line) and _SCHEME_STARTSWITH_CALL_RE.search(line):
        return True
    if _GREP_RE.search(line) and _GREP_DIS_DIGIT_RE.search(line):
        return True
    return False


_SHELL_CUT_RE = re.compile(r"cut\s+-d:|awk\s+-F:|IFS=:")


def _shell_cut(line: str) -> bool:
    return bool(_SHELL_CUT_RE.search(line)) and _line_has_id_bearing(line)


PATTERNS = [
    ("method_parse", _method_parse,
     "id-bearing name.split/startswith/endsWith/.../Substring("),
    ("bloblang_parse", _bloblang_parse,
     "id-bearing name.split/has_prefix/trim_suffix/... (bloblang)"),
    ("py_slice", _py_slice, "id-bearing_name[a:b] (Python slice)"),
    ("regex_call", _regex_call, "re.match/search/... or .test(/.exec( on an id-bearing name"),
    ("in_substring", _in_substring, '"literal" in id-bearing_name (substring test)'),
    ("sql_like", _sql_like, "id-bearing column LIKE/ILIKE/~ or split_part/substr/left/right/position"),
    ("scheme_literal", _scheme_literal, "literal or regex that tests the dis: scheme shape"),
    ("shell_cut", _shell_cut, "cut -d: / awk -F: / IFS=: on a line with an id-bearing variable"),
]


# --------------------------------------------------------------------------
# Scanning
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Finding:
    pattern: str
    path: str
    line: int
    text: str


@dataclass(frozen=True)
class AllowlistEntry:
    path: str
    substring: str
    reason: str


def scan_file(root: pathlib.Path, path: pathlib.Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    rel = path.relative_to(root).as_posix()
    out: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pid, fn, _desc in PATTERNS:
            if fn(line):
                out.append(Finding(pid, rel, lineno, line))
    return out


def parse_allowlist(path: pathlib.Path) -> tuple[list[AllowlistEntry], list[str]]:
    entries: list[AllowlistEntry] = []
    errors: list[str] = []
    if not path.exists():
        return entries, errors
    raw = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(raw.splitlines(), start=1):
        if not line.strip() or line.strip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            errors.append(f"{path}:{lineno}: expected 3 tab-separated fields, got {len(parts)}")
            continue
        rpath, substring, reason = parts
        rpath = rpath.strip().replace("\\", "/")
        reason = reason.strip()
        if not reason or not reason.startswith(VALID_REASON_PREFIXES):
            errors.append(f"{path}:{lineno}: reason {reason!r} must start with one of {VALID_REASON_PREFIXES}")
            continue
        entries.append(AllowlistEntry(rpath, substring, reason))
    return entries, errors


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Fail on a new asset_id parse site (ADR-0047)."
    )
    ap.add_argument("--root", default=".")
    ap.add_argument("--allowlist", default=None)
    ap.add_argument("--list-patterns", action="store_true")
    ap.add_argument("--json", action="store_true")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = _build_parser()
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return 3 if e.code else 0

    if args.list_patterns:
        for pid, _fn, desc in PATTERNS:
            print(f"{pid}\t{desc}")
        return 0

    root = pathlib.Path(args.root).resolve()
    allowlist_path = (
        pathlib.Path(args.allowlist) if args.allowlist else root / ".asset-id-allowlist"
    )

    files_scanned = 0
    findings: list[Finding] = []
    for f in iter_files(root):
        files_scanned += 1
        findings.extend(scan_file(root, f))

    entries, parse_errors = parse_allowlist(allowlist_path)
    usage_error = bool(parse_errors)

    used = [False] * len(entries)
    new_findings: list[Finding] = []
    allowlisted_findings: list[Finding] = []
    for finding in findings:
        matched = False
        for i, e in enumerate(entries):
            if e.path == finding.path and e.substring in finding.text:
                used[i] = True
                matched = True
                break
        (allowlisted_findings if matched else new_findings).append(finding)

    stale_entries = [e for e, u in zip(entries, used) if not u]
    pending_count = sum(1 for e in entries if e.reason.startswith("pending:"))

    files = files_scanned
    total = len(findings)
    allowlisted = len(allowlisted_findings)
    new = len(new_findings)
    stale = len(stale_entries)

    if usage_error or files == 0:
        exit_code = 3
    elif new:
        exit_code = 1
    elif stale:
        exit_code = 2
    else:
        exit_code = 0

    if args.json:
        payload = {
            "files": files,
            "findings": total,
            "allowlisted": allowlisted,
            "new": new,
            "stale": stale,
            "pending": pending_count,
            "exit_code": exit_code,
            "new_findings": [f.__dict__ for f in new_findings],
            "stale_entries": [e.__dict__ for e in stale_entries],
            "usage_errors": parse_errors,
        }
        print(json.dumps(payload, indent=2))
    else:
        for err in parse_errors:
            print(f"usage error: {err}", file=sys.stderr)
        if files == 0 and not usage_error:
            print("usage error: no files scanned", file=sys.stderr)
        if new:
            for f in new_findings:
                print(f"{f.path}:{f.line}: [{f.pattern}] {f.text.strip()}")
            print("See ADR-0047 (asset_id is opaque): add a boundary mapper, or a "
                  "charset/length validation entry, to the allowlist with a reason.")
        elif stale:
            for e in stale_entries:
                print(f"stale allowlist entry: {e.path}\t{e.substring}\t{e.reason}")

    print(f"asset-id-opaque: files={files} findings={total} allowlisted={allowlisted} "
          f"new={new} stale={stale} pending={pending_count}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
