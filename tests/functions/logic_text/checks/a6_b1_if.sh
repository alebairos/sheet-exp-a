#!/bin/sh
# b1: IF and IFERROR match Calc.
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
    print("ok a6_b1_if: %d cases match Calc" % len(cases))


BOOK = json.loads(r"""{"sheets":{"Sheet1":{"A1":1,"A2":0,"A3":"abc","A4":true,"A6":"  hello   world  ","A7":{"error":"#N/A"},"A8":"3","A9":2.5,"A10":false,"A12":{"error":"#DIV/0!"},"A13":1234.5678,"A14":"Ünïcode straße","A15":-3,"A16":"TRUE","A17":0.1}}}""")
run(BOOK, json.loads(r"""[
["=IF(A1,\"y\",\"n\")","y"],
["=IF(A2,\"y\",\"n\")","n"],
["=IF(A3,\"y\",\"n\")",{"error":"#VALUE!"}],
["=IF(A5,\"y\",\"n\")","n"],
["=IF(A7,\"y\",\"n\")",{"error":"#N/A"}],
["=IF(1>2,\"y\")",false],
["=IF(1<2,\"y\")","y"],
["=IF(TRUE,,1)",0],
["=IF(FALSE,1)",false],
["=IF(\"TRUE\",1,2)",1],
["=IF(A8,1,2)",1],
["=IF(A9,\"y\",\"n\")","y"],
["=IF(1,A5)",0],
["=IF(1,1/0,2)",{"error":"#DIV/0!"}],
["=IF(0,1/0,2)",2],
["=IF(A4,\"t\",\"f\")","t"],
["=IF(A10,\"t\",\"f\")","f"],
["=IF(A16,1,2)",1],
["=IF(A12,1,2)",{"error":"#DIV/0!"}],
["=IF(-1,\"y\",\"n\")","y"],
["=IF(1,A3)","abc"],
["=IF(0,1)",false],
["=IF(1,\"\")",""],
["=IFERROR(1/0,\"e\")","e"],
["=IFERROR(A7,\"na\")","na"],
["=IFERROR(1,\"e\")",1],
["=IFERROR(A3,\"e\")","abc"],
["=IFERROR(A5,\"e\")",0],
["=IFERROR(A12,0)",0],
["=IFERROR(\"a\"+1,\"v\")","v"],
["=IFERROR(A4,0)",true],
["=IFERROR(1/0,1/0)",{"error":"#DIV/0!"}],
["=IFERROR(A7,A5)",0],
["=IFERROR(FOO(),\"n\")","n"],
["=IF(ISBLANK(A5),\"empty\",A5)","empty"],
["=IF(AND(A1>0,A9>2),\"both\",\"no\")","both"],
["=IFERROR(IF(A2,1,1/0),\"caught\")","caught"],
["=IF(OR(ISTEXT(A1),ISNUMBER(A1)),\"ok\",\"no\")","ok"]
]"""))
PY
