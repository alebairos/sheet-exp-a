#!/bin/sh
# b1 and b2 in the browser: the page's Open, Save JSON and Save CSV are wired to the grid and the engine.
# Contract (plan a-i11-open-save):
#   web/io/io.js also exports createController({compute}) -> controller with
#     async openText(fileName, text) -> {ok: true} or {ok: false, message}   (.csv opens as CSV, else JSON)
#     async edit(ref, text)  one grid edit: writes only the typed cell (the grid's typing rules; "" clears it)
#       into the stored workbook's current sheet, then recomputes;  state -> {book, computed, sheet, name, message}
#     saveJSON() / saveCSV() -> {name, text, type}  (JSON keeps the book as typed; CSV the computed values)
#   web/io/index.html: the page (Open file input #open, buttons #save-json and #save-csv, #message, #grid),
#     loading ./io.js and ../grid/grid.js; each grid edit goes to the controller's edit(ref, text), never the
#     grid's whole computed book back through setBook. web/io/serve.py: python3 web/io/serve.py [port] serves
#     web/ and answers POST /compute with ./engine's computed workbook.
set -eu
cd "$(dirname "$0")/../../../.."
export PYTHONDONTWRITEBYTECODE=1
for f in web/io/io.js web/io/index.html web/io/serve.py; do [ -f "$f" ] || { echo "FAIL: $f missing"; exit 1; }; done
node --input-type=module -e '
import { pathToFileURL } from "node:url";
import { readFileSync } from "node:fs";
const io = await import(pathToFileURL("web/io/io.js").href);
let bad = 0;
const fail = (m) => { bad++; console.log("FAIL " + m); };
if (typeof io.createController !== "function") { console.log("FAIL createController is not exported"); process.exit(1); }
// A stand-in engine: "=<ref>*<n>" is computed from the given book; any other formula is 99.
const calls = [];
const compute = async (book) => {
  calls.push(JSON.parse(JSON.stringify(book)));
  return {sheets: Object.fromEntries(Object.entries(book.sheets).map(([s, c]) => [s, Object.fromEntries(Object.entries(c).map(([k, v]) => {
    if (typeof v !== "string" || !v.startsWith("=")) return [k, v];
    const m = /^=([A-Z]+[0-9]+)\*([0-9]+)$/.exec(v);
    return [k, m && typeof c[m[1]] === "number" ? c[m[1]] * Number(m[2]) : 99];
  }))]))};
};
const c = io.createController({compute});
if (typeof c.edit !== "function") fail("the controller has no edit(ref, text)");
let r = await c.openText("book.json", JSON.stringify({sheets: {Data: {A1: 2, B1: "=A1*2", C1: "a,b", D1: "=SUM(A1:A2)"}, Other: {}}}));
if (!r || r.ok !== true) fail("opening a JSON workbook did not succeed: " + JSON.stringify(r));
if (c.state.sheet !== "Data") fail("the first sheet is not shown after opening: " + c.state.sheet);
if (!calls.length) fail("opening did not ask the engine to compute");
if (!c.state.computed || c.state.computed.sheets.Data.B1 !== 4) fail("the computed workbook is not kept");
let s = c.saveJSON();
if (s.name !== "book.json" || JSON.parse(s.text).sheets.Data.B1 !== "=A1*2") fail("Save JSON does not keep the formula: " + JSON.stringify(s));
s = c.saveCSV();
if (s.name !== "book.csv" || s.text !== "2,4,\"a,b\",99\n") fail("Save CSV does not write the computed values: " + JSON.stringify(s));
// The HITL case: open {A1: 2, B1: "=A1*2"}, type 7 into A1; JSON keeps the formula, CSV shows it recomputed.
r = await c.openText("edit.json", JSON.stringify({sheets: {Sheet1: {A1: 2, B1: "=A1*2"}}}));
if (!r || r.ok !== true) fail("opening edit.json did not succeed: " + JSON.stringify(r));
const before = calls.length;
if (typeof c.edit === "function") await c.edit("A1", "7");
const saved = JSON.parse(c.saveJSON().text).sheets.Sheet1;
if (saved.A1 !== 7) fail("an edit through edit() is not saved: A1 = " + JSON.stringify(saved.A1));
if (saved.B1 !== "=A1*2") fail("an edit replaced the formula in B1 with a computed value: B1 = " + JSON.stringify(saved.B1));
if (JSON.stringify(Object.keys(saved).sort()) !== "[\"A1\",\"B1\"]") fail("an edit wrote cells it was not given: " + JSON.stringify(saved));
if (calls.length <= before) fail("an edit did not recompute");
else if (calls[calls.length - 1].sheets.Sheet1.B1 !== "=A1*2") fail("an edit sent the engine a computed B1, not the formula");
if (c.saveCSV().text !== "7,14\n") fail("Save CSV after the edit does not show the recomputed B1: " + JSON.stringify(c.saveCSV().text));
if (typeof c.edit === "function") await c.edit("C1", "=A1*3");
if (JSON.parse(c.saveJSON().text).sheets.Sheet1.C1 !== "=A1*3") fail("a typed formula is not kept as typed");
if (c.saveCSV().text !== "7,14,21\n") fail("a typed formula is not computed: " + JSON.stringify(c.saveCSV().text));
if (typeof c.edit === "function") await c.edit("C1", "");
if ("C1" in JSON.parse(c.saveJSON().text).sheets.Sheet1) fail("typing nothing does not clear the cell");
if (typeof c.edit === "function") await c.edit("A2", "TRUE");
if (JSON.parse(c.saveJSON().text).sheets.Sheet1.A2 !== true) fail("TRUE is not typed as a boolean like the grid does");
r = await c.openText("broken.json", "{not json");
if (!r || r.ok !== false || !r.message) fail("a bad file does not give a message: " + JSON.stringify(r));
if (!c.state.message) fail("the message for a bad file is not in the state");
if (JSON.parse(c.saveJSON().text).sheets.Sheet1.A1 !== 7) fail("a bad file replaced the open workbook");
r = await c.openText("list.csv", "x,1\ny,2\n");
if (!r || r.ok !== true || c.state.book.sheets[c.state.sheet].B2 !== 2) fail("opening a CSV did not load its values");
if (c.saveCSV().text !== "x,1\ny,2\n") fail("CSV opened then saved changed: " + JSON.stringify(c.saveCSV().text));
const html = readFileSync("web/io/index.html", "utf8");
for (const id of ["open", "save-json", "save-csv", "message", "grid"]) if (!new RegExp(`id="${id}"`).test(html)) fail(`index.html has no element #${id}`);
if (!/type="file"[^>]*id="open"|id="open"[^>]*type="file"/.test(html)) fail("#open is not a file input");
if (!/from\s+"\.\/io\.js"/.test(html)) fail("index.html does not load ./io.js");
if (!/from\s+"\.\.\/grid\/grid\.js"/.test(html)) fail("index.html does not load the grid (../grid/grid.js)");
if (!/createController\s*\(/.test(html) || !/\bmount\s*\(/.test(html)) fail("index.html does not create the controller and mount the grid");
if (!/\.\s*edit\s*\(/.test(html)) fail("index.html does not send grid edits to the controller (controller.edit(ref, text))");
if (/setBook\s*\(/.test(html)) fail("index.html still sends the grid'"'"'s whole book back through setBook");
if (bad) process.exit(1);
console.log("ok page and controller");
'
python3 - <<'PY'
import json, socket, subprocess, sys, time, urllib.request
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
p = subprocess.Popen([sys.executable, "web/io/serve.py", str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
bad = 0
try:
    base = "http://127.0.0.1:%d" % port
    for _ in range(50):
        try:
            urllib.request.urlopen(base + "/io/index.html", timeout=1); break
        except Exception:
            time.sleep(0.1)
    page = urllib.request.urlopen(base + "/io/index.html", timeout=5).read().decode()
    if 'id="save-csv"' not in page:
        bad += 1; print("FAIL serve.py does not serve /io/index.html")
    grid = urllib.request.urlopen(base + "/grid/grid.js", timeout=5)
    if "javascript" not in grid.headers.get("Content-Type", ""):
        bad += 1; print("FAIL /grid/grid.js is not served as JavaScript (ES modules need it): %s" % grid.headers.get("Content-Type"))
    book = {"sheets": {"Sheet1": {"A1": 1, "A2": "text", "A3": True}, "Sheet2": {}}}
    req = urllib.request.Request(base + "/compute", data=json.dumps(book).encode(), headers={"Content-Type": "application/json"})
    want = json.loads(subprocess.run(["./engine", "-"], input=json.dumps(book), capture_output=True, text=True).stdout)
    got = json.loads(urllib.request.urlopen(req, timeout=10).read())
    if got != want:
        bad += 1; print("FAIL POST /compute: got %r, want ./engine's %r" % (got, want))
finally:
    p.terminate(); p.wait(5)
if bad:
    sys.exit(1)
print("ok serve.py")
PY
