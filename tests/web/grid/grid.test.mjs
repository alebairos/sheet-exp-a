// Unit tests for web/grid/grid.js: node --test tests/web/grid/
import { test } from "node:test";
import assert from "node:assert/strict";
import * as g from "../../../web/grid/grid.js";

test("column names and references", () => {
  assert.deepEqual([0, 25, 26, 51, 52, 701, 702].map(g.colName), ["A", "Z", "AA", "AZ", "BA", "ZZ", "AAA"]);
  for (const i of [0, 25, 26, 701, 702]) assert.equal(g.colIndex(g.colName(i)), i);
  assert.deepEqual(g.parseRef("AB12"), { col: 27, row: 12 });
  assert.equal(g.parseRef("A0"), null);
  assert.equal(g.parseRef("12"), null);
});

test("display follows Calc's general format", () => {
  const cases = [[1, "1"], [0, "0"], [-3, "-3"], [2.5, "2.5"], [0.1 + 0.2, "0.3"], [1 / 3, "0.333333333333333"],
    [1e20, "1E+20"], [1e-7, "1E-07"], [123456789012, "123456789012"], [0.0001, "0.0001"], [-1.5e-10, "-1.5E-10"],
    [true, "TRUE"], [false, "FALSE"], [null, ""], [undefined, ""], ["a", "a"], [{ error: "#NUM!" }, "#NUM!"]];
  for (const [v, want] of cases) assert.equal(g.display(v), want, JSON.stringify(v));
});

test("typed input becomes a value", () => {
  const cases = [["42", 42], [".5", 0.5], ["-1e3", -1000], ["TRUE", true], ["False", false], ["abc", "abc"],
    ["=A1", "=A1"], [" 1", " 1"], ["1e999", "1e999"], ["", undefined]];
  for (const [text, want] of cases) assert.equal(g.parseInput(text), want, text);
  assert.equal(g.inputText({ error: "#N/A" }), "");
  assert.equal(g.inputText(true), "TRUE");
});

test("state functions are pure", () => {
  const book = { sheets: { Sheet1: { A1: 1 } } };
  const s0 = g.createState(book, "Sheet1");
  const s1 = g.edit(g.select(s0, "b2"), "b2", "7");
  assert.equal(s1.selected, "B2");
  assert.deepEqual(s1.book.sheets.Sheet1, { A1: 1, B2: 7 });
  assert.deepEqual(book.sheets.Sheet1, { A1: 1 });
  assert.equal(s0.selected, "A1");
  assert.equal(g.edit(s1, "A1", "").book.sheets.Sheet1.A1, undefined);
});

test("createState defaults to the first sheet", () => {
  assert.equal(g.createState({ sheets: { Data: {}, Other: {} } }).sheet, "Data");
  assert.equal(g.createState(null).sheet, "Sheet1");
  assert.equal(g.edit(g.createState({ sheets: {} }, "New"), "A1", "x").book.sheets.New.A1, "x");
});

test("move stays inside the sheet", () => {
  const s = g.createState({ sheets: { S: {} } }, "S");
  assert.equal(g.move(s, -1, -1).selected, "A1");
  assert.equal(g.move(s, 1, 2).selected, "B3");
  assert.equal(g.move(g.select(s, "Z1"), 1, 0).selected, "AA1");
});

test("renderHTML marks kinds and escapes text", () => {
  const s = g.select(g.createState({ sheets: { S: { A1: 5, B1: "<b>&", A2: { error: "#REF!" }, B2: true } } }, "S"), "B2");
  const html = g.renderHTML(s, { rows: 2, cols: 2 });
  assert.match(html, /<td data-ref="A1" class="num">5<\/td>/);
  assert.match(html, /<td data-ref="B1">&lt;b&gt;&amp;<\/td>/);
  assert.match(html, /<td data-ref="A2" class="err">#REF!<\/td>/);
  assert.match(html, /<td data-ref="B2" class="selected num">TRUE<\/td>/);
  assert.equal((html.match(/<td /g) || []).length, 4);
});
