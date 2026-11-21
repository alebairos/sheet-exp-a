"""Unit tests for src.recalc (intent a-i4-recalc), beyond the plan's checks."""

import copy
import json
import os
import subprocess
import sys
import unittest

from src.recalc import Workbook, compute

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CYC = {"error": "Err:522"}


def sheet(cells, **more):
    return compute({"sheets": {"S": cells, **more}})["sheets"]["S"]


class Order(unittest.TestCase):
    def test_range_over_formulas_is_read_after_them(self):
        got = sheet({"B1": "=A1:A3", "C1": "=A2:A2*10", "A2": "=A3+1", "A3": "=1+1", "B2": "=A1:A3*2", "B5": "=A1:A3"})
        self.assertEqual(got["C1"], 30)
        # A 3-cell range where one value is expected takes the cell in the formula's row, as Calc does
        # (implicit intersection, a-v1-eval-edges): A1 is blank, A2 is computed first; row 5 is outside.
        self.assertEqual(got["B1"], 0)
        self.assertEqual(got["B2"], 6)
        self.assertEqual(got["B5"], {"error": "#VALUE!"})

    def test_output_keeps_input_order_and_constants(self):
        book = {"sheets": {"S": {"B2": "=A1*2", "A1": 1.5, "Z1": {"error": "#N/A"}, "T": "x"}}}
        before = copy.deepcopy(book)
        out = compute(book)
        self.assertEqual(list(out["sheets"]["S"]), ["B2", "A1", "Z1", "T"])
        self.assertEqual(out["sheets"]["S"], {"B2": 3, "A1": 1.5, "Z1": {"error": "#N/A"}, "T": "x"})
        self.assertEqual(book, before)

    def test_a_formula_that_does_not_parse_is_value_error(self):
        self.assertEqual(sheet({"A1": "=1+", "A2": "=A1+1"}), {"A1": {"error": "#VALUE!"}, "A2": {"error": "#VALUE!"}})

    def test_bad_input_is_an_empty_workbook(self):
        self.assertEqual(compute({}), {"sheets": {}})
        self.assertEqual(compute([]), {"sheets": {}})


class Cycles(unittest.TestCase):
    def test_a_range_that_holds_its_own_cell(self):
        got = sheet({"A1": 1, "A2": "=A1:A3", "A3": 3, "B1": "=A2+1"})
        self.assertEqual(got["A2"], CYC)
        self.assertEqual(got["B1"], CYC)

    def test_the_cycle_error_flows_as_any_error(self):
        # As LibreOffice, 1/0+A1 is #DIV/0! even when A1 is circular. (LibreOffice also gives
        # #DIV/0! for A1+1/0, where the evaluator's leftmost error wins: not pinned here.)
        got = sheet({"A1": "=B1", "B1": "=A1", "C1": "=1/0+A1", "E1": "=A1&\"t\""})
        self.assertEqual(got["C1"], {"error": "#DIV/0!"})
        self.assertEqual(got["E1"], CYC)

    def test_two_cycles_joined_by_a_reader(self):
        got = sheet({"A1": "=A2", "A2": "=A1", "B1": "=B2", "B2": "=B1", "C1": "=A1+B1", "D1": 4, "D2": "=D1"})
        self.assertEqual([got[a] for a in ("A1", "A2", "B1", "B2", "C1")], [CYC] * 5)
        self.assertEqual(got["D2"], 4)


class CalcCycleOrder(unittest.TestCase):
    """A self-reference through a branch not taken computes (a-v1-eval-edges): Calc evaluates a cycle's
    formulas by address (sheet, column, row), computes a precedent of the cycle when it is read, and
    gives Err:522 to a read of a formula still being computed."""

    def test_untaken_branches_are_not_read(self):
        got = sheet({"A1": "=IF(TRUE,1,A1)", "A2": "=IF(FALSE,A2)", "A3": "=IFERROR(A3,7)", "A4": "=IF(TRUE,A4)",
                     "B1": "=IF(1,2,1/0)", "B2": "=IFERROR(1,NOPE())", "B3": "=IF(TRUE,)", "B4": "=IF(\"x\",1,B4)"})
        self.assertEqual([got[a] for a in ("A1", "A2", "A3", "A4")], [1, False, 7, CYC])
        self.assertEqual([got[a] for a in ("B1", "B2", "B3")], [2, 1, 0])
        self.assertEqual(got["B4"], {"error": "#VALUE!"})  # a text condition: no branch is taken

    def test_the_first_by_address_starts_and_keeps_what_it_gets(self):
        # B1 starts (column B before C), reads C1 on demand, and C1 reads B1 still being computed.
        got = sheet({"C1": "=B1", "B1": "=IFERROR(C1,0)"})
        self.assertEqual((got["B1"], got["C1"]), (0, CYC))
        # Here the reader of the guard starts, so both get 0.
        got = sheet({"C1": "=IFERROR(B1,0)", "B1": "=C1"})
        self.assertEqual((got["B1"], got["C1"]), (0, 0))

    def test_a_long_guarded_cycle_does_not_recurse(self):
        n = 10000
        cells = {f"A{i}": f"=A{i + 1}+1" for i in range(1, n)}
        cells[f"A{n}"] = "=IFERROR(A1,0)"
        got = sheet(cells)
        self.assertEqual((got["A1"], got[f"A{n - 1}"], got[f"A{n}"]), (n - 1, 1, 0))
        plain = sheet({**{f"A{i}": f"=A{i + 1}" for i in range(1, n)}, f"A{n}": "=A1"})
        self.assertEqual(set(map(json.dumps, plain.values())), {json.dumps(CYC)})

    def test_a_range_read_inside_a_cycle(self):
        got = sheet({"B1": "=SUM(A1:A3)", "A1": 1, "A2": "=IF(A1>5,B1,2)", "A3": "=IFERROR(B1,10)"})
        self.assertEqual(got, {"B1": CYC, "A1": 1, "A2": 2, "A3": 10})

    def test_sheets_in_book_order(self):
        out = compute({"sheets": {"P": {"A1": "=Q!A1"}, "Q": {"A1": "=IFERROR(P!A1,3)"}}})["sheets"]
        self.assertEqual((out["P"]["A1"], out["Q"]["A1"]), (3, 3))

    def test_edits_make_and_break_the_cycle(self):
        wb = Workbook({"sheets": {"S": {"A1": "=IF(C1,B1,1)", "B1": "=A1+1", "C1": False}}})
        self.assertEqual((wb.value("S", "A1"), wb.value("S", "B1")), (1, 2))
        wb.set("S", "C1", True)
        self.assertEqual((wb.value("S", "A1"), wb.value("S", "B1")), (CYC, CYC))
        wb.set("S", "C1", False)
        self.assertEqual((wb.value("S", "A1"), wb.value("S", "B1")), (1, 2))


class Edits(unittest.TestCase):
    def test_set_on_a_new_sheet_resolves_references_to_it(self):
        wb = Workbook({"sheets": {"S": {"A1": "=New!A1+1"}}})
        self.assertEqual(wb.computed()["sheets"]["S"]["A1"], {"error": "#REF!"})
        wb.set("New", "A1", 41)
        self.assertEqual(wb.computed()["sheets"]["S"]["A1"], 42)
        self.assertEqual(wb.computed()["sheets"]["New"], {"A1": 41})

    def test_an_edit_inside_a_range_on_another_sheet(self):
        wb = Workbook({"sheets": {"S": {"A1": "=T!B2:B2+1"}, "T": {}}})
        self.assertEqual(wb.set("T", "B2", 5), {("S", "A1")})
        self.assertEqual(wb.value("S", "A1"), 6)
        self.assertEqual(wb.set("T", "C2", 5), set())

    def test_blanking_a_formula_frees_its_readers(self):
        wb = Workbook({"sheets": {"S": {"A1": "=A1", "B1": "=A1+1"}}})
        self.assertEqual(wb.value("S", "B1"), CYC)
        self.assertEqual(wb.set("S", "A1", None), {("S", "B1")})
        self.assertEqual(wb.computed()["sheets"]["S"], {"B1": 1})


class Cli(unittest.TestCase):
    def test_engine_computes_and_prints_one_cell(self):
        book = {"sheets": {"Sheet1": {"A2": "=A1*3", "A1": 2}}}
        p = subprocess.run([sys.executable, os.path.join(ROOT, "engine"), "-", "--cell", "Sheet1!A2"],
                           input=json.dumps(book), capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(p.stdout), 6)


if __name__ == "__main__":
    unittest.main()
