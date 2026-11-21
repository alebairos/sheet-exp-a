"""Shared by the a-v1-cli-input checks: run ./engine as a user does and read its output strictly."""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
HERE = os.path.dirname(os.path.abspath(__file__))
CALC = json.load(open(os.path.join(HERE, "a_v1_ci_calc.json")))["shown"]
fails = []


def engine(args, stdin=""):
    """./engine with args and stdin text: (exit code, stdout, stderr)."""
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([os.path.join(ROOT, "engine")] + args, input=stdin, capture_output=True, text=True,
                       cwd=ROOT, env=env, timeout=60)
    return p.returncode, p.stdout, p.stderr


def strict(text):
    """JSON as RFC 8259 has it: NaN, Infinity and -Infinity are not JSON."""
    def no(c):
        raise ValueError("not JSON: " + c)
    return json.loads(text, parse_constant=no)


def fail(m):
    fails.append(m)


def finish(ok):
    for f in fails:
        print("FAIL " + f)
    if not fails:
        print("ok " + ok)
    sys.exit(1 if fails else 0)
