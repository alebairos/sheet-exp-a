#!/bin/sh
# b3: ./test.sh builds and runs every test from a clean clone.
# Copies the tree (without .git or build output) to a fresh dir and runs ./test.sh there.
# It must pass, run a real suite (not the seed's "no tests yet"), the repo must have one
# directory per part, and a function registers by adding a file under src/functions/<group>/
# with no shared file edited (src/functions exposes register(name) and registry()).
set -eu
export PYTHONDONTWRITEBYTECODE=1
root=$(pwd)
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/clone"
tar -C "$root" --exclude=.git --exclude=__pycache__ --exclude=node_modules -cf - . | tar -C "$tmp/clone" -xf -
cd "$tmp/clone"
for d in src/parser src/values src/eval src/recalc src/functions/math src/functions/logic_text \
         src/functions/lookup web/grid web/formula_bar web/io tests/e2e; do
  [ -d "$d" ] || { echo "FAIL: part directory $d missing"; exit 1; }
done
if ! ./test.sh > "$tmp/test.log" 2>&1; then
  cat "$tmp/test.log"; echo "FAIL: ./test.sh exited non-zero"; exit 1
fi
cat "$tmp/test.log"
if grep -q "no tests yet" "$tmp/test.log"; then echo "FAIL: ./test.sh runs no tests"; exit 1; fi
# A new function registers by dropping a file into its group's directory.
cat > src/functions/math/zz_probe_fn.py <<'PY'
from src.functions import register

@register("ZZPROBE")
def zz_probe(*args):
    return 42
PY
python3 -c '
import sys; sys.path.insert(0, ".")
from src.functions import registry
r = registry()
assert "ZZPROBE" in r, "ZZPROBE not discovered: %r" % sorted(r)
assert r["ZZPROBE"]() == 42
' || { echo "FAIL: a function file under src/functions/math is not discovered"; exit 1; }
echo "ok b3"
