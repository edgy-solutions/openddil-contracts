"""Tests for openddil_identity.episode (PROPOSED ADR-0056 section 5a, #39)."""

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


def test_exports():
    assert openddil_identity.EPISODE_NAMESPACE is EPISODE_NAMESPACE
    assert openddil_identity.episode_id is episode_id
    assert openddil_identity.episode_seed is episode_seed


def test_version_5_and_deterministic():
    a = episode_id(ID_A, "pump", "F001")
    assert a.version == 5
    assert a.variant == uuid.RFC_4122
    assert a == episode_id(ID_A, "pump", "F001")


def test_seed_form_and_lowercase():
    seed = episode_seed(ID_A, "pump", "F001")
    assert seed == "episode|" + as_iri(ID_A) + "|pump|F001"
    assert seed.startswith("episode|urn:uuid:")
    iri = as_iri(ID_A)
    assert iri == iri.lower()


def test_distinct_inputs_distinct_ids():
    base = episode_id(ID_A, "pump", "F001")
    other = Identity(uuid.UUID("01900000-0000-7000-8000-000000000002"))
    assert episode_id(ID_A, "motor", "F001") != base
    assert episode_id(ID_A, "pump", "F002") != base
    assert episode_id(other, "pump", "F001") != base
    assert episode_id(ID_A, "Pump", "F001") != base
    assert episode_id(ID_A, " pump", "F001") != base


def test_no_normalisation():
    assert episode_seed(ID_A, " Pump ", "f 1") == "episode|" + as_iri(ID_A) + "| Pump |f 1"
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


def test_empty_strings_are_accepted_current_behaviour():
    assert episode_seed(ID_A, "", "") == "episode|" + as_iri(ID_A) + "||"
    assert episode_id(ID_A, "pump", "").version == 5


def test_pipe_collision_is_current_behaviour():
    assert episode_seed(ID_A, "a|b", "c") == episode_seed(ID_A, "a", "b|c")
    assert episode_id(ID_A, "a|b", "c") == episode_id(ID_A, "a", "b|c")
    by_name = {v["name"]: v for v in _load()["vectors"]}
    pair = [v for v in by_name.values() if "collides_with" in v]
    assert len(pair) == 2
    for v in pair:
        assert by_name[v["collides_with"]]["collides_with"] == v["name"]
        assert by_name[v["collides_with"]]["episode_id"] == v["episode_id"]


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
