#!/bin/sh
# b1: multi-sheet workbooks mixing every function group compute as Calc does.
# Contract (plan a-r1-engine): the engine CLI (./engine, SPEC.md) computes whole workbooks as LibreOffice Calc does.
# 1. The workbook below goes through ./engine as one file; every cell must equal Calc's answer, which LibreOffice
#    headless computed over this exact workbook (numbers within 1e-9 relative; Calc's Err:5xx kept as Calc shows it).
# 2. The product carries its own end-to-end suite: tests/e2e/engine/books/<name>.json workbooks, each with Calc's
#    answers in <name>.calc.json, and unittest tests under tests/e2e/engine that ./test.sh discovers and that pass;
#    every product workbook computes through ./engine as its .calc.json says.
# 3. Across the product's workbooks: at least one has two or more sheets with formulas reading another sheet, and
#    the formulas name every one of SPEC's 40 functions.
set -eu
cd "$(dirname "$0")/../../../.."
export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=utf-8
# The shared helpers (run ./engine, compare with Calc, read the product books, run the e2e suite) are in
# a_r1_common.py and a_r1_chain.py next to this script; the check workbook and Calc's answers too.
python3 - <<'PY'
import re, sys
sys.path.insert(0, "tests/e2e/engine/checks")
from a_r1_common import FUNCS, fails, compare, formulas, load, product_books, product_suite, finish

BOOK, CALC = load("a_r1_b1_book.json"), load("a_r1_b1_calc.json")
compare(BOOK, CALC, "check workbook")
pb = product_books()
if not pb:
    fails.append("no product workbooks in tests/e2e/engine/books")
named = set()
multi = False
for n, b, c in pb:
    compare(b, c, "tests/e2e/engine/books/%s.json" % n)
    fs = formulas(b)
    for f in fs.values():
        body = re.sub(r'"[^"]*"', "", f).upper()
        named |= {fn for fn in FUNCS if re.search(r"(?<![A-Z0-9_.])%s\s*\(" % fn, body)}
    if len(b["sheets"]) >= 2 and any("!" in re.sub(r'"[^"]*"', "", f) for f in fs.values()):
        multi = True
missing = [f for f in FUNCS if f not in named]
if pb and missing:
    fails.append("the product workbooks never call: " + ", ".join(missing))
if pb and not multi:
    fails.append("no product workbook has two sheets with a cross-sheet formula")
product_suite()
finish()
PY
