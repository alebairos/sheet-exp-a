"""Calc's evaluation edges: implicit intersection and self-references through untaken branches.

Implicit intersection: a range where one value is expected (an operator's operand, unary minus, a cell's value)
takes the cell in the formula's own row (one-column range) or column (one-row range), also from another sheet;
otherwise it is #VALUE!. Functions still receive the whole range (=SUM(C2:C3)).

Untaken branches: IF evaluates only the branch it takes and IFERROR its fallback only on an error, so a cell that
refers to itself only through a branch not taken computes. Inside a real cycle Calc evaluates cells column by
column, then row by row; a read of a cell still being computed is Err:522 to that read.

Expected values are not written by hand: BOOK and CALC are copied from tests/eval/checks/a_v1_ee_calc.json, the
output of LibreOffice Calc 26.8.1.1 run headless by a_v1_ee_probe.py.
"""

import unittest

from src.cli import compute

BOOK = {'Data': {'C2': 3,
          'C3': 4,
          'B1': 10,
          'C1': 20,
          'D1': 30,
          'G2': '=C2:C3',
          'G3': '=C2:C3*2',
          'G5': '=C2:C3',
          'C7': '=B1:D1',
          'E7': '=B1:D1+1',
          'F2': '=B2:C3',
          'G4': '=SUM(C2:C3)',
          'G6': '=-C2:C3',
          'H3': '=C2:C3&"x"',
          'H2': '=IF(C2:C3>3,"big","small")',
          'I3': '=C2:C3=4',
          'D7': '=B1:D1*C2:C3'},
 'T': {'A2': '=Data!C2:C3', 'A1': '=Data!G2', 'A3': '=Data!C2:C3', 'B5': '=Data!B1:D1'},
 'Cyc': {'A16': '=IF(TRUE,1,A16)',
         'B7': '=IF(FALSE,B7,2)',
         'B8': '=IFERROR(B9,0)',
         'B9': '=B8',
         'C8': '=C9',
         'C9': '=IFERROR(C8,0)',
         'D2': 0,
         'D1': '=IF(D2>0,D1,5)',
         'D3': '=IF(D2=0,D3,5)',
         'E1': '=E2+1',
         'E2': '=E1',
         'F1': '=IFERROR(F1,7)',
         'G1': '=A16+1',
         'H1': '=IF(H2,1,2)',
         'H2': '=H1>0',
         'J2': '=IFERROR(K1,0)',
         'K1': '=J2',
         'L2': '=IFERROR(L1,0)',
         'L1': '=L2',
         'N1': '=IFERROR(M2,0)',
         'M2': '=N1'}}

CALC = {'Data': {'G2': {'number': 3.0},
          'G3': {'number': 8.0},
          'G5': {'error': '#VALUE!'},
          'C7': {'number': 20.0},
          'E7': {'error': '#VALUE!'},
          'F2': {'error': '#VALUE!'},
          'G4': {'number': 7.0},
          'G6': {'error': '#VALUE!'},
          'H3': {'text': '4x'},
          'H2': {'text': 'small'},
          'I3': {'bool': True},
          'D7': {'error': '#VALUE!'}},
 'T': {'A2': {'number': 3.0}, 'A1': {'number': 3.0}, 'A3': {'number': 4.0}, 'B5': {'number': 10.0}},
 'Cyc': {'A16': {'number': 1.0},
         'B7': {'number': 2.0},
         'B8': {'number': 0.0},
         'B9': {'error': 'Err:522'},
         'C8': {'number': 0.0},
         'C9': {'number': 0.0},
         'D1': {'number': 5.0},
         'D3': {'error': 'Err:522'},
         'E1': {'error': 'Err:522'},
         'E2': {'error': 'Err:522'},
         'F1': {'number': 7.0},
         'G1': {'number': 2.0},
         'H1': {'error': 'Err:522'},
         'H2': {'error': 'Err:522'},
         'J2': {'number': 0.0},
         'K1': {'error': 'Err:522'},
         'L2': {'number': 0.0},
         'L1': {'number': 0.0},
         'N1': {'number': 0.0},
         'M2': {'number': 0.0}}}


def _matches(got, want):
    if "number" in want:
        return isinstance(got, (int, float)) and not isinstance(got, bool) and abs(got - want["number"]) <= 1e-9
    if "bool" in want:
        return got is want["bool"]
    if "text" in want:
        return got == want["text"]
    return got == {"error": want["error"]}


class _CalcCase(unittest.TestCase):
    SHEETS = ()

    @classmethod
    def setUpClass(cls):
        cls.out = compute({"sheets": BOOK})["sheets"]

    def _check(self, sheet, refs=None):
        for ref, want in CALC[sheet].items():
            if refs is None or ref in refs:
                got = self.out[sheet].get(ref)
                self.assertTrue(_matches(got, want), "%s!%s %s gives %r, Calc gives %r"
                                % (sheet, ref, BOOK[sheet][ref], got, want))


class ImplicitIntersectionTest(_CalcCase):
    def test_one_column_range_takes_the_formula_row(self):
        self._check("Data", {"G2", "G3", "G5", "G6", "H3", "I3"})

    def test_one_row_range_takes_the_formula_column(self):
        self._check("Data", {"C7", "E7"})

    def test_two_dimensional_range_is_value_error(self):
        self._check("Data", {"F2", "D7"})

    def test_inside_an_operator_in_a_function_argument(self):
        self._check("Data", {"H2"})

    def test_functions_still_receive_the_range(self):
        self._check("Data", {"G4"})

    def test_range_on_another_sheet(self):
        self._check("T")


class UntakenBranchTest(_CalcCase):
    def test_if_with_self_reference_in_untaken_branch(self):
        self._check("Cyc", {"A16", "B7", "D1", "D3", "G1", "H1", "H2"})

    def test_iferror_fallback_on_self_reference(self):
        self._check("Cyc", {"F1", "B8", "B9", "C8", "C9"})

    def test_cycle_order_is_column_then_row(self):
        self._check("Cyc", {"J2", "K1", "L1", "L2", "M2", "N1"})

    def test_plain_cycle_stays_err_522(self):
        self._check("Cyc", {"E1", "E2"})


class LongCycleTest(unittest.TestCase):
    def test_long_guarded_cycle_does_not_overflow(self):
        # a-i4's lesson: evaluation inside a cycle must not recurse per cell. A1 reads A2, ..., A5000 reads A1.
        n = 5000
        cells = {"A%d" % i: "=A%d" % (i + 1) for i in range(1, n)}
        cells["A%d" % n] = "=IFERROR(A1,0)"
        out = compute({"sheets": {"S": cells}})["sheets"]["S"]
        self.assertEqual(len(out), n)
        for v in out.values():
            self.assertTrue(v == {"error": "Err:522"} or v == 0, v)


if __name__ == "__main__":
    unittest.main()
