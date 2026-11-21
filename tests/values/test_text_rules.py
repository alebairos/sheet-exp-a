"""Calc's text rules through the evaluator (plan a-v1-text-rules): how text compares and how text reads as a number.

Every expected value was obtained by running LibreOffice Calc 26.8.1.1 (headless, new document: case-sensitive,
en-US) on these very formulas, never written by hand. ORDER and NUMBERS list (formula, Calc's result); the texts
in VALUE_ERRORS give #VALUE! in Calc. One deliberate difference: Calc reads a number beyond the largest double
as 1.7976931348623157E+308, and ./engine reads 1.79769313486231E+308, 3e-15 below it, because the CLI prints
15 significant digits and the largest double rounds up past itself (see src/values/text_rules.py, _LARGEST).
"""
import unittest

from src.eval import evaluate
from src.values import Bool, Error, Number

BOOK = {"sheets": {"Sheet1": {}}}

# = <> < > on text: case-sensitive (lower before upper), accents after the plain letter and before the next letter,
# punctuation before digits before letters, ß æ þ as Calc sorts them; = and <> compare text exactly.
ORDER = [
    ('="a"="A"', False), ('="a"<"A"', True), ('="A"<"b"', True), ('="abc"<"ABC"', True), ('="Ab"<"aB"', False),
    ('="aB"<"Ab"', True), ('="a"<>"A"', True), ('="Yes"="yes"', False), ('="Yes"="Yes"', True),
    ('="é">"f"', False), ('="e"<"é"', True), ('="E"<"é"', True), ('="é"<"É"', True), ('="Zürich"<"Zuse"', True),
    ('="ñ"<"o"', True), ('="ä"<"b"', True), ('="Émile"<"Eric"', True),
    ('="a-b"<"ab"', True), ('="-"<"a"', True), ('="10"<"9"', True), ('="!"<"1"', True), ('="ß">"ss"', True),
    ('="Strasse"<"straße"', True), ('="æ">"ae"', True), ('="æ"<"af"', True), ('="þ">"z"', True),
    ('="a"<"a "', True), ('=""<"a"', True),
    # e + combining acute against é: not =, yet both <= and >= (they sort equal).
    ('="é"="é"', False), ('="é"<>"é"', True), ('="é"<="é"', True),
    ('="é">="é"', True),
]

# Text read as a number: spaces, TRUE/FALSE, $ before or after, (5) and a trailing sign for a negative, thousands
# by threes, a trailing %; and the functions that read a number read it the same way.
NUMBERS = [
    ('=" 5 "+0', 5), ('="TRUE"+0', 1), ('="false"+0', 0), ('="$5"+0', 5), ('="5$"+0', 5), ('="-$5"+0', -5),
    ('="($5)"+0', -5), ('="(5)"+0', -5), ('="5-"+0', -5), ('="1,000"+0', 1000), ('="1,234.5"+0', 1234.5),
    ('="$1,000.50"+0', 1000.5), ('="50%"+0', 0.5), ('="5 %"+0', 0.05), ('="(5)%"+0', -0.05),
    ('="1,000e3"+0', 1e6), ('="1 e3"+0', 1000), ('="00,123"+0', 123), ('="5 "+0', 5), ('=-"50%"', -0.5),
    ('="50%"*2', 1), ('="1,000"+"$5"', 1005),
    ('=ROUND("(5)",0)', -5), ('=ABS("$5")', 5), ('=COUNT("1,000")', 1), ('=INT("50%")', 0),
    ('=SQRT(" 4 ")', 2), ('=MOD("1,000",7)', 6), ('=POWER("5-",2)', 25),
]
OVERFLOW = [('="1E400"+0', 1.7976931348623157e308), ('="-1e309"+0', 1.7976931348623157e308)]

# Text Calc refuses: #VALUE!.
VALUE_ERRORS = ["1 000", "1,00", "12,34", "1.000,5", "€5", "--5", "5%%", "%5", "1.5e2%", "1e3%", "$5%", "2e3$",
                "(-5)", "-(5)", "(50%)", "-5-", "$$5", "TRUE1", "-TRUE", "\t5", "yes", "", "abc", "1_000", "0x10"]


def ev(f):
    return evaluate(f, BOOK, "Sheet1")


class TextOrderTest(unittest.TestCase):
    def test_compare_as_calc(self):
        for f, want in ORDER:
            self.assertEqual(ev(f), Bool(want), f)


class TextNumberTest(unittest.TestCase):
    def test_read_as_numbers(self):
        for f, x in NUMBERS:
            got = ev(f)
            self.assertIsInstance(got, Number, f)
            self.assertAlmostEqual(got.value, x, delta=1e-12 * max(1, abs(x)), msg=f)

    def test_beyond_the_largest_double(self):
        for f, x in OVERFLOW:
            got = ev(f)
            self.assertIsInstance(got, Number, f)
            self.assertAlmostEqual(got.value / x, 1.0, delta=1e-14, msg=f)  # see the module's docstring

    def test_stay_value_errors(self):
        for t in VALUE_ERRORS:
            self.assertEqual(ev('="%s"+0' % t), Error("#VALUE!"), repr(t))


if __name__ == "__main__":
    unittest.main()
