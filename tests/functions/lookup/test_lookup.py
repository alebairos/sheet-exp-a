"""Unit tests for src/functions/lookup/lookup.py, beyond checks a7_b1 and a7_b2.

Every expected value is LibreOffice Calc's (headless) over the same cells:
A1:A10 hold 1, 5, 2, "3", "30", TRUE, "b", "a", "c", 30 (unsorted on purpose).
"""

import unittest

from src.eval import evaluate
from src.values import to_json

BOOK = {"sheets": {"Sheet1": {
    "A1": 1, "A2": 5, "A3": 2, "A4": "3", "A5": "30", "A6": True,
    "A7": "b", "A8": "a", "A9": "c", "A10": 30,
}}}
E = lambda c: {"error": c}  # noqa: E731

CALC = [
    ("=MATCH(3,A1:A3,1)", 1),          # stops at the first key above the value
    ("=MATCH(4,A1:A3,1)", 1),
    ("=MATCH(6,A1:A3,1)", 3),
    ("=MATCH(1.5,A1:A3,1)", 1),
    ("=MATCH(\"3\",A4,0)", 1),
    ("=MATCH(3,A4,0)", E("#N/A")),     # a number never finds numeric text
    ("=MATCH(\"30\",A5:A10,0)", 1),    # numeric text finds the text first
    ("=MATCH(30,A5:A10,0)", 6),
    ("=MATCH(TRUE,A1:A6,0)", 1),       # TRUE is the number 1
    ("=MATCH(\"bb\",A7:A9,1)", 2),
    ("=MATCH(\"b\",A7:A9,1)", 1),      # an equal key ends the scan
    ("=MATCH(5,A1:A3,-1)", 2),
    ("=MATCH(3,A1:A3,-1)", E("#N/A")),
    ("=VLOOKUP(5,A1:A3,1,)", 5),       # an omitted mode is exact
    ("=VLOOKUP(4,A1:A3,1,)", E("#N/A")),
    ("=MATCH(B1,A1:A10,0)", E("#N/A")),  # a blank finds nothing
    ("=MATCH(\"\",A1:A10,0)", E("#N/A")),
    ("=MATCH(2,A1:A10,1)", 1),
    ("=MATCH(100,A1:A10,1)", 10),      # text cells are skipped by a number
    ("=MATCH(\"3\",A1:A10,1)", 4),
    ("=INDEX(A1:A3,,1)", E("#VALUE!")),
    ("=INDEX(A1:A3)", E("#VALUE!")),
    ("=INDEX(A2,1)", 5),
    ("=INDEX(A2,1,1)", 5),
    ("=INDEX(A2,2)", E("#REF!")),
]


class LookupLikeCalcTest(unittest.TestCase):
    def test_calc_answers(self):
        for formula, want in CALC:
            with self.subTest(formula=formula):
                self.assertEqual(to_json(evaluate(formula, BOOK, "Sheet1")), want)

    def test_index_returns_a_reference(self):
        from src.eval import Range
        from src.functions import registry
        from src.values import Number
        r = registry()["INDEX"](Range(BOOK, "Sheet1", 1, 1, 10, 1), Number(2))
        self.assertIsInstance(r, Range)
        self.assertEqual((r.top, r.left, r.bottom, r.right), (2, 1, 2, 1))


if __name__ == "__main__":
    unittest.main()
