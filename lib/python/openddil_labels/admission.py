"""Label validation, admission and high-water.

Implements ADR-0055 section 1 (the four-type table, conjunction, undeclared
fails closed), section 1a (no default anywhere), section 2 (no originator is
unlabelled), section 3b (high-water of the inputs) and ADR-0029's effective
audience: SPEC-labels.md, admission.py.

Nothing calls this module yet.
"""

from collections.abc import Mapping
from dataclasses import dataclass

from .model import (
    EXCLUSIONARY,
    HIERARCHICAL,
    PERMISSIVE,
    RESTRICTIVE,
    normalise_name,
)

DIMENSION_UNDECLARED = "dimension_undeclared"
DIMENSION_MISSING = "dimension_missing"
VALUE_OUT_OF_VOCABULARY = "value_out_of_vocabulary"
HIERARCHICAL_EMPTY = "hierarchical_empty"
VALUE_MALFORMED = "value_malformed"
DIMENSION_AMBIGUOUS = "dimension_ambiguous"

_COLLECTIONS = (list, tuple, set, frozenset)


@dataclass(frozen=True)
class Valid:
    label: dict


@dataclass(frozen=True)
class Refused:
    reason: str
    dimension: "str | None"
    value: "str | None"


def _is_str_collection(v):
    return isinstance(v, _COLLECTIONS) and all(isinstance(x, str) for x in v)


def _sorted_distinct(v):
    return sorted(set(v))


def _first_outside(values, vocab):
    for x in sorted(set(values)):
        if x not in vocab:
            return x
    return None


def validate(label, declaration):
    """Return Valid (normalised label) or Refused (first failure). Never raises."""
    try:
        return _validate(label, declaration)
    except Exception:
        return Refused(VALUE_MALFORMED, None, None)


def _validate(label, declaration):
    if not isinstance(label, Mapping):
        return Refused(VALUE_MALFORMED, None, None)
    str_keys = sorted(k for k in label if isinstance(k, str))
    other_keys = [k for k in label if not isinstance(k, str)]
    by_name = {}
    for k in str_keys + other_keys:
        if not isinstance(k, str):
            return Refused(DIMENSION_UNDECLARED, None, None)
        try:
            n = normalise_name(k)
        except ValueError:
            return Refused(DIMENSION_UNDECLARED, k, None)
        if n in by_name:
            return Refused(DIMENSION_AMBIGUOUS, n, None)
        if declaration.get(n) is None:
            return Refused(DIMENSION_UNDECLARED, n, None)
        by_name[n] = k
    out = {}
    for dim in declaration.dimensions:
        if dim.name not in by_name:
            return Refused(DIMENSION_MISSING, dim.name, None)
        v = label[by_name[dim.name]]
        vocab = dim.vocabulary
        if dim.type == HIERARCHICAL:
            if v is None or v == "":
                return Refused(HIERARCHICAL_EMPTY, dim.name, None)
            if not isinstance(v, str):
                return Refused(VALUE_MALFORMED, dim.name, None)
            if v not in vocab:
                return Refused(VALUE_OUT_OF_VOCABULARY, dim.name, v)
            out[dim.name] = v
        elif dim.type == PERMISSIVE and dim.has_author:
            if not isinstance(v, Mapping) or set(v.keys()) != {"author", "release"}:
                return Refused(VALUE_MALFORMED, dim.name, None)
            author = v["author"]
            release = v["release"]
            if author is None or author == "":
                return Refused(DIMENSION_MISSING, dim.name, None)
            if not isinstance(author, str):
                return Refused(VALUE_MALFORMED, dim.name, None)
            if author not in vocab:
                return Refused(VALUE_OUT_OF_VOCABULARY, dim.name, author)
            if release is not None:
                if not _is_str_collection(release):
                    return Refused(VALUE_MALFORMED, dim.name, None)
                bad = _first_outside(release, vocab)
                if bad is not None:
                    return Refused(VALUE_OUT_OF_VOCABULARY, dim.name, bad)
                release = _sorted_distinct(release)
            out[dim.name] = {"author": author, "release": release}
        else:
            if v is None:
                return Refused(DIMENSION_MISSING, dim.name, None)
            if not _is_str_collection(v):
                return Refused(VALUE_MALFORMED, dim.name, None)
            bad = _first_outside(v, vocab)
            if bad is not None:
                return Refused(VALUE_OUT_OF_VOCABULARY, dim.name, bad)
            out[dim.name] = _sorted_distinct(v)
    return Valid(out)


def _viewer_entries(viewer, declaration):
    """Map declared name -> raw viewer entry; None when the viewer is malformed."""
    if not isinstance(viewer, Mapping):
        return None
    held = {}
    for k, v in viewer.items():
        if not isinstance(k, str):
            return None
        try:
            n = normalise_name(k)
        except ValueError:
            continue
        if n in held:
            return None
        held[n] = v
    return held


def admits(viewer, label, declaration, *, single_authorship):
    """True when every declared dimension admits the viewer. Never raises."""
    try:
        return _admits(viewer, label, declaration, single_authorship)
    except Exception:
        return False


def _admits(viewer, label, declaration, single_authorship):
    res = validate(label, declaration)
    if isinstance(res, Refused):
        return False
    held_by_name = _viewer_entries(viewer, declaration)
    if held_by_name is None:
        return False
    ok = True
    for dim in declaration.dimensions:
        rec = res.label[dim.name]
        entry = held_by_name.get(dim.name)
        if dim.type == HIERARCHICAL:
            if entry is None or not isinstance(entry, str) or entry not in dim.vocabulary:
                return False
            if dim.vocabulary.index(entry) < dim.vocabulary.index(rec):
                ok = False
            continue
        if entry is None:
            held = set()
        elif _is_str_collection(entry):
            held = set(entry)
        else:
            return False
        if dim.type == PERMISSIVE and dim.has_author:
            audience = set(rec["release"] or ())
            if single_authorship:
                audience.add(rec["author"])
            if not (held & audience):
                ok = False
        elif dim.type == PERMISSIVE:
            if not (held & set(rec)):
                ok = False
        elif dim.type == RESTRICTIVE:
            if not set(rec) <= held:
                ok = False
        elif dim.type == EXCLUSIONARY:
            if held & set(rec):
                ok = False
    return ok


def high_water(labels, declaration, *, single_authorship):
    """High-water label of the inputs (ADR-0055 section 3b), or None.

    None when labels is empty or any element is None or fails validate.
    Sets come back as sorted lists.

    For a permissive dimension with an author, the audience is the
    intersection of the effective audiences ({author} | release). When
    single_authorship is true and every input has the same author, that
    author is kept and release is the intersection of the release sets
    (absent only when every input's is absent), which gives that same
    audience, and the high-water of one label is that label. Otherwise
    author is None and release is the whole intersection of the effective
    audiences.

    When author is None the result does not validate (dimension_missing) and
    compiles to no lk1 key, so it is served to nobody. ADR-0029's addendum and
    ADR-0055 section 2 disagree on that case and the ruling is owed. This
    function does not resolve it.
    """
    try:
        return _high_water(labels, declaration, single_authorship)
    except Exception:
        return None


def _high_water(labels, declaration, single_authorship):
    items = list(labels)
    if not items:
        return None
    norm = []
    for lab in items:
        if lab is None:
            return None
        res = validate(lab, declaration)
        if isinstance(res, Refused):
            return None
        norm.append(res.label)
    out = {}
    for dim in declaration.dimensions:
        vals = [n[dim.name] for n in norm]
        if dim.type == HIERARCHICAL:
            out[dim.name] = max(vals, key=dim.vocabulary.index)
        elif dim.type == PERMISSIVE and dim.has_author:
            authors = {v["author"] for v in vals}
            if single_authorship and len(authors) == 1:
                # With one author A kept: the intersection of (R_i | {A}) is (the intersection of R_i) | {A},
                # so release is the intersection of the release sets and the audience is unchanged.
                # It stays absent only when every input's is absent, so one label's high-water is that
                # label, key included (declared-empty and absent are two keys, ADR-0055 section 2).
                author = next(iter(authors))
                if all(v["release"] is None for v in vals):
                    release = None
                else:
                    release = sorted(set.intersection(*[set(v["release"] or ()) for v in vals]))
            else:
                author = None
                audiences = [set(v["release"] or ()) | {v["author"]} for v in vals]
                release = sorted(set.intersection(*audiences))
            out[dim.name] = {"author": author, "release": release}
        elif dim.type == PERMISSIVE:
            out[dim.name] = sorted(set.intersection(*[set(v) for v in vals]))
        else:
            out[dim.name] = sorted(set().union(*[set(v) for v in vals]))
    return out
