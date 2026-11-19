#!/bin/sh
# b2: INDEX and MATCH (types 0 and 1) match Calc, errors included.
# Contract (plan a-i7-lookup): VLOOKUP, INDEX and MATCH are registered with src.functions.register under
# src/functions/lookup and called by src.eval (a-i3's convention: a reference arrives as a Range, any
# other argument as a Value, errors included; a function may return a Range). Every expected value
# below is LibreOffice Calc's own answer, computed headless over this exact fixture.
# INDEX(range,row[,col]): 1-based, truncated, a one-row range takes a single index as the column; outside
# the range #REF!, negative Err:502, a whole row or column in one cell #VALUE!. MATCH type 0 first equal
# (wildcards, case-insensitive), type 1 (default) last <= in a sorted vector; #N/A when nothing fits;
# a two-dimensional range or type 2 is Err:504.
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
  ["=INDEX(A1:C5,2,2)", "twenty"],
  ["=INDEX(A1:C5,2)", {"error": "#VALUE!"}],
  ["=INDEX(A1:A5,3)", 30],
  ["=INDEX(A1:C5,6,1)", {"error": "#REF!"}],
  ["=INDEX(A1:C5,1,4)", {"error": "#REF!"}],
  ["=INDEX(I1:L1,3)", 15],
  ["=INDEX(I1:L1,1,3)", 15],
  ["=INDEX(A1:C5,-1,1)", {"error": "Err:502"}],
  ["=INDEX(A1:C5,\"2\",2)", "twenty"],
  ["=INDEX(A1:C5,2.7,1)", 20],
  ["=INDEX(A1:C5,5,3)", 0],
  ["=INDEX(A1:C5,3,3)", {"error": "#N/A"}],
  ["=INDEX(A1:A5,1/0)", {"error": "#DIV/0!"}],
  ["=INDEX(A1:C5,MATCH(40,A1:A5,0),2)", "forty"],
  ["=INDEX(A1:C5,1,1)", 10],
  ["=INDEX(B1:B5,5)", "fifty"],
  ["=INDEX(Sheet2!A1:B2,2,2)", 200],
  ["=INDEX(A1:A5,0)", {"error": "#VALUE!"}],
  ["=INDEX(A1:A5,6)", {"error": "#REF!"}],
  ["=INDEX(A1:C5,0,0)", {"error": "#VALUE!"}],
  ["=INDEX(I1:L2,2,4)", "d"],
  ["=INDEX(I1:L2,2)", {"error": "#VALUE!"}],
  ["=INDEX(A1:A5,2,1)", 20],
  ["=INDEX(A1:A5,2,2)", {"error": "#REF!"}],
  ["=INDEX(A1:C5,\"x\",1)", {"error": "#VALUE!"}],
  ["=INDEX(A1:C5,3,2)&\"?\"", "thirty?"],
  ["=INDEX(G1:G7,6)", 0],
  ["=INDEX(A1:C5,MATCH(\"fifty\",B1:B5,0),1)", 50],
  ["=MATCH(30,A1:A5,0)", 3],
  ["=MATCH(35,A1:A5,0)", {"error": "#N/A"}],
  ["=MATCH(35,A1:A5,1)", 3],
  ["=MATCH(35,A1:A5)", 3],
  ["=MATCH(5,A1:A5,1)", {"error": "#N/A"}],
  ["=MATCH(99,A1:A5,1)", 5],
  ["=MATCH(\"BANANA\",E1:E5,0)", 2],
  ["=MATCH(\"b*\",E1:E5,0)", 2],
  ["=MATCH(\"d?te\",E1:E5,0)", 4],
  ["=MATCH(\"cat\",E1:E5,1)", 2],
  ["=MATCH(15,I1:L1,1)", 3],
  ["=MATCH(15,I1:L1,0)", 3],
  ["=MATCH(12,I1:L1)", 2],
  ["=MATCH(3,G1:G7,0)", 1],
  ["=MATCH(\"3\",G1:G7,0)", 1],
  ["=MATCH(2,M1:M5,0)", 2],
  ["=MATCH(2,M1:M5,1)", 4],
  ["=MATCH(30,A1:C5,0)", {"error": "Err:504"}],
  ["=MATCH(1/0,A1:A5,0)", {"error": "#DIV/0!"}],
  ["=MATCH(30,A1:A5,2)", {"error": "Err:504"}],
  ["=MATCH(\"zzz\",E1:E5,1)", 5],
  ["=MATCH(\"a\",E1:E5,1)", {"error": "#N/A"}],
  ["=MATCH(\"x\",G1:G7,0)", 2],
  ["=MATCH(30,A1:A5,\"x\")", {"error": "#VALUE!"}],
  ["=MATCH(10,A1:A5,0)", 1],
  ["=MATCH(\"c\",I2:L2,0)", 3],
  ["=MATCH(\"cc\",I2:L2,1)", 3],
  ["=MATCH(50,A1:A5,1)", 5],
  ["=MATCH(30,A3,0)", 1],
  ["=MATCH(30,A1:A5,0.5)", 3],
  ["=MATCH(1,G1:G7,0)", 3],
  ["=MATCH(P1,A1:A5,1)", {"error": "#N/A"}],
  ["=MATCH(\"*\",E1:E5,0)", 1],
  ["=MATCH(2.5,M1:M5,1)", 4]
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
print("ok b2: %d cases match Calc" % len(CASES))
PY
