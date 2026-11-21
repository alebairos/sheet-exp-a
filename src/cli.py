"""The engine CLI: ``engine <file|-> [--cell Sheet!A1]`` (SPEC.md).

Bad input (a missing file, a directory, text that is not JSON, JSON that is not a workbook) is
refused with one plain line on stderr, ``engine: <what is wrong>``, and exit 1; usage errors exit 2.
Output is always strict JSON. Cell keys and --cell references are read regardless of case and of
``$``, as Calc reads them.
"""

import json
import math
import re
import sys

from src.recalc import compute as recalc

CELL_KEY = re.compile(r"^\$?([A-Za-z]+)\$?([1-9][0-9]*)$")


class BadInput(Exception):
    """Input the engine cannot read; its message is what the user is told."""


def _no_constant(name):
    raise BadInput(f"the input is not valid JSON: {name} is not a JSON number")


def _number(text):
    """A JSON number: integral values as ints (1e3 is 1000, as Calc shows it), never inf."""
    x = float(text)
    if not math.isfinite(x):
        raise BadInput(f"the input is not valid JSON: {text} is too large for a number")
    if x == int(x) and abs(x) < 2 ** 53:
        return int(x)
    return x


def _integer(text):
    """A JSON integer, refused like 1e400 when no spreadsheet number can hold it."""
    try:
        n = int(text)
        float(n)
    except (OverflowError, ValueError):
        shown = text if len(text) <= 20 else text[:12] + f"... ({len(text)} digits)"
        raise BadInput(f"the input is not valid JSON: {shown} is too large for a number") from None
    return n


def _parse(text):
    if not text.strip():
        raise BadInput("the input is empty; expected a workbook such as {\"sheets\": {\"Sheet1\": {}}}")
    try:
        return json.loads(text, parse_constant=_no_constant, parse_float=_number, parse_int=_integer)
    except json.JSONDecodeError as e:
        raise BadInput(f"the input is not valid JSON: {e.msg} at line {e.lineno} column {e.colno}") from None
    except RecursionError:
        raise BadInput("the input is not valid JSON: it is nested too deeply") from None


def load(path):
    """The workbook at `path` ("-" is stdin), checked; BadInput if it cannot be read."""
    try:
        if path == "-":
            data = sys.stdin.buffer.read()
        else:
            with open(path, "rb") as f:
                data = f.read()
    except FileNotFoundError:
        raise BadInput(f"no such file: {path}") from None
    except IsADirectoryError:
        raise BadInput(f"is a directory, not a workbook file: {path}") from None
    except PermissionError:
        raise BadInput(f"cannot read (permission denied): {path}") from None
    except OSError as e:
        raise BadInput(f"cannot read {path}: {e.strerror or e}") from None
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise BadInput("the input is not UTF-8 text") from None
    return check(_parse(text))


def _cell_ok(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return True
    return isinstance(v, dict) and set(v) == {"error"} and isinstance(v["error"], str)


def check(book):
    """`book` as a workbook with upper-case cell keys; BadInput if it is not one."""
    if not isinstance(book, dict):
        raise BadInput(f"the input is not a workbook: expected an object with \"sheets\", got {_kind(book)}")
    if "sheets" not in book:
        raise BadInput("the input is not a workbook: it has no \"sheets\"")
    sheets = book["sheets"]
    if not isinstance(sheets, dict):
        raise BadInput(f"the input is not a workbook: \"sheets\" should be an object of sheets, got {_kind(sheets)}")
    out = {}
    for name, cells in sheets.items():
        if not isinstance(cells, dict):
            raise BadInput(f"sheet {name!r} should be an object of cells, got {_kind(cells)}")
        norm = {}
        for key, v in cells.items():
            m = CELL_KEY.match(key)
            if not m:
                raise BadInput(f"sheet {name!r}: {key!r} is not a cell address such as A1")
            ref = m.group(1).upper() + m.group(2)
            if ref in norm:
                raise BadInput(f"sheet {name!r}: the cell {ref} is given twice")
            if not _cell_ok(v):
                raise BadInput(f"sheet {name!r} cell {ref}: {_kind(v)} is not a cell value"
                               " (a number, text, true/false, null or {\"error\": \"#N/A\"})")
            norm[ref] = v
        out[name] = norm
    return {**book, "sheets": out}


def _kind(v):
    return {dict: "an object", list: "a list", str: "text", bool: "true/false", type(None): "null"}.get(
        type(v), "a number")


def compute(book):
    """Return the computed workbook: formulas in dependency order, constants unchanged."""
    return recalc(book)


def _sheet(sheets, name):
    """The sheet called `name`, matched as Calc does: exactly, else regardless of case."""
    if name in sheets:
        return sheets[name]
    folded = name.casefold()
    for k, cells in sheets.items():
        if k.casefold() == folded:
            return cells
    return None


def cell_value(book, ref):
    sheet, sep, addr = ref.rpartition("!")
    if not sep:
        sheet = next(iter(book["sheets"]), "Sheet1")
    sheet = sheet.strip()
    if len(sheet) >= 2 and sheet[0] == sheet[-1] == "'":
        sheet = sheet[1:-1].replace("''", "'")
    cells = _sheet(book["sheets"], sheet)
    m = CELL_KEY.match(addr.strip())
    if cells is None or not m:
        return {"error": "#REF!"}
    return cells.get(m.group(1).upper() + m.group(2), None)


def _reported(x):
    """A float as Calc reports it: 15 significant digits, so =0.1+0.2 prints 0.3 and the budget's
    1200-850.5-384.02 prints -34.52, not binary noise; integral results print as integers, as
    to_json writes them. Only the output is rounded; computing keeps full doubles, as Calc does."""
    r = float(f"{x:.15g}")
    if r == int(r) and abs(r) < 2 ** 53:
        return int(r)
    return r


def _strict(v):
    """`v` as printed: any non-finite number (never valid JSON) as Calc's #NUM!, every other float to
    15 significant digits."""
    if isinstance(v, float):
        return _reported(v) if math.isfinite(v) else {"error": "#NUM!"}
    if isinstance(v, dict):
        return {k: _strict(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_strict(x) for x in v]
    return v


def usage():
    sys.stderr.write("usage: engine <file|-> [--cell Sheet1!A1]\n")
    return 2


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    cell = None
    if "--cell" in args:
        i = args.index("--cell")
        if i + 1 >= len(args):
            return usage()
        cell = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        return usage()
    try:
        book = load(args[0])
    except BadInput as e:
        sys.stderr.write(f"engine: {e}\n")
        return 1
    out = compute(book)
    if cell is not None:
        out = cell_value(out, cell)
    sys.stdout.write(json.dumps(_strict(out), ensure_ascii=False, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
