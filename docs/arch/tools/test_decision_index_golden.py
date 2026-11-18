"""The kit's check_decision_indexes against this repository's scripts/check-decision-indexes.sh.

Both run on the same temporary copy of decisions/ and scripts/, with this repository's arch-kit.yaml, and must give
identical stdout, stderr and exit code: on the unmodified copy and on a copy broken once for each failure the script
reports. The breaks are made on the copy at test time. The real files, and the real pin script, are never edited.

Needs env ARCH_KIT (the kit checkout) and bash on the PATH. Run from the worktree root:
    python -m unittest discover -s docs/arch/tools -p "test_decision_index_golden.py" -v
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import kit_path  # noqa: F401  (needs env ARCH_KIT; puts the kit on sys.path)

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
KIT = Path(os.environ["ARCH_KIT"]).resolve()
BASH = shutil.which("bash")

ROW = re.compile(r"^\| ([A-Z]{2}-[0-9]{1,2}) \|.*\| ([^|]*) \|$")
STATUS_LINE = re.compile(r"^`Status: .*`$")
HEADING = re.compile(r"^\*\*([A-Z]{2}-[0-9]+) —")


def read(path):
    return path.read_text(encoding="utf-8")


def write(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")


class Tree:
    """A copy of this repository's index inputs, laid out as in the repository."""

    def __init__(self, root):
        self.root = root
        shutil.copytree(REPO / "decisions", root / "decisions")
        shutil.copytree(REPO / "scripts", root / "scripts")
        (root / ".github").mkdir()
        shutil.copy(REPO / ".github" / "invincible-agent.ref", root / ".github" / "invincible-agent.ref")
        (root / "docs" / "arch").mkdir(parents=True)
        shutil.copy(REPO / "docs" / "arch" / "arch-kit.yaml", root / "docs" / "arch" / "arch-kit.yaml")
        self.dec = root / "decisions"

    def index_rows(self):
        lines = read(self.dec / "FOLLOW-UPS.md").split("\n")
        return lines, [i for i, line in enumerate(lines) if ROW.match(line)]

    def delete_a_row(self):
        lines, rows = self.index_rows()
        del lines[rows[0]]
        write(self.dec / "FOLLOW-UPS.md", "\n".join(lines))

    def add_a_phantom_row(self):
        lines, rows = self.index_rows()
        prefix = ROW.match(lines[rows[0]]).group(1).split("-")[0]
        lines.insert(rows[-1] + 1, f"| {prefix}-99 | a row whose id exists nowhere else | open |")
        write(self.dec / "FOLLOW-UPS.md", "\n".join(lines))

    def unindex_a_document(self):
        text = read(self.dec / "README.md")
        assert "PRINCIPLES.md" in text
        write(self.dec / "README.md", text.replace("PRINCIPLES.md", "PRINCIPLES.x"))

    def change_a_status(self):
        lines, rows = self.index_rows()
        i = rows[0]
        lines[i] = lines[i].rsplit("|", 2)[0] + "| not-a-real-status |"
        write(self.dec / "FOLLOW-UPS.md", "\n".join(lines))

    def drop_a_home_token(self):
        indexed = {ROW.match(line).group(1) for line in read(self.dec / "FOLLOW-UPS.md").split("\n")
                   if ROW.match(line)}
        for path in sorted(self.dec.glob("ADR-*.md")):
            lines = read(path).split("\n")
            for i in range(len(lines) - 1):
                if not STATUS_LINE.match(lines[i]):
                    continue
                j = i + 1
                while j < len(lines) and not lines[j].strip():
                    j += 1
                m = HEADING.match(lines[j]) if j < len(lines) else None
                if m and m.group(1) in indexed:
                    del lines[i]
                    write(path, "\n".join(lines))
                    return
        raise AssertionError("no prose home row to drop a token from")

    def add_an_unknown_citation(self):
        write(self.dec / "README.md", read(self.dec / "README.md") + "\nSee zz:ADR-0001.\n")

    def add_an_unresolved_local_citation(self):
        write(self.dec / "README.md", read(self.dec / "README.md") + "\nSee openddil:ADR-9999.\n")

    def fail_the_pin_check(self):
        stub = self.root / "scripts" / "check-iagent-citation-pins.sh"
        write(stub, "#!/usr/bin/env bash\necho 'error: the pin moved' >&2\nexit 1\n")


CASES = [
    ("unmodified", None, 0, "decision indexes clean:"),
    ("a row deleted from the register index", "delete_a_row", 1, "FAIL: register IDs with no row in FOLLOW-UPS.md:"),
    ("a phantom row", "add_a_phantom_row", 1, "FAIL: rows in FOLLOW-UPS.md whose ID exists nowhere else:"),
    ("a document unindexed", "unindex_a_document", 1, "FAIL: documents not referenced by decisions/README.md:"),
    ("a status changed", "change_a_status", 1, "status disagrees"),
    ("a home's token dropped", "drop_a_home_token", 1, "has no declared Status token in its home document"),
    ("an unknown citation prefix", "add_an_unknown_citation", 1,
     "FAIL: cross-repo citations with an unrecognised prefix:"),
    ("an unresolved local citation", "add_an_unresolved_local_citation", 1,
     "FAIL: openddil:-prefixed citations with no matching document here:"),
    ("a failed pin check", "fail_the_pin_check", 1, "FAIL: an iagent citation is not pinned (errors above)"),
]


def run(args, cwd, env):
    p = subprocess.run(args, cwd=cwd, env=env, capture_output=True)
    return p.stdout.decode("utf-8"), p.stderr.decode("utf-8"), p.returncode


@unittest.skipUnless(BASH, "needs bash on the PATH")
class KitToolMatchesTheScript(unittest.TestCase):
    def test_every_case_is_identical(self):
        env = dict(os.environ, PYTHONPATH=str(KIT), PYTHONIOENCODING="utf-8")
        env.pop("ARCH_KIT_CONFIG", None)
        env.pop("PINS_OUT", None)
        table = []
        for name, mutate, rc, fragment in CASES:
            with self.subTest(case=name):
                root = Path(tempfile.mkdtemp())
                self.addCleanup(shutil.rmtree, root, True)
                tree = Tree(root)
                if mutate:
                    getattr(tree, mutate)()
                script = run([BASH, "scripts/check-decision-indexes.sh"], root, env)
                kit = run([sys.executable, "-m", "arch_kit", "--config", "docs/arch/arch-kit.yaml",
                           "check_decision_indexes"], root, env)
                table.append((name, script[2], kit[2]))
                self.assertEqual(script[2], rc, "the script's exit code: " + script[0] + script[1])
                self.assertIn(fragment, script[0] + script[1])
                self.assertEqual(kit[0], script[0], "stdout")
                self.assertEqual(kit[1], script[1], "stderr")
                self.assertEqual(kit[2], script[2], "exit code")
        for name, script_rc, kit_rc in table:
            print(f"  {name}: rc={script_rc} (kit {kit_rc})")


if __name__ == "__main__":
    unittest.main()
