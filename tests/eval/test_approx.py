"""Formulas compare, add and subtract decimals the way LibreOffice Calc does (a-v1-decimal-noise).

Every expected value here comes from running LibreOffice Calc 26.8.1.1 headless
(tests/eval/checks/a_v1_dn_probe.py wrote tests/eval/checks/a_v1_dn_calc.json); none is written from memory.
The cases are run through the evaluator (src.cli.compute) and through ./engine as a user runs it."""

import json
import os
import subprocess
import sys
import unittest

from src.cli import compute

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
with open(os.path.join(ROOT, "tests", "eval", "checks", "a_v1_dn_calc.json")) as fh:
    CALC = json.load(fh)
CASES = CALC["cases"]
BUDGET = CALC["budget"]


def book():
    """Calc's probe sheets: Cases (A1.. the formulas; B1 =0.1+0.2 and B2 0.3, which some read) and Budget."""
    cells = {"B1": "=0.1+0.2", "B2": 0.3}
    cells.update({"A%d" % (i + 1): c["formula"] for i, c in enumerate(CASES)})
    return {"sheets": {"Cases": cells, "Budget": BUDGET["book"]}}


def one(formula):
    return compute({"sheets": {"S": {"A1": formula}}})["sheets"]["S"]["A1"]


class CalcComparisonTest(unittest.TestCase):
    """Comparisons of nearly equal decimals give Calc's TRUE and FALSE."""

    def test_point_one_plus_point_two_equals_point_three(self):
        self.assertIs(one("=0.1+0.2=0.3"), True)
        self.assertIs(one("=0.1+0.2<>0.3"), False)
        self.assertEqual(one('=IF(0.1+0.2=0.3,"same","different")'), "same")

    def test_just_past_2_pow_minus_48_stays_unequal(self):
        # Calc: =1=1+1E-15 is TRUE (inside 2**-48), =1=1+1E-14 is FALSE (past it).
        self.assertIs(one("=1=1+1E-15"), True)
        self.assertIs(one("=1=1+1E-14"), False)

    def test_every_calc_comparison(self):
        out = compute(book())["sheets"]["Cases"]
        n = 0
        for i, c in enumerate(CASES):
            if "bool" in c:
                n += 1
                self.assertIs(out["A%d" % (i + 1)], c["bool"], c["formula"])
            elif "text" in c:
                n += 1
                self.assertEqual(out["A%d" % (i + 1)], c["text"], c["formula"])
        self.assertGreaterEqual(n, 10)


class CalcSubtractionTest(unittest.TestCase):
    """Subtracting nearly equal decimals gives Calc's 0; real differences are kept."""

    def test_noise_subtracts_to_zero(self):
        self.assertEqual(one("=(0.1+0.2)-0.3"), 0)
        self.assertEqual(one("=1.1*3-3.3"), 0)

    def test_real_difference_past_2_pow_minus_48_is_kept(self):
        self.assertEqual(one("=(1+1E-14)-1"), 9.992007221626409e-15)

    def test_every_calc_number_as_stored(self):
        # The evaluator keeps the double Calc stores (=0.1+0.2 is 0.30000000000000004 inside, as in Calc).
        from src.recalc import Workbook
        wb = Workbook(book())
        n = 0
        for i, c in enumerate(CASES):
            if "number" in c:
                n += 1
                self.assertEqual(wb.value("Cases", "A%d" % (i + 1)), float(c["number"]), c["formula"])
        self.assertEqual(wb.value("Budget", "B5"), float(BUDGET["B5"]["number"]))
        self.assertGreaterEqual(n, 10)


class EnginePrintsAsCalcTest(unittest.TestCase):
    """./engine prints numbers as Calc reports them: 0.3, 3.3, -34.52, not binary float noise."""

    @classmethod
    def setUpClass(cls):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "engine"), "-"], input=json.dumps(book()),
                           capture_output=True, text=True, cwd=ROOT,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=60)
        if p.returncode != 0:
            raise AssertionError("./engine exited %d: %s" % (p.returncode, p.stderr[-300:]))
        cls.text = p.stdout
        cls.out = json.loads(p.stdout)["sheets"]

    def test_review_cases(self):
        cases = self.out["Cases"]
        by_formula = {c["formula"]: "A%d" % (i + 1) for i, c in enumerate(CASES)}
        self.assertEqual(cases[by_formula["=0.1+0.2"]], 0.3)
        self.assertEqual(cases[by_formula["=1.1*3"]], 3.3)
        self.assertEqual(self.out["Budget"]["B5"], -34.52)
        for noise in ("0.30000000000000004", "3.3000000000000003", "-34.51999999999998"):
            self.assertNotIn(noise, self.text)

    def test_every_calc_number_as_shown(self):
        cases = self.out["Cases"]
        for i, c in enumerate(CASES):
            if "number" in c:
                self.assertEqual(cases["A%d" % (i + 1)], float(c["shown"]), c["formula"])
        self.assertEqual(self.out["Budget"]["B5"], float(BUDGET["B5"]["shown"]))


if __name__ == "__main__":
    unittest.main()
