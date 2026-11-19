"""Formula evaluator (intent a-i3-evaluator).

``evaluate(formula, book, sheet)`` parses a cell formula and computes it with
LibreOffice Calc's operators, coercions and error propagation; the result is a
:mod:`src.values` Value.  ``book`` is the workbook JSON of SPEC.md and
``sheet`` the name of the formula's own sheet.

Errors are ordinary values: they flow through operators (the leftmost operand
error wins) and arrive at functions as arguments.  Nothing here raises for a
spreadsheet error; a formula that does not parse evaluates to ``#VALUE!``.

Calling convention for functions registered with :func:`src.functions.register`:
positional arguments; a reference or range argument arrives as a :class:`Range`,
every other argument as a Value (errors included), an omitted argument as the
blank value.  The function returns a Value (or a Range, collapsed like a
reference in operator context).

Referenced formula cells are read as they stand in the book; computing them
first is recalculation's job (a-i4).
"""

import math

from src import parser as p
from src.functions import registry
from src.values import (
    BLANK,
    DIV0,
    NAME,
    NUM,
    REF,
    VALUE,
    Blank,
    Bool,
    Error,
    Number,
    Text,
    Value,
    compare,
    from_json,
    to_number,
    to_text,
)

__all__ = ["evaluate", "evaluate_node", "Range"]


class Range:
    """A rectangle of cells on one sheet of a book (corners inclusive, 1-based)."""

    __slots__ = ("book", "sheet", "top", "left", "bottom", "right")

    def __init__(self, book, sheet, top, left, bottom, right):
        self.book = book
        self.sheet = sheet
        self.top, self.bottom = min(top, bottom), max(top, bottom)
        self.left, self.right = min(left, right), max(left, right)

    @property
    def rows(self):
        return self.bottom - self.top + 1

    @property
    def cols(self):
        return self.right - self.left + 1

    def cell(self, row, col):
        """The Value at an absolute (row, col) of this range's sheet."""
        cells = self.book["sheets"][self.sheet]
        return from_json(cells.get(p.col_to_letters(col) + str(row)))

    def values(self):
        """Every cell's Value, row by row, blanks included."""
        cells = self.book["sheets"][self.sheet]
        letters = [p.col_to_letters(c) for c in range(self.left, self.right + 1)]
        return [from_json(cells.get(l + str(r)))
                for r in range(self.top, self.bottom + 1) for l in letters]

    def collapse(self):
        """The Value of a one-cell range; #VALUE! for more than one cell."""
        if self.rows == 1 and self.cols == 1:
            return self.cell(self.top, self.left)
        return VALUE

    def __repr__(self):
        a = p.col_to_letters(self.left) + str(self.top)
        b = p.col_to_letters(self.right) + str(self.bottom)
        return "Range(%r, %s:%s)" % (self.sheet, a, b)


def _sheet_name(book, name):
    """The book's own name for a sheet (Calc matches names case-insensitively)."""
    sheets = book.get("sheets", {}) if isinstance(book, dict) else {}
    if name in sheets:
        return name
    folded = name.casefold()
    for s in sheets:
        if s.casefold() == folded:
            return s
    return None


def _ref_range(node, book, sheet):
    """A Ref or Range node as a Range, or #REF! for a sheet the book lacks."""
    start, end = (node, node) if isinstance(node, p.Ref) else (node.start, node.end)
    name = _sheet_name(book, start.sheet if start.sheet is not None else sheet)
    if name is None:
        return REF
    return Range(book, name, start.row, start.col, end.row, end.col)


def _scalar(v):
    """A value in operator context: a Range collapses to its single cell."""
    return v.collapse() if isinstance(v, Range) else v


def _num(x):
    return Number(x) if math.isfinite(x) else NUM


def _power(a, b):
    # As LibreOffice: 0^-1 is #NUM!, and a negative base takes an odd root
    # ((-8)^(1/3) is -2) while other fractional powers of it are #NUM!.
    if a == 0 and b < 0:
        return NUM
    if a < 0 and b != int(b):
        n = 1.0 / b
        if abs(n - round(n)) < 1e-9 and round(n) % 2 == 1:
            try:
                return _num(-math.pow(-a, b))
            except (ValueError, OverflowError):
                return NUM
        return NUM
    try:
        return _num(math.pow(a, b))
    except (ValueError, OverflowError):
        return NUM


def _arith(op, a, b):
    if op == "+":
        return _num(a + b)
    if op == "-":
        return _num(a - b)
    if op == "*":
        return _num(a * b)
    if op == "/":
        return DIV0 if b == 0 else _num(a / b)
    return _power(a, b)


def _concat_text(v):
    # Calc stores TRUE/FALSE as the numbers 1/0, so & joins them as digits.
    if isinstance(v, Bool):
        v = Number(1.0 if v.value else 0.0)
    return to_text(v)


_COMPARE = {
    "=": lambda c: c == 0, "<>": lambda c: c != 0,
    "<": lambda c: c < 0, ">": lambda c: c > 0,
    "<=": lambda c: c <= 0, ">=": lambda c: c >= 0,
}


def _binary(op, left, right):
    if op in ("+", "-", "*", "/", "^"):
        a, b = to_number(left), to_number(right)
        if isinstance(a, Error):
            return a
        if isinstance(b, Error):
            return b
        return _arith(op, a.value, b.value)
    if op == "&":
        a, b = _concat_text(left), _concat_text(right)
        if isinstance(a, Error):
            return a
        if isinstance(b, Error):
            return b
        return Text(a.value + b.value)
    if op in _COMPARE:
        c = compare(left, right)
        return c if isinstance(c, Error) else Bool(_COMPARE[op](c))
    return VALUE


def _call(node, book, sheet):
    fn = registry().get(node.name.upper())
    if fn is None:
        return NAME
    args = []
    for a in node.args:
        if isinstance(a, p.Missing):
            args.append(BLANK)
        else:
            args.append(_eval(a, book, sheet))
    result = fn(*args)
    if isinstance(result, (Value, Range)):
        return result
    return from_json(result)


def _eval(node, book, sheet):
    """A node's value: a Value, or a Range for a reference (not yet collapsed)."""
    if isinstance(node, p.Number):
        return _num(float(node.value))
    if isinstance(node, p.Text):
        return Text(node.value)
    if isinstance(node, p.Bool):
        return Bool(node.value)
    if isinstance(node, p.Error):
        return Error(node.code)
    if isinstance(node, (p.Ref, p.Range)):
        return _ref_range(node, book, sheet)
    if isinstance(node, p.Name):
        return NAME
    if isinstance(node, p.Missing):
        return BLANK
    if isinstance(node, p.Call):
        return _call(node, book, sheet)
    if isinstance(node, p.Unary):
        v = to_number(_scalar(_eval(node.operand, book, sheet)))
        return v if isinstance(v, Error) else _num(-v.value)
    if isinstance(node, p.Percent):
        v = to_number(_scalar(_eval(node.operand, book, sheet)))
        return v if isinstance(v, Error) else _num(v.value / 100.0)
    if isinstance(node, p.Binary):
        left = _scalar(_eval(node.left, book, sheet))
        right = _scalar(_eval(node.right, book, sheet))
        return _binary(node.op, left, right)
    return VALUE


def evaluate_node(node, book, sheet):
    """Evaluate a parse tree to a cell's final Value (a lone blank shows as 0)."""
    v = _scalar(_eval(node, book, sheet))
    return Number(0.0) if isinstance(v, Blank) else v


def evaluate(formula, book, sheet):
    """The Value of ``formula`` (cell text with its leading ``=``) on ``sheet`` of ``book``."""
    try:
        tree = p.parse(formula)
    except p.ParseError:
        return VALUE
    return evaluate_node(tree, book, sheet)
