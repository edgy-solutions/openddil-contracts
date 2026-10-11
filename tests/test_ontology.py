"""
test_ontology.py — Validates the DIS entity type ontology YAML.

Tests:
  - File parses as valid YAML
  - Top-level 'mappings' key exists
  - _default entry exists and has required keys
  - All entries have the 7 required keys
  - No entry has a null platform_variant (except _default which is "UNKNOWN")
"""
import yaml
import pathlib
import pytest

ONTOLOGY_PATH = pathlib.Path(__file__).parent.parent / "ontology" / "dis_entity_types.yaml"

REQUIRED_KEYS = {
    "platform_variant",
    "platform_family",
    "nomenclature",
    "cm_schema",
    "default_baseline",
    "cbm_schema",
    "domain_authority",
}


@pytest.fixture(scope="module")
def ontology():
    with open(ONTOLOGY_PATH) as f:
        return yaml.safe_load(f)


def test_ontology_parses(ontology):
    assert ontology is not None, "Ontology YAML failed to parse"


def test_mappings_key_exists(ontology):
    assert "mappings" in ontology, "Top-level 'mappings' key missing"


def test_default_entry_exists(ontology):
    assert "_default" in ontology["mappings"], "_default fallback entry is required and missing"


def test_default_entry_has_required_keys(ontology):
    default = ontology["mappings"]["_default"]
    missing = REQUIRED_KEYS - set(default.keys())
    assert not missing, f"_default entry missing required keys: {missing}"


def test_all_entries_have_required_keys(ontology):
    mappings = ontology["mappings"]
    failures = []
    for triple, entry in mappings.items():
        missing = REQUIRED_KEYS - set(entry.keys())
        if missing:
            failures.append(f"{triple}: missing {missing}")
    assert not failures, "Ontology entries missing required keys:\n" + "\n".join(failures)


def test_no_null_platform_variant_except_default(ontology):
    mappings = ontology["mappings"]
    for triple, entry in mappings.items():
        if triple == "_default":
            continue
        assert entry.get("platform_variant") not in (None, ""), \
            f"Entry '{triple}' has null/empty platform_variant"


def test_default_platform_variant_is_unknown(ontology):
    assert ontology["mappings"]["_default"]["platform_variant"] == "UNKNOWN", \
        "_default.platform_variant must be 'UNKNOWN'"


VALID_DEPLOYMENT_SIGNALS = {"launcher_bit", "emission"}
EXPECTED_DEPLOYMENT_SIGNALS = {
    "MRAD_Sensor": "emission",
    "MRAD_Interceptor": "launcher_bit",
}


def _declared_signals(ontology):
    return {
        e["platform_variant"]: e["deployment_signal"]
        for e in ontology["mappings"].values()
        if "deployment_signal" in e
    }


def test_deployment_signal_values_are_valid(ontology):
    bad = {
        k: e["deployment_signal"]
        for k, e in ontology["mappings"].items()
        if "deployment_signal" in e
        and e["deployment_signal"] not in VALID_DEPLOYMENT_SIGNALS
    }
    assert not bad, f"invalid deployment_signal values: {bad}"


def test_mrad_deployment_signals(ontology):
    declared = _declared_signals(ontology)
    assert declared.get("MRAD_Sensor") == "emission"
    assert declared.get("MRAD_Interceptor") == "launcher_bit"


def test_no_other_entry_declares_deployment_signal(ontology):
    assert _declared_signals(ontology) == EXPECTED_DEPLOYMENT_SIGNALS,         "deployment_signal set changed; update EXPECTED_DEPLOYMENT_SIGNALS deliberately"
