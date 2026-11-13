"""openddil_identity: the first slice of ADR-0056 (pure library).

Nothing calls this package yet.
"""

from .declaration import (
    Alias,
    Bind,
    Binding,
    Conflict,
    Mint,
    Replay,
    declaration_ref,
    decide,
)
from .equivalence import (
    ALREADY_MERGED,
    OWNER_MISSING,
    REASON_MISSING,
    SURVIVOR_IS_MERGED,
    Ok,
    Refused,
    check_equivalence,
)
from .era import era
from .ids import (
    GENERATOR,
    GENERATOR_VERSION,
    Identity,
    LookupKey,
    as_iri,
    lookup_key,
    mint_identity,
)

__all__ = [
    "ALREADY_MERGED",
    "Alias",
    "Bind",
    "Binding",
    "Conflict",
    "GENERATOR",
    "GENERATOR_VERSION",
    "Identity",
    "LookupKey",
    "Mint",
    "OWNER_MISSING",
    "Ok",
    "REASON_MISSING",
    "Refused",
    "Replay",
    "SURVIVOR_IS_MERGED",
    "as_iri",
    "check_equivalence",
    "declaration_ref",
    "decide",
    "era",
    "lookup_key",
    "mint_identity",
]
