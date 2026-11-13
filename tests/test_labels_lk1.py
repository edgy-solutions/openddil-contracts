"""Tests for openddil_labels.lk1, named after the ADR-0055 Checks."""

import copy
import hashlib
import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib" / "python"))

from openddil_labels import canonical_lk1, compile_lk1, generate_vectors, verify  # noqa: E402

P1, P2 = "example:policy-1", "example:policy-2"
VECTORS = pathlib.Path(__file__).resolve().parents[1] / "lib" / "python" / "openddil_labels" / "vectors" / "lk1.json"


def key(policy, orig, rel):
    r = compile_lk1(policy, orig, rel)
    return None if r is None else r[0]


def test_check3_key_determinism():
    assert key(P1, "ATL", []) != key(P1, "ATL", None)
    assert key(P1, "ATL", ["BDR", "ATL"]) == key(P1, "ATL", ["ATL", "BDR", "ATL"])
    assert key(P1, "ATL", ["BDR", "CRD"]) == key(P1, "ATL", ["CRD", "BDR"])
    assert key(P1, None, None) is None
    assert key(P1, None, []) is None
    assert key(P1, "ATL", None) != key(P2, "ATL", None)
    assert canonical_lk1(P1, "ATL", []) == "lk1|example:policy-1|nation|ATL|"
    assert canonical_lk1(P1, "ATL", None) == "lk1|example:policy-1|nation|ATL|~"


def test_check3_pinned_key():
    expected = "lk1:" + hashlib.sha256(b"lk1|example:policy-1|nation|ATL|BDR").hexdigest()
    assert compile_lk1(P1, "ATL", ["BDR"])[0] == expected


def test_no_key_cases():
    assert canonical_lk1(None, "ATL", ["BDR"]) is None
    assert canonical_lk1("", "ATL", ["BDR"]) is None
    assert canonical_lk1(P1, "", ["BDR"]) is None
    assert canonical_lk1(P1, "atl", None) is None
    assert canonical_lk1(P1, "ATLX", None) is None
    assert canonical_lk1(P1, "ATL\n", None) is None
    assert canonical_lk1(P1, "ATL", [None]) is None
    assert canonical_lk1(P1, "ATL", ["bdr"]) is None
    assert canonical_lk1(P1, "ATL", [""]) is None
    assert canonical_lk1(P1, "ATL", ["BDR\n"]) is None
    assert compile_lk1(P1, None, None) is None
    for bad in ("Example", "x\n", ":x", "x" * 64):
        with pytest.raises(ValueError):
            canonical_lk1(bad, "ATL", None)


def test_body_shape():
    key_, body = compile_lk1(P1, "ATL", ["CRD", "BDR", "CRD"])
    assert body == {"policy": P1, "v": 1, "dims": {"nation": {"author": "ATL", "release": ["BDR", "CRD"]}}}
    assert compile_lk1(P1, "ATL", None)[1]["dims"]["nation"]["release"] is None


def test_check11_verify():
    for v in generate_vectors():
        if v["label_key"] is not None:
            assert verify(v["label_key"], v["label"]) is True
    k, body = compile_lk1(P1, "ATL", ["BDR", "CRD"])
    flipped = k[:-1] + ("0" if k[-1] != "0" else "1")
    assert not verify(flipped, body)
    assert not verify(k, None)
    assert not verify(None, body)
    reordered = copy.deepcopy(body)
    reordered["dims"]["nation"]["release"] = ["CRD", "BDR"]
    assert not verify(k, reordered)
    duplicated = copy.deepcopy(body)
    duplicated["dims"]["nation"]["release"] = ["BDR", "BDR", "CRD"]
    assert not verify(k, duplicated)
    extra = copy.deepcopy(body)
    extra["x"] = 1
    assert not verify(k, extra)
    extra_dim = copy.deepcopy(body)
    extra_dim["dims"]["level"] = "low"
    assert not verify(k, extra_dim)
    for v in (2, True, "1", 1.0):
        bad = copy.deepcopy(body)
        bad["v"] = v
        assert not verify(k, bad)
    for bad in ([], "x", 5, None):
        assert not verify(k, bad)
    wrong_policy = copy.deepcopy(body)
    wrong_policy["policy"] = P2
    assert not verify(k, wrong_policy)
    garbage = copy.deepcopy(body)
    garbage["dims"]["nation"]["release"] = [None]
    assert not verify(k, garbage)


def test_vectors_pinned():
    on_disk = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert on_disk == generate_vectors()
    for v in on_disk:
        if v["canonical"] is None:
            assert v["label_key"] is None and v["label"] is None
        else:
            assert v["label_key"] == "lk1:" + hashlib.sha256(v["canonical"].encode("utf-8")).hexdigest()
    assert len({v["name"] for v in on_disk}) == len(on_disk)
    assert len(on_disk) >= 18


def test_vectors_file_is_canonical_text():
    raw = VECTORS.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")
    text = json.dumps(generate_vectors(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert raw == text.encode("utf-8")
