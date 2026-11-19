// Open and save (intent a-i11-open-save): a plain ES module, no build step.
//
// parseJSON/toJSON and parseCSV/toCSV are pure text functions over SPEC.md's workbook
// ({sheets: {Sheet1: {A1: 1, ...}}}); createController is the page's logic without the DOM.
// Only download() touches the DOM. Cells are typed and numbers shown by the grid's rules.
import { colName, parseRef, parseInput, display } from "../grid/grid.js";

const isObject = (x) => x !== null && typeof x === "object" && !Array.isArray(x);

/** The workbook in `text`; throws an Error saying why when it is not one. */
export function parseJSON(text) {
  let book;
  try {
    book = JSON.parse(text);
  } catch (e) {
    throw new Error("not a JSON file: " + e.message);
  }
  if (!isObject(book) || !isObject(book.sheets)) throw new Error('not a workbook: expected {"sheets": {...}}');
  for (const [name, cells] of Object.entries(book.sheets)) {
    if (!isObject(cells)) throw new Error(`not a workbook: sheet ${JSON.stringify(name)} is not an object of cells`);
  }
  return book;
}

/** The workbook as SPEC.md's JSON text, every cell and the sheet order kept. */
export function toJSON(book) {
  return JSON.stringify(book, null, 2) + "\n";
}

/** The rows of RFC 4180 text: quoted fields may hold separators, doubled quotes and line breaks. */
function csvRows(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c !== '"') field += c;
      else if (text[i + 1] === '"') { field += '"'; i++; }
      else quoted = false;
    } else if (c === '"') {
      quoted = true;
    } else if (c === ",") {
      row.push(field);
      field = "";
    } else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += c;
    }
  }
  if (field !== "" || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

/** A one-sheet workbook from CSV text, each field typed as the grid types input (an empty field is no cell). */
export function parseCSV(text, sheet = "Sheet1") {
  const cells = {};
  csvRows(String(text).replace(/^﻿/, "")).forEach((fields, r) =>
    fields.forEach((t, c) => {
      const v = parseInput(t);
      if (v !== undefined) cells[colName(c) + (r + 1)] = v;
    }),
  );
  return { sheets: { [sheet]: cells } };
}

const csvField = (v) => {
  const s = display(v);
  return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
};

/** The sheet's computed values as CSV, from A1 to its last used row and column, LF line ends. */
export function toCSV(computed, sheet) {
  const cells = (computed && computed.sheets && computed.sheets[sheet]) || {};
  let rows = 0;
  let cols = 0;
  for (const ref of Object.keys(cells)) {
    const p = parseRef(ref);
    if (!p) continue;
    rows = Math.max(rows, p.row);
    cols = Math.max(cols, p.col + 1);
  }
  let out = "";
  for (let r = 1; r <= rows; r++) {
    const fields = [];
    for (let c = 0; c < cols; c++) fields.push(csvField(cells[colName(c) + r]));
    out += fields.join(",") + "\n";
  }
  return out;
}

/** Hands `text` to the browser as a file called `name`. */
export function download(name, text, type = "text/plain") {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 0);
}

/**
 * The page without the DOM. `compute(book)` returns the computed workbook (the page asks ./engine).
 * state.book is the workbook as typed (what Save JSON writes); state.computed what the grid shows.
 */
export function createController({ compute = async (book) => book } = {}) {
  const state = {
    book: { sheets: { Sheet1: {} } },
    computed: { sheets: { Sheet1: {} } },
    sheet: "Sheet1",
    name: "workbook",
    message: "",
  };
  const recompute = async () => {
    try {
      state.computed = await compute(state.book);
      return true;
    } catch (e) {
      state.message = "Could not compute: " + (e && e.message ? e.message : e);
      return false;
    }
  };
  return {
    state,
    /** Opens a .csv as CSV and anything else as JSON; a bad file leaves the open workbook alone. */
    async openText(fileName, text) {
      let book;
      try {
        book = /\.csv$/i.test(fileName) ? parseCSV(text) : parseJSON(text);
      } catch (e) {
        state.message = `Could not open ${fileName}: ${e.message}`;
        return { ok: false, message: state.message };
      }
      state.book = book;
      state.sheet = Object.keys(book.sheets)[0] || "Sheet1";
      state.name = String(fileName).replace(/^.*[\\/]/, "").replace(/\.[^.]*$/, "") || "workbook";
      state.message = `Opened ${fileName}`;
      if (!(await recompute())) return { ok: false, message: state.message };
      return { ok: true };
    },
    async openFile(file) {
      return this.openText(file.name, await file.text());
    },
    /** One grid edit: only `ref` of the current sheet takes `text` (typed as the grid types it; "" clears). */
    async edit(ref, text) {
      const key = String(ref).toUpperCase();
      const cells = { ...(state.book.sheets[state.sheet] || {}) };
      const v = parseInput(String(text ?? ""));
      if (v === undefined) delete cells[key];
      else cells[key] = v;
      state.book = { ...state.book, sheets: { ...state.book.sheets, [state.sheet]: cells } };
      await recompute();
    },
    saveJSON() {
      return { name: state.name + ".json", text: toJSON(state.book), type: "application/json" };
    },
    saveCSV() {
      return { name: state.name + ".csv", text: toCSV(state.computed, state.sheet), type: "text/csv" };
    },
  };
}
