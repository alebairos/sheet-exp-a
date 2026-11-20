#!/bin/sh
# b1: that walk-through runs end to end in a browser test.
# Contract (plan a-r2-ui):
# 1. In headless Chrome/Chromium, with real clicks and keys, on web/io/index.html as web/io/serve.py serves it
#    (a_r2_walk.mjs, a_r2_cdp.mjs next to this script): Open (#open) {A1: 10, A2: 2, B1: "=A1/A2"}, B1 shows 5;
#    click B1 and the formula bar (#formula-bar, its input aria-label="Formula") shows =A1/A2; type =A1/A3 + Enter
#    in the bar: B1 shows #DIV/0! and the bar, B1 selected, shows =A1/A3 and the error (#formula-bar .error);
#    type =A1/A2*3 + Enter: B1 shows 15, no error; Save JSON (#save-json) downloads walk.json holding
#    exactly {A1: 10, A2: 2, B1: "=A1/A2*3"}; the page throws nothing.
# 2. The product carries its own browser test of that walk-through: unittest tests under tests/e2e/ui that
#    ./test.sh discovers, that run (not skipped) when a browser is found, start the browser named by $CHROME
#    (first, before google-chrome or chromium on PATH) and pass.
# The browser: $CHROME, else google-chrome, google-chrome-stable, chromium or chromium-browser; none is a FAIL.
set -eu
cd "$(dirname "$0")/../../../.."
export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=utf-8
command -v node >/dev/null || { echo "FAIL: node is not installed"; exit 1; }
status=0
node tests/e2e/ui/checks/a_r2_walk.mjs || status=1
python3 - <<'PY' || status=1
import os, shutil, stat, sys, tempfile, unittest
real = os.environ.get("CHROME") or next(filter(None, map(shutil.which, ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"])), None)
if not real:
    print("FAIL no browser: set CHROME or put google-chrome or chromium on PATH"); sys.exit(1)
d = tempfile.mkdtemp(prefix="a-r2-chrome-")
marker, wrapper = os.path.join(d, "started"), os.path.join(d, "chrome")
with open(wrapper, "w") as f:
    f.write('#!/bin/sh\ntouch "%s"\nexec "%s" "$@"\n' % (marker, shutil.which(real) or real))
os.chmod(wrapper, stat.S_IRWXU)
os.environ["CHROME"] = wrapper
picked = unittest.TestSuite()
def walk(s):
    for t in s:
        if isinstance(t, unittest.TestSuite): walk(t)
        elif t.id().startswith("tests.e2e.ui."): picked.addTest(t)
walk(unittest.defaultTestLoader.discover("tests", top_level_dir="."))
fails = []
if picked.countTestCases() == 0:
    fails.append("the product suite has no tests under tests/e2e/ui (discovered from tests/, as ./test.sh does)")
else:
    r = unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(picked)
    fails += ["e2e ui test %s fails: %s" % (t.id(), tb.strip().splitlines()[-1]) for t, tb in r.failures + r.errors]
    fails += ["e2e ui test %s was skipped: %s" % (t.id(), why) for t, why in r.skipped]
    if not os.path.exists(marker):
        fails.append("the tests under tests/e2e/ui never started the browser named by $CHROME")
for f in fails: print("FAIL " + f)
sys.exit(1 if fails else 0)
PY
[ "$status" = 0 ] && echo ok
exit "$status"
