"""Where a_v1_bs_calc.json comes from: LibreOffice Calc itself, headless, over UNO (not run by the checks).

Builds big.csv as a_v1_bs_page.mjs does (header colA..colL, then rows 2..2001 with cell = row*100 + column
index), opens it in Calc, adds M1 =SUM(B2:B2001) and M2001 =B2001*2, reads what Calc shows, sets B2001 to 5,
recalculates and reads again. Run: python3 a_v1_bs_probe.py /tmp/somewhere (needs soffice and python3-uno).
"""
import json, os, subprocess, sys, tempfile, time
import uno
from com.sun.star.beans import PropertyValue

d = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
csv = os.path.join(d, "big.csv")
rows = [",".join("col" + chr(65 + c) for c in range(12))]
rows += [",".join(str(r * 100 + c) for c in range(12)) for r in range(2, 2002)]
open(csv, "w").write("\n".join(rows) + "\n")
p = subprocess.Popen(["soffice", "--headless", "--invisible", "--norestore", "-env:UserInstallation=file://" + d + "/prof",
                      "--accept=socket,host=127.0.0.1,port=2301;urp;"])
ctx = uno.getComponentContext()
res = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
for _ in range(60):
    try:
        c = res.resolve("uno:socket,host=127.0.0.1,port=2301;urp;StarOffice.ComponentContext"); break
    except Exception:
        time.sleep(0.5)
desk = c.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", c)
def pv(n, v):
    x = PropertyValue(); x.Name = n; x.Value = v; return x
doc = desk.loadComponentFromURL("file://" + csv, "_blank", 0,
                                (pv("Hidden", True), pv("FilterName", "Text - txt - csv (StarCalc)"), pv("FilterOptions", "44,34,76,1")))
cell = doc.Sheets.getByIndex(0).getCellRangeByName
out = {"csv": {r: cell(r).getString() for r in ("L2001", "B2001", "A2")}, "formulas": {"M1": "=SUM(B2:B2001)", "M2001": "=B2001*2"}}
for r, f in out["formulas"].items(): cell(r).setFormula(f)
doc.calculateAll()
out["before"] = {r: cell(r).getString() for r in out["formulas"]}
cell("B2001").setValue(5); out["edit"] = {"B2001": "5"}
doc.calculateAll()
out["after"] = {r: cell(r).getString() for r in out["formulas"]}
print(json.dumps(out))
doc.close(True)
try: desk.terminate()
except Exception: pass
p.wait(timeout=30)
