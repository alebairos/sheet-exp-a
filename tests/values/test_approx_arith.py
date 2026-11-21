"""LibreOffice's approximate equality, addition and subtraction (a-v1-decimal-noise), and the CLI's
15-digit output. The Calc results these rules give are pinned against LibreOffice by
tests/eval/checks/a_v1_dn_*.sh; here the rule's own edges are kept."""

import json
import os
import subprocess
import sys
import unittest

from src.values import approx_add, approx_equal, approx_sub

E48 = 2.0 ** -48
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ApproxEqualTest(unittest.TestCase):
    def test_noise_is_equal(self):
        self.assertTrue(approx_equal(0.1 + 0.2, 0.3))
        self.assertTrue(approx_equal(1.1 * 3, 3.3))
        self.assertTrue(approx_equal(-(0.1 + 0.2), -0.3))

    def test_the_2_pow_minus_48_edge_is_relative(self):
        self.assertTrue(approx_equal(1.0, 1.0 + 1e-15))
        self.assertFalse(approx_equal(1.0, 1.0 + 1e-14))
        self.assertTrue(approx_equal(1e300, 1e300 * (1 + 0.5 * E48)))
        self.assertFalse(approx_equal(1e300, 1e300 * (1 + 2 * E48)))
        self.assertTrue(approx_equal(1e-300, 1e-300 * (1 + 0.5 * E48)))

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
