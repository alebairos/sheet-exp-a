#!/bin/sh
# b2: ROUND, ROUNDUP, ROUNDDOWN, INT, MOD, ABS, POWER, SQRT match Calc, errors included.
# Contract (plan a-i5-math): each function is registered with src.functions.register under
# src/functions/math and called by src.eval (a-i3's convention: a reference arrives as a Range, any
# other argument as a Value). Every expected value below is LibreOffice Calc's own answer, computed
# headless over this exact fixture (TRUE/FALSE cells stored as Calc stores them: 1/0, boolean format).
# Half away from zero on the decimal value Calc shows (ROUND(1.005,2) is 1.01, ROUNDUP(0.1+0.2,1) is 0.3);
# MOD takes the divisor's sign; text that reads as a number is coerced, other text is #VALUE!.
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
    ("=ROUND(2.5,0)", 3),
    ("=ROUND(-2.5,0)", -3),
    ("=ROUND(1.005,2)", 1.01),
    ("=ROUND(1234.567,-2)", 1200),
    ("=ROUND(2.345,2)", 2.35),
    ("=ROUND(A6,0)", 5),
    ("=ROUND(\"2.5\",0)", 3),
    ("=ROUND(1/0,0)", {"error": "#DIV/0!"}),
    ("=ROUND(\"abc\",1)", {"error": "#VALUE!"}),
    ("=ROUND(2.5)", 3),
    ("=ROUND(0.5,0)", 1),
    ("=ROUND(-0.5,0)", -1),
    ("=ROUND(2.15,1)", 2.2),
    ("=ROUND(TRUE,0)", 1),
    ("=ROUND(A5,0)", 0),
    ("=ROUND(5.5,-1)", 10),
    ("=ROUND(3.14159,3)", 3.142),
    ("=ROUND(2.5,0.9)", 3),
    ("=ROUND(1,1/0)", {"error": "#DIV/0!"}),
    ("=ROUND(A8,1)", {"error": "#VALUE!"}),
    ("=ROUND(-1.55,1)", -1.6),
    ("=ROUNDUP(1.21,1)", 1.3),
    ("=ROUNDUP(-1.21,1)", -1.3),
    ("=ROUNDUP(3.2)", 4),
    ("=ROUNDUP(1234,-2)", 1300),
    ("=ROUNDUP(0.1+0.2,1)", 0.3),
    ("=ROUNDUP(5,0)", 5),
    ("=ROUNDUP(2.0000001,2)", 2.01),
    ("=ROUNDUP(\"x\",1)", {"error": "#VALUE!"}),
    ("=ROUNDUP(C2,1)", {"error": "#DIV/0!"}),
    ("=ROUNDDOWN(1.29,1)", 1.2),
    ("=ROUNDDOWN(-1.29,1)", -1.2),
    ("=ROUNDDOWN(1299,-2)", 1200),
    ("=ROUNDDOWN(2.5)", 2),
    ("=ROUNDDOWN(-2.5)", -2),
    ("=ROUNDDOWN(0.3,1)", 0.3),
    ("=ROUNDDOWN(A8,0)", {"error": "#VALUE!"}),
    ("=INT(2.7)", 2),
    ("=INT(-2.7)", -3),
    ("=INT(\"3.9\")", 3),
    ("=INT(A8)", {"error": "#VALUE!"}),
    ("=INT(TRUE)", 1),
    ("=INT(-0.5)", -1),
    ("=INT(5)", 5),
    ("=INT(A5)", 0),
    ("=INT(1/0)", {"error": "#DIV/0!"}),
    ("=MOD(10,3)", 1),
    ("=MOD(-10,3)", 2),
    ("=MOD(10,-3)", -2),
    ("=MOD(-10,-3)", -1),
    ("=MOD(5,0)", {"error": "#DIV/0!"}),
    ("=MOD(5.5,2)", 1.5),
    ("=MOD(0,5)", 0),
    ("=MOD(1/0,2)", {"error": "#DIV/0!"}),
    ("=MOD(7,1/0)", {"error": "#DIV/0!"}),
    ("=MOD(\"7\",2)", 1),
    ("=MOD(A8,2)", {"error": "#VALUE!"}),
    ("=MOD(-1.5,1)", 0.5),
    ("=MOD(3,A5)", {"error": "#DIV/0!"}),
    ("=ABS(-3.5)", 3.5),
    ("=ABS(\"-2\")", 2),
    ("=ABS(A8)", {"error": "#VALUE!"}),
    ("=ABS(A5)", 0),
    ("=ABS(C2)", {"error": "#DIV/0!"}),
    ("=ABS(TRUE)", 1),
    ("=ABS(0)", 0),
    ("=POWER(2,10)", 1024),
    ("=POWER(2,-1)", 0.5),
    ("=POWER(-8,1/3)", -2),
    ("=POWER(0,0)", 1),
    ("=POWER(0,-1)", {"error": "#NUM!"}),
    ("=POWER(-1,0.5)", {"error": "#NUM!"}),
    ("=POWER(\"2\",3)", 8),
    ("=POWER(4,0.5)", 2),
    ("=POWER(-2,3)", -8),
    ("=POWER(A8,2)", {"error": "#VALUE!"}),
    ("=POWER(1/0,2)", {"error": "#DIV/0!"}),
    ("=POWER(10,400)", {"error": "#NUM!"}),
    ("=SQRT(16)", 4),
    ("=SQRT(2)", 1.4142135623730951),
    ("=SQRT(-1)", {"error": "Err:502"}),
    ("=SQRT(0)", 0),
    ("=SQRT(\"9\")", 3),
    ("=SQRT(A8)", {"error": "#VALUE!"}),
    ("=SQRT(A5)", 0),
    ("=SQRT(C2)", {"error": "#DIV/0!"}),
    ("=SQRT(TRUE)", 1),
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
print("ok b2: %d cases match Calc" % len(CASES))
PY
