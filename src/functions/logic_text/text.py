"""Text functions as LibreOffice Calc computes them (intent a-i6-logic-text, WI 2).

CONCATENATE, LEFT, RIGHT, MID, LEN, UPPER, LOWER and TRIM.  Arguments follow
a-i3's calling convention: a reference arrives as a ``Range`` (collapsed to its
single cell here), anything else as a Value with errors left in.

Calc's habits kept here:
- a boolean is stored as the number 1/0, so it reads as "1"/"0" in text;
- a count is truncated toward zero, and a negative one is Calc's ``Err:502``;
- MID's start below 1 is ``Err:502``, a missing length ``Err:511``;
- UPPER maps ß to ẞ; TRIM strips spaces and collapses inner runs of them.
"""

import math
import re

from src.functions import register
from src.values import Bool, Error, Number, Text, to_number, to_text

ERR_502 = Error("Err:502")  # invalid argument
ERR_511 = Error("Err:511")  # missing variable (a required argument omitted)

_SPACES = re.compile(" +")


def _scalar(v):
    collapse = getattr(v, "collapse", None)
    return collapse() if collapse is not None else v


def _text(v):
    """An argument as Text, or the Error it carries."""
    v = _scalar(v)
    if isinstance(v, Bool):
        v = Number(1.0 if v.value else 0.0)
    return to_text(v)


def _count(v):
    """A character count or position: an int, or an Error (negative is Err:502)."""
    n = to_number(_scalar(v))
    if isinstance(n, Error):
        return n
    x = n.value
    if not math.isfinite(x):
        return ERR_502
    if x < 0:
        return ERR_502
    return int(x)


@register("CONCATENATE")
def concatenate(*args):
    parts = []
    for a in args:
        t = _text(a)
        if isinstance(t, Error):
            return t
        parts.append(t.value)
    return Text("".join(parts))


def _side(args, take):
    if not args or len(args) > 2:
        return ERR_511 if not args else ERR_502
    t = _text(args[0])
    if isinstance(t, Error):
        return t
    n = 1 if len(args) == 1 else _count(args[1])
    if isinstance(n, Error):
        return n
    return Text(take(t.value, n))


@register("LEFT")
def left(*args):
    return _side(args, lambda s, n: s[:n])


@register("RIGHT")
def right(*args):
    return _side(args, lambda s, n: s[len(s) - n:] if n < len(s) else s)


@register("MID")
def mid(*args):
    if len(args) < 3:
        return ERR_511
    if len(args) > 3:
        return ERR_502
    t = _text(args[0])
    if isinstance(t, Error):
        return t
    start = _count(args[1])
    if isinstance(start, Error):
        return start
    length = _count(args[2])
    if isinstance(length, Error):
        return length
    if start < 1:
        return ERR_502
    return Text(t.value[start - 1:start - 1 + length])


def _one(args, fn):
    if len(args) != 1:
        return ERR_511 if not args else ERR_502
    t = _text(args[0])
    if isinstance(t, Error):
        return t
    return fn(t.value)


@register("LEN")
def len_(*args):
    return _one(args, lambda s: Number(len(s)))


@register("UPPER")
def upper(*args):
    return _one(args, lambda s: Text(s.replace("ß", "ẞ").upper()))


@register("LOWER")
def lower(*args):
    return _one(args, lambda s: Text(s.lower()))


@register("TRIM")
def trim(*args):
    return _one(args, lambda s: Text(_SPACES.sub(" ", s.strip(" "))))
