"""openddil_labels: ADR-0055 labels as a set of declared dimensions.

Implements the first slice of ADR-0055 (SPEC-labels.md): model, admission and
the lk1 key.

Nothing calls this module yet.
"""

from .admission import (
    DIMENSION_AMBIGUOUS,
    DIMENSION_MISSING,
    DIMENSION_UNDECLARED,
    HIERARCHICAL_EMPTY,
    VALUE_MALFORMED,
    VALUE_OUT_OF_VOCABULARY,
    Refused,
    Valid,
    admits,
    high_water,
    validate,
)
from .lk1 import NATION_RE, POLICY_RE, canonical_lk1, compile_lk1, generate_vectors, verify
from .model import (
    EXCLUSIONARY,
    HIERARCHICAL,
    PERMISSIVE,
    RESTRICTIVE,
    Declaration,
    Dimension,
    normalise_name,
)

__all__ = [
    "DIMENSION_AMBIGUOUS",
    "DIMENSION_MISSING",
    "DIMENSION_UNDECLARED",
    "EXCLUSIONARY",
    "HIERARCHICAL",
    "HIERARCHICAL_EMPTY",
    "NATION_RE",
    "PERMISSIVE",
    "POLICY_RE",
    "RESTRICTIVE",
    "VALUE_MALFORMED",
    "VALUE_OUT_OF_VOCABULARY",
    "Declaration",
    "Dimension",
    "Refused",
    "Valid",
    "admits",
    "canonical_lk1",
    "compile_lk1",
    "generate_vectors",
    "high_water",
    "normalise_name",
    "validate",
    "verify",
]
