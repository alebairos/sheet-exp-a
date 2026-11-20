// One workbook in a real browser, with real clicks, on web/io/index.html as serve.py serves it:
// open books/<name>.json, see its first sheet as Calc shows it (books/<name>.shown.json, A1:H20), select its
// first formula cell and read the formula as typed in the formula bar, Save JSON and get the workbook back.
// Usage: node browser_walk.mjs <name>. Exits 0 printing "ok", 1 with FAIL lines, 2 when there is no browser.
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { findBrowser, serve, launch, sleep } from "../ui/browser.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..", "..");
const name = process.argv[2];
if (!name) { console.log("FAIL usage: node browser_walk.mjs <name>"); process.exit(1); }
const browser = findBrowser();
if (!browser) { console.log("no browser: set CHROME or put google-chrome or chromium on PATH"); process.exit(2); }

const file = join(HERE, "books", name + ".json");
const book = JSON.parse(readFileSync(file, "utf8"));
const shown = JSON.parse(readFileSync(join(HERE, "books", name + ".shown.json"), "utf8"));
const first = Object.keys(book.sheets)[0];
const COLS = "ABCDEFGH", ROWS = 20;
const want = {};
for (let r = 1; r <= ROWS; r++) for (const c of COLS) want[c + r] = String(shown.sheets[first][c + r] ?? "").trim();

const fails = [];
const downloads = mkdtempSync(join(tmpdir(), "e2e-workbooks-saved-"));
const server = await serve(ROOT);
let b = null;
try {
  b = await launch(browser);
  const thrown = [];
  b.on("Runtime.exceptionThrown", (p) => thrown.push(p.exceptionDetails.exception?.description ?? p.exceptionDetails.text));
  await b.send("Runtime.enable");
  await b.send("Page.enable");
  await b.send("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: downloads });
  const js = async (expr) => (await b.send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result.value;
  const click = async (sel) => {
    const at = await js(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return null;
      const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; })()`);
    if (!at) throw new Error(`the page has no ${sel}`);
    for (const type of ["mousePressed", "mouseReleased"]) await b.send("Input.dispatchMouseEvent", { type, ...at, button: "left", clickCount: 1 });
  };
  const BAR = '#formula-bar input[aria-label="Formula"]';
  const grid = `(() => { const o = {}; for (const td of document.querySelectorAll('#grid td[data-ref]')) o[td.dataset.ref] = td.textContent.trim(); return o; })()`;

  await b.send("Page.navigate", { url: server.url + "/io/index.html" });
  for (let t = 0; t < 100 && !(await js(`!!document.querySelector('#grid td[data-ref="A1"]') && !!document.querySelector('${BAR}')`)); t++) await sleep(100);
  // 1. Open the workbook through the file input, as a user picks it.
  const doc = await b.send("DOM.getDocument");
  const input = await b.send("DOM.querySelector", { nodeId: doc.root.nodeId, selector: "#open" });
  if (!input.nodeId) throw new Error("the page has no #open file input");
  await b.send("DOM.setFileInputFiles", { nodeId: input.nodeId, files: [file] });
  // 2. Display: every visible cell of the first sheet as Calc shows it, the rest blank.
  let got = {}, bad = [];
  for (let t = 0; t < 100; t++) {
    got = await js(grid);
    bad = Object.keys(want).filter((a) => got[a] !== want[a]);
    if (!bad.length) break;
    await sleep(100);
  }
  for (const a of bad.slice(0, 20)) fails.push(`${first}!${a}: Calc shows ${JSON.stringify(want[a])}, the grid ${JSON.stringify(got[a] ?? null)}`);
  if (bad.length > 20) fails.push(`... and ${bad.length - 20} more cells`);
  // 3. The formula bar shows the first formula cell as typed.
  const [ref, formula] = Object.entries(book.sheets[first]).find(([, v]) => typeof v === "string" && v.startsWith("="));
  await click(`#grid td[data-ref="${ref}"]`);
  let bar = null;
  for (let t = 0; t < 50 && (bar = await js(`document.querySelector('${BAR}')?.value ?? null`)) !== formula; t++) await sleep(100);
  if (bar !== formula) fails.push(`selecting ${ref} shows ${JSON.stringify(bar)} in the formula bar, wanted ${formula}`);
  // 4. Save JSON: the workbook comes back as opened, every sheet and cell, formulas as typed.
  await click("#save-json");
  const out = join(downloads, name + ".json");
  for (let t = 0; t < 100 && !existsSync(out); t++) await sleep(100);
  await sleep(200);
  if (!existsSync(out)) fails.push(`Save JSON downloaded no ${name}.json`);
  else if (JSON.stringify(JSON.parse(readFileSync(out, "utf8"))) !== JSON.stringify(book)) fails.push(`the saved ${name}.json is not the workbook opened`);
  if (thrown.length) fails.push("the page threw: " + thrown.join(" | "));
} catch (e) {
  fails.push(String(e && e.message ? e.message : e));
} finally {
  if (b) b.close();
  server.close();
}
for (const f of fails) console.log("FAIL " + name + ": " + f);
if (!fails.length) console.log("ok " + name);
process.exit(fails.length ? 1 : 0);
