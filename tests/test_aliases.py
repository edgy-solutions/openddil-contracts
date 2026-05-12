"""
test_aliases.py — Validates the asset identity alias YAML.

Tests:
  - File parses as valid YAML
  - Top-level 'aliases' key exists
  - 'dis' section exists
  - Every DIS entry has 'dis_entity_id' and 'canonical_asset_id'
  - Every DIS entity_id has site, application, entity fields
"""
import yaml
import pathlib
import pytest

ALIASES_PATH = pathlib.Path(__file__).parent.parent / "ontology" / "asset_identity_aliases.yaml"


@pytest.fixture(scope="module")
def aliases():
    with open(ALIASES_PATH) as f:
        return yaml.safe_load(f)


def test_aliases_parses(aliases):
    assert aliases is not None


def test_aliases_key_exists(aliases):
    assert "aliases" in aliases


def test_dis_section_exists(aliases):
    assert "dis" in aliases["aliases"], "'dis' section missing from aliases"


def test_dis_entries_have_required_fields(aliases):
    dis_entries = aliases["aliases"].get("dis") or []
    for entry in dis_entries:
        assert "dis_entity_id" in entry, f"Entry missing dis_entity_id: {entry}"
        assert "canonical_asset_id" in entry, f"Entry missing canonical_asset_id: {entry}"
        eid = entry["dis_entity_id"]
        for field in ("site", "application", "entity"):
            assert field in eid, f"dis_entity_id missing '{field}': {eid}"


def test_canonical_asset_ids_are_nonempty(aliases):
    dis_entries = aliases["aliases"].get("dis") or []
    for entry in dis_entries:
        cid = entry.get("canonical_asset_id", "")
        assert cid, f"canonical_asset_id is empty for entry: {entry}"
