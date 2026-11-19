"""ROUND, ROUNDUP, ROUNDDOWN, INT, MOD, ABS, POWER and SQRT (intent a-i5-math, wi 2).

Each argument is one number: a reference collapses to its cell (a blank is 0), a
boolean is 1/0, text that reads as a number is that number, other text is #VALUE!,
and an error argument is returned (the leftmost first).

Rounding works on the decimal value Calc shows, the number rounded to 15 significant
digits, so ROUND(1.005,2) is 1.01 and ROUNDUP(0.1+0.2,1) is 0.3; ROUND goes half away
from zero, ROUNDUP away from zero, ROUNDDOWN toward it, and the digit count is
truncated toward zero (negative counts round left of the point).
"""

import math
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal, InvalidOperation

from src.eval import Range, _power
from src.functions import register
from src.values import DIV0, NUM, VALUE, Error, Number, to_number

# Calc's "invalid argument", for SQRT of a negative number.
INVALID = Error("Err:502")


def _number(arg):
    """One argument as a float, or the Error it gives."""
    if isinstance(arg, Range):
        arg = arg.collapse()
    v = to_number(arg)
    return v if isinstance(v, Error) else v.value


def _numbers(*args):
    """The arguments as floats, or the first Error among them."""
    out = []
    for a in args:
        x = _number(a)
        if isinstance(x, Error):
            return x
        out.append(x)
    return out


def _result(x):
    return Number(x) if math.isfinite(x) else NUM


def _shown(x):
    """``x`` as the decimal Calc shows: 15 significant digits."""
    return Decimal("%.15g" % x) if x else Decimal(0)


def _approx_floor(x):
    """Floor of the value Calc shows, so 2.9999999999999996 floors to 3 as in Calc."""
    return math.floor(float(_shown(x)))


def _approx_equal(a, b):
    """Equal up to Calc's rounding noise (rtl::math::approxEqual: about 15 significant digits)."""
    return a == b or abs(a - b) < max(abs(a), abs(b)) * 2.0 ** -48


def _round(x, digits, mode):
    if not math.isfinite(x) or not math.isfinite(digits):
        return NUM
    places = int(digits)  # truncated toward zero, as Calc does
    if places > 300:
        return _result(x)
    if places < -308:
        return _result(0.0)
    d = _shown(x)
    try:
        r = d.quantize(Decimal(1).scaleb(-places), rounding=mode)
    except InvalidOperation:
        # More digits than the decimal context holds: the shown value is already exact.
        return _result(float(d))
    return _result(float(r))


def _rounding(mode):
    def fn(number, digits=Number(0.0)):
        args = _numbers(number, digits)
        if isinstance(args, Error):
            return args
        return _round(args[0], args[1], mode)

    return fn


register("ROUND")(_rounding(ROUND_HALF_UP))      # ROUND_HALF_UP is half away from zero
register("ROUNDUP")(_rounding(ROUND_UP))         # away from zero
register("ROUNDDOWN")(_rounding(ROUND_DOWN))     # toward zero


@register("INT")
def int_(number):
    x = _number(number)
    return x if isinstance(x, Error) else _result(float(_approx_floor(x)))


@register("MOD")
def mod(dividend, divisor):
    args = _numbers(dividend, divisor)
    if isinstance(args, Error):
        return args
    a, b = args
    if b == 0:
        return DIV0
    # As Calc: approxSub(a, approxFloor(a / b) * b), which must lie between 0 and the divisor.
    whole = _approx_floor(a / b) * b
    r = 0.0 if _approx_equal(a, whole) else a - whole
    if (b > 0 and 0 <= r < b) or (b < 0 and b < r <= 0):
        return _result(r)
    return VALUE


@register("ABS")
def abs_(number):
    x = _number(number)
    return x if isinstance(x, Error) else _result(abs(x))


@register("POWER")
def power(base, exponent):
    args = _numbers(base, exponent)
    if isinstance(args, Error):
        return args
    return _power(args[0], args[1])  # exactly the ^ operator


@register("SQRT")
def sqrt(number):
    x = _number(number)
    if isinstance(x, Error):
        return x
    return INVALID if x < 0 else _result(math.sqrt(x))
