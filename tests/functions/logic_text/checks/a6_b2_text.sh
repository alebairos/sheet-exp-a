#!/bin/sh
# b2: CONCATENATE, LEFT, RIGHT, MID, LEN, UPPER, LOWER, TRIM match Calc, coercion and errors included.
# Contract (plan a-i6-logic-text): each function is registered with src.functions.register under
# src/functions/logic_text and called by src.eval (a-i3's convention: a reference arrives as a Range,
# any other argument as a Value, errors included; a function may return a Range). Every expected
# value below is LibreOffice Calc's own answer, computed headless over this exact fixture (TRUE/FALSE
# cells stored as Calc stores them: 1/0 with a boolean format; boolean results told apart by ISLOGICAL).
# Numbers become text as Calc shows them (15 significant digits), a TRUE cell is "1", a blank is "";
# counts are truncated, a negative count is Err:502, MID without its length is Err:511 (Calc's names);
# TRIM also collapses inner runs of spaces; UPPER/LOWER follow Unicode as Calc does (straße -> STRAẞE).
set -eu
cd "$(dirname "$0")/../../../.."
export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=utf-8
python3 - <<'PY'
import json
import sys

from src.eval import evaluate
from src.values import to_json

BOOK = json.loads(r"""{"sheets": {"Sheet1": {"A1": 1, "A2": 0, "A3": "abc", "A4": true, "A6": "  hello   world  ", "A7": {"error": "#N/A"}, "A8": "3", "A9": 2.5, "A10": false, "A12": {"error": "#DIV/0!"}, "A13": 1234.5678, "A14": "Ünïcode straße", "A15": -3, "A16": "TRUE", "A17": 0.1}}}""")

CASES = json.loads(r"""[
  ["=CONCATENATE(\"a\",\"b\")", "ab"],
  ["=CONCATENATE(A1,A3)", "1abc"],
  ["=CONCATENATE(A4,\"x\")", "1x"],
  ["=CONCATENATE(A9,\"-\",A13)", "2.5-1234.5678"],
  ["=CONCATENATE(A5,\"x\")", "x"],
  ["=CONCATENATE(A7,\"x\")", {"error": "#N/A"}],
  ["=CONCATENATE(1/3)", "0.333333333333333"],
  ["=CONCATENATE(TRUE)", "1"],
  ["=CONCATENATE(\"x\",1/0)", {"error": "#DIV/0!"}],
  ["=CONCATENATE(A15,A10)", "-30"],
  ["=CONCATENATE(0.1+0.2)", "0.3"],
  ["=CONCATENATE(-0.5)", "-0.5"],
  ["=CONCATENATE(123456789012)", "123456789012"],
  ["=CONCATENATE(A17*3)", "0.3"],
  ["=CONCATENATE(\"a\",,\"b\")", "ab"],
  ["=LEFT(\"hello\",2)", "he"],
  ["=LEFT(\"hello\")", "h"],
  ["=LEFT(\"hello\",0)", ""],
  ["=LEFT(\"hello\",10)", "hello"],
  ["=LEFT(\"hello\",-1)", {"error": "Err:502"}],
  ["=LEFT(A13,4)", "1234"],
  ["=LEFT(A4,2)", "1"],
  ["=LEFT(A5,2)", ""],
  ["=LEFT(A7,1)", {"error": "#N/A"}],
  ["=LEFT(\"abc\",1.9)", "a"],
  ["=LEFT(12345,2)", "12"],
  ["=LEFT(A14,3)", "Ünï"],
  ["=LEFT(\"abc\",A3)", {"error": "#VALUE!"}],
  ["=LEFT(\"abc\",\"2\")", "ab"],
  ["=LEFT(\"x\",1/0)", {"error": "#DIV/0!"}],
  ["=RIGHT(\"hello\",3)", "llo"],
  ["=RIGHT(\"hello\")", "o"],
  ["=RIGHT(\"hello\",10)", "hello"],
  ["=RIGHT(A9,2)", ".5"],
  ["=RIGHT(\"x\",-1)", {"error": "Err:502"}],
  ["=RIGHT(A15,1)", "3"],
  ["=RIGHT(A10,2)", "0"],
  ["=RIGHT(\"hello\",0)", ""],
  ["=RIGHT(A14,4)", "raße"],
  ["=MID(\"hello\",2,3)", "ell"],
  ["=MID(\"hello\",0,2)", {"error": "Err:502"}],
  ["=MID(\"hello\",5,10)", "o"],
  ["=MID(\"hello\",6,1)", ""],
  ["=MID(\"hello\",2,0)", ""],
  ["=MID(\"hello\",1,-1)", {"error": "Err:502"}],
  ["=MID(A13,3,4)", "34.5"],
  ["=MID(\"hello\",1.5,2.9)", "he"],
  ["=MID(A7,1,1)", {"error": "#N/A"}],
  ["=MID(\"hello\",2)", {"error": "Err:511"}],
  ["=MID(A14,2,5)", "nïcod"],
  ["=MID(TRUE,1,1)", "1"],
  ["=MID(\"hello\",10,1)", ""],
  ["=LEN(\"hello\")", 5],
  ["=LEN(\"\")", 0],
  ["=LEN(A5)", 0],
  ["=LEN(A1)", 1],
  ["=LEN(A9)", 3],
  ["=LEN(A6)", 17],
  ["=LEN(A14)", 14],
  ["=LEN(A7)", {"error": "#N/A"}],
  ["=LEN(1/3)", 17],
  ["=LEN(A4)", 1],
  ["=LEN(0.1+0.2)", 3],
  ["=LEN(A13)", 9],
  ["=LEN(-1)", 2],
  ["=LEN(A16)", 4],
  ["=UPPER(\"abc\")", "ABC"],
  ["=UPPER(A14)", "ÜNÏCODE STRAẞE"],
  ["=UPPER(A1)", "1"],
  ["=UPPER(A4)", "1"],
  ["=UPPER(A5)", ""],
  ["=UPPER(A7)", {"error": "#N/A"}],
  ["=UPPER(\"MiXeD 1\")", "MIXED 1"],
  ["=LOWER(\"ABC Déf\")", "abc déf"],
  ["=LOWER(A5)", ""],
  ["=LOWER(A7)", {"error": "#N/A"}],
  ["=LOWER(A10)", "0"],
  ["=LOWER(A14)", "ünïcode straße"],
  ["=LOWER(2.50)", "2.5"],
  ["=TRIM(A6)", "hello world"],
  ["=TRIM(\"  a  \")", "a"],
  ["=TRIM(A1)", "1"],
  ["=TRIM(A5)", ""],
  ["=TRIM(\"a  b   c\")", "a b c"],
  ["=TRIM(A7)", {"error": "#N/A"}],
  ["=TRIM(A4)", "1"],
  ["=TRIM(\"   \")", ""],
  ["=TRIM(A9)", "2.5"],
  ["=LEN(TRIM(A6))", 11],
  ["=UPPER(LEFT(A3,1))&MID(A3,2,10)", "Abc"],
  ["=CONCATENATE(LEFT(A14,2),RIGHT(A14,2))", "Ünße"],
  ["=LEN(CONCATENATE(A1,A9))", 4]
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
