#!/bin/sh
# b2: `engine - --cell Sheet1!A1` prints one value (that cell's JSON value only).
set -eu
export PYTHONDONTWRITEBYTECODE=1
[ -x ./engine ] || { echo "FAIL: ./engine missing or not executable"; exit 1; }
wb='{"sheets": {"Sheet1": {"A1": 42, "A2": "text", "A3": true, "B1": 2.5}, "Sheet2": {"C3": "other"}}}'
check() {
  out=$(printf '%s' "$wb" | ./engine - --cell "$1")
  python3 -c '
import json, sys
got = json.loads(sys.argv[1]); want = json.loads(sys.argv[2])
same = type(got) is type(want) and got == want if isinstance(want, (bool, str)) else (type(got) in (int, float) and type(got) is not bool and got == want)
if not same:
    sys.exit("FAIL --cell %s: got %r, want %r" % (sys.argv[3], got, want))
' "$out" "$2" "$1"
}
check 'Sheet1!A1' '42'
check 'Sheet1!A2' '"text"'
check 'Sheet1!A3' 'true'
check 'Sheet1!B1' '2.5'
check 'Sheet2!C3' '"other"'
echo "ok b2"
