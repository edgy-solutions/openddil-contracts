"""Tests for openddil_labels.model and the package-wide no-default rule (ADR-0055 1a)."""

import dataclasses
import inspect
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib" / "python"))

import openddil_labels as L  # noqa: E402
from openddil_labels import Declaration, Dimension, normalise_name  # noqa: E402


def test_normalise_name_cases():
    assert normalise_name("Data Rights-Holder") == "data_rights_holder"
    assert normalise_name("  nation ") == "nation"
    assert normalise_name("a__b--c") == "a_b_c"
    assert normalise_name("_x_") == "x"
    for bad in ("9x", "", "__", "   ", None, 5):
        with pytest.raises(ValueError):
            normalise_name(bad)


def test_dimension_normalises_name_and_constructors():
    d = Dimension.restrictive("Data-Rights Holder", ["H", "K"], "owner-1")
    assert d.name == "data_rights_holder"
    assert d.type == L.RESTRICTIVE and d.vocabulary == ("H", "K")
    p = Dimension.permissive("nation", ["ATL", "BDR"], "owner-1", has_author=True)
    assert p.has_author and p.type == L.PERMISSIVE
    h = Dimension.hierarchical("level", ["low", "mid", "high"], "owner-1")
    assert h.vocabulary == ("low", "mid", "high") and h.type == L.HIERARCHICAL
    assert Dimension.exclusionary("x", ["H"], "o").type == L.EXCLUSIONARY


def test_dimension_refusals():
    with pytest.raises(ValueError):
        Dimension("a", "bogus", ("H",), "o", False)
    for owner in ("", "   "):
        with pytest.raises(ValueError):
            Dimension.restrictive("a", ["H"], owner)
    for vocab in ([], ["H", "H"], ["H", ""], ["H", 5]):
        with pytest.raises(ValueError):
            Dimension.restrictive("a", vocab, "o")
    with pytest.raises(ValueError):
        Dimension("a", L.RESTRICTIVE, ("H",), "o", True)
    with pytest.raises(ValueError):
        Dimension("9x", L.RESTRICTIVE, ("H",), "o", False)


def test_declaration():
    a = Dimension.restrictive("a", ["H"], "o")
    b = Dimension.exclusionary("b", ["K"], "o")
    decl = Declaration("example:policy-1", (a, b))
    assert decl.get("A") is a and decl.get("b") is b and decl.get("c") is None
    assert decl.get("9x") is None
    for bad in ("", "Example", ":x", "x" * 64, "a\n", "has space"):
        with pytest.raises(ValueError):
            Declaration(bad, (a,))
    with pytest.raises(ValueError):
        Declaration("example:policy-1", ())
    with pytest.raises(ValueError):
        Declaration("example:policy-1", (a, Dimension.restrictive("A", ["K"], "o")))


def test_no_implicit_label_no_defaults():
    def check(obj, label):
        for pname, p in inspect.signature(obj).parameters.items():
            assert p.default is inspect.Parameter.empty, "%s.%s has a default" % (label, pname)

    for name in L.__all__:
        obj = getattr(L, name)
        if inspect.isclass(obj):
            check(obj, name)
            for mname, m in inspect.getmembers(obj, callable):
                if not mname.startswith("_"):
                    check(m, name + "." + mname)
        elif callable(obj):
            check(obj, name)
    for cls in (Dimension, Declaration, L.Valid, L.Refused):
        for f in dataclasses.fields(cls):
            assert f.default is dataclasses.MISSING, f.name
            assert f.default_factory is dataclasses.MISSING, f.name
