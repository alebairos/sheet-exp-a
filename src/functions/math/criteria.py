"""SUMIF, COUNTIF, AVERAGEIF and Calc's criteria (intent a-i5-math).

Every rule below was checked against LibreOffice Calc headless (wildcards on,
regular expressions off, the defaults of a new document):

* A criterion is a value or a text.  A number (TRUE/FALSE are 1/0, a blank
  criterion cell is 0) matches number and boolean cells equal to it; never text.
* A text starts with an optional operator (= <> < > <= >=, none means =); the
  rest is the operand.  An operand that reads as a number (" 10 ", "1E1", "$10",
  "TRUE") compares numerically against number and boolean cells; against text
  cells (and error cells, by their name) it is matched as text.
* = with a text operand matches case-insensitively with the wildcards * ? and
  ~ (escape), anchored to the whole cell; a number cell is matched by its shown
  text ("1*" matches 1, 10 and TRUE, which is 1).  A bare "" matches blank cells
  and empty text; "=" only blank cells.
* <> matches every cell = does not, blanks and errors included ("<>" is every
  non-blank cell).
* < > <= >= never match blanks or errors: a number operand compares number
  cells, a text operand text cells (case-insensitively, no wildcards).
* The sum range is resized from its top-left cell to the criteria range's shape;
  in it numbers and booleans are summed, text and blanks skipped, and an error
  in a matched cell is the result.
"""

import math
import re

from src.eval import Range
from src.functions import register
from src.values import (DIV0, NUM, Blank, Bool, Error, Number, Text,
                        format_number)

ERR504 = Error("Err:504")

_NUMBER = re.compile(r"\$?[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?%?")
_OPS = ("<>", "<=", ">=", "=", "<", ">")


def _as_number(text):
    """The number a criterion operand reads as, or None."""
    t = text.strip()
    if t.upper() == "TRUE":
        return 1.0
    if t.upper() == "FALSE":
        return 0.0
    if not _NUMBER.fullmatch(t):
        return None
    pct = t.endswith("%")
    t = t.lstrip("$").rstrip("%")
    x = float(t)
    if not math.isfinite(x):
        return None
    return x / 100.0 if pct else x


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


def _cell_number(v):
    if isinstance(v, Number):
        return v.value
    if isinstance(v, Bool):
        return 1.0 if v.value else 0.0
    return None


def _cell_text(v):
    """The text a cell is matched by in = criteria; None for a blank."""
    if isinstance(v, Text):
        return v.value
    if isinstance(v, Error):
        return v.code
    x = _cell_number(v)
    return None if x is None else format_number(x)


def _equals(operand, explicit):
    """A test for = with a text operand."""
    if operand == "":
        if explicit:
            return lambda v: isinstance(v, Blank)
        return lambda v: isinstance(v, Blank) or (isinstance(v, Text) and v.value == "")
    num = _as_number(operand)
    pat = _wildcard(operand)
    if num is not None:
        def test(v):
            x = _cell_number(v)
            if x is not None:
                return x == num
            if isinstance(v, (Text, Error)):
                return bool(pat.fullmatch(_cell_text(v)))
            return False
        return test

    def test(v):
        t = _cell_text(v)
        return t is not None and bool(pat.fullmatch(t))
    return test


_ORDER = {
    "<": lambda c: c < 0, ">": lambda c: c > 0,
    "<=": lambda c: c <= 0, ">=": lambda c: c >= 0,
}


def _ordered(op, operand):
    keep = _ORDER[op]
    num = _as_number(operand)
    if num is not None:
        def test(v):
            x = _cell_number(v)
            return x is not None and keep((x > num) - (x < num))
        return test
    key = operand.casefold()

    def test(v):
        if not isinstance(v, Text):
            return False
        t = v.value.casefold()
        return keep((t > key) - (t < key))
    return test


def criterion(c):
    """A cell test for criterion value ``c``; an Error when the criterion is one."""
    if isinstance(c, Range):
        c = c.collapse()
    if isinstance(c, Error):
        return c
    if isinstance(c, Blank):
        c = Number(0)
    if isinstance(c, (Number, Bool)):
        num = _cell_number(c)
        return lambda v: _cell_number(v) == num
    text = c.value
    op = next((o for o in _OPS if text.startswith(o)), None)
    operand = text[len(op):] if op else text
    if op in (None, "="):
        return _equals(operand, explicit=op == "=")
    if op == "<>":
        eq = _equals(operand, explicit=True)
        return lambda v: not eq(v)
    return _ordered(op, operand)


def _cells(r):
    """(row, col, value) of a range column by column, the order Calc walks it."""
    for col in range(r.left, r.right + 1):
        for row in range(r.top, r.bottom + 1):
            yield row, col, r.cell(row, col)


def _matched(args):
    """The sum-range values of the cells SUMIF/AVERAGEIF's criterion matches, or an Error."""
    if len(args) not in (2, 3) or not isinstance(args[0], Range):
        return ERR504
    rng = args[0]
    test = criterion(args[1])
    if isinstance(test, Error):
        return test
    if len(args) == 3:
        s = args[2]
        if not isinstance(s, Range):
            return ERR504
        dr, dc = s.top - rng.top, s.left - rng.left
        sheet = s.sheet
    else:
        dr = dc = 0
        sheet = rng.sheet
    sums = Range(rng.book, sheet, rng.top + dr, rng.left + dc, rng.bottom + dr, rng.right + dc)
    return [sums.cell(row + dr, col + dc) for row, col, v in _cells(rng) if test(v)]


def _numbers(values):
    """The numbers among summed values, or the first Error."""
    out = []
    for v in values:
        if isinstance(v, Error):
            return v
        x = _cell_number(v)
        if x is not None:
            out.append(x)
    return out


def _num(x):
    return Number(x) if math.isfinite(x) else NUM


def _approx_equal(a, b):
    """rtl::math::approxEqual: equal to within 2^-48 of both."""
    if a == b:
        return True
    if a == 0.0 or b == 0.0:
        return False
    d = abs(a - b)
    return d < abs(a) * 2.0 ** -48 and d < abs(b) * 2.0 ** -48


def _neumaier(total, err, x):
    t = total + x
    if abs(total) >= abs(x):
        err += (total - t) + x
    else:
        err += (x - t) + total
    return t, err


def _calc_sum(xs):
    """Calc's KahanSum (sc/inc/kahan.hxx), which SUMIF and AVERAGEIF add with, in the
    order the cells are walked.  Each term is held back one step; at the end the held
    term cancels the rest to 0 when it is approximately its negative, and is otherwise
    added with one more Neumaier step.  So 0.1, 0.2, -0.3 sum to 0 and 0.1, 0.2, -0.3,
    1E-17, 0.7, 0.1 to 0.8, as in LibreOffice."""
    total = err = mem = 0.0
    for x in xs:
        if x == 0.0:
            continue
        if mem != 0.0:
            total, err = _neumaier(total, err, mem)
        mem = x
    whole = total + err
    if mem == 0.0:
        return whole
    if ((mem < 0.0 < whole) or (whole < 0.0 < mem)) and _approx_equal(mem, -whole):
        return 0.0
    total, err = _neumaier(total, err, mem)
    return total + err


@register("COUNTIF")
def countif(*args):
    if len(args) != 2 or not isinstance(args[0], Range):
        return ERR504
    test = criterion(args[1])
    if isinstance(test, Error):
        return test
    return Number(sum(1 for _, _, v in _cells(args[0]) if test(v)))


@register("SUMIF")
def sumif(*args):
    m = _matched(args)
    if isinstance(m, Error):
        return m
    xs = _numbers(m)
    if isinstance(xs, Error):
        return xs
    try:
        return _num(_calc_sum(xs))
    except OverflowError:
        return NUM


@register("AVERAGEIF")
def averageif(*args):
    m = _matched(args)
    if isinstance(m, Error):
        return m
    xs = _numbers(m)
    if isinstance(xs, Error):
        return xs
    if not xs:
        return DIV0
    try:
        return _num(_calc_sum(xs) / len(xs))
    except OverflowError:
        return NUM
