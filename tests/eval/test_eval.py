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
    def test_unparseable_formula_is_calcs_error_value(self):
        # Calc's codes (plan a-v1-parse-fidelity, run in LibreOffice Calc 26.8.1.1): ending where an
        # operand is expected is Err:520 at top level and Err:511 inside an open '('.
        for f, code in [("=1+", "Err:520"), ("=(", "Err:511"), ("=SUM(1,", "Err:511")]:
            self.assertEqual(ev(f), E(code), f)

    def test_separator_after_an_operator_is_a_missing_variable(self):
        # LibreOffice Calc 26.8 (the a-v1-parse-fidelity reviewer's UNO run): a ',' right after an
        # operator is Err:511; one that opens the expression is Err:509.
        for f in ["=1+,", "=1+,2", "=1*,", "=1&,", "=-,", "=(1+,", "=SUM(1+,2)", "=SUM(-,1)", "=SUM(1,2+,3)",
                  "=IF(1>,2,3)"]:
            self.assertEqual(ev(f), E("Err:511"), f)
        for f in ["=,1", "=(,1)"]:
            self.assertEqual(ev(f), E("Err:509"), f)

    def test_a_list_in_a_group_is_calcs_code(self):
        # LibreOffice Calc 26.8.1.1 over UNO (attempt 3's probe): inside a bracket group ',' and ';'
        # separate a list. Ending after one, where an operand is expected, is Err:511; a whole list is
        # Err:509, but only when nothing later is malformed (that later code wins).
        for f in ["=(2,", "=(2;", "=(2,,", "=((2,", "=SUM((2,", "=SUM(1,(2,", "=1+(2,", "=IF((1,", "=(,",
                  "=SUM((2,,", "=(1+2,", "=(A1,", "=((2),", "=(2,(", "=(2,-", "=(2,+", "=((1,2),",
                  "=SUM((2,3),", "=SUM((2,3)+", "=(2,3)+("]:
            self.assertEqual(ev(f), E("Err:511"), f)
        for f in ["=(2,3)", "=(2,)", "=(1,2", "=(2,3", "=SUM((2,3))", "=SUM(1,(2,3)", "=(2,,3", "=(,)",
                  "=(2,3)4", "=(2,3)+1", "=1+(2,3)", "=-(2,3)", "=((1,2)"]:
            self.assertEqual(ev(f), E("Err:509"), f)
        for f, code in [("=(2,3)+", "Err:520"), ("=(2,)+", "Err:520"), ("=(2,3)*/2", "Err:510"),
                        ("=(2,*3)", "Err:510"), ("=(1,2))", "Err:508")]:
            self.assertEqual(ev(f), E(code), f)

    def test_what_follows_a_range_colon(self):
        # LibreOffice Calc 26.8.1.1 (attempt 3's probe): Calc reads the operand after ':' on.
        for f, want in [("=A1:(2,", E("Err:511")), ("=A1:(", E("Err:511")), ("=A1:(1+", E("Err:511")),
                        ("=A1:-A2", E("Err:520")), ("=A1:-", E("Err:520")), ("=A1:+", E("Err:520")),
                        ("=A1:(2)+", E("Err:520")), ("=A1:*2", E("Err:510")), ("=A1:2", E("Err:502")),
                        ("=A1:(2)", E("Err:502")), ("=A1:\"x\"", E("Err:502")), ("=A1:SUM(1", E("Err:502")),
                        ("=A1:(2,3)", E("Err:502")), ("=A1:B", E("#NAME?"))]:
            self.assertEqual(ev(f), want, f)

    def test_ranges_after_colon_compute(self):
        book = {"sheets": {"Sheet1": {"A1": 1, "A2": 2}}}
        for f in ["=SUM(A1:(A2", "=SUM(A1:(A2))", "=SUM(A1:+A2)"]:
            self.assertEqual(to_json(evaluate(f, book, "Sheet1")), 3, f)

    def test_empty_stdev_is_div0_as_in_calc(self):
        # LibreOffice Calc 26.8.1.1: =STDEV() and =STDEV( are #DIV/0!, not Err:511.
        for f in ["=STDEV()", "=STDEV("]:
            self.assertEqual(ev(f), E("#DIV/0!"), f)

    def test_missing_final_parenthesis_is_closed_as_in_calc(self):
        self.assertEqual(ev("=SUM(1"), 1)
        self.assertEqual(ev("=(1+2"), 3)


if __name__ == "__main__":
    unittest.main()
