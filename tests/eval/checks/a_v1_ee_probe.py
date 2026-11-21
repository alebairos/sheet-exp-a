"""Where a_v1_ee_calc.json comes from: LibreOffice Calc itself, headless, over UNO (not run by the checks).

BOOK (three sheets: Data for implicit intersection, T reading Data, Cyc for self-references through IF and
IFERROR branches) is entered into a new Calc document; every formula's result is read back as Calc shows it:
a number, a text, a boolean or an error name. Run: python3 a_v1_ee_probe.py /tmp/x (needs soffice, python3-uno).
"""
import json, subprocess, sys, tempfile, time
import uno

BOOK = {
    "Data": {"C2": 3, "C3": 4, "B1": 10, "C1": 20, "D1": 30, "G2": "=C2:C3", "G3": "=C2:C3*2", "G5": "=C2:C3",
             "C7": "=B1:D1", "E7": "=B1:D1+1", "F2": "=B2:C3", "G4": "=SUM(C2:C3)", "G6": "=-C2:C3",
             "H3": "=C2:C3&\"x\"", "H2": "=IF(C2:C3>3,\"big\",\"small\")", "I3": "=C2:C3=4", "D7": "=B1:D1*C2:C3"},
    "T": {"A2": "=Data!C2:C3", "A1": "=Data!G2", "A3": "=Data!C2:C3", "B5": "=Data!B1:D1"},
    "Cyc": {"A16": "=IF(TRUE,1,A16)", "B7": "=IF(FALSE,B7,2)", "B8": "=IFERROR(B9,0)", "B9": "=B8",
            "C8": "=C9", "C9": "=IFERROR(C8,0)", "D2": 0, "D1": "=IF(D2>0,D1,5)", "D3": "=IF(D2=0,D3,5)",
            "E1": "=E2+1", "E2": "=E1", "F1": "=IFERROR(F1,7)", "G1": "=A16+1", "H1": "=IF(H2,1,2)", "H2": "=H1>0",
            # which cell of a cycle Calc starts from: row-major, column-major and entry order disagree on these
            "J2": "=IFERROR(K1,0)", "K1": "=J2", "L2": "=IFERROR(L1,0)", "L1": "=L2", "N1": "=IFERROR(M2,0)", "M2": "=N1"},
}
d = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
p = subprocess.Popen(["soffice", "--headless", "--invisible", "--norestore", "-env:UserInstallation=file://" + d + "/prof",
                      "--accept=socket,host=127.0.0.1,port=2309;urp;"])
try:
    ctx = uno.getComponentContext()
    res = ctx.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", ctx)
    for _ in range(60):
        try:
            c = res.resolve("uno:socket,host=127.0.0.1,port=2309;urp;StarOffice.ComponentContext"); break
        except Exception:
            time.sleep(0.5)
    desk = c.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", c)
    doc = desk.loadComponentFromURL("private:factory/scalc", "_blank", 0, ())
    doc.Sheets.getByIndex(0).setName("Data")
    for i, name in enumerate(["T", "Cyc"]): doc.Sheets.insertNewByName(name, i + 1)
    for name, cells in BOOK.items():
        sh = doc.Sheets.getByName(name)
        for ref, v in cells.items():
            cell = sh.getCellRangeByName(ref)
            if isinstance(v, str): cell.setFormula(v.replace(",", ";").replace("Data!", "$Data."))
            else: cell.setValue(float(v))
    doc.calculateAll()
    def result(x):
        s = x.getString()
        if x.getError(): return {"error": s}
        if x.getType().value == "TEXT" or (x.getType().value == "FORMULA" and x.FormulaResultType2 == 2): return {"text": s}  # FormulaResult.STRING
        if s in ("TRUE", "FALSE"): return {"bool": s == "TRUE"}
        return {"number": x.getValue()}
    out = {name: {ref: result(doc.Sheets.getByName(name).getCellRangeByName(ref)) for ref, v in cells.items() if isinstance(v, str)} for name, cells in BOOK.items()}
    print(json.dumps({"book": BOOK, "results": out}))
    doc.close(True)
finally:
    if p.poll() is None: p.kill()
