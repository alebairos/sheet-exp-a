"""The engine CLI: ``engine <file|-> [--cell Sheet!A1]`` (SPEC.md)."""

import json
import sys

from src.recalc import compute as recalc


def load(path):
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compute(book):
    """Return the computed workbook: formulas in dependency order, constants unchanged."""
    return recalc(book)


def cell_value(book, ref):
    sheet, sep, addr = ref.rpartition("!")
    if not sep:
        sheet = next(iter(book["sheets"]), "Sheet1")
    sheet = sheet.strip("'")
    cells = book["sheets"].get(sheet)
    if cells is None:
        return {"error": "#REF!"}
    addr = addr.replace("$", "").upper()
    return cells.get(addr, None)


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
    out = compute(load(args[0]))
    if cell is not None:
        out = cell_value(out, cell)
    json.dump(out, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
