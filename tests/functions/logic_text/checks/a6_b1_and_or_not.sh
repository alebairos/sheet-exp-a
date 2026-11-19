#!/bin/sh
# b1: AND, OR and NOT match Calc.
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
    print("ok a6_b1_and_or_not: %d cases match Calc" % len(cases))


BOOK = json.loads(r"""{"sheets":{"Sheet1":{"A1":1,"A2":0,"A3":"abc","A4":true,"A6":"  hello   world  ","A7":{"error":"#N/A"},"A8":"3","A9":2.5,"A10":false,"A12":{"error":"#DIV/0!"},"A13":1234.5678,"A14":"Ünïcode straße","A15":-3,"A16":"TRUE","A17":0.1}}}""")
run(BOOK, json.loads(r"""[
["=AND(1,1)",true],
["=AND(1,0)",false],
["=AND(A1:A2)",false],
["=AND(A3)",{"error":"#VALUE!"}],
["=AND(A4,A1)",true],
["=AND(A5)",{"error":"#VALUE!"}],
["=AND(TRUE,\"x\")",{"error":"#VALUE!"}],
["=AND(A7,1)",{"error":"#N/A"}],
["=AND(A1:A10)",{"error":"#N/A"}],
["=AND(\"TRUE\")",{"error":"#VALUE!"}],
["=AND(2)",true],
["=AND(A1,A3)",true],
["=AND(A1:A4)",false],
["=AND(A16)",{"error":"#VALUE!"}],
["=AND(1/0,0)",{"error":"#DIV/0!"}],
["=AND(A9,A15)",true],
["=OR(0,0)",false],
["=OR(0,1)",true],
["=OR(A2,A10)",false],
["=OR(A3)",{"error":"#VALUE!"}],
["=OR(A7,1)",{"error":"#N/A"}],
["=OR(A1:A3)",true],
["=OR(A5,A2)",false],
["=OR(\"FALSE\",1)",{"error":"#VALUE!"}],
["=OR(A2:A3)",false],
["=OR(A12,1)",{"error":"#DIV/0!"}],
["=NOT(1)",false],
["=NOT(0)",true],
["=NOT(A3)",{"error":"#VALUE!"}],
["=NOT(A5)",true],
["=NOT(A7)",{"error":"#N/A"}],
["=NOT(\"1\")",false],
["=NOT(2.5)",false],
["=NOT(A4)",false],
["=NOT(A16)",false],
["=NOT(\"TRUE\")",false],
["=NOT(A1:A2)",{"error":"#VALUE!"}],
["=NOT(ISERROR(A1))",true]
]"""))
PY
