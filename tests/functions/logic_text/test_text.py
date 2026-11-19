"""Unit tests for the text functions (src/functions/logic_text/text.py)."""

import unittest

from src.eval import evaluate
from src.values import to_json

BOOK = {"sheets": {"Sheet1": {
    "A1": 1, "A2": True, "A3": "  a   b  ", "A4": {"error": "#N/A"},
    "A5": 2.5, "A6": "straße", "B1": "x", "B2": "y",
}}}
E = lambda c: {"error": c}  # noqa: E731


def ev(formula):
    return to_json(evaluate(formula, BOOK, "Sheet1"))


class ConcatenateTest(unittest.TestCase):
    def test_joins_text_numbers_and_booleans(self):
        self.assertEqual(ev('=CONCATENATE("a",A1,A2,A5)'), "a112.5")

    def test_blank_and_missing_are_empty(self):
        self.assertEqual(ev('=CONCATENATE(Z9,"x",,"y")'), "xy")

    def test_first_error_wins(self):
        self.assertEqual(ev('=CONCATENATE("x",A4,1/0)'), E("#N/A"))


class LeftRightMidTest(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(ev('=LEFT("hello",2)'), "he")
        self.assertEqual(ev('=LEFT("hello")'), "h")
        self.assertEqual(ev('=RIGHT("hello",3)'), "llo")
        self.assertEqual(ev('=RIGHT("hello",0)'), "")
        self.assertEqual(ev('=RIGHT("hi",9)'), "hi")
        self.assertEqual(ev('=LEFT("abc",1.9)'), "a")

    def test_negative_count_is_err502(self):
        self.assertEqual(ev('=LEFT("x",-1)'), E("Err:502"))
        self.assertEqual(ev('=RIGHT("x",-1)'), E("Err:502"))

    def test_count_coercion(self):
        self.assertEqual(ev('=LEFT("abc","2")'), "ab")
        self.assertEqual(ev('=LEFT("abc","z")'), E("#VALUE!"))
        self.assertEqual(ev('=LEFT(A4,1/0)'), E("#N/A"))

    def test_mid(self):
        self.assertEqual(ev('=MID("hello",2,3)'), "ell")
        self.assertEqual(ev('=MID("hello",9,3)'), "")
        self.assertEqual(ev('=MID("hello",0,1)'), E("Err:502"))
        self.assertEqual(ev('=MID("hello",1,-1)'), E("Err:502"))
        self.assertEqual(ev('=MID("hello",2)'), E("Err:511"))
        self.assertEqual(ev('=MID(A2,1,1)'), "1")


class LenCaseTrimTest(unittest.TestCase):
    def test_len(self):
        self.assertEqual(ev('=LEN(A3)'), 9)
        self.assertEqual(ev('=LEN(Z9)'), 0)
        self.assertEqual(ev('=LEN(1/3)'), 17)
        self.assertEqual(ev('=LEN(A4)'), E("#N/A"))

    def test_case(self):
        self.assertEqual(ev('=UPPER(A6)'), "STRAẞE")
        self.assertEqual(ev('=LOWER("ÀB")'), "àb")
        self.assertEqual(ev('=UPPER(A2)'), "1")

    def test_trim_collapses_spaces(self):
        self.assertEqual(ev('=TRIM(A3)'), "a b")
        self.assertEqual(ev('=TRIM("   ")'), "")
        self.assertEqual(ev('=TRIM(A4)'), E("#N/A"))


if __name__ == "__main__":
    unittest.main()
