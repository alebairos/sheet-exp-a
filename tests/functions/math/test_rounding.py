"""Unit tests for src/functions/math/rounding.py (intent a-i5-math, wi 2), beyond the check."""

import unittest

from src.eval import evaluate
from src.values import to_json

BOOK = {"sheets": {"S": {"A1": 2.5, "A2": "7", "A3": True, "B1": 1, "B2": 2}}}


def ev(formula):
    return to_json(evaluate(formula, BOOK, "S"))


class Rounding(unittest.TestCase):
    def test_on_the_shown_value(self):
        self.assertEqual(ev("=ROUND(0.285,2)"), 0.29)       # 0.28499999999999998 in binary
        self.assertEqual(ev("=ROUNDDOWN(0.1*3,1)"), 0.3)
        self.assertEqual(ev("=INT(2.9999999999999996)"), 3)

    def test_extreme_digit_counts(self):
        self.assertEqual(ev("=ROUND(123.456,400)"), 123.456)
        self.assertEqual(ev("=ROUND(1E300,-400)"), 0)
        self.assertEqual(ev("=ROUNDUP(-2.5,-1E10)"), 0)
        self.assertEqual(ev("=ROUND(-0.0001,2)"), 0)

    def test_references_and_coercion(self):
        self.assertEqual(ev("=ROUND(A1)"), 3)
        self.assertEqual(ev("=ROUND(A1:A1,0)"), 3)
        self.assertEqual(ev("=ROUND(B1:B2,0)"), {"error": "#VALUE!"})  # more than one cell
        self.assertEqual(ev("=MOD(A2,A3+1)"), 1)
        self.assertEqual(ev("=ABS(-A3)"), 1)

    def test_the_leftmost_error_wins(self):
        self.assertEqual(ev("=ROUND(\"x\",1/0)"), {"error": "#VALUE!"})
        self.assertEqual(ev("=POWER(1/0,\"x\")"), {"error": "#DIV/0!"})


class Mod(unittest.TestCase):
    def test_decimal_divisors_have_no_noise(self):
        for f in ("=MOD(0.3,0.1)", "=MOD(1,0.1)", "=MOD(-0.3,0.1)", "=MOD(1E20,3)"):
            self.assertEqual(ev(f), 0, f)
        self.assertAlmostEqual(ev("=MOD(0.35,0.1)"), 0.05)

    def test_the_divisors_sign(self):
        self.assertEqual(ev("=MOD(-7,2.5)"), 0.5)
        self.assertEqual(ev("=MOD(7,-2.5)"), -0.5)


class PowerAndSqrt(unittest.TestCase):
    def test_power_is_the_operator(self):
        for a, b in (("2", "0.5"), ("-27", "1/3"), ("0", "0"), ("-4", "0.5"), ("1E200", "2")):
            self.assertEqual(ev("=POWER(%s,%s)" % (a, b)), ev("=(%s)^(%s)" % (a, b)), (a, b))

    def test_sqrt(self):
        self.assertEqual(ev("=SQRT(-0.0001)"), {"error": "Err:502"})
        self.assertEqual(ev("=SQRT(A3)"), 1)


if __name__ == "__main__":
    unittest.main()
