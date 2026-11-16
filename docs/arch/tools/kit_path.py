"""Put the export kit's tools on sys.path and point them at this repository's declaration.

Needs env ARCH_KIT: the kit checkout root.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_KIT = os.environ.get("ARCH_KIT")
if not _KIT:
    raise SystemExit("kit_path: env ARCH_KIT is not set; point it at the arch-kit checkout")

TOOLS = Path(_KIT).resolve() / "arch_kit" / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(1, str(TOOLS))
os.environ.setdefault("ARCH_KIT_CONFIG", str(Path(__file__).resolve().parent.parent / "arch-kit.yaml"))
