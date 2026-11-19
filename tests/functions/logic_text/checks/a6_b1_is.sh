#!/bin/sh
# b1: ISBLANK, ISNUMBER, ISTEXT and ISERROR match Calc.
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
    print("ok a6_b1_is: %d cases match Calc" % len(cases))


BOOK = json.loads(r"""{"sheets":{"Sheet1":{"A1":1,"A2":0,"A3":"abc","A4":true,"A6":"  hello   world  ","A7":{"error":"#N/A"},"A8":"3","A9":2.5,"A10":false,"A12":{"error":"#DIV/0!"},"A13":1234.5678,"A14":"Ünïcode straße","A15":-3,"A16":"TRUE","A17":0.1}}}""")
run(BOOK, json.loads(r"""[
["=ISBLANK(A5)",true],
["=ISBLANK(A3)",false],
["=ISBLANK(\"\")",false],
["=ISBLANK(A2)",false],
["=ISBLANK(X99)",true],
["=ISBLANK(A7)",false],
["=ISBLANK(A5+0)",false],
["=ISBLANK(IF(1,A5))",true],
["=ISNUMBER(A1)",true],
["=ISNUMBER(A8)",false],
["=ISNUMBER(A4)",true],
["=ISNUMBER(\"3\")",false],
["=ISNUMBER(A5)",false],
["=ISNUMBER(A7)",false],
["=ISNUMBER(1/0)",false],
["=ISNUMBER(TRUE)",true],
["=ISNUMBER(A9)",true],
["=ISNUMBER(A8*1)",true],
["=ISTEXT(A3)",true],
["=ISTEXT(A8)",true],
["=ISTEXT(A1)",false],
["=ISTEXT(A5)",false],
["=ISTEXT(A7)",false],
["=ISTEXT(\"x\")",true],
["=ISTEXT(A4)",false],
["=ISTEXT(A16)",true],
["=ISTEXT(1)",false],
["=ISTEXT(\"\")",true],
["=ISERROR(A7)",true],
["=ISERROR(A12)",true],
["=ISERROR(1/0)",true],
["=ISERROR(A3)",false],
["=ISERROR(A5)",false],
["=ISERROR(\"#N/A\")",false],
["=ISERROR(FOO())",true],
["=ISERROR(A3+1)",true],
["=ISERROR(Nope!A1)",true]
]"""))
PY
