"""Dimension and declaration model for labels.

Implements ADR-0055 section 1 (a label is a set of declared dimensions: the
four types, snake_case names by rule) and section 1a (no default anywhere):
SPEC-labels.md, model.py.

Nothing calls this module yet.
"""

import re
from dataclasses import dataclass

HIERARCHICAL, PERMISSIVE, RESTRICTIVE, EXCLUSIONARY = (
    "hierarchical",
    "permissive",
    "restrictive",
    "exclusionary",
)

TYPES = (HIERARCHICAL, PERMISSIVE, RESTRICTIVE, EXCLUSIONARY)

_NAME_RE = re.compile(r"[a-z][a-z0-9_]*")
_POLICY_ID_RE = re.compile(r"[a-z0-9][a-z0-9:._-]{0,62}")


def normalise_name(s: str) -> str:
    """Return the snake_case form of a dimension name, or raise ValueError."""
    if not isinstance(s, str):
        raise ValueError("dimension name must be a str")
    t = re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")
    if not _NAME_RE.fullmatch(t):
        raise ValueError("invalid dimension name: %r" % (s,))
    return t


@dataclass(frozen=True)
class Dimension:
    """One declared dimension. For hierarchical, vocabulary is the level list, lowest first."""

    name: str
    type: str
    vocabulary: tuple[str, ...]
    owner: str
    has_author: bool

    def __post_init__(self):
        object.__setattr__(self, "name", normalise_name(self.name))
        if self.type not in TYPES:
            raise ValueError("unknown dimension type: %r" % (self.type,))
        if not isinstance(self.owner, str) or not self.owner.strip():
            raise ValueError("owner must be a non-empty str")
        vocab = self.vocabulary
        if isinstance(vocab, (str, bytes)) or not hasattr(vocab, "__iter__"):
            raise ValueError("vocabulary must be a collection of str")
        vocab = tuple(vocab)
        if not vocab:
            raise ValueError("vocabulary must not be empty")
        for v in vocab:
            if not isinstance(v, str) or not v:
                raise ValueError("vocabulary elements must be non-empty str")
        if len(set(vocab)) != len(vocab):
            raise ValueError("vocabulary has duplicates")
        object.__setattr__(self, "vocabulary", vocab)
        if not isinstance(self.has_author, bool):
            raise ValueError("has_author must be a bool")
        if self.has_author and self.type != PERMISSIVE:
            raise ValueError("has_author is only valid on a permissive dimension")

    @classmethod
    def hierarchical(cls, name, levels, owner):
        return cls(name, HIERARCHICAL, tuple(levels), owner, False)

    @classmethod
    def permissive(cls, name, vocabulary, owner, *, has_author):
        return cls(name, PERMISSIVE, tuple(vocabulary), owner, has_author)

    @classmethod
    def restrictive(cls, name, vocabulary, owner):
        return cls(name, RESTRICTIVE, tuple(vocabulary), owner, False)

    @classmethod
    def exclusionary(cls, name, vocabulary, owner):
        return cls(name, EXCLUSIONARY, tuple(vocabulary), owner, False)


@dataclass(frozen=True)
class Declaration:
    """A deployment's declared policy: an id and its dimensions, in order."""

    policy_id: str
    dimensions: tuple[Dimension, ...]

    def __post_init__(self):
        if not isinstance(self.policy_id, str) or not _POLICY_ID_RE.fullmatch(self.policy_id):
            raise ValueError("invalid policy_id: %r" % (self.policy_id,))
        dims = tuple(self.dimensions)
        if not dims:
            raise ValueError("a declaration needs at least one dimension")
        names = []
        for d in dims:
            if not isinstance(d, Dimension):
                raise ValueError("dimensions must be Dimension instances")
            names.append(d.name)
        if len(set(names)) != len(names):
            raise ValueError("two dimensions share a normalised name")
        object.__setattr__(self, "dimensions", dims)

    def get(self, name):
        """Return the dimension with this (normalised) name, or None."""
        try:
            n = normalise_name(name)
        except ValueError:
            return None
        for d in self.dimensions:
            if d.name == n:
                return d
        return None
