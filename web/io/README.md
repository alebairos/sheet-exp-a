# web/io

Open and save a workbook in the browser (intent a-i11-open-save).

Run `python3 web/io/serve.py [port]` and open `http://127.0.0.1:8000/io/index.html`. It serves `web/`
and answers `POST /compute` with what `./engine` computes, so the page and the engine always agree.

- `index.html`: Open (`.json` or `.csv`), Save JSON, Save CSV, a message line and the grid (`../grid/grid.js`).
  Each grid edit sends only the cell typed into to `controller.edit(ref, text)`; formulas you did not touch stay formulas.
- `io.js` (ES module, no DOM except `download`):
  - `parseJSON(text)` / `toJSON(book)`: SPEC.md's workbook, every cell and the sheet order kept; a file that
    is not a workbook throws an `Error` saying why.
  - `parseCSV(text, sheet = "Sheet1")`: RFC 4180 (quotes, separators and line breaks inside quotes, CRLF, LF or CR),
    fields typed as the grid types input; an empty field is no cell.
  - `toCSV(computed, sheet)`: the sheet's computed values from A1 to its last used cell, numbers as Calc shows them,
    TRUE/FALSE, errors by name, LF line ends.
  - `createController({compute})`: `openText(name, text)`, `openFile(file)`, `edit(ref, text)`, `saveJSON()`,
    `saveCSV()` and `state` (`book` as typed, `computed`, `sheet`, `name`, `message`).
