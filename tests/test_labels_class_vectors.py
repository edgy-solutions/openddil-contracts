"""Golden vectors for the class row (rollup marker) form.

Status: Builds on the ADR-0055 §2a rollup marker, accepted 2026-11-16.
"""

import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib" / "python"))

from openddil_labels import Refused, admits_class, class_label, split_by_audience  # noqa: E402
from openddil_labels import rollup_vectors  # noqa: E402

PATH = pathlib.Path(rollup_vectors.__file__).resolve().parent / "vectors" / "class_label.json"
RAW = PATH.read_bytes()
V = json.loads(RAW.decode("utf-8"))
DECL = rollup_vectors.load_declaration(V["declaration"])


def test_vectors_file_is_byte_equal_to_regenerated():
    assert RAW == rollup_vectors.vectors_text().encode("utf-8")
    assert b"\r" not in RAW and RAW.endswith(b"\n")


def test_required_cases_present():
    assert {c["name"] for c in V["class_label"]} >= {
        "single_author_with_release",
        "single_author_no_release",
        "author_already_in_release",
        "null_label",
    }
    assert {c["name"] for c in V["split"]} >= {
        "rollup_over_one_author",
        "two_authors_two_classes",
        "mixed_with_withheld",
    }


@pytest.mark.parametrize("case", V["class_label"], ids=lambda c: c["name"])
def test_class_label_vectors(case):
    r = class_label(case["label"], DECL)
    if case["refused"] is None:
        assert r == case["class_label"]
        assert "author" not in r["nation"]
    else:
        assert case["class_label"] is None
        assert isinstance(r, Refused) and r.reason == case["refused"]


def test_class_label_refusal_reasons():
    by = {c["name"]: c for c in V["class_label"]}
    assert by["null_label"]["refused"] == "no_label"
    assert by["invalid_label_out_of_vocabulary"]["refused"] == "value_out_of_vocabulary"
    assert by["single_author_no_release"]["class_label"]["nation"] == {"rollup": True, "release": ["ATL"]}


@pytest.mark.parametrize("case", V["admits_class"], ids=lambda c: c["name"])
def test_admits_class_vectors(case):
    assert admits_class(case["viewer"], case["class_label"], DECL) is case["admitted"]


def test_admits_class_expected_values():
    by = {c["name"]: c["admitted"] for c in V["admits_class"]}
    assert by["rollup_viewer_holds_release_value"] is True
    assert by["rollup_viewer_holds_none"] is False
    assert by["rollup_empty_release_viewer_all"] is False
    assert by["old_form_author_none"] is False
    assert by["empty_author_set_without_marker"] is False
    assert by["marker_with_author"] is False
    assert by["rollup_is_integer_one"] is False and by["rollup_is_string_true"] is False
    assert by["rollup_no_release"] is False
    assert by["restrictive_dimension_unmet"] is False
    assert by["restrictive_dimension_met"] is True


@pytest.mark.parametrize("case", V["split"], ids=lambda c: c["name"])
def test_split_vectors(case):
    s = split_by_audience([(c["id"], c["label"]) for c in case["contributors"]], DECL)
    assert [{"label": c.label, "members": list(c.members)} for c in s.classes] == case["classes"]
    assert s.withheld == case["withheld"]
    assert [list(p) for p in s.withheld_by_reason] == case["withheld_by_reason"]


def test_rollup_over_one_author_is_marker_not_authors_label():
    case = next(c for c in V["split"] if c["name"] == "rollup_over_one_author")
    assert len(case["classes"]) == 1
    label = case["classes"][0]["label"]["nation"]
    assert label == {"rollup": True, "release": ["ATL"]}
    for c in case["contributors"]:
        assert case["classes"][0]["label"] != c["label"]
    assert case["classes"][0]["members"] == ["c1", "c2", "c3"]
