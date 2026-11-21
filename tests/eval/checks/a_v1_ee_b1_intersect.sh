#!/bin/sh
# b1 (plan a-v1-eval-edges): implicit intersection as LibreOffice computes it. ./engine computes the probe's
# workbook (a_v1_ee_calc.json "book"); every formula of sheets Data and T must give Calc's result: =C2:C3 in
# row 2 is 3 and in row 5 #VALUE!; =C2:C3*2 in row 3 is 8; =B1:D1 in column C is 20, in column E +1 #VALUE!;
# a 2-D range =B2:C3 is #VALUE!; =C2:C3&"x" in row 3 is "4x"; =IF(C2:C3>3,"big","small") in row 2 is "small";
# =C2:C3=4 in row 3 is TRUE; from sheet T, =Data!C2:C3 takes T's own row (3 in row 2, 4 in row 3) and
# =Data!B1:D1 in column B is 10; =SUM(C2:C3) stays 7. Expected values: a_v1_ee_calc.json, from running
# LibreOffice Calc 26.8.1.1 (a_v1_ee_probe.py), never written by hand.
set -eu
cd "$(dirname "$0")"
exec python3 -c 'from a_v1_ee_common import run_and_compare; run_and_compare(["Data", "T"], "b1: implicit intersection matches LibreOffice on 16 formulas")'
