#!/bin/sh
# b2: an edit recomputes only its dependents.
# Contract (plan a-i4-recalc): src.recalc.Workbook(book) computes a workbook (SPEC.md's JSON);
# .computed() returns the computed workbook as the CLI prints it; .set(sheet, addr, raw) sets one
# cell as typed (a "=..." string is a formula, None blanks it) and returns the set of (sheet, addr)
# formula cells it recomputed: exactly the formulas that read the edited cell, directly, through a
# range or through other formulas, on any sheet. Every other formula is not evaluated again (a probe
# function counts evaluations), and .computed() always equals src.recalc.compute() of the edited book.
set -eu
cd "$(dirname "$0")/../../.."
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
import copy
import json
import sys

from src.eval import Range
from src.functions import register
from src.recalc import Workbook, compute

ticks = []


@register("ZZTICK")
def _tick(label, x):
    # Records each evaluation of the formula labelled `label`; returns x (a range's first cell).
    ticks.append(label.value)
    return x.values()[0] if isinstance(x, Range) else x


raw = {"sheets": {
    "Sheet1": {
        "A1": 1, "A2": 2,
        "B1": "=A1*2",
        "C1": "=ZZTICK(\"C1\",B1)+1",
        "D1": 5,
        "E1": "=ZZTICK(\"E1\",D1)",
        "G1": "=ZZTICK(\"G1\",A2:A3)",
    },
    "Sheet2": {"A1": "=ZZTICK(\"S2\",Sheet1!B1)", "B1": "=ZZTICK(\"S2B\",Sheet2!A1)"},
}}
bad = 0


def fail(msg):
    global bad
    bad += 1
    print("FAIL " + msg)


wb = Workbook(copy.deepcopy(raw))
if sorted(ticks) != ["C1", "E1", "G1", "S2", "S2B"]:
    fail("the first computation should evaluate each formula once, got %s" % sorted(ticks))

S1 = lambda *a: {("Sheet1", x) for x in a}
steps = [
    # (sheet, addr, raw), recomputed cells, probes that must tick
    (("Sheet1", "A1", 10), S1("B1", "C1") | {("Sheet2", "A1"), ("Sheet2", "B1")}, ["C1", "S2", "S2B"]),
    (("Sheet1", "A3", 7), S1("G1"), ["G1"]),            # inside G1's range, was blank
    (("Sheet1", "Z9", 1), set(), []),                   # nothing reads it
    (("Sheet1", "D1", "=A1+1"), S1("D1", "E1"), ["E1"]),  # a constant becomes a formula
    (("Sheet1", "A1", 1), S1("B1", "C1", "D1", "E1") | {("Sheet2", "A1"), ("Sheet2", "B1")},
     ["C1", "E1", "S2", "S2B"]),                       # ...and now depends on A1
    (("Sheet1", "D1", 3), S1("E1"), ["E1"]),            # a formula becomes a constant
    (("Sheet1", "A1", 4), S1("B1", "C1") | {("Sheet2", "A1"), ("Sheet2", "B1")}, ["C1", "S2", "S2B"]),
    (("Sheet1", "B1", "=A2*100"), S1("B1", "C1") | {("Sheet2", "A1"), ("Sheet2", "B1")}, ["C1", "S2", "S2B"]),
    (("Sheet1", "A1", 5), set(), []),                   # B1 no longer reads A1
    (("Sheet1", "A2", None), S1("B1", "C1", "G1") | {("Sheet2", "A1"), ("Sheet2", "B1")},
     ["C1", "G1", "S2", "S2B"]),                       # a cell blanked
]
for args, want_cells, want_ticks in steps:
    del ticks[:]
    sheet, addr, value = args
    if value is None:
        raw["sheets"][sheet].pop(addr, None)
    else:
        raw["sheets"][sheet][addr] = value
    got = wb.set(sheet, addr, value)
    got_set = {tuple(c) for c in (got or ())}
    if got_set != want_cells:
        fail("set%r recomputed %s, want %s" % (args, sorted(got_set), sorted(want_cells)))
    if sorted(ticks) != sorted(want_ticks):
        fail("set%r evaluated %s, want only %s" % (args, sorted(ticks), sorted(want_ticks)))
    del ticks[:]
    want = compute(copy.deepcopy(raw))
    del ticks[:]
    have = wb.computed()
    if json.dumps(have, sort_keys=True) != json.dumps(want, sort_keys=True):
        fail("after set%r computed() = %s, want %s" % (args, json.dumps(have, sort_keys=True),
                                                       json.dumps(want, sort_keys=True)))
spot = wb.computed()["sheets"]
for (s, a), w in {("Sheet1", "B1"): 0, ("Sheet1", "C1"): 1, ("Sheet1", "G1"): 0, ("Sheet1", "E1"): 3,
                  ("Sheet2", "B1"): 0}.items():
    if spot[s].get(a) != w or isinstance(spot[s].get(a), bool):
        fail("%s!%s = %s, want %s" % (s, a, json.dumps(spot[s].get(a)), w))
if "A2" in spot["Sheet1"]:
    fail("a blanked cell should leave the computed workbook")
if bad:
    sys.exit(1)
print("ok b2")
PY
