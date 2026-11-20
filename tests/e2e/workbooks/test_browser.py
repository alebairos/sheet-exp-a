"""End to end: the three realistic workbooks open, display and save in a real browser.

browser_walk.mjs drives headless Chrome/Chromium ($CHROME first, then google-chrome or chromium on PATH) over
the DevTools pipe (tests/e2e/ui/browser.mjs, Node's standard library only), against web/io/serve.py. For each
workbook: Open books/<name>.json; the grid (A1:H20) shows its first sheet as Calc shows it
(books/<name>.shown.json: Calc's answers as the grid writes them, numbers to 15 significant digits), every other
visible cell blank; selecting the first formula cell shows the formula as typed in the formula bar; Save JSON
gives back the workbook opened; the page throws nothing. Skipped only without node or a browser.
"""
import json
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
NO_BROWSER = 2


class WorkbookBrowserTest(unittest.TestCase):
    def walk(self, name):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([node, os.path.join(HERE, "browser_walk.mjs"), name], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=180)
        if p.returncode == NO_BROWSER:
            self.skipTest(p.stdout.strip())
        self.assertEqual(p.returncode, 0, (p.stdout + p.stderr).strip()[-2000:])
        self.assertIn("ok " + name, p.stdout)

    def test_budget_in_the_browser(self):
        """The household budget: Summary shows as Calc shows it; open, formula bar, save."""
        self.walk("budget")

    def test_grades_in_the_browser(self):
        """The grade sheet: Grades shows as Calc shows it; open, formula bar, save."""
        self.walk("grades")

    def test_orders_in_the_browser(self):
        """The order sheet: Orders shows as Calc shows it; open, formula bar, save."""
        self.walk("orders")

    def test_shown_matches_calc(self):
        """books/<name>.shown.json covers every cell of the first sheet Calc computed (the grid's view of it)."""
        for name in ["budget", "grades", "orders"]:
            with open(os.path.join(HERE, "books", name + ".json"), encoding="utf-8") as f:
                book = json.load(f)
            with open(os.path.join(HERE, "books", name + ".shown.json"), encoding="utf-8") as f:
                shown = json.load(f)
            first = next(iter(book["sheets"]))
            self.assertEqual(set(shown["sheets"][first]), set(book["sheets"][first]), name)


if __name__ == "__main__":
    unittest.main()
