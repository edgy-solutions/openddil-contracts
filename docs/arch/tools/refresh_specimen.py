#!/usr/bin/env python3
"""refresh_specimen.py - regenerate docs/arch/specimen/ from the chart and the twin.

Renders every output profile with render_profile.py, using the chart's
`openddil-demo` directory with the bundle's tier-node values and egress twin
layered in that order, into docs/arch/specimen/<profile>/.

Usage:
    python docs/arch/tools/refresh_specimen.py

Takes no arguments. Inputs come from the environment:
    OPENDDIL_REPOS   directory holding openddil-helm (default: the directory
                     that holds this repository)
    OPENDDIL_BUNDLE  bundle root (default: $OPENDDIL_REPOS/openddil-customer-bundle-example)

Exit codes: 0 ok, 2 an input is missing or a render failed. Stdlib only.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCH = HERE.parent
SPECIMEN = ARCH / "specimen"
PROFILES = ("uaf", "dodaf202", "naf4")
REPOS = Path(os.environ.get("OPENDDIL_REPOS", HERE.parents[3]))
CHART = REPOS / "openddil-helm" / "openddil-demo"
BUNDLE_ROOT = Path(os.environ.get("OPENDDIL_BUNDLE", REPOS / "openddil-customer-bundle-example"))
TIER_NODE = BUNDLE_ROOT / "k8s" / "tier-node-values.yaml"
TWIN = BUNDLE_ROOT / "k8s" / "egress-values.yaml"
REFRESH_COMMAND = "python docs/arch/tools/refresh_specimen.py"


def missing_input() -> str | None:
    if shutil.which("helm") is None:
        return "helm is not on PATH"
    for label, p in (("chart", CHART), ("tier-node values", TIER_NODE), ("egress twin", TWIN)):
        if not p.exists():
            return f"{label} missing at {p}"
    return None


def render_profile(profile: str, out: Path) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(HERE / "render_profile.py"), "--profile", profile,
           "--out", str(out), "--chart", str(CHART),
           "--values", str(TIER_NODE), "--values", str(TWIN)]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")


def render_all(root: Path) -> str | None:
    """Render all profiles under root/<profile>; return an error text or None."""
    for prof in PROFILES:
        p = render_profile(prof, root / prof)
        if p.returncode != 0:
            return f"render of {prof} failed (exit {p.returncode}): {p.stderr.strip()[-600:]}"
    return None


def main() -> int:
    why = missing_input()
    if why:
        print(f"error: {why}", file=sys.stderr)
        return 2
    for prof in PROFILES:
        out = SPECIMEN / prof
        p = render_profile(prof, out)
        if p.returncode != 0:
            print(f"error: render of {prof} failed (exit {p.returncode}): "
                  f"{p.stderr.strip()[-600:]}", file=sys.stderr)
            return 2
        n = len(list(out.glob("*.md")))
        print(f"wrote {n} files to {out.relative_to(ARCH.parent.parent).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
