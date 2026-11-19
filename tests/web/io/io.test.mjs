// Node tests for web/io/io.js (intent a-i11-open-save), beyond the acceptance checks.
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseJSON, toJSON, parseCSV, toCSV, createController } from "../../../web/io/io.js";

test("a workbook with no sheets or an empty sheet saves as opened", () => {
  for (const book of [{ sheets: {} }, { sheets: { Empty: {} } }]) assert.deepEqual(parseJSON(toJSON(book)), book);
});

test("a sheet that is not an object of cells is refused", () => {
  assert.throws(() => parseJSON('{"sheets": {"Sheet1": [1, 2]}}'), /Sheet1/);
  assert.throws(() => parseJSON('{"sheets": {"Sheet1": null}}'), /not a workbook/);
});

test("CSV with old Mac line ends, a BOM and an empty line", () => {
  assert.deepEqual(parseCSV("﻿a,1\r\rb,2\r"), { sheets: { Sheet1: { A1: "a", B1: 1, A3: "b", B3: 2 } } });
});

test("an empty CSV is an empty sheet, and an empty sheet saves as nothing", () => {
  assert.deepEqual(parseCSV(""), { sheets: { Sheet1: {} } });
  assert.equal(toCSV({ sheets: { Sheet1: {} } }, "Sheet1"), "");
  assert.equal(toCSV({ sheets: {} }, "Missing"), "");
});

test("numbers in CSV are shown as Calc's general format", () => {
  assert.equal(toCSV({ sheets: { S: { A1: 1e20, B1: 1e-7, C1: 1 / 3 } } }, "S"), "1E+20,1E-07,0.333333333333333\n");
});

test("columns past Z round-trip", () => {
  const vals = { sheets: { Sheet1: { AA1: 1, AB2: "x" } } };
  assert.deepEqual(parseCSV(toCSV(vals, "Sheet1")), vals);
});

test("an engine that fails leaves a message and the workbook as typed", async () => {
  const c = createController({ compute: async () => { throw new Error("down"); } });
  const r = await c.openText("dir/book.json", '{"sheets": {"S": {"A1": "=1+1"}}}');
  assert.equal(r.ok, false);
  assert.match(c.state.message, /Could not compute: down/);
  assert.equal(c.saveJSON().name, "book.json");
  assert.equal(JSON.parse(c.saveJSON().text).sheets.S.A1, "=1+1");
});

test("edit keeps other sheets and is case-insensitive in its ref", async () => {
  const c = createController();
  await c.openText("b.json", '{"sheets": {"One": {"A1": 1}, "Two": {"A1": "=One!A1"}}}');
  await c.edit("b2", "x");
  assert.deepEqual(JSON.parse(c.saveJSON().text), { sheets: { One: { A1: 1, B2: "x" }, Two: { A1: "=One!A1" } } });
});
