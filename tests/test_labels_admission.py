"""Tests for openddil_labels.admission, named after the ADR-0055 Checks."""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib" / "python"))

from openddil_labels import (  # noqa: E402
    DIMENSION_AMBIGUOUS,
    DIMENSION_MISSING,
    DIMENSION_UNDECLARED,
    HIERARCHICAL_EMPTY,
    VALUE_MALFORMED,
    VALUE_OUT_OF_VOCABULARY,
    Declaration,
    Dimension,
    Refused,
    Valid,
    admits,
    high_water,
    validate,
)

NATIONS = ["ATL", "BDR", "CRD"]
P = "example:policy-1"


def decl(*dims):
    return Declaration(P, tuple(dims))


LEVEL = Dimension.hierarchical("level", ["low", "mid", "high"], "o")
PERM = Dimension.permissive("tags", ["H", "K"], "o", has_author=False)
RESTR = Dimension.restrictive("data_rights_holder", ["H", "K"], "o")
EXCL = Dimension.exclusionary("barred", ["H", "K"], "o")
NATION = Dimension.permissive("nation", NATIONS, "o", has_author=True)


def adm(viewer, label, d, single=True):
    return admits(viewer, label, d, single_authorship=single)


def test_check1_hierarchical_truth_table():
    d = decl(LEVEL)
    assert adm({"level": "mid"}, {"level": "mid"}, d)
    assert adm({"level": "high"}, {"level": "mid"}, d)
    assert not adm({"level": "low"}, {"level": "mid"}, d)
    assert not adm({}, {"level": "low"}, d)
    assert not adm({"level": "other"}, {"level": "low"}, d)
    for empty in (None, ""):
        assert validate({"level": empty}, d) == Refused(HIERARCHICAL_EMPTY, "level", None)
        assert not adm({"level": "high"}, {"level": empty}, d)


def test_check1_permissive_truth_table():
    d = decl(PERM)
    assert adm({"tags": ["H"]}, {"tags": ["H", "K"]}, d)
    assert not adm({"tags": ["K"]}, {"tags": ["H"]}, d)
    assert not adm({}, {"tags": ["H"]}, d)
    # empty set: released to nobody, even a viewer holding every value
    assert not adm({"tags": ["H", "K"]}, {"tags": []}, d)


def test_check1_restrictive_truth_table():
    d = decl(RESTR)
    assert adm({"data_rights_holder": ["H", "K"]}, {"data_rights_holder": ["H", "K"]}, d)
    assert adm({"data_rights_holder": ["H", "K"]}, {"data_rights_holder": ["H"]}, d)
    assert not adm({"data_rights_holder": ["H"]}, {"data_rights_holder": ["H", "K"]}, d)
    assert not adm({}, {"data_rights_holder": ["H"]}, d)
    # empty set: no restriction, a viewer holding nothing is admitted
    assert adm({}, {"data_rights_holder": []}, d)


def test_check1_exclusionary_truth_table():
    d = decl(EXCL)
    assert adm({"barred": ["K"]}, {"barred": ["H"]}, d)
    assert adm({}, {"barred": ["H", "K"]}, d)
    assert not adm({"barred": ["H", "K"]}, {"barred": ["H"]}, d)
    # empty set: no exclusion
    assert adm({}, {"barred": []}, d)
    assert adm({"barred": ["H", "K"]}, {"barred": []}, d)


def test_check1_nation_truth_table():
    d = decl(NATION)
    lab = {"nation": {"author": "ATL", "release": ["BDR"]}}
    assert adm({"nation": ["ATL"]}, lab, d, single=True)
    assert not adm({"nation": ["ATL"]}, lab, d, single=False)
    assert adm({"nation": ["BDR"]}, lab, d, single=False)
    assert not adm({"nation": ["CRD"]}, lab, d, single=True)
    absent = {"nation": {"author": "ATL", "release": None}}
    assert adm({"nation": ["ATL"]}, absent, d, single=True)
    assert not adm({"nation": ["BDR"]}, absent, d, single=True)
    empty = {"nation": {"author": "ATL", "release": []}}
    assert not adm({"nation": ["ATL", "BDR", "CRD"]}, empty, d, single=False)


def test_check1_conjunction():
    d = decl(LEVEL, RESTR)
    lab = {"level": "low", "data_rights_holder": ["H"]}
    assert adm({"level": "high", "data_rights_holder": ["H"]}, lab, d)
    assert not adm({"level": "high"}, lab, d)
    assert not adm({"level": "low", "data_rights_holder": ["H"]}, {"level": "mid", "data_rights_holder": ["H"]}, d)


def test_check2_missing_and_undeclared():
    d = decl(NATION)
    assert validate({}, d) == Refused(DIMENSION_MISSING, "nation", None)
    assert not adm({"nation": ["ATL"]}, {}, d)
    d2 = decl(NATION, RESTR)
    lab = {"nation": {"author": "ATL", "release": None}}
    assert validate(lab, d2) == Refused(DIMENSION_MISSING, "data_rights_holder", None)
    assert not adm({"nation": ["ATL"], "data_rights_holder": ["H"]}, lab, d2)
    extra = dict(lab, level="low")
    assert validate(extra, d) == Refused(DIMENSION_UNDECLARED, "level", None)
    assert not adm({"nation": ["ATL"]}, extra, d)
    assert validate({"nation": lab["nation"], "9x": 1}, d) == Refused(DIMENSION_UNDECLARED, "9x", None)
    assert validate({5: 1}, d) == Refused(DIMENSION_UNDECLARED, None, None)


def test_author_missing_is_unlabelled():
    d = decl(NATION)
    for author in (None, ""):
        r = validate({"nation": {"author": author, "release": ["BDR"]}}, d)
        assert r == Refused(DIMENSION_MISSING, "nation", None)


def test_check4_high_water_each_type():
    d = decl(LEVEL, PERM, RESTR, EXCL, NATION)

    def lab(level, perm, restr, excl, author, release):
        return {
            "level": level,
            "tags": perm,
            "data_rights_holder": restr,
            "barred": excl,
            "nation": {"author": author, "release": release},
        }

    a = lab("low", ["H", "K"], ["H"], ["H"], "ATL", ["BDR", "CRD"])
    b = lab("high", ["K"], ["K"], ["K"], "ATL", ["BDR"])
    hw = high_water([a, b], d, single_authorship=True)
    assert hw["level"] == "high"
    assert hw["tags"] == ["K"]
    assert hw["data_rights_holder"] == ["H", "K"]
    assert hw["barred"] == ["H", "K"]
    assert hw["nation"] == {"author": "ATL", "release": ["BDR"]}
    assert isinstance(validate(hw, d), Valid)


def test_check4_high_water_none_inputs():
    d = decl(RESTR)
    ok = {"data_rights_holder": ["H"]}
    assert high_water([], d, single_authorship=True) is None
    assert high_water([ok, None], d, single_authorship=True) is None
    assert high_water([ok, {}], d, single_authorship=True) is None
    assert high_water(None, d, single_authorship=True) is None


def test_check4_high_water_nation_authors():
    d = decl(NATION)
    a = {"nation": {"author": "ATL", "release": []}}
    b = {"nation": {"author": "ATL", "release": ["BDR"]}}
    hw = high_water([a, b], d, single_authorship=True)
    assert hw == {"nation": {"author": "ATL", "release": []}}
    assert isinstance(validate(hw, d), Valid)
    # two authors: no author claimed, intersection of effective audiences
    c = {"nation": {"author": "BDR", "release": ["ATL"]}}
    hw2 = high_water([b, c], d, single_authorship=True)
    assert hw2 == {"nation": {"author": None, "release": ["ATL", "BDR"]}}
    assert validate(hw2, d) == Refused(DIMENSION_MISSING, "nation", None)
    # single_authorship false: an aggregate claims no author even when shared
    hw3 = high_water([a, b], d, single_authorship=False)
    assert hw3["nation"]["author"] is None
    assert hw3["nation"]["release"] == ["ATL"]


def test_check4_high_water_of_one_label_is_that_label():
    # Absent and declared-empty release are two keys (check 3), so the high-water may not turn one
    # into the other, and a release naming the author keeps it.
    from openddil_labels import compile_lk1

    d = decl(NATION)
    for release in (None, [], ["BDR"], ["ATL", "BDR"]):
        lab = {"nation": {"author": "ATL", "release": release}}
        hw = high_water([lab], d, single_authorship=True)
        assert hw == validate(lab, d).label
        assert compile_lk1(P, "ATL", hw["nation"]["release"]) == compile_lk1(P, "ATL", release)
    absent = {"nation": {"author": "ATL", "release": None}}
    assert high_water([absent, absent], d, single_authorship=True)["nation"]["release"] is None
    # absent with declared: the release is declared, and the audience is the author alone either way
    mixed = high_water([absent, {"nation": {"author": "ATL", "release": ["BDR"]}}], d, single_authorship=True)
    assert mixed == {"nation": {"author": "ATL", "release": []}}
    for viewer, want in ((["ATL"], True), (["BDR"], False)):
        assert adm({"nation": viewer}, mixed, d) is want


def test_check7_red_case():
    full = decl(NATION, RESTR)
    lab = {"nation": {"author": "ATL", "release": None}, "data_rights_holder": ["H"]}
    assert not adm({"nation": ["ATL"]}, lab, full, single=True)
    assert adm({"nation": ["ATL"], "data_rights_holder": ["H"]}, lab, full, single=True)
    nation_only = decl(NATION)
    assert adm({"nation": ["ATL"]}, {"nation": {"author": "ATL", "release": None}}, nation_only, single=True)


def test_check9_out_of_vocabulary_names_value():
    d = decl(NATION, RESTR, LEVEL)
    r = validate({"nation": {"author": "ZZZ", "release": None}, "data_rights_holder": [], "level": "low"}, d)
    assert r == Refused(VALUE_OUT_OF_VOCABULARY, "nation", "ZZZ")
    r = validate({"nation": {"author": "ATL", "release": ["BDR", "QQQ", "PPP"]}, "data_rights_holder": [], "level": "low"}, d)
    assert r == Refused(VALUE_OUT_OF_VOCABULARY, "nation", "PPP")
    r = validate({"nation": {"author": "ATL", "release": None}, "data_rights_holder": ["X"], "level": "low"}, d)
    assert r == Refused(VALUE_OUT_OF_VOCABULARY, "data_rights_holder", "X")
    r = validate({"nation": {"author": "ATL", "release": None}, "data_rights_holder": [], "level": "top"}, d)
    assert r == Refused(VALUE_OUT_OF_VOCABULARY, "level", "top")


def test_malformed_values():
    d = decl(NATION, RESTR, LEVEL)
    good = {"nation": {"author": "ATL", "release": None}, "data_rights_holder": [], "level": "low"}
    assert isinstance(validate(good, d), Valid)
    for key, bad in (
        ("data_rights_holder", "H"),
        ("data_rights_holder", [1]),
        ("data_rights_holder", {"H": 1}),
        ("level", 3),
        ("nation", "ATL"),
        ("nation", {"author": "ATL"}),
        ("nation", {"author": "ATL", "release": "BDR"}),
        ("nation", {"author": "ATL", "release": [1]}),
        ("nation", {"author": "ATL", "release": None, "x": 1}),
    ):
        r = validate(dict(good, **{key: bad}), d)
        assert isinstance(r, Refused) and r.reason == VALUE_MALFORMED, (key, bad)
    assert validate(dict(good, data_rights_holder=None), d) == Refused(DIMENSION_MISSING, "data_rights_holder", None)


def test_valid_label_is_normalised():
    d = decl(NATION, RESTR)
    r = validate(
        {"Data Rights Holder": ("K", "H", "K"), "nation": {"author": "ATL", "release": {"CRD", "BDR"}}}, d
    )
    assert r == Valid(
        {"nation": {"author": "ATL", "release": ["BDR", "CRD"]}, "data_rights_holder": ["H", "K"]}
    )


def test_names_in_labels():
    d = decl(RESTR)
    assert isinstance(validate({"Data Rights Holder": ["H"]}, d), Valid)
    r = validate({"data_rights_holder": ["H"], "Data-Rights-Holder": ["H"]}, d)
    assert r == Refused(DIMENSION_AMBIGUOUS, "data_rights_holder", None)


def test_no_implicit_label_empty_is_missing():
    assert validate({}, decl(RESTR)) == Refused(DIMENSION_MISSING, "data_rights_holder", None)
    assert validate({}, decl(NATION, LEVEL)).reason == DIMENSION_MISSING


@pytest.mark.parametrize("garbage", [None, 5, [], ["nation"], "nation", 1.5, object()])
def test_never_raises(garbage):
    d = decl(NATION)
    good = {"nation": {"author": "ATL", "release": None}}
    assert isinstance(validate(garbage, d), Refused)
    assert admits(garbage, good, d, single_authorship=True) is False
    assert admits({"nation": ["ATL"]}, garbage, d, single_authorship=True) is False
    assert high_water([garbage], d, single_authorship=True) is None
    assert high_water(garbage, d, single_authorship=True) is None
    assert admits({"nation": garbage}, good, d, single_authorship=True) in (False,)
    assert isinstance(validate(good, garbage), Refused)
    assert admits({"nation": ["ATL"]}, good, garbage, single_authorship=True) is False
