// Unit tests for web/formula_bar/formula_bar.js: node --test tests/web/formula_bar/
import { test } from "node:test";
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const f = await import(pathToFileURL(path.join(root, "web/formula_bar/formula_bar.js")).href);

const raw = { sheets: { Sheet1: { A1: 0.1 + 0.2, A2: 1e21, A3: -0, B1: "=A1/A2", T1: "42", T2: "true", T3: "#DIV/0!" }, Sheet2: {} } };

test("numbers show as Calc's input line", () => {
  assert.equal(f.barText(raw, "Sheet1", "A1"), "0.3");
  assert.equal(f.barText(raw, "Sheet1", "A2"), "1E+21");
  assert.equal(f.barText(raw, "Sheet1", "A3"), "0");
  assert.equal(f.formatNumber(1e-7), "1E-7");
});

test("text that reads as a value keeps the apostrophe and round-trips", () => {
  assert.equal(f.barText(raw, "Sheet1", "T1"), "'42");
  assert.equal(f.barText(raw, "Sheet1", "T2"), "'true");
  assert.equal(f.barText(raw, "Sheet1", "T3"), "#DIV/0!");
  for (const ref of ["T1", "T2", "T3", "B1", "A2"]) {
    const back = f.commit(raw, "Sheet1", ref, f.barText(raw, "Sheet1", ref));
    assert.deepEqual(back.sheets.Sheet1[ref], raw.sheets.Sheet1[ref], ref);
  }
});

test("input parsing", () => {
  assert.equal(f.parseInput("50%"), 0.5);
  assert.equal(f.parseInput(" 7 "), 7);
  assert.equal(f.parseInput("FALSE"), false);
  assert.equal(f.parseInput("'"), undefined);
  assert.equal(f.parseInput("   "), undefined);
  assert.equal(f.parseInput("= 1"), "= 1");
  assert.equal(f.parseInput("1 2"), "1 2");
});

test("commit on a missing sheet or workbook", () => {
  assert.deepEqual(f.commit({ sheets: {} }, "New", "A1", "1").sheets.New, { A1: 1 });
  assert.deepEqual(f.commit(null, "Sheet1", "A1", "x"), { sheets: { Sheet1: { A1: "x" } } });
});

test("errors only for computed error cells; HTML escaped", () => {
  const computed = { sheets: { Sheet1: { B1: { error: "#DIV/0!" }, T3: "#DIV/0!" } } };
  assert.equal(f.errorText(computed, "Sheet1", "B1"), "#DIV/0!");
  assert.equal(f.errorText(computed, "Sheet1", "T3"), "");
  assert.equal(f.errorText(undefined, "Sheet1", "B1"), "");
  const html = f.renderHTML({ raw: { sheets: { Sheet1: { A1: "<b>'x\"" } } }, computed, sheet: "Sheet1", ref: "A1" });
  assert.ok(html.includes('value="&lt;b&gt;&#39;x&quot;"'), html);
  assert.ok(!html.includes('class="error"'));
});

test("mount: Enter commits, Escape cancels, update follows the selection", () => {
  // A minimal stand-in for the DOM: one input whose keydown handler mount wires.
  let input;
  const container = {
    set innerHTML(h) {
      const m = h.match(/value="([^"]*)"/);
      input = { value: m ? m[1] : "", handlers: {}, addEventListener(t, fn) { this.handlers[t] = fn; } };
      this.html = h;
    },
    querySelector() { return input; },
  };
  const commits = [];
  const bar = f.mount(container, { raw, computed: {}, sheet: "Sheet1", ref: "B1" }, { onCommit: (r, ref) => commits.push([r, ref]) });
  assert.equal(input.value, "=A1/A2");
  input.value = "=A1*2";
  input.handlers.keydown({ key: "Enter", preventDefault() {} });
  assert.equal(commits.length, 1);
  assert.equal(commits[0][0].sheets.Sheet1.B1, "=A1*2");
  assert.equal(bar.state.raw.sheets.Sheet1.B1, "=A1*2");
  input.value = "junk";
  input.handlers.keydown({ key: "Escape", preventDefault() {} });
  assert.equal(input.value, "=A1*2");
  assert.equal(commits.length, 1);
  bar.update({ ref: "A1" });
  assert.ok(container.html.includes(">A1<"));
  assert.equal(input.value, "0.3");
});
