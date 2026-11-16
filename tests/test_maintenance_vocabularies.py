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
        assert set(r) == {
            "meaning", "confirms_failure", "ends_life", "censors_life",
            "in_reliability", "in_bit_counts", "candidate", "basis",
        }, name
        for flag in ("confirms_failure", "ends_life", "censors_life",
                     "in_reliability", "in_bit_counts", "candidate"):
            assert isinstance(r[flag], bool), (name, flag)
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
    assert on == ["battle_damage", "cannot_duplicate", "confirmed", "no_fault_found"]
    assert [n for n, r in reasons.items() if r["candidate"]] == ["retest_okay"]


def test_a_censored_life_is_never_also_ended():
    reasons = _load("closure_reasons.yaml")["reasons"]
    for name, r in reasons.items():
        assert not (r["censors_life"] and r["ends_life"]), name


def test_a_failure_is_always_counted():
    # A closure outside reliability or the built-in test counts can never be
    # the one that confirms a failure, or a failure would vanish from them.
    reasons = _load("closure_reasons.yaml")["reasons"]
    for name, r in reasons.items():
        if r["confirms_failure"]:
            assert r["in_reliability"] and r["in_bit_counts"], name


def test_battle_damage_is_excluded_and_censored():
    # Added from BDAR (2026-11-16): not a failure, outside every reliability
    # count, outside the built-in test counts, censored for remaining life.
    r = _load("closure_reasons.yaml")["reasons"]["battle_damage"]
    assert r["confirms_failure"] is False
    assert r["ends_life"] is False
    assert r["censors_life"] is True
    assert r["in_reliability"] is False
    assert r["in_bit_counts"] is False
    assert r["candidate"] is False


def test_only_battle_damage_is_excluded_or_censors():
    reasons = _load("closure_reasons.yaml")["reasons"]
    for flag, odd in (("censors_life", True), ("in_reliability", False), ("in_bit_counts", False)):
        assert [n for n, r in reasons.items() if r[flag] is odd] == ["battle_damage"], flag


def test_repair_types_shape():
    types = _load("repair_types.yaml")["types"]
    assert types, "no types declared"
    for name, t in types.items():
        assert NAME.match(name), name
        assert set(t) == {"kind", "meaning", "requires"}, name
        assert t["kind"] in {"replaced", "in_place"}, name
        assert t["meaning"].strip(), name
        assert isinstance(t["requires"], list), name
        assert all(NAME.match(f) for f in t["requires"]), name
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


def test_temporary_carries_the_permanent_repairs_due_date():
    # Added from BDAR (2026-11-16): a temporary repair is in place and owes a
    # permanent one by a stated date. It is the only type that requires a field.
    types = _load("repair_types.yaml")["types"]
    t = types["temporary"]
    assert t["kind"] == "in_place"
    assert t["requires"] == ["permanent_repair_due"]
    assert [n for n, x in types.items() if x["requires"]] == ["temporary"]
