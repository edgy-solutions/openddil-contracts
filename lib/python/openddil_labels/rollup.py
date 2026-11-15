"""The ADR-0055 section 3a audience split, with the withheld tally.

Status: Builds on the PROPOSED ADR-0055 §3a ruling (an unlabelled contributor forms no class and is counted in a withheld
tally). It is not a ruled behaviour: the built regional rollup keeps an empty-audience class, and which one
stands is an owed ruling.

A contributor with no label, or one that does not validate, forms no class.
There is no empty-audience class; that is the difference from the built
aggregator (regional/aggregator_app.py:_class_key, "The empty string is a real
class").

What this slice does not do:

- No key for a class row. Its nation value has no author, and lk1 keys only
  author|release; the key form for an author-less row is owed (it sits with the
  lk2 ruling). class_label returns a label, never a key.
- No sums or rows, and no stamping. The caller computes rows from each class's
  members.

Nothing calls this module yet.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass

from .admission import Refused, Valid, _is_str_collection, _viewer_entries, validate
from .model import EXCLUSIONARY, HIERARCHICAL, PERMISSIVE, RESTRICTIVE, normalise_name

NO_LABEL = "no_label"


def class_label(label, declaration):
    """The label a contributor carries in an aggregate, or Refused. Never raises.

    A permissive dimension with an author becomes {"author": None, "release":
    sorted({author} | release)}: in an aggregate the author grants nothing
    alone. Every other dimension keeps its validated value.
    """
    try:
        return _class_label(label, declaration)
    except Exception:
        return Refused("value_malformed", None, None)


def _class_label(label, declaration):
    if label is None:
        return Refused(NO_LABEL, None, None)
    res = validate(label, declaration)
    if isinstance(res, Refused):
        return res
    out = {}
    for dim in declaration.dimensions:
        v = res.label[dim.name]
        if dim.type == PERMISSIVE and dim.has_author:
            out[dim.name] = {
                "author": None,
                "release": sorted({v["author"]} | set(v["release"] or ())),
            }
        else:
            out[dim.name] = v
    return out


@dataclass(frozen=True)
class RollupClass:
    label: dict
    members: tuple


@dataclass(frozen=True)
class Split:
    classes: tuple
    withheld: int
    withheld_by_reason: tuple
    withheld_ids: tuple


def _label_key(label):
    return json.dumps(label, sort_keys=True, separators=(",", ":"))


def split_by_audience(contributors, declaration):
    """Group (contributor_id, label) pairs into classes; tally the rest as withheld.

    ValueError for a non-str, empty or duplicate id (a programming error).
    Everything else about the input is data.
    """
    seen = set()
    classes = {}
    by_reason = {}
    withheld_ids = []
    for cid, label in contributors:
        if not isinstance(cid, str) or not cid:
            raise ValueError("contributor id must be a non-empty str")
        if cid in seen:
            raise ValueError("duplicate contributor id: %r" % (cid,))
        seen.add(cid)
        cl = class_label(label, declaration)
        if isinstance(cl, Refused):
            by_reason[cl.reason] = by_reason.get(cl.reason, 0) + 1
            withheld_ids.append(cid)
            continue
        key = _label_key(cl)
        if key not in classes:
            classes[key] = (cl, [])
        classes[key][1].append(cid)
    rows = tuple(
        RollupClass(classes[k][0], tuple(sorted(classes[k][1]))) for k in sorted(classes)
    )
    return Split(
        rows,
        len(withheld_ids),
        tuple(sorted(by_reason.items())),
        tuple(sorted(withheld_ids)),
    )


def _class_form(label, declaration):
    """Normalise a class-form label (author-less on has_author dimensions), or None.

    The label must name exactly the declared dimensions, each well-formed and
    inside its vocabulary. A has_author dimension needs author None and a
    release list.
    """
    if not isinstance(label, Mapping):
        return None
    by_name = {}
    for k in label:
        if not isinstance(k, str):
            return None
        try:
            n = normalise_name(k)
        except ValueError:
            return None
        if n in by_name or declaration.get(n) is None:
            return None
        by_name[n] = k
    out = {}
    for dim in declaration.dimensions:
        if dim.name not in by_name:
            return None
        v = label[by_name[dim.name]]
        vocab = dim.vocabulary
        if dim.type == HIERARCHICAL:
            if not isinstance(v, str) or v not in vocab:
                return None
            out[dim.name] = v
            continue
        if dim.type == PERMISSIVE and dim.has_author:
            if not isinstance(v, Mapping) or set(v.keys()) != {"author", "release"}:
                return None
            if v["author"] is not None:
                return None
            v = v["release"]
            if not isinstance(v, (list, tuple, set, frozenset)):
                return None
            if not _is_str_collection(v) or any(x not in vocab for x in v):
                return None
            out[dim.name] = {"author": None, "release": sorted(set(v))}
            continue
        if v is None or not _is_str_collection(v) or any(x not in vocab for x in v):
            return None
        out[dim.name] = sorted(set(v))
    return out


def admits_class(viewer, class_label, declaration):
    """True when the viewer may read a class row. Never raises.

    As admits, except that on a permissive dimension with an author the class
    label's author must be None and the viewer needs one release value.
    """
    try:
        return _admits_class(viewer, class_label, declaration)
    except Exception:
        return False


def _admits_class(viewer, class_label, declaration):
    rec_all = _class_form(class_label, declaration)
    if rec_all is None:
        return False
    held_by_name = _viewer_entries(viewer, declaration)
    if held_by_name is None:
        return False
    ok = True
    for dim in declaration.dimensions:
        rec = rec_all[dim.name]
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
            if not (held & set(rec["release"])):
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
