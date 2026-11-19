"""Unit tests for src.eval: operators, references, errors and function calls."""

import unittest

from src.eval import Range, evaluate
from src.functions import register
from src.values import from_json, to_json

BOOK = {"sheets": {
    "Sheet1": {"A1": 5, "A2": "3", "A3": True, "B1": {"error": "#N/A"}, "C1": "=1+1"},
    "Data Two": {"B2": 7, "C3": 8},
}}
E = lambda c: {"error": c}  # noqa: E731


def ev(formula, sheet="Sheet1"):
    return to_json(evaluate(formula, BOOK, sheet))


class OperatorTest(unittest.TestCase):
    def test_arithmetic(self):
        self.assertEqual(ev("=7-2*3"), 1)
        self.assertEqual(ev("=10/4"), 2.5)
        self.assertEqual(ev("=-A1"), -5)

    def test_power_like_calc(self):
        self.assertEqual(ev("=0^0"), 1)
        self.assertEqual(ev("=0^-1"), E("#NUM!"))
        self.assertEqual(ev("=(-8)^(1/3)"), -2)
        self.assertEqual(ev("=(-8)^(-1/3)"), -0.5)
        self.assertEqual(ev("=(-8)^0.5"), E("#NUM!"))
        self.assertEqual(ev("=(-8)^(2/3)"), E("#NUM!"))
        self.assertEqual(ev("=(-2)^3"), -8)
        self.assertEqual(ev("=10^400"), E("#NUM!"))

    def test_overflow_is_num(self):
        self.assertEqual(ev("=1E300*1E300"), E("#NUM!"))

    def test_concat_bool_as_number(self):
        self.assertEqual(ev("=FALSE&\"\""), "0")
        self.assertEqual(ev("=A3&A3"), "11")

    def test_comparison_returns_bool(self):
        self.assertIs(ev("=A1>4"), True)
        self.assertIs(ev("=A2=\"3\""), True)


class ReferenceTest(unittest.TestCase):
    def test_blank_reference_is_zero(self):
        self.assertEqual(ev("=Z99"), 0)

    def test_formula_cell_read_as_it_stands(self):
        self.assertEqual(ev("=C1"), "=1+1")

    def test_quoted_and_case_insensitive_sheet(self):
        self.assertEqual(ev("='Data Two'!B2+1"), 8)
        self.assertEqual(ev("='data two'!B2"), 7)

    def test_other_sheet_relative_to_own(self):
        self.assertEqual(ev("=B2", sheet="Data Two"), 7)

    def test_unknown_sheet_is_ref(self):
        self.assertEqual(ev("=Nope!A1"), E("#REF!"))

    def test_range_corners_normalised(self):
        r = Range(BOOK, "Data Two", 3, 3, 2, 2)
        self.assertEqual([to_json(v) for v in r.values()], [7, None, None, 8])
        self.assertEqual((r.rows, r.cols), (2, 2))

    def test_multi_cell_range_in_operator(self):
        self.assertEqual(ev("=-A1:A2"), E("#VALUE!"))
        self.assertEqual(ev("=A1:A1*2"), 10)


class CallTest(unittest.TestCase):
    def test_missing_argument_is_blank(self):
        seen = {}

        @register("ZZTESTMISSING")
        def _f(*args):
            seen["args"] = [to_json(a) for a in args]
            return from_json(1)

        evaluate("=ZZTESTMISSING(1,,2)", BOOK, "Sheet1")
        self.assertEqual(seen["args"], [1, None, 2])

    def test_registered_late_is_found(self):
        self.assertEqual(ev("=ZZTESTLATE()"), E("#NAME?"))

        @register("ZZTESTLATE")
        def _f():
            return from_json("late")

        self.assertEqual(ev("=zztestlate()"), "late")

    def test_function_returning_range_collapses(self):
        @register("ZZTESTRANGE")
        def _f(r):
            return r

        self.assertEqual(ev("=ZZTESTRANGE(A1)+1"), 6)
        self.assertEqual(ev("=ZZTESTRANGE(A1:A2)"), E("#VALUE!"))

    def test_unknown_function_does_not_evaluate_args(self):
        calls = []

        @register("ZZTESTSIDE")
        def _f():
            calls.append(1)
            return from_json(0)

        self.assertEqual(ev("=NOPE(ZZTESTSIDE())"), E("#NAME?"))
        self.assertEqual(calls, [])


class MalformedTest(unittest.TestCase):
    def test_unparseable_formula_is_an_error_value(self):
        for f in ["=1+", "=(", "=SUM(1"]:
            self.assertEqual(ev(f), E("#VALUE!"), f)


if __name__ == "__main__":
    unittest.main()
