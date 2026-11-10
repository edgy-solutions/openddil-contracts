"""
test_iagent_citation_pins.py — an ADR that cites an iagent record pins the commit it read, and the
CI job that proves it cannot be decorative.

scripts/check-iagent-citation-pins.sh checks each `**Cites:**` line against
.github/invincible-agent.ref; scripts/check-decision-indexes.sh fails when it fails; and
.github/workflows/decision-indexes.yml fetches the pin and checks each cited file exists. This file
is hermetic: it runs the script on the real tree and on tmp trees with one defect each, and seals
the workflow's shape (the network half runs only on GitHub). It mirrors invincible-agent's
tests/test_reference_adrs_pin_their_source.py.

The bash used is OPENDDIL_BASH if set, else the first `bash` on PATH.
"""
import os
import pathlib
import shutil
import subprocess

import pytest
import yaml

ROOT = pathlib.Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check-iagent-citation-pins.sh"
INDEX = ROOT / "scripts" / "check-decision-indexes.sh"
WF = ROOT / ".github" / "workflows" / "decision-indexes.yml"
PIN = "46df48255d02274ac66538fe77bd7b0a69da48cb"
BASH = os.environ.get("OPENDDIL_BASH") or shutil.which("bash")
GOOD_CITES = "**Cites:** `invincible-agent/docs/adr/ADR-0063-x.md` at `46df482`\n"


def run(script, *args):
    return subprocess.run([BASH, str(script), *map(str, args)], capture_output=True, text=True)


def tree(tmp_path, adrs, ref=PIN + "\n"):
    (tmp_path / "decisions").mkdir()
    (tmp_path / ".github").mkdir()
    for name, body in adrs.items():
        (tmp_path / "decisions" / name).write_text(body, encoding="utf-8")
    if ref is not None:
        (tmp_path / ".github" / "invincible-agent.ref").write_text(ref, encoding="utf-8")
    return tmp_path


def adr(cites=GOOD_CITES, text="It follows `iagent:ADR-0063`.\n"):
    return f"# ADR-0001 — t\n\n{cites}\n## Status\n\nProposed.\n\n{text}"


def test_the_real_tree_passes_and_lists_five_adrs_at_the_full_pin():
    r = run(SCRIPT, ROOT)
    assert r.returncode == 0, r.stderr
    rows = [line.split() for line in r.stdout.splitlines()]
    assert {row[0][:8] for row in rows} == {"ADR-0042", "ADR-0051", "ADR-0052", "ADR-0053", "ADR-0055"}
    assert all(row[1] == "invincible-agent" and row[2] == PIN for row in rows)
    assert {row[3] for row in rows} == {
        "docs/adr/ADR-0054-data-classes-every-write-declares-what-it-is.md",
        "docs/adr/ADR-0063-field-kinds-from-openddil.md",
        "docs/adr/ADR-0064-classification-propagates-through-derivation.md",
    }


def test_a_good_tmp_tree_passes(tmp_path):
    r = run(SCRIPT, tree(tmp_path, {"ADR-0001-t.md": adr()}))
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["ADR-0001-t.md", "invincible-agent", PIN, "docs/adr/ADR-0063-x.md"]


def test_a_short_sha_that_is_not_a_prefix_of_the_pin_is_refused(tmp_path):
    r = run(SCRIPT, tree(tmp_path, {"ADR-0001-t.md": adr(cites=GOOD_CITES.replace("46df482", "abcdef1"))}))
    assert r.returncode == 1
    assert "not a prefix of the pin" in r.stderr


def test_a_missing_ref_file_is_refused(tmp_path):
    r = run(SCRIPT, tree(tmp_path, {"ADR-0001-t.md": adr()}, ref=None))
    assert r.returncode == 1
    assert "invincible-agent.ref is missing" in r.stderr


@pytest.mark.parametrize("ref", ["46df482\n", PIN + "\n" + PIN + "\n", "# only a comment\n"])
def test_a_malformed_ref_file_is_refused(tmp_path, ref):
    r = run(SCRIPT, tree(tmp_path, {"ADR-0001-t.md": adr()}, ref=ref))
    assert r.returncode == 1
    assert "exactly one full 40-hex sha" in r.stderr


def test_an_inline_citation_without_a_cites_line_is_refused(tmp_path):
    r = run(SCRIPT, tree(tmp_path, {"ADR-0001-t.md": adr(), "ADR-0002-u.md": adr(cites="")}))
    assert r.returncode == 1
    assert "ADR-0002-u.md: cites iagent:ADR-0063 with no Cites line" in r.stderr


def test_a_cites_line_without_an_inline_citation_is_refused(tmp_path):
    r = run(SCRIPT, tree(tmp_path, {"ADR-0001-t.md": adr(text="No citation here.\n")}))
    assert r.returncode == 1
    assert "never cites iagent:ADR-0063" in r.stderr


def test_a_malformed_cites_line_is_refused(tmp_path):
    r = run(SCRIPT, tree(tmp_path, {"ADR-0001-t.md": adr(cites=GOOD_CITES.replace(" at ", " @ "))}))
    assert r.returncode == 1
    assert "Cites line is malformed" in r.stderr


def test_zero_cites_lines_is_not_a_pass(tmp_path):
    r = run(SCRIPT, tree(tmp_path, {"ADR-0001-t.md": adr(cites="", text="Nothing foreign.\n")}))
    assert r.returncode == 1
    assert "an empty list is not a pass" in r.stderr


def test_two_errors_are_both_reported(tmp_path):
    r = run(SCRIPT, tree(tmp_path, {
        "ADR-0001-t.md": adr(cites=GOOD_CITES.replace("46df482", "abcdef1")),
        "ADR-0002-u.md": adr(cites=""),
    }))
    assert r.returncode == 1
    assert "not a prefix of the pin" in r.stderr and "with no Cites line" in r.stderr


def test_the_index_check_fails_when_a_pin_fails(tmp_path):
    shutil.copytree(ROOT / "decisions", tmp_path / "decisions")
    shutil.copytree(ROOT / "scripts", tmp_path / "scripts")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "invincible-agent.ref").write_text("f" * 40 + "\n", encoding="utf-8")
    r = run(tmp_path / "scripts" / "check-decision-indexes.sh")
    assert r.returncode == 1
    assert "not a prefix of the pin" in r.stderr


def _wf():
    return yaml.safe_load(WF.read_text(encoding="utf-8"))


def test_the_workflow_triggers_on_the_adrs_the_pin_the_scripts_this_test_and_a_schedule():
    on = _wf()[True]
    for event in ("push", "pull_request"):
        paths = on[event]["paths"]
        for p in ("decisions/**", ".github/invincible-agent.ref", "scripts/check-iagent-citation-pins.sh",
                  "scripts/check-decision-indexes.sh", "tests/test_iagent_citation_pins.py",
                  ".github/workflows/decision-indexes.yml"):
            assert p in paths, (event, p)
    assert on["schedule"][0]["cron"]


def _step(name_part):
    steps = _wf()["jobs"]["check"]["steps"]
    return next(s for s in steps if name_part in s.get("name", ""))


def test_the_index_step_runs_under_pipefail_and_writes_the_pin_list_to_a_file():
    run_ = _step("Check decision indexes")["run"]
    assert "set -euo pipefail" in run_
    assert 'PINS_OUT="$RUNNER_TEMP/pins.txt" ./scripts/check-decision-indexes.sh' in run_
    assert "|" not in run_


def test_the_fetch_step_fetches_by_sha_resolves_fetch_head_and_checks_the_path():
    run_ = _step("exists at the pinned commit")["run"]
    assert 'fetch -q --depth=1 "https://github.com/edgy-solutions/${repo}.git" "$sha"' in run_
    assert 'rev-parse FETCH_HEAD' in run_ and '[ "$got" != "$sha" ]' in run_
    assert 'cat-file -e "${sha}:${path}"' in run_
    assert 'exit "$fail"' in run_
    assert "an empty list is not a pass" in run_


def test_nothing_in_the_workflow_continues_on_error():
    assert "continue-on-error" not in WF.read_text(encoding="utf-8")
