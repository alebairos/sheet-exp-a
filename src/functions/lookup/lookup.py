"""VLOOKUP, INDEX and MATCH (intent a-i7-lookup).

Tables arrive as src.eval Ranges.  Calc's rules, checked against LibreOffice
headless:

* Exact match: a number (TRUE/FALSE are 1/0) finds an equal number or boolean
  cell, never text; a text finds a text cell case-insensitively with the
  wildcards * ? and ~, and if it reads as a number also an equal number cell
  ("30" finds 30).  The first hit wins.  Blanks and errors never match.
* Approximate match (sorted keys): cells of the other type are skipped; the
  scan stops at the first key greater than the value and answers the last key
  before it; on an equal key it answers the last of that run of equal keys.
  Nothing at or below the value is #N/A.
* Errors in the lookup value or in an index pass through.  Calc's own error
  names are kept where it has no #-name: Err:502 (invalid argument) and Err:504
  (parameter list error).
"""

import math
import re

from src.eval import Range
from src.functions import register
from src.values import (NA, REF, VALUE, Blank, Bool, Error, Number, Text,
                        to_number)

ERR502 = Error("Err:502")
ERR504 = Error("Err:504")

_NUMBER_TEXT = re.compile(r"\s*[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?\s*")


def _scalar(v):
    return v.collapse() if isinstance(v, Range) else v


def _int_arg(v, default=0):
    """An index or type argument truncated toward zero, or an Error."""
    v = _scalar(v)
    if isinstance(v, Blank):
        return default
    n = to_number(v)
    if isinstance(n, Error):
        return n
    return int(n.value) if math.isfinite(n.value) else VALUE


def _cell_number(v):
    if isinstance(v, Number):
        return v.value
    if isinstance(v, Bool):
        return 1.0 if v.value else 0.0
    return None


def _wildcard(pattern):
    out, i = [], 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "~" and i + 1 < len(pattern):
            out.append(re.escape(pattern[i + 1]))
            i += 2
            continue
        out.append(".*" if ch == "*" else "." if ch == "?" else re.escape(ch))
        i += 1
    return re.compile("".join(out), re.IGNORECASE | re.DOTALL)


def _exact(query):
    """A test for exact-match cells, or None when nothing can match."""
    num = _cell_number(query)
    if num is not None:
        return lambda v: _cell_number(v) == num
    if isinstance(query, Text):
        pat = _wildcard(query.value)
        as_num = float(query.value) if _NUMBER_TEXT.fullmatch(query.value) else None

        def test(v):
            if isinstance(v, Text):
                return bool(pat.fullmatch(v.value))
            return as_num is not None and _cell_number(v) == as_num
        return test
    return None


def _key(v, text):
    """A cell's sort key against a text (``text``) or number query; None to skip it."""
    if text:
        return v.value.casefold() if isinstance(v, Text) else None
    return _cell_number(v)


def _find(cells, query, mode):
    """The 0-based position of ``query`` among ``cells`` for MATCH type ``mode`` (0, 1, -1)."""
    if mode == 0:
        test = _exact(query)
        if test is not None:
            for i, v in enumerate(cells):
                if test(v):
                    return i
        return None
    text = isinstance(query, Text)
    if not text and _cell_number(query) is None:
        return None
    q = _key(query, text)
    found = None
    if mode < 0:
        # Descending keys: an equal key wins (the last of its run), else the
        # last key above the value before the first one below it.
        for i, v in enumerate(cells):
            k = _key(v, text)
            if k is not None and k == q:
                j = i
                for m in range(i + 1, len(cells)):
                    km = _key(cells[m], text)
                    if km is None:
                        continue
                    if km != q:
                        break
                    j = m
                return j
    in_run = False
    for i, v in enumerate(cells):
        k = _key(v, text)
        if k is None:
            continue
        if in_run and k != q:
            break
        if (k > q) if mode > 0 else (k < q):
            break
        found = i
        in_run = k == q
    return found


def _vector(r):
    """A one-row or one-column range's cells in order, or None for a 2-D range."""
    if r.rows == 1:
        return [r.cell(r.top, c) for c in range(r.left, r.right + 1)]
    if r.cols == 1:
        return [r.cell(row, r.left) for row in range(r.top, r.bottom + 1)]
    return None


@register("MATCH")
def match(*args):
    if len(args) not in (2, 3) or not isinstance(args[1], Range):
        return ERR504
    query = _scalar(args[0])
    if isinstance(query, Error):
        return query
    mode = _int_arg(args[2], 1) if len(args) == 3 else 1
    if isinstance(mode, Error):
        return mode
    if mode not in (-1, 0, 1):
        return ERR504
    cells = _vector(args[1])
    if cells is None:
        return ERR504
    i = _find(cells, query, mode)
    return NA if i is None else Number(i + 1)


@register("VLOOKUP")
def vlookup(*args):
    if len(args) not in (3, 4) or not isinstance(args[1], Range):
        return ERR504
    query = _scalar(args[0])
    if isinstance(query, Error):
        return query
    table = args[1]
    col = _int_arg(args[2])
    if isinstance(col, Error):
        return col
    sorted_ = True
    if len(args) == 4:
        mode = _scalar(args[3])
        if isinstance(mode, Blank):
            sorted_ = False
        else:
            n = to_number(mode)
            if isinstance(n, Error):
                return n
            sorted_ = n.value != 0
    if col < 1 or col > table.cols:
        return ERR502
    keys = [table.cell(row, table.left) for row in range(table.top, table.bottom + 1)]
    i = _find(keys, query, 1 if sorted_ else 0)
    if i is None:
        return NA
    return table.cell(table.top + i, table.left + col - 1)


@register("INDEX")
def index(*args):
    if not 1 <= len(args) <= 3 or not isinstance(args[0], Range):
        return ERR504
    r = args[0]
    row = _int_arg(args[1]) if len(args) > 1 else 0
    if isinstance(row, Error):
        return row
    col = _int_arg(args[2]) if len(args) > 2 else 0
    if isinstance(col, Error):
        return col
    if len(args) == 2 and r.rows == 1:
        row, col = 0, row          # a one-row range takes a single index as the column
    if row < 0 or col < 0:
        return ERR502
    if row > r.rows or col > r.cols:
        return REF
    top, bottom = (r.top + row - 1,) * 2 if row else (r.top, r.bottom)
    left, right = (r.left + col - 1,) * 2 if col else (r.left, r.right)
    return Range(r.book, r.sheet, top, left, bottom, right)
