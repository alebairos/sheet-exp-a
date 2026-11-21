"""Calc's number-to-text rule (src.values.format_number), as &, CONCATENATE, LEFT and LEN use it.

The rule: an integer below 2**53 is written exactly; any other number is rounded to 15 significant digits,
half away from zero, and written as a decimal when its exponent is from -14 to 14, else as mantissa, E, sign
and a 3-digit exponent (1E+021, 1E-020); no trailing zeros.

Expected values are not written by hand: CALC is copied from tests/values/checks/a_v1_nt_calc.json, the output
of LibreOffice Calc 26.8.1.1 run headless by a_v1_nt_probe.py. Each row is (expression, Calc's text, Calc's LEN).
"""

import unittest

from src.cli import compute
from src.values import Number, Text, format_number, to_text

CALC = [
    ('1E-7', '0.0000001', 9),
    ('1E15', '1000000000000000', 16),
    ('1E21', '1E+021', 6),
    ('123456789012345678', '1.23456789012346E+017', 21),
    ('1E-20', '1E-020', 6),
    ('0.1', '0.1', 3),
    ('1/3', '0.333333333333333', 17),
    ('2/3', '0.666666666666667', 17),
    ('1E14', '100000000000000', 15),
    ('999999999999999', '999999999999999', 15),
    ('1234567890123456', '1234567890123456', 16),
    ('0.000123456', '0.000123456', 11),
    ('1E-5', '0.00001', 7),
    ('0.00001234', '0.00001234', 10),
    ('1.5E-8', '0.000000015', 11),
    ('123456.789', '123456.789', 10),
    ('-1234567.891', '-1234567.891', 12),
    ('1E100', '1E+100', 6),
    ('1E-100', '1E-100', 6),
    ('-1E-7', '-0.0000001', 10),
    ('12345678901234.5', '12345678901234.5', 16),
    ('0.5', '0.5', 3),
    ('1000', '1000', 4),
    ('1E20', '1E+020', 6),
    ('3.14159265358979', '3.14159265358979', 16),
    ('0.1+0.2', '0.3', 3),
    ('2^53', '9.00719925474099E+015', 21),
    ('1E16', '1E+016', 6),
    ('1E17', '1E+017', 6),
    ('1E19', '1E+019', 6),
    ('1E-4', '0.0001', 6),
    ('1E-10', '0.0000000001', 12),
    ('1E-15', '1E-015', 6),
    ('1E-18', '1E-018', 6),
    ('1E-19', '1E-019', 6),
    ('1.23456789E-12', '0.00000000000123456789', 22),
    ('0.1234567890123455', '0.123456789012346', 17),
    ('123456789012345.5', '123456789012346', 15),
    ('9.99999999999999E-10', '0.000000000999999999999999', 26),
    ('-0', '0', 1),
    ('7', '7', 1),
    ('-2.5', '-2.5', 4),
    ('1E300', '1E+300', 6),
    ('4.5E-15', '4.5E-015', 8),
    ('98765432109876543210', '9.87654321098765E+019', 21),
    ('1E-14', '0.00000000000001', 16),
    ('1.5E-14', '0.000000000000015', 17),
    ('9.99999999999999E-15', '9.99999999999999E-015', 21),
    ('2^53-1', '9007199254740991', 16),
    ('2^53+2', '9.00719925474099E+015', 21),
    ('5E15', '5000000000000000', 16),
    ('1E15+0.5', '1E+015', 6),
    ('-9007199254740991', '-9007199254740991', 17),
    ('1E15*9', '9000000000000000', 16),
    ('0.000000000000012345678901234', '0.000000000000012345678901234', 29),
]


def _engine(formulas):
    """Compute one sheet of formulas through the engine, as ./engine does."""
    return compute({"sheets": {"S": formulas}})["sheets"]["S"]


def _numbers():
    """Each expression's value as the engine computes it (=2^53-1, =1/3, ...)."""
    out = _engine({"A%d" % (i + 1): "=" + n for i, (n, _, _) in enumerate(CALC)})
    return [out["A%d" % (i + 1)] for i in range(len(CALC))]


class FormatNumberTest(unittest.TestCase):
    def test_matches_calc(self):
        for (n, text, _), x in zip(CALC, _numbers()):
            self.assertEqual(format_number(float(x)), text, n)
            self.assertEqual(to_text(Number(x)), Text(text), n)

    def test_text_length_matches_calc_len(self):
        for (n, text, length), x in zip(CALC, _numbers()):
            self.assertEqual(len(format_number(float(x))), length, n)


class TextFunctionsTest(unittest.TestCase):
    """The same conversion reaches every text operation through the engine."""

    FORMS = {"amp": '="x"&({})', "concat": "=CONCATENATE({})", "left": "=LEFT({},40)", "len": "=LEN({})"}

    def test_forms_match_calc(self):
        cells = {}
        for i, (n, _, _) in enumerate(CALC):
            for j, form in enumerate(self.FORMS.values()):
                cells["%s%d" % ("ABCD"[j], i + 1)] = form.format(n)
        out = _engine(cells)
        for i, (n, text, length) in enumerate(CALC):
            row = [out["%s%d" % (c, i + 1)] for c in "ABCD"]
            self.assertEqual(row, ["x" + text, text, text, length], n)


class RuleEdgesTest(unittest.TestCase):
    """Where Calc switches form, from the same LibreOffice run."""

    def _text(self, n):
        return next(t for m, t, _ in CALC if m == n)

    def test_decimal_from_1e_minus_14(self):
        self.assertEqual(self._text("1E-14"), "0.00000000000001")
        self.assertEqual(self._text("9.99999999999999E-15"), "9.99999999999999E-015")
        self.assertEqual(format_number(1e-14), self._text("1E-14"))
        self.assertEqual(format_number(9.99999999999999e-15), self._text("9.99999999999999E-15"))

    def test_exact_integers_below_2_to_53(self):
        self.assertEqual(format_number(2.0 ** 53 - 1), self._text("2^53-1"))
        self.assertEqual(format_number(2.0 ** 53), self._text("2^53"))
        self.assertEqual(format_number(-(2.0 ** 53 - 1)), self._text("-9007199254740991"))

    def test_three_digit_exponent(self):
        self.assertEqual(format_number(1e21), self._text("1E21"))
        self.assertEqual(format_number(1e-20), self._text("1E-20"))
        self.assertEqual(format_number(1e300), self._text("1E300"))

    def test_halves_round_away_from_zero(self):
        self.assertEqual(format_number(0.1234567890123455), self._text("0.1234567890123455"))
        self.assertEqual(format_number(123456789012345.5), self._text("123456789012345.5"))


if __name__ == "__main__":
    unittest.main()
