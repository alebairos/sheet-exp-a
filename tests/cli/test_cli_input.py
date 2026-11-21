"""./engine on bad input and on references typed as users type them (a-v1-cli-input).

Bad input (malformed JSON, a file that is JSON but not a workbook, a missing file, a directory) gives
one plain line on stderr, nothing on stdout and a non-zero exit, never a Python traceback. Output is
strict JSON. Cell keys and --cell references are read regardless of case and of `$`, as LibreOffice
Calc reads them; the expected values below are the ones Calc 26.8.1.1 showed for the same workbook
(tests/cli/checks/a_v1_ci_calc.json, from a_v1_ci_probe.py).
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENGINE = os.path.join(ROOT, "engine")
PY_INTERNALS = re.compile(r"Traceback|\b[A-Z][A-Za-z]*(Error|Exception)\b")


def engine(args, stdin=""):
    """Run ./engine as a user does: (exit code, stdout, stderr)."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, ENGINE] + args, input=stdin, capture_output=True, text=True,
                       cwd=ROOT, env=env, timeout=60)
    return p.returncode, p.stdout, p.stderr


def strict(text):
    """JSON as RFC 8259 has it: NaN, Infinity and -Infinity are refused."""
    def no(c):
        raise ValueError("not JSON: " + c)
    return json.loads(text, parse_constant=no)


BAD_STDIN = {
    "malformed JSON": '{"sheets": {',
    "empty input": "",
    "blank input": "  \n",
    "a NaN constant": '{"sheets": {"S": {"A1": NaN}}}',
    "an Infinity constant": '{"sheets": {"S": {"A1": Infinity}}}',
    "a -Infinity constant": '{"sheets": {"S": {"A1": -Infinity}}}',
    "a 1e999 constant": '{"sheets": {"S": {"A1": 1e999}}}',
    "a huge integer": '{"sheets": {"S": {"A1": 1' + "0" * 400 + '}}}',
    "a list": "[]",
    "a number": "3",
    "no sheets": '{"foo": 1}',
    "sheets as a list": '{"sheets": []}',
    "sheets as text": '{"sheets": "Sheet1"}',
    "a sheet as a list": '{"sheets": {"S": []}}',
    "a cell as a list": '{"sheets": {"S": {"A1": [1]}}}',
    "a cell as an object": '{"sheets": {"S": {"A1": {"value": 1}}}}',
    "a key that is not a cell": '{"sheets": {"S": {"total": 1}}}',
    "the same cell twice": '{"sheets": {"S": {"A1": 1, "a1": 2}}}',
}

BOOK = {"sheets": {"Sheet1": {"a2": 5, "A3": "=A2+1", "A4": 1e3, "$B$1": 2, "B2": "=b1*a2",
                              "A5": "=1E308*10", "A6": "=SQRT(-1)"},
                   "My Sheet": {"A1": 7}}}


class BadInputTest(unittest.TestCase):
    def assert_refused(self, what, args, stdin="", says=None):
        code, out, err = engine(args, stdin)
        lines = [l for l in err.splitlines() if l.strip()]
        self.assertNotEqual(code, 0, f"{what}: exit 0")
        self.assertEqual(out.strip(), "", f"{what}: printed on stdout")
        self.assertEqual(len(lines), 1, f"{what}: stderr is not one line: {err!r}")
        self.assertIsNone(PY_INTERNALS.search(err), f"{what}: stderr shows Python internals: {err!r}")
        self.assertTrue(lines[0].startswith("engine: "), f"{what}: {lines[0]!r}")
        if says:
            self.assertIn(says, lines[0], what)
        return lines[0]

    def test_bad_stdin(self):
        for what, text in BAD_STDIN.items():
            with self.subTest(what):
                self.assert_refused(what, ["-"], text)

    def test_malformed_json_says_where(self):
        line = self.assert_refused("malformed", ["-"], '{"sheets": {"S": {"A1": 1,}}}', says="not valid JSON")
        self.assertRegex(line, r"line 1 column \d+")

    def test_files(self):
        with tempfile.TemporaryDirectory() as d:
            missing = os.path.join(d, "missing.json")
            bad = os.path.join(d, "bad.json")
            with open(bad, "w") as f:
                f.write('{"sheets": {')
            notbook = os.path.join(d, "list.json")
            with open(notbook, "w") as f:
                f.write("[1, 2]")
            binary = os.path.join(d, "bin.json")
            with open(binary, "wb") as f:
                f.write(b"\xff\xfe\x00garbage")
            self.assert_refused("a missing file", [missing], says="no such file: " + missing)
            self.assert_refused("a directory", [d], says="directory")
            self.assert_refused("a malformed file", [bad], says="not valid JSON")
            self.assert_refused("a file that is not a workbook", [notbook], says="not a workbook")
            self.assert_refused("a file that is not text", [binary])
            self.assert_refused("a missing file with --cell", [missing, "--cell", "A1"], says="no such file")

    def test_usage_errors_exit_2(self):
        for args in ([], ["a.json", "b.json"], ["-", "--cell"]):
            with self.subTest(args=args):
                code, out, err = engine(args, '{"sheets": {}}')
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("usage: engine", err)

    def test_good_input_is_not_refused(self):
        for book in ({"sheets": {}}, {"sheets": {"S": {}}},
                     {"sheets": {"S": {"A1": None, "A2": True, "A3": "x", "A4": {"error": "#N/A"}}}}):
            with self.subTest(book=book):
                code, out, err = engine(["-"], json.dumps(book))
                self.assertEqual((code, err), (0, ""))
                self.assertEqual(strict(out), book)

    def test_utf8_bom_is_read(self):
        code, out, err = engine(["-"], '﻿{"sheets": {"S": {"A1": "=1+1"}}}')
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(strict(out), {"sheets": {"S": {"A1": 2}}})


class ReferencesTest(unittest.TestCase):
    def run_book(self, args=()):
        code, out, err = engine(["-"] + list(args), json.dumps(BOOK))
        self.assertEqual((code, err), (0, ""), args)
        return strict(out)

    def test_whole_book_is_strict_json_with_cells_as_calc_reads_them(self):
        cells = self.run_book()["sheets"]["Sheet1"]
        self.assertEqual(cells["A2"], 5)
        self.assertNotIn("a2", cells)
        self.assertEqual(cells["A3"], 6)          # Calc: =A2+1 with a2 = 5 shows 6
        self.assertEqual(cells["B1"], 2)          # $B$1 is the cell B1
        self.assertEqual(cells["B2"], 10)         # =b1*a2 reads both
        self.assertEqual(cells["A4"], 1000)       # Calc shows 1000
        self.assertIsInstance(cells["A4"], int)   # printed 1000, not 1000.0
        self.assertIsInstance(cells["A5"], dict)  # overflow is an error value, not Infinity
        self.assertIn("error", cells["A5"])
        self.assertIn("error", cells["A6"])

    def test_cell_references(self):
        for ref, want in [("sheet1!a2", 5), ("SHEET1!$A$3", 6), ("$A$3", 6), ("a3", 6), ("Sheet1!A$4", 1000),
                          ("'my sheet'!a1", 7), ("'My Sheet'!$A$1", 7), ("My Sheet!A1", 7)]:
            with self.subTest(ref=ref):
                self.assertEqual(self.run_book(["--cell", ref]), want)

    def test_unknown_reference_is_ref_error(self):
        for ref in ("Nope!A1", "Sheet1!11", "Sheet1!A0"):
            with self.subTest(ref=ref):
                self.assertEqual(self.run_book(["--cell", ref]), {"error": "#REF!"})

    def test_empty_cell_is_null(self):
        self.assertIsNone(self.run_book(["--cell", "sheet1!z99"]))


if __name__ == "__main__":
    unittest.main()
