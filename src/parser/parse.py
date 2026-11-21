"""Tokenizer and recursive-descent parser in Calc's operator order."""

import dataclasses
import math
import re

from .nodes import (
    MAX_COL,
    MAX_ROW,
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
    letters_to_col,
)


class ParseError(Exception):
    """A malformed formula. The only exception ``parse`` raises."""


_CELL = r"(\$?)([A-Za-z]{1,3})(\$?)([0-9]+)"
# A reference ends where an identifier could not go on; 'LOG10(' is a call, 'A1B' a name, and
# 'S2!' a sheet name, so S2!A1:S2!A2 reads as two references and not as S2!A1:S2 then !A2.
_REF_END = r"(?![A-Za-z0-9_.(!])"

_TOKEN = re.compile(
    r"""
      (?P<ws>\s+)
    | (?P<num>(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)
    | (?P<str>"(?:[^"]|"")*")
    | (?P<err>\#(?:NULL!|DIV/0!|VALUE!|REF!|NAME\?|NUM!|N/A))
    | (?P<ref>
          (?:(?P<qsheet>'(?:[^']|'')+')!|(?P<sheet>[A-Za-z_][A-Za-z0-9_.]*)!)?
          """ + _CELL + r"""(?::""" + _CELL + r""")?""" + _REF_END + r"""
      )
    | (?P<badsheet>(?:'(?:[^']|'')+'|[A-Za-z_][A-Za-z0-9_.]*)!)
    | (?P<ident>[A-Za-z_][A-Za-z0-9_.]*)
    | (?P<op><>|<=|>=|[-+*/^&=<>%(),;:])
    """,
    re.VERBOSE | re.IGNORECASE,
)

_CELL_GROUPS = _TOKEN.groupindex["sheet"]

_COMPARE = ("=", "<>", "<", ">", "<=", ">=")


class Token:
    __slots__ = ("kind", "value", "pos")

    def __init__(self, kind, value, pos):
        self.kind = kind
        self.value = value
        self.pos = pos

    def __repr__(self):
        return "Token(%s, %r, %d)" % (self.kind, self.value, self.pos)


def _cell(sheet, groups, pos):
    cabs, letters, rabs, digits = groups
    col = letters_to_col(letters)
    row = int(digits)
    if not (1 <= col <= MAX_COL and 1 <= row <= MAX_ROW):
        return None
    return Ref(sheet, col, row, bool(cabs), bool(rabs))


def _ref_token(m, pos):
    text = m.group("ref")
    sheet = None
    if m.group("qsheet"):
        sheet = m.group("qsheet")[1:-1].replace("''", "'")
    elif m.group("sheet"):
        sheet = m.group("sheet")
    # The eight unnamed cell groups come right after the 'sheet' group
    # (groups() is 0-based, group numbers 1-based).
    g = m.groups()
    first = g[_CELL_GROUPS:_CELL_GROUPS + 4]
    second = g[_CELL_GROUPS + 4:_CELL_GROUPS + 8]
    a = _cell(sheet, first, pos)
    if second[1] is None:
        if a is None:
            if sheet is not None:
                raise ParseError("invalid reference %r at %d" % (text, pos))
            return Token("ident", text, pos)  # e.g. XFE1: a name, #NAME? later
        return Token("ref", a, pos)
    b = _cell(sheet, second, pos)
    if a is None or b is None:
        raise ParseError("invalid range %r at %d" % (text, pos))
    return Token("ref", Range(a, b), pos)


def tokenize(src):
    """The tokens of a formula body (without its leading '=')."""
    out = []
    pos = 0
    n = len(src)
    while pos < n:
        m = _TOKEN.match(src, pos)
        if m is None:
            raise ParseError("unexpected %r at %d" % (src[pos], pos))
        kind = m.lastgroup
        text = m.group(0)
        if kind == "ws":
            pass
        elif kind == "num":
            value = float(text)
            if not math.isfinite(value):
                raise ParseError("number out of range at %d" % pos)
            out.append(Token("num", value, pos))
        elif kind == "str":
            out.append(Token("str", text[1:-1].replace('""', '"'), pos))
        elif kind == "err":
            out.append(Token("err", text.upper(), pos))
        elif kind == "ref":
            out.append(_ref_token(m, pos))
        elif kind == "badsheet":
            raise ParseError("sheet name without a reference at %d" % pos)
        elif kind == "ident":
            out.append(Token("ident", text, pos))
        else:
            out.append(Token("op", text, pos))
        pos = m.end()
    out.append(Token("end", None, n))
    return out


class _Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.i = 0

    @property
    def tok(self):
        return self.toks[self.i]

    def is_op(self, *ops):
        t = self.toks[self.i]
        return t.kind == "op" and t.value in ops

    def take(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def fail(self, what="unexpected"):
        t = self.tok
        shown = "end of formula" if t.kind == "end" else repr(t.value)
        raise ParseError("%s %s at %d" % (what, shown, t.pos))

    def expect(self, op):
        if not self.is_op(op):
            self.fail("expected %r, got" % op)
        return self.take()

    def close(self):
        """A ')', or the end of the formula: Calc closes open parentheses there (=SUM(1,2 is 3)."""
        if self.tok.kind != "end":
            self.expect(")")

    def range_end(self, start):
        """After a reference, ':' and a second reference make a range, spaces allowed around ':'
        (A1 : A2). The second end may name the first one's sheet again (S2!A1:S2!A2)."""
        if not self.is_op(":"):
            return start
        if not isinstance(start, Ref):
            self.fail()
        self.take()
        t = self.tok
        end = t.value if t.kind == "ref" else None
        if not isinstance(end, Ref):
            self.fail("expected a reference after ':', got")
        if end.sheet is not None and (start.sheet is None or end.sheet.upper() != start.sheet.upper()):
            raise ParseError("a range ends on another sheet at %d" % t.pos)
        self.take()
        return Range(start, dataclasses.replace(end, sheet=start.sheet))

    # Loosest first.
    def expr(self):
        return self.compare()

    def compare(self):
        left = self.concat()
        while self.is_op(*_COMPARE):
            op = self.take().value
            left = Binary(op, left, self.concat())
        return left

    def concat(self):
        left = self.additive()
        while self.is_op("&"):
            self.take()
            left = Binary("&", left, self.additive())
        return left

    def additive(self):
        left = self.multiplicative()
        while self.is_op("+", "-"):
            op = self.take().value
            left = Binary(op, left, self.multiplicative())
        return left

    def multiplicative(self):
        left = self.power()
        while self.is_op("*", "/"):
            op = self.take().value
            left = Binary(op, left, self.power())
        return left

    def power(self):
        left = self.postfix()
        while self.is_op("^"):
            self.take()
            left = Binary("^", left, self.postfix())
        return left

    def postfix(self):
        node = self.unary()
        while self.is_op("%"):
            self.take()
            node = Percent(node)
        return node

    def unary(self):
        if self.is_op("-"):
            self.take()
            return Unary("-", self.unary())
        if self.is_op("+"):
            self.take()
            return self.unary()
        return self.primary()

    def primary(self):
        t = self.tok
        if t.kind == "num":
            self.take()
            return Number(t.value)
        if t.kind == "str":
            self.take()
            return Text(t.value)
        if t.kind == "err":
            self.take()
            return Error(t.value)
        if t.kind == "ref":
            self.take()
            return self.range_end(t.value)
        if t.kind == "ident":
            self.take()
            name = t.value.upper()
            if self.is_op("("):
                return Call(name, self.args())
            if name in ("TRUE", "FALSE"):
                return Bool(name == "TRUE")
            return Name(name)
        if self.is_op("("):
            self.take()
            node = self.expr()
            self.close()
            return node
        self.fail()

    def args(self):
        self.expect("(")
        if self.is_op(")"):
            self.take()
            return ()
        args = []
        while True:
            if self.is_op(",", ";", ")"):
                args.append(Missing())
            else:
                args.append(self.expr())
            if self.is_op(",", ";"):
                self.take()
                continue
            self.close()
            return tuple(args)


def parse(formula):
    """Parse a cell formula such as '=SUM(A1:A3)*2' into a tree.

    Raises ParseError for anything malformed, never another exception.
    """
    if not isinstance(formula, str):
        raise ParseError("a formula is a string, got %s" % type(formula).__name__)
    body = formula.lstrip()
    if not body.startswith("="):
        raise ParseError("a formula starts with '='")
    try:
        p = _Parser(tokenize(body[1:]))
        node = p.expr()
        if p.tok.kind != "end":
            p.fail()
        return node
    except RecursionError:
        raise ParseError("formula nested too deeply") from None
