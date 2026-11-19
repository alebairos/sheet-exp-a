"""Unit tests for src/functions/logic_text/logic.py (intent a-i6-logic-text, wi 1), beyond the checks.

Every expected value is LibreOffice Calc's, computed headless over the same cells
(A1 = 1, A2 = 0, B1:B2 empty) with the formula outside rows 1-2, so no implicit
intersection applies.
"""

import unittest

from src.eval import evaluate
from src.values import to_json

BOOK = {"sheets": {"S": {"A1": 1, "A2": 0}}}
E = lambda c: {"error": c}  # noqa: E731

CALC = [
    # the wrong number of arguments
    ("=IFERROR(1)", E("Err:511")),
    ("=NOT()", E("Err:511")),
    ("=NOT(1,2)", E("Err:508")),
    ("=NOT(,)", E("Err:508")),
    ("=ISBLANK()", E("Err:511")),
    ("=AND()", E("Err:511")),
    ("=IF()", E("Err:511")),
    ("=IF(1,2,3,4)", E("Err:504")),
    ("=IFERROR(,1)", E("Err:518")),
    # conditions read from text
    ('=IF(" true ",1,2)', 1),
    ('=IF("tRuE",1,2)', 1),
    ('=IF(" 1 ",1,2)', 1),
    ('=IF("+1",1,2)', 1),
    ('=IF(".5",1,2)', 1),
    ('=IF("1E2",1,2)', 1),
    ('=IF("",1,2)', E("#VALUE!")),
    ('=NOT("yes")', E("#VALUE!")),
    # omitted arguments
    ("=AND(,1)", False),
    ("=OR(,0)", False),
    ("=AND(,)", False),
    ("=IF(1,,)", 0),
    ('=AND("")', E("#VALUE!")),
    ('=AND(IF(1,""))', E("#VALUE!")),
    # ranges wider than one cell
    ("=IF(A1:A2,1,2)", E("#VALUE!")),
    ("=IF(TRUE,A1:A2)", E("#VALUE!")),
    ("=ISBLANK(A1:A2)", False),
    ("=ISBLANK(B1:B2)", False),
    ("=ISERROR(A1:A2)", True),
    ("=ISNUMBER(A1:A2)", False),
    ("=ISTEXT(A1:A2)", False),
    ('=IFERROR(A1:A2,"e")', "e"),
]


class LogicLikeCalcTest(unittest.TestCase):
    def test_calc_answers(self):
        for formula, want in CALC:
            with self.subTest(formula=formula):
                self.assertEqual(to_json(evaluate(formula, BOOK, "S")), want)

    def test_if_hands_back_the_reference(self):
        self.assertTrue(to_json(evaluate("=ISBLANK(IF(1,B1))", BOOK, "S")))
        self.assertTrue(to_json(evaluate("=ISBLANK(IF(0,1,B1))", BOOK, "S")))
        self.assertTrue(to_json(evaluate("=ISBLANK(IFERROR(B1,0))", BOOK, "S")))
        self.assertTrue(to_json(evaluate("=ISBLANK(IFERROR(1/0,B1))", BOOK, "S")))


if __name__ == "__main__":
    unittest.main()
