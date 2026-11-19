#!/bin/sh
# b2: LEFT, RIGHT and MID match Calc, coercion and errors included.
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
    print("ok a6_b2_left_right_mid: %d cases match Calc" % len(cases))


BOOK = json.loads(r"""{"sheets":{"Sheet1":{"A1":1,"A2":0,"A3":"abc","A4":true,"A6":"  hello   world  ","A7":{"error":"#N/A"},"A8":"3","A9":2.5,"A10":false,"A12":{"error":"#DIV/0!"},"A13":1234.5678,"A14":"Ünïcode straße","A15":-3,"A16":"TRUE","A17":0.1}}}""")
run(BOOK, json.loads(r"""[
["=LEFT(\"hello\",2)","he"],
["=LEFT(\"hello\")","h"],
["=LEFT(\"hello\",0)",""],
["=LEFT(\"hello\",10)","hello"],
["=LEFT(\"hello\",-1)",{"error":"Err:502"}],
["=LEFT(A13,4)","1234"],
["=LEFT(A4,2)","1"],
["=LEFT(A5,2)",""],
["=LEFT(A7,1)",{"error":"#N/A"}],
["=LEFT(\"abc\",1.9)","a"],
["=LEFT(12345,2)","12"],
["=LEFT(A14,3)","Ünï"],
["=LEFT(\"abc\",A3)",{"error":"#VALUE!"}],
["=LEFT(\"abc\",\"2\")","ab"],
["=LEFT(\"x\",1/0)",{"error":"#DIV/0!"}],
["=RIGHT(\"hello\",3)","llo"],
["=RIGHT(\"hello\")","o"],
["=RIGHT(\"hello\",10)","hello"],
["=RIGHT(A9,2)",".5"],
["=RIGHT(\"x\",-1)",{"error":"Err:502"}],
["=RIGHT(A15,1)","3"],
["=RIGHT(A10,2)","0"],
["=RIGHT(\"hello\",0)",""],
["=RIGHT(A14,4)","raße"],
["=MID(\"hello\",2,3)","ell"],
["=MID(\"hello\",0,2)",{"error":"Err:502"}],
["=MID(\"hello\",5,10)","o"],
["=MID(\"hello\",6,1)",""],
["=MID(\"hello\",2,0)",""],
["=MID(\"hello\",1,-1)",{"error":"Err:502"}],
["=MID(A13,3,4)","34.5"],
["=MID(\"hello\",1.5,2.9)","he"],
["=MID(A7,1,1)",{"error":"#N/A"}],
["=MID(\"hello\",2)",{"error":"Err:511"}],
["=MID(A14,2,5)","nïcod"],
["=MID(TRUE,1,1)","1"],
["=MID(\"hello\",10,1)",""]
]"""))
PY
