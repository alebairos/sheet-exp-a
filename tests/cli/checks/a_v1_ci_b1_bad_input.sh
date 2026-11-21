#!/bin/sh
# b1 (plan a-v1-cli-input): bad input to ./engine prints one plain error line on stderr and exits non-zero:
# no traceback (no "Traceback", no Python exception name such as JSONDecodeError or FileNotFoundError),
# stdout empty. Cases, on stdin (-) unless named: malformed JSON {"sheets": {, an empty input, NaN and
# Infinity / 1e999 constants (not JSON numbers), [], {"foo": 1}, {"sheets": []}, a sheet that is a list,
# a cell that is a list; a missing file, a directory, and a malformed JSON file. Good input is not refused:
# {"sheets": {}} still prints {"sheets": {}} and exits 0.
set -eu
cd "$(dirname "$0")"
exec python3 - <<'PY'
import os, re, tempfile
from a_v1_ci_common import engine, fail, finish, strict
BAD = {"malformed JSON": '{"sheets": {', "empty input": "", "a NaN constant": '{"sheets": {"S": {"A1": NaN}}}',
       "an Infinity constant": '{"sheets": {"S": {"A1": Infinity}}}', "a 1e999 constant": '{"sheets": {"S": {"A1": 1e999}}}',
       "a list": "[]", "no sheets": '{"foo": 1}', "sheets as a list": '{"sheets": []}',
       "a sheet as a list": '{"sheets": {"S": []}}', "a cell as a list": '{"sheets": {"S": {"A1": [1]}}}'}
d = tempfile.mkdtemp()
bad_file = os.path.join(d, "bad.json")
open(bad_file, "w").write('{"sheets": {')
cases = [(what, ["-"], text) for what, text in BAD.items()]
cases += [("a missing file", [os.path.join(d, "missing.json")], ""), ("a directory", [d], ""), ("a malformed file", [bad_file], "")]
PY_NAME = re.compile(r"Traceback|\b[A-Z][A-Za-z]*(Error|Exception)\b")
for what, args, text in cases:
    code, out, err = engine(args, text)
    lines = [l for l in err.splitlines() if l.strip()]
    if code == 0: fail(f"{what}: exit 0, wanted non-zero")
    if out.strip(): fail(f"{what}: printed on stdout {out.strip()[:80]!r}, wanted nothing")
    if len(lines) != 1: fail(f"{what}: {len(lines)} lines on stderr, wanted one: {err.strip()[-160:]!r}")
    elif PY_NAME.search(err): fail(f"{what}: stderr shows Python internals: {lines[-1][:120]!r}")
code, out, err = engine(["-"], '{"sheets": {}}')
if code != 0 or strict(out) != {"sheets": {}}: fail(f'{{"sheets": {{}}}} is refused: exit {code}, {out.strip()!r} {err.strip()[-120:]!r}')
finish(f"{len(cases)} kinds of bad input each give one plain error line and a non-zero exit")
PY
