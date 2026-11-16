"""The downgrade record (ADR-0055 section 3 "Both rules", check 6).

Status: Builds on the PROPOSED ADR-0055 §3a ruling (an unlabelled contributor forms no class and is counted in a withheld
tally). It is not a ruled behaviour: the built regional rollup keeps an empty-audience class, and which one
stands is an owed ruling.

A floor may be in class form: on a permissive dimension with an author, the PROPOSED ADR-0055 §2a (#38) rollup marker
{"rollup": True, "release": [...]}, which has no author and counts by its release only. A label in marker form never
validates, so a downgrade cannot hand out a rollup label.

A downgrade is a record of four things: the label it gives, the reason, the
inputs it covers, and the owner who decided it. The owner is a person or role
named in the declaration of each dimension the downgrade lowers. A downgrade
with no owner or no reason is refused. The framework performs no automatic
downgrade: record_downgrade records a label it is handed and never computes
one. No function in the package takes a floor and returns a lower label.

Not in this slice: a standing downgrade rule (a declared rule signed by a named
owner). It needs a signed-rule record that no ADR shapes yet.

Nothing calls this module yet.
"""

from dataclasses import dataclass

from .admission import VALUE_MALFORMED, Refused, validate
from .model import EXCLUSIONARY, HIERARCHICAL, PERMISSIVE, RESTRICTIVE
from .rollup import _class_form

DOWNGRADE_NO_OWNER = "downgrade_no_owner"
DOWNGRADE_NO_REASON = "downgrade_no_reason"
DOWNGRADE_NO_INPUTS = "downgrade_no_inputs"
DOWNGRADE_OWNER_NOT_DECLARED = "downgrade_owner_not_declared"
DOWNGRADE_LOWERS_NOTHING = "downgrade_lowers_nothing"


@dataclass(frozen=True)
class Downgrade:
    label: dict
    reason: str
    inputs: tuple
    owner: str
    floor: dict
    lowers: tuple


def record_downgrade(*, floor, label, reason, inputs, owner, declaration, single_authorship):
    """Return a Downgrade or Refused (first failure). Never raises."""
    try:
        return _record(floor, label, reason, inputs, owner, declaration, single_authorship)
    except Exception:
        return Refused(VALUE_MALFORMED, None, None)


def _blank(s):
    return not isinstance(s, str) or not s.strip()


def _record(floor, label, reason, inputs, owner, declaration, single_authorship):
    if _blank(owner):
        return Refused(DOWNGRADE_NO_OWNER, None, None)
    if _blank(reason):
        return Refused(DOWNGRADE_NO_REASON, None, None)
    if not isinstance(inputs, (list, tuple, set, frozenset)) or len(inputs) == 0:
        return Refused(DOWNGRADE_NO_INPUTS, None, None)
    if any(_blank(i) for i in inputs):
        return Refused(VALUE_MALFORMED, None, None)
    res = validate(label, declaration)
    if isinstance(res, Refused):
        return res
    fres = validate(floor, declaration)
    fl = fres.label if not isinstance(fres, Refused) else _class_form(floor, declaration)
    if fl is None:
        return Refused(VALUE_MALFORMED, None, None)
    lab = res.label

    def aud(x):
        s = set(x["release"] or ())
        if x.get("author") is not None and single_authorship:
            s.add(x["author"])
        return s

    lowers = []
    for dim in declaration.dimensions:
        new, old = lab[dim.name], fl[dim.name]
        if dim.type == HIERARCHICAL:
            low = dim.vocabulary.index(new) < dim.vocabulary.index(old)
        elif dim.type == PERMISSIVE and dim.has_author:
            low = bool(aud(new) - aud(old))
        elif dim.type == PERMISSIVE:
            low = bool(set(new) - set(old))
        else:
            low = bool(set(old) - set(new))
        if low:
            lowers.append(dim)
    if not lowers:
        return Refused(DOWNGRADE_LOWERS_NOTHING, None, None)
    who = owner.strip()
    for dim in lowers:
        if who != dim.owner:
            return Refused(DOWNGRADE_OWNER_NOT_DECLARED, dim.name, None)
    return Downgrade(
        lab,
        reason.strip(),
        tuple(sorted(set(inputs))),
        who,
        fl,
        tuple(d.name for d in lowers),
    )
