# A spreadsheet engine (experiment)

A public demo for an experiment: the same spec built by the same AI harness, once with cooknship and once without.

The only spec is [SPEC.md](SPEC.md).

## Build and test

Python 3 (standard library only); nothing to install.

```sh
./test.sh                                  # the whole suite, from a clean clone
./engine book.json                         # compute a workbook (or `./engine - < book.json`)
./engine - --cell Sheet1!A1 < book.json    # print one cell's value
```

## Layout

- `engine`: the CLI launcher; `src/cli.py` reads and writes the workbook JSON.
- `src/parser`, `src/values`, `src/eval`, `src/recalc`: the engine's parts.
- `src/functions/{math,logic_text,lookup}`: one module per function; a module registers with `@register("NAME")` from `src.functions`, and `registry()` discovers it.
- `web/{grid,formula_bar,io}`: the browser UI.
- `tests/`: unit tests (`tests/e2e`: end to end).
