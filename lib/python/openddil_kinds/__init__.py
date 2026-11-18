"""openddil_kinds: ADR-0061 Decision 3's load check, in report mode.

Given a kind's JSON Schema, reports open objects, unbounded strings, arrays
with no maxItems and whether the kind qualifies as cross-domain eligible
(Decision 4): SPEC-kinds-closure.md.

Nothing calls this module yet.
"""

from .closure import (
    BOUNDED_FORMATS,
    FINDINGS,
    LOAD_REFUSALS,
    check_kind,
    generate_vectors,
)

__all__ = ["BOUNDED_FORMATS", "FINDINGS", "LOAD_REFUSALS", "check_kind", "generate_vectors"]
