"""The parse tree: immutable nodes and their canonical text (``show``)."""

import json
import re
from dataclasses import dataclass
from typing import Optional, Tuple

MAX_COL = 16384      # XFD
MAX_ROW = 1048576

_PLAIN_SHEET = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def letters_to_col(letters):
    """'A' -> 1, 'Z' -> 26, 'AA' -> 27."""
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def col_to_letters(col):
    """1 -> 'A', 27 -> 'AA'."""
    out = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        out = chr(65 + rem) + out
    return out


def _sheet_text(sheet):
    if _PLAIN_SHEET.match(sheet):
        return sheet + "!"
    return "'" + sheet.replace("'", "''") + "'!"


@dataclass(frozen=True)
class Number:
    value: float


@dataclass(frozen=True)
class Text:
    value: str


@dataclass(frozen=True)
class Bool:
    value: bool


@dataclass(frozen=True)
class Error:
    code: str          # e.g. '#DIV/0!'


@dataclass(frozen=True)
class Ref:
    sheet: Optional[str]   # None: the formula's own sheet
    col: int               # 1-based
    row: int               # 1-based
    col_abs: bool = False
    row_abs: bool = False


@dataclass(frozen=True)
class Range:
    start: Ref
    end: Ref               # end.sheet is always start.sheet

    @property
    def sheet(self):
        return self.start.sheet


@dataclass(frozen=True)
class Name:
    name: str              # upper-cased; evaluates to #NAME?


@dataclass(frozen=True)
class Call:
    name: str              # upper-cased
    args: Tuple


@dataclass(frozen=True)
class Missing:
    """An omitted argument, as in IF(A1,,1)."""


@dataclass(frozen=True)
class Unary:
    op: str                # only '-' (unary plus is dropped)
    operand: object


@dataclass(frozen=True)
class Percent:
    operand: object


@dataclass(frozen=True)
class Binary:
    op: str
    left: object
    right: object


def _ref_text(ref, with_sheet=True):
    out = _sheet_text(ref.sheet) if (with_sheet and ref.sheet is not None) else ""
    out += ("$" if ref.col_abs else "") + col_to_letters(ref.col)
    out += ("$" if ref.row_abs else "") + str(ref.row)
    return out


def show(node):
    """The canonical one-line text of a tree."""
    if isinstance(node, Number):
        return repr(float(node.value))
    if isinstance(node, Text):
        return json.dumps(node.value, ensure_ascii=False)
    if isinstance(node, Bool):
        return "TRUE" if node.value else "FALSE"
    if isinstance(node, Error):
        return node.code
    if isinstance(node, Ref):
        return _ref_text(node)
    if isinstance(node, Range):
        return _ref_text(node.start) + ":" + _ref_text(node.end, with_sheet=False)
    if isinstance(node, Name):
        return node.name
    if isinstance(node, Missing):
        return "_"
    if isinstance(node, Call):
        return "(" + " ".join([node.name] + [show(a) for a in node.args]) + ")"
    if isinstance(node, Unary):
        return "(neg %s)" % show(node.operand)
    if isinstance(node, Percent):
        return "(%% %s)" % show(node.operand)
    if isinstance(node, Binary):
        return "(%s %s %s)" % (node.op, show(node.left), show(node.right))
    raise TypeError("not a parse node: %r" % (node,))
