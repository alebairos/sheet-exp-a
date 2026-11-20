"""The walk-through in a real browser: open a workbook, edit a formula, see the error, fix it, save.

walkthrough.mjs drives headless Chrome/Chromium ($CHROME first, then google-chrome or chromium on PATH) over
the DevTools pipe, Node's standard library only, against web/io/serve.py. Skipped only without node or a browser.
"""
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
NO_BROWSER = 2


class WalkthroughTest(unittest.TestCase):
    def test_open_edit_error_fix_save_in_the_browser(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run([node, os.path.join(HERE, "walkthrough.mjs")], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=180)
        if p.returncode == NO_BROWSER:
            self.skipTest(p.stdout.strip())
        self.assertEqual(p.returncode, 0, (p.stdout + p.stderr).strip()[-2000:])
        self.assertIn("ok", p.stdout)


if __name__ == "__main__":
    unittest.main()
