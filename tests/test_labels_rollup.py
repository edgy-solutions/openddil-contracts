"""Tests for openddil_labels.rollup, named after ADR-0055 check 5 (section 3a).

Status: Builds on ADR-0055 §3a as written, ACCEPTED 2026-11-16 (an unlabelled contributor forms no class and is
counted in a withheld tally). The built regional rollup still keeps an empty-audience class, so it differs from
the ruling until it is changed.
"""

import itertools
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib" / "python"))

from openddil_labels import (  # noqa: E402
    DIMENSION_MISSING,
    DIMENSION_UNDECLARED,
    NO_LABEL,
    VALUE_OUT_OF_VOCABULARY,
    Declaration,
    Dimension,
    Refused,
    Split,
    admits,
    admits_class,
    class_label,
    split_by_audience,
)

NATIONS = ("ATL", "BDR", "CRD")
P = "example:policy-1"
NATION = Dimension.permissive("nation", NATIONS, "nation-steward", has_author=True)
HOLDER = Dimension.restrictive("data_rights_holder", ("H1", "H2"), "rights-steward")
CLASSIF = Dimension.hierarchical("classification", ("U", "C", "S"), "class-steward")


def decl(*dims):
    return Declaration(P, tuple(dims))


D1 = decl(NATION)
D3 = decl(NATION, HOLDER, CLASSIF)


def nl(author, release):
    return {"nation": {"author": author, "release": release}}


def rl(release):
    return {"nation": {"rollup": True, "release": release}}


def subsets(items):
    for n in range(len(items) + 1):
        for c in itertools.combinations(items, n):
            yield list(c)


def fourteen():
    out = []
    for i in range(7):
        out.append(("a%d" % i, nl("ATL", None if i % 2 else [])))
    for i in range(6):
        out.append(("b%d" % i, nl("BDR", [])))
    out.append(("x0", nl("ATL", ["BDR"])))
    return out


def test_check5_three_classes():
    s = split_by_audience(fourteen(), D1)
    assert [c.label["nation"]["release"] for c in s.classes] == [["ATL", "BDR"], ["ATL"], ["BDR"]]
    assert [len(c.members) for c in s.classes] == [1, 7, 6]
    assert all(c.label["nation"]["rollup"] is True and "author" not in c.label["nation"] for c in s.classes)
    assert s.withheld == 0 and s.withheld_by_reason == () and s.withheld_ids == ()


def test_check5_each_row_readable_only_by_its_class():
    s = split_by_audience(fourteen(), D1)
    rows = [c.label for c in s.classes]  # ATL+BDR, ATL, BDR (json order)

    def seen(nations):
        return [admits_class({"nation": nations}, r, D1) for r in rows]

    assert seen(["ATL"]) == [True, True, False]
    assert seen(["BDR"]) == [True, False, True]
    assert seen(["CRD"]) == [False, False, False]
    assert seen(["ATL", "BDR"]) == [True, True, True]


def _sum_check(contribs, decl_, viewers):
    nums = {cid: i + 1 for i, (cid, _) in enumerate(contribs)}
    s = split_by_audience(contribs, decl_)
    for v in viewers:
        via_classes = [m for c in s.classes if admits_class(v, c.label, decl_) for m in c.members]
        direct = [cid for cid, lab in contribs if admits(v, lab, decl_, single_authorship=True)]
        assert sum(nums[m] for m in via_classes) == sum(nums[m] for m in direct), v
        assert len(via_classes) == len(direct), v
        assert sorted(via_classes) == sorted(direct), v


def test_check5_sum_property():
    _sum_check(fourteen(), D1, [{"nation": n} for n in subsets(list(NATIONS))])


def test_check5_unlabelled_contributor_is_withheld_not_classed():
    before = split_by_audience(fourteen(), D1)
    after = split_by_audience(fourteen() + [("u0", None)], D1)
    assert after.classes == before.classes
    assert after.withheld == 1
    assert after.withheld_by_reason == ((NO_LABEL, 1),)
    assert "u0" in after.withheld_ids


def test_check5_proposed_s3a_no_empty_audience_class():
    s = split_by_audience([("m0", nl(None, [])), ("m1", nl("", [])), ("ok", nl("ATL", []))], D1)
    assert s.withheld == 2
    assert s.withheld_by_reason == ((DIMENSION_MISSING, 2),)
    assert s.withheld_ids == ("m0", "m1")
    assert len(s.classes) == 1
    assert all(c.label["nation"]["release"] for c in s.classes)


def test_check5_refusals_tallied_by_reason():
    contribs = [
        ("oov", nl("ZZZ", [])),
        ("undeclared", {"nation": {"author": "ATL", "release": []}, "extra": ["x"]}),
        ("missing", {}),
        ("none", None),
        ("fine", nl("ATL", [])),
    ]
    s = split_by_audience(contribs, D1)
    assert s.withheld == 4
    assert dict(s.withheld_by_reason) == {
        VALUE_OUT_OF_VOCABULARY: 1,
        DIMENSION_UNDECLARED: 1,
        DIMENSION_MISSING: 1,
        NO_LABEL: 1,
    }
    assert sum(n for _, n in s.withheld_by_reason) == s.withheld
    assert list(s.withheld_by_reason) == sorted(s.withheld_by_reason)
    assert s.withheld_ids == ("missing", "none", "oov", "undeclared")


def ml(author, release, holders, level):
    return {"nation": {"author": author, "release": release}, "data_rights_holder": holders, "classification": level}


def test_check5_multi_dimension():
    contribs = [
        ("c0", ml("ATL", [], ["H1"], "C")),
        ("c1", ml("ATL", [], ["H1", "H2"], "C")),
        ("c2", ml("ATL", ["BDR"], ["H1"], "C")),
        ("c3", ml("BDR", [], ["H1"], "S")),
        ("c4", ml("BDR", None, ["H1"], "C")),
        ("c5", ml("ATL", None, ["H1"], "C")),
    ]
    s = split_by_audience(contribs, D3)
    by = {c.members: c for c in s.classes}
    assert ("c0", "c5") in by  # differ only by release None vs []
    assert ("c1",) in by and ("c0", "c5") in by
    assert len(s.classes) == 5
    viewers = [
        {"nation": n, "data_rights_holder": h, "classification": lv}
        for n in subsets(list(NATIONS))
        for h in subsets(["H1", "H2"])
        for lv in ("U", "C", "S")
    ]
    _sum_check(contribs, D3, viewers)


def test_check5_determinism():
    c = fourteen() + [("u0", None), ("u1", nl("ZZZ", []))]
    base = split_by_audience(c, D1)
    assert isinstance(base, Split)
    for perm in (list(reversed(c)), c[5:] + c[:5], sorted(c, key=lambda p: p[0])):
        assert split_by_audience(perm, D1) == base
    assert split_by_audience(iter(c), D1) == base


def test_empty_input():
    assert split_by_audience([], D1) == Split((), 0, (), ())


@pytest.mark.parametrize("bad", [[("a", None), ("a", None)], [("", None)], [(1, None)], [(None, None)]])
def test_ids_are_programming_errors(bad):
    with pytest.raises(ValueError):
        split_by_audience(bad, D1)


def test_class_label_values():
    assert class_label(nl("ATL", None), D1) == class_label(nl("ATL", []), D1) == rl(["ATL"])
    assert class_label(nl("ATL", ["CRD", "BDR"]), D1) == rl(["ATL", "BDR", "CRD"])
    assert class_label(None, D1) == Refused(NO_LABEL, None, None)
    assert class_label({}, D1) == Refused(DIMENSION_MISSING, "nation", None)
    cl = class_label(ml("ATL", [], ["H2", "H1"], "C"), D3)
    assert cl == {"nation": {"rollup": True, "release": ["ATL"]}, "data_rights_holder": ["H1", "H2"], "classification": "C"}


@pytest.mark.parametrize(
    "bad",
    [
        nl("ATL", ["ATL"]),  # author present
        nl(None, ["ATL"]),  # the old form
        {"nation": {"author": [], "release": ["ATL"]}},  # empty author set, no marker
        {"nation": {"rollup": True, "author": "ATL", "release": ["ATL"]}},  # marker with an author
        {"nation": {"rollup": True, "author": None, "release": ["ATL"]}},  # marker with an author key
        {"nation": {"rollup": True, "author": [], "release": ["ATL"]}},
        {"nation": {"rollup": 1, "release": ["ATL"]}},
        {"nation": {"rollup": "true", "release": ["ATL"]}},
        {"nation": {"rollup": False, "release": ["ATL"]}},
        {"nation": {"release": ["ATL"]}},  # marker missing
        {"nation": {"rollup": True}},  # release absent
        rl(None),  # release None
        rl(["ZZZ"]),  # out of vocabulary
        rl("ATL"),  # not a collection
        rl({"ATL"}),  # a set is not a list or tuple
        rl([None]),
        {},  # missing dimension
        {"nation": {"rollup": True, "release": ["ATL"]}, "extra": ["x"]},  # extra dimension
        {"nation": ["ATL"]},  # wrong shape
        None,
        5,
        "nation",
        ["nation"],
        object(),
    ],
)
def test_admits_class_fail_closed(bad):
    for viewer in ({"nation": ["ATL"]}, {"nation": ["ATL", "BDR", "CRD"]}, None, 5, {1: 2}):
        assert admits_class(viewer, bad, D1) is False
    assert admits_class({"nation": ["ATL"]}, rl(["ATL"]), D1) is True
    assert admits_class({"nation": ["ATL"]}, rl(("ATL",)), D1) is True
    assert admits_class({"nation": ["ATL"]}, bad, object()) is False


def test_admits_class_viewer_junk():
    row = rl(["ATL"])
    for v in (None, 5, "x", [], {1: ["ATL"]}, {"nation": 5}, {"nation": None}):
        assert admits_class(v, row, D1) is False


def test_marker_empty_release_admits_nobody():
    for v in ({"nation": []}, {"nation": ["ATL"]}, {"nation": ["ATL", "BDR", "CRD"]}):
        assert admits_class(v, rl([]), D1) is False


def test_rollup_over_one_author_is_not_the_authors_label():
    contribs = [("c1", nl("ATL", None)), ("c2", nl("ATL", []))]
    s = split_by_audience(contribs, D1)
    assert len(s.classes) == 1
    label = s.classes[0].label
    assert label == rl(["ATL"])
    assert all(label != lab for _, lab in contribs)
    assert admits_class({"nation": ["ATL"]}, label, D1) is True
    assert admits_class({"nation": ["ATL"]}, nl("ATL", []), D1) is False
