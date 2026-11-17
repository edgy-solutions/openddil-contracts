"""Tests for openddil_identity.episode (ADR-0056 section 5a, #39, ruled
2026-11-16 with the canonical-JSON seed)."""

import json
import os
import pathlib
import sys
import time
import uuid

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib" / "python"))

import openddil_identity  # noqa: E402
from openddil_identity import episode as ep  # noqa: E402
from openddil_identity.episode import (  # noqa: E402
    EPISODE_NAMESPACE,
    episode_id,
    episode_seed,
    generate_episode_vectors,
)
from openddil_identity.ids import Identity, LookupKey, as_iri  # noqa: E402

VECTORS = pathlib.Path(ep.__file__).resolve().parent / "vectors" / "episode_id.json"
ID_A = Identity(uuid.UUID("01900000-0000-7000-8000-000000000001"))


def _load():
    return json.loads(VECTORS.read_text(encoding="utf-8"))


def test_regenerating_gives_committed_file_byte_for_byte():
    text = json.dumps(generate_episode_vectors(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert VECTORS.read_bytes() == text.encode("utf-8")
    assert b"\r" not in VECTORS.read_bytes()


def test_every_vector_recomputes():
    data = _load()
    assert len(data["vectors"]) >= 10
    for v in data["vectors"]:
        ident = Identity(uuid.UUID(v["identity"]))
        assert v["identity"] == str(ident.value)
        assert v["episode_id"] == v["episode_id"].lower()
        assert episode_seed(ident, v["component"], v["fault_code"]) == v["seed"]
        assert str(episode_id(ident, v["component"], v["fault_code"])) == v["episode_id"]


def test_namespace_literal_matches_file_and_is_v7():
    data = _load()
    assert str(EPISODE_NAMESPACE) == data["namespace"] == "01a1e284-45a5-7101-a8c8-9882e4b3e92d"
    assert EPISODE_NAMESPACE.version == 7
    assert EPISODE_NAMESPACE.variant == uuid.RFC_4122
    assert data["generator"] == ep.EPISODE_NAMESPACE_GENERATOR
    assert data["generator_version"] == ep.EPISODE_NAMESPACE_GENERATOR_VERSION
    assert data["minted_at"] == ep.EPISODE_NAMESPACE_MINTED_AT
    assert data["seed_form"] == ep.SEED_FORM
    assert data["canonical_json"] == ep.CANONICAL_JSON_FORM


def test_exports():
    assert openddil_identity.EPISODE_NAMESPACE is EPISODE_NAMESPACE
    assert openddil_identity.episode_id is episode_id
    assert openddil_identity.episode_seed is episode_seed


def test_version_5_and_deterministic():
    a = episode_id(ID_A, "pump", "F001")
    assert a.version == 5
    assert a.variant == uuid.RFC_4122
    assert a == episode_id(ID_A, "pump", "F001")


def test_seed_is_canonical_json_of_the_field_list():
    iri = as_iri(ID_A)
    assert iri == iri.lower()
    seed = episode_seed(ID_A, "pump", "F001")
    # Written out by hand, not through json.dumps: compact, no spaces.
    assert seed == '["episode","' + iri + '","pump","F001"]'
    assert json.loads(seed) == ["episode", iri, "pump", "F001"]
    assert seed.startswith('["episode","urn:uuid:')
    assert uuid.uuid5(EPISODE_NAMESPACE, seed) == episode_id(ID_A, "pump", "F001")


def test_canonical_json_escaping():
    # Only '"', backslash and control characters are escaped; '/' and
    # non-ASCII are written raw, as UTF-8. Short escapes where JSON has them,
    # otherwise lowercase \\u00xx.
    bs = chr(92)
    seed = episode_seed(ID_A, 'a"b' + bs + "c/d", "\n\t\x1fé")
    tail = seed.split('","')[2:]
    assert tail == [
        "a" + bs + '"b' + bs + bs + "c/d",
        bs + "n" + bs + "t" + bs + "u001fé\"]",
    ]
    assert json.loads(seed)[2:] == ['a"b' + bs + "c/d", "\n\t\x1fé"]


def test_distinct_inputs_distinct_ids():
    base = episode_id(ID_A, "pump", "F001")
    other = Identity(uuid.UUID("01900000-0000-7000-8000-000000000002"))
    assert episode_id(ID_A, "motor", "F001") != base
    assert episode_id(ID_A, "pump", "F002") != base
    assert episode_id(other, "pump", "F001") != base
    assert episode_id(ID_A, "Pump", "F001") != base
    assert episode_id(ID_A, " pump", "F001") != base


def test_no_normalisation():
    assert json.loads(episode_seed(ID_A, " Pump ", "f 1"))[2:] == [" Pump ", "f 1"]
    composed, decomposed = "é", "é"
    assert episode_id(ID_A, composed, "F") != episode_id(ID_A, decomposed, "F")


@pytest.mark.parametrize(
    "identity",
    [uuid.UUID("01900000-0000-7000-8000-000000000001"), str(ID_A.value), as_iri(ID_A), None,
     LookupKey(uuid.uuid5(uuid.NAMESPACE_URL, "x"))],
)
def test_identity_must_be_identity(identity):
    with pytest.raises(TypeError):
        episode_id(identity, "pump", "F001")
    with pytest.raises(TypeError):
        episode_seed(identity, "pump", "F001")


@pytest.mark.parametrize("bad", [None, 1, b"pump", ["pump"]])
def test_component_and_fault_must_be_str(bad):
    with pytest.raises(TypeError):
        episode_id(ID_A, bad, "F001")
    with pytest.raises(TypeError):
        episode_id(ID_A, "pump", bad)


def test_empty_values_are_accepted():
    iri = as_iri(ID_A)
    assert episode_seed(ID_A, "", "") == '["episode","' + iri + '","",""]'
    assert episode_seed(ID_A, "", "F001") == '["episode","' + iri + '","","F001"]'
    assert episode_seed(ID_A, "pump", "") == '["episode","' + iri + '","pump",""]'
    ids = {
        episode_id(ID_A, "", ""),
        episode_id(ID_A, "", "F001"),
        episode_id(ID_A, "pump", ""),
        episode_id(ID_A, "pump", "F001"),
    }
    assert len(ids) == 4
    assert all(i.version == 5 for i in ids)
    names = {v["name"] for v in _load()["vectors"]}
    assert {"empty_component", "empty_fault_code", "empty_both"} <= names


def test_pipe_pair_gives_different_ids():
    # ("a|b", "c") and ("a", "b|c") collided under the "|"-joined seed; the
    # canonical-JSON seed keeps each field's boundary.
    assert episode_seed(ID_A, "a|b", "c") != episode_seed(ID_A, "a", "b|c")
    assert episode_id(ID_A, "a|b", "c") != episode_id(ID_A, "a", "b|c")
    # The same pair under the era-1 joining would collide.
    assert "|".join(["a|b", "c"]) == "|".join(["a", "b|c"])
    by_name = {v["name"]: v for v in _load()["vectors"]}
    pair = [v for v in by_name.values() if "differs_from" in v]
    assert len(pair) == 2
    for v in pair:
        other = by_name[v["differs_from"]]
        assert other["differs_from"] == v["name"]
        assert other["seed"] != v["seed"]
        assert other["episode_id"] != v["episode_id"]


def test_field_boundaries_cannot_be_forged():
    # A value carrying JSON punctuation stays inside its field.
    forged = episode_id(ID_A, 'a","b', "c")
    assert forged != episode_id(ID_A, "a", 'b","c')
    assert json.loads(episode_seed(ID_A, 'a","b', "c"))[2:] == ['a","b', "c"]


@pytest.mark.parametrize("field", ["component", "fault_code"])
def test_lone_surrogate_refused(field):
    bad = "x\ud800"
    args = {"component": "pump", "fault_code": "F001"}
    args[field] = bad
    with pytest.raises(ValueError, match=field):
        episode_seed(ID_A, **args)
    with pytest.raises(ValueError, match=field):
        episode_id(ID_A, **args)


def test_era1_contrast_never_equal():
    contrast = _load()["era1_contrast"]
    assert len(contrast) == 2
    for c in contrast:
        era1 = uuid.uuid5(uuid.NAMESPACE_URL, "episode|" + c["asset_id"] + "|" + c["component"] + "|" + c["fault_code"])
        ident = Identity(uuid.UUID(c["identity"]))
        assert c["era1_id"] == str(era1)
        assert c["era2_id"] == str(episode_id(ident, c["component"], c["fault_code"]))
        assert c["era1_id"] != c["era2_id"]


def test_era2_never_equals_era1_for_same_inputs():
    era1 = uuid.uuid5(uuid.NAMESPACE_URL, "episode|" + as_iri(ID_A) + "|pump|F001")
    assert episode_id(ID_A, "pump", "F001") != era1


def test_no_clock_or_randomness(monkeypatch):
    expected = episode_id(ID_A, "pump", "F001")

    def boom(*a, **k):
        raise AssertionError("clock or randomness used")

    monkeypatch.setattr(time, "time_ns", boom)
    monkeypatch.setattr(os, "urandom", boom)
    assert episode_id(ID_A, "pump", "F001") == expected
