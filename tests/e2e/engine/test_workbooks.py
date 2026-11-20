"""End to end: whole workbooks computed through the engine CLI, every cell compared with LibreOffice Calc.

Each workbook is books/<name>.json; books/<name>.calc.json holds what LibreOffice Calc (headless) computed for
every cell of the same workbook. Numbers match within 1e-9 relative; text, booleans and errors match exactly.
"""
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ENGINE = os.path.join(ROOT, "engine")
BOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "books")

FUNCTIONS = """SUM AVERAGE MIN MAX COUNT COUNTA ROUND ROUNDUP ROUNDDOWN INT MOD ABS POWER SQRT PRODUCT SUMIF
COUNTIF AVERAGEIF MEDIAN STDEV IF IFERROR AND OR NOT ISBLANK ISNUMBER ISTEXT ISERROR CONCATENATE LEFT RIGHT MID
LEN UPPER LOWER TRIM VLOOKUP INDEX MATCH""".split()


def load(name):
    with open(os.path.join(BOOKS, name), encoding="utf-8") as f:
        return json.load(f)


def compute(book):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, ENGINE, "-"], input=json.dumps(book), capture_output=True,
                       text=True, env=env, timeout=120)
    if p.returncode:
        raise AssertionError("the engine CLI exited %d: %s" % (p.returncode, p.stderr.strip()[-300:]))
    return json.loads(p.stdout)


def same(got, want):
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    if num(got) and num(want):
        return abs(got - want) <= 1e-9 * max(1.0, abs(want))
    return type(got) is type(want) and got == want


def formulas(book):
    return [v for cells in book["sheets"].values() for v in cells.values()
            if isinstance(v, str) and v.startswith("=")]


class WorkbookTest(unittest.TestCase):
    def check(self, name):
        book, calc = load(name + ".json"), load(name + ".calc.json")
        got = compute(book)
        bad = []
        for sheet, cells in calc["sheets"].items():
            for addr, want in cells.items():
                g = got.get("sheets", {}).get(sheet, {}).get(addr)
                if not same(g, want):
                    bad.append("%s!%s %s: Calc %s, engine %s" % (sheet, addr, book["sheets"][sheet][addr],
                                                                json.dumps(want), json.dumps(g)))
        self.assertEqual(bad, [], "%s: %d cells differ from Calc" % (name, len(bad)))
        return book, calc

    def test_mixed_workbook_matches_calc(self):
        """Data, Summary and Calc sheets reading each other, all 40 SPEC functions together."""
        book, _ = self.check("mixed")
        self.assertGreaterEqual(len(book["sheets"]), 2)
        bodies = [re.sub(r'"[^"]*"', "", f).upper() for f in formulas(book)]
        self.assertTrue(any("!" in b for b in bodies), "no cross-sheet formula")
        named = {fn for fn in FUNCTIONS for b in bodies if re.search(r"(?<![A-Z0-9_.])%s\s*\(" % fn, b)}
        self.assertEqual(sorted(set(FUNCTIONS) - named), [])

    def test_chain_workbook_matches_calc(self):
        """100-formula chains: #DIV/0! through a chain and SUM, #N/A through text, a chain written bottom-up."""
        book, calc = self.check("chain")
        self.assertGreaterEqual(len(formulas(book)), 100)
        errors = {v["error"] for cells in calc["sheets"].values() for v in cells.values()
                  if isinstance(v, dict) and "error" in v}
        self.assertTrue({"#DIV/0!", "#N/A"} <= errors, errors)


if __name__ == "__main__":
    unittest.main()
