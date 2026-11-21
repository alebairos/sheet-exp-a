"""Shared by the a-v1-eval-edges checks: ./engine on the probe's workbook, compared with Calc's results."""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
CALC = json.load(open(os.path.join(HERE, "a_v1_ee_calc.json")))


def run_and_compare(sheets, ok):
    """Computes CALC's whole book with ./engine and checks every formula of `sheets` against Calc."""
    p = subprocess.run([os.path.join(ROOT, "engine"), "-"], input=json.dumps({"sheets": CALC["book"]}), capture_output=True,
                       text=True, cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), timeout=60)
    if p.returncode != 0:
        print("FAIL ./engine exited %d: %s" % (p.returncode, p.stderr.strip()[-300:])); sys.exit(1)
    out, fails = json.loads(p.stdout)["sheets"], []
    for sheet in sheets:
        for ref, want in CALC["results"][sheet].items():
            got, f = out[sheet].get(ref), CALC["book"][sheet][ref]
            if "number" in want: good = isinstance(got, (int, float)) and not isinstance(got, bool) and abs(got - want["number"]) <= 1e-9
            elif "bool" in want: good = got is want["bool"]
            elif "text" in want: good = got == want["text"]
            else: good = got == {"error": want["error"]}
            if not good: fails.append("%s!%s %s gives %s, Calc gives %s" % (sheet, ref, f, json.dumps(got), json.dumps(want)))
    for f in fails: print("FAIL " + f)
    if not fails: print("ok " + ok)
    sys.exit(1 if fails else 0)
