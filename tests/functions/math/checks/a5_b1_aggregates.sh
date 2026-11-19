#!/bin/sh
# b1: SUM, AVERAGE, MIN, MAX, COUNT, COUNTA, PRODUCT, MEDIAN, STDEV match Calc on ranges with blanks and text.
# Contract (plan a-i5-math): each function is registered with src.functions.register under
# src/functions/math and called by src.eval (a-i3's convention: a reference arrives as a Range, any
# other argument as a Value). Every expected value below is LibreOffice Calc's own answer, computed
# headless over this exact fixture (TRUE/FALSE cells stored as Calc stores them: 1/0, boolean format).
# In a range, text and blanks are skipped and a TRUE/FALSE cell counts as 1/0 (Calc stores booleans as numbers);
# a typed argument is coerced (COUNT counts "2"; SUM("3",1) is #VALUE!); an error in a range propagates.
# Calc's own error names are kept where it has no #-name: Err:502 (invalid argument), Err:504
# (parameter list error).
set -eu
cd "$(dirname "$0")/../../../.."
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
import json
import sys

from src.eval import evaluate
from src.values import to_json

BOOK = json.loads("{\"sheets\": {\"Sheet1\": {\"A1\": 1, \"A2\": 2, \"A3\": \"3\", \"A4\": true, \"A6\": 4.5, \"A7\": -2, \"A8\": \"abc\", \"B1\": 3, \"B2\": 1, \"B3\": 4, \"B4\": 1, \"B5\": 5, \"B6\": 9, \"C1\": 1, \"C2\": {\"error\": \"#DIV/0!\"}, \"C3\": 2, \"D1\": \"x\", \"D3\": \"y\", \"E1\": \"apple\", \"E2\": \"banana\", \"E3\": \"Apple\", \"E4\": \"cherry\", \"E5\": 10, \"E6\": 20, \"E7\": \"b*n\", \"E9\": \"10\", \"F1\": 1, \"F2\": 2, \"F3\": 3, \"F4\": 4, \"F5\": 5, \"F6\": 6, \"F7\": 7, \"F8\": 8, \"F9\": 9, \"H1\": false, \"H2\": true, \"H3\": 0}}}")

CASES = [
    ("=SUM(A1:A8)", 6.5),
    ("=SUM(B1:B6)", 23),
    ("=SUM(1,2,3)", 6),
    ("=SUM(A1:A8,10)", 16.5),
    ("=SUM(\"3\",1)", {"error": "#VALUE!"}),
    ("=SUM(TRUE,1)", 2),
    ("=SUM(A3)", 0),
    ("=SUM(G1:G5)", 0),
    ("=SUM(C1:C3)", {"error": "#DIV/0!"}),
    ("=SUM(\"abc\")", {"error": "#VALUE!"}),
    ("=SUM(A4)", 1),
    ("=SUM(A1:B6)", 31.5),
    ("=SUM(H1:H3)", 1),
    ("=SUM(D1:D3)", 0),
    ("=SUM(A1,A2,A3)", 3),
    ("=SUM(0.1,0.2)", 0.30000000000000004),
    ("=AVERAGE(A1:A8)", 1.3),
    ("=AVERAGE(B1:B6)", 3.8333333333333335),
    ("=AVERAGE(G1:G5)", {"error": "#DIV/0!"}),
    ("=AVERAGE(D1:D3)", {"error": "#DIV/0!"}),
    ("=AVERAGE(1,\"2\",TRUE)", {"error": "#VALUE!"}),
    ("=AVERAGE(C1:C3)", {"error": "#DIV/0!"}),
    ("=AVERAGE(A3)", {"error": "#DIV/0!"}),
    ("=AVERAGE(H1:H3)", 0.3333333333333333),
    ("=AVERAGE(B1:B6,A1:A2)", 3.25),
    ("=MIN(A1:A8)", -2),
    ("=MIN(G1:G5)", 0),
    ("=MIN(B1:B6,0.5)", 0.5),
    ("=MIN(\"x\")", {"error": "Err:504"}),
    ("=MIN(C1:C3)", {"error": "#DIV/0!"}),
    ("=MIN(D1:D3)", 0),
    ("=MIN(\"-7\",1)", {"error": "Err:504"}),
    ("=MIN(H1:H3)", 0),
    ("=MIN(A7,A6)", -2),
    ("=MAX(A1:A8)", 4.5),
    ("=MAX(G1:G5)", 0),
    ("=MAX(B1:B6,-1)", 9),
    ("=MAX(TRUE,0)", 1),
    ("=MAX(\"7\",1)", {"error": "Err:504"}),
    ("=MAX(C1:C3)", {"error": "#DIV/0!"}),
    ("=MAX(D1:D3)", 0),
    ("=MAX(-1,-5)", -1),
    ("=MAX(A7)", -2),
    ("=COUNT(A1:A8)", 5),
    ("=COUNT(G1:G5)", 0),
    ("=COUNT(1,\"2\",\"x\",TRUE)", 3),
    ("=COUNT(C1:C3)", 2),
    ("=COUNT(D1:D3)", 0),
    ("=COUNT(B1:B6)", 6),
    ("=COUNT(H1:H3)", 3),
    ("=COUNT(A3)", 0),
    ("=COUNT(1/0)", 0),
    ("=COUNTA(A1:A8)", 7),
    ("=COUNTA(G1:G5)", 0),
    ("=COUNTA(C1:C3)", 3),
    ("=COUNTA(1,\"\",\"x\")", 3),
    ("=COUNTA(D1:D3)", 2),
    ("=COUNTA(E1:E9)", 8),
    ("=COUNTA(1/0,1)", 2),
    ("=PRODUCT(B1:B6)", 540),
    ("=PRODUCT(A1:A8)", -18),
    ("=PRODUCT(G1:G5)", 0),
    ("=PRODUCT(2,\"3\")", {"error": "#VALUE!"}),
    ("=PRODUCT(C1:C3)", {"error": "#DIV/0!"}),
    ("=PRODUCT(D1:D3)", 0),
    ("=PRODUCT(A7,A6,-1)", 9),
    ("=PRODUCT(TRUE,5)", 5),
    ("=MEDIAN(B1:B6)", 3.5),
    ("=MEDIAN(A1:A8)", 1),
    ("=MEDIAN(1,2,3,4)", 2.5),
    ("=MEDIAN(G1:G5)", {"error": "#VALUE!"}),
    ("=MEDIAN(B1:B5)", 3),
    ("=MEDIAN(C1:C3)", {"error": "#DIV/0!"}),
    ("=MEDIAN(D1:D3)", {"error": "#VALUE!"}),
    ("=MEDIAN(5,\"1\",3)", {"error": "Err:504"}),
    ("=STDEV(B1:B6)", 2.9944392908634274),
    ("=STDEV(A1:A8)", 2.3345235059857505),
    ("=STDEV(1)", {"error": "#DIV/0!"}),
    ("=STDEV(1,2,\"3\")", {"error": "Err:504"}),
    ("=STDEV(C1:C3)", {"error": "#DIV/0!"}),
    ("=STDEV(G1:G5)", {"error": "#DIV/0!"}),
    ("=STDEV(2,4,4,4,5,5,7,9)", 2.138089935299395),
    ("=STDEV(H1:H3)", 0.5773502691896258),
    ("=STDEV(D1:D3,1,2)", 0.7071067811865476),
]


def same(got, want):
    if isinstance(want, (bool, str, dict)) or want is None:
        return type(got) is type(want) and got == want
    return (type(got) in (int, float) and not isinstance(got, bool)
            and abs(got - want) <= 1e-9 * max(1.0, abs(want)))


bad = 0
for formula, want in CASES:
    try:
        got = to_json(evaluate(formula, BOOK, "Sheet1"))
    except Exception as e:  # noqa: BLE001 - a crash is a failure, reported
        got = "raised %s: %s" % (type(e).__name__, e)
    if not same(got, want):
        bad += 1
        print("FAIL %s: got %s, want %s (Calc)" % (formula, json.dumps(got), json.dumps(want)))
if bad:
    print("%d of %d cases differ from Calc" % (bad, len(CASES)))
    sys.exit(1)
print("ok b1: %d cases match Calc" % len(CASES))
PY
