"""Values, coercion and errors (intent a-i2-values).

Cell values as LibreOffice Calc has them: numbers, text, booleans, the blank cell
and the six errors. ``from_json``/``to_json`` map workbook cells both ways;
``to_number``, ``to_text`` and ``compare`` apply Calc's default coercion rules.
"""

import decimal
import math
import re

__all__ = [
    "Number", "Text", "Bool", "Blank", "BLANK", "Error", "ERROR_CODES",
    "DIV0", "VALUE", "REF", "NAME", "NA", "NUM",
    "from_json", "to_json", "to_number", "to_text", "to_bool", "compare",
    "is_error", "format_number", "approx_equal", "approx_add", "approx_sub",
]

ERROR_CODES = ("#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#N/A", "#NUM!")


class Value:
    __slots__ = ()

    def __setattr__(self, name, value):
        raise AttributeError("values are immutable")


class Number(Value):
    __slots__ = ("value",)

    def __init__(self, value):
        object.__setattr__(self, "value", float(value))

    def __eq__(self, other):
        return isinstance(other, Number) and other.value == self.value

    def __hash__(self):
        return hash(("Number", self.value))

    def __repr__(self):
        return "Number(%r)" % (self.value,)


class Text(Value):
    __slots__ = ("value",)

    def __init__(self, value):
        object.__setattr__(self, "value", str(value))

    def __eq__(self, other):
        return isinstance(other, Text) and other.value == self.value

    def __hash__(self):
        return hash(("Text", self.value))

    def __repr__(self):
        return "Text(%r)" % (self.value,)


class Bool(Value):
    __slots__ = ("value",)

    def __init__(self, value):
        object.__setattr__(self, "value", bool(value))

    def __eq__(self, other):
        return isinstance(other, Bool) and other.value == self.value

    def __hash__(self):
        return hash(("Bool", self.value))

    def __repr__(self):
        return "Bool(%r)" % (self.value,)


class Blank(Value):
    """The blank (missing) cell; use the ``BLANK`` singleton."""

    __slots__ = ()
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __eq__(self, other):
        return isinstance(other, Blank)

    def __hash__(self):
        return hash("Blank")

    def __repr__(self):
        return "BLANK"


BLANK = Blank()


class Error(Value):
    __slots__ = ("code",)

    def __init__(self, code):
        object.__setattr__(self, "code", str(code))

    def __eq__(self, other):
        return isinstance(other, Error) and other.code == self.code

    def __hash__(self):
        return hash(("Error", self.code))

    def __repr__(self):
        return "Error(%r)" % (self.code,)


DIV0 = Error("#DIV/0!")
VALUE = Error("#VALUE!")
REF = Error("#REF!")
NAME = Error("#NAME?")
NA = Error("#N/A")
NUM = Error("#NUM!")


def is_error(v):
    return isinstance(v, Error)


# --- JSON ------------------------------------------------------------------

def from_json(j):
    """A workbook cell (1, "text", true, null, {"error": "#N/A"}) as a Value."""
    if isinstance(j, Value):
        return j
    if j is None:
        return BLANK
    if isinstance(j, bool):
        return Bool(j)
    if isinstance(j, (int, float)):
        return Number(j)
    if isinstance(j, str):
        return Text(j)
    if isinstance(j, dict) and isinstance(j.get("error"), str):
        return Error(j["error"])
    return VALUE


def to_json(v):
    """A Value as a workbook cell; an integral number is written as an integer."""
    if isinstance(v, Number):
        x = v.value
        if not math.isfinite(x):
            return {"error": NUM.code}
        if x == int(x) and abs(x) < 2 ** 53:
            return int(x)
        return x
    if isinstance(v, Text):
        return v.value
    if isinstance(v, Bool):
        return v.value
    if isinstance(v, Error):
        return {"error": v.code}
    if isinstance(v, Blank):
        return None
    raise TypeError("not a value: %r" % (v,))


# --- coercion --------------------------------------------------------------

# Calc's default "unambiguous" text-to-number conversion: a signed decimal with
# an optional exponent, nothing around it.
_NUMBER_TEXT = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def to_number(v):
    """The operand of an arithmetic operator: a Number or an Error."""
    if isinstance(v, Number):
        return v if math.isfinite(v.value) else NUM
    if isinstance(v, Bool):
        return Number(1.0 if v.value else 0.0)
    if isinstance(v, Blank):
        return Number(0.0)
    if isinstance(v, Error):
        return v
    if isinstance(v, Text):
        if _NUMBER_TEXT.fullmatch(v.value):
            x = float(v.value)
            return Number(x) if math.isfinite(x) else NUM
        return VALUE
    return VALUE


def format_number(x):
    """A number as Calc turns it into text (&, CONCATENATE, LEN): an integer below 2**53 exactly; otherwise 15
    significant digits rounded half away from zero, as a decimal when the number itself is from 1E-14 up to
    below 1E15 (999999999999999.5 is 1000000000000000, 9.999999999999995E-15 is 1E-014) and else as
    mantissa E sign and a 3-digit exponent (1E+021, 1E-020); no trailing zeros."""
    if not math.isfinite(x):
        return "#NUM!"
    if x == 0:
        return "0"
    if x == int(x) and abs(x) < 2.0 ** 53:
        return str(int(x))
    d = decimal.Decimal(repr(x))
    q = d.quantize(decimal.Decimal(1).scaleb(d.adjusted() - 14), rounding=decimal.ROUND_HALF_UP)
    e = q.adjusted()
    if -14 <= d.adjusted() < 15:  # Calc picks the form from the exponent before rounding
        t = format(q, "f")
        return t.rstrip("0").rstrip(".") if "." in t else t
    m = format(q.scaleb(-e), "f")
    m = m.rstrip("0").rstrip(".") if "." in m else m
    return "%sE%s%03d" % (m, "-" if e < 0 else "+", abs(e))


def to_text(v):
    """The operand of ``&``: a Text or an Error."""
    if isinstance(v, Text):
        return v
    if isinstance(v, Number):
        return Text(format_number(v.value)) if math.isfinite(v.value) else NUM
    if isinstance(v, Bool):
        return Text("TRUE" if v.value else "FALSE")
    if isinstance(v, Blank):
        return Text("")
    if isinstance(v, Error):
        return v
    return VALUE


def to_bool(v):
    """A logical operand: a Bool or an Error (text is #VALUE!, blank is FALSE)."""
    if isinstance(v, Bool):
        return v
    if isinstance(v, Number):
        return Bool(v.value != 0)
    if isinstance(v, Blank):
        return Bool(False)
    if isinstance(v, Error):
        return v
    return VALUE


def _rank(v):
    # Calc orders numbers (booleans are numbers) before text.
    return 1 if isinstance(v, Text) else 0


def _sign(a, b):
    return (a > b) - (a < b)


def compare(a, b):
    """Compare two values as Calc's = <> < > <= >= do: -1, 0, 1 or an Error."""
    if isinstance(a, Error):
        return a
    if isinstance(b, Error):
        return b
    if isinstance(a, Blank) and isinstance(b, Blank):
        return 0
    if isinstance(a, Blank):
        a = Text("") if isinstance(b, Text) else Number(0.0)
    if isinstance(b, Blank):
        b = Text("") if isinstance(a, Text) else Number(0.0)
    ra, rb = _rank(a), _rank(b)
    if ra != rb:
        return _sign(ra, rb)
    if ra == 1:
        return _sign(a.value.casefold(), b.value.casefold())
    x = 1.0 if a.value is True else 0.0 if a.value is False else a.value
    y = 1.0 if b.value is True else 0.0 if b.value is False else b.value
    return _sign(x, y)


# --- LibreOffice's approximate arithmetic (a-v1-decimal-noise) -------------
# rtl::math as Calc's interpreter uses it for operators. Two doubles are equal when they are within 2**-44
# of each other (relative), are not both whole numbers up to 2**53-1 (nor their difference), and either lie
# within 2**-48 or read the same to 15 significant digits. Adding near-opposites or subtracting near-equals
# gives exactly 0. So =0.1+0.2=0.3 is TRUE and =(0.1+0.2)-0.3 is 0, =1.0000000000000049=1 is TRUE while
# =1.000000000000005=1 is FALSE, and =1E15+1-1E15 stays 1. Fitted to LibreOffice Calc 26.8.1.1 runs.

_E48 = 2.0 ** -48
_E44 = 2.0 ** -44
_MAX_INT = 2.0 ** 53 - 1


def _whole(x):
    """A whole number a double holds exactly, up to 2**53-1 (Calc's isRepresentableInteger)."""
    return x <= _MAX_INT and x == math.floor(x)


def _digits15(x):
    """``x`` rounded to 15 significant digits, half away from zero, from its shortest decimal form."""
    d = decimal.Decimal(repr(x))
    return d.quantize(decimal.Decimal(1).scaleb(d.adjusted() - 14), rounding=decimal.ROUND_HALF_UP)


def approx_equal(a, b):
    """True when the doubles ``a`` and ``b`` are equal as Calc's operators compare them."""
    if a == b:
        return True
    if a == 0.0 or b == 0.0:
        return False
    d = abs(a - b)
    if not math.isfinite(d):
        return False
    a, b = abs(a), abs(b)
    if d > a * _E44 or d > b * _E44:
        return False
    if _whole(d) and _whole(a) and _whole(b):
        return False
    return (d < a * _E48 and d < b * _E48) or _digits15(a) == _digits15(b)


def approx_add(a, b):
    """a + b, exactly 0 when they are near-opposites."""
    if ((a < 0.0 < b) or (b < 0.0 < a)) and approx_equal(a, -b):
        return 0.0
    return a + b


def approx_sub(a, b):
    """a - b, exactly 0 when they are near-equal numbers of the same sign."""
    if ((a < 0.0 and b < 0.0) or (a > 0.0 and b > 0.0)) and approx_equal(a, b):
        return 0.0
    return a - b
