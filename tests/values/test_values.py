"""Unit tests for src.values: kinds, JSON mapping and Calc's coercion rules."""

import unittest

from src.values import (BLANK, DIV0, NA, NUM, REF, VALUE, Bool, Error, Number, Text,
                        compare, format_number, from_json, to_bool, to_json, to_number,
                        to_text)


class JsonTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(from_json(1), Number(1))
        self.assertEqual(from_json("x"), Text("x"))
        self.assertEqual(from_json(True), Bool(True))
        self.assertIs(from_json(None), BLANK)
        self.assertEqual(from_json({"error": "#N/A"}), NA)

    def test_roundtrip(self):
        for j in [1, -2.5, 0, 1e-7, 123456789012, "", "12", True, False, None,
                  {"error": "#DIV/0!"}, {"error": "#NUM!"}]:
            got = to_json(from_json(j))
            self.assertEqual(got, j)
            self.assertIs(type(got), type(j))

    def test_integral_float_is_int(self):
        self.assertIs(type(to_json(Number(2.0))), int)

    def test_non_finite_is_num_error(self):
        self.assertEqual(to_json(Number(float("inf"))), {"error": "#NUM!"})
        self.assertEqual(to_json(Number(float("nan"))), {"error": "#NUM!"})

    def test_immutable(self):
        with self.assertRaises(AttributeError):
            Number(1).value = 2


class ToNumberTest(unittest.TestCase):
    def test_numbers_bools_blank(self):
        self.assertEqual(to_number(Number(3)), Number(3))
        self.assertEqual(to_number(Bool(True)), Number(1))
        self.assertEqual(to_number(Bool(False)), Number(0))
        self.assertEqual(to_number(BLANK), Number(0))

    def test_text(self):
        for s, x in [("12", 12), ("-2.5", -2.5), ("+4", 4), ("1E3", 1000), (".5", 0.5),
                     ("5.", 5), ("1e-2", 0.01)]:
            self.assertEqual(to_number(Text(s)), Number(x), s)
        for s, x in [(" 12", 12), ("12 ", 12), ("TRUE", 1), ("$5", 5), ("1,000", 1000), ("50%", 0.5)]:
            self.assertEqual(to_number(Text(s)), Number(x), s)  # as Calc reads them
        for s in ["abc", "", "inf", "nan", "1_000", "1,5", "0x10"]:
            self.assertEqual(to_number(Text(s)), VALUE, s)

    def test_error_passes(self):
        self.assertEqual(to_number(DIV0), DIV0)


class ToTextTest(unittest.TestCase):
    def test_general_format(self):
        for x, s in [(1, "1"), (2.5, "2.5"), (-3, "-3"), (0.1 + 0.2, "0.3"), (0, "0"),
                     (1e20, "1E+020"), (1e-7, "0.0000001"), (123456789012, "123456789012"),
                     (1 / 3, "0.333333333333333")]:
            self.assertEqual(format_number(x), s)
            self.assertEqual(to_text(Number(x)), Text(s))

    def test_rounding_carry_keeps_the_form(self):
        # Calc picks decimal or E from the number's exponent before rounding to 15 digits.
        # Expected values from LibreOffice Calc 26.8 (rev-a's probe on wi-a-v1-number-text-1 attempt 1).
        for x, s in [(999999999999999.5, "1000000000000000"), (9.999999999999995e14, "1000000000000000"),
                     (1e15 - 0.5, "1000000000000000"), (1e15 - 0.25, "1000000000000000"),
                     (-999999999999999.5, "-1000000000000000"), (9.999999999999995e-15, "1E-014"),
                     (9.9999999999999951e-15, "1E-014"), (-9.999999999999995e-15, "-1E-014"),
                     (1e15 + 0.5, "1E+015"), (9.999999999999995e20, "1E+021"),
                     (99999999999999.995, "100000000000000")]:
            self.assertEqual(format_number(x), s, repr(x))

    def test_other_kinds(self):
        self.assertEqual(to_text(Bool(True)), Text("TRUE"))
        self.assertEqual(to_text(Bool(False)), Text("FALSE"))
        self.assertEqual(to_text(BLANK), Text(""))
        self.assertEqual(to_text(REF), REF)


class ToBoolTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(to_bool(Number(2)), Bool(True))
        self.assertEqual(to_bool(Number(0)), Bool(False))
        self.assertEqual(to_bool(BLANK), Bool(False))
        self.assertEqual(to_bool(Text("x")), VALUE)
        self.assertEqual(to_bool(NA), NA)


class CompareTest(unittest.TestCase):
    def test_numbers_and_text(self):
        self.assertEqual(compare(Number(1), Number(2)), -1)
        self.assertEqual(compare(Number(1), Text("1")), -1)
        self.assertEqual(compare(Text("1"), Number(1)), 1)
        self.assertEqual(compare(Text("a"), Text("A")), -1)  # Calc: case-sensitive, lower first
        self.assertEqual(compare(Text("B"), Text("a")), 1)

    def test_bools_are_numbers(self):
        self.assertEqual(compare(Bool(True), Number(1)), 0)
        self.assertEqual(compare(Bool(False), Number(0)), 0)
        self.assertEqual(compare(Bool(True), Text("a")), -1)

    def test_blank(self):
        self.assertEqual(compare(BLANK, Number(0)), 0)
        self.assertEqual(compare(BLANK, Text("")), 0)
        self.assertEqual(compare(Text(""), BLANK), 0)
        self.assertEqual(compare(BLANK, BLANK), 0)
        self.assertEqual(compare(BLANK, Number(-1)), 1)
        self.assertEqual(compare(BLANK, Text("a")), -1)

    def test_errors(self):
        self.assertEqual(compare(DIV0, NA), DIV0)
        self.assertEqual(compare(Number(1), NA), NA)
        self.assertEqual(compare(Error("#NUM!"), BLANK), NUM)


if __name__ == "__main__":
    unittest.main()
