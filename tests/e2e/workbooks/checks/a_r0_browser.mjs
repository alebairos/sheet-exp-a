// b2 in a real browser: each plan workbook opens, its first sheet shows as Calc computes it, the formula bar
// shows a formula as typed, and Save JSON gives the workbook back unchanged. Exit 1 with FAIL lines.
import { mkdtempSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { findBrowser, serve, launch, sleep } from "./a_r0_cdp.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const books = JSON.parse(readFileSync(join(here, "a_r0_books.json"), "utf8"));
const shown = JSON.parse(readFileSync(join(here, "a_r0_shown.json"), "utf8"));
const fails = [];
const browser = findBrowser();
if (!browser) { console.log("FAIL no browser: set CHROME or put google-chrome or chromium on PATH"); process.exit(1); }
const server = await serve();
const b = await launch(browser);
const errors = [];
b.on("Runtime.exceptionThrown", (p) => errors.push(p.exceptionDetails.exception?.description ?? p.exceptionDetails.text));
const js = async (expr) => (await b.send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result.value;
const COLS = "ABCDEFGH", ROWS = 20;
const gridText = `(() => { const o = {}; for (const td of document.querySelectorAll('#grid td[data-ref]')) o[td.dataset.ref] = td.textContent.trim(); return o; })()`;
const click = async (sel) => {
  const r = await js(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return null;
    const r = e.getBoundingClientRect(); return {x: r.x + r.width / 2, y: r.y + r.height / 2}; })()`);
  if (!r) return false;
  for (const type of ["mousePressed", "mouseReleased"]) await b.send("Input.dispatchMouseEvent", { type, ...r, button: "left", clickCount: 1 });
  return true;
};
try {
  await b.send("Runtime.enable");
  await b.send("Page.enable");
  await b.send("Page.navigate", { url: server.url + "/io/index.html" });
  for (let t = 0; t < 100 && !(await js(`!!document.querySelector('#grid td[data-ref="A1"]')`)); t++) await sleep(100);
  for (const name of Object.keys(books)) {
    const book = books[name], first = Object.keys(book.sheets)[0], cells = book.sheets[first];
    const want = {};
    for (let r = 1; r <= ROWS; r++) for (const c of COLS) want[c + r] = (shown[name].sheets[first][c + r] ?? "").trim();
    const dir = mkdtempSync(join(tmpdir(), "a-r0-book-")), saved = mkdtempSync(join(tmpdir(), "a-r0-saved-"));
    writeFileSync(join(dir, name + ".json"), JSON.stringify(book));
    await b.send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: saved });
    const doc = await b.send("DOM.getDocument");
    const input = await b.send("DOM.querySelector", { nodeId: doc.root.nodeId, selector: "#open" });
    if (!input.nodeId) { fails.push("the page has no #open file input"); break; }
    await b.send("DOM.setFileInputFiles", { nodeId: input.nodeId, files: [join(dir, name + ".json")] });
    // 1. Display: every visible cell of the first sheet as Calc shows it (wait until the page settles).
    let got = {}, bad = [];
    for (let t = 0; t < 100; t++) {
      got = await js(gridText);
      bad = Object.keys(want).filter((a) => got[a] !== want[a]);
      if (!bad.length) break;
      await sleep(100);
    }
    for (const a of bad.slice(0, 20)) fails.push(`${name} ${first}!${a}: Calc shows ${JSON.stringify(want[a])}, the grid ${JSON.stringify(got[a] ?? null)}`);
    // 2. The formula bar shows the first formula cell as typed.
    const [ref, f] = Object.entries(cells).find(([, v]) => typeof v === "string" && v.startsWith("="));
    if (!(await click(`#grid td[data-ref="${ref}"]`))) fails.push(`${name}: the grid has no cell ${ref}`);
    const bar = `document.querySelector('#formula-bar input[aria-label="Formula"]')?.value ?? null`;
    let v = null;
    for (let t = 0; t < 50 && (v = await js(bar)) !== f; t++) await sleep(100);
    if (v !== f) fails.push(`${name}: selecting ${ref} shows ${JSON.stringify(v)} in the formula bar, wanted ${f}`);
    // 3. Save JSON: the workbook comes back as opened, every sheet and cell, formulas as typed.
    if (!(await click("#save-json"))) fails.push("the page has no #save-json");
    const out = join(saved, name + ".json");
    for (let t = 0; t < 100 && !existsSync(out); t++) await sleep(100);
    await sleep(200);
    if (!existsSync(out)) fails.push(`${name}: Save JSON downloaded no ${name}.json`);
    else if (JSON.stringify(JSON.parse(readFileSync(out, "utf8"))) !== JSON.stringify(book)) fails.push(`${name}: the saved ${name}.json is not the workbook opened`);
  }
  if (errors.length) fails.push("the page threw: " + errors.join(" | "));
} catch (e) { fails.push(String(e.stack || e)); }
b.close(); server.close();
for (const f of fails) console.log("FAIL " + f);
if (!fails.length) console.log("ok budget, grades and orders open, display and save in the browser");
process.exit(fails.length ? 1 : 0);
