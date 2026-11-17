"""Tests for openddil_labels.class_key: the lk2 key of a rollup class row (ADR-0055 section 2a)."""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib" / "python"))

import openddil_labels as pkg  # noqa: E402
from openddil_labels import lk2, rollup, rollup_vectors  # noqa: E402
from openddil_labels import NoKey, class_key, class_label, compile_lk2, split_by_audience, verify_lk2  # noqa: E402

LIB = pathlib.Path(__file__).resolve().parents[1] / "lib" / "python" / "openddil_labels"
DATA = json.loads((LIB / "vectors" / "lk2.json").read_text(encoding="utf-8"))
BY_NAME = {v["name"]: v for v in DATA["vectors"]}
RIGHTS = lk2.declaration_from_data(DATA["declarations"]["nation_rights"])
NATION_ONLY = lk2.declaration_from_data(DATA["declarations"]["nation_only"])


def lab(author, release, holders=("H1",)):
    return {"nation": {"author": author, "release": release}, "data_rights_holder": list(holders)}


def test_split_classes_each_keyed():
    contributors = [
        ("c1", lab("ATL", ["BDR"])),
        ("c2", lab("ATL", ["BDR"])),
        ("c3", lab("BDR", ["CRD"])),
        ("c4", None),
    ]
    split = split_by_audience(contributors, RIGHTS)
    assert len(split.classes) == 2 and split.withheld == 1
    keyed = []
    for row in split.classes:
        res = class_key(row.label, RIGHTS)
        assert not isinstance(res, NoKey)
        key, body = res
        nation = body["dims"]["nation"]
        assert set(nation) == {"rollup", "release"} and nation["rollup"] is True
        assert nation["release"] == row.label["nation"]["release"]
        assert verify_lk2(key, body, declaration=RIGHTS)
        keyed.append(key)
    assert keyed[0] != keyed[1]


def test_contributors_with_swapped_author_fold_into_one_class():
    # ATL/[BDR] and BDR/[ATL] fold to the same release set, so they share one class row.
    split = split_by_audience([("c1", lab("ATL", ["BDR"])), ("c3", lab("BDR", ["ATL"]))], RIGHTS)
    assert len(split.classes) == 1
    assert split.classes[0].members == ("c1", "c3")


def test_class_key_differs_from_single_author_keys():
    split = split_by_audience([("c1", lab("ATL", ["BDR"])), ("c2", lab("ATL", ["BDR"]))], RIGHTS)
    assert len(split.classes) == 1
    ck = class_key(split.classes[0].label, RIGHTS)[0]
    for release in (["BDR"], ["ATL", "BDR"]):
        single = lk2.compile_label(lab("ATL", release), RIGHTS, life=None)
        assert not isinstance(single, NoKey)
        assert single[0].startswith("lk2:")
        assert ck != single[0]


def test_class_key_matches_vector():
    cl = class_label({"nation": {"author": "ATL", "release": ["BDR"]}}, NATION_ONLY)
    assert not isinstance(cl, NoKey) and isinstance(cl, dict)
    res = class_key(cl, NATION_ONLY)
    v = BY_NAME["rollup_over_one_author"]
    assert res == (v["label_key"], v["label"])
    assert res[0].startswith("lk2:")


def test_class_key_refuses_bad_forms():
    bad = NoKey("value_malformed", None)
    good = {"nation": {"rollup": True, "release": ["ATL"]}}
    assert class_key(good, NATION_ONLY) == compile_lk2(good, NATION_ONLY, life=None)
    assert class_key({"nation": {"rollup": True, "author": ["ATL"], "release": ["ATL"]}}, NATION_ONLY) == bad
    assert class_key({"nation": {"rollup": 1, "release": ["ATL"]}}, NATION_ONLY) == bad
    assert class_key({"nation": {"rollup": True, "release": ["ZZZ"]}}, NATION_ONLY) == bad
    assert class_key(None, NATION_ONLY) == bad
    assert class_key(good, None) == bad
    assert class_key(object(), object()) == bad


def test_class_key_legacy_policy_has_no_key():
    decl = rollup_vectors.load_declaration(rollup_vectors.declaration_data())
    label = {"nation": {"rollup": True, "release": ["ATL"]}, "data_rights_holder": ["H1"]}
    assert class_key(label, decl) == NoKey(lk2.POLICY_ID_NOT_URN_OID, None)


def test_export():
    assert pkg.class_key is rollup.class_key
    assert "class_key" in pkg.__all__
