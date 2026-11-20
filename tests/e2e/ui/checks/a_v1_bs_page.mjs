// Shared by the a-v1-big-sheets checks: the big workbook, the app page in headless Chrome (a_r2_cdp.mjs) and
// what "the user sees a cell" means. Node standard library only.
import { mkdtempSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { findBrowser, serve, launch, sleep } from "./a_r2_cdp.mjs";

export const CALC = JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)), "a_v1_bs_calc.json"), "utf8"));
export const fail = (m) => { console.log("FAIL " + m); process.exit(1); };

// big.csv: header colA..colL, then rows 2..2001, cell = row*100 + column index (A2 = 200, L2001 = 200111).
export function bigCSV() {
  const rows = [[...Array(12)].map((_, c) => "col" + String.fromCharCode(65 + c)).join(",")];
  for (let r = 2; r <= 2001; r++) rows.push([...Array(12)].map((_, c) => r * 100 + c).join(","));
  return rows.join("\n") + "\n";
}

// The same cells as a workbook JSON, plus the formulas of a_v1_bs_calc.json.
export function bigJSON() {
  const cells = {};
  bigCSV().trim().split("\n").forEach((line, i) => line.split(",").forEach((v, c) => {
    cells[String.fromCharCode(65 + c) + (i + 1)] = i === 0 ? v : Number(v);
  }));
  return JSON.stringify({ sheets: { Sheet1: { ...cells, ...CALC.formulas } } });
}

// Opens the app page (web/io/serve.py, /io/index.html, window 1200x900) and picks `name` with `text` in #open.
export async function openPage(name, text) {
  const browser = findBrowser();
  if (!browser) fail("no browser: set CHROME or put google-chrome or chromium on PATH");
  const dir = mkdtempSync(join(tmpdir(), "a-v1-bs-"));
  const file = join(dir, name);
  writeFileSync(file, text);
  const server = await serve();
  const b = await launch(browser);
  const errors = [];
  b.on("Runtime.exceptionThrown", (p) => errors.push(p.exceptionDetails.exception?.description ?? p.exceptionDetails.text));
  const done = (code) => { if (code === 0 && errors.length) { console.log("FAIL the page threw: " + errors.join(" | ")); code = 1; } b.close(); server.close(); process.exit(code); };
  await b.send("Runtime.enable");
  await b.send("Page.enable");
  const js = async (expr) => (await b.send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result.value;
  const until = async (what, expr, want, tries = 300) => {
    let got;
    for (let t = 0; t < tries; t++) { got = await js(expr); if (got === want) return; await sleep(100); }
    fail(`${what}: wanted ${JSON.stringify(want)}, the page shows ${JSON.stringify(got)}`);
  };
  await b.send("Page.navigate", { url: server.url + "/io/index.html" });
  await until("the page loads with its grid", `!!document.querySelector('#grid td[data-ref="A1"]')`, true);
  const doc = await b.send("DOM.getDocument");
  const input = await b.send("DOM.querySelector", { nodeId: doc.root.nodeId, selector: "#open" });
  if (!input.nodeId) fail("the page has no #open file input");
  await b.send("DOM.setFileInputFiles", { nodeId: input.nodeId, files: [file] });
  await until(`after Open, A2 shows ${CALC.csv.A2}`, text_(`A2`), CALC.csv.A2);
  return { b, js, until, done, errors };
}

const text_ = (ref) => `document.querySelector('#grid td[data-ref="${ref}"]')?.textContent.trim() ?? null`;
export const cellText = text_;

// "The user sees it": the element is in the window, and the point at its centre hits it (not covered, not
// clipped by a scroll box). For a cell: td[data-ref]; for a header: a th whose text is exactly `label`.
export const seen = (sel, label) => `(() => {
  const els = [...document.querySelectorAll(${JSON.stringify(sel)})].filter((e) => ${label === undefined ? "true" : `e.textContent.trim() === ${JSON.stringify(label)}`});
  return els.some((e) => { const r = e.getBoundingClientRect();
    if (r.width < 4 || r.height < 4 || r.left < 0 || r.top < 0 || r.right > innerWidth || r.bottom > innerHeight) return false;
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !!hit && (hit === e || e.contains(hit)); });
})()`;
export const seenCell = (ref) => seen(`#grid td[data-ref="${ref}"]`);
export const selectedRef = `document.querySelector('#grid td.selected')?.dataset.ref ?? null`;

// One real key press (keyDown + keyUp) through the DevTools input domain, as a keyboard sends it.
const VK = { ArrowDown: 40, ArrowUp: 38, ArrowLeft: 37, ArrowRight: 39, PageDown: 34, PageUp: 33, Enter: 13 };
export const press = async (b, key) => {
  for (const type of ["keyDown", "keyUp"]) {
    const p = { type, key, code: key, windowsVirtualKeyCode: VK[key] ?? key.toUpperCase().charCodeAt(0) };
    if (type === "keyDown" && key.length === 1) p.text = key;
    await b.send("Input.dispatchKeyEvent", p);
  }
};
// After the next paint: the frame callback runs before the paint, the task it queues runs after it.
export const frames = `new Promise((ok) => requestAnimationFrame(() => setTimeout(() => ok(true), 0)))`;
export { sleep };

// Some desktop Chromium builds open an extension tab at start that hides the test page; a hidden page draws no
// frames. Before a step and if its frames do not come within 1 s, the page is brought to the front; a step
// during which the page was hidden is run again (at most twice) and its time is not counted.
export async function timedStep(b, js, act) {
  for (let attempt = 0; ; attempt++) {
    if ((await js("document.visibilityState")) !== "visible") await b.send("Page.bringToFront");
    const t0 = performance.now();
    await act();
    const drawn = await Promise.race([js(frames), sleep(1000).then(() => false)]);
    const dt = performance.now() - t0;
    if (drawn || attempt === 2 || (await js("document.visibilityState")) === "visible") { if (!drawn) await js(frames); return dt; }
    await b.send("Page.bringToFront");
  }
}
