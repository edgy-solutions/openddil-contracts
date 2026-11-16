"""Tests for openddil_identity.era and .equivalence (ADR-0056 checks 5 and 6)."""

import pathlib
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib" / "python"))

import openddil_identity  # noqa: E402
from openddil_identity import equivalence as eq_mod  # noqa: E402
from openddil_identity.equivalence import (  # noqa: E402
    ALREADY_MERGED,
    OWNER_MISSING,
    REASON_MISSING,
    SURVIVOR_IS_MERGED,
    Ok,
    Refused,
    check_equivalence,
)
from openddil_identity.era import era  # noqa: E402
from openddil_identity.ids import lookup_key, mint_identity  # noqa: E402

T = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_check6_era():
    assert era(T - timedelta(seconds=1), T) == 2
    assert era(T, T) == 2
    assert era(T + timedelta(seconds=1), T) == 1
    assert era(None, T) == 1


def test_check6_era_type_errors():
    with pytest.raises(TypeError):
        era(datetime(2026, 1, 1), T)
    with pytest.raises(TypeError):
        era(T, datetime(2026, 1, 1))
    with pytest.raises(TypeError):
        era("2026-01-01T00:00:00Z", T)
    with pytest.raises(TypeError):
        era(T, "2026-01-01T00:00:00Z")
    with pytest.raises(TypeError):
        era(mint_identity(), T)
    with pytest.raises(TypeError):
        era(T, mint_identity())


def test_check5_pure_refusals():
    a, b = mint_identity(), mint_identity()
    assert check_equivalence(a, b, "", "reason-1", False) == Refused(OWNER_MISSING)
    assert check_equivalence(a, b, "  \t", "reason-1", False) == Refused(OWNER_MISSING)
    assert check_equivalence(a, b, None, "reason-1", False) == Refused(OWNER_MISSING)
    assert check_equivalence(a, b, "owner-a", "", False) == Refused(REASON_MISSING)
    assert check_equivalence(a, b, "owner-a", "   ", False) == Refused(REASON_MISSING)
    assert check_equivalence(a, a, "owner-a", "reason-1", False) == Refused(SURVIVOR_IS_MERGED)
    assert check_equivalence(a, b, "owner-a", "reason-1", True) == Refused(ALREADY_MERGED)
    assert check_equivalence(a, b, "owner-a", "reason-1", False) == Ok()


def test_check5_order_of_checks():
    a = mint_identity()
    assert check_equivalence(a, a, "", "", True) == Refused(OWNER_MISSING)
    assert check_equivalence(a, a, "owner-a", "", True) == Refused(REASON_MISSING)
    assert check_equivalence(a, a, "owner-a", "reason-1", True) == Refused(SURVIVOR_IS_MERGED)


def test_check5_type_errors():
    ns = uuid.UUID("11111111-1111-4111-8111-111111111111")
    key = lookup_key(ns, "SN-0001")
    with pytest.raises(TypeError):
        check_equivalence(key, mint_identity(), "owner-a", "reason-1", False)
    with pytest.raises(TypeError):
        check_equivalence(mint_identity(), key, "owner-a", "reason-1", False)


def test_check5_nothing_proposes_or_scores():
    for mod in (openddil_identity, eq_mod):
        for name in dir(mod):
            if name.startswith("_"):
                continue
            low = name.lower()
            for word in ("similar", "suggest", "propose", "score"):
                assert word not in low
