#!/bin/sh
# b1: VLOOKUP exact and sorted approximate match Calc.
# Contract (plan a-i7-lookup): VLOOKUP, INDEX and MATCH are registered with src.functions.register under
# src/functions/lookup and called by src.eval (a-i3's convention: a reference arrives as a Range, any
# other argument as a Value, errors included; a function may return a Range). Every expected value
# below is LibreOffice Calc's own answer, computed headless over this exact fixture.
# Exact (0/FALSE): first match, text case-insensitive with * ? ~ wildcards, numeric text matches a number;
# approximate (1/TRUE/omitted, any non-zero): the last row whose key is <= the value in a sorted column
# (the last of equal keys), #N/A below the first; a column index outside the table is Err:502 (Calc's name).
set -eu
cd "$(dirname "$0")/../../../.."
export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=utf-8
python3 - <<'PY'
import json
import sys

from src.eval import evaluate
from src.values import to_json

BOOK = json.loads(r"""{"sheets": {"Sheet1": {"A1": 10, "B1": "ten", "C1": 1.5, "A2": 20, "B2": "twenty", "C2": 2.5, "A3": 30, "B3": "thirty", "C3": {"error": "#N/A"}, "A4": 40, "B4": "forty", "C4": 4, "A5": 50, "B5": "fifty", "E1": "apple", "F1": 1, "E2": "Banana", "F2": 2, "E3": "cherry", "F3": 3, "E4": "date", "F4": 4, "E5": "fig", "F5": 5, "G1": 3, "G2": "x", "G3": 1, "G4": 3, "G5": true, "G7": "3", "I1": 5, "J1": 10, "K1": 15, "L1": 20, "I2": "a", "J2": "b", "K2": "c", "L2": "d", "M1": 1, "N1": "a", "M2": 2, "N2": "b", "M3": 2, "N3": "c", "M4": 2, "N4": "d", "M5": 3, "N5": "e", "P1": 7}, "Sheet2": {"A1": "k1", "B1": 100, "A2": "k2", "B2": 200}}}""")

CASES = json.loads(r"""[
  ["=VLOOKUP(30,A1:C5,2,0)", "thirty"],
  ["=VLOOKUP(30,A1:C5,2,FALSE)", "thirty"],
  ["=VLOOKUP(35,A1:C5,2,0)", {"error": "#N/A"}],
  ["=VLOOKUP(35,A1:C5,2,1)", "thirty"],
  ["=VLOOKUP(35,A1:C5,2)", "thirty"],
  ["=VLOOKUP(5,A1:C5,2,1)", {"error": "#N/A"}],
  ["=VLOOKUP(99,A1:C5,2)", "fifty"],
  ["=VLOOKUP(30,A1:C5,4,0)", {"error": "Err:502"}],
  ["=VLOOKUP(30,A1:C5,0,0)", {"error": "Err:502"}],
  ["=VLOOKUP(30,A1:C5,1,0)", 30],
  ["=VLOOKUP(50,A1:C5,3,0)", 0],
  ["=VLOOKUP(\"30\",A1:C5,2,0)", "thirty"],
  ["=VLOOKUP(\"banana\",E1:F5,2,0)", 2],
  ["=VLOOKUP(\"b*\",E1:F5,2,0)", 2],
  ["=VLOOKUP(\"c?erry\",E1:F5,2,0)", 3],
  ["=VLOOKUP(\"cat\",E1:F5,2,1)", 2],
  ["=VLOOKUP(\"zzz\",E1:F5,2,TRUE)", 5],
  ["=VLOOKUP(\"a\",E1:F5,2,1)", {"error": "#N/A"}],
  ["=VLOOKUP(1/0,A1:C5,2,0)", {"error": "#DIV/0!"}],
  ["=VLOOKUP(30,A1:C5,\"2\",0)", "thirty"],
  ["=VLOOKUP(30,A1:C5,2.9,0)", "thirty"],
  ["=VLOOKUP(20,A1:C5,3,0)", 2.5],
  ["=VLOOKUP(40,A1:C5,3,1)", 4],
  ["=VLOOKUP(30,A1:C5,3,0)", {"error": "#N/A"}],
  ["=VLOOKUP(3,G1:G7,1,0)", 3],
  ["=VLOOKUP(\"3\",G1:G7,1,0)", 3],
  ["=VLOOKUP(\"k2\",Sheet2!A1:B2,2,0)", 200],
  ["=VLOOKUP(\"fig\",E1:F5,2,0)", 5],
  ["=VLOOKUP(2,M1:N5,2,0)", "b"],
  ["=VLOOKUP(2,M1:N5,2,1)", "d"],
  ["=VLOOKUP(2.5,M1:N5,2,1)", "d"],
  ["=VLOOKUP(10,A1:C5,2,1)", "ten"],
  ["=VLOOKUP(50,A1:C5,2,1)", "fifty"],
  ["=VLOOKUP(P1,A1:C5,2,1)", {"error": "#N/A"}],
  ["=VLOOKUP(30,A1:C5,-1,0)", {"error": "Err:502"}],
  ["=VLOOKUP(30,A1:C5,2,\"x\")", {"error": "#VALUE!"}],
  ["=VLOOKUP(30,A1:C5,2,2)", "thirty"],
  ["=VLOOKUP(A5,A1:C5,2,0)", "fifty"],
  ["=VLOOKUP(\"Apple\",E1:F5,2,0)", 1],
  ["=VLOOKUP(\"~*\",E1:F5,2,0)", {"error": "#N/A"}],
  ["=VLOOKUP(30,A1:A5,1,0)", 30],
  ["=VLOOKUP(30,A1:C5,2,0)&\"!\"", "thirty!"]
]""")


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
        print("FAIL %s: got %s, want %s (Calc)" % (formula, json.dumps(got, ensure_ascii=False),
                                                   json.dumps(want, ensure_ascii=False)))
if bad:
    print("%d of %d cases differ from Calc" % (bad, len(CASES)))
    sys.exit(1)
print("ok b1: %d cases match Calc" % len(CASES))
PY
