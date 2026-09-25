"""Treemaps, icicles and sunbursts: a hierarchy drawn into a panel's area.

Each function here backs a `Panel` method and fills the plot area with the
tree, in millimetres; the panel's scales are not consulted. They share the
input of `inklet.plot.hierarchy` and one colouring rule (see `_Paint`).
"""

from __future__ import annotations

import math
from typing import Mapping, Sequence

from ..core import Diagram, DiagramError, Rect, Vec2, mm
from ..diagnostics.abut import abutting
from ..draw.coords import active_theme
from ..draw.path import path, polygon, straight_cubic
from ..draw.place import place as draw_place
from ..draw.shapes import MARK_KIND, arc_cubics
from ..themes import contrast_ratio
from ..themes.color import mix
from .axis import text_node
from .hierarchy import Hierarchy, HierarchyNode, hierarchy, partition_layout, treemap_layout

__all__ = ["treemap", "icicle", "sunburst", "ICICLE_ORIENTS", "ICICLE_LABELS"]

ICICLE_ORIENTS = ("h", "v")
ICICLE_LABELS = ("fit", "highlight")

#: How far a node's fill is blended towards paper per level below the first,
#: and the most it ever is, when colours come from the branch palette.
_DEPTH_TINT = 0.16
_DEPTH_TINT_MAX = 0.56

#: The pale fill of the nodes that are not highlighted, as a blend of the
#: first palette colour towards paper.
_UNLIT_TINT = 0.7

#: Link fans between icicle levels, as a blend of muted towards paper.
_LINK_TINT = 0.84

#: The most of a column's length node spacing may take.
_SPACING_SHARE = 0.3

LABEL_KIND = "label"


class _Paint:
    """Fill colours for nodes.

    Highlighted nodes (`highlight=` names or paths) get `highlight_color`.
    Otherwise `colors=` decides: a single colour for every node; a mapping of
    node name to colour, inherited by the node's descendants; or a sequence
    of colours, one per branch (child of the root). Without `colors`, each
    branch takes the theme's categorical colour and deeper levels are blended
    towards paper, except when a highlight is given: then every other node is
    one pale colour, so the highlighted ones are the only thing that stands
    out.
    """

    def __init__(self, tree: Hierarchy, colors, highlight, highlight_color, depth_tint):
        theme = active_theme()
        self.theme = theme
        self.tree = tree
        self.lit = tree.matches(highlight)
        if highlight is not None and not self.lit:
            raise DiagramError(f"highlight= names no node of the hierarchy: {highlight!r}")
        self.lit_color = highlight_color or "#c9352b"
        self.colors = colors
        self.branches = {id(c): k for k, c in enumerate(tree.root.children)}
        self.palette = branch_colors(max(1, len(tree.root.children)), theme)
        self.pale = mix("#4a90c2", theme.paper, _UNLIT_TINT)
        self.highlighting = highlight is not None
        self.depth_tint = depth_tint

    def __call__(self, node: HierarchyNode) -> str:
        if id(node) in self.lit:
            return self.lit_color
        colors = self.colors
        if isinstance(colors, str):
            return colors
        if isinstance(colors, Mapping):
            n = node
            while n is not None:
                if n.name in colors:
                    return str(colors[n.name])
                if n.path in colors:
                    return str(colors[n.path])
                n = n.parent
            return self.pale if self.highlighting else mix(
                self.theme.muted, self.theme.paper, _UNLIT_TINT)
        if self.highlighting and colors is None:
            return self.pale
        if node.parent is None:
            return mix(self.theme.muted, self.theme.paper, _UNLIT_TINT)
        k = self.branches.get(id(node.branch), 0)
        if colors is not None:
            palette = list(colors)
            if not palette:
                raise DiagramError("colors= is empty")
            base = str(palette[k % len(palette)])
        else:
            base = self.palette[k % len(self.palette)]
        if not self.depth_tint:
            return base
        return mix(base, self.theme.paper,
                   min(_DEPTH_TINT_MAX, _DEPTH_TINT * (node.depth - 1)))


def _text_on(fill: str, theme) -> str:
    """Ink, or paper when the fill is too dark for ink to be read on it."""
    ink, paper = contrast_ratio(theme.ink, fill), contrast_ratio(theme.paper, fill)
    best = theme.ink if ink >= min(4.5, paper) else theme.paper
    if max(ink, paper) >= 4.5:
        return best
    from ..themes import readable
    return readable(best, fill, 4.5)


def branch_colors(count: int, theme) -> list[str]:
    """`count` fills from the theme's palette, skipping any too close to the
    ink (Okabe-Ito opens with black, which reads as a hole in an area chart)."""
    out: list[str] = []
    index = 0
    while len(out) < count and index < count + 16:
        color = theme.color(index)
        index += 1
        if contrast_ratio(color, theme.ink) >= 1.6:
            out.append(color)
    while len(out) < count:
        out.append(theme.color(len(out)))
    return out


def _label(text: str, size: float, fill: str | None, theme, align: str = "center",
           **style) -> Diagram:
    paint = {} if fill is None else {"text_fill": _text_on(fill, theme)}
    paint.update(style)
    return text_node(text, size, LABEL_KIND, align=align, markup=False, **paint)


def _rect_node(rect: Rect, **style) -> Diagram:
    return polygon(rect.corners, kind=MARK_KIND, **style)


def _format(values, value: float) -> str | None:
    if values is None or values is False:
        return None
    if values is True:
        return f"{value:g}"
    if callable(values):
        return str(values(value))
    return str(values).format(value)


# -- treemap -------------------------------------------------------------------


def treemap(panel, data, *, colors=None, highlight=None, highlight_color=None,
            padding: float | str | None = None, header: bool | None = None,
            labels: bool = True, values=None, sort: bool = True,
            size: float | str | None = None, **style) -> tuple[Diagram, dict]:
    """A squarified treemap filling `panel`'s plot area. See `Panel.treemap`."""
    theme = active_theme()
    tree = hierarchy(data)
    area = panel.area
    pad = (theme.gap("xs") * 0.6 if tree.height > 1 else 0.0) if padding is None else mm(padding)
    font = theme.font_size_small if size is None else mm(size)
    head = (tree.height > 1) if header is None else bool(header)
    head_h = font * 1.35 if head else 0.0
    cells = treemap_layout(tree, area, padding=pad, header=head_h, sort=sort)
    paint = _Paint(tree, colors, highlight, highlight_color, depth_tint=False)
    edge = {"stroke": theme.paper, "stroke_width": max(theme.stroke, 0.25),
            "stroke_linejoin": "miter"}
    edge.update(style)
    shapes: list = []
    texts: list = []
    inset = theme.gap("xs") * 0.8
    for node, rect in cells:
        if rect.width <= 1e-9 or rect.height <= 1e-9:
            continue
        fill = paint(node)
        if node.children:
            # A group is a pale plate its children sit on, with its name in
            # the header strip.
            plate = mix(fill, theme.paper, 0.8) if id(node) not in paint.lit else fill
            shapes.append(_rect_node(rect, fill=plate, **edge))
            if head and labels:
                name = _label(node.name, font, plate, theme, font_weight="bold")
                box = name.bbox
                if box.width <= rect.width - 2 * inset and box.height <= head_h + pad:
                    texts.append((Vec2(rect.x0 + inset, rect.y0 + pad + head_h / 2), name))
            continue
        shapes.append(_rect_node(rect, fill=fill, **edge))
        if not labels:
            continue
        text = node.name
        extra = _format(values, node.value)
        if extra:
            text = f"{text}\n{extra}"
        name = _label(text, font, fill, theme, align="left")
        box = name.bbox
        if box.width > rect.width - 2 * inset or box.height > rect.height - 2 * inset:
            name = _label(node.name, font, fill, theme)
            box = name.bbox
            if box.width > rect.width - 2 * inset or box.height > rect.height - 2 * inset:
                continue
        texts.append((Vec2(rect.x0 + inset, rect.y0 + inset + box.height / 2), name))
    # Names are left-aligned: a leaf's in its top-left corner, a group's on
    # its header strip.
    node = draw_place(shapes + _left(texts), origin=(0, 0), kind=abutting("treemap"))
    note = {"cells": [(n.path, round(r.width * r.height, 6)) for n, r in cells],
            "height": tree.height, "total": tree.root.value,
            "highlighted": sorted(n.path for n in tree.root.walk() if id(n) in paint.lit)}
    node.notes["treemap"] = note
    return node, note


def _left(texts) -> list:
    """Labels whose left edge (and vertical centre) is given, placed."""
    out = []
    for p, t in texts:
        box = t.bbox
        out.append(draw_place([(Vec2(p.x + box.width / 2, p.y), t)], origin=(0, 0)))
    return out


# -- icicle --------------------------------------------------------------------


def _spread(wanted: list[float], height: float, lo: float, hi: float) -> list[float]:
    """Centres as close to `wanted` as possible with `height` between
    neighbours, kept inside [lo, hi] when there is room."""
    if not wanted:
        return []
    order = sorted(range(len(wanted)), key=lambda i: wanted[i])
    pos = [wanted[i] for i in order]
    for _ in range(200):
        moved = False
        for k in range(1, len(pos)):
            gap = pos[k] - pos[k - 1]
            if gap < height - 1e-9:
                push = (height - gap) / 2
                pos[k - 1] -= push
                pos[k] += push
                moved = True
        if pos[0] < lo:
            shift = lo - pos[0]
            pos = [p + shift for p in pos]
        if pos[-1] > hi and pos[0] - (pos[-1] - hi) >= lo - 1e-9:
            shift = pos[-1] - hi
            pos = [p - shift for p in pos]
        if not moved:
            break
    out = [0.0] * len(wanted)
    for i, p in zip(order, pos):
        out[i] = p
    return out


def icicle(panel, data, *, orient: str = "h", root: bool | None = None,
           gap: float | str | None = None, spacing: float | str | None = None,
           links: bool | None = None, colors=None, highlight=None,
           highlight_color=None, labels="fit", levels: bool = False,
           counts: bool = False, sort: bool = False, size: float | str | None = None,
           **style) -> tuple[Diagram, dict]:
    """An icicle (partition) chart in `panel`'s plot area. See `Panel.icicle`."""
    if orient not in ICICLE_ORIENTS:
        raise DiagramError(f'icicle orient is "h" or "v", not {orient!r}')
    if labels not in (False, None, "fit", "highlight") and isinstance(labels, str):
        raise DiagramError(f'icicle labels is "fit", "highlight", False or a list of names, not {labels!r}')
    theme = active_theme()
    tree = hierarchy(data)
    with_root = bool(tree.root.name) if root is None else bool(root)
    first = 0 if with_root else 1
    columns = tree.height - first + 1
    if columns < 1:
        raise DiagramError("icicle needs a hierarchy with at least one level below the root")
    area = panel.area
    depth_len = area.width if orient == "h" else area.height
    breadth = area.height if orient == "h" else area.width
    between = (0.0 if gap is None else mm(gap))
    if between * (columns - 1) >= depth_len:
        raise DiagramError("icicle gap= leaves no room for the levels")
    band = (depth_len - between * (columns - 1)) / columns
    fan = (between > 0) if links is None else bool(links)
    font = theme.font_size_small if size is None else mm(size)
    cells = [c for c in partition_layout(tree, sort=sort) if c.depth >= first]
    by_depth: dict[int, list] = {}
    for c in cells:
        by_depth.setdefault(c.depth, []).append(c)
    base_spacing = (theme.hairline * 3 if between > 0 else 0.0) if spacing is None else mm(spacing)
    # Each level: its own spacing, so a deep level of many nodes still gets
    # its values drawn in proportion.
    spans: dict[int, tuple[float, float]] = {}
    for depth, row in by_depth.items():
        live = [c for c in row if c.end - c.start > 0]
        count = len(live)
        space = 0.0 if count < 2 else min(base_spacing,
                                            _SPACING_SHARE * breadth / (count - 1))
        usable = breadth - space * max(0, count - 1)
        at = 0.0
        for c in row:
            length = (c.end - c.start) * usable
            spans[id(c.node)] = (at, at + length)
            if length > 0:
                at += length + space
    paint = _Paint(tree, colors, highlight, highlight_color, depth_tint=True)

    def box(depth: int, lo: float, hi: float) -> Rect:
        d0 = (depth - first) * (band + between)
        if orient == "h":
            return Rect(area.x0 + d0, area.y0 + lo, area.x0 + d0 + band, area.y0 + hi)
        return Rect(area.x0 + lo, area.y0 + d0, area.x0 + hi, area.y0 + d0 + band)

    edge = {"stroke": theme.paper if between == 0 else "none",
            "stroke_width": max(theme.stroke, 0.25)}
    edge.update(style)
    fans: list = []
    shapes: list = []
    texts: list = []
    inset = theme.gap("xs") * 0.6
    link_fill = mix(theme.muted, theme.paper, _LINK_TINT)
    for c in cells:
        lo, hi = spans[id(c.node)]
        if hi - lo <= 1e-9:
            continue
        rect = box(c.depth, lo, hi)
        fill = paint(c.node)
        shapes.append(_rect_node(rect, fill=fill, **edge))
        if fan and c.node.parent is not None and c.depth > first:
            plo, phi = spans[id(c.node.parent)]
            parent_total = c.node.parent.value or 1.0
            before = 0.0
            for sib in c.node.parent.children:
                if sib is c.node:
                    break
                before += sib.value
            a = plo + (phi - plo) * before / parent_total
            b = plo + (phi - plo) * (before + c.node.value) / parent_total
            prect = box(c.depth - 1, a, b)
            if orient == "h":
                pts = [(prect.x1, prect.y0), (rect.x0, rect.y0),
                       (rect.x0, rect.y1), (prect.x1, prect.y1)]
            else:
                pts = [(prect.x0, prect.y1), (rect.x0, rect.y0),
                       (rect.x1, rect.y0), (prect.x1, prect.y1)]
            fans.append(polygon(pts, kind=MARK_KIND, fill=link_fill, stroke=theme.paper,
                                stroke_width=theme.hairline))
        if labels == "fit":
            name = _label(c.node.name, font, fill, theme)
            b = name.bbox
            if orient == "h":
                fits = b.width <= rect.width - 2 * inset and b.height <= rect.height - inset
            else:
                fits = b.width <= rect.width - 2 * inset and b.height <= rect.height - inset
            if fits and c.node.name:
                texts.append(draw_place([(rect.center, name)], origin=(0, 0)))
    outside: list = []
    if labels == "highlight" or (labels not in (None, False, "fit")):
        wanted_nodes = ([n for n in tree.root.walk() if id(n) in paint.lit]
                        if labels == "highlight"
                        else [n for n in tree.root.walk() if id(n) in tree.matches(list(labels))])
        # The deepest drawn cell of each named node's subtree is where its
        # label points from: the far end of the chart.
        items = []
        for n in wanted_nodes:
            lo, hi = spans[id(n)]
            items.append((n, (lo + hi) / 2))
        heights = []
        texts_out = []
        for n, _ in items:
            fill = paint(n) if id(n) in paint.lit else None
            t = _label(n.name, font, None, theme,
                       **({"text_fill": _readable_on_paper(fill, theme)} if fill else {}))
            texts_out.append(t)
            heights.append(t.bbox.height if orient == "h" else t.bbox.width)
        step = max(heights, default=0.0) * 1.02
        centres = _spread([m for _, m in items], step, 0.0, breadth)
        far = area.x1 if orient == "h" else area.y1
        clear = theme.gap("xs")
        for (n, m), at, t in zip(items, centres, texts_out):
            deep = box(n.depth, *spans[id(n)])
            start = deep.x1 if orient == "h" else deep.y1
            color = t.style.text_fill if t.style and t.style.text_fill else theme.ink
            if orient == "h":
                tick = [(start, area.y0 + m), (far + clear * 0.6, area.y0 + m),
                        (far + clear * 1.6, area.y0 + at)]
                outside.append(path(tick, kind="mark-line", stroke=color,
                                    stroke_width=theme.hairline, fill="none"))
                b = t.bbox
                outside.append(draw_place([(Vec2(far + clear * 2 + b.width / 2, area.y0 + at), t)],
                                          origin=(0, 0)))
            else:
                b = t.bbox
                outside.append(draw_place([(Vec2(area.x0 + at, far + clear + b.height / 2), t)],
                                          origin=(0, 0)))
    furniture: list = []
    drawn_depths = sorted(by_depth)
    if levels:
        for k, depth in enumerate(drawn_depths):
            r = box(depth, 0.0, breadth)
            t = text_node(str(k), font, LABEL_KIND, markup=False)
            if orient == "h":
                at = Vec2(r.center.x, area.y0 - theme.gap("xs") - t.bbox.height / 2)
            else:
                at = Vec2(area.x0 - theme.gap("xs") - t.bbox.width / 2, r.center.y)
            furniture.append(draw_place([(at, t)], origin=(0, 0)))
    if counts:
        for depth in drawn_depths:
            row = [c for c in by_depth[depth] if c.end - c.start > 0]
            r = box(depth, 0.0, breadth)
            lines = [(str(len(row)), theme.ink)]
            if paint.lit:
                lit = sum(1 for c in row if id(c.node) in paint.lit)
                lines.insert(0, (str(lit), _readable_on_paper(paint.lit_color, theme)))
            y = area.y1 + theme.gap("xs")
            for text, ink in lines:
                t = text_node(text, font, LABEL_KIND, markup=False, text_fill=ink)
                if orient == "h":
                    at = Vec2(r.center.x, y + t.bbox.height / 2)
                    y += t.bbox.height
                else:
                    at = Vec2(area.x1 + theme.gap("xs") + t.bbox.width / 2, r.center.y)
                furniture.append(draw_place([(at, t)], origin=(0, 0)))
    node = draw_place(fans + shapes + texts, origin=(0, 0), kind=abutting("icicle"))
    extra = draw_place(outside + furniture, origin=(0, 0)) if outside or furniture else None
    note = {"levels": [len([c for c in by_depth[d] if c.end - c.start > 0]) for d in drawn_depths],
            "highlighted": [sum(1 for c in by_depth[d] if id(c.node) in paint.lit)
                            for d in drawn_depths],
            "spans": {c.node.path: spans[id(c.node)] for c in cells},
            "band": band, "root": with_root}
    node.notes["icicle"] = note
    if extra is not None:
        group = draw_place([node, extra], origin=(0, 0))
        group.notes["icicle"] = note
        return group, note
    return node, note


def _readable_on_paper(color: str, theme) -> str:
    from ..themes import readable
    return readable(color, theme.paper, 4.5)


# -- sunburst ------------------------------------------------------------------


def _annulus(centre: Vec2, r0: float, r1: float, a0: float, a1: float, **style) -> Diagram:
    """The ring segment between radii r0 < r1 and angles a0 < a1 (degrees,
    clockwise from east), as one closed path."""
    outer = list(arc_cubics(centre, r1, a0, a1))
    if r0 > 1e-9:
        inner = arc_cubics(centre, r0, a1, a0)
        chain = outer + [straight_cubic(outer[-1][3], inner[0][0])] + list(inner)
    else:
        chain = outer + [straight_cubic(outer[-1][3], centre)]
    chain.append(straight_cubic(chain[-1][3], chain[0][0]))
    return path(curves=tuple(chain), closed=True, kind=MARK_KIND, **style)


def _inside_annulus(point: Vec2, centre: Vec2, r0: float, r1: float,
                    a0: float, a1: float) -> bool:
    d = point - centre
    r = math.hypot(d.x, d.y)
    if not r0 <= r <= r1:
        return False
    if a1 - a0 >= 360 - 1e-9:
        return True
    angle = math.degrees(math.atan2(d.y, d.x))
    while angle < a0:
        angle += 360
    while angle >= a0 + 360:
        angle -= 360
    return angle <= a1


def sunburst(panel, data, *, inner: float = 0.3, start: float = -90.0,
             colors=None, highlight=None, highlight_color=None, labels: bool = True,
             center: str | None = None, sort: bool = False,
             size: float | str | None = None, **style) -> tuple[Diagram, dict]:
    """A sunburst in `panel`'s plot area. See `Panel.sunburst`."""
    theme = active_theme()
    tree = hierarchy(data)
    if not 0 <= inner < 1:
        raise DiagramError(f"sunburst inner= is a fraction from 0 to under 1, got {inner!r}")
    area = panel.area
    centre = area.center
    radius = min(area.width, area.height) / 2
    hole = inner * radius
    ring = (radius - hole) / max(1, tree.height)
    font = theme.font_size_small if size is None else mm(size)
    paint = _Paint(tree, colors, highlight, highlight_color, depth_tint=True)
    edge = {"stroke": theme.paper, "stroke_width": max(theme.stroke, 0.25),
            "stroke_linejoin": "round"}
    edge.update(style)
    shapes: list = []
    texts: list = []
    for c in partition_layout(tree, sort=sort):
        if c.depth == 0 or c.end - c.start <= 1e-12:
            continue
        r0 = hole + (c.depth - 1) * ring
        r1 = r0 + ring
        a0 = start + 360.0 * c.start
        a1 = start + 360.0 * c.end
        fill = paint(c.node)
        shapes.append(_annulus(centre, r0, r1, a0, a1, fill=fill, **edge))
        if not labels or not c.node.name:
            continue
        mid = math.radians((a0 + a1) / 2)
        rm = (r0 + r1) / 2
        at = centre + Vec2(math.cos(mid), math.sin(mid)) * rm
        name = _label(c.node.name, font, fill, theme)
        b = name.bbox
        pad = 0.3
        corners = [at + Vec2(sx * (b.width / 2 + pad), sy * (b.height / 2 + pad) * 0.8)
                   for sx in (-1, 1) for sy in (-1, 1)]
        if all(_inside_annulus(p, centre, r0, r1, a0, a1) for p in corners):
            texts.append(draw_place([(at, name)], origin=(0, 0)))
    if center is None and tree.root.name:
        center = tree.root.name
    if center and hole > 0:
        t = text_node(center, font, LABEL_KIND, markup=False)
        if t.bbox.width <= 2 * hole - 0.6:
            texts.append(draw_place([(centre, t)], origin=(0, 0)))
    node = draw_place(shapes + texts, origin=(0, 0), kind=abutting("sunburst"))
    note = {"radius": radius, "hole": hole, "ring": ring, "height": tree.height,
            "angles": [(c.node.path, 360.0 * (c.end - c.start))
                       for c in partition_layout(tree, sort=sort) if c.depth > 0]}
    node.notes["sunburst"] = note
    return node, note
