#!/bin/sh
# b2: the same workbooks open, display and save in the browser.
# Contract (plan a-r0-spreadsheet):
# 1. In headless Chrome/Chromium, on web/io/index.html as web/io/serve.py serves it (a_r0_browser.mjs,
#    a_r0_cdp.mjs next to this script), for each of the plan's workbooks budget, grades and orders:
#    Open (#open) <name>.json; the grid (#grid td[data-ref], A1:H20) shows its first sheet (Summary, Grades,
#    Orders) as checks/a_r0_shown.json says (outer spaces trimmed), every other visible cell blank; clicking
#    the first formula cell shows its formula as typed in the formula bar; Save JSON (#save-json) downloads <name>.json equal to
#    the workbook opened (every sheet, every cell, formulas as typed); the page throws nothing.
#    a_r0_shown.json is Calc's answer (a_r0_calc.json) as the grid writes it: numbers to 15 significant digits.
# 2. The product carries its own browser test of that: unittest tests in tests/e2e/workbooks/test_browser.py
#    that ./test.sh discovers, that run (not skipped) when a browser is found, start the browser named by $CHROME
#    (first, before google-chrome or chromium on PATH) and pass.
# The browser: $CHROME, else google-chrome, google-chrome-stable, chromium or chromium-browser; none is a FAIL.
set -eu
cd "$(dirname "$0")/../../../.."
export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=utf-8
command -v node >/dev/null || { echo "FAIL: node is not installed"; exit 1; }
status=0
node tests/e2e/workbooks/checks/a_r0_browser.mjs || status=1
python3 - <<'PY' || status=1
import sys
sys.path.insert(0, "tests/e2e/workbooks/checks")
from a_r0_common import product_tests, finish

product_tests("test_browser", chrome=True)
finish()
PY
[ "$status" = 0 ] && echo ok
exit "$status"
