"""IF, IFERROR, AND, OR, NOT, ISBLANK, ISNUMBER, ISTEXT and ISERROR (intent a-i6-logic-text, wi 1).

As LibreOffice Calc computes them:

- IF and NOT read their condition as a boolean: a number is TRUE when non-zero (a
  boolean is the number 1/0, as Calc stores it), a blank is FALSE, text that reads as a
  number is that number, the text TRUE/FALSE in any case is that boolean, other text is
  #VALUE!, and an error comes through.  IF hands back the chosen argument untouched, a
  reference included (so ISBLANK(IF(1,A5)) sees the empty cell); a missing else is FALSE.
- IFERROR gives its first argument unless that is an error.
- AND/OR take numbers and booleans; from a reference, text and blanks are skipped, while
  a typed text argument (even "TRUE") is #VALUE!; nothing logical at all is #VALUE!, and
  the first error comes through.
- The IS functions look at the referenced cell's value; ISBLANK is TRUE only for a
  reference to an empty cell, and ISNUMBER is TRUE for a boolean, as Calc stores it as 1/0.
"""

from src.eval import Range
from src.functions import register
from src.values import VALUE, Blank, Bool, Error, Number, Text, to_number

_FALSE = Bool(False)

# Calc's errors for a call with the wrong number of arguments: too few is Err:511
# ("missing variable"), too many Err:504 (Err:508 for NOT, which Calc compiles as an
# operator); an IFERROR whose value is left out is Err:518.
FEW = Error("Err:511")
MANY = Error("Err:504")
NOT_MANY = Error("Err:508")
MISSING = Error("Err:518")


def _count(args, low, high, many=MANY):
    """None when ``low <= len(args) <= high``, else Calc's error for the call."""
    if len(args) < low:
        return FEW
    if len(args) > high:
        return many
    return None


def _value(arg):
    """An argument as one Value: a reference collapses to its cell (#VALUE! if wider)."""
    return arg.collapse() if isinstance(arg, Range) else arg


def _condition(arg):
    """IF/NOT's condition as a Python bool, or the Error it gives."""
    v = _value(arg)
    if isinstance(v, Error):
        return v
    if isinstance(v, Bool):
        return v.value
    if isinstance(v, Blank):
        return False
    if isinstance(v, Text):
        word = v.value.strip().upper()
        if word in ("TRUE", "FALSE"):
            return word == "TRUE"
        v = to_number(Text(v.value.strip()))  # Calc reads " 1 " as 1 here
        if isinstance(v, Error):
            return v
    if isinstance(v, Number):
        return v.value != 0
    return VALUE


@register("IF")
def if_(*args):
    bad = _count(args, 1, 3)
    if bad:
        return bad
    c = _condition(args[0])
    if isinstance(c, Error):
        return c
    if c:
        return args[1] if len(args) > 1 else Bool(True)
    return args[2] if len(args) > 2 else _FALSE


@register("IFERROR")
def iferror(*args):
    bad = _count(args, 2, 2)
    if bad:
        return bad
    value, fallback = args
    if isinstance(value, Blank):  # IFERROR(,x): the value itself is missing
        return MISSING
    return fallback if isinstance(_value(value), Error) else value


def _logicals(args):
    """The truth values AND/OR combine, or the first Error (#VALUE! when there are none)."""
    out = []
    for arg in args:
        if isinstance(arg, Range):
            for v in arg.values():
                if isinstance(v, Error):
                    return v
                if isinstance(v, Bool):
                    out.append(v.value)
                elif isinstance(v, Number):
                    out.append(v.value != 0)
                # text and blanks in a reference are skipped
        elif isinstance(arg, Error):
            return arg
        elif isinstance(arg, Bool):
            out.append(arg.value)
        elif isinstance(arg, Number):
            out.append(arg.value != 0)
        elif isinstance(arg, Text):
            return VALUE
        elif isinstance(arg, Blank):  # an omitted argument: AND(,1) is FALSE in Calc
            out.append(False)
    return out if out else VALUE


@register("AND")
def and_(*args):
    xs = _count(args, 1, 255) or _logicals(args)
    return xs if isinstance(xs, Error) else Bool(all(xs))


@register("OR")
def or_(*args):
    xs = _count(args, 1, 255) or _logicals(args)
    return xs if isinstance(xs, Error) else Bool(any(xs))


@register("NOT")
def not_(*args):
    bad = _count(args, 1, 1, NOT_MANY)
    if bad:
        return bad
    c = _condition(args[0])
    return c if isinstance(c, Error) else Bool(not c)


@register("ISBLANK")
def isblank(*args):
    bad = _count(args, 1, 1)
    if bad:
        return bad
    value = args[0]
    return Bool(isinstance(value, Range) and isinstance(value.collapse(), Blank))


@register("ISNUMBER")
def isnumber(*args):
    bad = _count(args, 1, 1)
    if bad:
        return bad
    value = args[0]
    return Bool(isinstance(_value(value), (Number, Bool)))


@register("ISTEXT")
def istext(*args):
    bad = _count(args, 1, 1)
    if bad:
        return bad
    value = args[0]
    return Bool(isinstance(_value(value), Text))


@register("ISERROR")
def iserror(*args):
    bad = _count(args, 1, 1)
    if bad:
        return bad
    value = args[0]
    return Bool(isinstance(_value(value), Error))
