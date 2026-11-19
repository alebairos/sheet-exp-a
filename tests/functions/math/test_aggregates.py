"""Unit tests for src/functions/math/aggregates.py, beyond check a5_b1.

Every expected value is LibreOffice Calc's (headless, 26.x) for the same formula.
"""

import unittest

from src.eval import evaluate
from src.values import to_json

BOOK = {"sheets": {"Sheet1": {"A1": 1, "B1": 2, "A2": 3, "B2": "t", "C1": True,
                              "D1": {"error": "#N/A"}, "D2": {"error": "#DIV/0!"}}}}
E = lambda c: {"error": c}  # noqa: E731


def ev(formula):
    return to_json(evaluate(formula, BOOK, "Sheet1"))


class SumLikeCalcTest(unittest.TestCase):
    def test_near_cancelling_sums_are_zero(self):
        self.assertEqual(ev("=SUM(0.1,0.2,-0.3)"), 0)
        self.assertEqual(ev("=SUM(1,-1,1E-17)"), 0)
        self.assertEqual(ev("=SUM(1E10,-1E10,1E-7)"), 0)
        self.assertEqual(ev("=AVERAGE(1,-1,1E-17)"), 0)

    def test_order_matters_as_in_calc(self):
        self.assertEqual(ev("=SUM(1E-17,1,-1)"), 1e-17)
        self.assertEqual(ev("=SUM(0.1,0.2)"), 0.30000000000000004)
        self.assertEqual(ev("=SUM(0.1,0.2,0.3)"), 0.6)

    def test_overflow_is_num(self):
        self.assertEqual(ev("=SUM(1E308,1E308)"), E("#NUM!"))
        self.assertEqual(ev("=AVERAGE(1E308,1E308)"), E("#NUM!"))
        self.assertEqual(ev("=PRODUCT(1E200,1E200)"), E("#NUM!"))
        self.assertEqual(ev("=STDEV(1E308,-1E308)"), E("#NUM!"))


class OmittedArgumentTest(unittest.TestCase):
    def test_omitted_is_zero(self):
        self.assertEqual(ev("=SUM(1,,2)"), 3)
        self.assertEqual(ev("=AVERAGE(1,,2)"), 1)
        self.assertEqual(ev("=MIN(1,,2)"), 0)
        self.assertEqual(ev("=MEDIAN(1,,3)"), 1)
        self.assertEqual(ev("=COUNT(1,,2)"), 3)
        self.assertEqual(ev("=COUNTA(,)"), 2)


class ErrorOrderTest(unittest.TestCase):
    def test_first_error_wins(self):
        self.assertEqual(ev("=SUM(D2,D1)"), E("#DIV/0!"))
        self.assertEqual(ev("=SUM(D1,1/0)"), E("#N/A"))
        self.assertEqual(ev("=SUM(D1:D2)"), E("#N/A"))

    def test_error_beats_text(self):
        self.assertEqual(ev("=MIN(\"x\",1/0)"), E("#DIV/0!"))
        self.assertEqual(ev("=MIN(1/0,\"x\")"), E("#DIV/0!"))


class RangeTest(unittest.TestCase):
    def test_two_dimensional_range(self):
        self.assertEqual(ev("=SUM(A1:C2)"), 7)
        self.assertEqual(ev("=COUNT(A1:C2)"), 4)
        self.assertEqual(ev("=COUNTA(A1:C2)"), 5)
        self.assertEqual(ev("=MAX(A1:C2)"), 3)

    def test_reversed_corners(self):
        self.assertEqual(ev("=SUM(C2:A1)"), 7)


if __name__ == "__main__":
    unittest.main()
