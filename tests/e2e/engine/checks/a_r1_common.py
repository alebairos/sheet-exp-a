"""Shared helpers for the a-r1-engine checks (a_r1_b1_workbooks.sh, a_r1_b2_chain.sh). Run from the repo root."""
import json, os, re, subprocess, sys, unittest

ENGINE = os.path.abspath("engine")
FUNCS = """SUM AVERAGE MIN MAX COUNT COUNTA ROUND ROUNDUP ROUNDDOWN INT MOD ABS POWER SQRT PRODUCT SUMIF COUNTIF
AVERAGEIF MEDIAN STDEV IF IFERROR AND OR NOT ISBLANK ISNUMBER ISTEXT ISERROR CONCATENATE LEFT RIGHT MID LEN
UPPER LOWER TRIM VLOOKUP INDEX MATCH""".split()
fails = []
HERE = os.path.join("tests", "e2e", "engine", "checks")  # the check workbook and Calc's answers sit next to this script

def same(g, w):
    if isinstance(w, bool) or isinstance(g, bool) or not isinstance(w, (int, float)) or not isinstance(g, (int, float)):
        return type(g) is type(w) and g == w
    return abs(g - w) <= 1e-9 * max(1.0, abs(w))

def run_cli(book, label):
    p = subprocess.run([sys.executable, ENGINE, "-"], input=json.dumps(book), capture_output=True, text=True, timeout=120)
    if p.returncode:
        fails.append("%s: the CLI exited %d: %s" % (label, p.returncode, p.stderr.strip()[-300:]))
        return None
    return json.loads(p.stdout)

def compare(book, want, label):
    got = run_cli(book, label)
    if got is None:
        return
    for sheet, cells in want["sheets"].items():
        for a, w in cells.items():
            g = got.get("sheets", {}).get(sheet, {}).get(a)
            if not same(g, w):
                fails.append("%s %s!%s %s: Calc %s, engine %s" % (label, sheet, a, book["sheets"][sheet][a], json.dumps(w), json.dumps(g)))

from a_r1_chain import formulas, longest_chain  # noqa: E402,F401  (re-exported for the scripts)

def product_books():
    """The product's own e2e workbooks: tests/e2e/engine/books/<name>.json with Calc's answers in <name>.calc.json."""
    d = os.path.join("tests", "e2e", "engine", "books")
    out = []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".json") and not f.endswith(".calc.json"):
                ans = os.path.join(d, f[:-5] + ".calc.json")
                if not os.path.exists(ans):
                    fails.append("tests/e2e/engine/books/%s has no %s" % (f, f[:-5] + ".calc.json"))
                    continue
                out.append((f[:-5], json.load(open(os.path.join(d, f), encoding="utf-8")), json.load(open(ans, encoding="utf-8"))))
    return out

def product_suite():
    """The e2e tests are part of the product suite (./test.sh discovers them) and pass."""
    suite = unittest.defaultTestLoader.discover("tests", top_level_dir=".")
    picked = unittest.TestSuite()
    def walk(s):
        for t in s:
            if isinstance(t, unittest.TestSuite): walk(t)
            elif t.id().startswith("tests.e2e.engine.") or "tests.e2e.engine" in str(type(t)): picked.addTest(t)
    walk(suite)
    if picked.countTestCases() == 0:
        fails.append("the product suite has no tests under tests/e2e/engine (discovered from tests/, as ./test.sh does)")
        return
    r = unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(picked)
    if not r.wasSuccessful():
        for t, tb in r.failures + r.errors:
            fails.append("e2e test %s fails: %s" % (t.id(), tb.strip().splitlines()[-1]))

def load(name):
    """A check workbook or Calc's answers for it, stored next to this module."""
    return json.load(open(os.path.join(HERE, name), encoding="utf-8"))

def finish():
    """Print every failure and exit 1 (red), or print ok and exit 0."""
    if fails:
        print("FAIL (%d)" % len(fails))
        for f in fails[:60]:
            print("  " + f)
        sys.exit(1)
    print("ok")
