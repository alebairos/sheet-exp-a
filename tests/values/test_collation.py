"""Calc's text order through the six comparison operators (wi-a-v1-text-rules-1).

Every expected relation comes from LibreOffice Calc 26.8.1.1 (new document, en-US): each text ranked in Calc with
=SUMPRODUCT(range<cell), never written by hand. "<" and ">": Calc's order; "~": different texts Calc sorts equal
(<= and >= TRUE, = FALSE). The first pairs are the cases of the review of attempt 1 (symbols, emoji and dashes before
digits and letters; ł đ ı ŋ; fullwidth, ligature and numbered forms) and the levels behind them; the rest are drawn
at random from 221 texts of names, words, punctuation, currency and other scripts ranked by Calc.
"""
import functools
import unittest

from src.eval import evaluate
from src.values import Bool

OPS = ["=", "<", ">", "<>", "<=", ">="]
REL = {"<": [False, True, False, True, True, False], ">": [False, False, True, True, False, True],
       "~": [False, False, False, True, True, True]}
PAIRS = [
    ["•", "1", "<"], ["†", "1", "<"], ["¶", "1", "<"], ["√", "1", "<"], ["∞", "1", "<"], ["✓", "a", "<"],
    ["→", "a", "<"], ["😀", "a", "<"], ["😀", "α", "<"], ["a–b", "ab", "<"], ["ł", "m", "<"], ["đ", "e", "<"],
    ["ı", "j", "<"], ["ŋ", "o", "<"], ["Ａ", "b", "<"], ["１", "2", "<"], ["ﬁ", "fj", "<"], ["łb", "lc", "<"],
    ["lb", "łb", "<"], ["ıb", "ic", ">"], ["ŋa", "nz", ">"], ["ǝa", "əa", "<"], ["ſb", "Sb", ">"],
    ["ſb", "sc", "<"], ["śa", "ſa", "<"], ["a", "ａ", "<"], ["ａ", "A", "<"], ["A", "Ａ", "<"],
    ["Straße", "ſtraße", "<"], ["Ⅻ", "XII", ">"], ["🍕", "😀", "<"], ["🦄", "😀", "<"], ["$", "🍕", ">"],
    ["٣", "3", "~"], ["❶", "2", "<"], ["ᴀa", "ab", ">"], ["ᴀb", "ba", "<"], ["ა", "Ա", "<"], ["α", "а", "<"],
    ["а", "א", "<"], ["中", "あ", ">"], ["ア", "中", "<"], ["Ђ", "Е", "<"], ["ё", "ж", "<"],
    ["Øster", "Ostrava", "<"], ["Ørsted", "Orsted", ">"], ["ıstanbul", "istanbul", ">"],
    ["İstanbul", "Istanbul", ">"], ["Łódź", "Lodz", ">"], ["Đorđe", "Dorde", ">"],
    ["Ångström", "Angstrom", ">"], ["item10", "item9", "<"], ["O'Brien", "OBrien", "<"], ["co-op", "coop", "<"],
    ["…", "...", ">"], ["½", "1/2", ">"], ["x²", "x2", ">"], ["µm", "μm", ">"], ["€5", "$5", ">"],
    ["£5", "€5", "<"], ["①", "STRASSE", "<"], ["☆", "þa", "<"], ["abc", "е", "<"], ["ea2", "☆", ">"],
    ["ijs", "[a]", ">"], ["coop", "ea2", "<"], ["cafè", "×", ">"], ["Strasse", "ijs", ">"],
    ["Zuse", "item10", ">"], ["Oster", "ñandú", ">"], ["ação", "Strasse", "<"], ["Ñandu", "‘a’", ">"],
    ["Hamrun", "½", ">"], ["Strasse", "Resume", ">"], ["♥", "done", "<"], ["Capek", "Ørsted", "<"],
    ["a—b", "°", ">"], ["țara", "item10", ">"], ["‰", "ABC", "<"], ["MÜLLER", "Apple", ">"],
    ["❶", "naïve", "<"], ["file", "fjord", "<"], ["résumé", "Résumé", "<"], ["next", "×", ">"],
    ["done", "item 9", "<"], ["item 9", "istanbul", ">"], ["ǝa", "•item", ">"], ["'a'", "б", "<"],
    ["1", "→next", ">"], ["a—b", "е", "<"], ["•item", "ţara", "<"], ["Istanbul", "résume", "<"],
    ["ðe", "Ångström", ">"], ["item 9", "１st", ">"], ["Aesir", "Mueller", "<"], ["ŧb", "ŋa", ">"],
    ["éb", "o", "<"], ["um", "résumé", ">"], ["a", "б", "<"], ["ア", "ƀb", ">"], ["Mueller", "oa", "<"],
    ["ʒa", "éb", ">"], ["na", "O'Brien", "<"], ["中", "ǝa", ">"], ["ab", "O'Brien", "<"], ["ação", "あ", "<"],
    ["a-b", "Zurich", "<"], ["STRASSE", "résume", ">"], ["®", "þa", "<"], ["a b", "Čapek", "<"],
    ["RESUME", "“a”", ">"], ["aB", "Angstrom", "<"], ["de", "nandu", "<"], ["µm", "ea2", ">"],
    ["resume", "café", ">"], ["coöp", "ア", "<"], ["a—b", "①", ">"], ["•item", "østerbro", "<"],
    ["§", "Straße", "<"], ["éb", "CAFE", ">"],
]


class CalcTextOrderTest(unittest.TestCase):
    def test_pairs_compare_as_in_calc(self):
        for a, b, rel in PAIRS:
            book = {"sheets": {"S": {"A1": a, "B1": b}}}
            got = [evaluate("=A1%sB1" % op, book, "S") for op in OPS]
            self.assertEqual(got, [Bool(x) for x in REL[rel]], "%r vs %r: Calc says %s" % (a, b, rel))

    def test_sorting_a_list(self):
        names = ["Zuse", "zoe", "Zoë", "Zürich", "Łódź", "Lodz", "lodz", "Ørsted", "Orsted", "ıstanbul", "istanbul",
                 "co-op", "coop", "Co-op", "item10", "item9", "Ápple", "apple", "Apple", "•note", "1st"]
        book = {"sheets": {"S": {"A%d" % (i + 1): n for i, n in enumerate(names)}}}

        def order(i, j):
            return -1 if evaluate("=A%d<A%d" % (i + 1, j + 1), book, "S") == Bool(True) else 1
        got = sorted(range(len(names)), key=functools.cmp_to_key(order))
        # Calc's order of these names: each ranked with =SUMPRODUCT(A1:A21<A1) in Calc
        self.assertEqual([names[i] for i in got], [
            "•note", "1st", "apple", "Apple", "Ápple", "co-op", "Co-op", "coop", "istanbul", "item10", "item9",
            "ıstanbul", "lodz", "Lodz", "Łódź", "Orsted", "Ørsted", "zoe", "Zoë", "Zürich", "Zuse"])


if __name__ == "__main__":
    unittest.main()
