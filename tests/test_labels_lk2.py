"""Tests for openddil_labels.lk2 (ADR-0055 sections 2a and 2b)."""

import copy
import hashlib
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib" / "python"))

import openddil_labels as pkg  # noqa: E402
from openddil_labels import lk1, lk2  # noqa: E402
from openddil_labels.lk2 import (  # noqa: E402
    AUTHOR_EMPTY,
    DECLARATION_NOT_LK2,
    FORM_IS_LK1,
    LIFE_MALFORMED,
    NoKey,
    POLICY_ID_NOT_URN_OID,
    VALUE_MALFORMED,
    canonical_lk2,
    check_lk2_declaration,
    check_policy_id,
    compile_label,
    compile_lk2,
    declaration_from_data,
    generate_vectors,
    verify_label,
    verify_lk2,
)

LIB = pathlib.Path(__file__).resolve().parents[1] / "lib" / "python" / "openddil_labels"
VECTORS = LIB / "vectors" / "lk2.json"
LK1_VECTORS = LIB / "vectors" / "lk1.json"

DATA = json.loads(VECTORS.read_text(encoding="utf-8"))
BY_NAME = {v["name"]: v for v in DATA["vectors"]}
DECLS = {k: declaration_from_data(d) for k, d in DATA["declarations"].items()}

REQUIRED = """composite_release composite_release_empty composite_release_absent composite_duplicate_authors
rollup_release rollup_release_empty rollup_release_absent rollup_not_true rollup_over_one_author
single_author_atl_bdr single_author_atl_atl_bdr single_author_as_list lk1_keeps_key_legacy_policy
legacy_policy_composite author_empty_no_marker author_null_no_marker marker_with_author marker_with_empty_author
second_dim_empty second_dim_values second_dim_missing second_dim_null dimension_undeclared dimension_undeclared_byte_order hierarchical_level
hierarchical_as_list rollup_with_two_dims separator_pipe separator_comma separator_tilde separator_at
value_empty_string value_too_long value_space nation_author_malformed life_a life_b life_extra_member
life_missing_review life_bad_time life_offset life_lowercase_z life_feb_30 life_on_lk1_form
life_on_lk1_legacy_policy life_malformed_on_lk1_form no_policy""".split()


def decl_of(v):
    return None if v["declaration"] is None else DECLS[v["declaration"]]


def test_vectors_regenerate_byte_for_byte():
    text = json.dumps(generate_vectors(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    raw = VECTORS.read_bytes()
    assert raw == text.encode("utf-8")
    assert b"\r" not in raw


def test_every_vector_recomputes():
    for v in DATA["vectors"]:
        decl = decl_of(v)
        res = compile_label(v["dims"], decl, life=v["life"])
        if isinstance(res, NoKey):
            assert v["no_key"] == res.reason, v["name"]
            assert v["no_key_dimension"] == res.dimension, v["name"]
            assert v["label_key"] is None and v["label"] is None and v["canonical"] is None
            assert v["form"] is None
            continue
        key, body = res
        assert v["no_key"] is None and v["no_key_dimension"] is None
        assert (v["label_key"], v["label"]) == (key, body), v["name"]
        prefix = "lk1:" if v["form"] == "lk1" else "lk2:"
        assert key == prefix + hashlib.sha256(v["canonical"].encode("utf-8")).hexdigest()
        assert key.startswith(prefix)
        assert v["canonical"].startswith(v["form"] + "|")
        if v["form"] == "lk2":
            assert canonical_lk2(v["dims"], decl, life=v["life"]) == v["canonical"]
            assert verify_lk2(key, body, declaration=None)
            assert verify_lk2(key, body, declaration=decl)
        else:
            bare = {k: x for k, x in body.items() if k != "life"}
            assert lk1.verify(key, bare)
        assert ("life" in body) == (v["life"] is not None), v["name"]
        assert verify_label(key, body, declaration=None)
        assert verify_label(key, body, declaration=decl)


def test_required_vectors_exist():
    for name in REQUIRED:
        assert name in BY_NAME, name
    assert len(DATA["vectors"]) == len(BY_NAME)


def test_expected_outcomes():
    expect = {
        "composite_release": ("lk2", "ATL,BDR|CRD"),
        "composite_release_empty": ("lk2", "ATL,BDR|"),
        "rollup_release": ("lk2", "@rollup|ATL,BDR"),
        "rollup_release_empty": ("lk2", "@rollup|"),
        "single_author_atl_bdr": ("lk1", None),
        "single_author_atl_atl_bdr": ("lk1", None),
        "single_author_as_list": ("lk1", None),
        "lk1_keeps_key_legacy_policy": ("lk1", None),
        "second_dim_empty": ("lk2", "|data_rights_holder|"),
        "second_dim_values": ("lk2", "|data_rights_holder|H1,H2"),
        "rollup_with_two_dims": ("lk2", None),
        "hierarchical_level": ("lk2", None),
        "life_a": ("lk2", None),
        "life_b": ("lk2", None),
        "life_on_lk1_form": ("lk1", None),
        "life_on_lk1_legacy_policy": ("lk1", None),
    }
    for name, (form, tail) in expect.items():
        v = BY_NAME[name]
        assert v["form"] == form, name
        if tail is not None:
            assert v["canonical"].endswith(tail) or ("|nation|" + tail) in v["canonical"], name
    no_key = {
        "composite_release_absent": ("release_absent", "nation"),
        "rollup_release_absent": ("release_absent", "nation"),
        "rollup_not_true": ("value_malformed", "nation"),
        "legacy_policy_composite": ("policy_id_not_urn_oid", None),
        "author_empty_no_marker": ("author_empty", "nation"),
        "author_null_no_marker": ("author_empty", "nation"),
        "marker_with_author": ("rollup_with_author", "nation"),
        "marker_with_empty_author": ("rollup_with_author", "nation"),
        "second_dim_missing": ("dimension_missing", "data_rights_holder"),
        "second_dim_null": ("dimension_missing", "data_rights_holder"),
        "dimension_undeclared": ("dimension_undeclared", "caveat"),
        "dimension_undeclared_byte_order": ("dimension_undeclared", "Caveat"),
        "hierarchical_as_list": ("value_malformed", "classification"),
        "separator_pipe": ("value_malformed", "data_rights_holder"),
        "separator_comma": ("value_malformed", "data_rights_holder"),
        "separator_tilde": ("value_malformed", "data_rights_holder"),
        "separator_at": ("value_malformed", "data_rights_holder"),
        "value_empty_string": ("value_malformed", "data_rights_holder"),
        "value_too_long": ("value_malformed", "data_rights_holder"),
        "value_space": ("value_malformed", "data_rights_holder"),
        "nation_author_malformed": ("value_malformed", "nation"),
        "life_extra_member": ("life_malformed", None),
        "life_missing_review": ("life_malformed", None),
        "life_bad_time": ("life_malformed", None),
        "life_offset": ("life_malformed", None),
        "life_lowercase_z": ("life_malformed", None),
        "life_feb_30": ("life_malformed", None),
        "life_malformed_on_lk1_form": ("life_malformed", None),
        "no_policy": ("no_policy", None),
    }
    for name, (reason, dim) in no_key.items():
        assert (BY_NAME[name]["no_key"], BY_NAME[name]["no_key_dimension"]) == (reason, dim), name
    # a one-author label under a second dimension is still lk2
    assert BY_NAME["second_dim_empty"]["form"] == "lk2"
    # composite rollup release empty is a keyed label
    assert BY_NAME["composite_release_empty"]["label"]["dims"]["nation"]["release"] == []


def test_same_key_and_not_key_pairs():
    for v in DATA["vectors"]:
        if "same_key_as" in v:
            assert v["label_key"] is not None
            assert v["label_key"] == BY_NAME[v["same_key_as"]]["label_key"], v["name"]
        if "not_key_of" in v:
            keys = {BY_NAME[n]["label_key"] for n in v["not_key_of"]}
            assert len(keys) == len(v["not_key_of"])
            assert v["label_key"] not in keys
    a, b, c = BY_NAME["life_a"], BY_NAME["life_b"], BY_NAME["composite_release"]
    assert a["label_key"] == b["label_key"] == c["label_key"]
    assert a["label"] != b["label"]
    strip = lambda body: {k: x for k, x in body.items() if k != "life"}  # noqa: E731
    assert strip(a["label"]) == strip(b["label"]) == c["label"]
    assert "life" not in c["label"]
    assert a["label"]["life"] == a["life"] and b["label"]["life"] == b["life"]


def test_lk1_form_key_is_compile_lk1():
    v = BY_NAME["single_author_atl_bdr"]
    assert (v["label_key"], v["label"]) == lk1.compile_lk1(DECLS["nation_only"].policy_id, "ATL", ["BDR"])
    legacy = BY_NAME["lk1_keeps_key_legacy_policy"]
    lk1_vectors = {x["name"]: x for x in json.loads(LK1_VECTORS.read_text(encoding="utf-8"))}
    assert legacy["label_key"] == lk1_vectors["atl_bdr"]["label_key"]
    assert legacy["label"] == lk1_vectors["atl_bdr"]["label"]


def test_compile_lk2_and_canonical_refuse_lk1_form():
    decl = DECLS["nation_only"]
    for dims in ({"nation": {"author": "ATL", "release": ["BDR"]}}, {"nation": {"author": ["ATL"], "release": None}}):
        assert compile_lk2(dims, decl, life=None) == NoKey(FORM_IS_LK1, "nation")
        assert canonical_lk2(dims, decl, life=None) == NoKey(FORM_IS_LK1, "nation")


def test_canonical_order_is_byte_order():
    c = BY_NAME["hierarchical_level"]["canonical"]
    assert "|classification|" in c and "|data_rights_holder|" in c
    assert c.index("|classification|") < c.index("|data_rights_holder|")
    names = [d.name for d in DECLS["nation_rights_level"].dimensions]
    assert names.index("data_rights_holder") < names.index("classification")
    assert c == (
        "lk2|urn:oid:1.3.6.1.4.1.32473.3|nation|ATL,BDR|CRD|classification|L2|data_rights_holder|H1"
    )


def _lk2_item(name="composite_release"):
    v = BY_NAME[name]
    return v["label_key"], copy.deepcopy(v["label"]), decl_of(v)


def test_verify_false_cases():
    key, body, decl = _lk2_item()
    assert verify_lk2(key, body, declaration=None) and verify_label(key, body, declaration=None)

    def bad(mutate, k=key):
        b = copy.deepcopy(body)
        mutate(b)
        assert not verify_lk2(k, b, declaration=None), b
        assert not verify_label(k, b, declaration=None), b

    bad(lambda b: b["dims"]["nation"].__setitem__("release", ["ATL"]))
    bad(lambda b: b.__setitem__("extra", 1))
    bad(lambda b: b.__setitem__("v", 1))
    bad(lambda b: b.__setitem__("v", True))
    bad(lambda b: b.__setitem__("v", "2"))
    bad(lambda b: b.__setitem__("policy", "example:policy-1"))
    bad(lambda b: b.__setitem__("policy", "urn:isbn:0451450523"))
    bad(lambda b: b.__setitem__("life", {"CreationDateTime": "2026-11-16T09:30:00Z", "ReviewDateTime": None, "x": 1}))
    bad(lambda b: b["dims"]["nation"].__setitem__("author", ["BDR", "ATL"]))
    bad(lambda b: b["dims"].__setitem__("extra", ["X"]))
    # uppercase hex
    assert not verify_lk2("lk2:" + key[4:].upper(), body, declaration=None)
    assert not verify_label("lk2:" + key[4:].upper(), body, declaration=None)
    # lk1 form re-wrapped as v 2
    k1, b1 = lk1.compile_lk1(decl.policy_id, "ATL", ["BDR"])
    wrapped = {"policy": b1["policy"], "v": 2, "dims": {"nation": {"author": ["ATL"], "release": ["BDR"]}}}
    canon = "lk2|%s|nation|ATL|BDR" % decl.policy_id
    wk = "lk2:" + hashlib.sha256(canon.encode()).hexdigest()
    assert not verify_lk2(wk, wrapped, declaration=None) and not verify_label(wk, wrapped, declaration=None)
    # an lk2: key over an lk1 body
    assert not verify_label("lk2:" + k1[4:], b1, declaration=None)
    assert not verify_lk2("lk2:" + k1[4:], b1, declaration=None)
    # an lk1 key over an lk2 body
    assert not verify_label("lk1:" + key[4:], body, declaration=None)
    # prefix mismatch / unknown prefix
    assert not verify_label("lk3:" + key[4:], body, declaration=None)
    # a life that rides along is fine
    lk, lb, _ = _lk2_item("life_b")
    assert verify_lk2(lk, lb, declaration=None) and verify_label(lk, lb, declaration=None)


def test_verify_never_raises():
    key, body, _ = _lk2_item()
    for k in (key, None, 1, b"x", ["lk2:x"]):
        for b in (None, [], "", {}, {"dims": object()}, {"policy": 1, "v": 2, "dims": {"nation": 3}}, 5):
            assert verify_lk2(k, b, declaration=None) is False
            assert verify_label(k, b, declaration=None) is False
    assert verify_label(None, body, declaration=None) is False
    assert verify_label(1, body, declaration=None) is False
    assert verify_lk2(key, body, declaration=object()) is False
    assert verify_label("", body, declaration=None) is False


def test_verify_with_declaration_catches_set_for_hierarchy():
    v = BY_NAME["hierarchical_level"]
    decl = DECLS["nation_rights_level"]
    key, body = v["label_key"], copy.deepcopy(v["label"])
    assert verify_lk2(key, body, declaration=decl)
    body["dims"]["classification"] = ["L2"]
    # same canonical text, so the key is unchanged and the body-only check accepts it
    assert verify_lk2(key, body, declaration=None)
    assert not verify_lk2(key, body, declaration=decl)
    assert not verify_label(key, body, declaration=decl)
    # and the other way: a hierarchical string where the policy declares a set
    rights = BY_NAME["second_dim_values"]
    rb = copy.deepcopy(rights["label"])
    rb["dims"]["data_rights_holder"] = "H1"
    rk = "lk2:" + hashlib.sha256(b"lk2|urn:oid:1.3.6.1.4.1.32473.2|nation|ATL|BDR|data_rights_holder|H1").hexdigest()
    assert verify_lk2(rk, rb, declaration=None)
    assert not verify_lk2(rk, rb, declaration=DECLS["nation_rights"])


ACCEPTED_IDS = ["urn:oid:1.3.6.1.4.1.32473.1", "urn:oid:1.3.26.1.3.1", "urn:oid:0.0", "urn:oid:2.999.5"]
REFUSED_IDS = [
    "urn:isbn:0451450523",
    "example:policy-1",
    "URN:OID:1.2",
    "urn:oid:1.03",
    "urn:oid:3.1",
    "urn:oid:1",
    "urn:oid:1." + "1" * 60,
    "urn:oid:1.2.",
    "urn:oid:1..2",
    "",
    None,
    1,
]


@pytest.mark.parametrize("pid", ACCEPTED_IDS)
def test_policy_id_accepted(pid):
    assert check_policy_id(pid) is None


@pytest.mark.parametrize("pid", REFUSED_IDS)
def test_policy_id_refused(pid):
    with pytest.raises(ValueError) as e:
        check_policy_id(pid)
    assert repr(pid) in str(e.value)


def test_policy_id_vector_list():
    got = {repr(x["policy_id"]): x["accepted"] for x in DATA["policy_ids"]}
    assert got["'urn:oid:1.3.6.1.4.1.32473.1'"] is True
    assert got["'urn:isbn:0451450523'"] is False
    assert got["'example:policy-1'"] is False
    assert got["None"] is False and got["1"] is False
    assert any(x["accepted"] for x in DATA["policy_ids"]) and any(not x["accepted"] for x in DATA["policy_ids"])


def _data(*dims, pid="urn:oid:1.3.6.1.4.1.32473.9"):
    return {"policy_id": pid, "dimensions": list(dims)}


def _d(name, type_, vocab, has_author=False):
    return {"name": name, "type": type_, "vocabulary": vocab, "owner": "o", "has_author": has_author}


NATION = _d("nation", "permissive", ["ATL", "BDR"], True)


def test_check_lk2_declaration():
    for d in DECLS.values():
        if d.policy_id.startswith("urn:oid:"):
            assert check_lk2_declaration(d) is None
    refused = [
        declaration_from_data(_data(NATION, pid="example:policy-1")),
        declaration_from_data(_data(_d("caveat", "restrictive", ["X"]))),
        declaration_from_data(_data(_d("nation", "permissive", ["ATL"], False))),
        declaration_from_data(_data(NATION, _d("other", "permissive", ["X"], True))),
        declaration_from_data(_data(_d("nation", "permissive", ["atl"], True))),
        declaration_from_data(_data(NATION, _d("holder", "restrictive", ["a|b"]))),
        declaration_from_data(_data(NATION, _d("holder", "restrictive", ["a,b"]))),
        declaration_from_data(_data(NATION, _d("holder", "restrictive", ["a~b"]))),
        declaration_from_data(_data(NATION, _d("holder", "restrictive", ["@rollup"]))),
        declaration_from_data(_data(NATION, _d("level", "hierarchical", ["L1", "L|2"]))),
        declaration_from_data(_data(NATION, _d("holder", "exclusionary", ["H" + "1" * 63]))),
    ]
    for d in refused:
        with pytest.raises(ValueError):
            check_lk2_declaration(d)
    with pytest.raises(ValueError):
        check_lk2_declaration(None)
    # the reasons compile_lk2 gives
    dims = {"nation": {"rollup": True, "release": ["ATL"]}}
    assert compile_lk2(dims, refused[0], life=None) == NoKey(POLICY_ID_NOT_URN_OID, None)
    assert compile_lk2(dims, refused[2], life=None) == NoKey(DECLARATION_NOT_LK2, None)


def test_legacy_declaration_is_still_valid_and_keeps_lk1():
    legacy = DECLS["legacy_nation_only"]
    assert legacy.policy_id == "example:policy-1"
    res = compile_label({"nation": {"author": "ATL", "release": ["BDR"]}}, legacy, life=None)
    assert res == lk1.compile_lk1("example:policy-1", "ATL", ["BDR"])


LIFE_OK = {"CreationDateTime": "2026-11-16T09:30:00Z", "ReviewDateTime": None}
COMP = {"nation": {"author": ["ATL", "BDR"], "release": ["CRD"]}}


def _life(life):
    return compile_lk2(COMP, DECLS["nation_only"], life=life)


def test_life_accepted():
    assert not isinstance(_life(LIFE_OK), NoKey)
    assert not isinstance(_life({"CreationDateTime": "2026-11-16T09:30:00.5Z", "ReviewDateTime": "2027-01-01T00:00:00.123456Z"}), NoKey)
    assert _life(None)[0] == _life(LIFE_OK)[0]
    key, body = _life(LIFE_OK)
    assert body["life"] == LIFE_OK
    assert LIFE_OK is not body["life"]


@pytest.mark.parametrize(
    "life",
    [
        {"CreationDateTime": "2026-11-16T09:30:00Z", "ReviewDateTime": None, "X": 1},
        {"CreationDateTime": "2026-11-16T09:30:00Z"},
        {"ReviewDateTime": None},
        {"CreationDateTime": None, "ReviewDateTime": None},
        {"CreationDateTime": "2026-11-16", "ReviewDateTime": None},
        {"CreationDateTime": "2026-11-16T09:30:00+00:00", "ReviewDateTime": None},
        {"CreationDateTime": "2026-11-16T09:30:00z", "ReviewDateTime": None},
        {"CreationDateTime": "2026-11-16T09:30:00Z", "ReviewDateTime": "later"},
        {"CreationDateTime": "2026-02-30T09:30:00Z", "ReviewDateTime": None},
        {"CreationDateTime": "2026-11-16T09:30:60Z", "ReviewDateTime": None},
        {"CreationDateTime": "2026-11-16T24:00:00Z", "ReviewDateTime": None},
        {"CreationDateTime": "2026-11-16T09:30:00.Z", "ReviewDateTime": None},
        [],
        "x",
        5,
        {},
    ],
)
def test_life_refused(life):
    assert _life(life) == NoKey(LIFE_MALFORMED, None)
    assert compile_label(COMP, DECLS["nation_only"], life=life) == NoKey(LIFE_MALFORMED, None)


def test_life_on_lk1_form_keeps_lk1_key():
    # Ruled 2026-11-17: an lk1 label with life gets its lk1 key; life never enters any key.
    one = {"nation": {"author": "ATL", "release": ["BDR"]}}
    decl = DECLS["nation_only"]
    key, bare = lk1.compile_lk1(decl.policy_id, "ATL", ["BDR"])
    got_key, body = compile_label(one, decl, life=LIFE_OK)
    assert got_key == key == compile_label(one, decl, life=None)[0]
    assert body == dict(bare, life=LIFE_OK)
    assert compile_label(one, decl, life=None) == (key, bare)
    assert verify_label(key, body, declaration=None)
    assert verify_label(key, body, declaration=decl)
    # lk1.verify itself is unchanged: exactly policy, v and dims
    assert not lk1.verify(key, body)
    assert lk1.verify(key, bare)
    # a malformed life is refused on the lk1 form too
    assert compile_label(one, decl, life="garbage") == NoKey(LIFE_MALFORMED, None)
    assert compile_label(one, decl, life=dict(LIFE_OK, Extra="x")) == NoKey(LIFE_MALFORMED, None)
    for bad in (None, {}, dict(LIFE_OK, Extra="x"), dict(LIFE_OK, CreationDateTime="2026-11-16")):
        assert not verify_label(key, dict(bare, life=bad), declaration=None)
    # the legacy-id lk1 key is unchanged by life
    legacy = BY_NAME["life_on_lk1_legacy_policy"]
    assert legacy["label_key"] == BY_NAME["lk1_keeps_key_legacy_policy"]["label_key"]
    assert legacy["label"]["life"] == legacy["life"]


def test_declaration_from_data_has_author():
    from copy import deepcopy

    for bad in (_MISSING, None, 1, 0, "true"):
        d = deepcopy(NATION)
        if bad is _MISSING:
            del d["has_author"]
        else:
            d["has_author"] = bad
        with pytest.raises(ValueError, match="has_author must be a bool: nation"):
            declaration_from_data(_data(d))
    for type_ in ("restrictive", "hierarchical", "exclusionary"):
        with pytest.raises(ValueError, match="only valid on a permissive"):
            declaration_from_data(_data(NATION, _d("x", type_, ["A"], True)))
    d = _d("x", "restrictive", ["A"])
    del d["has_author"]
    with pytest.raises(ValueError, match="has_author must be a bool: x"):
        declaration_from_data(_data(NATION, d))
    for name, data in DATA["declarations"].items():
        assert declaration_from_data(data) == DECLS[name]


_MISSING = object()


def test_undeclared_key_byte_order_any_insertion_order():
    import itertools

    decl = DECLS["nation_only"]
    comp = BY_NAME["dimension_undeclared_byte_order"]["dims"]["nation"]
    items = {"zz": ["X"], "Caveat": ["X"], "b": ["X"], "nation": comp}
    for perm in itertools.permutations(items):
        dims = {k: items[k] for k in perm}
        for f in (compile_label, compile_lk2):
            assert f(dims, decl, life=None) == NoKey("dimension_undeclared", "Caveat"), perm


def test_garbage_never_raises():
    nation_only, rights = DECLS["nation_only"], DECLS["nation_rights"]
    vm = NoKey(VALUE_MALFORMED, None)
    for f in (compile_lk2, canonical_lk2, compile_label):
        fn = lambda d, decl, f=f: f(d, decl, life=None)  # noqa: E731
        assert fn(None, nation_only) == vm
        assert fn([], nation_only) == vm
        assert fn("nation", nation_only) == vm
        assert fn(object(), nation_only) == vm
        assert fn({1: "x"}, nation_only) == NoKey("dimension_undeclared", None)
        assert fn({"nation": "ATL"}, nation_only) == NoKey(VALUE_MALFORMED, "nation")
        assert fn({"nation": ["ATL"]}, nation_only) == NoKey(VALUE_MALFORMED, "nation")
        assert fn({}, nation_only) == NoKey("dimension_missing", "nation")
        assert fn({"nation": None}, rights) == NoKey("dimension_missing", "nation")
        assert fn(COMP, object()).reason in (DECLARATION_NOT_LK2, VALUE_MALFORMED)
        assert fn({"nation": {"author": 5, "release": []}}, nation_only) == NoKey(VALUE_MALFORMED, "nation")
        assert fn({"nation": {"author": ["ATL", "BDR"]}}, nation_only) == NoKey(VALUE_MALFORMED, "nation")
        assert fn({"nation": {"author": [""], "release": []}}, nation_only) == NoKey(VALUE_MALFORMED, "nation")
        assert fn({"nation": {"author": "", "release": []}}, nation_only) == NoKey(AUTHOR_EMPTY, "nation")
        assert fn({"nation": {"rollup": "true", "release": []}}, nation_only) == NoKey(VALUE_MALFORMED, "nation")
        assert fn({"nation": {"rollup": False, "release": []}}, nation_only) == NoKey(VALUE_MALFORMED, "nation")
        assert fn({"nation": {"rollup": True, "author": None, "release": []}}, nation_only) == NoKey(
            "rollup_with_author", "nation"
        )
        assert fn({"nation": {"rollup": True}}, nation_only) == NoKey("release_absent", "nation")
        assert fn({"nation": {"rollup": True, "release": "ATL"}}, nation_only) == NoKey(VALUE_MALFORMED, "nation")
        assert fn({"nation": {"rollup": True, "release": [], "x": 1}}, nation_only) == NoKey(VALUE_MALFORMED, "nation")
        assert fn({"nation": {"rollup": True, "release": ["atl"]}}, nation_only) == NoKey(VALUE_MALFORMED, "nation")
        assert fn({"nation": {"author": ["ATL", "BDR"], "release": ["CRD"]}, "data_rights_holder": "H1"}, rights) == NoKey(
            VALUE_MALFORMED, "data_rights_holder"
        )
        assert fn({"nation": {"rollup": True, "release": []}, "data_rights_holder": [1]}, rights) == NoKey(
            VALUE_MALFORMED, "data_rights_holder"
        )
        assert fn(COMP, None) == NoKey("no_policy", None)


def test_set_dimension_normalisation():
    decl = DECLS["nation_rights"]
    dims = {"nation": {"rollup": True, "release": ("BDR", "ATL", "ATL")}, "data_rights_holder": {"H2", "H1"}}
    key, body = compile_lk2(dims, decl, life=None)
    assert body["dims"]["data_rights_holder"] == ["H1", "H2"]
    assert body["dims"]["nation"] == {"rollup": True, "release": ["ATL", "BDR"]}
    assert body["v"] == 2 and body["policy"] == decl.policy_id
    assert verify_lk2(key, body, declaration=decl)


def test_exports():
    names = """AUTHOR_EMPTY DECLARATION_NOT_LK2 FORM_IS_LK1 LIFE_MALFORMED LIFE_MEMBERS NO_POLICY
    POLICY_ID_NOT_URN_OID RELEASE_ABSENT ROLLUP_WITH_AUTHOR TIME_RE URN_OID_RE VALUE_RE NoKey canonical_lk2
    check_lk2_declaration check_policy_id compile_label compile_lk2 declaration_from_data verify_label
    verify_lk2""".split()
    for n in names:
        assert n in pkg.__all__, n
        assert getattr(pkg, n) is getattr(lk2, n), n
    # lk2's generator is exported under its own name; lk1's keeps the plain one
    assert "generate_lk2_vectors" in pkg.__all__
    assert pkg.generate_lk2_vectors is lk2.generate_vectors
    assert pkg.generate_vectors is lk1.generate_vectors
    assert len(pkg.__all__) == len(set(pkg.__all__))
    for n in pkg.__all__:
        assert hasattr(pkg, n), n


def test_lk1_unchanged():
    text = json.dumps(lk1.generate_vectors(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert LK1_VECTORS.read_bytes() == text.encode("utf-8")
    assert lk1.canonical_lk1("example:policy-1", "ATL", ["BDR"]) == "lk1|example:policy-1|nation|ATL|BDR"
    assert pkg.compile_lk1 is lk1.compile_lk1 and pkg.verify is lk1.verify
