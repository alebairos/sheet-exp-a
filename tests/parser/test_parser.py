"""Unit tests for src.parser: the tree, Calc's precedence and parse errors."""

import unittest

from src.parser import (
    Binary, Bool, Call, Error, Missing, Name, Number, ParseError, Percent,
    Range, Ref, Text, Unary, col_to_letters, letters_to_col, parse, show,
)


def s(formula):
    return show(parse(formula))


class Nodes(unittest.TestCase):
    def test_ref_fields(self):
        self.assertEqual(parse("=$B7"), Ref(None, 2, 7, True, False))
        self.assertEqual(parse("=Sheet2!A$1"), Ref("Sheet2", 1, 1, False, True))

    def test_range_keeps_one_sheet(self):
        r = parse("='My Sheet'!A1:B2")
        self.assertIsInstance(r, Range)
        self.assertEqual(r.sheet, "My Sheet")
        self.assertEqual(r.end, Ref("My Sheet", 2, 2))

    def test_literals(self):
        self.assertEqual(parse("=1.5"), Number(1.5))
        self.assertEqual(parse('="x"'), Text("x"))
        self.assertEqual(parse("=true"), Bool(True))
        self.assertEqual(parse("=#div/0!"), Error("#DIV/0!"))
        self.assertEqual(s("=#N/A"), "#N/A")

    def test_call_missing_and_semicolon(self):
        self.assertEqual(parse("=IF(A1;;1)"),
                         Call("IF", (Ref(None, 1, 1), Missing(), Number(1.0))))
        self.assertEqual(s("=MAX(1,)"), "(MAX 1.0 _)")

    def test_names_and_function_like_refs(self):
        self.assertEqual(parse("=foo"), Name("FOO"))
        self.assertEqual(s("=LOG10(100)"), "(LOG10 100.0)")
        self.assertEqual(s("=XFE1"), "XFE1")          # past the last column: a name
        self.assertEqual(s("=XFD1048576"), "XFD1048576")

    def test_quoted_sheet_escape(self):
        self.assertEqual(s("='It''s'!A1"), "'It''s'!A1")
        self.assertEqual(parse("='It''s'!A1").sheet, "It's")

    def test_column_letters(self):
        for col in (1, 26, 27, 52, 702, 703, 16384):
            self.assertEqual(letters_to_col(col_to_letters(col)), col)
        self.assertEqual(col_to_letters(16384), "XFD")


class Precedence(unittest.TestCase):
    def test_calc_order(self):
        self.assertEqual(parse("=-A1^2"),
                         Binary("^", Unary("-", Ref(None, 1, 1)), Number(2.0)))
        self.assertEqual(s("=2^3^2"), "(^ (^ 2.0 3.0) 2.0)")
        self.assertEqual(s("=1+2*3^2%"), "(+ 1.0 (* 2.0 (^ 3.0 (% 2.0))))")
        self.assertEqual(s("=1&2+3<4"), "(< (& 1.0 (+ 2.0 3.0)) 4.0)")
        self.assertEqual(parse("=5%"), Percent(Number(5.0)))

    def test_whitespace(self):
        self.assertEqual(s("=  SUM( A1 , 2 ) "), "(SUM A1 2.0)")


class Malformed(unittest.TestCase):
    def test_parse_errors(self):
        for src in ["", "1+1", "=", "=1+", "=1)", "=A1:", "=Sheet2!", "=1,2",
                    "=SUM(1,", "=\"x", "=#BAD!", "=Sheet2!XFE1", "=A1:XFE1",
                    "=A1:Sheet2!B2", "=1E999", None, 5]:
            with self.assertRaises(ParseError, msg=repr(src)):
                parse(src)

    def test_spaces_around_a_range_colon(self):
        want = parse("=SUM(A1:A2)")
        for src in ["= SUM( A1 : A2 )", "=SUM(A1 :A2)", "=SUM(A1: A2)"]:
            self.assertEqual(parse(src), want, src)
        self.assertEqual(parse("=SUM( 'My Sheet'!A1 : A2 )"), parse("=SUM('My Sheet'!A1:A2)"))

    def test_range_names_its_sheet_on_both_ends(self):
        self.assertEqual(parse("=S2!A1:S2!A2"), parse("=S2!A1:A2"))
        self.assertEqual(parse("='My Sheet'!A1:'My Sheet'!B2"), parse("='My Sheet'!A1:B2"))
        self.assertEqual(parse("=s2!A1:S2!A2"), parse("=s2!A1:A2"))
        for src in ["=S2!A1:S3!A2", "=A1:S2!A2", "=A1:1", "=1:2", "=A1:B2:C3", "=A1 :"]:
            with self.assertRaises(ParseError, msg=src):
                parse(src)

    def test_missing_closing_parentheses_close_at_the_end(self):
        # Calc computes these: =(1 is 1, =((1+2) is 3, =SUM(1,2 is 3.
        self.assertEqual(parse("=(1"), parse("=1"))
        self.assertEqual(parse("=((1+2)"), parse("=1+2"))
        self.assertEqual(parse("=SUM(1,2"), parse("=SUM(1,2)"))
        self.assertEqual(parse('=IF(A1=1,"one","other"'), parse('=IF(A1=1,"one","other")'))
        # Only at the end: a missing ')' before more of the formula, or a dangling argument, is malformed.
        for src in ["=(1+", "=SUM(1,", "=(1 2", "=SUM(1 2"]:
            with self.assertRaises(ParseError, msg=src):
                parse(src)

    def test_deep_nesting_is_a_parse_error(self):
        with self.assertRaises(ParseError):
            parse("=" + "(" * 5000 + "1" + ")" * 5000)


if __name__ == "__main__":
    unittest.main()
