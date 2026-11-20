"""Shared helpers for the a-r0-spreadsheet checks (a_r0_b1_cli.sh, a_r0_b2_browser.sh). Run from the repo root."""
import json, os, shutil, stat, subprocess, sys, tempfile, unittest

HERE = os.path.join("tests", "e2e", "workbooks", "checks")  # the plan's workbooks and Calc's answers
PRODUCT = os.path.join("tests", "e2e", "workbooks", "books")  # the product's copies: <name>.json, <name>.calc.json
NAMES = ["budget", "grades", "orders"]
fails = []

def load(name, d=HERE):
    with open(os.path.join(d, name), encoding="utf-8") as f:
        return json.load(f)

def same(g, w):
    if isinstance(w, bool) or isinstance(g, bool) or not isinstance(w, (int, float)) or not isinstance(g, (int, float)):
        return type(g) is type(w) and g == w
    return abs(g - w) <= 1e-9 * max(1.0, abs(w))

def compare(book, want, label):
    """The book through ./engine (stdin, SPEC's CLI); every cell must equal Calc's answer."""
    p = subprocess.run([sys.executable, "engine", "-"], input=json.dumps(book), capture_output=True, text=True, timeout=120)
    if p.returncode:
        fails.append("%s: the CLI exited %d: %s" % (label, p.returncode, p.stderr.strip()[-300:]))
        return
    got = json.loads(p.stdout).get("sheets", {})
    for sheet, cells in want["sheets"].items():
        for a, w in cells.items():
            g = got.get(sheet, {}).get(a)
            if not same(g, w):
                fails.append("%s %s!%s %s: Calc %s, engine %s" % (label, sheet, a, book["sheets"][sheet][a], json.dumps(w), json.dumps(g)))

def product_books():
    """The product carries the plan's three workbooks and Calc's answers for them, unchanged."""
    books, calc = load("a_r0_books.json"), load("a_r0_calc.json")
    for n in NAMES:
        for f, want in [(n + ".json", books[n]), (n + ".calc.json", calc[n])]:
            p = os.path.join(PRODUCT, f)
            if not os.path.exists(p):
                fails.append("the product has no %s" % p)
            elif load(f, PRODUCT) != want:
                fails.append("%s is not the plan's %s (checks/a_r0_%s.json)" % (p, n, "calc" if "calc" in f else "books"))

def product_tests(module, chrome=False):
    """unittest tests in tests/e2e/workbooks/<module>.py, discovered from tests/ as ./test.sh does, run and pass.
    chrome=True: $CHROME is a wrapper that records its start; the tests must start it and none may be skipped."""
    marker = None
    if chrome:
        real = os.environ.get("CHROME") or next(filter(None, map(shutil.which, ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"])), None)
        if not real:
            fails.append("no browser: set CHROME or put google-chrome or chromium on PATH")
            return
        d = tempfile.mkdtemp(prefix="a-r0-chrome-")
        marker, wrapper = os.path.join(d, "started"), os.path.join(d, "chrome")
        with open(wrapper, "w") as f:
            f.write('#!/bin/sh\ntouch "%s"\nexec "%s" "$@"\n' % (marker, shutil.which(real) or real))
        os.chmod(wrapper, stat.S_IRWXU)
        os.environ["CHROME"] = wrapper
    prefix = "tests.e2e.workbooks.%s." % module
    picked = unittest.TestSuite()
    def walk(s):
        for t in s:
            if isinstance(t, unittest.TestSuite): walk(t)
            elif t.id().startswith(prefix): picked.addTest(t)
    walk(unittest.defaultTestLoader.discover("tests", top_level_dir="."))
    if picked.countTestCases() == 0:
        fails.append("./test.sh discovers no tests in tests/e2e/workbooks/%s.py" % module)
        return
    r = unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(picked)
    fails.extend("test %s fails: %s" % (t.id(), tb.strip().splitlines()[-1]) for t, tb in r.failures + r.errors)
    if chrome:
        fails.extend("test %s was skipped: %s" % (t.id(), why) for t, why in r.skipped)
        if not os.path.exists(marker):
            fails.append("the tests in tests/e2e/workbooks/%s.py never started the browser named by $CHROME" % module)

def finish():
    if fails:
        print("FAIL (%d)" % len(fails))
        for f in fails[:60]:
            print("  " + f)
        sys.exit(1)
    print("ok")
