"""LibreOffice's approximate equality, addition and subtraction (a-v1-decimal-noise), and the CLI's
15-digit output. The Calc results these rules give are pinned against LibreOffice by
tests/eval/checks/a_v1_dn_*.sh; here the rule's own edges are kept.

CALC holds formulas at the rule's edges (whole numbers up to 2**53, the 2**-48 to 2**-44 band, 15-digit
rounding) with LibreOffice Calc 26.8.1.1's results, not written by hand: run headless by a copy of
tests/eval/checks/a_v1_dn_probe.py with these formulas as its CASES. A number is the double Calc holds."""

import json
import os
import subprocess
import sys
import unittest

from src.values import approx_add, approx_equal, approx_sub

E48 = 2.0 ** -48
CALC = [
    ('=1E15+1-1E15', 1.0),
    ('=3000000000000001-3000000000000000', 1.0),
    ('=4503599627370496+1-4503599627370496', 1.0),
    ('=2^49+1-2^49', 1.0),
    ('=2^52=2^52+1', False),
    ('=2^50=2^50+1', False),
    ('=1E15+1=1E15', False),
    ('=-(2^52)-1=-(2^52)', False),
    ('=1E15+1>1E15', True),
    ('=2^53-(2^53-1)', 0.0),
    ('=9007199254740992=9007199254740991', True),
    ('=2^53+2=2^53', True),
    ('=2^60+1000=2^60', True),
    ('=1E16+2=1E16', True),
    ('=1.000000000000004=1', True),
    ('=1.0000000000000049=1', True),
    ('=1.0000000000000049<>1', False),
    ('=1.000000000000004-1', 0.0),
    ('=1.000000000000005=1', False),
    ('=1.000000000000006-1', 5.995204332975845e-15),
    ('=1+5E-14=1', False),
    ('=1+5E-14-1', 4.9960036108132044e-14),
    ('=1.000000000000004>1', False),
    ('=1<1.000000000000004', False),
    ('=1.0000000000000049-1', 0.0),
    ('=1-1.0000000000000049', 0.0),
    ('=1.000000000000005-1', 5.10702591327572e-15),
    ('=1.0000000000000051=1', False),
    ('=1.00000000000001=1', False),
    ('=1.00000000000001-1', 9.992007221626409e-15),
    ('=1.000000000000014=1', False),
    ('=1.000000000000014-1', 1.3988810110276972e-14),
    ('=1.000000000000015=1', False),
    ('=1.00000000000002-1', 1.9984014443252818e-14),
    ('=-1.000000000000004=-1', True),
    ('=-1.000000000000004+1', 0.0),
    ('=1.000000000000004+(-1)', 0.0),
    ('=-1+1.000000000000004', 0.0),
    ('=0.1+0.2=0.3', True),
    ('=(0.1+0.2)-0.3', 0.0),
    ('=1.1*3-3.3', 0.0),
    ('=1E15+0.1-1E15', 0.0),
    ('=123456789012345.6-123456789012345.5', 0.0),
    ('=99999999999999.9=99999999999999.8', True),
    ('=1E14+0.5=1E14', False),
    ('=281474976710656+1=281474976710656', False),
    ('=281474976710656+1-281474976710656', 1.0),
    ('=2^48+0.5-2^48', 0.0),
    ('=2^48+0.5=2^48', True),
    ('=2^53-1=2^53-2', False),
    ('=(2^53-1)-(2^53-2)', 1.0),
    ('=2^53=2^53-1', True),
    ('=2^53-(2^53-2)', 0.0),
    ('=1E300*1.000000000000004=1E300', True),
    ('=1E-300*1.000000000000004=1E-300', True),
    ('=1E-300*1.000000000000004-1E-300', 0.0),
    ('=0.3=0.30000000000000004', True),
    ('=1E15+2-1E15', 2.0),
    ('=1E15+0.5-1E15', 0.0),
    ('=5-4.999999999999999', 0.0),
    ('=4.999999999999999=5', True),
    ('=10.000000000000004=10', True),
    ('=10.00000000000004=10', True),
    ('=1234567.000000004=1234567', True),
    ('=1234567.000000004-1234567', 0.0),
    ('=1E15+1>=1E15', True),
    ('=1E15<1E15+1', True),
]
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ApproxEqualTest(unittest.TestCase):
    def test_noise_is_equal(self):
        self.assertTrue(approx_equal(0.1 + 0.2, 0.3))
        self.assertTrue(approx_equal(1.1 * 3, 3.3))
        self.assertTrue(approx_equal(-(0.1 + 0.2), -0.3))

    def test_within_2_pow_minus_48_is_equal_at_any_size(self):
        self.assertTrue(approx_equal(1.0, 1.0 + 1e-15))
        self.assertFalse(approx_equal(1.0, 1.0 + 1e-14))
        self.assertTrue(approx_equal(1e300, 1e300 * (1 + 0.5 * E48)))
        self.assertTrue(approx_equal(1e-300, 1e-300 * (1 + 0.5 * E48)))
        self.assertTrue(approx_equal(2.0 ** 48 + 0.5, 2.0 ** 48))   # 15 digits differ, 2**-48 decides

    def test_up_to_2_pow_minus_44_the_15_digits_decide(self):
        # 1.0000000000000049 reads 1.00000000000000, 1.000000000000005 reads 1.00000000000001 (half up from
        # the decimal form; the double itself is just below the half).
        self.assertTrue(approx_equal(1.000000000000004, 1.0))
        self.assertTrue(approx_equal(1.0000000000000049, 1.0))
        self.assertFalse(approx_equal(1.000000000000005, 1.0))
        self.assertTrue(approx_equal(10.00000000000004, 10.0))
        self.assertFalse(approx_equal(1.0 + 5e-14, 1.0))
        self.assertFalse(approx_equal(1e14 + 0.5, 1e14))

    def test_beyond_2_pow_minus_44_is_never_equal(self):
        self.assertFalse(approx_equal(1e300, 1e300 * (1 + 32 * E48)))
        self.assertFalse(approx_equal(1.0 + 1e-13, 1.0))

    def test_whole_numbers_up_to_2_pow_53_minus_1_stay_apart(self):
        self.assertFalse(approx_equal(1e15 + 1, 1e15))
        self.assertFalse(approx_equal(2.0 ** 52 + 1, 2.0 ** 52))
        self.assertFalse(approx_equal(2.0 ** 53 - 1, 2.0 ** 53 - 2))
        self.assertEqual(approx_sub(3000000000000001.0, 3000000000000000.0), 1.0)
        # 2**53 itself is past the guard: there the 2**-48 rule collapses them, as in Calc.
        self.assertTrue(approx_equal(2.0 ** 53, 2.0 ** 53 - 1))
        self.assertTrue(approx_equal(1e16 + 2, 1e16))

    def test_zero_and_signs_are_exact(self):
        self.assertTrue(approx_equal(0.0, 0.0))
        self.assertFalse(approx_equal(0.0, 1e-300))
        self.assertFalse(approx_equal(1e-20, -1e-20))

    def test_infinities_are_not_equal_to_finite_numbers(self):
        inf = float("inf")
        self.assertFalse(approx_equal(inf, 1e308))
        self.assertTrue(approx_equal(inf, inf))


class ApproxAddSubTest(unittest.TestCase):
    def test_near_equal_subtraction_is_zero(self):
        self.assertEqual(approx_sub(0.1 + 0.2, 0.3), 0.0)
        self.assertEqual(approx_sub(-0.3, -(0.1 + 0.2)), 0.0)
        self.assertEqual(approx_sub(5, 4.999999999999999), 0.0)

    def test_near_opposite_addition_is_zero(self):
        self.assertEqual(approx_add(0.1 + 0.2, -0.3), 0.0)
        self.assertEqual(approx_add(-0.3, 0.1 + 0.2), 0.0)

    def test_real_differences_are_kept(self):
        self.assertEqual(approx_sub(1 + 1e-14, 1), (1 + 1e-14) - 1)
        self.assertEqual(approx_sub(100.1, 100), 100.1 - 100)
        self.assertEqual(approx_add(0.1, 0.2), 0.1 + 0.2)  # same signs: an ordinary sum
        self.assertEqual(approx_sub(0.3, -0.3), 0.6)       # opposite signs: an ordinary difference


class CalcEdgesTest(unittest.TestCase):
    def test_formulas_match_calc(self):
        from src.cli import compute
        out = compute({"sheets": {"S": {"A%d" % (i + 1): f for i, (f, _) in enumerate(CALC)}}})["sheets"]["S"]
        for i, (f, want) in enumerate(CALC):
            got = out["A%d" % (i + 1)]
            if isinstance(want, bool):
                self.assertIs(got, want, f)
            else:
                self.assertFalse(isinstance(got, bool), f)
                self.assertEqual(got, want, f)


class CliOutputTest(unittest.TestCase):
    def engine(self, cells):
        p = subprocess.run([sys.executable, os.path.join(ROOT, "engine"), "-"], capture_output=True, text=True,
                           input=json.dumps({"sheets": {"S": cells}}), cwd=ROOT,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout, json.loads(p.stdout)["sheets"]["S"]

    def test_floats_print_to_15_significant_digits(self):
        text, out = self.engine({"A1": "=0.1+0.2", "A2": "=1.1*3", "A3": "=100.1-100", "A4": "=1/3",
                                 "A5": "=2^0.5*2^0.5", "A6": "=1E21*1", "A7": "=-1/3"})
        self.assertNotIn("0.30000000000000004", text)
        self.assertEqual(out["A1"], 0.3)
        self.assertEqual(out["A2"], 3.3)
        self.assertEqual(out["A3"], 0.0999999999999943)
        self.assertEqual(out["A4"], 0.333333333333333)
        self.assertEqual(out["A5"], 2)               # 2.0000000000000004 shows as 2
        self.assertIsInstance(out["A5"], int)
        self.assertEqual(out["A6"], 1e21)
        self.assertEqual(out["A7"], -0.333333333333333)

    def test_full_precision_is_kept_inside(self):
        # Only the CLI's output is rounded: the computed cell keeps 0.30000000000000004, as Calc stores it.
        from src.recalc import Workbook
        wb = Workbook({"sheets": {"S": {"A1": "=0.1+0.2"}}})
        self.assertEqual(wb.value("S", "A1"), 0.1 + 0.2)
        self.assertEqual(self.engine({"A1": "=0.1+0.2"})[1]["A1"], 0.3)


if __name__ == "__main__":
    unittest.main()
