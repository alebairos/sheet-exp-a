#!/bin/sh
# b4: 10,000 dependent cells recompute in under one second.
# Contract (plan a-i4-recalc), in process, best of three runs each:
#  - src.recalc.compute() of a 10,000-cell chain (A2 = A1+1 ... A10000, written last-first) < 1 s;
#  - Workbook.set() of the chain's head, recomputing its 9,999 dependents, < 1 s;
#  - Workbook.set() of a cell that 10,000 formulas read (B1..B10000 = $C$1*2), < 1 s;
#  with the right values, and no recursion limit hit.
set -eu
cd "$(dirname "$0")/../../.."
export PYTHONDONTWRITEBYTECODE=1
python3 - <<'PY'
import sys
import time

from src.recalc import Workbook, compute

N = 10000
LIMIT = 1.0
chain = {"A%d" % n: "=A%d+1" % (n - 1) for n in range(N, 1, -1)}
chain["A1"] = 1
fan = {"B%d" % n: "=$C$1*2" for n in range(1, N + 1)}
fan["C1"] = 1


def best(fn):
    times = []
    out = None
    for _ in range(3):
        t = time.perf_counter()
        out = fn()
        times.append(time.perf_counter() - t)
    return min(times), out


bad = 0
t, out = best(lambda: compute({"sheets": {"Sheet1": dict(chain)}}))
v = out["sheets"]["Sheet1"]["A%d" % N]
print("compute chain of %d: %.3f s, A%d = %s" % (N, t, N, v))
if v != N or t >= LIMIT:
    bad += 1
    print("FAIL compute of the chain: %.3f s (limit %.1f), A%d = %s, want %d" % (t, LIMIT, N, v, N))

wb = Workbook({"sheets": {"Sheet1": dict(chain)}})
k = [0]


def edit_head():
    k[0] += 1
    return wb.set("Sheet1", "A1", 1 + k[0])


t, got = best(edit_head)
v = wb.computed()["sheets"]["Sheet1"]["A%d" % N]
print("edit chain head, %s recomputed: %.3f s, A%d = %s" % (len(got or ()), t, N, v))
if v != N + k[0] or len(got or ()) != N - 1 or t >= LIMIT:
    bad += 1
    print("FAIL edit of the chain head: %.3f s (limit %.1f), %d recomputed (want %d), A%d = %s, want %d"
          % (t, LIMIT, len(got or ()), N - 1, N, v, N + k[0]))

wb = Workbook({"sheets": {"Sheet1": dict(fan)}})


def edit_fan():
    k[0] += 1
    return wb.set("Sheet1", "C1", k[0])


t, got = best(edit_fan)
v = wb.computed()["sheets"]["Sheet1"]["B%d" % N]
print("edit read by %d, %s recomputed: %.3f s, B%d = %s" % (N, len(got or ()), t, N, v))
if v != 2 * k[0] or len(got or ()) != N or t >= LIMIT:
    bad += 1
    print("FAIL edit of a cell %d formulas read: %.3f s (limit %.1f), %d recomputed, B%d = %s, want %d"
          % (N, t, LIMIT, len(got or ()), N, v, 2 * k[0]))
if bad:
    sys.exit(1)
print("ok b4")
PY
