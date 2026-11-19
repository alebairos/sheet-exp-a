#!/bin/sh
# b3: a cycle gives an error.
# Contract (plan a-i4-recalc): every cell on a circular reference, and every formula that reads one,
# computes to Calc's circular-reference error {"error": "Err:522"} (LibreOffice headless gives
# Err:522 for each of these cells); cells off the cycle compute normally; the engine never hangs or
# crashes, even on a cycle of 5,000 cells. Through the CLI, and through src.recalc.Workbook when an
# edit makes or breaks a cycle.
set -eu
cd "$(dirname "$0")/../../.."
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
import json
import subprocess
import sys

CYC = {"error": "Err:522"}
s1 = {
    "A1": "=B1+1", "B1": "=A1+1",          # a two-cell cycle
    "C1": "=A1*2", "I1": "=A1&\"t\"",      # formulas reading it
    "D1": 5, "E1": "=D1+1", "K1": "=E1*2", # off the cycle
    "F1": "=F1",                            # a cell reading itself
    "G1": "=Sheet2!A1",                     # a cycle across sheets
    "H1": "=G1+E1",                         # reading it, with a good cell
}
for n in range(1, 5000):                    # a long cycle
    s1["L%d" % n] = "=L%d+1" % (n + 1)
s1["L5000"] = "=L1"
book = {"sheets": {"Sheet1": s1, "Sheet2": {"A1": "=Sheet2!B1", "B1": "=Sheet1!G1", "C1": "=Sheet1!K1"}}}
want = {("Sheet1", a): CYC for a in ("A1", "B1", "C1", "I1", "F1", "G1", "H1", "L1", "L2500", "L5000")}
want.update({("Sheet2", "A1"): CYC, ("Sheet2", "B1"): CYC, ("Sheet1", "D1"): 5,
             ("Sheet1", "E1"): 6, ("Sheet1", "K1"): 12, ("Sheet2", "C1"): 12})


def same(got, w):
    if isinstance(w, (bool, str, dict)) or w is None:
        return type(got) is type(w) and got == w
    return type(got) in (int, float) and not isinstance(got, bool) and abs(got - w) < 1e-9


bad = 0
try:
    p = subprocess.run([sys.executable, "engine", "-"], input=json.dumps(book),
                       capture_output=True, text=True, timeout=30)
except subprocess.TimeoutExpired:
    sys.exit("FAIL the engine hung on a circular reference (30 s)")
if p.returncode != 0:
    sys.exit("FAIL engine exited %d: %s" % (p.returncode, p.stderr[-500:]))
out = json.loads(p.stdout)["sheets"]
for (sheet, addr), w in sorted(want.items()):
    got = out.get(sheet, {}).get(addr, "<missing>")
    if not same(got, w):
        bad += 1
        print("FAIL %s!%s: got %s, want %s" % (sheet, addr, json.dumps(got), json.dumps(w)))

# An edit that makes a cycle, and one that breaks it.
from src.recalc import Workbook

wb = Workbook({"sheets": {"S": {"A1": 1, "B1": "=A1+1", "C1": "=B1*2", "D1": 7, "E1": "=D1"}}})
steps = [
    (("S", "A1", "=C1"), {"A1": CYC, "B1": CYC, "C1": CYC, "D1": 7, "E1": 7}),
    (("S", "A1", 3), {"A1": 3, "B1": 4, "C1": 8, "D1": 7, "E1": 7}),
    (("S", "D1", "=E1"), {"A1": 3, "B1": 4, "C1": 8, "D1": CYC, "E1": CYC}),
    (("S", "E1", 2), {"A1": 3, "B1": 4, "C1": 8, "D1": 2, "E1": 2}),
]
for args, w in steps:
    wb.set(*args)
    got = wb.computed()["sheets"]["S"]
    for addr, v in w.items():
        if not same(got.get(addr, "<missing>"), v):
            bad += 1
            print("FAIL after set%r: S!%s = %s, want %s" % (args, addr, json.dumps(got.get(addr)), json.dumps(v)))
if bad:
    sys.exit(1)
print("ok b3")
PY
