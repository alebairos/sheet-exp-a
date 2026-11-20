#!/bin/sh
# b1 and the NFR (plan a-v1-big-sheets): in headless Chrome/Chromium on web/io/index.html as web/io/serve.py
# serves it, Open (#open) a CSV of 2001 rows x 12 columns (a_v1_bs_page.mjs builds it); real mouse-wheel steps
# over #grid reach row 2001 and column L: the user sees td[data-ref="L2001"] showing 200111, B2001 showing
# 200101, and the headers "2001" and "L" (seen = inside the window and hit at its centre by elementFromPoint);
# wheeling back shows A1 again; every wheel step, from sending it to the next paint after it,
# takes under 100 ms; the page throws nothing. Values: a_v1_bs_calc.json, from LibreOffice Calc (a_v1_bs_probe.py).
# The browser: $CHROME, else google-chrome, google-chrome-stable, chromium or chromium-browser; none is a FAIL.
set -eu
cd "$(dirname "$0")/../../../.."
command -v node >/dev/null || { echo "FAIL: node is not installed"; exit 1; }
export PYTHONDONTWRITEBYTECODE=1
exec node tests/e2e/ui/checks/a_v1_bs_b1.mjs
