# web/grid

The spreadsheet grid: `grid.js`, a plain ES module (no build step, no libraries), and `grid.css`.
`index.html` shows it on a sample workbook: serve the repo (`python3 -m http.server`) and open `/web/grid/`.

State is the workbook JSON of SPEC.md plus the sheet shown and the selected cell. All but `mount` are pure:

- `display(value)`: the text a cell shows for a computed JSON value (Calc's general format, 15 digits).
- `createState(book, sheet)`, `select(state, ref)`, `move(state, dc, dr)`.
- `edit(state, ref, text)`: typed text becomes a number, TRUE/FALSE (any case) or text; `""` removes the cell.
  Formulas are kept as text for now.
- `renderHTML(state, {rows, cols})`: the table; `data-ref` on every cell, class `selected`, `num`, `err`.
- `mount(container, state, {rows, cols, onChange})`: draws and wires the grid (click selects; double-click,
  Enter, F2 or typing edits; Enter commits, Escape cancels; arrows move; Delete clears) and calls
  `onChange(state)` on every change. Returns `{state, setState(state), destroy()}`.

Tests: `node --test tests/web/grid/` and the plan checks in `tests/web/grid/checks/`.
