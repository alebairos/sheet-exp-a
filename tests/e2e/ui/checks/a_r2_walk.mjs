// b1's walk-through in a real browser, with real clicks and keys: open a workbook, edit a formula in the
// formula bar, see the error, fix it, save. Exit 1 with FAIL lines on the first step that does not happen.
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { findBrowser, serve, launch, sleep } from "./a_r2_cdp.mjs";

const fail = (m) => { console.log("FAIL " + m); process.exit(1); };
const browser = findBrowser();
if (!browser) fail("no browser: set CHROME or put google-chrome or chromium on PATH");
const dir = mkdtempSync(join(tmpdir(), "a-r2-walk-"));
const file = join(dir, "walk.json");
const downloads = mkdtempSync(join(tmpdir(), "a-r2-saved-"));
writeFileSync(file, JSON.stringify({ sheets: { Sheet1: { A1: 10, A2: 2, B1: "=A1/A2" } } }));
const server = await serve();
const b = await launch(browser);
const errors = [];
b.on("Runtime.exceptionThrown", (p) => errors.push(p.exceptionDetails.exception?.description ?? p.exceptionDetails.text));
const done = (code) => { b.close(); server.close(); process.exit(code); };
try {
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
    const r = await js(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return null;
      const r = e.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2}; })()`);
    if (!r) fail(`the page has no ${sel}`);
    for (const type of ["mousePressed", "mouseReleased"]) await b.send("Input.dispatchMouseEvent", { type, ...r, button: "left", clickCount: 1 });
  };
  const key = (k, code, vk) => ["keyDown", "keyUp"].reduce((p, type) => p.then(() => b.send("Input.dispatchKeyEvent", { type, key: k, code, windowsVirtualKeyCode: vk })), Promise.resolve());
  const BAR = '#formula-bar input[aria-label="Formula"]';
  const cell = (ref) => `document.querySelector('#grid td[data-ref="${ref}"]')?.textContent.trim() ?? null`;
  const bar = `document.querySelector('${BAR}')?.value ?? null`;
  const barError = `document.querySelector('#formula-bar .error')?.textContent.trim() ?? ""`;
  const typeInBar = async (text) => {
    await click(BAR);
    await b.send("Input.dispatchKeyEvent", { type: "rawKeyDown", commands: ["selectAll"], key: "a", code: "KeyA", modifiers: 2 });
    await b.send("Input.dispatchKeyEvent", { type: "keyUp", key: "a", code: "KeyA", modifiers: 2 });
    await b.send("Input.insertText", { text });
    await key("Enter", "Enter", 13);
  };

  await b.send("Page.navigate", { url: server.url + "/io/index.html" });
  await until("the page loads with its grid", `!!document.querySelector('#grid td[data-ref="A1"]')`, true);
  // 1. Open: the file input, as a user picks the file.
  const doc = await b.send("DOM.getDocument");
  const input = await b.send("DOM.querySelector", { nodeId: doc.root.nodeId, selector: "#open" });
  if (!input.nodeId) fail("the page has no #open file input");
  await b.send("DOM.setFileInputFiles", { nodeId: input.nodeId, files: [file] });
  await until("after Open, B1 shows =A1/A2 computed", cell("B1"), "5");
  // 2. Select B1: the formula bar shows its formula.
  await click('#grid td[data-ref="B1"]');
  await until("selecting B1 shows its formula in the formula bar", bar, "=A1/A2");
  // 3. Edit the formula to divide by a blank cell: the error shows in the cell and in the bar.
  await typeInBar("=A1/A3");
  await until("after the edit, B1 shows the error", cell("B1"), "#DIV/0!");
  await click('#grid td[data-ref="B1"]');
  await until("the formula bar keeps the edited formula", bar, "=A1/A3");
  await until("the formula bar shows the error", barError, "#DIV/0!");
  // 4. Fix it: the value comes back and the error goes.
  await typeInBar("=A1/A2*3");
  await until("after the fix, B1 shows 15", cell("B1"), "15");
  await click('#grid td[data-ref="B1"]');
  await until("the formula bar shows the fixed formula", bar, "=A1/A2*3");
  await until("the error is gone from the formula bar", barError, "");
  // 5. Save JSON: the downloaded workbook keeps the fixed formula as typed and the other cells.
  await click("#save-json");
  const out = join(downloads, "walk.json");
  for (let t = 0; t < 100 && !existsSync(out); t++) await sleep(100);
  await sleep(200);
  if (!existsSync(out)) fail("Save JSON downloaded no walk.json");
  const book = JSON.parse(readFileSync(out, "utf8"));
  const want = { A1: 10, A2: 2, B1: "=A1/A2*3" };
  if (JSON.stringify(book.sheets?.Sheet1) !== JSON.stringify(want)) fail("the saved workbook is " + JSON.stringify(book) + ", wanted Sheet1 " + JSON.stringify(want));
  if (errors.length) fail("the page threw: " + errors.join(" | "));
  console.log("ok walk-through: open, edit a formula, see the error, fix it, save");
  done(0);
} catch (e) { console.log("FAIL " + (e.stack || e)); done(1); }
