"""Runs the formula bar's Node tests from the unittest suite (skipped without Node.js)."""

import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


@unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
class FormulaBarNodeTests(unittest.TestCase):
    def test_node_suite(self):
        r = subprocess.run(["node", "--test", os.path.join(HERE, "formula_bar.test.mjs")],
                           cwd=ROOT, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
