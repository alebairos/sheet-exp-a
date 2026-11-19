#!/bin/sh
# b1: `engine -` prints a workbook of constants unchanged, in SPEC.md's output shape.
# Also reads the workbook from a file path. Runs from the product root.
set -eu
export PYTHONDONTWRITEBYTECODE=1
[ -x ./engine ] || { echo "FAIL: ./engine missing or not executable"; exit 1; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
cat > "$tmp/in.json" <<'JSON'
{"sheets": {"Sheet1": {"A1": 1, "A2": "text", "A3": true, "A4": false, "B1": 2.5, "B2": -3, "C7": "", "D1": "hello world"},
            "Sheet2": {"A1": 0, "Z99": "x"}, "Empty": {}}}
JSON
./engine - < "$tmp/in.json" > "$tmp/out_stdin.json"
./engine "$tmp/in.json" > "$tmp/out_file.json"
python3 - "$tmp/in.json" "$tmp/out_stdin.json" "$tmp/out_file.json" <<'PY'
import json, sys
def strict(path):
    with open(path) as f:
        return json.load(f)
want = strict(sys.argv[1])
for p in sys.argv[2:]:
    got = strict(p)
    if not isinstance(got, dict) or set(got) != {"sheets"}:
        sys.exit(f"FAIL {p}: top level must be {{\"sheets\": ...}}, got {got!r}")
    for sheet, cells in want["sheets"].items():
        g = got["sheets"].get(sheet)
        if g is None:
            sys.exit(f"FAIL {p}: sheet {sheet} missing")
        for ref, v in cells.items():
            if ref not in g:
                sys.exit(f"FAIL {p}: {sheet}!{ref} missing")
            gv = g[ref]
            if type(gv) is bool or type(v) is bool:
                ok = type(gv) is type(v) and gv == v
            else:
                ok = type(gv) in (int, float) and type(v) in (int, float) and gv == v if not isinstance(v, str) else gv == v
            if not ok:
                sys.exit(f"FAIL {p}: {sheet}!{ref} = {gv!r}, want {v!r}")
        extra = set(g) - set(cells)
        if extra:
            sys.exit(f"FAIL {p}: {sheet} has cells not in the input: {sorted(extra)}")
    extra = set(got["sheets"]) - set(want["sheets"])
    if extra:
        sys.exit(f"FAIL {p}: sheets not in the input: {sorted(extra)}")
print("ok b1")
PY
