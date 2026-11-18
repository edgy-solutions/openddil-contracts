"""The consumer's declaration (docs/arch/arch-kit.yaml) against the literals it replaced.

The literals are written here as they stood in the kit at 5f0a595.
Run from the worktree root:
    python -m unittest discover -s docs/arch/tools -p "test_*.py"
"""
import unittest

import kit_path  # noqa: F401  (puts the kit on sys.path, sets ARCH_KIT_CONFIG)
import declared
import project

TOOL = "test_arch_kit_declaration"

PHASES = ["measured", "built unmeasured", "accepted design", "proposed", "row"]
FLOOR_PHASES = ("measured", "built unmeasured")
NOT_REQUIRED = ("superseded", "rejected", "deprecated", "withdrawn")
REQUIRED_DODAF = ["OV-1", "OV-2", "OV-5a", "OV-5b", "SV-1", "SV-2", "SV-4", "SV-6", "StdV-1", "DIV-2", "CV-2"]
REQUIRED_VIEWS = ["Op-Cn", "Rs-Sr", "Rs-If", "Sc-Sr", "Sd-Tx", "St-Rm-P", "Rs-Tr"]
CAP_NAME_VIEWS = ["St-Tx", "St-Rm-P"]
PHASES_HOME = "St-Rm-P"
HOMES = {"dependencies": "St-Cn", "taxonomy": "Rs-Tx", "dictionary": "Am-If", "trace": "Am-Tr",
         "severed-behaviour": "St-Tx"}


class DeclarationMatchesLiterals(unittest.TestCase):
    def test_portal(self):
        self.assertEqual(declared.portal_hosting(TOOL), "ci-artifact")
        self.assertEqual(declared.portal_audience(TOOL), "public")

    def test_phases(self):
        got = declared.phases(TOOL)
        self.assertEqual([p.name for p in got], PHASES)
        self.assertEqual([p.badge for p in got], ["m", "b", "a", "p", "r"])
        self.assertEqual([[k if r is None else {k: r} for k, r in p.when] for p in got],
                         [["measured"], ["built"], [{"status": "Accepted"}],
                          [{"status": "Proposed"}, "still-open", "pending"], ["rows"]])

    def test_floor(self):
        self.assertEqual(tuple(declared.floor_phases(TOOL)), FLOOR_PHASES)

    def test_statuses(self):
        st = declared.statuses(TOOL)
        self.assertEqual([s.lead for s in st if not s.in_force], list(NOT_REQUIRED))
        self.assertEqual([s.lead for s in st if s.in_force], ["accepted", "proposed"])
        self.assertEqual([s.word for s in st if s.in_force], ["Accepted", "Proposed"])
        self.assertEqual([s.word for s in st if s.sources_check], ["Proposed"])

    def test_views(self):
        v = declared.views(TOOL)
        self.assertEqual(v["required"], REQUIRED_VIEWS)
        self.assertEqual(v["required_dodaf"], REQUIRED_DODAF)
        self.assertEqual(v["capability_links"], CAP_NAME_VIEWS)
        self.assertEqual(v["homes"].get("capability-phases"), PHASES_HOME)
        for name, view in HOMES.items():
            self.assertEqual(v["homes"].get(name), view, name)

    def test_phase_column_and_browser(self):
        self.assertEqual(project.need("labels.phase.column", TOOL), "Phase")
        b = project.need("export.browser", TOOL)
        self.assertEqual(b["views"], {"table": "Rs-Cn", "diagram": "Op-Tx", "profile_only": "Sc-Sr"})
        self.assertEqual(b["search"], {"phrase": "Which resource talks to which", "finds": "Rs-Cn"})
        self.assertEqual((b["min_pages"], b["min_tables"], b["min_tokens"]), (30, 30, 1000))


if __name__ == "__main__":
    unittest.main()
