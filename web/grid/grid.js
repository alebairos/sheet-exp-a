// The spreadsheet grid (intent a-i9-grid): a plain ES module, no build step.
//
// Everything but mount() is a pure function over the workbook JSON of SPEC.md
// ({sheets: {Sheet1: {A1: 1, ...}}}), so it runs and is tested under Node.js.
// mount() is the only code that touches the DOM.

/** Column index (0-based) to its letters: 0 -> A, 25 -> Z, 26 -> AA. */
export function colName(i) {
  let s = "";
  for (let n = i + 1; n > 0; n = Math.floor((n - 1) / 26)) {
    s = String.fromCharCode(65 + ((n - 1) % 26)) + s;
  }
  return s;
}

/** Letters to a column index (0-based): A -> 0, AA -> 26. */
export function colIndex(letters) {
  let n = 0;
  for (const ch of letters.toUpperCase()) n = n * 26 + (ch.charCodeAt(0) - 64);
  return n - 1;
}

/** "B12" -> {col: 1, row: 12}; null if it is not a cell reference. */
export function parseRef(ref) {
  const m = /^([A-Za-z]+)([1-9]\d*)$/.exec(ref);
  return m ? { col: colIndex(m[1]), row: Number(m[2]) } : null;
}

/** A number in Calc's general format: up to 15 significant digits, 1E+20, 1E-07. */
export function formatNumber(x) {
  if (!Number.isFinite(x)) return "#NUM!";
  if (x === 0) return "0";
  const exp = Math.floor(Math.log10(Math.abs(Number(x.toPrecision(15)))));
  if (exp < -4 || exp >= 15) {
    let [mant, e] = x.toExponential(14).split("e");
    if (mant.includes(".")) mant = mant.replace(/0+$/, "").replace(/\.$/, "");
    const sign = e[0] === "-" ? "-" : "+";
    return `${mant}E${sign}${e.replace(/^[+-]/, "").padStart(2, "0")}`;
  }
  return String(Number(x.toPrecision(15)));
}

/** The text a cell shows for a computed JSON value. */
export function display(v) {
  if (v === null || v === undefined) return "";
  if (typeof v === "boolean") return v ? "TRUE" : "FALSE";
  if (typeof v === "number") return formatNumber(v);
  if (typeof v === "object") return typeof v.error === "string" ? v.error : "";
  return String(v);
}

const escapeHTML = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const cellsOf = (state) => (state.book.sheets && state.book.sheets[state.sheet]) || {};

/** The grid's state: the workbook, the sheet shown and the selected cell. */
export function createState(book, sheet) {
  const b = book && book.sheets ? book : { sheets: {} };
  const name = sheet ?? Object.keys(b.sheets)[0] ?? "Sheet1";
  return { book: b, sheet: name, selected: "A1" };
}

export function select(state, ref) {
  return { ...state, selected: String(ref).toUpperCase() };
}

/** The selected cell moved by (dc, dr), never past A1. */
export function move(state, dc, dr) {
  const p = parseRef(state.selected) || { col: 0, row: 1 };
  return select(state, colName(Math.max(0, p.col + dc)) + Math.max(1, p.row + dr));
}

const NUMBER_TEXT = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;

/** Typed text as a cell value: a number, TRUE/FALSE, text; undefined for "" (a blank). */
export function parseInput(text) {
  if (text === "") return undefined;
  if (NUMBER_TEXT.test(text)) {
    const x = Number(text);
    if (Number.isFinite(x)) return x;
  }
  if (/^true$/i.test(text)) return true;
  if (/^false$/i.test(text)) return false;
  return text;
}

/**
 * Text typed into a cell's editor as a cell value: parseInput, except that a leading apostrophe makes
 * the rest text as typed (Calc's rule, and the formula bar's: '007 is the text "007", ' alone is a
 * blank). The editor can open with that apostrophe (the page's textOf), so a commit reads it back.
 */
export function typedInput(text) {
  const s = String(text ?? "");
  if (s.startsWith("'")) return s.length > 1 ? s.slice(1) : undefined;
  return parseInput(s);
}

/** The text an editor starts with for a cell: its value as typed back. */
export function inputText(v) {
  if (v === null || v === undefined || typeof v === "object") return "";
  return display(v);
}

/** The state whose sheet holds `text` typed into `ref`. */
export function edit(state, ref, text) {
  const key = String(ref).toUpperCase();
  const cells = { ...cellsOf(state) };
  const v = typedInput(text);
  if (v === undefined) delete cells[key];
  else cells[key] = v;
  return { ...state, book: { ...state.book, sheets: { ...state.book.sheets, [state.sheet]: cells } } };
}

/**
 * How far the sheet reaches, in rows and columns: its used cells and the selection plus a margin
 * (10 rows, 2 columns), never under `rows` x `cols`. The scroll box is this big.
 */
export function extent(state, { rows = 20, cols = 8, margin = 10 } = {}) {
  let r = 0, c = 0;
  for (const ref of [...Object.keys(cellsOf(state)), state.selected]) {
    const p = parseRef(ref);
    if (p) { r = Math.max(r, p.row); c = Math.max(c, p.col + 1); }
  }
  return { rows: Math.max(rows, r + margin), cols: Math.max(cols, c + 2) };
}

/**
 * The grid as an HTML table: `rows` x `cols` cells from row `top` (1-based) and column index `left`
 * (0-based), with their headers. Every cell carries data-ref, the selected one class "selected".
 */
export function renderHTML(state, { rows = 20, cols = 8, top = 1, left = 0 } = {}) {
  const cells = cellsOf(state);
  const out = ['<table class="grid"><thead><tr><th class="corner"></th>'];
  for (let c = left; c < left + cols; c++) out.push(`<th class="col">${colName(c)}</th>`);
  out.push("</tr></thead><tbody>");
  for (let r = top; r < top + rows; r++) {
    out.push(`<tr><th class="row">${r}</th>`);
    for (let c = left; c < left + cols; c++) {
      const ref = colName(c) + r;
      const v = cells[ref];
      const cls = [];
      if (ref === state.selected) cls.push("selected");
      if (typeof v === "number" || typeof v === "boolean") cls.push("num");
      if (v && typeof v === "object") cls.push("err");
      const attr = cls.length ? ` class="${cls.join(" ")}"` : "";
      out.push(`<td data-ref="${ref}"${attr}>${escapeHTML(display(v))}</td>`);
    }
    out.push("</tr>");
  }
  out.push("</tbody></table>");
  return out.join("");
}

const ARROWS = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
// One row and one column of scrolling, in pixels of the scroll box. The table itself stays put
// (sticky) and is redrawn for the rows and columns the scroll position points at.
const STEP_Y = 22, STEP_X = 88;

/**
 * Draws the grid into `container` and wires it. The container is a scroll box as big as the sheet
 * (extent()); only the rows and columns in view are drawn, with their headers, and a scroll redraws
 * them. Click selects; double-click, Enter, F2 or typing edits; Enter commits, Escape cancels; the
 * arrows and PageDown/PageUp move, and the view follows the selection. onChange(state) runs on
 * every selection and edit. `rows` x `cols` is the least the sheet shows. Returns
 * {state, setState(state, {reveal}), destroy()}; setState scrolls to the selection when it moved
 * or when `reveal` is set.
 */
export function mount(container, state, { rows = 20, cols = 8, onChange = () => {}, textOf = null, onEdit = null } = {}) {
  let s = state;
  let editing = null;
  let top = 1, left = 0; // the first row and column index drawn
  const doc = container.ownerDocument;
  const win = doc.defaultView;
  container.classList.add("grid-scroll");
  const space = doc.createElement("div");
  space.className = "grid-space";
  container.replaceChildren(space);
  const tdOf = (ref) => space.querySelector(`td[data-ref="${ref}"]`);

  // Rows and columns wholly inside the box, from the sizes the browser drew (fonts differ).
  let size = { head: 24, side: 48, row: STEP_Y, col: STEP_X };
  const measure = () => {
    const th = space.querySelector("tbody th.row"), td = space.querySelector("tbody td");
    const head = space.querySelector("thead tr");
    if (th && td && head) {
      size = { head: head.getBoundingClientRect().height, side: th.getBoundingClientRect().width,
               row: th.getBoundingClientRect().height || STEP_Y, col: td.getBoundingClientRect().width || STEP_X };
    }
  };
  const fit = () => {
    const h = Math.min(container.clientHeight || 0, win ? win.innerHeight : Infinity);
    const w = Math.min(container.clientWidth || 0, win ? win.innerWidth : Infinity);
    return {
      rows: Math.max(1, Math.floor((h - size.head) / size.row) || rows),
      cols: Math.max(1, Math.floor((w - size.side) / size.col) || cols),
    };
  };
  const resize = () => {
    const ext = extent(s, { rows, cols });
    // One row and column more than the sheet, so the drawn window always fits inside the space.
    space.style.height = (ext.rows + 1) * STEP_Y + size.head + "px";
    space.style.width = (ext.cols + 1) * STEP_X + size.side + "px";
  };
  const draw = () => {
    editing = null;
    resize();
    const f = fit();
    // The drawn window has one row and column more than fit, partly shown at the far edges. It sits in a
    // sticky view the size of the box, clipped: a sticky element taller or wider than the box is pushed back
    // at the end of the scroll range, which would lift the column headers (or the row headers) out of view.
    const h = container.clientHeight, w = container.clientWidth;
    const box = h > 0 && w > 0 ? ` style="width:${w}px;height:${h}px"` : "";
    space.innerHTML = `<div class="grid-view"${box}>` + renderHTML(s, { rows: f.rows + 1, cols: f.cols + 1, top, left }) + "</div>";
  };
  // Scroll so the selected cell is wholly in view.
  const follow = () => {
    const p = parseRef(s.selected);
    if (!p) return;
    const f = fit();
    if (p.row < top) top = p.row;
    else if (p.row >= top + f.rows) top = p.row - f.rows + 1;
    if (p.col < left) left = p.col;
    else if (p.col >= left + f.cols) left = p.col - f.cols + 1;
    resize();
    container.scrollTop = (top - 1) * STEP_Y;
    container.scrollLeft = left * STEP_X;
  };
  const show = (reveal) => {
    if (reveal) follow();
    draw();
    measure();
  };
  const update = (next) => {
    s = next;
    show(true);
    onChange(s);
  };
  const onScroll = () => {
    const t = 1 + Math.floor(container.scrollTop / STEP_Y), l = Math.floor(container.scrollLeft / STEP_X);
    if (t !== top || l !== left) {
      top = t;
      left = l;
      if (!editing) draw();
    }
  };

  const startEdit = (ref, initial) => {
    if (!tdOf(ref)) show(true);
    const td = tdOf(ref);
    if (!td) return;
    const input = doc.createElement("input");
    // The editor starts from the cell as typed when the page knows it (textOf: formulas, '007), else
    // from the grid's own text of the value.
    const before = textOf ? textOf(ref) : inputText(cellsOf(s)[ref]);
    input.value = initial ?? before;
    // Closing the editor: text left as it was changes nothing; changed text goes to the page (onEdit)
    // and into the grid's copy.
    const finish = (after) => {
      if (initial === undefined && input.value === before) return update(after(s));
      if (onEdit) onEdit(ref, input.value);
      update(after(edit(s, ref, input.value)));
    };
    td.textContent = "";
    td.appendChild(input);
    editing = input;
    input.focus();
    if (initial === undefined) input.select();
    input.addEventListener("keydown", (e) => {
      e.stopPropagation();
      if (e.key === "Enter") {
        e.preventDefault();
        finish((x) => move(x, 0, 1));
        container.focus();
      } else if (e.key === "Escape") {
        e.preventDefault();
        draw();
        container.focus();
      }
    });
    input.addEventListener("blur", () => {
      if (editing === input) finish((x) => x);
    });
  };

  const onClick = (e) => {
    const td = e.target.closest("td[data-ref]");
    // A click on the selected cell redraws nothing, so a double-click's second click lands on the
    // same cell and the browser sends dblclick.
    if (td && !td.contains(editing) && td.dataset.ref !== s.selected) update(select(s, td.dataset.ref));
  };
  const onDblClick = (e) => {
    const td = e.target.closest("td[data-ref]");
    if (td) {
      if (s.selected !== td.dataset.ref) update(select(s, td.dataset.ref));
      startEdit(td.dataset.ref);
    }
  };
  const onKey = (e) => {
    if (editing) return;
    if (ARROWS[e.key]) {
      update(move(s, ...ARROWS[e.key]));
      e.preventDefault();
    } else if (e.key === "PageDown" || e.key === "PageUp") {
      // A screen at a time: the view and the selection move together, as in Calc.
      const n = fit().rows;
      const d = e.key === "PageDown" ? n : -n;
      top = Math.max(1, top + d);
      update(move(s, 0, d));
      e.preventDefault();
    } else if (e.key === "Enter" || e.key === "F2") {
      startEdit(s.selected);
      e.preventDefault();
    } else if (e.key === "Delete" || e.key === "Backspace") {
      if (onEdit) onEdit(s.selected, "");
      update(edit(s, s.selected, ""));
      e.preventDefault();
    } else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      startEdit(s.selected, e.key);
      e.preventDefault();
    }
  };
  const onResize = () => { if (!editing) show(false); };

  container.tabIndex = 0;
  container.addEventListener("click", onClick);
  container.addEventListener("dblclick", onDblClick);
  container.addEventListener("keydown", onKey);
  container.addEventListener("scroll", onScroll);
  const observer = win && win.ResizeObserver ? new win.ResizeObserver(onResize) : null;
  if (observer) observer.observe(container);
  show(false);
  show(false); // again with the sizes the browser drew
  return {
    get state() { return s; },
    setState(next, { reveal = false } = {}) {
      const moved = next.selected !== s.selected || next.sheet !== s.sheet;
      s = next;
      show(reveal || moved);
    },
    destroy() {
      container.removeEventListener("click", onClick);
      container.removeEventListener("dblclick", onDblClick);
      container.removeEventListener("keydown", onKey);
      container.removeEventListener("scroll", onScroll);
      if (observer) observer.disconnect();
      container.classList.remove("grid-scroll");
      container.innerHTML = "";
    },
  };
}
