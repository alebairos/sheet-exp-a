#!/bin/sh
# b2 (plan a-v1-cli-input): ./engine's output is strict JSON (no NaN/Infinity) with numbers as Calc shows them,
# and references are case-insensitive as in Calc. Values: a_v1_ci_calc.json, from LibreOffice Calc
# (a_v1_ci_probe.py): {"a2": 5, "A3": "=A2+1", "A4": 1e3} gives A3 6 and A4 1000 (an integer, not 1000.0),
# with the 5 kept once as the cell A2 (key "A2" or "a2"); --cell sheet1!a2 prints 5, --cell 'SHEET1!$A$3'
# and --cell '$A$3' print 6; with a sheet "My Sheet" (A1 7), --cell "'my sheet'!a1" prints 7. Overflowing
# formulas (=1E308*10, =SQRT(-1)) still print strict JSON. Every run exits 0.
set -eu
cd "$(dirname "$0")"
exec python3 - <<'PY'
import json
from a_v1_ci_common import CALC, engine, fail, finish, strict
S1, MS = CALC["Sheet1"], CALC["My Sheet"]
BOOK = json.dumps({"sheets": {"Sheet1": {"a2": 5, "A3": "=A2+1", "A4": 1e3, "A5": "=1E308*10", "A6": "=SQRT(-1)"},
                              "My Sheet": {"A1": 7}}})
def run(args, what):
    code, out, err = engine(["-"] + args, BOOK)
    if code != 0: fail(f"{what}: exit {code}: {err.strip()[-160:]!r}"); return None
    try: return strict(out), out
    except ValueError as e: fail(f"{what}: output is not strict JSON ({e}): {out.strip()[:160]!r}"); return None
r = run([], "the whole book")
if r:
    cells, text = r[0]["sheets"]["Sheet1"], r[1]
    if cells.get("A3") != float(S1["A3"]): fail(f"=A2+1 with the key a2 = 5 gives {cells.get('A3')!r}, Calc shows {S1['A3']}")
    if [k for k in cells if k.upper() == "A2"] not in (["A2"], ["a2"]) or cells.get("A2", cells.get("a2")) != 5:
        fail(f"the cell a2 = 5 is not kept once as A2: {cells!r}")
    if cells.get("A4") != int(S1["A4"]) or not isinstance(cells.get("A4"), int): fail(f"the constant 1e3 prints as {json.dumps(cells.get('A4'))}, Calc shows {S1['A4']}")
for args, want, what in [(["--cell", "sheet1!a2"], S1["A2"], "--cell sheet1!a2"), (["--cell", "SHEET1!$A$3"], S1["A3"], "--cell SHEET1!$A$3"),
                         (["--cell", "$A$3"], S1["A3"], "--cell $A$3"), (["--cell", "'my sheet'!a1"], MS["A1"], "--cell 'my sheet'!a1")]:
    r = run(args, what)
    if r and r[0] != float(want): fail(f"{what} prints {r[1].strip()!r}, Calc shows {want}")
finish("output is strict JSON; a2, sheet1!a2, $A$3 and 'my sheet'!a1 read their cells as in Calc; 1e3 prints 1000")
PY
