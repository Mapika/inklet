"""Dendrograms: the merge tree of a hierarchical clustering as elbows.

`dendrogram_layout` does the arithmetic and draws nothing. It accepts either

- a linkage matrix in the SciPy format: one row `[a, b, distance, count]`
  per merge, where `a` and `b` are leaf indices `0..n-1` or earlier merges
  `n + row`; or
- a nested sequence such as `(("a", "b"), ("c", ("d", "e")))`, whose leaves
  are anything that is not a list or tuple. A nested tree has no distances,
  so each merge is drawn one level above its tallest child (leaves are at 0).
  A node may have more than two children.

It returns the leaf order (left child first, as SciPy draws it), and one
link per merge with the positions and heights of its children. Leaves sit
at positions `0..n-1` in that order; a merge sits midway between its outer
children.

`Panel.dendrogram` draws the layout. On a band scale the leaves go to the
band positions of their labels, and the band's category order must be the
leaf order, so a heatmap beside it on the same categories lines up row for
row.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ..core import Diagram, DiagramError
from ..draw.coords import active_theme
from ..draw.path import polyline
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_LINE_KIND
from ..themes import contrast_ratio
from .scale import Band

__all__ = ["dendrogram_layout", "dendrogram", "DendrogramLayout",
           "DendrogramLink", "DENDROGRAM_ORIENTS"]

#: Accepted values of `dendrogram(orient=)`: leaves along x ("v", the tree
#: grows up the page) or along y ("h", the tree grows along x).
DENDROGRAM_ORIENTS = ("v", "h")


@dataclass(frozen=True)
class DendrogramLink:
    """One merge: the children's `(position, height)` from left to right,
    the merge `height` and its own `position`, and `members`, the leaf
    indices beneath it."""
    children: tuple[tuple[float, float], ...]
    height: float
    position: float
    members: tuple[int, ...]


@dataclass(frozen=True)
class DendrogramLayout:
    """`order` is the leaf indices from left to right, `leaves` their
    labels in that order, `links` the merges from the lowest up, and
    `height` the root's height."""
    order: tuple[int, ...]
    leaves: tuple[str, ...]
    links: tuple[DendrogramLink, ...]
    height: float


def _rows(tree) -> list:
    """`tree` as a list of rows, each a list, for an array or a sequence of
    arrays."""
    rows = tree.tolist() if hasattr(tree, "tolist") else list(tree)
    return [row.tolist() if hasattr(row, "tolist") else row for row in rows]


def _is_linkage(tree) -> bool:
    if not isinstance(tree, (list, tuple)) and not hasattr(tree, "tolist"):
        return False
    rows = _rows(tree)
    if not rows:
        return False
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != 4:
            return False
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in row):
            return False
    return True


def dendrogram_layout(tree, *, labels: Sequence | None = None) -> DendrogramLayout:
    """Leaf order and merge geometry of `tree`, without drawing.

    `tree` is a SciPy linkage matrix (rows `[a, b, distance, count]`, or an
    array with `tolist()`) or a nested sequence of leaves. `labels` names
    the leaves of a linkage, one per leaf index; the default is the index
    as text. A nested tree's leaves are their own labels, and `labels` must
    be omitted. A sequence whose items are all four numbers is read as a
    linkage, so give a nested tree's leaves as strings.
    """
    if _is_linkage(tree):
        return _from_linkage(_rows(tree), labels)
    if labels is not None:
        raise DiagramError("dendrogram labels= applies to a linkage matrix; "
                           "a nested tree's leaves are their own labels")
    if not isinstance(tree, (list, tuple)) or len(tree) < 1:
        raise DiagramError(
            "a dendrogram needs a linkage matrix or a nested sequence of leaves")
    return _from_nested(tree)


def _from_linkage(rows: list, labels) -> DendrogramLayout:
    n = len(rows) + 1
    if labels is not None and len(labels) != n:
        raise DiagramError(
            f"a linkage of {len(rows)} merges has {n} leaves, got {len(labels)} labels")
    names = [str(v) for v in labels] if labels is not None else [str(i) for i in range(n)]
    children: dict[int, tuple[int, int]] = {}
    heights: dict[int, float] = {i: 0.0 for i in range(n)}
    used: set[int] = set()
    for r, row in enumerate(rows):
        a, b, distance = row[0], row[1], float(row[2])
        if a != int(a) or b != int(b):
            raise DiagramError(f"linkage row {r} joins non-integer clusters {a!r}, {b!r}")
        a, b = int(a), int(b)
        if a == b:
            raise DiagramError(f"linkage row {r} joins cluster {a} to itself")
        for c in (a, b):
            if not 0 <= c < n + r:
                raise DiagramError(
                    f"linkage row {r} refers to cluster {c}, which does not exist yet")
            if c in used:
                raise DiagramError(f"linkage row {r} joins cluster {c} a second time")
        if math.isnan(distance) or distance < 0:
            raise DiagramError(f"linkage row {r} has distance {row[2]!r}")
        used.update((a, b))
        children[n + r] = (a, b)
        heights[n + r] = distance
    root = 2 * n - 2 if rows else 0

    order: list[int] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node < n:
            order.append(node)
        else:
            a, b = children[node]
            stack.extend((b, a))
    slot = {leaf: float(k) for k, leaf in enumerate(order)}
    position: dict[int, float] = dict(slot)
    members: dict[int, tuple[int, ...]] = {i: (i,) for i in range(n)}
    links = []
    for node in range(n, 2 * n - 1):
        a, b = children[node]
        if position[a] > position[b]:
            a, b = b, a
        position[node] = (position[a] + position[b]) / 2
        members[node] = members[a] + members[b]
        links.append(DendrogramLink(
            children=((position[a], heights[a]), (position[b], heights[b])),
            height=heights[node], position=position[node], members=members[node]))
    return DendrogramLayout(order=tuple(order), leaves=tuple(names[i] for i in order),
                            links=tuple(links), height=heights[root])


def _from_nested(tree) -> DendrogramLayout:
    leaves: list[str] = []
    links: list[DendrogramLink] = []

    def walk(node) -> tuple[float, float, tuple[int, ...]]:
        if not isinstance(node, (list, tuple)):
            leaves.append(str(node))
            index = len(leaves) - 1
            return float(index), 0.0, (index,)
        if not node:
            raise DiagramError("a dendrogram node has no children")
        parts = [walk(child) for child in node]
        if len(parts) == 1:
            return parts[0]
        height = 1.0 + max(h for _, h, _ in parts)
        position = (parts[0][0] + parts[-1][0]) / 2
        members = tuple(i for _, _, m in parts for i in m)
        links.append(DendrogramLink(children=tuple((p, h) for p, h, _ in parts),
                                    height=height, position=position, members=members))
        return position, height, members

    _, top, _ = walk(tree)
    if len(set(leaves)) != len(leaves):
        raise DiagramError("dendrogram leaf labels repeat; each leaf needs its own label")
    return DendrogramLayout(order=tuple(range(len(leaves))), leaves=tuple(leaves),
                            links=tuple(links), height=top)


def dendrogram(panel, tree, *, labels: Sequence | None = None, orient: str = "v",
               threshold: float | None = None, colors=None,
               **style) -> tuple[Diagram, DendrogramLayout, dict]:
    """The elbows of `tree` on `panel`. See `Panel.dendrogram`.

    Returns `(node, layout, note)`.
    """
    if orient not in DENDROGRAM_ORIENTS:
        raise DiagramError(f'dendrogram orient is "v" or "h", not {orient!r}')
    layout = dendrogram_layout(tree, labels=labels)
    if not layout.links:
        raise DiagramError("a dendrogram needs at least two leaves")
    along, height = (panel.x, panel.y) if orient == "v" else (panel.y, panel.x)
    if isinstance(height, Band):
        raise DiagramError("a dendrogram's height axis must be continuous")
    if isinstance(along, Band):
        domain = [str(v) for v in along.domain]
        if domain != list(layout.leaves):
            raise DiagramError(
                "the band categories must be the dendrogram's leaf order; "
                f"use {list(layout.leaves)!r} (the layout's `leaves`), "
                f"not {domain!r}")

        def spot(position: float) -> float:
            lo = along.map(along.domain[math.floor(position)])
            hi = along.map(along.domain[math.ceil(position)])
            return lo + (hi - lo) * (position - math.floor(position))
    else:
        def spot(position: float) -> float:
            return along.map(position)

    def page(position: float, h: float):
        if orient == "v":
            return (spot(position), height.map(h))
        return (height.map(h), spot(position))

    theme = active_theme()
    clusters = _clusters(layout, threshold)
    count = max(clusters.values(), default=-1) + 1
    if colors is None:
        palette = _cluster_colors(count, theme)
    elif isinstance(colors, str):
        palette = (colors,) * max(count, 1)
    else:
        palette = tuple(colors)
        if count and not palette:
            raise DiagramError("dendrogram colors= is empty")
    stroke = {"stroke": theme.ink, "stroke_width": theme.stroke,
              "fill": "none", "stroke_linejoin": "miter", "stroke_linecap": "butt"}
    items: list = []
    for k, link in enumerate(layout.links):
        paint = dict(stroke)
        if k in clusters:
            paint["stroke"] = palette[clusters[k] % len(palette)]
        paint.update(style)
        first, last = link.children[0], link.children[-1]
        items.append(polyline((page(first[0], first[1]), page(first[0], link.height),
                               page(last[0], link.height), page(last[0], last[1])),
                              kind=MARK_LINE_KIND, **paint))
        for middle in link.children[1:-1]:
            items.append(polyline((page(middle[0], middle[1]),
                                   page(middle[0], link.height)),
                                  kind=MARK_LINE_KIND, **paint))
    node = draw_place(items, origin=(0, 0), kind="dendrogram")
    groups: dict[int, list[str]] = {}
    for k, c in clusters.items():
        members = layout.links[k].members
        groups.setdefault(c, [])
        for m in members:
            name = layout.leaves[layout.order.index(m)]
            if name not in groups[c]:
                groups[c].append(name)
    note = {"order": layout.order, "leaves": layout.leaves, "height": layout.height,
            "clusters": [sorted(groups[c], key=layout.leaves.index)
                         for c in sorted(groups)]}
    node.notes["dendrogram"] = note
    return node, layout, note


def _cluster_colors(count: int, theme) -> tuple[str, ...]:
    """`count` colours from the theme's ink palette, skipping any that is
    too close to the ink the links above the threshold are drawn in."""
    out: list[str] = []
    index = 0
    while len(out) < count and index < count + 16:
        color = theme.ink_color(index)
        index += 1
        if contrast_ratio(color, theme.ink) >= 1.6:
            out.append(color)
    while len(out) < count:
        out.append(theme.ink_color(len(out)))
    return tuple(out)


def _clusters(layout: DendrogramLayout, threshold: float | None) -> dict[int, int]:
    """Link index -> cluster number for links below `threshold`.

    A cluster is a link whose height is below the threshold and whose parent
    is not; the links beneath it share its number. Clusters are numbered
    from left to right.
    """
    if threshold is None:
        return {}
    below = [k for k, link in enumerate(layout.links) if link.height < threshold]
    tops = [k for k in below
            if not any(set(layout.links[k].members) < set(layout.links[j].members)
                       for j in below)]
    tops.sort(key=lambda k: layout.links[k].position)
    out: dict[int, int] = {}
    for number, top in enumerate(tops):
        inside = set(layout.links[top].members)
        for k in below:
            if set(layout.links[k].members) <= inside:
                out[k] = number
    return out
