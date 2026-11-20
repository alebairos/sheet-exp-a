"""Unit tests for src/functions/math/criteria.py, beyond check a5_b3.

Every expected value is LibreOffice Calc's (headless, wildcards on, regular
expressions off) over the same cells: A1:A10 hold 1, 10, the text "10", the
empty text "", TRUE, FALSE, "apple", a blank, #DIV/0! and the text "TRUE".
"""

import unittest

from src.eval import evaluate
from src.values import to_json

BOOK = {"sheets": {"Sheet1": {
    "A1": 1, "A2": 10, "A3": "10", "A4": "", "A5": True, "A6": False, "A7": "apple",
    "A9": {"error": "#DIV/0!"}, "A10": "TRUE",
}}}
E = lambda c: {"error": c}  # noqa: E731

CALC = [
    ('=COUNTIF(A1:A10,"1*")', 4),
    ('=COUNTIF(A1:A10,"")', 2),
    ('=COUNTIF(A1:A10,"<>")', 9),
    ('=COUNTIF(A1:A10,C1)', 1),
    ('=COUNTIF(A1:A10,"TRUE")', 3),
    ('=COUNTIF(A1:A10,"true")', 3),
    ('=COUNTIF(A1:A10,"=TRUE")', 3),
    ('=COUNTIF(A1:A10,"<>TRUE")', 7),
    ('=COUNTIF(A1:A10,"FALSE")', 1),
    ('=COUNTIF(A1:A10,">5")', 1),
    ('=COUNTIF(A1:A10,"<>10")', 8),
    ('=COUNTIF(A1:A10,"=")', 1),
    ('=COUNTIF(A1:A10,">a")', 2),
    ('=COUNTIF(A1:A10,"*")', 9),
    ('=COUNTIF(A1:A8,"*")', 7),
    ('=COUNTIF(A1:A10,"<>*")', 1),
    ('=COUNTIF(A1:A10,"t*")', 1),
    ('=COUNTIF(A1:A10,"T*")', 1),
    ('=COUNTIF(A1:A10,"tr?e")', 1),
    ('=COUNTIF(A1:A10,"1")', 2),
    ('=COUNTIF(A1:A10,"=1.0")', 2),
    ('=COUNTIF(A1:A10," 1")', 2),
    ('=COUNTIF(A1:A10,"  10  ")', 1),
    ('=COUNTIF(A1:A10,"$10")', 1),
    ('=COUNTIF(A1:A10,"10%")', 0),
    ('=COUNTIF(A1:A10,"1E1")', 1),
    ('=COUNTIF(A1:A10,"=10")', 2),
    ('=COUNTIF(A1:A10,"#DIV/0!")', 1),
    ('=COUNTIF(A9,"#div/0!")', 1),
    ('=COUNTIF(A9,"<>")', 1),
    ('=COUNTIF(A9,"<>1")', 1),
    ('=COUNTIF(A4,"=")', 0),
    ('=COUNTIF(A4,"")', 1),
    ('=COUNTIF(A8,"")', 1),
    ('=COUNTIF(A1:A10,"a?ple*")', 1),
    ('=COUNTIF(A1:A10,"~a*")', 1),
    ('=COUNTIF(A1:A10,"(apple)")', 0),
    ('=COUNTIF(A1:A10,".*")', 0),
    ('=COUNTIF(A1:A10,"APPLE")', 1),
    ('=COUNTIF(A1:A10,"<>APPLE")', 9),
    ('=COUNTIF(A1:A10,"<>1*")', 6),
    ('=COUNTIF(A1:A10,">=a*")', 2),
    ('=COUNTIF(A1:A10,"<1")', 1),
    ('=COUNTIF(A1:A10,">=0")', 4),
    ('=COUNTIF(A1:A10,"<z")', 4),
    ('=COUNTIF(A1:A10,"<")', 0),
    ('=COUNTIF(A1:A10,">")', 3),
    ('=COUNTIF(A1:A10,"<=")', 1),
    ('=COUNTIF(A1:A10,0)', 1),
    ('=COUNTIF(A1:A10,"0")', 1),
    ('=COUNTIF(A1:A10,TRUE)', 2),
    ('=COUNTIF(A1:A10,1/0)', E("#DIV/0!")),
    ('=COUNTIF(A1:A10,"abc*",1)', E("Err:504")),
    ('=COUNTIF(5,5)', E("Err:504")),
    ('=SUMIF(A1:A10,"<>apple",A1:A10)', E("#DIV/0!")),
    ('=SUMIF(A1:A10,"*",A1:A10)', E("#DIV/0!")),
    ('=SUMIF(A2:A3,10,A9:A10)', E("#DIV/0!")),
    ('=SUMIF(A1:A10,">0",A2)', 10),
    ('=SUMIF(A1:A10,"1*")', 12),
    ('=SUMIF(A1:A10,"apple",A1:A10)', 0),
    ('=AVERAGEIF(A1:A8,"*",A1:A8)', 3),
    ('=AVERAGEIF(A1:A10,"apple")', E("#DIV/0!")),
]


class CriteriaLikeCalcTest(unittest.TestCase):
    def test_calc_answers(self):
        for formula, want in CALC:
            with self.subTest(formula=formula):
                self.assertEqual(to_json(evaluate(formula, BOOK, "Sheet1")), want)



# Calc adds SUMIF/AVERAGEIF's matches with its KahanSum, as SUM does; LibreOffice headless
# on these cells gives every value below (math.fsum would give 2.8E-17 for the first).
SUMS = {"sheets": {"S": {
    "A1": 0.1, "A2": 0.2, "A3": -0.3, "B1": 1e-17, "B2": 0.7, "B3": 0.1,
    "C1": 1e308, "C2": 1e308, "C3": -1e308, "D1": 1e308, "D2": -1e308, "D3": 1e308,
}}}

CALC_SUMS = [
    ('=SUMIF(A1:A3,"<>")', 0),
    ('=AVERAGEIF(A1:A3,"<>")', 0),
    ('=SUMIF(A1:B3,"<>")', 0.8),
    ('=AVERAGEIF(A1:B3,"<>")', 0.13333333333333333),
    ('=SUMIF(B1:B3,"<>",A1)', 0),
    ('=SUMIF(C1:C3,"<>")', E("#NUM!")),
    ('=AVERAGEIF(C1:C3,"<>")', E("#NUM!")),
    ('=SUMIF(D1:D3,"<>")', 1e308),
]


class SumsLikeCalcTest(unittest.TestCase):
    def test_calc_sums(self):
        for formula, want in CALC_SUMS:
            with self.subTest(formula=formula):
                self.assertEqual(to_json(evaluate(formula, SUMS, "S")), want)


if __name__ == "__main__":
    unittest.main()
