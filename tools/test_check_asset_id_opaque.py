#!/usr/bin/env python3
"""Tests for check_asset_id_opaque.py (ADR-0047)."""
from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import check_asset_id_opaque as tool


def _run(root: pathlib.Path, *extra_args: str) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = tool.main(["--root", str(root), *extra_args])
    return code, buf.getvalue()


def _write(root: pathlib.Path, rel: str, content: str) -> pathlib.Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class PerPatternTests(unittest.TestCase):
    """Each pattern: one line it must catch, one near-miss it must not."""

    def _assert_catches(self, rel: str, line: str, pattern: str):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, rel, line + "\n")
            code, out = _run(root)
            self.assertEqual(code, 1, out)
            self.assertIn(f"[{pattern}]", out, out)

    def _assert_clean(self, rel: str, line: str):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, rel, line + "\n")
            code, out = _run(root)
            self.assertEqual(code, 0, out)
            self.assertIn("findings=0", out)

    def test_method_parse_split(self):
        self._assert_catches("a.py", "site = asset_id.split(':')[1]", "method_parse")

    def test_method_parse_startswith_near_miss_equality(self):
        self._assert_clean("a.py", "if asset_id == x:")

    def test_method_parse_includes_collection_near_miss(self):
        self._assert_clean("a.ts", "if (assetIds.includes(x)) { return; }")

    def test_method_parse_endswith_js(self):
        self._assert_catches("a.ts", "if (selectedAssetId.endsWith('_Sensor')) { x(); }", "method_parse")

    def test_bloblang_parse(self):
        self._assert_catches("a.blobl", 'root.site = this.asset_id.trim_prefix("dis:")', "bloblang_parse")

    def test_bloblang_parse_near_miss_other_field(self):
        self._assert_clean("a.blobl", 'root.site = this.callsign.trim_prefix("x")')

    def test_py_slice(self):
        self._assert_catches("a.py", "tail = asset_id[4:]", "py_slice")

    def test_py_slice_near_miss_other_name(self):
        self._assert_clean("a.py", "tail = other_value[4:]")

    def test_regex_call_py(self):
        self._assert_catches("a.py", "m = re.match(r'dis:(\\d+)', asset_id)", "regex_call")

    def test_regex_call_js(self):
        self._assert_catches("a.ts", "if (/^dis:/.test(assetId)) { go(); }", "regex_call")

    def test_regex_call_js_named_pattern_receiver(self):
        # ASSET_ID_PATTERN.test(param): the id-bearing name is the regex
        # object, not its argument -- calibration found this real site.
        self._assert_catches("a.ts", "if (param && ASSET_ID_PATTERN.test(param)) return param;", "regex_call")

    def test_regex_call_near_miss_no_id(self):
        self._assert_clean("a.py", "m = re.match(r'dis:(\\d+)', other)")

    def test_in_substring(self):
        self._assert_catches("a.py", 'if "edge-03" in asset_id: return True', "in_substring")

    def test_in_substring_near_miss_collection(self):
        self._assert_clean("a.py", "if asset_id in seen_ids: return True")

    def test_in_substring_dotted_chain(self):
        # evt.asset.asset_id: the id-bearing name is the last segment of a
        # dotted chain -- calibration found this real site.
        self._assert_catches("a.py", 'if "9999" in evt.asset.asset_id: return True', "in_substring")

    def test_in_substring_near_miss_dict_value(self):
        self._assert_clean("a.py", 'row = {"id": "dis:1:1:1099"}')

    def test_sql_like(self):
        self._assert_catches("a.sql", "SELECT * FROM t WHERE asset_id LIKE 'dis:%'", "sql_like")

    def test_sql_like_in_shell_heredoc(self):
        self._assert_catches("a.sh", "echo \"SELECT 1 WHERE asset_id LIKE 'dis:%'\"", "sql_like")

    def test_sql_like_near_miss_equality(self):
        self._assert_clean("a.sql", "SELECT * FROM t WHERE asset_id = 'dis:1:1:1099'")

    def test_scheme_literal_wildcard(self):
        self._assert_catches("a.sh", "grep -q 'dis:%' file.txt", "scheme_literal")

    def test_scheme_literal_startswith(self):
        self._assert_catches("a.py", 'ok = asset_id.startswith("dis:")', "scheme_literal")

    def test_scheme_literal_near_miss_construction(self):
        self._assert_clean("a.py", 'asset_id = f"dis:{site}:{app}:{entity}"')

    def test_scheme_literal_near_miss_full_literal_value(self):
        self._assert_clean("a.py", 'row = {"id": "dis:1:1:1099"}')

    def test_shell_cut(self):
        self._assert_catches("a.sh", "site=$(echo \"$asset_id\" | cut -d: -f2)", "shell_cut")

    def test_shell_cut_near_miss_no_id(self):
        self._assert_clean("a.sh", "field=$(echo \"$line\" | cut -d: -f2)")


class AllowlistTests(unittest.TestCase):
    def test_allowlisted_finding_exits_zero(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, "a.py", "tail = asset_id[4:]\n")
            _write(root, ".asset-id-allowlist",
                   "a.py\tasset_id[4:]\tmapper: legacy DIS mapper, pending cleanup\n")
            code, out = _run(root)
            self.assertEqual(code, 0, out)
            self.assertIn("allowlisted=1", out)
            self.assertIn("new=0", out)

    def test_stale_entry_exits_two(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, "a.py", "x = 1\n")
            _write(root, ".asset-id-allowlist",
                   "a.py\tasset_id[4:]\tmapper: nothing matches this anymore\n")
            code, out = _run(root)
            self.assertEqual(code, 2, out)
            self.assertIn("stale=1", out)

    def test_bad_reason_prefix_exits_three(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, "a.py", "tail = asset_id[4:]\n")
            _write(root, ".asset-id-allowlist",
                   "a.py\tasset_id[4:]\tbecause I said so\n")
            code, out = _run(root)
            self.assertEqual(code, 3, out)

    def test_pending_entry_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, "a.py", "tail = asset_id[4:]\n")
            _write(root, ".asset-id-allowlist",
                   "a.py\tasset_id[4:]\tpending: follow-up ticket OPEN-1\n")
            code, out = _run(root)
            self.assertEqual(code, 1, out)
            self.assertIn("PENDING (not allowed): a.py\tasset_id[4:]", out)
            self.assertIn("pending=1", out)

    def test_mapper_entry_for_same_finding_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, "a.py", "tail = asset_id[4:]\n")
            _write(root, ".asset-id-allowlist",
                   "a.py\tasset_id[4:]\tmapper: constructs the id\n")
            code, out = _run(root)
            self.assertEqual(code, 0, out)
            self.assertNotIn("PENDING", out)
            self.assertIn("pending=0", out)

    def test_missing_allowlist_file_is_empty_allowlist(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, "a.py", "x = 1\n")
            code, out = _run(root)
            self.assertEqual(code, 0, out)


class ExitCodeTests(unittest.TestCase):
    def test_empty_tree_exits_three(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            code, out = _run(root)
            self.assertEqual(code, 3, out)
            self.assertIn("files=0", out)

    def test_skipped_dirs_do_not_count(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, "node_modules/vendor.py", "asset_id.split(':')\n")
            code, out = _run(root)
            self.assertEqual(code, 3, out)
            self.assertIn("files=0", out)

    def test_precedence_new_beats_stale(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, "a.py", "tail = asset_id[4:]\n")
            _write(root, "b.py", "other = asset_id[9:]\n")
            _write(root, ".asset-id-allowlist",
                   "a.py\tasset_id[4:]\tmapper: ok\n"
                   "c.py\tasset_id[0:]\tmapper: now stale\n")
            code, out = _run(root)
            # b.py's finding is unallowlisted (new), c.py's entry is stale;
            # new (exit 1) must win per the documented precedence 3>1>2.
            self.assertEqual(code, 1, out)


class SummaryLineTests(unittest.TestCase):
    def test_summary_line_format(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, "a.py", "x = 1\n")
            code, out = _run(root)
            self.assertEqual(code, 0, out)
            last = out.strip().splitlines()[-1]
            self.assertRegex(
                last,
                r"^asset-id-opaque: files=\d+ findings=\d+ allowlisted=\d+ "
                r"new=\d+ stale=\d+ pending=\d+$",
            )

    def test_summary_line_present_on_usage_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            code, out = _run(root)
            self.assertEqual(code, 3)
            last = out.strip().splitlines()[-1]
            self.assertTrue(last.startswith("asset-id-opaque: "))

    def test_self_files_skipped_but_a_copy_is_scanned(self):
        here = pathlib.Path(tool.__file__).resolve().parent
        code, out = _run(here)
        # Only the checker and its test live here: both skipped, so the
        # scan is empty, which is a usage error rather than a pass.
        self.assertEqual(code, 3, out)
        self.assertIn("files=0", out.strip().splitlines()[-1])
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            _write(root, "check_asset_id_opaque.py",
                   pathlib.Path(tool.__file__).read_text(encoding="utf-8"))
            code, out = _run(root)
            self.assertEqual(code, 1, out)

    def test_list_patterns(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = tool.main(["--list-patterns"])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        for pid, _fn, _desc in tool.PATTERNS:
            self.assertIn(pid, out)


if __name__ == "__main__":
    unittest.main()
