#!/bin/sh
# b2 (plan a-v1-big-sheets): in headless Chrome/Chromium on web/io/index.html as web/io/serve.py serves it,
# Open (#open) big.json: big.csv's cells plus M1 =SUM(B2:B2001) and M2001 =B2001*2. With real keys
# (DevTools Input.dispatchKeyEvent) and after every key the selection (#grid td.selected) is the expected cell
# and the user sees it (inside the window, hit at its centre):
# ArrowDown A1 -> A40; PageDown moves at least 10 rows a press until row 2001; PageUp moves at least 10 rows up;
# ArrowRight B2001 -> M2001, which shows 400202; ArrowLeft back to B2001; type 5, Enter; right to M2002, up to
# M2001 (moving on before the recompute returns): it shows 10, M2001 stays selected and B2001 shows 5;
# PageUp to M1, which shows 200101904; the page throws nothing.
# Expected values: a_v1_bs_calc.json, from LibreOffice Calc (a_v1_bs_probe.py), not written by hand.
set -eu
cd "$(dirname "$0")/../../../.."
command -v node >/dev/null || { echo "FAIL: node is not installed"; exit 1; }
export PYTHONDONTWRITEBYTECODE=1
exec node tests/e2e/ui/checks/a_v1_bs_b2.mjs
