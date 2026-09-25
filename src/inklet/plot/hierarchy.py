"""Hierarchies: one tree input for treemaps, icicles and sunbursts.

`hierarchy` reads a tree in any of three spellings and returns the same
`Hierarchy` for each:

- a nested mapping, `{"cortex": {"L2/3": 120, "L5": {"ET": 40, "IT": 65}}}`.
  A number is a leaf's value; a mapping is a node with children; a list or
  set of names is a node whose children are leaves of value 1. A mapping with
  more than one top-level key gets an unnamed root.
- nested tuples, `("cortex", [("L2/3", 120), ("L5", [("ET", 40), ("IT", 65)])])`:
  `(name, number)` is a leaf and `(name, [children])` a node.
- a parent-child table: rows `(name, parent)` or `(name, parent, value)`, with
  `parent` None or `""` for the root. A sequence whose rows all have a string
  (or None) in second place is read as a table. A leaf without a value counts
  as 1.

A node's value is the sum of its children's; a value given for a node that
has children is ignored, so the areas always add up. The layouts here draw
nothing: `treemap_layout` returns squarified rectangles and
`partition_layout` the fractions an icicle or a sunburst is built from.
`Panel.treemap`, `Panel.icicle` and `Panel.sunburst` draw them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from numbers import Real
from typing import Iterator, Mapping, Sequence

from ..core import DiagramError, Rect

__all__ = ["Hierarchy", "HierarchyNode", "hierarchy", "treemap_layout",
           "partition_layout", "PartitionCell"]


@dataclass(eq=False)
class HierarchyNode:
    """One node: `name`, `value` (a leaf's own, or the sum of its children),
    `children` in input order, `depth` (the root is 0) and `path`, the names
    from the root's first child down to this node."""
    name: str
    value: float
    children: list["HierarchyNode"] = field(default_factory=list)
    depth: int = 0
    path: tuple[str, ...] = ()
    parent: "HierarchyNode | None" = field(default=None, repr=False)

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def walk(self) -> Iterator["HierarchyNode"]:
        """This node and every node below it, depth first, in input order."""
        yield self
        for child in self.children:
            yield from child.walk()

    def leaves(self) -> list["HierarchyNode"]:
        return [n for n in self.walk() if n.is_leaf]

    @property
    def branch(self) -> "HierarchyNode":
        """The root's child this node descends from (itself at depth 1)."""
        node = self
        while node.parent is not None and node.parent.parent is not None:
            node = node.parent
        return node


@dataclass(frozen=True)
class Hierarchy:
    """A read tree: `root`, and `height`, the depth of the deepest leaf."""
    root: HierarchyNode
    height: int

    def nodes(self, depth: int | None = None) -> list[HierarchyNode]:
        """Every node, or those at one `depth`, depth first."""
        return [n for n in self.root.walk() if depth is None or n.depth == depth]

    def find(self, key) -> HierarchyNode:
        """A node by name, or by path (a tuple of names from depth 1)."""
        for node in self.root.walk():
            if (isinstance(key, tuple) and node.path == key) or node.name == key:
                return node
        raise KeyError(key)

    def matches(self, keys) -> set[int]:
        """The ids of the nodes named or pathed by any of `keys`."""
        if keys is None:
            return set()
        if isinstance(keys, (str, tuple)):
            keys = [keys]
        wanted = list(keys)
        out = set()
        for node in self.root.walk():
            if node.name in wanted or node.path in wanted:
                out.add(id(node))
        return out


def _number(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise DiagramError(f"hierarchy value for {where!r} must be a number, got {value!r}")
    value = float(value)
    if math.isnan(value) or value < 0 or math.isinf(value):
        raise DiagramError(f"hierarchy value for {where!r} must be zero or more, got {value!r}")
    return value


def _is_table(data) -> bool:
    if isinstance(data, (str, bytes, Mapping)) or not isinstance(data, Sequence):
        return False
    rows = list(data)
    if not rows:
        return False
    return all(isinstance(r, (tuple, list)) and len(r) in (2, 3)
               and (r[1] is None or isinstance(r[1], str)) for r in rows)


def _from_mapping(name: str, value) -> HierarchyNode:
    if isinstance(value, Mapping):
        return HierarchyNode(str(name), 0.0,
                             [_from_mapping(k, v) for k, v in value.items()])
    if isinstance(value, (set, frozenset)):
        return HierarchyNode(str(name), 0.0,
                             [HierarchyNode(str(v), 1.0) for v in sorted(value, key=str)])
    if isinstance(value, (list, tuple)) and all(isinstance(v, str) for v in value):
        return HierarchyNode(str(name), 0.0, [HierarchyNode(v, 1.0) for v in value])
    if isinstance(value, (list, tuple)):
        return HierarchyNode(str(name), 0.0, [_from_tuple(v) for v in value])
    return HierarchyNode(str(name), _number(value, str(name)))


def _from_tuple(item) -> HierarchyNode:
    if isinstance(item, str):
        return HierarchyNode(item, 1.0)
    if not isinstance(item, (tuple, list)) or len(item) != 2:
        raise DiagramError(
            f"a hierarchy node is (name, value) or (name, [children]), not {item!r}")
    name, rest = item
    if isinstance(rest, Mapping) or (isinstance(rest, (list, tuple, set, frozenset))):
        return _from_mapping(name, rest)
    return HierarchyNode(str(name), _number(rest, str(name)))


def _from_table(rows) -> HierarchyNode:
    nodes: dict[str, HierarchyNode] = {}
    parents: dict[str, str | None] = {}
    order: list[str] = []
    for row in rows:
        name, parent = str(row[0]), row[1]
        if name in nodes:
            raise DiagramError(f"hierarchy table names {name!r} twice")
        value = _number(row[2], name) if len(row) == 3 else None
        nodes[name] = HierarchyNode(name, 1.0 if value is None else value)
        parents[name] = None if parent in (None, "") else str(parent)
        order.append(name)
    roots = [n for n in order if parents[n] is None]
    for name in order:
        parent = parents[name]
        if parent is None:
            continue
        if parent not in nodes:
            # A parent named only as a parent is an internal node.
            nodes[parent] = HierarchyNode(parent, 0.0)
            parents[parent] = None
            order.append(parent)
            roots.append(parent)
        nodes[parent].children.append(nodes[name])
    # Cycles leave nodes unreachable from every root.
    reach = set()
    stack = list(roots)
    while stack:
        n = stack.pop()
        if n in reach:
            raise DiagramError(f"hierarchy table has a cycle through {n!r}")
        reach.add(n)
        stack.extend(c.name for c in nodes[n].children)
    if len(reach) != len(nodes):
        missing = sorted(set(nodes) - reach)
        raise DiagramError(f"hierarchy table has a cycle through {missing[0]!r}")
    if len(roots) == 1:
        return nodes[roots[0]]
    return HierarchyNode("", 0.0, [nodes[r] for r in roots])


def _finish(node: HierarchyNode, depth: int, path: tuple[str, ...],
            parent: HierarchyNode | None) -> int:
    node.depth = depth
    node.path = path
    node.parent = parent
    if not node.children:
        return depth
    deepest = max(_finish(c, depth + 1, path + (c.name,), node) for c in node.children)
    node.value = sum(c.value for c in node.children)
    return deepest


def hierarchy(data) -> Hierarchy:
    """Read a tree from a nested mapping, nested tuples or a parent-child
    table; see the module docstring. A `Hierarchy` is returned unchanged."""
    if isinstance(data, Hierarchy):
        return data
    if isinstance(data, Mapping):
        if len(data) == 1:
            (name, value), = data.items()
            root = _from_mapping(name, value)
        else:
            root = _from_mapping("", data)
    elif _is_table(data):
        root = _from_table(data)
    elif isinstance(data, tuple) and len(data) == 2 and isinstance(data[0], str):
        root = _from_tuple(data)
    elif isinstance(data, (list, tuple)):
        root = HierarchyNode("", 0.0, [_from_tuple(v) for v in data])
    else:
        raise DiagramError(
            "hierarchy data is a nested mapping, (name, children) tuples or "
            f"a (name, parent[, value]) table, not {type(data).__name__}")
    height = _finish(root, 0, (), None)
    if root.value <= 0:
        raise DiagramError("hierarchy has no positive values to draw")
    return Hierarchy(root=root, height=height)


# -- squarified treemap --------------------------------------------------------


def _worst(row: Sequence[float], short: float) -> float:
    total = sum(row)
    if total <= 0 or short <= 0:
        return math.inf
    return max(max(row) * short * short / (total * total),
               total * total / (short * short * min(row)))


def squarify(values: Sequence[float], box: Rect) -> list[Rect]:
    """Rectangles tiling `box` with areas proportional to `values`, in the
    order given (Bruls, Huizing and van Wijk's squarified layout). Values
    should be sorted largest first for squarest cells; zeros get empty boxes."""
    total = sum(values)
    out: list[Rect | None] = [None] * len(values)
    live = [(i, v) for i, v in enumerate(values) if v > 0]
    if total <= 0 or box.width <= 0 or box.height <= 0:
        return [Rect(box.x0, box.y0, box.x0, box.y0) for _ in values]
    scale = box.width * box.height / total
    x, y, w, h = box.x0, box.y0, box.width, box.height
    k = 0
    while k < len(live):
        short = min(w, h)
        row = [live[k][1] * scale]
        j = k + 1
        while j < len(live):
            trial = row + [live[j][1] * scale]
            if _worst(trial, short) > _worst(row, short):
                break
            row = trial
            j += 1
        s = sum(row)
        last = j == len(live)
        if w >= h:
            cw = w if last else s / h
            yy = y
            for n, (i, _) in enumerate(live[k:j]):
                hh = h - (yy - y) if n == j - k - 1 else row[n] / cw
                out[i] = Rect(x, yy, x + cw, yy + hh)
                yy += hh
            x += cw
            w -= cw
        else:
            rh = h if last else s / w
            xx = x
            for n, (i, _) in enumerate(live[k:j]):
                ww = w - (xx - x) if n == j - k - 1 else row[n] / rh
                out[i] = Rect(xx, y, xx + ww, y + rh)
                xx += ww
            y += rh
            h -= rh
        k = j
    return [r if r is not None else Rect(box.x0, box.y0, box.x0, box.y0) for r in out]


def treemap_layout(data, box: Rect, *, padding: float = 0.0, header: float = 0.0,
                   sort: bool = True) -> list[tuple[HierarchyNode, Rect]]:
    """Every node below the root and its rectangle inside `box`.

    Children are laid out inside their parent's rectangle shrunk by
    `padding` on each side, and by `header` more at the top for a node that
    has children (room for its name). `sort=True` orders siblings largest
    first, which is what makes the squarified cells square; with `False`
    the input order is kept. Parents come before their children.
    """
    tree = hierarchy(data)
    out: list[tuple[HierarchyNode, Rect]] = []

    def inner(node: HierarchyNode, rect: Rect, top: bool) -> Rect:
        if top:
            return rect
        pad = min(padding, rect.width / 4, rect.height / 4)
        head = min(header, max(0.0, rect.height - 2 * pad) / 2) if node.children else 0.0
        return Rect(rect.x0 + pad, rect.y0 + pad + head, rect.x1 - pad, rect.y1 - pad)

    def place(node: HierarchyNode, rect: Rect, top: bool) -> None:
        kids = list(node.children)
        if sort:
            kids.sort(key=lambda c: -c.value)
        room = inner(node, rect, top)
        for child, cell in zip(kids, squarify([c.value for c in kids], room)):
            out.append((child, cell))
            if child.children:
                place(child, cell, False)

    place(tree.root, box, True)
    return out


# -- partition (icicle and sunburst) ---------------------------------------------


@dataclass(frozen=True)
class PartitionCell:
    """One node of a partition: its `depth` and the fraction of the whole,
    `start` to `end`, that it spans along the breadth axis."""
    node: HierarchyNode
    depth: int
    start: float
    end: float


def partition_layout(data, *, sort: bool = False) -> list[PartitionCell]:
    """Every node including the root, with the span of the breadth axis it
    covers as fractions of the root's value. Children split their parent's
    span in proportion to their values, in input order unless `sort=True`
    (largest first). Parents come before their children."""
    tree = hierarchy(data)
    out: list[PartitionCell] = []

    def walk(node: HierarchyNode, start: float) -> None:
        span = node.value / tree.root.value
        out.append(PartitionCell(node, node.depth, start, start + span))
        kids = sorted(node.children, key=lambda c: -c.value) if sort else node.children
        at = start
        for child in kids:
            walk(child, at)
            at += child.value / tree.root.value

    walk(tree.root, 0.0)
    return out
