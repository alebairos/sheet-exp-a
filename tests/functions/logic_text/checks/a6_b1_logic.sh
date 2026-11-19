#!/bin/sh
# b1: IF, IFERROR, AND, OR, NOT, ISBLANK, ISNUMBER, ISTEXT, ISERROR match Calc.
# Contract (plan a-i6-logic-text): functions registered under src/functions/logic_text, called by
# src.eval (a-i3). Expected values: LibreOffice Calc's own answers over this fixture (TRUE/FALSE cells
# stored as Calc does: 1/0, boolean format).
# IF returns a reference as a reference (ISBLANK(IF(1,A5)) is TRUE), a missing branch FALSE;
# AND/OR skip text in ranges; a TRUE cell is a number to ISNUMBER; errors reach IFERROR, ISERROR.
set -eu
cd "$(dirname "$0")/../../../.."
export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=utf-8
python3 - <<'PY'
import json
import sys

from src.eval import evaluate
from src.values import to_json

BOOK = json.loads(r"""{"sheets":{"Sheet1":{"A1":1,"A2":0,"A3":"abc","A4":true,"A6":"  hello   world  ","A7":{"error":"#N/A"},"A8":"3","A9":2.5,"A10":false,"A12":{"error":"#DIV/0!"},"A13":1234.5678,"A14":"Ünïcode straße","A15":-3,"A16":"TRUE","A17":0.1}}}""")

CASES = json.loads(r"""[
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
["=ISERROR(Nope!A1)",true],
["=IF(ISBLANK(A5),\"empty\",A5)","empty"],
["=IF(AND(A1>0,A9>2),\"both\",\"no\")","both"],
["=IFERROR(IF(A2,1,1/0),\"caught\")","caught"],
["=IF(OR(ISTEXT(A1),ISNUMBER(A1)),\"ok\",\"no\")","ok"],
["=NOT(ISERROR(A1))",true]
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
