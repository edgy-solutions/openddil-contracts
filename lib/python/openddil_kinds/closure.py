"""The kind closure check: ADR-0061 Decision 3 (report mode) and Decision 4.

Implements the load check of ADR-0061 Decision 3 as a pure library: given a
kind's JSON Schema, name every open object, every unbounded string not
declared free text, every array with no maxItems, and say whether the kind
qualifies as cross-domain eligible (Decision 4): SPEC-kinds-closure.md,
closure.py.

Report mode never refuses. load_refusals only names what a load would refuse.

Nothing calls this module yet.
"""

import copy
import json
import os
import pathlib
import sys

BOUNDED_FORMATS = frozenset({"date-time", "date", "uuid"})

FINDINGS = (
    "object_open",
    "string_unbounded",
    "free_text_no_max_length",
    "array_no_max_items",
    "untyped",
    "ref_unresolved",
    "schema_malformed",
)

LOAD_REFUSALS = (
    "enforce_not_clean",
    "eligible_in_report",
    "eligible_not_clean",
    "eligible_free_text",
)

_MAP_KEYWORDS = ("properties", "patternProperties", "$defs", "definitions", "dependentSchemas")
_ARRAY_KEYWORDS = ("allOf", "anyOf", "oneOf", "prefixItems")
_SINGLE_KEYWORDS = ("additionalItems", "contains", "if", "then", "else")
_OBJECT_ONLY_KEYWORDS = ("additionalProperties", "unevaluatedProperties", "unevaluatedItems")


def _esc(name):
    return name.replace("~", "~0").replace("/", "~1")


def _is_count(v):
    return type(v) is int and v >= 0


def _ref_resolves(root, ref):
    if not isinstance(ref, str) or not ref.startswith("#"):
        return False
    ptr = ref[1:]
    if ptr == "":
        return True
    if not ptr.startswith("/"):
        return False
    cur = root
    for tok in ptr[1:].split("/"):
        tok = tok.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict):
            if tok not in cur:
                return False
            cur = cur[tok]
        elif isinstance(cur, list):
            if not tok.isascii() or not tok.isdigit() or (len(tok) > 1 and tok[0] == "0"):
                return False
            i = int(tok)
            if i >= len(cur):
                return False
            cur = cur[i]
        else:
            return False
    return True


_TYPE_NAMES = frozenset({"array", "boolean", "integer", "null", "number", "object", "string"})


def _types(node, ptr, findings):
    """Return the set of types, or None when there is no usable type.

    A type name outside the seven JSON Schema names, and an empty type list, are schema_malformed: neither may be read
    as "no finding", so the node is treated as having no type (and is untyped unless something else constrains it).
    """
    if "type" not in node:
        return None
    t = node["type"]
    if isinstance(t, str):
        t = [t]
    if isinstance(t, list) and t and all(isinstance(x, str) and x in _TYPE_NAMES for x in t):
        return set(t)
    findings.add(("schema_malformed", ptr + "/type"))
    return None


def check_kind(schema):
    """Report on one parsed JSON schema. Never raises, never mutates."""
    findings = set()
    free_text = set()

    closure = "report"
    eligible_declared = False
    if isinstance(schema, dict):
        v = schema.get("x-closure")
        if isinstance(v, str) and v == "enforce":
            closure = "enforce"
        v = schema.get("x-cross-domain")
        eligible_declared = isinstance(v, str) and v == "eligible"

    stack = [(schema, "")]
    while stack:
        node, ptr = stack.pop()
        if node is False:
            continue
        if node is True:
            findings.add(("untyped", ptr))
            continue
        if not isinstance(node, dict):
            findings.add(("schema_malformed", ptr))
            continue

        # enum must be an array to make the value set finite; any other enum is malformed and exempts nothing.
        if "enum" in node and not isinstance(node["enum"], list):
            findings.add(("schema_malformed", ptr + "/enum"))
        finite = isinstance(node.get("enum"), list) or "const" in node
        types = _types(node, ptr, findings)

        if node.get("x-free-text") is True:
            free_text.add(ptr)

        if "$ref" in node and not _ref_resolves(schema, node["$ref"]):
            findings.add(("ref_unresolved", ptr + "/$ref"))

        if not finite:
            if types is None and not any(k in node for k in ("$ref", "allOf", "anyOf", "oneOf")):
                findings.add(("untyped", ptr))
            if types is not None:
                if "object" in types and node.get("additionalProperties") is not False:
                    findings.add(("object_open", ptr))
                if "array" in types and not _is_count(node.get("maxItems")):
                    findings.add(("array_no_max_items", ptr))
                if "string" in types:
                    fmt = node.get("format")
                    bounded = isinstance(node.get("pattern"), str) or (
                        isinstance(fmt, str) and fmt in BOUNDED_FORMATS
                    )
                    free = node.get("x-free-text") is True
                    if not bounded and not free:
                        findings.add(("string_unbounded", ptr))
                    if free and not _is_count(node.get("maxLength")):
                        findings.add(("free_text_no_max_length", ptr))

        for kw in _MAP_KEYWORDS:
            if kw in node:
                v = node[kw]
                if isinstance(v, dict):
                    for name, sub in v.items():
                        stack.append((sub, ptr + "/" + kw + "/" + _esc(name)))
                else:
                    findings.add(("schema_malformed", ptr + "/" + kw))
        for kw in _ARRAY_KEYWORDS:
            if kw in node:
                v = node[kw]
                if isinstance(v, list):
                    for i, sub in enumerate(v):
                        stack.append((sub, ptr + "/" + kw + "/" + str(i)))
                else:
                    findings.add(("schema_malformed", ptr + "/" + kw))
        if "items" in node:
            v = node["items"]
            if isinstance(v, list):
                for i, sub in enumerate(v):
                    stack.append((sub, ptr + "/items/" + str(i)))
            elif isinstance(v, (dict, bool)):
                stack.append((v, ptr + "/items"))
            else:
                findings.add(("schema_malformed", ptr + "/items"))
        for kw in _SINGLE_KEYWORDS:
            if kw in node:
                stack.append((node[kw], ptr + "/" + kw))
        for kw in _OBJECT_ONLY_KEYWORDS:
            if kw in node:
                v = node[kw]
                if isinstance(v, dict):
                    stack.append((v, ptr + "/" + kw))
                elif not isinstance(v, bool):
                    findings.add(("schema_malformed", ptr + "/" + kw))

    out_findings = [{"finding": f, "pointer": p} for p, f in sorted((p, f) for f, p in findings)]
    out_free = sorted(free_text)
    clean = not out_findings
    refusals = set()
    if closure == "enforce" and not clean:
        refusals.add("enforce_not_clean")
    if eligible_declared:
        if closure == "report":
            refusals.add("eligible_in_report")
        if not clean:
            refusals.add("eligible_not_clean")
        if out_free:
            refusals.add("eligible_free_text")
    return {
        "closure": closure,
        "eligible_declared": eligible_declared,
        "findings": out_findings,
        "free_text": out_free,
        "clean": clean,
        "qualifies_eligible": clean and not out_free,
        "load_refusals": [r for r in LOAD_REFUSALS if r in refusals],
    }


def _vector_cases():
    S = {"type": "string"}
    PAT = {"type": "string", "pattern": "^[A-Z]{3}$"}
    CLOSED = {"type": "object", "additionalProperties": False}
    OPEN = {"type": "object"}
    clean_root = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"id": {"type": "string", "format": "uuid"}},
    }
    note = {"type": "string", "x-free-text": True, "maxLength": 200}

    def obj(props, **extra):
        d = {"type": "object", "additionalProperties": False, "properties": props}
        d.update(extra)
        return d

    cases = [
        # Objects
        ("object_closed_minimal", CLOSED),
        ("object_additional_absent", OPEN),
        ("object_additional_true", {"type": "object", "additionalProperties": True}),
        ("object_additional_schema", {"type": "object", "additionalProperties": {"type": "string"}}),
        ("object_additional_open_object_schema", {"type": "object", "additionalProperties": {"type": "object"}}),
        ("object_open_under_properties", obj({"a": OPEN})),
        ("object_open_under_items", {"type": "array", "maxItems": 3, "items": OPEN}),
        ("object_open_under_defs", {"$defs": {"x": OPEN}, "type": "object", "additionalProperties": False}),
        ("object_open_under_anyof", {"anyOf": [OPEN, {"type": "null"}]}),
        ("object_open_under_allof", {"allOf": [OPEN]}),
        ("object_open_under_oneof", {"oneOf": [OPEN, {"type": "null"}]}),
        ("object_open_under_prefixitems", {"type": "array", "maxItems": 1, "prefixItems": [OPEN]}),
        (
            "object_open_under_patternproperties",
            {"type": "object", "additionalProperties": False, "patternProperties": {"^x-": OPEN}},
        ),
        (
            "object_closed_with_patternproperties_still_closed",
            {"type": "object", "additionalProperties": False, "patternProperties": {"^x-": {"type": "null"}}},
        ),
        ("object_or_null_open", {"type": ["object", "null"]}),
        # Strings
        ("string_bounded_by_enum", {"type": "string", "enum": ["a", "b"]}),
        ("string_bounded_by_const", {"type": "string", "const": "a"}),
        ("string_bounded_by_pattern", PAT),
        ("string_bounded_by_format_date_time", {"type": "string", "format": "date-time"}),
        ("string_bounded_by_format_date", {"type": "string", "format": "date"}),
        ("string_bounded_by_format_uuid", {"type": "string", "format": "uuid"}),
        ("string_format_email_unbounded", {"type": "string", "format": "email"}),
        ("string_max_length_only_unbounded", {"type": "string", "maxLength": 10}),
        ("string_free_text_with_max_length", note),
        ("string_free_text_no_max_length", {"type": "string", "x-free-text": True}),
        ("string_free_text_max_length_bool", {"type": "string", "x-free-text": True, "maxLength": True}),
        (
            "string_free_text_and_pattern",
            {"type": "string", "x-free-text": True, "pattern": "^a", "maxLength": 5},
        ),
        (
            "string_free_text_declared_as_string_true",
            {"type": "string", "x-free-text": "true", "maxLength": 5},
        ),
        ("string_or_null_unbounded", {"type": ["string", "null"]}),
        ("string_enum_without_type", {"enum": ["a", "b"]}),
        ("string_format_not_a_string", {"type": "string", "format": ["uuid"]}),
        # Arrays
        ("array_with_max_items", {"type": "array", "maxItems": 4, "items": PAT}),
        ("array_without_max_items", {"type": "array", "items": PAT}),
        ("array_max_items_zero", {"type": "array", "maxItems": 0}),
        ("array_max_items_true_does_not_count", {"type": "array", "maxItems": True, "items": PAT}),
        ("array_items_open_object", {"type": "array", "maxItems": 2, "items": OPEN}),
        ("array_tuple_form_items", {"type": "array", "maxItems": 2, "items": [PAT, S]}),
        # Nodes and references
        ("node_empty_untyped", {}),
        ("node_true_under_properties", obj({"a": True})),
        ("node_false_clean", False),
        ("node_false_under_properties", obj({"a": False})),
        ("node_anyof_pattern_or_null_no_type", {"anyOf": [PAT, {"type": "null"}]}),
        ("ref_local_resolves", obj({"a": {"$ref": "#/$defs/id"}}, **{"$defs": {"id": S}})),
        ("ref_root", obj({"self": {"$ref": "#"}})),
        ("ref_escaped_slash_resolves", obj({"a": {"$ref": "#/$defs/a~1b"}}, **{"$defs": {"a/b": PAT}})),
        ("ref_external", obj({"a": {"$ref": "https://example.test/x.json"}})),
        ("ref_dangling", obj({"a": {"$ref": "#/$defs/missing"}})),
        (
            "ref_anchor",
            obj({"a": {"$ref": "#thing"}}, **{"$defs": {"t": {"$anchor": "thing", "type": "null"}}}),
        ),
        ("ref_not_a_string", obj({"a": {"$ref": 5}})),
        # Pointers and malformed schemas
        ("pointer_escapes_slash_and_tilde", obj({"a/b": OPEN, "c~d": OPEN, "e~/f": OPEN})),
        ("type_list_three_findings_one_pointer", {"type": ["object", "string", "array"]}),
        ("type_integer_malformed", {"type": 5}),
        ("type_list_with_non_string_malformed", {"type": ["string", 5]}),
        ("type_list_empty_malformed", {"type": []}),
        ("type_name_unknown_malformed", {"type": "strin"}),
        ("type_list_unknown_name_malformed", {"type": ["string", "text"]}),
        ("enum_not_an_array_malformed", {"type": "string", "enum": "a"}),
        ("properties_is_array_malformed", obj([])),
        ("allof_is_object_malformed", {"type": "object", "additionalProperties": False, "allOf": {}}),
        ("root_is_array", []),
        ("root_is_number", 7),
        ("root_is_string", "x"),
        ("root_is_null", None),
        ("member_is_number_malformed", obj({"a": 3})),
        ("allof_sibling_bound_not_credited", {"type": "string", "allOf": [{"pattern": "^a$"}]}),
        # Declarations
        ("declare_enforce_clean", dict(clean_root, **{"x-closure": "enforce"})),
        ("declare_enforce_with_findings", {"type": "object", "x-closure": "enforce"}),
        ("declare_enforced_misspelt_is_report", dict(clean_root, **{"x-closure": "enforced"})),
        ("declare_closure_true_is_report", dict(clean_root, **{"x-closure": True})),
        (
            "declare_eligible_enforce_clean",
            dict(clean_root, **{"x-closure": "enforce", "x-cross-domain": "eligible"}),
        ),
        ("declare_eligible_in_report", dict(clean_root, **{"x-cross-domain": "eligible"})),
        (
            "declare_eligible_enforce_free_text",
            obj({"n": note}, **{"x-closure": "enforce", "x-cross-domain": "eligible"}),
        ),
        ("declare_eligible_report_free_text", obj({"n": note}, **{"x-cross-domain": "eligible"})),
        (
            "declare_eligible_enforce_not_clean",
            {"type": "object", "x-closure": "enforce", "x-cross-domain": "eligible"},
        ),
        (
            "declare_eligible_capitalised_not_declared",
            dict(clean_root, **{"x-closure": "enforce", "x-cross-domain": "Eligible"}),
        ),
        ("declare_eligible_true_not_declared", dict(clean_root, **{"x-cross-domain": True})),
        (
            "declare_nested_ignored",
            obj({"a": dict(CLOSED, **{"x-closure": "enforce", "x-cross-domain": "eligible"})}),
        ),
        ("free_text_deep_nested", obj({"a": {"type": "array", "maxItems": 2, "items": obj({"n": note})}})),
    ]

    cases.append(
        (
            "realistic_example_outbound_event",
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": "ExampleOutboundEvent",
                "type": "object",
                "additionalProperties": False,
                "x-closure": "report",
                "required": ["event_id", "subject_id", "observed_at", "status"],
                "properties": {
                    "event_id": {"type": "string", "format": "uuid"},
                    "subject_id": {"type": "string", "format": "uuid"},
                    "observed_at": {"type": "string", "format": "date-time"},
                    "expires_on": {"type": "string", "format": "date"},
                    "status": {"type": "string", "enum": ["new", "updated", "closed"]},
                    "schema_version": {"type": "string", "const": "1"},
                    "region_code": {"type": "string", "pattern": "^[A-Z]{3}$"},
                    "count": {"type": "integer", "minimum": 0},
                    "label": obj(
                        {
                            "policy": {"type": "string", "pattern": "^[a-z0-9:._-]{1,63}$"},
                            "release": {"type": "array", "maxItems": 8, "items": PAT},
                        }
                    ),
                    "parts": {
                        "type": "array",
                        "maxItems": 16,
                        "items": obj(
                            {
                                "part_id": {"type": "string", "format": "uuid"},
                                "kind": {"type": "string", "enum": ["a", "b"]},
                            }
                        ),
                    },
                    "extra": {"type": "object", "properties": {"k": {"type": "string", "enum": ["x"]}}},
                    "tags": {"type": "array", "items": {"type": "string", "enum": ["t1", "t2"]}},
                    "note": {"type": "string", "x-free-text": True, "maxLength": 280},
                },
            },
        )
    )
    return cases


def generate_vectors():
    """Golden vectors for the closure check."""
    return {
        "bounded_formats": sorted(BOUNDED_FORMATS),
        "findings": list(FINDINGS),
        "load_refusals": list(LOAD_REFUSALS),
        "vectors": [
            {"name": name, "schema": schema, "report": check_kind(copy.deepcopy(schema))}
            for name, schema in _vector_cases()
        ],
    }


def _vectors_path():
    return pathlib.Path(__file__).resolve().parent / "vectors" / "closure.json"


def _write_vectors():
    path = _vectors_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(generate_vectors(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _report(paths):
    status = 0
    for p in paths:
        base = os.path.basename(p)
        try:
            with open(p, "r", encoding="utf-8") as f:
                schema = json.load(f)
            line = json.dumps(check_kind(schema), sort_keys=True)
        except (OSError, ValueError, RecursionError):
            line = "unreadable"
            status = 2
        sys.stdout.write(base + "\t" + line + "\n")
    return status


_USAGE = "usage: python -m openddil_kinds.closure --write | --report FILE...\n"

if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        _write_vectors()
    elif len(sys.argv) >= 3 and sys.argv[1] == "--report":
        sys.exit(_report(sys.argv[2:]))
    else:
        sys.stderr.write(_USAGE)
        sys.exit(2)
