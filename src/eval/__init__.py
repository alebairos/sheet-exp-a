"""Formula evaluator (intent a-i3-evaluator).

``evaluate(formula, book, sheet)`` parses a cell formula and computes it with
LibreOffice Calc's operators, coercions and error propagation; the result is a
:mod:`src.values` Value.  ``book`` is the workbook JSON of SPEC.md and
``sheet`` the name of the formula's own sheet.

Errors are ordinary values: they flow through operators (the leftmost operand
error wins) and arrive at functions as arguments.  Nothing here raises for a
spreadsheet error; a formula that does not parse evaluates to Calc's code for it (``ParseError.code``:
Err:508 to Err:520, Err:502, else ``#VALUE!``).

Calling convention for functions registered with :func:`src.functions.register`:
positional arguments; a reference or range argument arrives as a :class:`Range`,
every other argument as a Value (errors included), an omitted argument as the
blank value.  The function returns a Value (or a Range, collapsed like a
reference in operator context).

Referenced formula cells are read as they stand in the book; computing them
first is recalculation's job (a-i4).

Implicit intersection (a-v1-eval-edges): given the formula's own cell
(``cell="C7"``), a range used where one value is expected (an operator's
operand, unary minus, %, the cell's final value) takes the cell in the
formula's row (a one-column range) or column (a one-row range), as Calc does;
outside the range, or without the position, it is ``#VALUE!``.

IF evaluates its condition and then only the branch it takes; IFERROR evaluates its
fallback only when the value is an error (a-v1-eval-edges). As in Calc, a branch
that is not taken is never read.
"""

import inspect
import math
import re

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
    TEXT_TIE,
    approx_add,
    approx_equal,
    approx_sub,
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

    def collapse(self, pos=None):
        """The Value of the range where one value is expected: a one-cell range is its cell; with the
        formula's position ``(row, col)``, a taller range takes the cell in that row and a wider one the
        cell in that column (Calc's implicit intersection); anything else is #VALUE!."""
        if self.rows == 1:
            row = self.top
        elif pos is not None and self.top <= pos[0] <= self.bottom:
            row = pos[0]
        else:
            return VALUE
        if self.cols == 1:
            col = self.left
        elif pos is not None and self.left <= pos[1] <= self.right:
            col = pos[1]
        else:
            return VALUE
        return self.cell(row, col)

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


def _scalar(v, pos=None):
    """A value in operator context: a Range collapses to one cell (implicit intersection at ``pos``)."""
    return v.collapse(pos) if isinstance(v, Range) else v


def _position(cell):
    """'C7' -> (7, 3), the (row, col) of the formula's own cell; None without one."""
    if not cell:
        return None
    letters = cell.rstrip("0123456789")
    digits = cell[len(letters):]
    if not letters.isalpha() or not digits or digits[0] == "0":
        return None
    return int(digits), p.letters_to_col(letters)


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
        return _num(approx_add(a, b))
    if op == "-":
        return _num(approx_sub(a, b))
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
    # TEXT_TIE: different texts that sort equal (é and e + combining acute) are <= and >= but not =.
    "=": lambda c: c == 0 and c is not TEXT_TIE, "<>": lambda c: c != 0 or c is TEXT_TIE,
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
        # Calc compares two near-equal numbers as equal (values.approx_equal): =0.1+0.2=0.3 is TRUE.
        if c != 0 and isinstance(left, Number) and isinstance(right, Number) and approx_equal(left.value, right.value):
            c = 0
        return c if isinstance(c, Error) else Bool(_COMPARE[op](c))
    return VALUE


class _Unevaluated(Value):
    """Stands for an argument not evaluated yet; the registered IF/IFERROR return the argument they
    choose as it is, so getting one back names the one branch to evaluate."""

    __slots__ = ("node",)

    def __init__(self, node):
        object.__setattr__(self, "node", node)


# Functions that evaluate only what they use, as Calc does: (name, how many leading arguments are
# evaluated before the choice). IF's branch not taken and IFERROR's unused fallback are never read,
# so a cell may refer to itself through them without a circular reference.
_LAZY = {"IF": 1, "IFERROR": 1}


def _arg(a, book, sheet, pos):
    return BLANK if isinstance(a, p.Missing) else _eval(a, book, sheet, pos)


# The functions Calc computes with no arguments at all (=SUM() is 0, =AVERAGE() #DIV/0!,
# =STDEV() #DIV/0!, =CONCATENATE() ""); any other call with none is Calc's Err:511 (a missing variable). Run in
# LibreOffice Calc 26.8.1.1 (plan a-v1-parse-fidelity's probe).
_EMPTY_CALL_OK = frozenset({"SUM", "COUNT", "COUNTA", "PRODUCT", "AVERAGE", "STDEV", "CONCATENATE"})
_MISSING_VARIABLE = Error("Err:511")
_NO_OPERATOR = Error("Err:509")


def _takes_arguments(fn):
    """False for a function registered with no parameters at all, which a call with none suits."""
    try:
        return bool(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        return True


def _is_cell_address(name):
    m = re.fullmatch(r"([A-Z]{1,3})([0-9]+)", name)
    return bool(m) and 1 <= p.letters_to_col(m.group(1)) <= p.nodes.MAX_COL and 1 <= int(m.group(2)) <= p.nodes.MAX_ROW


def _call(node, book, sheet, pos=None):
    name = node.name.upper()
    fn = registry().get(name)
    if fn is None:
        # =A1(2): Calc reads a cell address before '(' as a reference beside a bracket, Err:509.
        return _NO_OPERATOR if _is_cell_address(name) else NAME
    if not node.args and name not in _EMPTY_CALL_OK and _takes_arguments(fn):
        return _MISSING_VARIABLE
    eager = _LAZY.get(name, len(node.args))
    args = [_arg(a, book, sheet, pos) for a in node.args[:eager]]
    args += [_Unevaluated(a) for a in node.args[eager:]]
    result = fn(*args)
    if isinstance(result, _Unevaluated):
        result = _arg(result.node, book, sheet, pos)
    if isinstance(result, (Value, Range)):
        return result
    return from_json(result)


def _eval(node, book, sheet, pos=None):
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
        return _call(node, book, sheet, pos)
    if isinstance(node, p.Unary):
        v = to_number(_scalar(_eval(node.operand, book, sheet, pos), pos))
        return v if isinstance(v, Error) else _num(-v.value)
    if isinstance(node, p.Percent):
        v = to_number(_scalar(_eval(node.operand, book, sheet, pos), pos))
        return v if isinstance(v, Error) else _num(v.value / 100.0)
    if isinstance(node, p.Binary):
        left = _scalar(_eval(node.left, book, sheet, pos), pos)
        right = _scalar(_eval(node.right, book, sheet, pos), pos)
        return _binary(node.op, left, right)
    return VALUE


def evaluate_node(node, book, sheet, cell=None):
    """Evaluate a parse tree to a cell's final Value (a lone blank shows as 0); ``cell`` is the
    formula's own address on ``sheet``, for implicit intersection."""
    pos = _position(cell)
    v = _scalar(_eval(node, book, sheet, pos), pos)
    return Number(0.0) if isinstance(v, Blank) else v


def evaluate(formula, book, sheet, cell=None):
    """The Value of ``formula`` (cell text with its leading ``=``) on ``sheet`` of ``book``, written in
    ``cell`` (its address, optional)."""
    try:
        tree = p.parse(formula)
    except p.ParseError as e:
        return Error(e.code)
    return evaluate_node(tree, book, sheet, cell)
