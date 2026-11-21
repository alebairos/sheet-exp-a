# web/grid

The spreadsheet grid: `grid.js`, a plain ES module (no build step, no libraries), and `grid.css`.
`index.html` shows it on a sample workbook: serve the repo (`python3 -m http.server`) and open `/web/grid/`.

State is the workbook JSON of SPEC.md plus the sheet shown and the selected cell. All but `mount` are pure:

- `display(value)`: the text a cell shows for a computed JSON value (Calc's general format, 15 digits).
- `createState(book, sheet)`, `select(state, ref)`, `move(state, dc, dr)`.
- `edit(state, ref, text)`: typed text becomes a number, TRUE/FALSE (any case) or text; `""` removes the cell.
  Formulas are kept as text for now.
- `extent(state, {rows, cols})`: how far the sheet reaches (used cells and the selection, plus 10 rows and
  2 columns), never under `rows` x `cols`.
- `renderHTML(state, {rows, cols, top, left})`: the table of `rows` x `cols` cells from row `top` (default 1)
  and column index `left` (default 0); `data-ref` on every cell, class `selected`, `num`, `err`.
- `mount(container, state, {rows, cols, onChange})`: makes `container` a scroll box as big as the sheet and
  draws only the rows and columns in view, with sticky headers; a scroll redraws them. Click selects;
  double-click, Enter, F2 or typing edits; Enter commits, Escape cancels; the arrows and PageDown/PageUp move
  with no edge but A1, and the view follows the selection; Delete clears. Calls `onChange(state)` on every
  change. Returns `{state, setState(state, {reveal}), destroy()}`; `setState` scrolls to the selection when it
  moved or `reveal` is set. Give the container a height (it is at most the window's).

Tests: `node --test tests/web/grid/` and the plan checks in `tests/web/grid/checks/`.
