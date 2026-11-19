"""Recalculation in dependency order (intent a-i4-recalc).

``compute(book)`` returns SPEC.md's computed workbook: every formula replaced by its
value, constants exactly as given, cells in input order.  ``Workbook(book)`` keeps a
workbook live: ``set(sheet, addr, raw)`` changes one cell and recomputes only the
formulas that read it (directly, through a range, or through other formulas).

Each formula is parsed once and its references collected from the tree.  The values
the evaluator reads live in ``self._values`` (SPEC.md's shape holding
:mod:`src.values` Values; ``from_json`` passes them through), and a formula is always
evaluated after every formula it reads.  Order comes from an iterative Tarjan pass
(no Python recursion, so long chains and long cycles are safe): its strongly connected
components arrive precedents first, and a component that is a cycle (more than one
cell, or a cell reading itself) is Calc's circular-reference error ``Err:522`` without
being evaluated.  Formulas that read a cycle are evaluated as usual, so the error
flows through them as any error does (``ISERROR`` of it is TRUE, as in LibreOffice).
"""

import bisect

from src import parser as p
from src.eval import evaluate_node
from src.values import VALUE, Error, from_json, to_json

__all__ = ["Workbook", "compute", "CIRCULAR"]

CIRCULAR = Error("Err:522")


def compute(book):
    """The computed workbook (SPEC.md's JSON) of ``book``; the input is never changed."""
    return Workbook(book).computed()


def _addr(col, row):
    return p.col_to_letters(col) + str(row)


def _split(addr):
    """'AB12' -> (col, row), or None for text that is not a plain cell address."""
    addr = addr.upper()
    i = 0
    while i < len(addr) and "A" <= addr[i] <= "Z":
        i += 1
    if i == 0 or i == len(addr) or not addr[i:].isdigit() or addr[i] == "0":
        return None
    return p.letters_to_col(addr[:i]), int(addr[i:])


def _refs(tree):
    """Every Ref and Range node of a parse tree, without recursion."""
    out = []
    stack = [tree]
    while stack:
        n = stack.pop()
        if isinstance(n, (p.Ref, p.Range)):
            out.append(n)
        elif isinstance(n, p.Binary):
            stack.append(n.left)
            stack.append(n.right)
        elif isinstance(n, (p.Unary, p.Percent)):
            stack.append(n.operand)
        elif isinstance(n, p.Call):
            stack.extend(n.args)
    return out


def _is_formula(raw):
    return isinstance(raw, str) and raw.startswith("=")


class Workbook:
    """A live workbook: computed on creation, recomputed incrementally by :meth:`set`."""

    def __init__(self, book):
        sheets = book.get("sheets", {}) if isinstance(book, dict) else {}
        # The cells as given, per sheet, in input order (formulas as their text).
        self._raw = {name: dict(cells or {}) for name, cells in sheets.items()}
        self._build()
        self._recompute(list(self._trees))

    # --- the graph --------------------------------------------------------

    def _build(self):
        self._folded = {name.casefold(): name for name in reversed(list(self._raw))}
        self._values = {"sheets": {name: {} for name in self._raw}}
        self._trees = {}          # (sheet, addr) of a formula -> parse tree, or None
        self._points = {}         # (sheet, addr) of a formula -> the cells it reads
        self._rects = {}          # (sheet, addr) of a formula -> its ranges (sheet, top, left, bottom, right)
        self._readers = {}        # (sheet, addr) -> formulas reading that one cell
        self._range_readers = {}  # (sheet, col) -> [(top, bottom, left, right, formula)]
        self._formula_rows = {}   # (sheet, col) -> sorted rows of the formula cells there
        for sheet, cells in self._raw.items():
            values = self._values["sheets"][sheet]
            for addr, raw in cells.items():
                if _is_formula(raw):
                    self._add_formula(sheet, addr, raw)
                else:
                    values[addr] = from_json(raw)

    def _sheet(self, name, own):
        if name is None:
            return own
        if name in self._raw:
            return name
        return self._folded.get(name.casefold())

    def _add_formula(self, sheet, addr, raw):
        key = (sheet, addr)
        try:
            tree = p.parse(raw)
        except p.ParseError:
            tree = None
        self._trees[key] = tree
        points, rects = set(), []
        for node in _refs(tree) if tree is not None else ():
            start, end = (node, node) if isinstance(node, p.Ref) else (node.start, node.end)
            target = self._sheet(start.sheet, sheet)
            if target is None:
                continue  # a sheet the book lacks: the evaluator gives #REF!
            if start is end:
                points.add((target, _addr(start.col, start.row)))
            else:
                top, bottom = sorted((start.row, end.row))
                left, right = sorted((start.col, end.col))
                rects.append((target, top, left, bottom, right))
        self._points[key] = points
        self._rects[key] = rects
        for cell in points:
            self._readers.setdefault(cell, set()).add(key)
        for target, top, left, bottom, right in rects:
            for col in range(left, right + 1):
                self._range_readers.setdefault((target, col), []).append((top, bottom, left, right, key))
        pos = _split(addr)
        if pos:
            bisect.insort(self._formula_rows.setdefault((sheet, pos[0]), []), pos[1])

    def _drop_formula(self, sheet, addr):
        key = (sheet, addr)
        if key not in self._trees:
            return
        del self._trees[key]
        for cell in self._points.pop(key):
            readers = self._readers.get(cell)
            if readers is not None:
                readers.discard(key)
                if not readers:
                    del self._readers[cell]
        for target, top, left, bottom, right in self._rects.pop(key):
            for col in range(left, right + 1):
                entries = self._range_readers.get((target, col))
                if entries:
                    entries[:] = [e for e in entries if e[4] != key]
        pos = _split(addr)
        if pos:
            rows = self._formula_rows.get((sheet, pos[0]))
            if rows:
                i = bisect.bisect_left(rows, pos[1])
                if i < len(rows) and rows[i] == pos[1]:
                    del rows[i]

    def _precedents(self, key):
        """The formula cells ``key`` reads, in a stable order."""
        out = [c for c in self._points[key] if c in self._trees]
        for target, top, left, bottom, right in self._rects[key]:
            for col in range(left, right + 1):
                rows = self._formula_rows.get((target, col))
                if not rows:
                    continue
                letters = p.col_to_letters(col)
                for row in rows[bisect.bisect_left(rows, top):bisect.bisect_right(rows, bottom)]:
                    out.append((target, letters + str(row)))
        return out

    def _dependents(self, cell):
        """The formulas reading ``cell`` directly or through a range."""
        out = set(self._readers.get(cell, ()))
        pos = _split(cell[1])
        if pos:
            col, row = pos
            for top, bottom, _left, _right, key in self._range_readers.get((cell[0], col), ()):
                if top <= row <= bottom:
                    out.add(key)
        return out

    # --- evaluation -------------------------------------------------------

    def _recompute(self, keys):
        """Evaluate the formulas ``keys`` (closed under dependents), precedents first."""
        todo = set(keys)
        index, low, on_stack = {}, {}, set()
        stack, counter = [], 0
        for root in keys:
            if root in index:
                continue
            work = [(root, iter(self._precedents(root)))]
            index[root] = low[root] = counter
            counter += 1
            stack.append(root)
            on_stack.add(root)
            while work:
                node, succ = work[-1]
                advanced = False
                for nxt in succ:
                    if nxt not in todo:
                        continue  # already computed and unchanged
                    if nxt not in index:
                        index[nxt] = low[nxt] = counter
                        counter += 1
                        stack.append(nxt)
                        on_stack.add(nxt)
                        work.append((nxt, iter(self._precedents(nxt))))
                        advanced = True
                        break
                    if nxt in on_stack:
                        low[node] = min(low[node], index[nxt])
                if advanced:
                    continue
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    component = []
                    while True:
                        c = stack.pop()
                        on_stack.discard(c)
                        component.append(c)
                        if c == node:
                            break
                    if len(component) > 1 or node in self._precedents(node):
                        for c in component:
                            self._values["sheets"][c[0]][c[1]] = CIRCULAR
                    else:
                        self._evaluate(node)

    def _evaluate(self, key):
        sheet, addr = key
        tree = self._trees[key]
        self._values["sheets"][sheet][addr] = VALUE if tree is None else evaluate_node(tree, self._values, sheet)

    # --- the API ----------------------------------------------------------

    def set(self, sheet, addr, raw):
        """Set one cell as typed ("=..." is a formula, None blanks it); return the formulas recomputed."""
        if sheet not in self._raw:
            # A new sheet can resolve references that gave #REF!: start again.
            self._raw[sheet] = {}
            if raw is not None:
                self._raw[sheet][addr] = raw
            self._build()
            self._recompute(list(self._trees))
            return set(self._trees)
        cells = self._raw[sheet]
        values = self._values["sheets"][sheet]
        key = (sheet, addr)
        self._drop_formula(sheet, addr)
        values.pop(addr, None)
        if raw is None:
            cells.pop(addr, None)
        else:
            cells[addr] = raw
            if _is_formula(raw):
                self._add_formula(sheet, addr, raw)
            else:
                values[addr] = from_json(raw)
        dirty = {key} if key in self._trees else set()
        frontier = [key]
        while frontier:
            for reader in self._dependents(frontier.pop()):
                if reader not in dirty:
                    dirty.add(reader)
                    frontier.append(reader)
        self._recompute(sorted(dirty))
        return dirty

    def value(self, sheet, addr):
        """The computed cell as JSON (None for a blank)."""
        if (sheet, addr) in self._trees:
            return to_json(self._values["sheets"][sheet][addr])
        return self._raw.get(sheet, {}).get(addr)

    def computed(self):
        """The computed workbook: formulas as their values, constants as given, in input order."""
        out = {}
        for sheet, cells in self._raw.items():
            values = self._values["sheets"][sheet]
            out[sheet] = {addr: (to_json(values[addr]) if _is_formula(raw) else raw)
                          for addr, raw in cells.items()}
        return {"sheets": out}
