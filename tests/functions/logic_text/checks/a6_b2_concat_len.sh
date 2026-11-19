#!/bin/sh
# b2: CONCATENATE and LEN match Calc, coercion and errors included.
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
    print("ok a6_b2_concat_len: %d cases match Calc" % len(cases))


BOOK = json.loads(r"""{"sheets":{"Sheet1":{"A1":1,"A2":0,"A3":"abc","A4":true,"A6":"  hello   world  ","A7":{"error":"#N/A"},"A8":"3","A9":2.5,"A10":false,"A12":{"error":"#DIV/0!"},"A13":1234.5678,"A14":"Ünïcode straße","A15":-3,"A16":"TRUE","A17":0.1}}}""")
run(BOOK, json.loads(r"""[
["=CONCATENATE(\"a\",\"b\")","ab"],
["=CONCATENATE(A1,A3)","1abc"],
["=CONCATENATE(A4,\"x\")","1x"],
["=CONCATENATE(A9,\"-\",A13)","2.5-1234.5678"],
["=CONCATENATE(A5,\"x\")","x"],
["=CONCATENATE(A7,\"x\")",{"error":"#N/A"}],
["=CONCATENATE(1/3)","0.333333333333333"],
["=CONCATENATE(TRUE)","1"],
["=CONCATENATE(\"x\",1/0)",{"error":"#DIV/0!"}],
["=CONCATENATE(A15,A10)","-30"],
["=CONCATENATE(0.1+0.2)","0.3"],
["=CONCATENATE(-0.5)","-0.5"],
["=CONCATENATE(123456789012)","123456789012"],
["=CONCATENATE(A17*3)","0.3"],
["=CONCATENATE(\"a\",,\"b\")","ab"],
["=LEN(\"hello\")",5],
["=LEN(\"\")",0],
["=LEN(A5)",0],
["=LEN(A1)",1],
["=LEN(A9)",3],
["=LEN(A6)",17],
["=LEN(A14)",14],
["=LEN(A7)",{"error":"#N/A"}],
["=LEN(1/3)",17],
["=LEN(A4)",1],
["=LEN(0.1+0.2)",3],
["=LEN(A13)",9],
["=LEN(-1)",2],
["=LEN(A16)",4],
["=LEN(TRIM(A6))",11],
["=CONCATENATE(LEFT(A14,2),RIGHT(A14,2))","Ünße"],
["=LEN(CONCATENATE(A1,A9))",4]
]"""))
PY
