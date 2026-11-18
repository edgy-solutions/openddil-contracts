"""Tests for openddil_kinds.closure: ADR-0061 Decision 3 (report mode) and Decision 4."""

import copy
import hashlib
import inspect
import json
import os
import pathlib
import random
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib" / "python"))

import openddil_kinds  # noqa: E402
from openddil_kinds import BOUNDED_FORMATS, FINDINGS, LOAD_REFUSALS, check_kind, generate_vectors  # noqa: E402
from openddil_kinds import closure as closure_mod  # noqa: E402

VECTORS = ROOT / "lib" / "python" / "openddil_kinds" / "vectors" / "closure.json"
VECTORS_SHA256 = "60f6683f612ba125f5fba4d2054c8ef8bd4a1c0d141ab47ba7f9b0ca20581717"
REPORT_KEYS = {"closure", "eligible_declared", "findings", "free_text", "clean", "qualifies_eligible", "load_refusals"}


def resolve(doc, pointer):
    """RFC 6901 resolver. Raises KeyError, IndexError or ValueError when it does not resolve."""
    if pointer == "":
        return doc
    assert pointer.startswith("/")
    cur = doc
    for tok in pointer[1:].split("/"):
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict):
            cur = cur[tok]
        elif isinstance(cur, list):
            cur = cur[int(tok)]
        else:
            raise ValueError(pointer)
    return cur


def by_name():
    return {v["name"]: v for v in generate_vectors()["vectors"]}


def test_vectors_report_equals_check():
    for v in generate_vectors()["vectors"]:
        assert v["report"] == check_kind(v["schema"]), v["name"]


def test_vectors_match_file_and_canonical_dump():
    on_disk = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert generate_vectors() == on_disk
    text = json.dumps(generate_vectors(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    raw = VECTORS.read_bytes()
    assert raw == text.encode("utf-8")
    assert b"\r" not in raw


def test_vectors_sha256_pinned():
    assert hashlib.sha256(VECTORS.read_bytes()).hexdigest() == VECTORS_SHA256


def test_vector_names_unique_and_cover_findings():
    vs = generate_vectors()["vectors"]
    names = [v["name"] for v in vs]
    assert len(names) == len(set(names))
    seen = {f["finding"] for v in vs for f in v["report"]["findings"]}
    assert seen == set(FINDINGS)
    seen_ref = {r for v in vs for r in v["report"]["load_refusals"]}
    assert seen_ref == set(LOAD_REFUSALS)


def test_pointers_resolve():
    for v in generate_vectors()["vectors"]:
        schema, report = v["schema"], v["report"]
        pointers = [f["pointer"] for f in report["findings"]] + report["free_text"]
        for p in pointers:
            if p == "":
                continue  # the root itself, including schema_malformed on a non-object root
            try:
                resolve(schema, p)
            except (KeyError, IndexError, ValueError):
                # a ref_unresolved pointer ends in /$ref, which exists; a missing keyword never does
                raise AssertionError((v["name"], p))


def test_output_shape():
    for v in generate_vectors()["vectors"]:
        r = v["report"]
        assert set(r.keys()) == REPORT_KEYS
        keys = [(f["pointer"], f["finding"]) for f in r["findings"]]
        assert keys == sorted(keys)
        assert len(keys) == len(set(keys))
        assert all(f["finding"] in FINDINGS and set(f) == {"finding", "pointer"} for f in r["findings"])
        assert r["free_text"] == sorted(set(r["free_text"]))
        order = [LOAD_REFUSALS.index(x) for x in r["load_refusals"]]
        assert order == sorted(set(order))
        assert r["clean"] == (not r["findings"])
        assert r["qualifies_eligible"] == (r["clean"] and not r["free_text"])
        json.dumps(r)


def test_constants():
    assert BOUNDED_FORMATS == frozenset({"date-time", "date", "uuid"})
    assert FINDINGS == (
        "object_open",
        "string_unbounded",
        "free_text_no_max_length",
        "array_no_max_items",
        "untyped",
        "ref_unresolved",
        "schema_malformed",
    )
    assert LOAD_REFUSALS == ("enforce_not_clean", "eligible_in_report", "eligible_not_clean", "eligible_free_text")


def findings_of(name):
    return [(f["finding"], f["pointer"]) for f in by_name()[name]["report"]["findings"]]


def test_spec_cases():
    assert findings_of("object_closed_minimal") == []
    assert findings_of("object_additional_schema") == [("object_open", ""), ("string_unbounded", "/additionalProperties")]
    assert findings_of("object_open_under_patternproperties") == [("object_open", "/patternProperties/^x-")]
    assert findings_of("object_or_null_open") == [("object_open", "")]
    assert findings_of("string_max_length_only_unbounded") == [("string_unbounded", "")]
    assert findings_of("string_free_text_declared_as_string_true") == [("string_unbounded", "")]
    assert findings_of("string_enum_without_type") == []
    assert findings_of("array_max_items_true_does_not_count") == [("array_no_max_items", "")]
    assert findings_of("array_tuple_form_items") == [("string_unbounded", "/items/1")]
    assert findings_of("node_empty_untyped") == [("untyped", "")]
    assert findings_of("node_true_under_properties") == [("untyped", "/properties/a")]
    assert findings_of("node_false_clean") == []
    assert findings_of("node_anyof_pattern_or_null_no_type") == []
    assert findings_of("ref_local_resolves") == [("string_unbounded", "/$defs/id")]
    assert findings_of("ref_escaped_slash_resolves") == []
    for n in ("ref_external", "ref_dangling", "ref_anchor", "ref_not_a_string"):
        assert findings_of(n) == [("ref_unresolved", "/properties/a/$ref")]
    assert findings_of("pointer_escapes_slash_and_tilde") == [
        ("object_open", "/properties/a~1b"),
        ("object_open", "/properties/c~0d"),
        ("object_open", "/properties/e~0~1f"),
    ]
    assert findings_of("type_list_three_findings_one_pointer") == [
        ("array_no_max_items", ""),
        ("object_open", ""),
        ("string_unbounded", ""),
    ]
    assert ("schema_malformed", "/type") in findings_of("type_integer_malformed")
    assert ("schema_malformed", "/type") in findings_of("type_list_with_non_string_malformed")
    for n in ("type_list_empty_malformed", "type_name_unknown_malformed", "type_list_unknown_name_malformed"):
        assert findings_of(n) == [("untyped", ""), ("schema_malformed", "/type")], n
    assert findings_of("enum_not_an_array_malformed") == [("string_unbounded", ""), ("schema_malformed", "/enum")]
    assert findings_of("properties_is_array_malformed") == [("schema_malformed", "/properties")]
    for n in ("root_is_array", "root_is_number", "root_is_string", "root_is_null"):
        assert findings_of(n) == [("schema_malformed", "")]
    assert ("string_unbounded", "") in findings_of("allof_sibling_bound_not_credited")


def test_free_text():
    r = by_name()["string_free_text_with_max_length"]["report"]
    assert r["clean"] and r["free_text"] == [""] and not r["qualifies_eligible"]
    assert findings_of("string_free_text_no_max_length") == [("free_text_no_max_length", "")]
    assert findings_of("string_free_text_and_pattern") == []
    r = by_name()["free_text_deep_nested"]["report"]
    assert r["free_text"] == ["/properties/a/items/properties/n"]


def test_declarations():
    v = by_name()
    assert v["declare_enforce_clean"]["report"]["closure"] == "enforce"
    assert v["declare_enforce_clean"]["report"]["load_refusals"] == []
    assert v["declare_enforce_with_findings"]["report"]["load_refusals"] == ["enforce_not_clean"]
    for n in ("declare_enforced_misspelt_is_report", "declare_closure_true_is_report"):
        assert v[n]["report"]["closure"] == "report"
    r = v["declare_eligible_enforce_clean"]["report"]
    assert r["eligible_declared"] and r["qualifies_eligible"] and r["load_refusals"] == []
    assert v["declare_eligible_in_report"]["report"]["load_refusals"] == ["eligible_in_report"]
    assert v["declare_eligible_enforce_free_text"]["report"]["load_refusals"] == ["eligible_free_text"]
    assert v["declare_eligible_report_free_text"]["report"]["load_refusals"] == [
        "eligible_in_report",
        "eligible_free_text",
    ]
    assert v["declare_eligible_enforce_not_clean"]["report"]["load_refusals"] == [
        "enforce_not_clean",
        "eligible_not_clean",
    ]
    for n in ("declare_eligible_capitalised_not_declared", "declare_eligible_true_not_declared", "declare_nested_ignored"):
        assert v[n]["report"]["eligible_declared"] is False
        assert v[n]["report"]["load_refusals"] == []
    assert v["declare_nested_ignored"]["report"]["closure"] == "report"


def test_realistic_kind():
    r = by_name()["realistic_example_outbound_event"]["report"]
    assert [(f["finding"], f["pointer"]) for f in r["findings"]] == [
        ("object_open", "/properties/extra"),
        ("array_no_max_items", "/properties/tags"),
    ]
    assert r["free_text"] == ["/properties/note"]


def test_input_unchanged():
    for v in generate_vectors()["vectors"]:
        before = copy.deepcopy(v["schema"])
        check_kind(v["schema"])
        assert v["schema"] == before


def _rand_value(rng, depth):
    kinds = ["str", "int", "float", "bool", "null"]
    if depth < 5:
        kinds += ["dict", "dict", "list"]
    k = rng.choice(kinds)
    if k == "str":
        return rng.choice(["string", "object", "array", "enforce", "eligible", "#", "#/a", "#/~", "^a$", "uuid", "x/y~"])
    if k == "int":
        return rng.choice([-1, 0, 1, 5, 10**30])
    if k == "float":
        return rng.choice([0.0, 1.5, -2.5])
    if k == "bool":
        return rng.random() < 0.5
    if k == "null":
        return None
    if k == "list":
        return [_rand_value(rng, depth + 1) for _ in range(rng.randint(0, 3))]
    keys = [
        "type", "properties", "patternProperties", "$defs", "definitions", "dependentSchemas", "allOf", "anyOf",
        "oneOf", "prefixItems", "items", "additionalProperties", "additionalItems", "contains",
        "unevaluatedProperties", "unevaluatedItems", "if", "then", "else", "not", "enum", "const", "$ref",
        "pattern", "format", "maxLength", "maxItems", "x-free-text", "x-closure", "x-cross-domain",
    ]
    d = {}
    for _ in range(rng.randint(0, 5)):
        key = rng.choice(keys) if rng.random() < 0.8 else "".join(rng.choice("ab/~ ") for _ in range(rng.randint(0, 4)))
        d[key] = _rand_value(rng, depth + 1)
    return d


def test_never_raises_on_garbage():
    rng = random.Random(0)
    for _ in range(2000):
        value = _rand_value(rng, 0)
        before = copy.deepcopy(value)
        r = check_kind(value)
        assert set(r.keys()) == REPORT_KEYS
        json.dumps(r)
        assert value == before


def _deep(kw, n):
    node = {}
    for _ in range(n):
        node = {"properties": {"a": node}} if kw == "properties" else {"items": node}
    return node


def test_never_raises_on_deep_nesting():
    for kw in ("properties", "items"):
        r = check_kind(_deep(kw, 10000))
        assert r["findings"][-1]["finding"] == "untyped" or any(f["finding"] == "untyped" for f in r["findings"])
        assert not r["clean"]


def test_no_defaults_on_public_functions():
    for mod in (openddil_kinds, closure_mod):
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            if name.startswith("_") or fn.__module__ != closure_mod.__name__:
                continue
            for p in inspect.signature(fn).parameters.values():
                assert p.default is inspect.Parameter.empty, (name, p.name)


def run_cli(*args):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "lib" / "python")
    return subprocess.run(
        [sys.executable, "-W", "ignore", "-m", "openddil_kinds.closure", *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(ROOT),
    )


def test_cli_report(tmp_path):
    f = tmp_path / "k.json"
    f.write_text(json.dumps({"type": "object"}), encoding="utf-8")
    p = run_cli("--report", str(f))
    assert p.returncode == 0
    lines = p.stdout.splitlines()
    assert len(lines) == 1
    name, _, body = lines[0].partition("\t")
    assert name == "k.json"
    assert json.loads(body) == check_kind({"type": "object"})
    assert body == json.dumps(check_kind({"type": "object"}), sort_keys=True)


def test_cli_unreadable(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text("{not json", encoding="utf-8")
    p = run_cli("--report", str(f))
    assert p.returncode == 2
    assert p.stdout.splitlines() == ["bad.json\tunreadable"]


def test_cli_bad_argv():
    assert run_cli().returncode == 2
    assert run_cli("--report").returncode == 2
    assert run_cli("--nope").returncode == 2
    assert run_cli("--write", "x").returncode == 2
