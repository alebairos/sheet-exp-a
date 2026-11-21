"""Calc's text rules (LibreOffice defaults, en-US): how text sorts.

``collation_key(s)``: the key = <> < > <= >= order text by: letters first (a..z, then þ), then accents
(e < é < è < ê < ë < f), then case (lower before upper), as a new Calc document does (case-sensitive,
locale collation). Control characters (tab) sort first, then punctuation, symbols and digits in Calc's
order, then letters; other scripts come after Latin, by code point. Format characters (soft hyphen) are
ignored, so two different strings can sort equal (é and e + combining acute): = and <> still compare
text exactly, as Calc does. The order was taken from LibreOffice Calc 26.8.1.1 runs (plan a-v1-text-rules).
"""
import unicodedata

__all__ = ["collation_key"]

# Primary order of punctuation, symbols and digits as Calc sorts them, then the letters.
_SYMBOLS = " _-,;:!¡?¿.·'\"«»()[]{}§@*/\\&#%`´^¯¨¸°©®+±÷×<=>¬|¦~¤¢$£¥€⁄"
_PRIMARY = {c: i + 1 for i, c in enumerate(_SYMBOLS + "0123456789" + "abcdefghijklmnopqrstuvwxyzþ")}
# Accent order after "no accent" (1): acute grave breve circumflex caron ring diaeresis
# double-acute tilde dot-above cedilla ogonek macron.
_ACCENT = {m: i + 2 for i, m in enumerate("̧̨́̀̆̂̌̊̈̋̃̇̄")}
# Letters Calc sorts as other letters with a mark of their own (secondary weight).
_STROKE, _LIG, _ETH, _SZ = 40, 41, 42, 43
_SPECIAL = {"ø": ("o", _STROKE), "ð": ("d", _ETH), "æ": ("a", _LIG, "e"), "œ": ("o", _LIG, "e"), "ß": ("s", _SZ, "s")}
# Variant forms: sort as their base, after it at the case level.
_VARIANTS = {"ª": "a", "º": "o", "¹": "1", "²": "2", "³": "3", "½": "1⁄2", "¼": "1⁄4", "¾": "3⁄4", "µ": "μ",
             " ": " "}


def _elements(s, variant=False):
    """(primary, secondary, tertiary) per collation element; tertiary 1 lower, 2 upper, 3 a variant."""
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat == "Cf":
            continue
        if cat == "Cc":
            out.append((ord(ch) - 1000, 1, 1))  # before the space
            continue
        if cat == "Mn":  # a combining accent: on the letter before it
            out.append((0, _ACCENT.get(ch, 30 + ord(ch) % 1000), 1))
            continue
        if ch in _VARIANTS:
            out += _elements(_VARIANTS[ch], True)
            continue
        low = ch.lower()
        t = 3 if variant else 2 if ch != low else 1
        if low in _SPECIAL:
            out += [(0, p, 1) if isinstance(p, int) else (_PRIMARY[p], 1, t) for p in _SPECIAL[low]]
            continue
        d = unicodedata.normalize("NFD", low)
        out.append((_PRIMARY.get(d[0], 1000 + ord(d[0])), 1, t))  # other scripts: after Latin
        out += [(0, _ACCENT.get(m, 30 + ord(m) % 1000), 1) for m in d[1:]]
    return out


def collation_key(s):
    """Calc's sort key for text s: compare keys with < to order texts (letters, then accents, then case)."""
    e = _elements(s)
    return ([x[0] for x in e if x[0]], [x[1] for x in e], [x[2] for x in e])
