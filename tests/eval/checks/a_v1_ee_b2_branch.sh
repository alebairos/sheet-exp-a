#!/bin/sh
# b2 (plan a-v1-eval-edges): a self-reference through a branch IF or IFERROR does not take gives LibreOffice's
# value. ./engine computes the probe's workbook; every formula of sheet Cyc must give Calc's result:
# =IF(TRUE,1,A16) in A16 is 1, =IF(FALSE,B7,2) in B7 is 2, =IF(D2>0,D1,5) in D1 is 5 (D2 = 0), =IFERROR(F1,7)
# in F1 is 7, =A16+1 is 2; B8 =IFERROR(B9,0) with B9 =B8 gives B8 0 and B9 Err:522, while C8 =C9 with C9
# =IFERROR(C8,0) gives 0 and 0, and J2/K1, L1/L2, M2/N1 pin Calc's order (column by column, top to bottom,
# precedents on demand, a cell still being computed reads as Err:522). Real cycles stay Err:522 (D3, E1/E2,
# H1/H2). Expected values: a_v1_ee_calc.json, from running LibreOffice Calc 26.8.1.1 (a_v1_ee_probe.py).
set -eu
cd "$(dirname "$0")"
exec python3 -c 'from a_v1_ee_common import run_and_compare; run_and_compare(["Cyc"], "b2: self-references through untaken branches match LibreOffice on 20 formulas")'
