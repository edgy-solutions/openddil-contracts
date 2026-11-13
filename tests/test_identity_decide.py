"""Tests for openddil_identity.declaration.decide (ADR-0056 check 10, spec 2.3 and 2.4)."""

import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "lib" / "python"))

from openddil_identity.declaration import (  # noqa: E402
    Alias,
    Bind,
    Binding,
    Conflict,
    Mint,
    Replay,
    decide,
    declaration_ref,
)
from openddil_identity.ids import Identity, lookup_key, mint_identity  # noqa: E402

NS = {
    "asset_id": uuid.UUID("11111111-1111-4111-8111-111111111111"),
    "serial": uuid.UUID("22222222-2222-4222-8222-222222222222"),
    "uii": uuid.UUID("33333333-3333-4333-8333-333333333333"),
}


class Store:
    def __init__(self):
        self.identities = set()
        self.aliases = {}  # (scheme, lookup_key) -> Identity
        self.bindings = {}  # asset_id -> Binding

    def resolve(self, scheme, lk):
        self.calls.append(scheme)
        return self.aliases.get((scheme, lk))

    calls: list

    def current_binding(self, asset_id):
        return self.bindings.get(asset_id)

    def counts(self):
        return (len(self.identities), len(self.aliases), len(self.bindings))

    def put_alias(self, scheme, value, identity):
        self.aliases[(scheme, lookup_key(NS[scheme], value))] = identity

    def run(self, declaration, schemes=None):
        self.calls = []
        return decide(
            declaration,
            asset_id_scheme="asset_id",
            registered_schemes=NS if schemes is None else schemes,
            resolve=self.resolve,
            current_binding=self.current_binding,
        )

    def apply(self, result, asset_id):
        if isinstance(result, Mint):
            ident = mint_identity()
            self.identities.add(ident)
            for a in result.aliases:
                self.aliases[(a.scheme, a.lookup_key)] = ident
            self.bindings[asset_id] = Binding(ident, result.declaration)
        elif isinstance(result, Bind):
            for a in result.new_aliases:
                self.aliases[(a.scheme, a.lookup_key)] = result.identity
            self.bindings[asset_id] = Binding(result.identity, result.declaration)


def test_check10_uii_resolves_bind_never_mint():
    s = Store()
    x = mint_identity()
    s.put_alias("uii", "UII-0001", x)
    result = s.run({"asset_id": "asset-001", "serial": "SN-0001", "uii": "UII-0001"})
    assert isinstance(result, Bind)
    assert result.identity == x
    assert result.binding_exists is False
    assert {a.scheme for a in result.new_aliases} == {"asset_id", "serial"}
    assert [a.scheme for a in result.new_aliases] == ["asset_id", "serial"]
    assert result.skipped == ()


def test_check10_aliases_disagree():
    s = Store()
    x, y = mint_identity(), mint_identity()
    s.put_alias("serial", "SN-0001", x)
    s.put_alias("uii", "UII-0001", y)
    r = s.run({"asset_id": "asset-001", "serial": "SN-0001", "uii": "UII-0001"})
    assert isinstance(r, Conflict)
    assert r.reason == "aliases_disagree"
    assert r.asset_id == "asset-001"
    assert r.identities == tuple(sorted((x, y), key=lambda i: str(i.value)))


def test_check10_asset_bound_elsewhere():
    s = Store()
    x, y = mint_identity(), mint_identity()
    s.bindings["asset-001"] = Binding(x, "older-ref")
    s.put_alias("asset_id", "asset-001", x)
    s.put_alias("serial", "SN-0001", y)
    # asset_id's own alias resolves to x and serial to y: disagree comes first.
    r = s.run({"asset_id": "asset-001", "serial": "SN-0001"})
    assert isinstance(r, Conflict) and r.reason == "aliases_disagree"
    # Only the serial is open (asset_id alias closed): bound to X, serial is Y.
    del s.aliases[("asset_id", lookup_key(NS["asset_id"], "asset-001"))]
    r = s.run({"asset_id": "asset-001", "serial": "SN-0001"})
    assert isinstance(r, Conflict)
    assert r.reason == "asset_bound_elsewhere"
    assert r.identities == tuple(sorted((x, y), key=lambda i: str(i.value)))


def test_check10_replay():
    s = Store()
    d = {"asset_id": "asset-001", "serial": "SN-0001"}
    s.bindings["asset-001"] = Binding(mint_identity(), declaration_ref(d))
    assert s.run(d) == Replay(declaration_ref(d))


def test_check10_unregistered_scheme_skipped_not_looked_up():
    s = Store()
    schemes = {k: v for k, v in NS.items() if k != "uii"}
    r = s.run({"asset_id": "asset-001", "uii": "UII-0001"}, schemes)
    assert isinstance(r, Mint)
    assert r.skipped == ("uii",)
    assert s.calls == ["asset_id"]
    assert [a.scheme for a in r.aliases] == ["asset_id"]


def test_check10_bound_without_alias():
    s = Store()
    x = mint_identity()
    s.bindings["asset-001"] = Binding(x, "older-ref")
    r = s.run({"asset_id": "asset-001", "serial": "SN-0001"})
    assert isinstance(r, Conflict)
    assert r.reason == "bound_without_alias"
    assert r.identities == (x,)


def test_absent_none_and_empty_fields_skipped():
    s = Store()
    r = s.run({"asset_id": "asset-001", "serial": "", "uii": None})
    assert isinstance(r, Mint)
    assert [a.scheme for a in r.aliases] == ["asset_id"]
    assert r.skipped == ()


def test_asset_id_must_be_nonempty_str():
    import pytest

    s = Store()
    for bad in ({}, {"asset_id": ""}, {"asset_id": 5}):
        with pytest.raises(ValueError):
            s.run(bad)


def test_unregistered_asset_id_scheme_refused_not_minted():
    import pytest

    s = Store()
    schemes = {k: v for k, v in NS.items() if k != "asset_id"}
    with pytest.raises(ValueError):
        s.run({"asset_id": "asset-001", "serial": "SN-0001"}, schemes)


def test_spec_2_4_replay_changes_nothing():
    s = Store()
    decls = [
        {"asset_id": f"asset-{n:03d}", "serial": f"SN-{n:04d}", "uii": f"UII-{n:04d}"}
        for n in range(1, 6)
    ]
    first = []
    for d in decls:
        r = s.run(d)
        assert isinstance(r, Mint)
        s.apply(r, d["asset_id"])
        first.append(r)
    counts = s.counts()
    assert counts == (5, 15, 5)
    for d in decls:
        r = s.run(d)
        assert isinstance(r, Replay)
        s.apply(r, d["asset_id"])
    assert s.counts() == counts

    # A changed declaration for an already-bound asset binds, minting nothing.
    changed = {"asset_id": "asset-001", "serial": "SN-0001"}
    s2 = Store()
    base = {"asset_id": "asset-001"}
    s2.apply(s2.run(base), "asset-001")
    r = s2.run(changed)
    assert isinstance(r, Bind)
    assert r.binding_exists is True
    assert [a.scheme for a in r.new_aliases] == ["serial"]
    assert isinstance(r.identity, Identity)
    before = len(s2.identities)
    s2.apply(r, "asset-001")
    assert len(s2.identities) == before
    assert isinstance(s2.run(changed), Replay)
