#!/bin/sh
# b1: chains of formula cells compute in dependency order.
# Contract (plan a-i4-recalc): the engine CLI (SPEC.md) computes every formula after the cells it
# reads, whatever order the cells appear in the JSON, across sheets; constants pass through as given,
# the output has exactly the input's cells, and --cell prints a formula cell's computed value.
set -eu
cd "$(dirname "$0")/../../.."
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
import json
import subprocess
import sys

s1 = {
    # a short chain written last-first
    "A5": "=A4+1", "A4": "=A3*2", "A3": "=A2+A1", "A2": "=A1+1", "A1": 1,
    # a diamond fed by the chain
    "C1": "=C2+C3", "C2": "=C4*2", "C3": "=C4*3", "C4": "=A5",
    # a one-cell range read in operator context
    "E1": "=A3:A3+1",
    # text through a chain
    "G1": "=H1&\"!\"", "H1": "=\"a\"&\"b\"",
    # constants pass through as given
    "I1": 2.5, "J1": True, "K1": "txt", "K2": {"error": "#N/A"},
    # an error flows down a chain
    "L1": "=M1+1", "M1": "=1/0",
    # other sheets, by name in any case, and a missing one
    "B1": "=Sheet2!A1*10", "N1": "=sheet2!A1", "O1": "=Nope!A1",
    # a blank cell reads as 0
    "P1": "=Z99+1",
}
# 200 cells, each reading the one below it, written top-first
for n in range(1, 200):
    s1["F%d" % n] = "=F%d+1" % (n + 1)
s1["F200"] = 1
book = {"sheets": {"Sheet1": s1, "Sheet2": {"A1": "=Sheet1!A5-2", "B1": "=Sheet1!F1"}, "Empty": {}}}

want1 = {"A1": 1, "A2": 2, "A3": 3, "A4": 6, "A5": 7, "C1": 35, "C2": 14, "C3": 21, "C4": 7,
         "E1": 4, "G1": "ab!", "H1": "ab", "I1": 2.5, "J1": True, "K1": "txt",
         "K2": {"error": "#N/A"}, "L1": {"error": "#DIV/0!"}, "M1": {"error": "#DIV/0!"},
         "B1": 50, "N1": 5, "O1": {"error": "#REF!"}, "P1": 1, "F1": 200, "F100": 101, "F200": 1}
want2 = {"A1": 5, "B1": 200}


def same(got, want):
    if isinstance(want, (bool, str, dict)) or want is None:
        return type(got) is type(want) and got == want
    return type(got) in (int, float) and not isinstance(got, bool) and abs(got - want) < 1e-9


def engine(args):
    p = subprocess.run([sys.executable, "engine"] + args, input=json.dumps(book),
                       capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        sys.exit("FAIL engine %s exited %d: %s" % (" ".join(args), p.returncode, p.stderr[-500:]))
    return json.loads(p.stdout)


bad = 0
out = engine(["-"])
sheets = out.get("sheets", {}) if isinstance(out, dict) else {}
if sorted(sheets) != sorted(book["sheets"]):
    sys.exit("FAIL sheets: got %s" % sorted(sheets))
for name in book["sheets"]:
    if sorted(sheets[name]) != sorted(book["sheets"][name]):
        bad += 1
        print("FAIL %s should hold exactly the input's cells" % name)
for name, want in (("Sheet1", want1), ("Sheet2", want2)):
    for addr, w in want.items():
        got = sheets.get(name, {}).get(addr, "<missing>")
        if not same(got, w):
            bad += 1
            print("FAIL %s!%s = %s: got %s, want %s" % (name, addr, json.dumps(book["sheets"][name][addr]),
                                                      json.dumps(got), json.dumps(w)))
for n in range(1, 201):
    got = sheets.get("Sheet1", {}).get("F%d" % n)
    if not same(got, 201 - n):
        bad += 1
        print("FAIL Sheet1!F%d: got %s, want %d" % (n, json.dumps(got), 201 - n))
        break
for ref, w in (("Sheet1!F1", 200), ("Sheet1!$A$5", 7), ("Sheet2!B1", 200), ("Sheet1!L1", {"error": "#DIV/0!"})):
    got = engine(["-", "--cell", ref])
    if not same(got, w):
        bad += 1
        print("FAIL --cell %s: got %s, want %s" % (ref, json.dumps(got), json.dumps(w)))
if bad:
    sys.exit(1)
print("ok b1")
PY
