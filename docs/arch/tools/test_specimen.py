"""Tests for the committed specimen under docs/arch/specimen/.

Run from the worktree root:
    python -m unittest docs/arch/tools/test_specimen.py

The specimen is the three profiles rendered from the chart with the
tier-node values and the egress twin. These tests render fresh and compare,
read the twin for configuration values that must stay out of the views, and
check that every data-exchange output says it is declared, not measured. They
skip, printing why, when helm, the chart or the twin is absent.
"""
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import refresh_specimen as rs  # noqa: E402
import capability_phases as cp  # noqa: E402

SPECIMEN = rs.SPECIMEN
PROFILES = rs.PROFILES
CONFIG_KEYS = ("url", "token_url", "client_id", "client_secret_file", "token_file")
DX_OUTPUTS = (("uaf", "Rs-Cn.md"), ("dodaf202", "SV-6.md"), ("naf4", "P3.md"))
STAMP_PREFIX = "Chart: "
ATTRIBUTION_PREFIX = "built on OpenDDIL"
NOT_MEASURED = "Declared, not measured"
PHASES_OUTPUTS = (("uaf", "St-Rm-P.md"), ("dodaf202", "CV-3.md"), ("naf4", "Cr.md"))
MEASURED_EVIDENCE = re.compile(r"\d{4}-\d{2}-\d{2}, lab [A-Z], ")

WHY = rs.missing_input()
if WHY:
    print(f"SKIP specimen tests: {WHY}", file=sys.stderr)


def read_lf(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def without_chart_stamp(text: str) -> list[str]:
    """Lines without the two that carry the chart version: the stamp and the attribution."""
    return [ln for ln in text.split("\n")
            if not ln.startswith((STAMP_PREFIX, ATTRIBUTION_PREFIX))]


def tree(root: Path) -> dict[str, Path]:
    return {p.relative_to(root).as_posix(): p for p in sorted(root.rglob("*")) if p.is_file()}


def first_difference(want: Path, got: Path) -> str | None:
    """Compare two trees; return a sentence naming the first difference, or None."""
    a, b = tree(want), tree(got)
    for name in sorted(set(a) | set(b)):
        if name not in b:
            return f"{name}: in the specimen, not in a fresh render"
        if name not in a:
            return f"{name}: in a fresh render, not in the specimen"
        x, y = without_chart_stamp(read_lf(a[name])), without_chart_stamp(read_lf(b[name]))
        if x != y:
            for i in range(max(len(x), len(y))):
                lx = x[i] if i < len(x) else "<end of file>"
                ly = y[i] if i < len(y) else "<end of file>"
                if lx != ly:
                    return f"{name} line {i + 1}: specimen has {lx!r}, fresh render has {ly!r}"
    return None


ARTIFACT_VOCABULARY = {"owning_tier", "label"}


def collect_config_values(twin: dict) -> list[str]:
    """Values the twin sets as connection and credential configuration."""
    out: list[str] = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in CONFIG_KEYS and isinstance(v, str):
                    out.append(v)
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    def strings(o):
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            # A tier and a classification are vocabulary the views carry.
            for k, v in o.items():
                if k not in ARTIFACT_VOCABULARY:
                    strings(v)
        elif isinstance(o, list):
            for v in o:
                strings(v)

    eg = twin.get("egress") or {}
    for side in ("forwarder", "intake"):
        walk((eg.get(side) or {}).get("config"))
    for path in (("forwarder", "tokenSecret"), ("credentials", "existingSecret"),
                 ("trust", "caConfigMap")):
        v = eg.get(path[0], {}).get(path[1]) if isinstance(eg.get(path[0]), dict) else None
        if isinstance(v, str):
            out.append(v)
    strings((eg.get("stubSink") or {}).get("artifacts"))
    return sorted(set(out))


def occurrences(root: Path, values: list[str]) -> list[tuple[str, str]]:
    """Every (file, value) where a value appears in a file under root."""
    hits = []
    for name, path in tree(root).items():
        text = read_lf(path)
        hits += [(name, v) for v in values if v in text]
    return hits


@unittest.skipIf(WHY, WHY or "")
class Specimen(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.twin = yaml.safe_load(rs.TWIN.read_text(encoding="utf-8"))

    def test_specimen_matches_a_fresh_render(self):
        # Links in the views are relative to the output directory, so the fresh
        # render goes to a sibling of specimen/ at the same depth.
        fresh = rs.ARCH / f".specimen-fresh-{os.getpid()}"
        self.addCleanup(shutil.rmtree, fresh, True)
        err = rs.render_all(fresh)
        self.assertIsNone(err, err)
        for prof in PROFILES:
            self.assertTrue((SPECIMEN / prof).is_dir(), f"specimen/{prof} is missing")
        diff = first_difference(SPECIMEN, fresh)
        self.assertIsNone(diff, f"specimen is out of date, first difference in {diff}\n"
                                f"refresh it with: {rs.REFRESH_COMMAND}")

    def test_config_fields_stay_out_of_the_views(self):
        values = collect_config_values(self.twin)
        self.assertTrue(values, "the twin yielded no configuration values to look for")
        hits = occurrences(SPECIMEN, values)
        self.assertEqual(hits, [], "configuration values found in the specimen: "
                         + "; ".join(f"{f} contains {v!r}" for f, v in hits))

    def test_carried_fields_are_in_the_views(self):
        sv6 = read_lf(SPECIMEN / "dodaf202" / "SV-6.md")
        for want in ("system:depot-ledger", "FaultEvent", "Depot ledger"):
            self.assertIn(want, sv6)
        values = collect_config_values(self.twin)
        self.assertTrue(values)
        copy = self.tmp / "copy"
        shutil.copytree(SPECIMEN, copy)
        (copy / "naf4" / "planted.md").write_text(f"planted {values[0]}\n", encoding="utf-8")
        self.assertIn(("naf4/planted.md", values[0]), occurrences(copy, values))

    def test_specimen_states_what_it_is(self):
        for prof, name in DX_OUTPUTS:
            self.assertIn(NOT_MEASURED, read_lf(SPECIMEN / prof / name), f"{prof}/{name}")

    def test_every_file_leads_with_the_twins_system_name(self):
        name = self.twin["system"]["name"]
        self.assertTrue(isinstance(name, str) and name.strip(), "the twin names no system")
        for rel, path in tree(SPECIMEN).items():
            first = read_lf(path).split("\n")[0]
            self.assertTrue(first.startswith(f"# {name}: "), f"{rel}: {first!r}")

    def test_every_file_has_the_attribution_once(self):
        for rel, path in tree(SPECIMEN).items():
            lines = [ln for ln in read_lf(path).split("\n") if ln.startswith(ATTRIBUTION_PREFIX)]
            self.assertEqual(len(lines), 1, f"{rel}: {lines}")

    def test_the_framework_name_is_only_in_the_attribution_and_the_package(self):
        for rel, path in tree(SPECIMEN).items():
            for ln in read_lf(path).split("\n"):
                if "OpenDDIL" in ln:
                    self.assertTrue(ln.startswith(ATTRIBUTION_PREFIX) or "package OpenDDIL" in ln,
                                    f"{rel}: {ln!r}")

    def phase_rows(self, prof, name):
        """The capability table rows of a phases output, as lists of cells."""
        rows = []
        for ln in read_lf(SPECIMEN / prof / name).split("\n"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", ln.strip().strip("|"))]
            if ln.startswith("| ") and len(cells) == 7 and cells[0] != "Capability":
                rows.append(cells)
        return rows

    def test_phases_have_one_row_per_capability_with_computed_evidence(self):
        model = (rs.ARCH / "model" / "openddil.sysml").read_text(encoding="utf-8")
        names = list(cp.model_capabilities(model))
        self.assertTrue(names)
        for prof, name in PHASES_OUTPUTS:
            text = read_lf(SPECIMEN / prof / name)
            rows = self.phase_rows(prof, name)
            self.assertEqual([r[0] for r in rows], names, f"{prof}/{name}")
            for r in rows:
                self.assertIn(r[2], cp.PHASES, f"{prof}/{name}: {r[0]}")
                if r[2] == "measured":
                    self.assertRegex(r[3], MEASURED_EVIDENCE, f"{prof}/{name}: {r[0]}")
                else:
                    self.assertEqual(r[3], cp.NOT_MEASURED, f"{prof}/{name}: {r[0]}")
            self.assertIn("{{slot:increment-dates}}", text, f"{prof}/{name}")

    def test_line_endings_are_lf(self):
        for name, path in tree(SPECIMEN).items():
            self.assertNotIn(b"\r", path.read_bytes(), name)


if __name__ == "__main__":
    unittest.main()
