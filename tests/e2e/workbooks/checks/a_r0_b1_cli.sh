#!/bin/sh
# b1: three realistic workbooks compute as Calc does through the CLI.
# Contract (plan a-r0-spreadsheet):
# 1. The plan's three workbooks (checks/a_r0_books.json: a household budget, a grade sheet, an order sheet over
#    a product catalog; 7 sheets, cross-sheet formulas) go through ./engine one file each; every cell must equal
#    Calc's answer (checks/a_r0_calc.json, computed by LibreOffice headless over these exact workbooks; numbers
#    within 1e-9 relative, text and booleans exactly).
# 2. The product carries them as its own end-to-end suite: tests/e2e/workbooks/books/<name>.json and Calc's
#    answers in <name>.calc.json for budget, grades and orders, identical to the plan's files, and unittest tests
#    in tests/e2e/workbooks/test_cli.py that ./test.sh discovers and that pass.
set -eu
cd "$(dirname "$0")/../../../.."
export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=utf-8
python3 - <<'PY'
import sys
sys.path.insert(0, "tests/e2e/workbooks/checks")
from a_r0_common import NAMES, load, compare, product_books, product_tests, finish

books, calc = load("a_r0_books.json"), load("a_r0_calc.json")
for n in NAMES:
    compare(books[n], calc[n], n)
product_books()
product_tests("test_cli")
finish()
PY
