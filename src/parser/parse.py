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
    """A malformed formula. The only exception ``parse`` raises.

    ``code`` is the error LibreOffice Calc shows for it, read left to right: an unmatched ')' is
    Err:508; two operands side by side (=1 2, =(2)3) Err:509; a binary operator where an operand is
    expected (=*2, =1+*2) Err:510; the formula ending where an operand is expected Err:511 inside an
    open '(' (=(1+, =SUM(1,) and Err:520 at top level (=1+, =-); a number literal out of the double
    range (=1E400, =1E-400) Err:502. Anything else keeps #VALUE!."""

    def __init__(self, message, code="#VALUE!"):
        super().__init__(message)
        self.code = code


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
            mantissa = re.split("[eE]", text)[0]
            if not math.isfinite(value) or (value == 0 and re.search("[1-9]", mantissa)):
                raise ParseError("number out of range at %d" % pos, "Err:502")
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
        self.depth = 0  # open '(' (groups and calls) around the current token
        # A code Calc gives only when the whole formula parses (a list in a group, =(2,3), is Err:509):
        # any malformed part read later wins (=(2,3)+ is Err:520, =(1,2)) Err:508).
        self.deferred = None

    def defer(self, code):
        if self.deferred is None:
            self.deferred = code

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

    def fail(self, what="unexpected", code="#VALUE!"):
        t = self.tok
        shown = "end of formula" if t.kind == "end" else repr(t.value)
        raise ParseError("%s %s at %d" % (what, shown, t.pos), code)

    def need_operand(self, what="expected an operand, got"):
        """The current token stands where an operand must: fail with Calc's code for it."""
        t = self.tok
        if t.kind == "end":
            self.fail(what, "Err:511" if self.depth else "Err:520")
        if t.kind == "op" and t.value == ")":
            self.fail(what, "Err:511" if self.depth else "Err:508")
        if t.kind == "op" and t.value in (",", ";"):
            # After an operator (=1+,2, =SUM(-,1)) the operand is missing, Err:511; a separator that
            # opens the expression (=,1, =(,1)) stands beside nothing, Err:509.
            before = self.toks[self.i - 1] if self.i else None
            after_op = before is not None and before.kind == "op" and before.value not in ("(", ",", ";")
            self.fail(what, "Err:511" if after_op else "Err:509")
        if t.kind == "op" and t.value == "%":
            self.fail(what, "Err:520")
        if t.kind == "op":
            self.fail(what, "Err:510")
        self.fail(what)

    def after_operand(self, what="unexpected"):
        """The current token follows a whole operand where it cannot: Calc's code for it."""
        t = self.tok
        if t.kind == "op" and t.value == ")":
            self.fail(what, "Err:508")
        if t.kind != "op" or t.value in ("(", ",", ";"):
            self.fail(what, "Err:509")
        self.fail(what)

    def open(self):
        if not self.is_op("("):
            self.fail("expected '(', got")
        self.take()
        self.depth += 1

    def close(self):
        """A ')', or the end of the formula: Calc closes open parentheses there (=SUM(1,2 is 3)."""
        if self.tok.kind != "end":
            if not self.is_op(")"):
                self.after_operand("expected ')', got")
            self.take()
        self.depth -= 1

    def range_end(self, start):
        """After a reference, ':' and a second reference make a range, spaces allowed around ':'
        (A1 : A2). The second end may name the first one's sheet again (S2!A1:S2!A2)."""
        if not self.is_op(":"):
            return start
        if not isinstance(start, Ref):
            self.fail()
        self.take()
        while self.is_op("+") and self.toks[self.i + 1].kind != "end":
            self.take()  # =SUM(A1:+A2) is 3 in Calc: a plus sign there changes nothing
        t = self.tok
        if t.kind == "ref" and isinstance(t.value, Ref):
            end = t.value
            self.take()
        else:
            # Calc reads ':' as an operator and goes on reading its operand: a sign there is Err:520
            # (=A1:-A2, =A1:+), a missing operand the usual code (=A1: 520, =SUM(A1: 511, =A1:(1+ 511).
            if t.kind == "op" and t.value in ("+", "-"):
                self.fail("a sign after ':' at", "Err:520")
            if t.kind == "end" or (t.kind == "op" and t.value != "("):
                self.need_operand("expected a reference after ':', got")
            # A reference in brackets still ends the range (=SUM(A1:(A2)) is 3); any other operand
            # parses and gives Calc's Err:502 (=A1:2, =A1:(2,3)).
            before = self.deferred
            end = self.primary()
            if isinstance(end, Name) and self.deferred == before:
                return end  # =A1:B is #NAME?, as the unknown name B
            if not isinstance(end, Ref) or self.deferred != before:
                self.deferred = before
                self.defer("Err:502")
                return start
        if end.sheet is not None and (start.sheet is None or end.sheet.upper() != start.sheet.upper()):
            raise ParseError("a range ends on another sheet at %d" % t.pos)
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
            # A group. Calc reads ',' or ';' in it as a list separator: the list is Err:509 once the
            # formula parses (=(2,3), =(,1)), and the formula ending after one is Err:511 (=(2, =(,).
            self.open()
            node = Missing() if self.is_op(",", ";") else self.expr()
            listed = False
            while self.is_op(",", ";"):
                self.take()
                listed = True
                if self.tok.kind == "end":
                    self.need_operand()
                if not self.is_op(",", ";", ")"):
                    self.expr()
            self.close()
            if listed:
                self.defer("Err:509")
            return node
        self.need_operand()

    def args(self):
        self.open()
        if self.is_op(")") or self.tok.kind == "end":
            self.close()  # =SUM() and =SUM( are both the empty call
            return ()
        args = []
        while True:
            if self.is_op(",", ";", ")"):
                args.append(Missing())
            else:
                args.append(self.expr())
            if self.is_op(",", ";"):
                self.take()
                if self.tok.kind == "end":
                    self.need_operand()  # =SUM(1, is Err:511
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
            p.after_operand()
        if p.deferred is not None:
            raise ParseError("Calc gives %s for this formula" % p.deferred, p.deferred)
        return node
    except RecursionError:
        raise ParseError("formula nested too deeply") from None
