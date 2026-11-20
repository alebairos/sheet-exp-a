"""Formula dependency helpers for the a-r1-engine checks: which cells hold formulas, and the longest chain."""
import re, sys

def formulas(book):
    return {(s, a): v for s, cells in book["sheets"].items() for a, v in cells.items() if isinstance(v, str) and v.startswith("=")}

REF = re.compile(r"(?:(\$?'?[A-Za-z_][A-Za-z0-9_ ]*'?)!)?\$?([A-Z]{1,3})\$?([0-9]+)(?::\$?([A-Z]{1,3})\$?([0-9]+))?")

def col(c):
    n = 0
    for ch in c: n = n * 26 + ord(ch) - 64
    return n

def longest_chain(book):
    """Longest path of formula-to-formula references (a range reaches every formula inside it)."""
    fs = formulas(book)
    deps = {}
    for (s, a), f in fs.items():
        body = re.sub(r'"[^"]*"', "", f)
        d = set()
        for m in REF.finditer(body):
            sh = (m.group(1) or s).strip("$'")
            c1, r1 = col(m.group(2)), int(m.group(3))
            c2, r2 = (col(m.group(4)), int(m.group(5))) if m.group(4) else (c1, r1)
            for (s2, a2) in fs:
                if s2 != sh: continue
                mm = re.match(r"([A-Z]+)([0-9]+)$", a2)
                cc, rr = col(mm.group(1)), int(mm.group(2))
                if min(c1, c2) <= cc <= max(c1, c2) and min(r1, r2) <= rr <= max(r1, r2):
                    d.add((s2, a2))
        deps[(s, a)] = d
    memo = {}
    sys.setrecursionlimit(100000)
    def depth(k, seen=()):
        if k in memo: return memo[k]
        if k in seen: return 0
        v = 1 + max([depth(x, seen + (k,)) for x in deps[k]] or [0])
        memo[k] = v
        return v
    return max([depth(k) for k in fs] or [0])

