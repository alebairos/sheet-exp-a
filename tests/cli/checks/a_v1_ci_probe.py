"""Where a_v1_ci_calc.json comes from: LibreOffice Calc itself, headless, over UNO (not run by the checks).

Calc reads references case-insensitively: a cell typed as a2 is A2 and a sheet named "My Sheet" is also
'my sheet'. The probe builds Sheet1 (A2 = 5, A3 = =a2+1, A4 = 1E3) and "My Sheet" (A1 = 7, B1 = ='my sheet'.a1,
B2 = =$Sheet1.$a$2) and prints what Calc shows. Run: python3 a_v1_ci_probe.py /tmp/x (soffice, python3-uno).
"""
import json, subprocess, sys, tempfile, time
import uno

d = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
p = subprocess.Popen(["soffice", "--headless", "--invisible", "--norestore", "-env:UserInstallation=file://" + d + "/prof",
                      "--accept=socket,host=127.0.0.1,port=2303;urp;"])
ctx = uno.getComponentContext()
res = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
for _ in range(60):
    try:
        c = res.resolve("uno:socket,host=127.0.0.1,port=2303;urp;StarOffice.ComponentContext"); break
    except Exception:
        time.sleep(0.5)
desk = c.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", c)
doc = desk.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())
doc.Sheets.getByIndex(0).setName("Sheet1")
doc.Sheets.insertNewByName("My Sheet", 1)
s1, s2 = doc.Sheets.getByName("Sheet1"), doc.Sheets.getByName("My Sheet")
s1.getCellRangeByName("A2").setValue(5)
s1.getCellRangeByName("A3").setFormula("=a2+1")
s1.getCellRangeByName("A4").setFormula("1E3")
s2.getCellRangeByName("A1").setValue(7)
s2.getCellRangeByName("B1").setFormula("='my sheet'.a1")
s2.getCellRangeByName("B2").setFormula("=$sheet1.$a$2")
doc.calculateAll()
g = lambda s, r: s.getCellRangeByName(r).getString()
print(json.dumps({"Sheet1": {r: g(s1, r) for r in ("A2", "A3", "A4")}, "My Sheet": {r: g(s2, r) for r in ("A1", "B1", "B2")}}))
doc.close(True)
try: desk.terminate()
except Exception: pass
p.wait(timeout=30)
