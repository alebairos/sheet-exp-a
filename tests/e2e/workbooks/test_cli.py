"""End to end: three realistic workbooks computed through the engine CLI, every cell compared with LibreOffice Calc.

A household budget (Summary, Income, Expenses), a grade sheet (Grades, Scale) and an order sheet (Orders,
Catalog). Each workbook is books/<name>.json; books/<name>.calc.json holds what LibreOffice Calc (headless)
computed for every cell of the same workbook. Numbers match within 1e-9 relative; text, booleans and errors
match exactly.
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
NAMES = ["budget", "grades", "orders"]

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


def bodies(book):
    """Formula bodies with string literals removed, upper-cased."""
    return [re.sub(r'"[^"]*"', "", f).upper() for f in formulas(book)]


class WorkbookCliTest(unittest.TestCase):
    def check(self, name, sheets):
        book, calc = load(name + ".json"), load(name + ".calc.json")
        self.assertEqual(list(book["sheets"]), sheets)
        self.assertEqual(set(calc["sheets"]), set(book["sheets"]))
        for sheet, cells in book["sheets"].items():
            self.assertEqual(set(calc["sheets"][sheet]), set(cells), "%s!: Calc's answers cover every cell" % sheet)
        got = compute(book)
        bad = []
        for sheet, cells in calc["sheets"].items():
            for addr, want in cells.items():
                g = got.get("sheets", {}).get(sheet, {}).get(addr)
                if not same(g, want):
                    bad.append("%s!%s %s: Calc %s, engine %s" % (sheet, addr, book["sheets"][sheet][addr],
                                                                json.dumps(want), json.dumps(g)))
        self.assertEqual(bad, [], "%s: %d cells differ from Calc" % (name, len(bad)))
        self.assertTrue(any("!" in b for b in bodies(book)), "%s: no cross-sheet formula" % name)
        return book

    def test_budget_matches_calc(self):
        """A household budget: a Summary reading Income and Expenses."""
        self.check("budget", ["Summary", "Income", "Expenses"])

    def test_grades_matches_calc(self):
        """A grade sheet: Grades looking letters up in a Scale."""
        self.check("grades", ["Grades", "Scale"])

    def test_orders_matches_calc(self):
        """An order sheet: Orders pricing lines from a product Catalog."""
        self.check("orders", ["Orders", "Catalog"])

    def test_workbooks_use_every_spec_function(self):
        """Between them the three workbooks call all 40 of SPEC's functions."""
        named = {fn for n in NAMES for b in bodies(load(n + ".json"))
                 for fn in FUNCTIONS if re.search(r"(?<![A-Z0-9_.])%s\s*\(" % fn, b)}
        self.assertEqual(sorted(set(FUNCTIONS) - named), [])


if __name__ == "__main__":
    unittest.main()
