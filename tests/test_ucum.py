"""test_ucum.py - the one UCUM->pint dialect table.

Tests:
  - the module imports nothing (it is pure data, loadable anywhere)
  - it holds exactly the five known entries
  - pint_unit passes an unknown code through unchanged

pint validity of each value is checked in the service tests, which have pint.
"""
import ast
import importlib.util
import pathlib

UCUM_PATH = (pathlib.Path(__file__).parent.parent
             / "proto" / "openddil" / "common" / "v1" / "ucum.py")


def _load():
    spec = importlib.util.spec_from_file_location("ucum_under_test", UCUM_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_module_imports_nothing():
    tree = ast.parse(UCUM_PATH.read_text(encoding="utf-8"))
    imports = [n for n in ast.walk(tree)
               if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert imports == []


def test_exactly_the_five_entries():
    assert _load().UCUM_TO_PINT == {
        "[degF]": "degF",
        "[kn_i]": "knot",
        "gal_us": "gallon",
        "1": "dimensionless",
        "Cel": "degC",
    }


def test_pint_unit_passes_unknown_through():
    mod = _load()
    assert mod.pint_unit("Cel") == "degC"
    assert mod.pint_unit("kPa") == "kPa"
