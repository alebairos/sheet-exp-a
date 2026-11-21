#!/bin/sh
# b1, b2 kept by the product (plan a-v1-eval-edges): the product carries its own tests, unittest tests in
# tests/eval/test_eval_edges.py that ./test.sh discovers (python3 -m unittest discover -s tests -t .), of implicit
# intersection (a range in a single-value place takes the formula's row or column, else #VALUE!) and of
# self-references through untaken IF/IFERROR branches in Calc's order; they are not skipped and pass.
set -eu
cd "$(dirname "$0")/../../.."
export PYTHONDONTWRITEBYTECODE=1
exec python3 - <<'PY'
import os, sys, unittest
picked = unittest.TestSuite()
def walk(s):
    for t in s:
        if isinstance(t, unittest.TestSuite): walk(t)
        elif t.id().startswith("tests.eval.test_eval_edges."): picked.addTest(t)
walk(unittest.defaultTestLoader.discover("tests", top_level_dir="."))
fails = []
if picked.countTestCases() == 0:
    fails.append("the product suite has no tests in tests/eval/test_eval_edges.py (discovered as ./test.sh does)")
else:
    r = unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(picked)
    fails += ["%s fails: %s" % (t.id(), tb.strip().splitlines()[-1]) for t, tb in r.failures + r.errors]
    fails += ["%s was skipped: %s" % (t.id(), why) for t, why in r.skipped]
for f in fails: print("FAIL " + f)
if not fails: print("ok the product's evaluation-edge tests run and pass (%d)" % picked.countTestCases())
sys.exit(1 if fails else 0)
PY
