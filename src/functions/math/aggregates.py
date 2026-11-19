"""SUM, AVERAGE, MIN, MAX, COUNT, COUNTA, PRODUCT, MEDIAN, STDEV (intent a-i5-math).

Arguments arrive as src.eval passes them: a reference as a Range, anything else
as a Value.  Calc's rules, checked against LibreOffice headless:

* From a range, numbers and booleans (Calc stores TRUE/FALSE as 1/0) are taken;
  text and blanks are skipped; the first error is the result.
* A typed argument is coerced: a boolean is 1/0, an omitted one is 0, an error
  is the result, and text is #VALUE! for SUM, AVERAGE and PRODUCT but Err:504
  (Calc's parameter list error) for MIN, MAX, MEDIAN and STDEV.  Any error
  wins over that text error; the first error from left to right is the result.
* COUNT counts numbers, booleans, omitted and numeric typed text, never errors;
  COUNTA counts every non-blank cell and every typed argument, errors included.
* SUM (and AVERAGE's sum) add as Calc does, so near-cancelling sums are 0
  (SUM(0.1,0.2,-0.3) is 0); an overflow is #NUM!.
"""

import math

from src.eval import Range
from src.functions import register
from src.values import (BLANK, DIV0, NUM, VALUE, Blank, Bool, Error, Number, Text,
                        to_number)

ERR504 = Error("Err:504")


def _cells(r):
    """A range's values column by column, the order Calc iterates a range in."""
    return [r.cell(row, col) for col in range(r.left, r.right + 1)
            for row in range(r.top, r.bottom + 1)]


def _groups(args, text_error):
    """Per argument, the numbers Calc's aggregates take from it; or the result Error.

    Any error, in a range or typed, wins over a typed text's error: the first
    error from left to right is the result.  An omitted argument is the number 0.
    """
    groups, text_seen = [], False
    for a in args:
        if isinstance(a, Range):
            xs = []
            for v in _cells(a):
                if isinstance(v, Error):
                    return v
                if isinstance(v, Number):
                    xs.append(v.value)
                elif isinstance(v, Bool):
                    xs.append(1.0 if v.value else 0.0)
            groups.append(xs)
        elif isinstance(a, Error):
            return a
        elif isinstance(a, Text):
            text_seen = True
        elif isinstance(a, Blank):
            groups.append([0.0])
        else:
            n = to_number(a)
            if isinstance(n, Error):
                return n
            groups.append([n.value])
    return text_error if text_seen else groups


def _flat(groups):
    return [x for g in groups for x in g]


def _approx_add(a, b):
    """rtl::math::approxAdd: a sum that cancels to within 2^-48 of its terms is 0."""
    if ((a < 0 < b) or (b < 0 < a)) and abs(a + b) < abs(a) * 2.0 ** -48:
        return 0.0
    return a + b


def _calc_sum(groups):
    """Calc's SUM: Neumaier summation over the arguments last to first (the order
    the interpreter pops them), the last term added with approxAdd.  So
    SUM(0.1,0.2) is 0.30000000000000004 but SUM(0.1,0.2,-0.3) is 0."""
    total = err = mem = 0.0
    for x in (x for g in reversed(groups) for x in g):
        if x == 0.0:
            continue
        if mem == 0.0:
            mem = x
            continue
        t = total + mem
        if abs(total) >= abs(mem):
            err += (total - t) + mem
        else:
            err += (mem - t) + total
        total, mem = t, x
    s = total + err
    if mem == 0.0:
        return s
    return _approx_add(s, mem)


def _num(x):
    return Number(x) if math.isfinite(x) else NUM


def _sum_or_num(groups):
    try:
        return _num(_calc_sum(groups))
    except OverflowError:
        return NUM


@register("SUM")
def sum_(*args):
    g = _groups(args, VALUE)
    return g if isinstance(g, Error) else _sum_or_num(g)


@register("PRODUCT")
def product(*args):
    g = _groups(args, VALUE)
    if isinstance(g, Error):
        return g
    xs = _flat(g)
    return _num(math.prod(xs)) if xs else Number(0)


@register("AVERAGE")
def average(*args):
    g = _groups(args, VALUE)
    if isinstance(g, Error):
        return g
    n = len(_flat(g))
    if not n:
        return DIV0
    s = _sum_or_num(g)
    return s if isinstance(s, Error) else _num(s.value / n)


@register("MIN")
def min_(*args):
    g = _groups(args, ERR504)
    if isinstance(g, Error):
        return g
    xs = _flat(g)
    return Number(min(xs)) if xs else Number(0)


@register("MAX")
def max_(*args):
    g = _groups(args, ERR504)
    if isinstance(g, Error):
        return g
    xs = _flat(g)
    return Number(max(xs)) if xs else Number(0)


@register("MEDIAN")
def median(*args):
    g = _groups(args, ERR504)
    if isinstance(g, Error):
        return g
    xs = sorted(_flat(g))
    if not xs:
        return VALUE
    mid = len(xs) // 2
    return Number(xs[mid]) if len(xs) % 2 else _num((xs[mid - 1] + xs[mid]) / 2)


@register("STDEV")
def stdev(*args):
    g = _groups(args, ERR504)
    if isinstance(g, Error):
        return g
    xs = _flat(g)
    if len(xs) < 2:
        return DIV0
    try:
        mean = _calc_sum([xs]) / len(xs)
        ss = math.fsum((x - mean) ** 2 for x in xs)
        return _num(math.sqrt(ss / (len(xs) - 1)))
    except OverflowError:
        return NUM


@register("COUNT")
def count(*args):
    n = 0
    for a in args:
        if isinstance(a, Range):
            n += sum(1 for v in a.values() if isinstance(v, (Number, Bool)))
        elif isinstance(a, (Number, Bool, Blank)):
            n += 1
        elif isinstance(a, Text) and isinstance(to_number(a), Number):
            n += 1
    return Number(n)


@register("COUNTA")
def counta(*args):
    n = 0
    for a in args:
        if isinstance(a, Range):
            n += sum(1 for v in a.values() if v is not BLANK)
        else:
            n += 1  # every typed argument counts, an omitted one too
    return Number(n)
