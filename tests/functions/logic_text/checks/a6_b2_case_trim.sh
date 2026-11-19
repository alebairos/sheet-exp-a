#!/bin/sh
# b2: UPPER, LOWER and TRIM match Calc, coercion and errors included.
# Plan a-i6-logic-text: each case is a formula and LibreOffice Calc's own answer, computed headless over
# BOOK (TRUE/FALSE cells stored as Calc does). Passes only if src.eval gives every answer, same type.
set -eu
cd "$(dirname "$0")/../../../.."
export PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
python3 - <<'PY'
import json, sys
from src.eval import evaluate
from src.values import to_json


def same(got, want):  # type-strict: True never passes as 1, 1 never as "1"
    if isinstance(want, (bool, str, dict)) or want is None:
        return type(got) is type(want) and got == want
    return (type(got) in (int, float) and not isinstance(got, bool)
            and abs(got - want) <= 1e-9 * max(1.0, abs(want)))


def run(book, cases):
    bad = 0
    for formula, want in cases:
        try:
            got = to_json(evaluate(formula, book, "Sheet1"))
        except Exception as e:  # noqa: BLE001 - a crash is a failure
            got = "raised %s: %s" % (type(e).__name__, e)
        if not same(got, want):
            bad += 1
            print("FAIL %s: got %s, want %s" % (formula, json.dumps(got, ensure_ascii=False), json.dumps(want, ensure_ascii=False)))
    if bad or not cases:
        sys.exit("%d of %d cases differ from Calc" % (bad, len(cases)))
    print("ok a6_b2_case_trim: %d cases match Calc" % len(cases))


BOOK = json.loads(r"""{"sheets":{"Sheet1":{"A1":1,"A2":0,"A3":"abc","A4":true,"A6":"  hello   world  ","A7":{"error":"#N/A"},"A8":"3","A9":2.5,"A10":false,"A12":{"error":"#DIV/0!"},"A13":1234.5678,"A14":"Ünïcode straße","A15":-3,"A16":"TRUE","A17":0.1}}}""")
run(BOOK, json.loads(r"""[
["=UPPER(\"abc\")","ABC"],
["=UPPER(A14)","ÜNÏCODE STRAẞE"],
["=UPPER(A1)","1"],
["=UPPER(A4)","1"],
["=UPPER(A5)",""],
["=UPPER(A7)",{"error":"#N/A"}],
["=UPPER(\"MiXeD 1\")","MIXED 1"],
["=LOWER(\"ABC Déf\")","abc déf"],
["=LOWER(A5)",""],
["=LOWER(A7)",{"error":"#N/A"}],
["=LOWER(A10)","0"],
["=LOWER(A14)","ünïcode straße"],
["=LOWER(2.50)","2.5"],
["=TRIM(A6)","hello world"],
["=TRIM(\"  a  \")","a"],
["=TRIM(A1)","1"],
["=TRIM(A5)",""],
["=TRIM(\"a  b   c\")","a b c"],
["=TRIM(A7)",{"error":"#N/A"}],
["=TRIM(A4)","1"],
["=TRIM(\"   \")",""],
["=TRIM(A9)","2.5"],
["=UPPER(LEFT(A3,1))&MID(A3,2,10)","Abc"]
]"""))
PY
