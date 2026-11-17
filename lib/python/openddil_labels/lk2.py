"""The lk2 label key: canonical form, key, body, verification, golden vectors.

Implements ADR-0055 section 2a (more than one author, a rollup marker, or more
than one dimension: the lk2 canonical form and key) and section 2b (the
urn:oid: policy id, and the life member that rides in the body outside the
key): SPEC-labels-lk2.md.

The key compiler checks format only, never vocabulary. The key is a function of
the policy id and the body alone, so verify_lk2 and the stack's SQL function
need no vocabulary. Admission (admission.validate) stays the vocabulary check.

No parameter has a default (ADR-0055 section 1a): where there is no life or no
declaration, the caller passes None explicitly. Absence is passed, never defaulted.

Nothing calls this module yet.
"""

import datetime
import hashlib
import json
import pathlib
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass

from .admission import DIMENSION_MISSING, DIMENSION_UNDECLARED, VALUE_MALFORMED
from .lk1 import NATION_RE, POLICY_RE, canonical_lk1, compile_lk1
from .lk1 import verify as verify_lk1
from .model import HIERARCHICAL, Declaration, Dimension

URN_OID_RE = r"urn:oid:[0-2](\.(0|[1-9][0-9]*))+"
VALUE_RE = r"[A-Za-z0-9][A-Za-z0-9._:-]{0,62}"
TIME_RE = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z"
LIFE_MEMBERS = ("CreationDateTime", "ReviewDateTime")

NO_POLICY = "no_policy"
POLICY_ID_NOT_URN_OID = "policy_id_not_urn_oid"
DECLARATION_NOT_LK2 = "declaration_not_lk2"
AUTHOR_EMPTY = "author_empty"
ROLLUP_WITH_AUTHOR = "rollup_with_author"
RELEASE_ABSENT = "release_absent"
LIFE_MALFORMED = "life_malformed"
FORM_IS_LK1 = "form_is_lk1"
LK1_LIFE_UNDECIDED = "lk1_life_undecided"

_COLLECTIONS = (list, tuple, set, frozenset)

_NATION, _HIER, _SET = "nation", "hierarchical", "set"


@dataclass(frozen=True)
class NoKey:
    reason: str
    dimension: str | None


# ---------------------------------------------------------------- declarations


def _policy_id_ok(policy_id):
    return (
        isinstance(policy_id, str)
        and re.fullmatch(URN_OID_RE, policy_id) is not None
        and re.fullmatch(POLICY_RE, policy_id) is not None
    )


def check_policy_id(policy_id):
    """Return None, or raise ValueError naming the id, unless it is a valid urn:oid: id."""
    if not _policy_id_ok(policy_id):
        raise ValueError("policy_id is not a urn:oid: id: %r" % (policy_id,))


def _declaration_problem(declaration):
    """The first problem as (reason, message), or None."""
    if not isinstance(declaration, Declaration):
        return DECLARATION_NOT_LK2, "not a Declaration: %r" % (declaration,)
    if not _policy_id_ok(declaration.policy_id):
        return POLICY_ID_NOT_URN_OID, "policy_id is not a urn:oid: id: %r" % (declaration.policy_id,)
    authors = [d for d in declaration.dimensions if d.has_author]
    if len(authors) != 1 or authors[0].name != "nation":
        return DECLARATION_NOT_LK2, "exactly one dimension must have an author, and it must be nation"
    for d in declaration.dimensions:
        pattern = NATION_RE if d.name == "nation" else VALUE_RE
        for v in d.vocabulary:
            if re.fullmatch(pattern, v) is None:
                return DECLARATION_NOT_LK2, "vocabulary value %r of %s fails its format" % (v, d.name)
    return None


def check_lk2_declaration(declaration):
    """Raise ValueError naming the problem unless the declaration can be keyed as lk2."""
    problem = _declaration_problem(declaration)
    if problem is not None:
        raise ValueError(problem[1])


def _spec_from_declaration(declaration):
    spec = []
    for d in declaration.dimensions:
        if d.name == "nation":
            spec.append((d.name, _NATION))
        elif d.type == HIERARCHICAL:
            spec.append((d.name, _HIER))
        else:
            spec.append((d.name, _SET))
    return spec


# ---------------------------------------------------------------- parsing


def _distinct_nations(v):
    """Sorted distinct list, or None when v is not a collection of NATION_RE strings."""
    if not isinstance(v, _COLLECTIONS):
        return None
    for x in v:
        if not isinstance(x, str) or re.fullmatch(NATION_RE, x) is None:
            return None
    return sorted(set(v))


def _parse_nation(v):
    """Return ("author", authors, release) / ("rollup", None, release), or a NoKey."""
    bad = NoKey(VALUE_MALFORMED, "nation")
    if not isinstance(v, Mapping):
        return bad
    keys = set(v.keys())
    if not keys <= {"author", "rollup", "release"}:
        return bad
    if "rollup" in keys:
        if "author" in keys:
            return NoKey(ROLLUP_WITH_AUTHOR, "nation")
        if v["rollup"] is not True:
            return bad
        rel = v.get("release")
        if rel is None:
            return NoKey(RELEASE_ABSENT, "nation")
        release = _distinct_nations(rel)
        if release is None:
            return bad
        return "rollup", None, release
    if keys != {"author", "release"}:
        return bad
    a = v["author"]
    if a is None or a == "" or (isinstance(a, _COLLECTIONS) and len(a) == 0):
        return NoKey(AUTHOR_EMPTY, "nation")
    if isinstance(a, str):
        a = [a]
    authors = _distinct_nations(a)
    if authors is None:
        return bad
    rel = v["release"]
    if rel is None:
        release = None
    else:
        release = _distinct_nations(rel)
        if release is None:
            return bad
    if len(authors) >= 2 and release is None:
        return NoKey(RELEASE_ABSENT, "nation")
    return "author", authors, release


def _time_ok(t):
    if not isinstance(t, str) or re.fullmatch(TIME_RE, t) is None:
        return False
    try:
        datetime.datetime(int(t[0:4]), int(t[5:7]), int(t[8:10]), int(t[11:13]), int(t[14:16]), int(t[17:19]))
    except ValueError:
        return False
    return True


def _life_ok(life):
    if not isinstance(life, Mapping) or set(life.keys()) != set(LIFE_MEMBERS):
        return False
    if not _time_ok(life["CreationDateTime"]):
        return False
    review = life["ReviewDateTime"]
    return review is None or _time_ok(review)


# ---------------------------------------------------------------- the shared core


def _check_keys(dims, spec):
    """NoKey for a non-mapping, an undeclared key, or a missing dimension; else None."""
    if not isinstance(dims, Mapping):
        return NoKey(VALUE_MALFORMED, None)
    names = {n for n, _ in spec}
    for k in dims:
        if not isinstance(k, str):
            return NoKey(DIMENSION_UNDECLARED, None)
        if k not in names:
            return NoKey(DIMENSION_UNDECLARED, k)
    for n in ["nation"] + sorted(n for n in names if n != "nation"):
        if dims.get(n) is None:
            return NoKey(DIMENSION_MISSING, n)
    return None


def _core(policy_id, spec, dims, life):
    """Return (canonical, body) for an lk2-form label, or a NoKey."""
    if "nation" not in dict(spec):
        return NoKey(DECLARATION_NOT_LK2, None)
    err = _check_keys(dims, spec)
    if err is not None:
        return err
    parsed = _parse_nation(dims["nation"])
    if isinstance(parsed, NoKey):
        return parsed
    form, authors, release = parsed
    kinds = dict(spec)
    others = sorted(n for n in kinds if n != "nation")
    body_dims = {}
    parts = []
    for n in others:
        v = dims[n]
        if kinds[n] == _HIER:
            if not isinstance(v, str) or re.fullmatch(VALUE_RE, v) is None:
                return NoKey(VALUE_MALFORMED, n)
            body_dims[n] = v
            parts.extend([n, v])
        else:
            if not isinstance(v, _COLLECTIONS):
                return NoKey(VALUE_MALFORMED, n)
            for x in v:
                if not isinstance(x, str) or re.fullmatch(VALUE_RE, x) is None:
                    return NoKey(VALUE_MALFORMED, n)
            vals = sorted(set(v))
            body_dims[n] = vals
            parts.extend([n, ",".join(vals)])
    if life is not None and not _life_ok(life):
        return NoKey(LIFE_MALFORMED, None)
    if form == "author":
        if len(spec) == 1 and len(authors) == 1:
            return NoKey(FORM_IS_LK1, "nation")
        nation_body = {"author": authors, "release": release}
        author_text = ",".join(authors)
    else:
        nation_body = {"rollup": True, "release": release}
        author_text = "@rollup"
    release_text = "~" if release is None else ",".join(release)
    body_dims["nation"] = nation_body
    canonical = "|".join(["lk2", policy_id, "nation", author_text, release_text] + parts)
    body = {"policy": policy_id, "v": 2, "dims": body_dims}
    if life is not None:
        body["life"] = {m: life[m] for m in LIFE_MEMBERS}
    return canonical, body


def _key_of(canonical):
    return "lk2:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _compile_core(dims, declaration, life):
    if declaration is None:
        return NoKey(NO_POLICY, None)
    problem = _declaration_problem(declaration)
    if problem is not None:
        return NoKey(problem[0], None)
    return _core(declaration.policy_id, _spec_from_declaration(declaration), dims, life)


# ---------------------------------------------------------------- public functions


def canonical_lk2(dims, declaration, *, life):
    """The canonical string for an lk2-form label, or a NoKey. Never raises."""
    try:
        res = _compile_core(dims, declaration, life)
        return res if isinstance(res, NoKey) else res[0]
    except Exception:
        return NoKey(VALUE_MALFORMED, None)


def compile_lk2(dims, declaration, *, life):
    """(label_key, body) for an lk2-form label, or a NoKey. Never raises."""
    try:
        res = _compile_core(dims, declaration, life)
        if isinstance(res, NoKey):
            return res
        return _key_of(res[0]), res[1]
    except Exception:
        return NoKey(VALUE_MALFORMED, None)


def _lk1_candidate(declaration):
    ds = declaration.dimensions
    return len(ds) == 1 and ds[0].name == "nation" and ds[0].has_author


def compile_label(dims, declaration, *, life):
    """The one stamp entry point: lk1 for a one-author nation-only label, else lk2. Never raises."""
    try:
        if declaration is None:
            return NoKey(NO_POLICY, None)
        if isinstance(declaration, Declaration) and _lk1_candidate(declaration):
            spec = _spec_from_declaration(declaration)
            err = _check_keys(dims, spec)
            if err is not None:
                return err
            parsed = _parse_nation(dims["nation"])
            if isinstance(parsed, NoKey):
                return parsed
            form, authors, release = parsed
            if form == "author" and len(authors) == 1:
                if life is not None:
                    return NoKey(LK1_LIFE_UNDECIDED, None)
                return compile_lk1(declaration.policy_id, authors[0], release)
        return compile_lk2(dims, declaration, life=life)
    except Exception:
        return NoKey(VALUE_MALFORMED, None)


def verify_lk2(label_key, body, *, declaration):
    """True only when body is the canonical lk2 body for label_key. Never raises."""
    try:
        if not isinstance(body, dict) or set(body.keys()) not in (
            {"policy", "v", "dims"},
            {"policy", "v", "dims", "life"},
        ):
            return False
        if type(body["v"]) is not int or body["v"] != 2:
            return False
        if not _policy_id_ok(body["policy"]):
            return False
        dims = body["dims"]
        if not isinstance(dims, dict) or "nation" not in dims:
            return False
        spec = []
        for k, v in dims.items():
            if not isinstance(k, str):
                return False
            if k == "nation":
                spec.append((k, _NATION))
            elif isinstance(v, str):
                spec.append((k, _HIER))
            elif isinstance(v, list):
                spec.append((k, _SET))
            else:
                return False
        res = _core(body["policy"], spec, dims, body.get("life"))
        if isinstance(res, NoKey):
            return False
        if (_key_of(res[0]), res[1]) != (label_key, body):
            return False
        if declaration is not None:
            if compile_lk2(dims, declaration, life=body.get("life")) != (label_key, body):
                return False
        return True
    except Exception:
        return False


def verify_label(label_key, body, *, declaration):
    """Dispatch on the key prefix. Never raises."""
    try:
        if not isinstance(label_key, str):
            return False
        if label_key.startswith("lk1:"):
            return verify_lk1(label_key, body)
        if label_key.startswith("lk2:"):
            return verify_lk2(label_key, body, declaration=declaration)
        return False
    except Exception:
        return False


def declaration_from_data(data):
    """Build a Declaration from {"policy_id", "dimensions": [{name, type, vocabulary, owner, has_author}]}."""
    makers = {
        "permissive": lambda d: Dimension.permissive(
            d["name"], d["vocabulary"], d["owner"], has_author=d["has_author"]
        ),
        "restrictive": lambda d: Dimension.restrictive(d["name"], d["vocabulary"], d["owner"]),
        "exclusionary": lambda d: Dimension.exclusionary(d["name"], d["vocabulary"], d["owner"]),
        "hierarchical": lambda d: Dimension.hierarchical(d["name"], d["vocabulary"], d["owner"]),
    }
    dims = tuple(makers[d["type"]](d) for d in data["dimensions"])
    return Declaration(data["policy_id"], dims)


# ---------------------------------------------------------------- golden vectors

_FORM_TEXT = (
    "lk2|<policy_id>|nation|<authors>|<release>[|<name>|<values>]... ; nation first, then the other "
    "dimensions by name in byte order; <authors> is the sorted distinct authors joined by ',' or the "
    "literal @rollup; <release> is ~ when absent, empty when declared empty, else sorted distinct joined "
    "by ','; a set dimension is sorted distinct joined by ',' (empty when declared empty); a hierarchical "
    "dimension is its one level; key = 'lk2:' + sha256(canonical as UTF-8) in lower-case hex; life is in "
    "the body only, never in the canonical string or the key."
)


def _nation_decl():
    return {
        "name": "nation",
        "type": "permissive",
        "vocabulary": ["ATL", "BDR", "CRD"],
        "owner": "nation-steward",
        "has_author": True,
    }


def _rights_decl():
    return {
        "name": "data_rights_holder",
        "type": "restrictive",
        "vocabulary": ["H1", "H2"],
        "owner": "rights-steward",
        "has_author": False,
    }


def _level_decl():
    return {
        "name": "classification",
        "type": "hierarchical",
        "vocabulary": ["L1", "L2", "L3"],
        "owner": "level-steward",
        "has_author": False,
    }


def _declarations():
    return {
        "nation_only": {"policy_id": "urn:oid:1.3.6.1.4.1.32473.1", "dimensions": [_nation_decl()]},
        "nation_rights": {
            "policy_id": "urn:oid:1.3.6.1.4.1.32473.2",
            "dimensions": [_nation_decl(), _rights_decl()],
        },
        "nation_rights_level": {
            "policy_id": "urn:oid:1.3.6.1.4.1.32473.3",
            "dimensions": [_nation_decl(), _rights_decl(), _level_decl()],
        },
        "legacy_nation_only": {"policy_id": "example:policy-1", "dimensions": [_nation_decl()]},
    }


def _n(author, release):
    return {"author": author, "release": release}


def _r(release):
    return {"rollup": True, "release": release}


_LIFE_A = {"CreationDateTime": "2026-11-16T09:30:00Z", "ReviewDateTime": None}
_LIFE_B = {"CreationDateTime": "2026-11-16T10:45:12.250Z", "ReviewDateTime": "2027-11-16T10:45:12.250Z"}


def _vector_cases():
    """(name, declaration name or None, dims, life, extras) in file order."""
    nr = "nation_rights"
    no = "nation_only"
    comp = {"nation": _n(["BDR", "ATL"], ["CRD"])}

    def rights(nation, holders):
        return {"nation": nation, "data_rights_holder": holders}

    atl_bdr = _n("ATL", ["BDR"])
    life = lambda **kw: dict(_LIFE_A, **kw)  # noqa: E731
    return [
        ("composite_release", no, comp, None, {}),
        ("composite_release_empty", no, {"nation": _n(["ATL", "BDR"], [])}, None, {}),
        ("composite_release_absent", no, {"nation": _n(["ATL", "BDR"], None)}, None, {}),
        (
            "composite_duplicate_authors",
            no,
            {"nation": _n(["ATL", "BDR", "ATL"], ["CRD"])},
            None,
            {"same_key_as": "composite_release"},
        ),
        ("rollup_release", no, {"nation": _r(["BDR", "ATL"])}, None, {}),
        ("rollup_release_empty", no, {"nation": _r([])}, None, {}),
        ("rollup_release_absent", no, {"nation": _r(None)}, None, {}),
        ("rollup_not_true", no, {"nation": {"rollup": 1, "release": ["ATL"]}}, None, {}),
        (
            "rollup_over_one_author",
            no,
            {"nation": _r(["ATL", "BDR"])},
            None,
            {"not_key_of": ["single_author_atl_bdr", "single_author_atl_atl_bdr"]},
        ),
        ("single_author_atl_bdr", no, {"nation": atl_bdr}, None, {}),
        ("single_author_atl_atl_bdr", no, {"nation": _n("ATL", ["ATL", "BDR"])}, None, {}),
        (
            "single_author_as_list",
            no,
            {"nation": _n(["ATL"], ["BDR"])},
            None,
            {"same_key_as": "single_author_atl_bdr"},
        ),
        ("lk1_keeps_key_legacy_policy", "legacy_nation_only", {"nation": atl_bdr}, None, {}),
        (
            "legacy_policy_composite",
            "legacy_nation_only",
            {"nation": _n(["ATL", "BDR"], ["CRD"])},
            None,
            {},
        ),
        ("author_empty_no_marker", no, {"nation": _n([], ["BDR"])}, None, {}),
        ("author_null_no_marker", no, {"nation": _n(None, ["BDR"])}, None, {}),
        (
            "marker_with_author",
            no,
            {"nation": {"rollup": True, "author": ["ATL"], "release": ["BDR"]}},
            None,
            {},
        ),
        (
            "marker_with_empty_author",
            no,
            {"nation": {"rollup": True, "author": [], "release": ["BDR"]}},
            None,
            {},
        ),
        ("second_dim_empty", nr, rights(atl_bdr, []), None, {}),
        ("second_dim_values", nr, rights(atl_bdr, ["H2", "H1"]), None, {}),
        ("second_dim_missing", nr, {"nation": atl_bdr}, None, {}),
        ("second_dim_null", nr, rights(atl_bdr, None), None, {}),
        ("dimension_undeclared", no, {"nation": _n(["ATL", "BDR"], ["CRD"]), "caveat": ["X"]}, None, {}),
        (
            "hierarchical_level",
            "nation_rights_level",
            {
                "nation": _n(["ATL", "BDR"], ["CRD"]),
                "data_rights_holder": ["H1"],
                "classification": "L2",
            },
            None,
            {},
        ),
        (
            "hierarchical_as_list",
            "nation_rights_level",
            {
                "nation": _n(["ATL", "BDR"], ["CRD"]),
                "data_rights_holder": ["H1"],
                "classification": ["L2"],
            },
            None,
            {},
        ),
        (
            "rollup_with_two_dims",
            "nation_rights_level",
            {"nation": _r(["ATL"]), "data_rights_holder": ["H1"], "classification": "L1"},
            None,
            {},
        ),
        ("separator_pipe", nr, rights(atl_bdr, ["H|1"]), None, {}),
        ("separator_comma", nr, rights(atl_bdr, ["H,1"]), None, {}),
        ("separator_tilde", nr, rights(atl_bdr, ["H~1"]), None, {}),
        ("separator_at", nr, rights(atl_bdr, ["@rollup"]), None, {}),
        ("value_empty_string", nr, rights(atl_bdr, [""]), None, {}),
        ("value_too_long", nr, rights(atl_bdr, ["H" + "1" * 63]), None, {}),
        ("value_space", nr, rights(atl_bdr, ["H 1"]), None, {}),
        ("nation_author_malformed", no, {"nation": _n(["ATL", "AT|"], ["CRD"])}, None, {}),
        ("life_a", no, comp, _LIFE_A, {"same_key_as": "composite_release"}),
        ("life_b", no, comp, _LIFE_B, {"same_key_as": "life_a"}),
        ("life_extra_member", no, comp, life(Extra="x"), {}),
        ("life_missing_review", no, comp, {"CreationDateTime": "2026-11-16T09:30:00Z"}, {}),
        ("life_bad_time", no, comp, life(CreationDateTime="yesterday"), {}),
        ("life_offset", no, comp, life(CreationDateTime="2026-11-16T09:30:00+00:00"), {}),
        ("life_lowercase_z", no, comp, life(CreationDateTime="2026-11-16T09:30:00z"), {}),
        ("life_feb_30", no, comp, life(CreationDateTime="2026-02-30T09:30:00Z"), {}),
        ("life_on_lk1_form", no, {"nation": atl_bdr}, _LIFE_A, {}),
        ("no_policy", None, comp, None, {}),
    ]


_POLICY_ID_CASES = [
    "urn:oid:1.3.6.1.4.1.32473.1",
    "urn:oid:1.3.26.1.3.1",
    "urn:isbn:0451450523",
    "example:policy-1",
    "URN:OID:1.2",
    "urn:oid:1.03",
    "urn:oid:3.1",
    "urn:oid:1",
    "urn:oid:1." + "1" * 60,
    None,
    1,
]


def generate_vectors():
    """Golden vectors for lk2, as one dict."""
    decl_data = _declarations()
    decls = {name: declaration_from_data(d) for name, d in decl_data.items()}
    vectors = []
    for name, dname, dims, life, extras in _vector_cases():
        decl = None if dname is None else decls[dname]
        res = compile_label(dims, decl, life=life)
        v = {
            "name": name,
            "declaration": dname,
            "dims": dims,
            "life": life,
            "form": None,
            "canonical": None,
            "label_key": None,
            "label": None,
            "no_key": None,
            "no_key_dimension": None,
        }
        if isinstance(res, NoKey):
            v["no_key"] = res.reason
            v["no_key_dimension"] = res.dimension
        else:
            key, body = res
            v["label_key"] = key
            v["label"] = body
            if key.startswith("lk1:"):
                nation = body["dims"]["nation"]
                v["form"] = "lk1"
                v["canonical"] = canonical_lk1(body["policy"], nation["author"], nation["release"])
            else:
                v["form"] = "lk2"
                v["canonical"] = canonical_lk2(dims, decl, life=life)
        v.update(extras)
        vectors.append(v)
    policy_ids = []
    for pid in _POLICY_ID_CASES:
        try:
            check_policy_id(pid)
            ok = True
        except ValueError:
            ok = False
        policy_ids.append({"policy_id": pid, "accepted": ok})
    return {
        "form": _FORM_TEXT,
        "declarations": decl_data,
        "vectors": vectors,
        "policy_ids": policy_ids,
    }


def _vectors_path():
    return pathlib.Path(__file__).resolve().parent / "vectors" / "lk2.json"


def _write_vectors():
    path = _vectors_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(generate_vectors(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        _write_vectors()
    else:
        sys.stderr.write("usage: python -m openddil_labels.lk2 --write\n")
        sys.exit(2)
