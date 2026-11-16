"""Tests for openddil_labels.downgrade, named after ADR-0055 check 6.

Status: Builds on the PROPOSED ADR-0055 §3a ruling (an unlabelled contributor forms no class and is counted in a withheld
tally). It is not a ruled behaviour: the built regional rollup keeps an empty-audience class, and which one
stands is an owed ruling.
"""

import inspect
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib" / "python"))

from openddil_labels import (  # noqa: E402
    DOWNGRADE_LOWERS_NOTHING,
    DOWNGRADE_NO_INPUTS,
    DOWNGRADE_NO_OWNER,
    DOWNGRADE_NO_REASON,
    DOWNGRADE_OWNER_NOT_DECLARED,
    VALUE_MALFORMED,
    VALUE_OUT_OF_VOCABULARY,
    Declaration,
    Dimension,
    Downgrade,
    Refused,
    class_label,
    record_downgrade,
)

NATIONS = ("ATL", "BDR", "CRD")
P = "example:policy-1"
NATION = Dimension.permissive("nation", NATIONS, "nation-steward", has_author=True)
HOLDER = Dimension.restrictive("data_rights_holder", ("H1", "H2"), "rights-steward")
D = Declaration(P, (NATION, HOLDER))
DH = Declaration(P, (Dimension.hierarchical("classification", ("U", "C", "S"), "class-steward"),))


def lab(author, release, holders):
    return {"nation": {"author": author, "release": release}, "data_rights_holder": holders}


FLOOR = class_label(lab("BDR", [], ["H1"]), D)
GIVEN = lab("ATL", ["BDR"], ["H1"])


def rec(**kw):
    args = dict(
        floor=FLOOR,
        label=GIVEN,
        reason=" widened for the joint cell ",
        inputs=["i2", "i1", "i2"],
        owner=" nation-steward ",
        declaration=D,
        single_authorship=True,
    )
    args.update(kw)
    return record_downgrade(**args)


BLANKS = [None, "", "  ", 5]


@pytest.mark.parametrize("bad", BLANKS)
def test_check6_no_owner(bad):
    assert rec(owner=bad) == Refused(DOWNGRADE_NO_OWNER, None, None)


@pytest.mark.parametrize("bad", BLANKS)
def test_check6_no_reason(bad):
    assert rec(reason=bad) == Refused(DOWNGRADE_NO_REASON, None, None)


def test_check6_both_missing_owner_first():
    assert rec(owner=None, reason=None).reason == DOWNGRADE_NO_OWNER


@pytest.mark.parametrize("bad", [[], (), set(), None, "i1", 5])
def test_check6_empty_inputs(bad):
    assert rec(inputs=bad) == Refused(DOWNGRADE_NO_INPUTS, None, None)


@pytest.mark.parametrize("bad", [[1], ["i1", None], ["i1", " "], [b"x"]])
def test_check6_malformed_input(bad):
    assert rec(inputs=bad) == Refused(VALUE_MALFORMED, None, None)


def test_check6_valid_downgrade():
    r = rec()
    assert isinstance(r, Downgrade)
    assert r.lowers == ("nation",)
    assert r.inputs == ("i1", "i2")
    assert r.reason == "widened for the joint cell"
    assert r.owner == "nation-steward"
    assert r.label == GIVEN and r.floor == FLOOR


def test_check6_owner_not_declared():
    assert rec(owner="rights-steward") == Refused(DOWNGRADE_OWNER_NOT_DECLARED, "nation", None)
    assert rec(owner="someone-else") == Refused(DOWNGRADE_OWNER_NOT_DECLARED, "nation", None)


def test_check6_two_dimensions_lowered_needs_both_owners():
    label = lab("ATL", ["BDR"], [])
    r = rec(label=label)
    assert r == Refused(DOWNGRADE_OWNER_NOT_DECLARED, "data_rights_holder", None)
    assert rec(label=label, owner="rights-steward") == Refused(DOWNGRADE_OWNER_NOT_DECLARED, "nation", None)


def test_check6_lowers_nothing():
    same = lab(None, ["BDR"], ["H1"])
    assert rec(label=lab("BDR", [], ["H1"])) == Refused(DOWNGRADE_LOWERS_NOTHING, None, None)
    assert rec(label=lab("BDR", [], ["H1", "H2"])) == Refused(DOWNGRADE_LOWERS_NOTHING, None, None)
    assert same and rec(label=lab("BDR", None, ["H1"])).reason == DOWNGRADE_LOWERS_NOTHING


def test_check6_author_counts_only_under_single_authorship():
    floor = lab("BDR", [], ["H1"])
    label = lab("ATL", ["BDR"], ["H1"])
    assert isinstance(rec(floor=floor, label=label), Downgrade)
    assert isinstance(rec(floor=floor, label=lab("BDR", ["ATL"], ["H1"]), single_authorship=False), Downgrade)
    assert rec(floor=floor, label=lab("BDR", ["ATL"], ["H1"]), single_authorship=False, owner="x") == Refused(
        DOWNGRADE_OWNER_NOT_DECLARED, "nation", None
    )
    # With no single authorship the author grants nothing: ATL/[BDR] adds nothing over a floor of {BDR}.
    assert rec(floor=FLOOR, label=label, single_authorship=False).reason == DOWNGRADE_LOWERS_NOTHING


def test_check6_hierarchical_lowering_needs_class_steward():
    floor, label = {"classification": "S"}, {"classification": "C"}
    kw = dict(floor=floor, label=label, declaration=DH)
    assert rec(owner="class-steward", **kw).lowers == ("classification",)
    assert rec(owner="nation-steward", **kw) == Refused(DOWNGRADE_OWNER_NOT_DECLARED, "classification", None)
    assert rec(owner="class-steward", floor=label, label=floor, declaration=DH).reason == DOWNGRADE_LOWERS_NOTHING


def test_check6_invalid_label_and_malformed_floor():
    assert rec(label=lab("ZZZ", [], ["H1"])) == Refused(VALUE_OUT_OF_VOCABULARY, "nation", "ZZZ")
    assert rec(label={}).reason == "dimension_missing"
    assert rec(label=None).reason == VALUE_MALFORMED
    for bad in (None, {}, 5, lab("BDR", None, ["H1"]) | {"extra": 1}, lab(None, None, ["H1"]), lab(None, ["ZZZ"], ["H1"])):
        assert rec(floor=bad) == Refused(VALUE_MALFORMED, None, None), bad


def test_check6_floor_accepted_as_validating_label():
    r = rec(floor=lab("BDR", [], ["H1"]))
    assert isinstance(r, Downgrade)


@pytest.mark.parametrize("junk", [None, 5, "x", [], {}, object(), {"nation": 1}])
def test_never_raises(junk):
    for field in ("floor", "label", "reason", "inputs", "owner", "declaration", "single_authorship"):
        assert isinstance(rec(**{field: junk}), (Refused, Downgrade))


def test_no_automatic_downgrade():
    sig = inspect.signature(record_downgrade)
    for name, p in sig.parameters.items():
        assert p.kind is inspect.Parameter.KEYWORD_ONLY, name
        assert p.default is inspect.Parameter.empty, name
    assert "label" in sig.parameters
    given = lab("ATL", ["BDR"], ["H1"])
    r = rec(label=given)
    assert r.label == given


def test_marker_label_is_refused_a_downgrade_cannot_hand_out_a_rollup():
    marker = {"nation": {"rollup": True, "release": ["BDR", "CRD"]}, "data_rights_holder": ["H1"]}
    assert rec(label=marker) == Refused(VALUE_MALFORMED, "nation", None)
    assert rec(label=FLOOR) == Refused(VALUE_MALFORMED, "nation", None)


def test_marker_floor_counts_release_only():
    assert FLOOR["nation"] == {"rollup": True, "release": ["BDR"]}
    assert isinstance(rec(label=lab("ATL", ["BDR"], ["H1"])), Downgrade)
    # The floor's marker never supplies an author, even under single authorship.
    assert rec(label=lab("BDR", [], ["H1"]), floor=FLOOR).reason == DOWNGRADE_LOWERS_NOTHING
    wide = class_label(lab("ATL", ["BDR"], ["H1"]), D)
    assert rec(label=lab("ATL", ["BDR"], ["H1"]), floor=wide).reason == DOWNGRADE_LOWERS_NOTHING
