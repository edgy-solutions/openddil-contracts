"""scripts/kit_pin.py: the one arch-kit commit a workflow file pins, or exit 1."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "scripts" / "kit_pin.py"
A = "a" * 40
B = "b" * 40


def uses(sha):
    return f"      - uses: edgy-solutions/arch-kit@{sha} # pin\n        with:\n          config: x\n"


def ref(sha):
    return (f"      - uses: actions/checkout@{'c' * 40}\n        with:\n"
            f"          repository: edgy-solutions/arch-kit\n          ref: {sha} # pin\n          path: arch-kit\n")


class KitPin(unittest.TestCase):
    def run_tool(self, text):
        f = Path(tempfile.mkdtemp()) / "wf.yml"
        f.write_text("jobs:\n  j:\n    steps:\n" + text, encoding="utf-8")
        p = subprocess.run([sys.executable, str(TOOL), str(f)], capture_output=True, text=True)
        return p.returncode, p.stdout, p.stderr

    def test_one_pin_used_twice(self):
        rc, out, err = self.run_tool(uses(A) + ref(A))
        self.assertEqual((rc, out.strip()), (0, A), err)

    def test_two_pins_fail_and_are_named(self):
        rc, out, err = self.run_tool(uses(A) + ref(B))
        self.assertEqual(rc, 1)
        self.assertIn(A, err)
        self.assertIn(B, err)

    def test_no_pin_fails(self):
        rc, out, err = self.run_tool("      - uses: actions/checkout@" + "c" * 40 + "\n")
        self.assertEqual(rc, 1)
        self.assertEqual(out, "")

    def test_other_repositories_refs_are_not_the_kit(self):
        other = ref(B).replace("edgy-solutions/arch-kit", "edgy-solutions/openddil-helm")
        rc, out, err = self.run_tool(uses(A) + other)
        self.assertEqual((rc, out.strip()), (0, A), err)

    def test_an_expression_ref_is_not_a_pin(self):
        expr = ref("${{ steps.pins.outputs.old }}")
        rc, out, err = self.run_tool(uses(A) + expr)
        self.assertEqual((rc, out.strip()), (0, A), err)


if __name__ == "__main__":
    unittest.main()
