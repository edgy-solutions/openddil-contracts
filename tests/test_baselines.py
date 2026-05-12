"""
test_baselines.py — Validates the ConfigurationBaseline YAML files.

Tests:
  - All .yaml files in openddil-contracts/baselines/ parse cleanly
  - Each has the required top-level fields
  - authorized_cis entries have slot_id and acceptable_part_numbers
  - required_mods entries have mod_id, type, title, due_date, category
"""
import yaml
import pathlib
import pytest

BASELINES_DIR = pathlib.Path(__file__).parent.parent / "baselines"

BASELINE_REQUIRED_KEYS = {
    "baseline_id", "platform_variant", "version",
    "effective_from", "authorized_cis", "required_mods",
}

CI_REQUIRED_KEYS = {"slot_id", "acceptable_part_numbers"}

MOD_REQUIRED_KEYS = {"mod_id", "type", "title", "due_date", "category"}


def baseline_files():
    return list(BASELINES_DIR.glob("*.yaml"))


@pytest.mark.parametrize("baseline_file", baseline_files(), ids=lambda f: f.name)
def test_baseline_parses(baseline_file):
    with open(baseline_file) as f:
        data = yaml.safe_load(f)
    assert data is not None, f"{baseline_file.name} is empty"


@pytest.mark.parametrize("baseline_file", baseline_files(), ids=lambda f: f.name)
def test_baseline_required_fields(baseline_file):
    with open(baseline_file) as f:
        data = yaml.safe_load(f)
    missing = BASELINE_REQUIRED_KEYS - set(data.keys())
    assert not missing, f"{baseline_file.name} missing fields: {missing}"


@pytest.mark.parametrize("baseline_file", baseline_files(), ids=lambda f: f.name)
def test_authorized_cis_structure(baseline_file):
    with open(baseline_file) as f:
        data = yaml.safe_load(f)
    for ci in data.get("authorized_cis", []):
        missing = CI_REQUIRED_KEYS - set(ci.keys())
        assert not missing, f"{baseline_file.name} CI entry missing keys: {missing}"
        assert ci["acceptable_part_numbers"], "acceptable_part_numbers must not be empty"


@pytest.mark.parametrize("baseline_file", baseline_files(), ids=lambda f: f.name)
def test_required_mods_structure(baseline_file):
    with open(baseline_file) as f:
        data = yaml.safe_load(f)
    for mod in data.get("required_mods", []):
        missing = MOD_REQUIRED_KEYS - set(mod.keys())
        assert not missing, f"{baseline_file.name} mod entry missing keys: {missing}"


def test_at_least_three_baselines():
    files = baseline_files()
    assert len(files) >= 3, f"Expected at least 3 baseline files, found {len(files)}"
