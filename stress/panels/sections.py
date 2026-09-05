"""Panels d, e, f and q of the stress figure.

Four modalities that share one property: none of them is a call `inklet.plot`
already knows how to make. A coronal section is nested filled regions plus a
*hatch*, which is a fill pattern the library has no concept of; a protocol
timeline is bars whose labels sometimes do not fit inside them; a stack of
ΔF/F traces has no y spine at all, only a scale bar; and a receptive field is
a set of iso-contours that have to be extracted from a field before anything
can be drawn.

The two algorithms are real. `_hatch` clips parallel lines against the region
boundary with an even-odd scanline, so a hatch line crossing the cortical
ribbon four times is drawn as four spans and the white matter in the middle
stays clear. `_iso_contours` is marching squares with the bilinear saddle value
disambiguating the two ambiguous cases, stitched into chains and simplified
before it is smoothed. Neither is faked with concentric ellipses.

Every panel is a pure function of its width. Data is either closed form or
comes off a `random.Random` with a stated seed, so two runs emit the same file.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Iterable, Sequence

import inklet
from inklet import Diagram, Vec2

__all__ = ["panel_d", "panel_e", "panel_f", "panel_q"]

#: Two-column page, 183mm with a 10mm gutter.
CONTENT_WIDTH = 84.0

_EPS = 1e-9


# -- colour ---------------------------------------------------------------


def _tint(color: str, amount: float) -> str:
    """`color` weakened towards the paper, in CIELAB.

    Not `opacity`: `Style.opacity` is a group attribute covering stroke and
    fill together, so a region with a translucent fill and a solid outline
    would have to be drawn twice, as two paths carrying the same 200 points. A
    tint is one path, and it is also what a printer would rather be given.
    """
    return inklet.ramp([inklet.current_theme().paper, color])(amount)


def _shade(color: str, amount: float) -> str:
    """`color` darkened towards the ink, for the outline of a region filled
    with `_tint(color, ...)`."""
    return inklet.ramp([color, inklet.current_theme().ink])(amount)


def _readable(color: str, min_ratio: float = 4.5) -> str:
    """`color` darkened until small text in it clears WCAG AA on the paper.

    `Theme.ink_color` does this, but only for a palette *index* and only to
    3:1, which is the threshold for a line rather than for type. A contour
    label written in its contour's own colour needs the text threshold.
    """
    theme = inklet.current_theme()
    towards_ink = inklet.ramp([color, theme.ink])
    for step in range(21):
        candidate = towards_ink(step / 20)
        if inklet.contrast_ratio(candidate, theme.paper) >= min_ratio:
            return candidate
    return theme.ink


# -- geometry -------------------------------------------------------------


def _straight(p0: Vec2, p3: Vec2) -> tuple[Vec2, Vec2, Vec2, Vec2]:
    """A cubic that is its own chord. `inklet.path(curves=...)` insists the chain
    covers the whole path, so the straight runs between two corner arcs have to
    be spelled out as cubics too."""
    step = (p3 - p0) * (1.0 / 3.0)
    return (p0, p0 + step, p0 + step * 2, p3)


def _rounded_rect(x0: float, y0: float, x1: float, y1: float,
                  radius: float, **style) -> Diagram:
    """A rounded rectangle from two corners, as real arcs.

    `Style.corner_radius` only reaches a `RectPrim`, and nothing public builds
    one at a size the caller chooses -- `inklet.box` sizes itself to its contents.
    A Gantt bar is a rectangle whose width *is* the data, so it is built here.
    """
    r = max(0.0, min(radius, (x1 - x0) / 2, (y1 - y0) / 2))
    if r <= 1e-4:
        return inklet.polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1)), **style)
    chain: list[tuple[Vec2, Vec2, Vec2, Vec2]] = []
    # Angles run from east, clockwise on the page: 270 is north, 90 is south.
    corners = ((Vec2(x1 - r, y0 + r), 270.0, 360.0),
               (Vec2(x1 - r, y1 - r), 0.0, 90.0),
               (Vec2(x0 + r, y1 - r), 90.0, 180.0),
               (Vec2(x0 + r, y0 + r), 180.0, 270.0))
    for centre, start, end in corners:
        quarter = inklet.draw.arc_cubics(centre, r, start, end)
        if chain:
            chain.append(_straight(chain[-1][3], quarter[0][0]))
        chain.extend(quarter)
    chain.append(_straight(chain[-1][3], chain[0][0]))
    return inklet.path(curves=chain, closed=True, **style)


def _flatten(points: Sequence, smooth: float, closed: bool,
             steps: int = 8) -> list[Vec2]:
    """The polygon a `inklet.curve` of these points actually draws.

    Anything that has to agree with a smooth boundary -- a hatch, an offset --
    needs the flattening, and `curve()` keeps it to itself. Re-deriving it from
    the library's own `catmull_rom` is the only way to be sure the hatch stops
    where the outline is rather than where its control polygon is.
    """
    chain = inklet.draw.catmull_rom(inklet.draw.to_points(points), smooth, closed)
    out = [chain[0][0]]
    for p0, c1, c2, p3 in chain:
        for i in range(1, steps + 1):
            t = i / steps
            u = 1.0 - t
            out.append(p0 * (u * u * u) + c1 * (3 * u * u * t)
                       + c2 * (3 * u * t * t) + p3 * (t * t * t))
    if closed and (out[-1] - out[0]).length <= _EPS:
        out.pop()
    return out


def _hatch(contours: Sequence[Sequence[Vec2]], angle: float, spacing: float,
           shortest: float = 0.30) -> list[tuple[Vec2, Vec2]]:
    """Parallel lines clipped to the region bounded by `contours`.

    There is no clipping in `inklet` and no pattern fill, so a hatch is a set of
    segments somebody has to compute. This is the even-odd scanline: rotate
    every boundary into a frame where the hatch lines are horizontal, and for
    each line collect the crossings of every contour, sort them, and take them
    in pairs. Parity is counted over *all* the contours at once, so a hole
    given as a second contour subtracts itself -- which is how the cortical
    ribbon gets hatched without the hatch running on through the white matter.

    The half-open test `v0 <= v < v1` is what makes a vertex sitting exactly on
    a hatch line count once instead of twice or not at all; without it every
    span past such a vertex comes out inverted.
    """
    ca = math.cos(math.radians(angle))
    sa = math.sin(math.radians(angle))
    turned = [[(p.x * ca + p.y * sa, -p.x * sa + p.y * ca) for p in contour]
              for contour in contours if len(contour) >= 3]
    if not turned:
        return []
    across = [v for contour in turned for _, v in contour]
    first = math.ceil(min(across) / spacing)
    last = math.floor(max(across) / spacing)

    out: list[tuple[Vec2, Vec2]] = []
    for step in range(first, last + 1):
        v = step * spacing
        crossings: list[float] = []
        for contour in turned:
            count = len(contour)
            for i in range(count):
                u0, v0 = contour[i]
                u1, v1 = contour[(i + 1) % count]
                if (v0 <= v < v1) or (v1 <= v < v0):
                    crossings.append(u0 + (v - v0) * (u1 - u0) / (v1 - v0))
        crossings.sort()
        for a, b in zip(crossings[0::2], crossings[1::2]):
            if b - a >= shortest:
                out.append((Vec2(a * ca - v * sa, a * sa + v * ca),
                            Vec2(b * ca - v * sa, b * sa + v * ca)))
    return out


def _point_segment(p: Vec2, a: Vec2, b: Vec2) -> float:
    span = b - a
    length2 = span.dot(span)
    if length2 <= _EPS:
        return (p - a).length
    t = min(1.0, max(0.0, (p - a).dot(span) / length2))
    return (p - (a + span * t)).length


def _simplify(points: Sequence[Vec2], tolerance: float) -> list[Vec2]:
    """Ramer-Douglas-Peucker, iteratively.

    Marching squares emits one vertex per cell crossing, which for a 100x80
    grid is a couple of hundred points per contour; handing those to
    `inklet.curve` would mint a cubic per cell and describe a straight run with
    forty of them. Thinning first is what makes "smooth curve" mean anything.
    """
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo + 1:
            continue
        a, b = points[lo], points[hi]
        worst, at = -1.0, lo
        for i in range(lo + 1, hi):
            gap = _point_segment(points[i], a, b)
            if gap > worst:
                worst, at = gap, i
        if worst > tolerance:
            keep[at] = True
            stack.append((lo, at))
            stack.append((at, hi))
    return [p for p, flag in zip(points, keep) if flag]


# -- composition ----------------------------------------------------------


def _carry_origin(wrapper: Diagram, inner: Diagram) -> Diagram:
    """Re-register the plot-area anchor a wrapper would otherwise lose.

    `inklet.row` lines panels up on their `origin` anchor, which `Panel.build`
    puts on the centre of the plot area. Every layout combinator drops it.
    """
    try:
        point = inner.transform.apply(inner.anchor_point("origin"))
    except inklet.DiagramError:
        return wrapper
    return wrapper.anchor("origin", point)


def _fit(build: Callable[[float], Diagram], width: float,
         tries: int = 5) -> Diagram:
    """Build a panel whose *total* width is `width`.

    `inklet.panel` sizes the plot **area**; how much room the ticks, the axis
    names and any label overhanging the area will take is only known once the
    thing is built. There is no "fit into this box" mode, so the only way to
    hit a column width exactly is to build, measure, and build again.
    """
    area = width
    node = best = build(area)
    for _ in range(tries):
        if abs(node.bbox.width - width) < abs(best.bbox.width - width):
            best = node
        over = node.bbox.width - width
        if abs(over) <= 0.02:
            break
        area = max(width * 0.35, area - over)
        narrower = build(area)
        if narrower.bbox.width >= node.bbox.width - 0.01:
            # Shrinking the plot area did not narrow the panel, so something
            # in the tree has a minimum width of its own -- a legend, a long
            # axis name -- and no amount of further shrinking will reach the
            # target. Stop, rather than collapse the plot to nothing chasing a
            # width that is not the plot's to give.
            break
        node = narrower
    slack = width - best.bbox.width
    if slack > 0.02:
        best = _carry_origin(inklet.pad(best, 0.0, slack / 2), best)
    return best


def _at(panel, items: Iterable[tuple[Sequence[float], Diagram]],
        anchor: str = "center") -> Diagram:
    """`Panel.place` with an anchor.

    `Panel.place` hands every item to `draw.place` with the default centre
    anchor, so a column of labels that should hang off a guide by their east
    edge has to be placed by hand.
    """
    return inklet.place([(panel.point(*point), node) for point, node in items],
                     anchor=anchor)


def _shifted(node: Diagram, gap: float, side: str) -> Diagram:
    """A label with empty space added on one side, so that anchoring it
    against a point leaves it standing `gap` clear of that point.

    The padding is what holds a label off its leader, rather than a hand-tuned
    offset added to a coordinate.
    """
    return inklet.pad(node,
                   gap if side == "top" else 0.0,
                   gap if side == "right" else 0.0,
                   gap if side == "bottom" else 0.0,
                   gap if side == "left" else 0.0)


# =========================================================================
# d -- coronal section
# =========================================================================

# Drawn in millimetres of real mouse brain at roughly bregma -2.0: about
# 8.7mm across and 5.5mm deep, dorsal towards +y.
_D_HALF = 4.35
_D_X = (-8.2, 8.2)
_D_Y = (-6.35, 0.45)
_D_EDGE = 7.95            # where a label hangs, in brain millimetres
#: How deep the cortical ribbon is at the crown, the flank and the base: it is
#: thickest over the dorsal surface and thinnest where it gives way to the
#: ventral structures, which is both true and what makes the section read.
_D_CROWN, _D_LATERAL, _D_BASE = 0.95, 0.80, 0.42

#: Centre and radii of the hippocampal arc, shared by the region and its leader.
_D_HIPPO = (Vec2(1.78, -2.10), (1.05, 0.58))


def _d_dorsal(x: float, ripple: bool = True) -> float:
    """The cortical surface: a dome, plus the convolution the schematic wants.
    The ripple is even in x so the hemispheres match, and fades out laterally
    where the surface turns down into the wall."""
    y = -0.10 - 0.098 * x * x
    if ripple:
        y += 0.070 * math.cos(2.90 * x) * (1.0 - (abs(x) / _D_HALF) ** 4)
    return y


def _d_ventral(x: float) -> float:
    a = abs(x)
    return (-5.05
            - 0.50 * math.exp(-(x / 0.80) ** 2)            # hypothalamic midline
            + 1.75 * (a / _D_HALF) ** 3.0                  # rise to the wall
            - 0.30 * math.exp(-((a - 2.85) / 0.85) ** 2))  # piriform bulge


def _span(lo: float, hi: float, steps: int) -> list[float]:
    return [lo + (hi - lo) * i / steps for i in range(steps + 1)]


def _surface(lo: float, hi: float, surface, shift: float = 0.0,
             steps: int = 30) -> list[Vec2]:
    return [Vec2(x, surface(x) + shift) for x in _span(lo, hi, steps)]


def _d_outline(ripple: bool = True) -> list[Vec2]:
    """The silhouette: dorsal surface left to right, down the right wall, back
    along the ventral surface, up the left wall."""
    return (_surface(-_D_HALF, _D_HALF, lambda x: _d_dorsal(x, ripple))
            + _d_wall(1.0, ripple)
            + _surface(_D_HALF, -_D_HALF, _d_ventral)
            + _d_wall(-1.0, ripple))


def _d_wall(sign: float, ripple: bool, steps: int = 12) -> list[Vec2]:
    """The lateral wall between the two surfaces, bulging slightly outward.

    Sampled as finely as the surfaces are. Catmull-Rom through points whose
    spacing jumps by a factor of four overshoots at the join, and offsetting
    that curve inward turns the overshoot into a spike on the white matter --
    a visible tooth pointing out of an otherwise smooth boundary.
    """
    top = _d_dorsal(sign * _D_HALF, ripple)
    bottom = _d_ventral(sign * _D_HALF)
    if sign < 0:
        top, bottom = bottom, top
    return [Vec2(sign * (_D_HALF + 0.20 * math.sin(math.pi * (i / steps))),
                 top + (bottom - top) * (i / steps))
            for i in range(1, steps)]


def _d_core() -> list[Vec2]:
    """Everything deep to the cortical ribbon, as one closed boundary.

    Described the same way the silhouette is -- the same two surfaces moved
    inward by the cortical thickness, the same wall brought in -- rather than
    derived from the silhouette polygon by a numerical inward offset.

    The offset is the obvious way to do this and it does not survive contact
    with the shape. Where a boundary turns tighter than the offset distance the
    front passes through the centre of curvature and comes back out as a cusp,
    and at the shoulder, where the dome gives way to the lateral wall, the
    radius of curvature is 0.58mm against an offset of 0.80. Nothing catches
    that cheaply: the cusp points are still the full distance from the
    boundary, so a distance test passes them, and the two edges never quite
    cross, so an intersection test passes them too. Capping each offset at the
    local radius trades the fold for a crease in the same place. Both surfaces
    are known in closed form here, so the ribbon is stated rather than derived.

    The ripple is deliberately absent: the convolutions belong to the pial
    surface, and carrying them inward would corrugate the white matter too.
    """
    half = _D_HALF - _D_LATERAL
    return (_surface(-half, half, lambda x: _d_dorsal(x, False), -_D_CROWN)
            + _d_core_wall(1.0)
            + _surface(half, -half, _d_ventral, _D_BASE)
            + _d_core_wall(-1.0))


def _d_core_wall(sign: float, steps: int = 10) -> list[Vec2]:
    half = _D_HALF - _D_LATERAL
    top = _d_dorsal(sign * half, False) - _D_CROWN
    bottom = _d_ventral(sign * half) + _D_BASE
    if sign < 0:
        top, bottom = bottom, top
    return [Vec2(sign * half, top + (bottom - top) * (i / steps))
            for i in range(1, steps)]


def _d_inside(x: float, depth: float) -> Vec2:
    """A point `depth` beneath the dorsal surface, along its own normal --
    where a leader pointing at the cortical ribbon has to land."""
    slope = -0.196 * x
    scale = 1.0 / math.hypot(slope, 1.0)
    return Vec2(x + slope * depth * scale,
                _d_dorsal(x, False) - depth * scale)


def _d_arc_point(degrees: float) -> Vec2:
    """A point on the centre line of the left hippocampal band, so the leader
    lands on the structure rather than near it."""
    angle = math.radians(degrees)
    return Vec2(-(_D_HIPPO[0].x + _D_HIPPO[1][0] * math.cos(angle)),
                _D_HIPPO[0].y + _D_HIPPO[1][1] * math.sin(angle))


def _d_band(centre: Vec2, radii: tuple[float, float], start: float, end: float,
            thickness: float, steps: int = 22) -> list[Vec2]:
    """A C: an elliptical arc given width, closed at both ends."""
    outer, inner = [], []
    for i in range(steps + 1):
        angle = math.radians(start + (end - start) * i / steps)
        radius = Vec2(math.cos(angle) * radii[0], math.sin(angle) * radii[1])
        unit = radius * (1.0 / (radius.length or 1.0))
        outer.append(centre + radius + unit * (thickness / 2))
        inner.append(centre + radius - unit * (thickness / 2))
    return outer + inner[::-1]


def _d_blob(centre: Vec2, radii: tuple[float, float], waist: float = 0.0,
            steps: int = 26) -> list[Vec2]:
    """A rounded mass, optionally pinched at the vertical midline -- which is
    what the third ventricle does to the thalamus."""
    points = []
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        pinch = 1.0 - waist * math.exp(-(math.cos(angle) / 0.45) ** 2)
        points.append(Vec2(centre.x + radii[0] * math.cos(angle),
                           centre.y + radii[1] * math.sin(angle) * pinch))
    return points


def _mirrored(points: Sequence[Vec2]) -> list[Vec2]:
    return [Vec2(-p.x, p.y) for p in points]


def _d_regions() -> list[dict]:
    """The five regions, back to front.

    Each is a control polygon; what gets drawn is the closed Catmull-Rom
    through it. They are painted outermost first, each one opaque over the
    last, so the cortical ribbon is what is left of the cortex once the white
    matter has covered its middle. That is the only way to get a region with a
    hole out of this renderer: `PathPrim` has no fill rule, so even-odd is
    unavailable and a true annulus would have to be one boundary that does not
    cross itself.
    """
    hippocampus = _d_band(_D_HIPPO[0], _D_HIPPO[1], 165.0, -60.0, 0.34)
    ventricle = _d_band(Vec2(1.00, -1.95), (0.88, 0.80), 118.0, 168.0, 0.11)
    third = [Vec2(-0.055, -2.62), Vec2(0.055, -2.62),
             Vec2(0.055, -4.55), Vec2(-0.055, -4.55)]
    return [
        {"name": "cortex", "series": 5, "tint": 0.26, "smooth": 0.42,
         "contours": [_d_outline()]},
        {"name": "white matter", "series": 4, "tint": 0.30, "smooth": 0.42,
         "contours": [_d_core()]},
        {"name": "thalamus", "series": 1, "tint": 0.45, "smooth": 0.5,
         "contours": [_d_blob(Vec2(0.0, -3.50), (1.90, 0.95), waist=0.20)]},
        {"name": "hippocampus", "series": 3, "tint": 0.45, "smooth": 0.5,
         "contours": [hippocampus, _mirrored(hippocampus)]},
        {"name": "ventricle", "series": 2, "tint": 0.62, "smooth": 0.45,
         "contours": [ventricle, _mirrored(ventricle), third]},
    ]


# Where each leader lands, and how high up the margin its label hangs. Both
# are anatomy: the label sits beside the structure it names.
_D_LABELS = (
    ("cortex", -1.0, -0.85),
    ("hippocampus", -1.0, -2.55),
    ("white matter", 1.0, -1.35),
    ("thalamus", 1.0, -3.60),
)


def _d_targets() -> dict[str, Vec2]:
    return {
        "cortex": _d_inside(-3.20, 0.48),
        "hippocampus": _d_arc_point(-20.0),
        "white matter": Vec2(2.85, -2.85),
        "thalamus": Vec2(0.95, -3.55),
    }


def panel_d(width: float = CONTENT_WIDTH) -> Diagram:
    """A schematic coronal section: nested filled regions, one of them hatched."""
    theme = inklet.current_theme()
    regions = _d_regions()
    targets = _d_targets()

    def build(area: float) -> Diagram:
        span_x = _D_X[1] - _D_X[0]
        scale = area / span_x
        plot = inklet.panel(area, area * (_D_Y[1] - _D_Y[0]) / span_x,
                         x=_D_X, y=_D_Y)

        for region in regions:
            fill = _tint(theme.color(region["series"]), region["tint"])
            edge = _shade(theme.color(region["series"]), 0.45)
            for contour in region["contours"]:
                plot.draw(inklet.curve(plot.map([(p.x, p.y) for p in contour]),
                                    smooth=region["smooth"], closed=True,
                                    fill=fill, stroke=edge,
                                    stroke_width=theme.hairline))
            if region["name"] == "cortex":
                plot.draw(*_d_hatch(plot, regions, theme))

        # The interhemispheric fissure: a rule, not a region.
        plot.draw(inklet.polyline(plot.map([(0.0, _d_dorsal(0.0)), (0.0, -0.95)]),
                               stroke=_shade(theme.color(5), 0.45),
                               stroke_width=theme.hairline))

        for name, side, height in _D_LABELS:
            plot.draw(*_d_leader(plot, name, side, height, targets[name],
                                 scale, theme))
        plot.draw(*_d_furniture(plot, theme))
        return plot.build()

    return _fit(build, width)


def _d_hatch(plot, regions: Sequence[dict], theme) -> list[Diagram]:
    """The cortical ribbon, hatched.

    Both boundaries go into one even-odd scan, so the white matter punches its
    own hole. The spacing is a page measurement -- 0.62mm of paper, not 0.62mm
    of brain -- which is why the contours are mapped through the scales
    *before* they are hatched rather than after.
    """
    on_page = [[plot.point(p.x, p.y)
                for p in _flatten(region["contours"][0], region["smooth"], True)]
               for region in regions[:2]]
    ink = _shade(theme.color(5), 0.55)
    return [inklet.polyline((a, b), stroke=ink, stroke_width=theme.hairline)
            for a, b in _hatch(on_page, -38.0, 0.62)]


def _d_leader(plot, name: str, side: float, height: float, target: Vec2,
              scale: float, theme) -> list[Diagram]:
    """A label out in the margin and the line that ties it to its region.

    The label is anchored on the far edge of the frame and the leader starts
    from whichever end of it faces inward, so a longer name eats into the
    leader rather than pushing the panel wider.
    """
    text = inklet.label(name)
    gap = theme.gap("xs")
    edge = _D_EDGE * side
    inner = edge - side * (text.bbox.width + gap) / scale
    return [
        inklet.polyline(plot.map([(inner, height), (target.x, target.y)]),
                     stroke=theme.muted, stroke_width=theme.hairline),
        inklet.place([(plot.point(target.x, target.y),
                    inklet.marker("circle", 0.7, fill=theme.muted))]),
        _at(plot, [((edge, height), text)], anchor="w" if side < 0 else "e"),
    ]


def _d_furniture(plot, theme) -> list[Diagram]:
    """A 1mm scale bar and the plane of section."""
    y = -5.80
    return [
        inklet.polyline(plot.map([(-_D_EDGE, y), (-_D_EDGE + 1.0, y)]),
                     stroke=theme.ink, stroke_width=theme.thick),
        _at(plot, [((-_D_EDGE + 0.5, y),
                    _shifted(inklet.label("1 mm"), theme.gap("xs"), "top"))],
            anchor="n"),
        _at(plot, [((_D_EDGE, -6.05),
                    inklet.label("bregma −2.0 mm", text_fill=theme.muted))],
            anchor="e"),
    ]


# =========================================================================
# e -- experimental protocol
# =========================================================================

# (row, label, first day, last day, category). Rows read top to bottom.
_E_TASKS = (
    ("injection", "AAV2/1-syn-GCaMP6f", 0.0, 1.0, "surgery"),
    ("window", "3 mm cranial window", 0.0, 1.0, "surgery"),
    ("expression", "GCaMP6f expression", 1.0, 22.0, "expression"),
    ("recovery", "post-op recovery", 1.0, 14.0, "handling"),
    ("habituation", "head-fix habituation", 12.0, 22.0, "handling"),
    ("imaging", "1", 23.0, 25.0, "imaging"),
    ("imaging", "2", 26.5, 28.5, "imaging"),
    ("imaging", "3", 30.0, 32.0, "imaging"),
    ("imaging", "4", 33.5, 35.5, "imaging"),
    ("imaging", "5", 37.0, 39.0, "imaging"),
    ("perfusion", "perfusion + histology", 40.5, 41.5, "endpoint"),
)
_E_ROWS = ("injection", "window", "expression", "recovery", "habituation",
           "imaging", "perfusion")
_E_CATEGORIES = (("surgery", 6), ("expression", 3), ("handling", 2),
                 ("imaging", 5), ("endpoint", 7))
_E_DAYS = (-1.5, 43.5)
_E_TODAY = 20.0


def panel_e(width: float = CONTENT_WIDTH) -> Diagram:
    """A protocol timeline on a band scale of stages and a linear scale of days.

    The labels are the interesting part. A bar's own caption goes inside it
    when it fits with room to breathe, to the right of it when it does not and
    there is clear axis left, and to the left when there is not -- which
    happens exactly once, at the perfusion bar two days from the end of the
    axis, and reads as a decision rather than as an accident.

    The bars are a tint of their category with the full colour as their edge,
    which is what lets every caption be set in ink: white-on-dark would be
    legible on the page and unverifiable to `inklet.lint`, whose backdrop test
    only recognises rectangles and ellipses and so reads a caption on a drawn
    bar as ink on bare paper.
    """
    theme = inklet.current_theme()
    edges = {name: theme.color(index) for name, index in _E_CATEGORIES}
    fills = {name: _tint(color, 0.42) for name, color in edges.items()}

    def build(area: float) -> Diagram:
        rows = inklet.band(tuple(reversed(_E_ROWS)), (0.0, 1.0), padding=0.22)
        # Height off the *target* width, not off `area`: the fit loop shrinks
        # the area, and a height that followed it would thin the rows until a
        # caption no longer fitted inside its own bar.
        plot = inklet.panel(area, width * 0.34, x=inklet.linear(_E_DAYS), y=rows)

        for index, row in enumerate(_E_ROWS):
            if index % 2 == 0:
                plot.under(_e_stripe(plot, row, theme))
        plot.grid(y=False, count=6, stroke=theme.grid)

        bars, captions = [], []
        for task in _E_TASKS:
            bar, caption = _e_bar(plot, task, fills, edges, theme)
            bars.append(bar)
            captions.append(caption)
        plot.draw(*bars)
        # Between the bars and the captions: the rule has to read as being in
        # front of the schedule without cutting through anybody's words.
        plot.draw(*_e_today(plot, theme))
        plot.draw(*captions)

        plot.axis("bottom", label="days from surgery", count=6)
        # Spine only, and the row names placed by hand. `plot.axis("left")`
        # thins its labels with the rule a numeric axis uses -- drop any tick
        # whose label would come within 0.7em of its neighbour's -- and rows
        # one line-height apart trip it, so a seven-row schedule silently
        # arrives with four names on it and no way to ask for the other three.
        plot.axis("left", ticks=(), tick_size=0.0)
        plot.draw(*_e_rows(plot, theme))
        return plot.build()

    key = inklet.legend([(name, _e_swatch(fills[name], edges[name], theme))
                      for name, _ in _E_CATEGORIES], columns=3)
    return _fit(lambda area: inklet.vstack([build(area), key],
                                        gap=theme.gap("s"), align="center"),
                width)


def _e_rows(plot, theme) -> list[Diagram]:
    """One name per row, against the left spine."""
    gap = theme.gap("xs")
    return [inklet.place([(Vec2(plot.area.x0, sum(plot.y.edges(row)) / 2),
                        _shifted(inklet.label(row), gap, "right"))], anchor="e")
            for row in _E_ROWS]


def _e_swatch(fill: str, edge: str, theme) -> Diagram:
    """A miniature of the bar, so the key shows what is on the chart rather
    than a solid block of a colour that appears nowhere."""
    return _rounded_rect(0.0, 0.0, 3.6, 2.0, theme.radius / 2, fill=fill,
                         stroke=edge, stroke_width=theme.hairline)


def _e_stripe(plot, row: str, theme) -> Diagram:
    """A full-width band behind one row, so the eye can track it across 45
    days of empty axis."""
    lo, hi = plot.y.edges(row)
    slack = (abs(plot.y.step) - abs(hi - lo)) / 2
    box = plot.area
    return inklet.polygon(((box.x0, lo - slack), (box.x1, lo - slack),
                        (box.x1, hi + slack), (box.x0, hi + slack)),
                       fill=_tint(theme.grid, 0.5), stroke="none")


def _e_bar(plot, task, fills: dict, edges: dict, theme) -> tuple[Diagram, Diagram]:
    row, name, start, end, category = task
    lo, hi = plot.y.edges(row)
    x0, x1 = plot.x.map(start), plot.x.map(end)
    fill = fills[category]
    bar = _rounded_rect(x0, lo, x1, hi, min(theme.radius, abs(hi - lo) / 2.5),
                        fill=fill, stroke=edges[category],
                        stroke_width=theme.hairline)
    return bar, _e_caption(plot, name, fill, x0, x1, (lo + hi) / 2, theme)


def _e_caption(plot, name: str, color: str, x0: float, x1: float,
               middle: float, theme) -> Diagram:
    """Inside the bar, or beside it, by the rule in `panel_e`'s docstring."""
    clearance = theme.gap("2xs")
    inside = inklet.label(name, text_fill=theme.text_on(color))
    if inside.bbox.width + 2 * clearance <= x1 - x0:
        return inklet.place([(Vec2((x0 + x1) / 2, middle), inside)])
    outside = inklet.label(name)
    gap = theme.gap("xs")
    if x1 + gap + outside.bbox.width <= plot.area.x1:
        return inklet.place([(Vec2(x1, middle), _shifted(outside, gap, "left"))],
                         anchor="w")
    return inklet.place([(Vec2(x0, middle), _shifted(outside, gap, "right"))],
                     anchor="e")


def _e_today(plot, theme) -> list[Diagram]:
    box = plot.area
    at = plot.x.map(_E_TODAY)
    return [
        inklet.polyline(((at, box.y0), (at, box.y1)), stroke=theme.accent,
                     stroke_width=theme.stroke, stroke_dash=(1.1, 0.8)),
        inklet.place([(Vec2(at, box.y0),
                    _shifted(inklet.label("day %d" % _E_TODAY,
                                       text_fill=theme.accent),
                             theme.gap("xs"), "bottom"))], anchor="s"),
    ]


# =========================================================================
# f -- ΔF/F traces
# =========================================================================

_F_CELLS = 8
_F_SAMPLES = 400
_F_DT = 0.15
_F_STEP = 3.0                      # ΔF/F₀ between one trace and the next
_F_EPOCHS = ((13.0, 19.0), (37.0, 43.0))
_F_SEED = 20240822


def _f_traces() -> list[list[tuple[float, float]]]:
    """Eight calcium traces: sparse transients with an exponential decay on a
    drifting, noisy baseline.

    Which cells are driven by which epoch comes off the same seeded stream as
    everything else, so the panel shows a population that responds rather than
    eight independent noise generators.
    """
    rng = random.Random(_F_SEED)
    traces = []
    for _ in range(_F_CELLS):
        tau = rng.uniform(0.55, 1.45)
        driven = [rng.random() < 0.62 for _ in _F_EPOCHS]
        events = [(k * _F_DT, rng.uniform(0.35, 1.5)) for k in range(_F_SAMPLES)
                  if rng.random() < 0.055 * _F_DT]
        for epoch, responds in zip(_F_EPOCHS, driven):
            if not responds:
                continue
            events.append((epoch[0] + rng.uniform(0.05, 0.55),
                           rng.uniform(1.1, 2.4)))
            if rng.random() < 0.5:
                events.append((rng.uniform(epoch[0] + 1.5, epoch[1]),
                               rng.uniform(0.5, 1.4)))
        raw = [rng.gauss(0.0, 0.075) for _ in range(_F_SAMPLES + 2)]
        phase, slow = rng.uniform(0, 6.28), rng.uniform(0, 6.28)
        series = []
        for k in range(_F_SAMPLES):
            t = k * _F_DT
            # Three-tap smoothing on the white noise: one raw gaussian per
            # sample reads as hatching at this line width, not as a baseline.
            value = (raw[k] + 2 * raw[k + 1] + raw[k + 2]) / 4
            value += 0.055 * math.sin(t / 26.0 * 6.283 + phase)
            value += 0.035 * math.sin(t / 9.5 * 6.283 + slow)
            for onset, amplitude in events:
                lag = t - onset
                if lag >= 0:
                    value += (amplitude * (1 - math.exp(-lag / 0.12))
                              * math.exp(-lag / tau))
            series.append((t, value))
        traces.append(series)
    return traces


def panel_f(width: float = CONTENT_WIDTH) -> Diagram:
    """Stacked ΔF/F₀ traces with no y axis at all.

    A spine would claim the offsets mean something, and they do not -- they are
    there so that eight traces can share one time axis. What the reader needs
    is the two scale bars, which is why the panel has no `axes()` call in it.
    """
    theme = inklet.current_theme()
    traces = _f_traces()
    top = (_F_CELLS - 1) * _F_STEP + 3.4
    seconds = _F_SAMPLES * _F_DT

    def build(area: float) -> Diagram:
        plot = inklet.panel(area, area * 0.58, x=(0.0, seconds), y=(-2.1, top))
        for index, epoch in enumerate(_F_EPOCHS):
            plot.under(_f_epoch(plot, epoch, top, theme))
            plot.over(_at(plot, [((sum(epoch) / 2, top),
                                  _shifted(inklet.label("grating %d" % (index + 1),
                                                     text_fill=theme.muted),
                                           theme.gap("xs"), "bottom"))],
                          anchor="s"))
        for index, series in enumerate(traces):
            offset = (_F_CELLS - 1 - index) * _F_STEP
            plot.line([(t, v + offset) for t, v in series],
                      stroke=theme.ink_color(index), stroke_width=theme.hairline)
            plot.draw(_at(plot, [((0.0, offset), _f_tag("%d" % (index + 1), theme))],
                          anchor="e"))
        plot.draw(_at(plot, [((0.0, top - 0.5), _f_tag("ROI", theme))], anchor="e"))
        plot.over(*_f_scale_bars(plot, seconds, theme))
        return plot.build()

    return _fit(build, width)


def _f_tag(text: str, theme) -> Diagram:
    return _shifted(inklet.label(text, text_fill=theme.muted),
                    theme.gap("xs"), "right")


def _f_epoch(plot, epoch: tuple[float, float], top: float, theme) -> Diagram:
    """A stimulus window, shaded behind everything.

    Translucent here rather than tinted: the band is under the traces, so what
    the eye should see through it is the paper *and* the gridless white the
    traces sit on, and an opacity says that in one attribute.
    """
    start, end = epoch
    corners = plot.map([(start, -2.1), (end, -2.1), (end, top), (start, top)])
    return inklet.polygon(corners, fill=theme.accent, stroke="none", opacity=0.11)


def _f_scale_bars(plot, seconds: float, theme) -> list[Diagram]:
    """An L of two bars and their units, in the corner the data leaves empty."""
    corner = plot.point(seconds, -1.55)
    across = plot.point(seconds - 10.0, -1.55)
    up = plot.point(seconds, 0.45)
    return [
        inklet.polyline((across, corner, up), stroke=theme.ink,
                     stroke_width=theme.thick),
        inklet.place([(Vec2((across.x + corner.x) / 2, corner.y),
                    _shifted(inklet.label("10 s"), theme.gap("xs"), "top"))],
                  anchor="n"),
        inklet.place([(Vec2(corner.x, (corner.y + up.y) / 2),
                    _shifted(inklet.label("2 ΔF/F₀"), theme.gap("xs"), "left"))],
                  anchor="w"),
    ]


# =========================================================================
# q -- receptive field, contoured
# =========================================================================

_Q_X = (-9.0, 9.0)
_Q_Y = (-5.3, 5.3)
_Q_GRID = (109, 65)
_Q_SEED = 4711


def _q_gaussian(x: float, y: float, cx: float, cy: float, sx: float, sy: float,
                angle: float) -> float:
    ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    dx, dy = x - cx, y - cy
    u, v = dx * ca + dy * sa, -dx * sa + dy * ca
    return math.exp(-0.5 * ((u / sx) ** 2 + (v / sy) ** 2))


def _q_field() -> tuple[list[float], list[float], list[list[float]]]:
    """A difference of Gaussians in degrees of visual angle, plus four small
    seeded bumps.

    The bumps are the only random thing here and they exist to break the
    symmetry: a pure DoG contours into concentric ellipses, which is exactly
    what a faked marching squares would draw, and then the panel would prove
    nothing.
    """
    rng = random.Random(_Q_SEED)
    bumps = [(rng.uniform(-5.0, 5.0), rng.uniform(-3.4, 3.4),
              rng.uniform(1.9, 2.9), rng.uniform(-0.060, 0.070))
             for _ in range(4)]
    nx, ny = _Q_GRID
    xs = [_Q_X[0] + (_Q_X[1] - _Q_X[0]) * i / (nx - 1) for i in range(nx)]
    ys = [_Q_Y[0] + (_Q_Y[1] - _Q_Y[0]) * j / (ny - 1) for j in range(ny)]
    values = []
    for y in ys:
        row = []
        for x in xs:
            v = (_q_gaussian(x, y, 0.9, 0.5, 1.75, 2.35, 24.0)
                 - 0.60 * _q_gaussian(x, y, 0.1, -0.3, 3.30, 2.80, -12.0))
            for bx, by, bs, ba in bumps:
                v += ba * _q_gaussian(x, y, bx, by, bs, bs, 0.0)
            row.append(v)
        values.append(row)
    peak = max(abs(v) for row in values for v in row)
    return xs, ys, [[v / peak for v in row] for row in values]


def _iso_contours(xs: Sequence[float], ys: Sequence[float],
                  values: Sequence[Sequence[float]],
                  level: float) -> list[tuple[list[Vec2], bool]]:
    """Marching squares, saddle-disambiguated, stitched into chains.

    Each cell contributes zero, one or two segments. The two ambiguous cases --
    opposite corners on the same side of the level -- are resolved with the
    value of the bilinear interpolant at its own saddle point,
    `(v00*v11 - v10*v01) / (v00 + v11 - v10 - v01)`, which is where the two
    branches of the hyperbola meet. Resolving them by a fixed rule instead
    (always join, always split) leaves contours that cross themselves at every
    saddle, and resolving them by the corner mean is a guess that is wrong
    whenever the four corners are lopsided.

    Returns `(points, closed)` pairs. A contour that runs off the grid comes
    back open, because that is what it is.
    """
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for j in range(len(ys) - 1):
        for i in range(len(xs) - 1):
            v00, v10 = values[j][i], values[j][i + 1]
            v11, v01 = values[j + 1][i + 1], values[j + 1][i]
            case = ((1 if v00 > level else 0) | (2 if v10 > level else 0)
                    | (4 if v11 > level else 0) | (8 if v01 > level else 0))
            if case in (0, 15):
                continue
            edges = {
                "a": (_mix(xs[i], xs[i + 1], v00, v10, level), ys[j]),
                "b": (xs[i + 1], _mix(ys[j], ys[j + 1], v10, v11, level)),
                "c": (_mix(xs[i], xs[i + 1], v01, v11, level), ys[j + 1]),
                "d": (xs[i], _mix(ys[j], ys[j + 1], v00, v01, level)),
            }
            if case in (5, 10):
                divisor = v00 + v11 - v10 - v01
                saddle = ((v00 * v11 - v10 * v01) / divisor
                          if abs(divisor) > _EPS
                          else (v00 + v10 + v11 + v01) / 4.0)
                # Case 5 has corners 00 and 11 above the level; if the saddle
                # is above it too they are one region and the contour cuts the
                # other two corners off separately.
                pairs = ((("a", "b"), ("c", "d")) if (case == 5) == (saddle > level)
                         else (("d", "a"), ("b", "c")))
            else:
                pairs = _MARCH[case]
            for start, end in pairs:
                if edges[start] != edges[end]:
                    segments.append((edges[start], edges[end]))
    return _stitch(segments)


_MARCH = {
    1: (("d", "a"),), 2: (("a", "b"),), 3: (("d", "b"),), 4: (("b", "c"),),
    6: (("a", "c"),), 7: (("d", "c"),), 8: (("c", "d"),), 9: (("c", "a"),),
    11: (("c", "b"),), 12: (("b", "d"),), 13: (("b", "a"),), 14: (("a", "d"),),
}


def _mix(lo: float, hi: float, va: float, vb: float, level: float) -> float:
    if abs(vb - va) <= _EPS:
        return lo
    return lo + (hi - lo) * (level - va) / (vb - va)


def _stitch(segments) -> list[tuple[list[Vec2], bool]]:
    """Join segments end to end into chains.

    Neighbouring cells interpolate their shared edge from the same two corner
    values, so the endpoints agree bit for bit and can be matched exactly --
    no tolerance, no spatial index. Chains grow at either end and merge when a
    segment bridges two of them; one that closes on itself is a loop.
    """
    chains: list[list[tuple[float, float]]] = []
    ends: dict[tuple[float, float], int] = {}
    closed: list[list[Vec2]] = []

    def detach(chain: list) -> None:
        ends.pop(chain[0], None)
        ends.pop(chain[-1], None)

    def attach(index: int) -> None:
        chain = chains[index]
        ends[chain[0]] = index
        ends[chain[-1]] = index

    for a, b in segments:
        ia, ib = ends.get(a), ends.get(b)
        if ia is None and ib is None:
            chains.append([a, b])
            attach(len(chains) - 1)
        elif ib is None:
            chain = chains[ia]
            detach(chain)
            chain.insert(0, b) if chain[0] == a else chain.append(b)
            attach(ia)
        elif ia is None:
            chain = chains[ib]
            detach(chain)
            chain.insert(0, a) if chain[0] == b else chain.append(a)
            attach(ib)
        elif ia == ib:
            chain = chains[ia]
            detach(chain)
            closed.append([Vec2(*p) for p in chain])
            chains[ia] = []
        else:
            first, second = chains[ia], chains[ib]
            detach(first)
            detach(second)
            if first[-1] != a:
                first.reverse()
            if second[0] != b:
                second.reverse()
            chains[ia] = first + second
            chains[ib] = []
            attach(ia)
    out = [(points, True) for points in closed]
    out += [([Vec2(*p) for p in chain], False)
            for chain in chains if len(chain) > 2]
    return out


def panel_q(width: float = CONTENT_WIDTH) -> Diagram:
    """A receptive field as iso-contours, three of them labelled inline.

    An inline contour label has to interrupt its contour, and with no clipping
    the only way to interrupt anything is to not draw it: the arc-length window
    the label will cover is cut out of the contour and the remainder is drawn
    as one open curve. The label is then rotated onto the local tangent, the
    way contour labels have been set since hand-drawn topographic maps.
    """
    theme = inklet.current_theme()
    xs, ys, values = _q_field()
    low = min(v for row in values for v in row)
    levels = [0.72 * low, 0.40 * low, 0.20, 0.45, 0.70, 0.90]
    # Marched once, outside `build`: the fit loop rebuilds the panel several
    # times and the contours do not depend on how wide it is.
    contours = [sorted(_iso_contours(xs, ys, values, level),
                       key=lambda item: -len(item[0])) for level in levels]
    domain_x, domain_y = _q_domain(contours)
    # Two ramps, not one. A single ramp from a cool colour to a warm one passes
    # through grey in the middle, and the contour that landed on the middle
    # would read as the least important one on the page rather than as the
    # zero crossing it sits nearest.
    cool = inklet.ramp([theme.ink_color(5), theme.ink_color(2)])
    warm = inklet.ramp([theme.ink_color(4), theme.ink_color(1), theme.ink_color(6)])
    # Contour index -> where round it the label goes, as a page bearing
    # (y grows downward, so -75 is up and slightly to the right). Near the top
    # and bottom of a contour the tangent is flattest, which is where a label
    # rotated onto it stays readable; the three are spread over the ramp and
    # over the panel so no two land in the same place.
    labelled = {4: 45.0, 2: -80.0, 0: 100.0}

    def color_of(level: float) -> str:
        if level < 0:
            return cool((level - levels[0]) / (0.0 - levels[0]))
        return warm((level - levels[2]) / (levels[-1] - levels[2]))

    def build(area: float) -> Diagram:
        span_x = domain_x[1] - domain_x[0]
        plot = inklet.panel(area, area * (domain_y[1] - domain_y[0]) / span_x,
                         x=domain_x, y=domain_y)
        plot.background(fill=theme.paper)
        # Over the contours, not under them: half a fixation cross showing
        # through a contour reads as a break in the contour.
        plot.over(*_q_crosshair(plot, theme))

        for index, level in enumerate(levels):
            style = dict(stroke=color_of(level), stroke_width=theme.stroke,
                         fill="none")
            if level < 0:
                style["stroke_dash"] = (0.9, 0.6)
            for order, (points, closed) in enumerate(contours[index]):
                on_page = _simplify([plot.point(p.x, p.y) for p in points], 0.09)
                if len(on_page) < 5:
                    continue
                bearing = labelled.get(index) if order == 0 else None
                if bearing is None:
                    plot.draw(inklet.curve(on_page, smooth=0.45, closed=closed,
                                        **style))
                else:
                    plot.draw(*_q_labelled(on_page, closed, level, bearing,
                                           style, theme))
        plot.over(*_q_scale_bar(plot, domain_x, domain_y, theme))
        plot.outline(stroke=theme.grid, stroke_width=theme.hairline)
        return plot.build()

    swatch = lambda **kw: inklet.polyline(((0, 0), (3.4, 0)),
                                       stroke_width=theme.stroke, **kw)
    key = inklet.legend([("ON subfield", swatch(stroke=warm(1.0))),
                      ("OFF surround", swatch(stroke=cool(0.0),
                                              stroke_dash=(0.9, 0.6)))],
                     columns=2)
    return _fit(lambda area: inklet.vstack([build(area), key],
                                        gap=theme.gap("s"), align="center"),
                width)


def _q_domain(contours, margin: float = 0.085,
              ratio: float = 0.56) -> tuple[tuple, tuple]:
    """A domain that frames every contour, with square degrees.

    Guessing a domain and hoping the field fits inside it is how a contour ends
    up drawn across the panel below -- there is no clipping, so anything that
    leaves the plot area simply keeps going over whatever is next on the page.
    The extents come from the extracted contours themselves, and whichever axis
    is short of the panel's aspect is padded rather than stretched, because a
    receptive field measured in degrees is only readable if a degree across is
    a degree down.
    """
    points = [p for level in contours for chain, _ in level for p in chain]
    x0 = min(p.x for p in points)
    x1 = max(p.x for p in points)
    y0 = min(p.y for p in points)
    y1 = max(p.y for p in points)
    pad = margin * max(x1 - x0, y1 - y0)
    x0, x1, y0, y1 = x0 - pad, x1 + pad, y0 - pad, y1 + pad
    if (y1 - y0) < ratio * (x1 - x0):
        grow = (ratio * (x1 - x0) - (y1 - y0)) / 2
        y0, y1 = y0 - grow, y1 + grow
    else:
        grow = ((y1 - y0) / ratio - (x1 - x0)) / 2
        x0, x1 = x0 - grow, x1 + grow
    return (x0, x1), (y0, y1)


def _q_labelled(points: Sequence[Vec2], closed: bool, level: float,
                bearing: float, style: dict, theme) -> list[Diagram]:
    """One contour with its value set into a gap cut in the line.

    A contour only gives up an arc if it has one to spare: below about four
    label-widths of perimeter the gap is a sizeable fraction of the whole loop
    and the contour stops reading as a closed level set. Those get the label
    outside instead, set horizontally, which is the other half of the choice
    the brief left open.
    """
    text = inklet.label(_q_format(level), text_fill=_readable(style["stroke"]))
    window = text.bbox.width + 2 * theme.gap("xs")
    centre = Vec2(sum(p.x for p in points) / len(points),
                  sum(p.y for p in points) / len(points))
    index = _q_label_vertex(points, centre, bearing)
    count = len(points)
    perimeter = sum((points[(i + 1) % count] - points[i]).length
                    for i in range(count if closed else count - 1))
    if perimeter < 4.0 * window:
        return _q_outside(points, index, centre, text, closed, style, theme)
    run, angle = _q_open_at(points, closed, index, window)
    if run is None:
        return _q_outside(points, index, centre, text, closed, style, theme)
    if abs(angle) > 90.0:
        angle -= math.copysign(180.0, angle)
    return [inklet.curve(run, smooth=0.45, closed=False, **style),
            inklet.place([(points[index], text.rotated(angle))])]


def _q_outside(points: Sequence[Vec2], index: int, centre: Vec2, text: Diagram,
               closed: bool, style: dict, theme) -> list[Diagram]:
    """The contour drawn whole, with its value standing off it radially."""
    away = points[index] - centre
    away = away * (1.0 / (away.length or 1.0))
    reach = (text.bbox.height / 2 + theme.gap("xs"))
    return [inklet.curve(points, smooth=0.45, closed=closed, **style),
            inklet.place([(points[index] + away * reach, text)])]


def _q_label_vertex(points: Sequence[Vec2], centre: Vec2, bearing: float,
                    spread: float = 60.0) -> int:
    """Where on a contour its label should sit.

    Within a sector of the contour -- so that three labels on three nested
    contours do not stack up in the same place -- the flattest vertex wins,
    because a label rotated onto a near-vertical tangent is a label the reader
    has to tilt their head for.
    """
    count = len(points)
    best, score = 0, -1.0
    for i, point in enumerate(points):
        offset = point - centre
        away = math.degrees(math.atan2(offset.y, offset.x))
        if abs((away - bearing + 180.0) % 360.0 - 180.0) > spread:
            continue
        tangent = points[(i + 1) % count] - points[i - 1]
        flat = abs(tangent.x) / (tangent.length or 1.0)
        if flat > score:
            best, score = i, flat
    return best


def _q_open_at(points: Sequence[Vec2], closed: bool, index: int,
               gap: float) -> tuple[list[Vec2] | None, float]:
    """Cut an arc-length window of `gap` out of a contour, centred on `index`.

    A closed loop reopens into one run that starts past the window and wraps
    around to just before it. An open chain would fall into two, and rather
    than return two pieces for a case that does not arise here, it is left
    whole and the caller keeps its label off the line.
    """
    count = len(points)
    if not closed:
        return None, 0.0
    forward = back = index
    walked = 0.0
    while walked < gap / 2 and (forward + 1) % count != back % count:
        walked += (points[(forward + 1) % count] - points[forward % count]).length
        forward += 1
    walked = 0.0
    while walked < gap / 2 and (back - 1) % count != forward % count:
        walked += (points[(back - 1) % count] - points[back % count]).length
        back -= 1
    if forward - back >= count - 3:
        return None, 0.0
    run = [points[(forward + i) % count]
           for i in range((back - forward) % count + 1)]
    tangent = points[(index + 1) % count] - points[index - 1]
    return run, math.degrees(math.atan2(tangent.y, tangent.x))


def _q_format(level: float) -> str:
    return ("%.2f" % level).replace("-", "−")


def _q_crosshair(plot, theme) -> list[Diagram]:
    """Where the animal was looking: the origin of the visual field."""
    centre = plot.point(0.0, 0.0)
    arm = 1.5
    return [inklet.polyline(((centre.x - arm, centre.y), (centre.x + arm, centre.y)),
                         stroke=theme.muted, stroke_width=theme.hairline),
            inklet.polyline(((centre.x, centre.y - arm), (centre.x, centre.y + arm)),
                         stroke=theme.muted, stroke_width=theme.hairline)]


def _q_scale_bar(plot, domain_x, domain_y, theme) -> list[Diagram]:
    left = plot.point(domain_x[0] + 0.6, domain_y[0] + 1.0)
    right = plot.point(domain_x[0] + 5.6, domain_y[0] + 1.0)
    return [inklet.polyline((left, right), stroke=theme.ink,
                         stroke_width=theme.thick),
            inklet.place([(Vec2((left.x + right.x) / 2, left.y),
                        _shifted(inklet.label("5°"), theme.gap("xs"), "top"))],
                      anchor="n")]


# -- looking at them ------------------------------------------------------

if __name__ == "__main__":
    import dataclasses

    THEME = inklet.use_theme(dataclasses.replace(inklet.theme("nature"),
                                              font_family="Noto Sans"))

    def captioned(letter: str, node: Diagram) -> Diagram:
        tag = inklet.text(letter, size=THEME.font_size_large, font_weight="bold")
        return inklet.hstack([tag, node], gap=1.6, align="top")

    figure = inklet.figure(width=inklet.COLUMN_DOUBLE, theme=THEME)
    figure.add(inklet.vstack([captioned(letter, builder(CONTENT_WIDTH))
                           for letter, builder in (("d", panel_d), ("e", panel_e),
                                                   ("f", panel_f), ("q", panel_q))],
                          gap=THEME.gap("xl"), align="left"))
    figure.save("stress/panels/sections.svg")
    print(figure.report())
