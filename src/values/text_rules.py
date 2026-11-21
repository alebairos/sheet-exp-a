"""Calc's text rules (LibreOffice defaults, en-US): how text sorts and how text reads as a number.

``collation_key(s)``: the key = <> < > <= >= order text by, as a new Calc document does (case-sensitive,
locale collation): first the base characters, then accents, then case and width. Each character becomes
collation elements (primary, secondary, tertiary):

- Primary: Calc's own order of base characters, probed from Calc (collation_data.ORDER: spaces, punctuation,
  symbols, currency, digits, then the Latin letters a..z with the letters Calc sorts after each one, as
  ı after i, ŋ after n, ə after e, ŧ after t, then þ; then Greek and Cyrillic). What the probe did not
  cover follows rules: other punctuation, symbols and emoji sort just after the probed symbol of their
  category nearest below them in code point; any script's decimal digit is that digit (٣ sorts equal to 3);
  a numbered sign (❶, ➀) is its number; a Latin letter named "LATIN ... LETTER X ..." sorts just after x;
  letters of other scripts sort after Cyrillic, by script in Calc's order of scripts (collation_data.SCRIPTS),
  then by code point. Known to differ from Calc: a few rare blocks the probe did not cover (Latin
  Extended-E such as ꬾ, Braille, playing cards, alchemical symbols) and Coptic letters in the Greek block.
- Secondary: accents (e < é < è < ê < ë < f), from the decomposed form; ł đ ħ ø are l d h o with a stroke,
  ð is d, ſ is s, æ œ ß are ae oe ss with a mark of their own.
- Tertiary: lower case before upper case, then compatibility forms after their base (a < ａ < A < Ａ; ﬁ is
  f i, ² is 2, Ⅻ is XII), from the character's compatibility decomposition.

Control characters (tab) sort before everything; format characters (soft hyphen) are ignored, so two
different strings can sort equal (é and e + combining acute): = and <> still compare text exactly.

``parse_number(s)``: the number Calc reads from text in arithmetic (and in every function that reads a number),
or None. Spaces (U+0020 and no-break) around and between the parts; one number (ASCII digits, ',' grouping by
threes, '.', an exponent); at most one sign, before or after; one '$' before or after; '(' ')' around it for a
negative, with no sign; one '%' at the end; no '$' with '%'; no '$' or '%' with an exponent; TRUE and FALSE in
any case (spaces only around them). A number beyond the largest double gives the largest double, without its
sign. Text Calc reads as a date, time or fraction ("1/2", "1 1/2") is not read here: dates are out of scope.
"""
import bisect
import functools
import re
import unicodedata

from .collation_data import ORDER, SCRIPTS, TIES

__all__ = ["collation_key", "parse_number"]

# Primary weights: (position, code point). A probed character has (its position in Calc's order, 0).
_PRIMARY = {}
for _i, _c in enumerate(ORDER):
    _PRIMARY[_c] = _PRIMARY[ORDER[_i - 1]] if _c in TIES else (_i + 1, 0)
_DIGITS = _PRIMARY["0"][0]  # unprobed symbols sort just before the digits
_AFTER_LATIN = len(ORDER) + 1  # letters of other scripts: then by script, in Calc's order of scripts
_SCRIPT = {w: i for i, w in enumerate(SCRIPTS)}
_SYMBOL_CODES = {}  # general category -> code points of the probed symbols of that category
for _c in sorted(ORDER):
    if _PRIMARY[_c][0] < _DIGITS:
        _SYMBOL_CODES.setdefault(unicodedata.category(_c), []).append(ord(_c))

# Accent order after "no accent" (1): acute grave breve circumflex caron ring diaeresis
# double-acute tilde dot-above cedilla ogonek macron; other marks after them.
_ACCENT = {m: i + 2 for i, m in enumerate(
    "\u0301\u0300\u0306\u0302\u030c\u030a\u0308\u030b\u0303\u0307\u0327\u0328\u0304")}
_STROKE, _LIG, _ETH, _SZ, _LONG = 40, 41, 42, 43, 44
# Letters Calc sorts as a base letter with a mark of their own (secondary), not as letters of their own.
_SPECIAL = {"ø": ("o", _STROKE), "ł": ("l", _STROKE), "đ": ("d", _STROKE), "ħ": ("h", _STROKE),
            "ð": ("d", _ETH), "ſ": ("s", _LONG), "æ": ("a", _LIG, "e"), "œ": ("o", _LIG, "e"), "ß": ("s", _SZ, "s")}
# Tertiary weight of a compatibility form, by its decomposition tag (lower case 1; upper case adds 6
# for the first five: a < ａ < A < Ａ).
_TAG = {"": 1, "<wide>": 2, "<compat>": 3, "<font>": 4, "<circle>": 5, "<initial>": 13, "<medial>": 14,
        "<final>": 15, "<isolated>": 16, "<noBreak>": 17, "<square>": 18, "<super>": 19, "<sub>": 20,
        "<vertical>": 21, "<fraction>": 22, "<narrow>": 23, "<small>": 24}


def _small_number(ch):
    """A number sign of a small whole value (❶, ➀, ↅ): Calc sorts it as that number."""
    if unicodedata.category(ch) in ("No", "Nl") and unicodedata.normalize("NFKD", ch) == ch:
        v = unicodedata.numeric(ch, None)
        if v is not None and v == int(v) and 0 <= v <= 20:
            return str(int(v))
    return None


def _primary(ch):
    """The primary weight of a base character (lower case, no compatibility decomposition)."""
    p = _PRIMARY.get(ch)
    if p:
        return p
    cat = unicodedata.category(ch)
    if cat == "Nd":
        return _PRIMARY[str(unicodedata.decimal(ch))]
    if cat[0] in "PSZ" or cat == "Lm":  # just after the nearest probed symbol of its category below it
        codes = _SYMBOL_CODES.get(cat, ())
        i = bisect.bisect(codes, ord(ch))
        return (_PRIMARY[chr(codes[i - 1])][0] if i else _DIGITS - 1, ord(ch))
    name = unicodedata.name(ch, "")
    if name.startswith("LATIN "):
        # "LATIN SMALL LETTER L WITH MIDDLE TILDE", "LATIN LETTER SMALL CAPITAL A": just after that letter
        letter = [w for w in name.split(" LETTER ", 1)[-1].split() if w not in ("SMALL", "CAPITAL")][:1]
        if letter and len(letter[0]) == 1 and letter[0].lower() in _PRIMARY:
            return (_PRIMARY[letter[0].lower()][0], ord(ch))
        return (_PRIMARY["z"][0], ord(ch))
    if cat[0] in "LN":
        return (_AFTER_LATIN + _SCRIPT.get(name.split(" ")[0], len(SCRIPTS)), ord(ch))
    return (_DIGITS - 1, ord(ch))


def _elements(s, tag=""):
    """(primary, secondary, tertiary) per collation element; primary None for an accent."""
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat == "Cf":
            continue
        if cat == "Cc":
            out.append(((0, ord(ch)), 1, 1))  # before the space
            continue
        if cat.startswith("M"):  # a combining accent: on the letter before it
            out.append((None, _ACCENT.get(ch, 30 + ord(ch) % 1000), 1))
            continue
        if ch in _PRIMARY:  # probed as it is (spacing accents such as ´ ¨ ¯ are symbols of their own)
            out.append((_PRIMARY[ch], 1, _TAG.get(tag, 25)))
            continue
        low = ch.lower()
        d = unicodedata.normalize("NFD", low)
        base, accents = d[0], [(None, _ACCENT.get(m, 30 + ord(m) % 1000), 1) for m in d[1:]]
        dec = unicodedata.decomposition(base)
        if dec.startswith("<") and base not in _PRIMARY and base not in _SPECIAL:
            # a compatibility form (ﬁ ² Ａ Ⅻ): its base, marked at the tertiary level
            out += _elements(unicodedata.normalize("NFKD", ch), tag or dec.split(">")[0] + ">")
            continue
        number = _small_number(base)
        if number is not None:
            out += _elements(number, tag or "<circle>") + accents
            continue
        t = _TAG.get(tag, 25) + (6 if ch != low and _TAG.get(tag, 25) <= 5 else 0)
        if base in _SPECIAL:
            out += [(None, p, 1) if isinstance(p, int) else (_primary(p), 1, t) for p in _SPECIAL[base]] + accents
            continue
        out.append((_primary(base), 1, t))
        out += accents
    return out


@functools.lru_cache(maxsize=4096)
def collation_key(s):
    """Calc's sort key for text s: compare keys with < to order texts (base characters, then accents, then case)."""
    e = _elements(s)
    return (tuple(x[0] for x in e if x[0] is not None), tuple(x[1] for x in e), tuple(x[2] for x in e))


# One part of a number text: the number itself (grouped by threes or not, with an optional exponent) or a sign.
_TOKEN = re.compile(r" *(?:(?P<num>[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]*)?|[0-9]+(?:\.[0-9]*)?|\.[0-9]+)"
                    r"(?: *[eE] *(?P<exp>[-+]?[0-9]+))?|(?P<sym>[-+$()%]))")
# Calc reads a number beyond the largest double as its largest number (it shows 1.79769313486232E+308).
# Here it is the largest double that still has 15 significant digits: ./engine prints numbers rounded to
# 15 digits, and 1.7976931348623157E+308 rounds up past the largest double (src/cli.py's _reported crashes on
# it, also for a typed =1.7976931348623157E308 on main). 1.79769313486231E+308 is 3e-15 below Calc's value.
_LARGEST = 1.79769313486231e308


def parse_number(s):
    """The number Calc reads from text s, or None when Calc gives #VALUE! (see the module's docstring)."""
    b = s.strip(" ")
    if b.upper() in ("TRUE", "FALSE"):
        return 1.0 if b.upper() == "TRUE" else 0.0
    t = s.replace("\u00a0", " ").strip(" ")  # a no-break space separates parts like a space
    toks, pos, num = [], 0, None
    while pos < len(t):
        m = _TOKEN.match(t, pos)
        if not m or m.end() == pos:
            return None
        pos = m.end()
        if m["num"] is not None:
            if num is not None:
                return None
            num = m
            toks.append("N")
        else:
            toks.append(m["sym"])
    if num is None:
        return None
    if any(toks.count(c) > 1 for c in "$%()") or toks.count("+") + toks.count("-") > 1:
        return None
    if "%" in toks and (toks[-1] != "%" or "$" in toks):
        return None
    if num["exp"] and ("%" in toks or "$" in toks):
        return None
    n = toks.index("N")
    if "(" in toks or ")" in toks:
        if "(" not in toks[:n] or ")" not in toks[n:] or "+" in toks or "-" in toks:
            return None
    x = float(num["num"].replace(",", "") + ("e" + num["exp"] if num["exp"] else ""))
    if x > _LARGEST:
        return _LARGEST  # Calc gives its largest number, without the sign (see _LARGEST)
    if "-" in toks or "(" in toks:
        x = -x
    return x / 100 if "%" in toks else x
