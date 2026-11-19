"""Formula parser (intent i1-parser).

``parse(formula)`` turns a cell formula (with its leading ``=``) into a tree of
nodes; ``show(node)`` prints a tree as one canonical line.  Precedence follows
LibreOffice Calc, loosest first::

    comparisons (= <> < > <= >=)  &  + -  * /  ^  postfix %  unary - +  primary

Every binary level is left-associative, so ``2^3^2`` is ``(2^3)^2`` and
``-A1^2`` is ``(-A1)^2``.  Any malformed input raises :class:`ParseError` and
nothing else.
"""

from .nodes import (  # noqa: F401
    Binary,
    Bool,
    Call,
    Error,
    Missing,
    Name,
    Number,
    Percent,
    Range,
    Ref,
    Text,
    Unary,
    col_to_letters,
    letters_to_col,
    show,
)
from .parse import ParseError, parse, tokenize  # noqa: F401

__all__ = [
    "parse", "show", "tokenize", "ParseError",
    "Number", "Text", "Bool", "Error", "Ref", "Range", "Name", "Call",
    "Missing", "Unary", "Percent", "Binary",
    "col_to_letters", "letters_to_col",
]
