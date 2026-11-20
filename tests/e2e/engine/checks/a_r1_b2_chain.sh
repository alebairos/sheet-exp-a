#!/bin/sh
# b2: a workbook with a chain of 100 formulas and an error in it computes, the error propagating as in Calc.
# Contract (plan a-r1-engine): the engine CLI (./engine, SPEC.md) computes whole workbooks as LibreOffice Calc does.
# 1. The workbook below goes through ./engine as one file; every cell must equal Calc's answer, which LibreOffice
#    headless computed over this exact workbook (numbers within 1e-9 relative; Calc's Err:5xx kept as Calc shows it).
# 2. The product carries its own end-to-end suite: tests/e2e/engine/books/<name>.json workbooks, each with Calc's
#    answers in <name>.calc.json, and unittest tests under tests/e2e/engine that ./test.sh discovers and that pass;
#    every product workbook computes through ./engine as its .calc.json says.
# 3. Among the product's workbooks, one holds a chain of at least 100 formulas, each reading the one before
#    (the longest path of formula-to-formula references, a range reaching every formula inside it), and Calc's
#    answers for it carry an error value.
set -eu
cd "$(dirname "$0")/../../../.."
export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=utf-8
# The shared helpers (run ./engine, compare with Calc, read the product books, run the e2e suite) are in
# a_r1_common.py and a_r1_chain.py next to this script; the check workbook and Calc's answers too.
python3 - <<'PY'
import re, sys
sys.path.insert(0, "tests/e2e/engine/checks")
from a_r1_common import fails, compare, longest_chain, load, product_books, product_suite, finish

BOOK, CALC = load("a_r1_b2_book.json"), load("a_r1_b2_calc.json")
n = longest_chain(BOOK)
if n < 100:
    fails.append("check workbook chain is %d long" % n)
compare(BOOK, CALC, "check workbook")
pb = product_books()
found = False
for name, b, c in pb:
    compare(b, c, "tests/e2e/engine/books/%s.json" % name)
    errs = any(isinstance(v, dict) and "error" in v for cells in c["sheets"].values() for v in cells.values())
    if errs and longest_chain(b) >= 100:
        found = True
if not found:
    fails.append("no product workbook in tests/e2e/engine/books has a chain of 100 formulas with an error in Calc's answers")
product_suite()
finish()
PY
