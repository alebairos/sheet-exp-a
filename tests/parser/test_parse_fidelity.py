"""Formulas typed the way people type them, and broken ones, give what LibreOffice Calc gives.

Intent a-v1-parse-fidelity. Every expected value is Calc's own, recorded by running LibreOffice Calc
26.8.1.1 headless (parse_fidelity_calc.json, which says how): spaces around tokens, a sheet on both
ends of a range and a missing final parenthesis compute; malformed formulas give Calc's Err:508,
509, 510, 511 or 520; out-of-range numbers Err:502; calls with no arguments Err:511 or Calc's empty
value. Each formula is computed alone in Sheet1!C1 next to the recorded data, through the engine's
compute (what ./engine prints).
"""

import json
import os
import re
import unittest

from src.cli import compute

HERE = os.path.dirname(os.path.abspath(__file__))
CALC = json.load(open(os.path.join(HERE, "parse_fidelity_calc.json"), encoding="utf-8"))

EMPTY_CALL = re.compile(r"^=[A-Z]+\(\)?$")
PARSE_CODES = {"Err:508", "Err:509", "Err:510", "Err:511", "Err:520"}


def computed(formula):
    book = {"sheets": {name: dict(cells) for name, cells in CALC["data"].items()}}
    book["sheets"]["Sheet1"]["C1"] = formula
    return compute(book)["sheets"]["Sheet1"].get("C1")


def calc_value(case):
    if "error" in case:
        return {"error": case["error"]}
    return case["text"] if "text" in case else case["number"]


def cases(pick):
    return [c for c in CALC["cases"] if pick(c)]


class ParseFidelity(unittest.TestCase):
    def check(self, picked):
        self.assertTrue(picked, "no recorded cases picked")
        for c in picked:
            with self.subTest(formula=c["formula"]):
                got, want = computed(c["formula"]), calc_value(c)
                if "number" in c:
                    self.assertIsInstance(got, (int, float))
                    self.assertNotIsInstance(got, bool)
                    self.assertAlmostEqual(got, want, delta=1e-9)
                else:
                    self.assertEqual(got, want)

    def test_formulas_calc_accepts_compute(self):
        # = SUM( A1 : A2 ) is 3, =SUM(S2!A1:S2!A2) 7, =SUM(1,2 3, =SUM(A1:+A2) 3 ...
        self.check(cases(lambda c: "error" not in c and not EMPTY_CALL.match(c["formula"])))

    def test_malformed_formulas_give_calcs_code(self):
        # =(1+ Err:511, =1+ Err:520, =1+*2 Err:510, =1 2 Err:509, =1+2) Err:508, =(2,3) Err:509 ...
        self.check(cases(lambda c: c.get("error") in PARSE_CODES and not EMPTY_CALL.match(c["formula"])))

    def test_out_of_range_numbers_are_err502(self):
        self.check(cases(lambda c: re.search(r"[0-9][eE][-+]?[0-9]{3}", c["formula"]) is not None))

    def test_empty_calls_as_in_calc(self):
        # =MAX() Err:511, =SUM() 0, =AVERAGE() and =STDEV() #DIV/0!, =CONCATENATE() "" ...
        self.check(cases(lambda c: EMPTY_CALL.match(c["formula"])))

    def test_every_recorded_case(self):
        self.check(CALC["cases"])


if __name__ == "__main__":
    unittest.main()
