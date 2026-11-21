#!/bin/sh
# b1, b2 kept by the product (plan a-v1-cli-input): the product carries its own tests of the CLI's input
# handling, unittest tests in tests/cli/test_cli_input.py (with tests/cli/__init__.py) that ./test.sh discovers
# (python3 -m unittest discover -s tests -t .); they run ./engine on bad input (malformed JSON, wrong shape,
# missing file, directory) and on lower-case and $ references, are not skipped, and pass.
set -eu
cd "$(dirname "$0")/../../.."
export PYTHONDONTWRITEBYTECODE=1
exec python3 - <<'PY'
import os, sys, unittest
picked = unittest.TestSuite()
def walk(s):
    for t in s:
        if isinstance(t, unittest.TestSuite): walk(t)
        elif t.id().startswith("tests.cli.test_cli_input."): picked.addTest(t)
walk(unittest.defaultTestLoader.discover("tests", top_level_dir="."))
fails = []
if picked.countTestCases() == 0:
    fails.append("the product suite has no tests in tests/cli/test_cli_input.py (discovered as ./test.sh does)")
else:
    r = unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(picked)
    fails += ["%s fails: %s" % (t.id(), tb.strip().splitlines()[-1]) for t, tb in r.failures + r.errors]
    fails += ["%s was skipped: %s" % (t.id(), why) for t, why in r.skipped]
for f in fails: print("FAIL " + f)
if not fails: print("ok the product's CLI input tests run and pass (%d)" % picked.countTestCases())
sys.exit(1 if fails else 0)
PY
