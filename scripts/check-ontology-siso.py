#!/usr/bin/env python3
"""
check-ontology-siso.py -- every DIS tuple in the ontology resolves in SISO,
to the name we say it has.

WHAT THIS CHECKS
  For every key in ontology/dis_entity_types.yaml (except `_`-prefixed
  entries):
    1. the key parses as a DIS 7-tuple
    2. the tuple exists in the Entity Types table (enum uid 30) of
       SISO-REF-010-v37
    3. SISO's description for that tuple equals the entry's
       `siso_description`, exactly

  Check 3 is the one that matters. A tuple that exists in SISO under a
  different platform's name passes check 2 and is still wrong: stock CGF
  traffic for that tuple would be labelled as our platform. Existence is not
  identity; "known" is not "known as what".

WHERE SISO COMES FROM
  The v37 XML is fetched at check time from the open-dis source-generator
  repo, at a pinned commit, and its SHA-256 is compared to the pinned value.
  Moving to a newer SISO release is a deliberate edit of the three pins
  below, never a silent drift. Any failure to fetch or verify is a FAILURE,
  not a skip: a check that passes when it cannot see its reference passes
  when it has checked nothing.

  --siso-file PATH uses a local copy instead (the hash is still verified).

Only the Entity Types table is indexed. The same XML carries an Aggregate
Types table (uid 207) that reuses the <entity> element, so indexing by tag
alone would let an aggregate-type tuple pass as a platform.

Exit 0 = every entry resolves by name. Exit 1 = anything else.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys
import urllib.request
import xml.etree.ElementTree as ET

import yaml

SISO_TITLE = "SISO-REF-010-v37"
SISO_COMMIT = "604a0ee981b8487c7288c21230407a9e4d173105"
SISO_SHA256 = "eaafe0b868e5fe6b3497c915226f312ca9853c242fae11d2f6afcbfb53c8be8c"
SISO_URL = (
    "https://raw.githubusercontent.com/open-dis/opendis7-source-generator/"
    f"{SISO_COMMIT}/xml/SISO/SISO-REF-010.xml"
)
ENTITY_TYPES_UID = "30"

ONTOLOGY = pathlib.Path(__file__).resolve().parent.parent / "ontology" / "dis_entity_types.yaml"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def fetch_siso(local: str | None) -> bytes:
    if local:
        data = pathlib.Path(local).read_bytes()
    else:
        with urllib.request.urlopen(SISO_URL, timeout=120) as resp:
            data = resp.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SISO_SHA256:
        raise SystemExit(f"FAIL: SISO XML sha256 {digest} != pinned {SISO_SHA256}")
    return data


def entity_type_index(data: bytes) -> dict[tuple[int, ...], str]:
    root = ET.fromstring(data)
    if root.get("title") != SISO_TITLE:
        raise SystemExit(f"FAIL: SISO XML title {root.get('title')!r} != {SISO_TITLE!r}")
    tables = [t for t in root if _local(t.tag) == "cet" and t.get("uid") == ENTITY_TYPES_UID]
    if len(tables) != 1:
        raise SystemExit(f"FAIL: expected one Entity Types table (uid {ENTITY_TYPES_UID}), found {len(tables)}")
    idx: dict[tuple[int, ...], str] = {}
    for ent in tables[0]:
        if _local(ent.tag) != "entity":
            continue
        head = (int(ent.get("kind")), int(ent.get("domain")), int(ent.get("country")))
        for cat in ent:
            if _local(cat.tag) != "category":
                continue
            c = int(cat.get("value"))
            idx[head + (c, 0, 0, 0)] = cat.get("description")
            for sub in cat:
                if _local(sub.tag) != "subcategory":
                    continue
                s = int(sub.get("value"))
                idx[head + (c, s, 0, 0)] = sub.get("description")
                for spec in sub:
                    if _local(spec.tag) != "specific":
                        continue
                    p = int(spec.get("value"))
                    idx[head + (c, s, p, 0)] = spec.get("description")
                    for ext in spec:
                        if _local(ext.tag) == "extra":
                            idx[head + (c, s, p, int(ext.get("value")))] = ext.get("description")
    if not idx:
        raise SystemExit("FAIL: the Entity Types table is empty")
    return idx


def main() -> int:
    ap = argparse.ArgumentParser(description="Resolve every ontology tuple against SISO-REF-010-v37.")
    ap.add_argument("--siso-file", help="local SISO-REF-010.xml instead of fetching (hash still verified)")
    ap.add_argument("--ontology", default=str(ONTOLOGY))
    args = ap.parse_args()

    index = entity_type_index(fetch_siso(args.siso_file))
    mappings = yaml.safe_load(pathlib.Path(args.ontology).read_text(encoding="utf-8"))["mappings"]

    checked = failed = 0
    for key, entry in mappings.items():
        if key.startswith("_"):
            continue
        checked += 1
        try:
            tup = tuple(int(v) for v in key.split("_"))
        except ValueError:
            tup = ()
        claimed = (entry or {}).get("siso_description")
        if len(tup) != 7:
            print(f"FAIL  {key}: not a 7-tuple key")
            failed += 1
        elif tup not in index:
            print(f"FAIL  {key}: absent from {SISO_TITLE} Entity Types")
            failed += 1
        elif not claimed:
            print(f"FAIL  {key}: no siso_description; SISO calls it {index[tup]!r}")
            failed += 1
        elif index[tup] != claimed:
            print(f"FAIL  {key}: SISO calls it {index[tup]!r}, ontology says {claimed!r}")
            failed += 1
        else:
            print(f"ok    {key}  {claimed}")

    print()
    if checked == 0:
        print("FAIL: no entries checked -- a pass over nothing is not a pass")
        return 1
    print(f"{checked - failed} of {checked} entries resolve by name in {SISO_TITLE} "
          f"(Entity Types, commit {SISO_COMMIT[:12]})")
    if failed:
        print(f"RESULT: FAIL ({failed})")
        return 1
    print("RESULT: PASS")
    print("Does not establish: that platform_variant is the platform the "
          "siso_description names. That pairing is curated by a human.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
