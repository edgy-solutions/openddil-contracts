"""
test_maintenance_vocabularies.py — the closure reason and repair type
vocabularies (ontology/closure_reasons.yaml, ontology/repair_types.yaml).

Proposed 2026-11-14 and provisional: nothing reads them yet. These tests hold
the rules their headers state, so a later edit cannot quietly break one.
"""
import pathlib
import re

import yaml

ONTOLOGY = pathlib.Path(__file__).parent.parent / "ontology"
NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def _load(name):
    return yaml.safe_load((ONTOLOGY / name).read_text(encoding="utf-8"))


def test_closure_reasons_shape():
    reasons = _load("closure_reasons.yaml")["reasons"]
    assert reasons, "no reasons declared"
    for name, r in reasons.items():
        assert NAME.match(name), name
        assert set(r) == {"meaning", "confirms_failure", "ends_life", "candidate", "basis"}, name
        assert isinstance(r["confirms_failure"], bool), name
        assert isinstance(r["ends_life"], bool), name
        assert isinstance(r["candidate"], bool), name
        assert r["meaning"].strip() and r["basis"].strip(), name


def test_only_confirmed_confirms_a_failure():
    reasons = _load("closure_reasons.yaml")["reasons"]
    assert [n for n, r in reasons.items() if r["confirms_failure"]] == ["confirmed"]


def test_a_life_ends_only_on_a_confirmed_failure():
    reasons = _load("closure_reasons.yaml")["reasons"]
    for name, r in reasons.items():
        assert r["ends_life"] == r["confirms_failure"], name


def test_the_proposed_reasons():
    reasons = _load("closure_reasons.yaml")["reasons"]
    on = sorted(n for n, r in reasons.items() if not r["candidate"])
    assert on == ["cannot_duplicate", "confirmed", "no_fault_found"]
    assert [n for n, r in reasons.items() if r["candidate"]] == ["retest_okay"]


def test_repair_types_shape():
    types = _load("repair_types.yaml")["types"]
    assert types, "no types declared"
    for name, t in types.items():
        assert NAME.match(name), name
        assert set(t) == {"kind", "meaning"}, name
        assert t["kind"] in {"replaced", "in_place"}, name
        assert t["meaning"].strip(), name
    assert [n for n, t in types.items() if t["kind"] == "replaced"] == ["replaced"]


def test_no_repair_type_declares_a_renewal_or_none():
    # A renewal is declared per variant and component with its owner, never
    # here (DESIGN-2026-11-11-remaining-life-output-kind §5.2). No repair is
    # an absent type, not a value.
    doc = _load("repair_types.yaml")
    assert set(doc) == {"types"}
    assert "none" not in doc["types"]
    for name, t in doc["types"].items():
        assert not any("renew" in k for k in t), name
