// The walk-through in a real browser, with real clicks and keys, on web/io/index.html as serve.py serves it:
// open a workbook, edit a formula in the formula bar, see the error, fix it, save.
// Exits 0 printing "ok", 1 with a FAIL line naming the step that did not happen, 2 when there is no browser.
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { findBrowser, serve, launch, sleep } from "./browser.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const fail = (m) => { throw new Error(m); };
const browser = findBrowser();
if (!browser) { console.log("no browser: set CHROME or put google-chrome or chromium on PATH"); process.exit(2); }

const dir = mkdtempSync(join(tmpdir(), "e2e-ui-walk-"));
const file = join(dir, "walk.json");
const downloads = mkdtempSync(join(tmpdir(), "e2e-ui-saved-"));
writeFileSync(file, JSON.stringify({ sheets: { Sheet1: { A1: 10, A2: 2, B1: "=A1/A2" } } }));

const server = await serve(ROOT);
let b = null;
let code = 1;
try {
  b = await launch(browser);
  const thrown = [];
  b.on("Runtime.exceptionThrown", (p) => thrown.push(p.exceptionDetails.exception?.description ?? p.exceptionDetails.text));
  await b.send("Runtime.enable");
  await b.send("Page.enable");
  await b.send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: downloads });

  const js = async (expr) => (await b.send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result.value;
  const until = async (what, expr, want) => {
    let got;
    for (let t = 0; t < 100; t++) { got = await js(expr); if (got === want) return; await sleep(100); }
    fail(`${what}: wanted ${JSON.stringify(want)}, the page shows ${JSON.stringify(got)}`);
  };
  const click = async (sel) => {
    const at = await js(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return null;
      const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; })()`);
    if (!at) fail(`the page has no ${sel}`);
    for (const type of ["mousePressed", "mouseReleased"]) await b.send("Input.dispatchMouseEvent", { type, ...at, button: "left", clickCount: 1 });
  };
  const BAR = '#formula-bar input[aria-label="Formula"]';
  const cell = (ref) => `document.querySelector('#grid td[data-ref="${ref}"]')?.textContent.trim() ?? null`;
  const barText = `document.querySelector('${BAR}')?.value ?? null`;
  const barError = `document.querySelector('#formula-bar .error')?.textContent.trim() ?? ""`;
  const typeInBar = async (text) => {
    await click(BAR);
    await b.send("Input.dispatchKeyEvent", { type: "rawKeyDown", commands: ["selectAll"], key: "a", code: "KeyA", modifiers: 2 });
    await b.send("Input.dispatchKeyEvent", { type: "keyUp", key: "a", code: "KeyA", modifiers: 2 });
    await b.send("Input.insertText", { text });
    for (const type of ["keyDown", "keyUp"]) await b.send("Input.dispatchKeyEvent", { type, key: "Enter", code: "Enter", windowsVirtualKeyCode: 13 });
  };

  await b.send("Page.navigate", { url: server.url + "/io/index.html" });
  await until("the page loads with its grid and formula bar", `!!document.querySelector('#grid td[data-ref="A1"]') && !!document.querySelector('${BAR}')`, true);
  // 1. Open walk.json through the file input, as a user picks it.
  const doc = await b.send("DOM.getDocument");
  const input = await b.send("DOM.querySelector", { nodeId: doc.root.nodeId, selector: "#open" });
  if (!input.nodeId) fail("the page has no #open file input");
  await b.send("DOM.setFileInputFiles", { nodeId: input.nodeId, files: [file] });
  await until("after Open, B1 shows =A1/A2 computed", cell("B1"), "5");
  // 2. Select B1: the bar shows its formula as typed, no error.
  await click('#grid td[data-ref="B1"]');
  await until("selecting B1 shows its formula in the bar", barText, "=A1/A2");
  await until("B1 has no error", barError, "");
  // 3. Divide by the blank A3: the error shows in the cell and in the bar, B1 still selected.
  await typeInBar("=A1/A3");
  await until("after the edit, B1 shows the error", cell("B1"), "#DIV/0!");
  await until("the bar keeps the edited formula", barText, "=A1/A3");
  await until("the bar shows the error", barError, "#DIV/0!");
  await until("B1 stays selected", `document.querySelector('#grid td.selected')?.dataset.ref ?? null`, "B1");
  // 4. Fix it: the value comes back and the error goes.
  await typeInBar("=A1/A2*3");
  await until("after the fix, B1 shows 15", cell("B1"), "15");
  await until("the bar shows the fixed formula", barText, "=A1/A2*3");
  await until("the error is gone from the bar", barError, "");
  // 5. Save JSON: walk.json comes back with the fixed formula as typed and the other cells.
  await click("#save-json");
  const out = join(downloads, "walk.json");
  for (let t = 0; t < 100 && !existsSync(out); t++) await sleep(100);
  await sleep(200);
  if (!existsSync(out)) fail("Save JSON downloaded no walk.json");
  const saved = JSON.parse(readFileSync(out, "utf8"));
  const want = { sheets: { Sheet1: { A1: 10, A2: 2, B1: "=A1/A2*3" } } };
  if (JSON.stringify(saved) !== JSON.stringify(want)) fail(`saved ${JSON.stringify(saved)}, wanted ${JSON.stringify(want)}`);
  if (thrown.length) fail("the page threw: " + thrown.join(" | "));
  console.log("ok");
  code = 0;
} catch (e) {
  console.log("FAIL " + (e && e.message ? e.message : e));
} finally {
  if (b) b.close();
  server.close();
}
process.exit(code);
