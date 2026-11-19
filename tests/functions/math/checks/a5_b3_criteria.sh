#!/bin/sh
# b3: SUMIF, COUNTIF, AVERAGEIF match Calc's criteria.
# Contract (plan a-i5-math): each function is registered with src.functions.register under
# src/functions/math and called by src.eval (a-i3's convention: a reference arrives as a Range, any
# other argument as a Value). Every expected value below is LibreOffice Calc's own answer, computed
# headless over this exact fixture (TRUE/FALSE cells stored as Calc stores them: 1/0, boolean format).
# Criteria as Calc: = <> < > <= >= prefixes, a number matches numbers (and a numeric criterion text
# also matches text that equals it), text matches case-insensitively with * ? ~ wildcards, "" and "=" match
# blanks, "<>" non-blanks; a shorter sum range is extended from its top-left cell.
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
    ("=SUMIF(F1:F8,\">4\")", 26),
    ("=SUMIF(E1:E8,\"apple\",F1:F8)", 4),
    ("=SUMIF(E1:E8,\"<>apple\",F1:F8)", 32),
    ("=SUMIF(F1:F8,\"<\"&F3)", 3),
    ("=SUMIF(E1:E8,\"b*\",F1:F8)", 9),
    ("=SUMIF(F1:F8,\">100\")", 0),
    ("=SUMIF(E1:E8,\"cherry\",F1)", 4),
    ("=SUMIF(E1:E8,\"apple\",F1:F2)", 4),
    ("=SUMIF(E1:E9,10,F1:F9)", 5),
    ("=SUMIF(F1:F8,4)", 4),
    ("=SUMIF(F1:F8,\"4\")", 4),
    ("=SUMIF(F1:F8,\"=4\")", 4),
    ("=SUMIF(F1:F8,\"<=3\")", 6),
    ("=SUMIF(F1:F8,\">=7\")", 15),
    ("=SUMIF(E1:E8,\"*an*\",F1:F8)", 2),
    ("=SUMIF(E1:E8,\"?pple\",F1:F8)", 4),
    ("=SUMIF(A1:A8,\">1\")", 6.5),
    ("=SUMIF(C1:C3,\">0\")", 3),
    ("=SUMIF(B1:B6,1)", 2),
    ("=SUMIF(E1:E9,\"\",F1:F9)", 8),
    ("=COUNTIF(E1:E8,\"apple\")", 2),
    ("=COUNTIF(E1:E8,\"a*\")", 2),
    ("=COUNTIF(F1:F8,\">=3\")", 6),
    ("=COUNTIF(F1:F8,\"<>4\")", 7),
    ("=COUNTIF(E1:E8,\"<>apple\")", 6),
    ("=COUNTIF(E1:E9,10)", 1),
    ("=COUNTIF(E1:E9,\"10\")", 2),
    ("=COUNTIF(E1:E8,\">15\")", 1),
    ("=COUNTIF(E1:E8,\"b?nana\")", 1),
    ("=COUNTIF(E1:E9,\"\")", 1),
    ("=COUNTIF(E1:E9,\"=\")", 1),
    ("=COUNTIF(E1:E9,\"<>\")", 8),
    ("=COUNTIF(E1:E9,\"*\")", 8),
    ("=COUNTIF(A1:A8,3)", 0),
    ("=COUNTIF(A1:A8,\"3\")", 1),
    ("=COUNTIF(A1:A8,TRUE)", 2),
    ("=COUNTIF(H1:H3,FALSE)", 2),
    ("=COUNTIF(E1:E8,\"b*n\")", 1),
    ("=COUNTIF(E1:E8,\"APPLE\")", 2),
    ("=COUNTIF(C1:C3,\">0\")", 2),
    ("=COUNTIF(F1:F8,\">\"&\"5\")", 3),
    ("=COUNTIF(E1:E8,\"<c\")", 4),
    ("=COUNTIF(E1:E8,\">=b\")", 3),
    ("=COUNTIF(G1:G5,\"\")", 5),
    ("=COUNTIF(F1:F8,\"abc\")", 0),
    ("=COUNTIF(B1:B6,1)", 2),
    ("=COUNTIF(E1:E8,\"~*\")", 0),
    ("=COUNTIF(F1:F8,\"<>\")", 8),
    ("=COUNTIF(A1:A8,\"<>3\")", 7),
    ("=AVERAGEIF(F1:F8,\">4\")", 6.5),
    ("=AVERAGEIF(E1:E8,\"apple\",F1:F8)", 2),
    ("=AVERAGEIF(F1:F8,\">100\")", {"error": "#DIV/0!"}),
    ("=AVERAGEIF(E1:E8,\"cherry\",F1:F8)", 4),
    ("=AVERAGEIF(E1:E8,\"b*\",F1:F8)", 4.5),
    ("=AVERAGEIF(A1:A8,\">0\")", 2.125),
    ("=AVERAGEIF(E1:E9,10,F1:F9)", 5),
    ("=AVERAGEIF(F1:F8,\"<>4\")", 4.571428571428571),
    ("=AVERAGEIF(C1:C3,\">0\")", 1.5),
    ("=AVERAGEIF(E1:E8,\"apple\",F1)", 2),
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
print("ok b3: %d cases match Calc" % len(CASES))
PY
