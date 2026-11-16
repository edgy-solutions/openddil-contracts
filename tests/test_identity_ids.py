"""Tests for openddil_identity.ids and declaration_ref (ADR-0056 checks 3, spec 1.3)."""

import hashlib
import pathlib
import sys
import uuid

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib" / "python"))

import openddil_identity  # noqa: E402
from openddil_identity import declaration as decl_mod  # noqa: E402
from openddil_identity import equivalence as eq_mod  # noqa: E402
from openddil_identity import era as era_mod  # noqa: E402
from openddil_identity import ids as ids_mod  # noqa: E402
from openddil_identity.declaration import declaration_ref  # noqa: E402
from openddil_identity.ids import (  # noqa: E402
    GENERATOR,
    GENERATOR_VERSION,
    Identity,
    LookupKey,
    _Minter,
    as_iri,
    lookup_key,
    mint_identity,
)

NS_A = uuid.UUID("11111111-1111-4111-8111-111111111111")
NS_B = uuid.UUID("22222222-2222-4222-8222-222222222222")


def fake_urandom(seed_bytes=b"\x00\x05"):
    calls = []

    def f(n):
        calls.append(n)
        if n == 2:
            return seed_bytes
        return bytes([0xFF] * n)

    f.calls = calls
    return f


def test_uuidv7_form():
    ids = [mint_identity() for _ in range(10_000)]
    for i in ids:
        assert i.value.version == 7
        assert i.value.variant == uuid.RFC_4122
    ints = [i.value.int for i in ids]
    assert len(set(ints)) == len(ints)
    assert all(a < b for a, b in zip(ints, ints[1:]))
    strs = [str(i.value) for i in ids]
    assert all(a < b for a, b in zip(strs, strs[1:]))


def test_uuidv7_top_48_bits_are_clock_ms():
    clock = [1_700_000_000_123]
    m = _Minter(lambda: clock[0], fake_urandom())
    first = m.mint()
    clock[0] += 5
    second = m.mint()
    assert first.value.int >> 80 == 1_700_000_000_123
    assert second.value.int >> 80 == 1_700_000_000_128
    assert (first.value.int >> 76) & 0xF == 7
    assert (first.value.int >> 62) & 0x3 == 0b10


def test_counter_frozen_clock_still_increases():
    m = _Minter(lambda: 1_700_000_000_000, fake_urandom())
    ids = [m.mint().value.int for _ in range(5_000)]
    assert all(a < b for a, b in zip(ids, ids[1:]))
    # 5,000 > 4,096 so the overflow advanced the logical ms.
    assert ids[-1] >> 80 > 1_700_000_000_000


def test_counter_clock_steps_back_still_increases():
    clock = [1_700_000_000_100]
    m = _Minter(lambda: clock[0], fake_urandom())
    a = m.mint()
    clock[0] -= 50
    b = m.mint()
    clock[0] -= 50
    c = m.mint()
    assert a.value.int < b.value.int < c.value.int
    assert b.value.int >> 80 == 1_700_000_000_100


def test_counter_new_ms_reseeds_with_top_bit_clear():
    clock = [1_700_000_000_000]
    # 0xFFFF & 0x7FF = 0x7FF: the top bit of the 12-bit counter stays clear.
    m = _Minter(lambda: clock[0], fake_urandom(b"\xff\xff"))
    a = m.mint()
    assert (a.value.int >> 64) & 0xFFF == 0x7FF
    clock[0] += 1
    m2 = _Minter(lambda: clock[0], fake_urandom(b"\x00\x2a"))
    b = m2.mint()
    assert (b.value.int >> 64) & 0xFFF == 0x2A
    # Same ms: counter plus one; new ms: re-seeded.
    c = m2.mint()
    assert (c.value.int >> 64) & 0xFFF == 0x2B
    clock[0] += 1
    d = m2.mint()
    assert (d.value.int >> 64) & 0xFFF == 0x2A


def test_generator():
    assert GENERATOR == mint_identity.__module__ + "." + mint_identity.__qualname__
    assert isinstance(GENERATOR_VERSION, str) and GENERATOR_VERSION


def test_check3_never_the_identity():
    ids = {mint_identity().value for _ in range(1_000)}
    keys = set()
    for n in range(500):
        keys.add(lookup_key(NS_A, f"SN-{n:04d}").value)
        keys.add(lookup_key(NS_B, f"SN-{n:04d}").value)
    assert len(ids) == 1_000 and len(keys) == 1_000
    assert not ids & keys

    with pytest.raises(ValueError):
        Identity(uuid.uuid5(NS_A, "SN-0001"))
    with pytest.raises(ValueError):
        LookupKey(mint_identity().value)
    with pytest.raises(TypeError):
        Identity("not a uuid")
    with pytest.raises(TypeError):
        as_iri(lookup_key(NS_A, "SN-0001"))
    assert as_iri(mint_identity()).startswith("urn:uuid:")

    assert lookup_key(NS_A, "SN-1") != lookup_key(NS_A, " SN-1")
    assert lookup_key(NS_A, "SN-1") != lookup_key(NS_A, "sn-1")
    with pytest.raises(TypeError):
        lookup_key("ns", "SN-1")
    with pytest.raises(TypeError):
        lookup_key(NS_A, 1)

    for mod in (openddil_identity, ids_mod, decl_mod, era_mod, eq_mod):
        for name in dir(mod):
            if name.startswith("_"):
                continue
            assert "timestamp" not in name.lower()
            assert "time_of" not in name.lower()


def test_declaration_ref():
    a = {"asset_id": "asset-001", "serial": "SN-0001"}
    b = {"serial": "SN-0001", "asset_id": "asset-001"}
    assert declaration_ref(a) == declaration_ref(b)
    assert declaration_ref(a) != declaration_ref({"asset_id": "asset-001", "serial": "SN-0002"})
    assert declaration_ref(a) == hashlib.sha256(
        b'{"asset_id":"asset-001","serial":"SN-0001"}'
    ).hexdigest()
    non_ascii = {"asset_id": "asset-001", "serial": "SN-é"}
    assert declaration_ref(non_ascii) == hashlib.sha256(
        '{"asset_id":"asset-001","serial":"SN-é"}'.encode("utf-8")
    ).hexdigest()
