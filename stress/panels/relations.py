"""Panels j, l, m and n -- the four that need geometry nobody has written.

Every shape in here is computed, not posed:

* `panel_j` runs a Gaussian kernel density estimate at Silverman's bandwidth
  and draws its mirrored outline as one closed cubic spline; the box is read
  off the same sample by linear-interpolated quantiles; the swarm is packed by
  the collision-avoidance algorithm the R `beeswarm` package uses; and the
  significance brackets stack on an occupancy profile that already contains the
  violins, so a bracket cannot land on ink.
* `panel_l` builds every ribbon as a closed path whose two long edges are one
  cubic and its reverse, stacked at each node in flow order.
* `panel_m` places arc segments proportional to total connectivity and joins
  them with the quadratic-through-the-centre chord, written as the exact cubic.
* `panel_n` agglomerates a seeded distance matrix by average linkage
  (Lance-Williams), lays the resulting tree out, and cuts it at the height that
  yields four clusters.

Nothing here reads or writes a file, consults the clock, or touches a global.
Colour comes from `inklet.current_theme()` at call time, so the panels retheme
with everything else.
"""

from __future__ import annotations

import math
import random
from typing import Sequence

import inklet
from inklet import Diagram, Vec2
from inklet.plot import ribbon_cubics

__all__ = ["panel_j", "panel_l", "panel_m", "panel_n"]

CONTENT_WIDTH = 84.0

#: Plot-area height as a fraction of the width the panel was asked for. An
#: aspect ratio rather than a millimetre count, so a panel dropped into a
#: full-width slot grows instead of becoming a strip.
#:
#: These are the shape of the picture and nothing else decides them, but the
#: figure they go into is a page and a page has a bottom: every one is set so
#: the finished panel -- area plus the furniture that hangs off it -- comes out
#: near three to two. Five violins are naturally wider than tall, six Sankey
#: stages are not, and a dendrogram is a shallow band with its labels
#: underneath, so the fractions are nothing alike even where the results are.
#: Panel m has no constant here: a ring is as tall as it is wide whatever you
#: ask of it, so its proportion is solved rather than declared.
_ASPECT_J = 0.42
_ASPECT_L = 0.52
_ASPECT_N = 0.36

_EPS = 1e-9


# =====================================================================
# deterministic sampling
# =====================================================================


def _normals(rng: random.Random, count: int) -> list[float]:
    """`count` standard normal deviates by Box-Muller.

    `random.gauss` would do, but it caches a spare deviate on the generator, so
    the value a call returns depends on how many gaussians were drawn before
    it. Box-Muller from `.random()` alone keeps every sample a pure function of
    the seed and the index.
    """
    out: list[float] = []
    while len(out) < count:
        u1 = max(rng.random(), 1e-12)
        u2 = rng.random()
        radius = math.sqrt(-2.0 * math.log(u1))
        angle = 2.0 * math.pi * u2
        out.append(radius * math.cos(angle))
        out.append(radius * math.sin(angle))
    return out[:count]


def _mixture(seed: int, count: int, components: Sequence[tuple[float, float, float]],
             lo: float, hi: float) -> tuple[float, ...]:
    """A sample from a weighted mixture of normals, truncated to [lo, hi].

    Truncated by rejection, not by clipping. An index that cannot exceed one is
    not a normal variate pinned at one: clipping stacks every over-range draw on
    the boundary, and a density estimate reads that stack as a real spike right
    where a reader is most likely to over-interpret it.
    """
    rng = random.Random(seed)
    weights = [c[0] for c in components]
    total = sum(weights)
    cuts = []
    running = 0.0
    for w in weights:
        running += w / total
        cuts.append(running)
    values = []
    while len(values) < count:
        pick = rng.random()
        index = next(i for i, cut in enumerate(cuts) if pick <= cut or i == len(cuts) - 1)
        _, mean, sd = components[index]
        value = mean + sd * _normals(rng, 1)[0]
        if lo <= value <= hi:
            values.append(value)
    return tuple(values)


# =====================================================================
# statistics
# =====================================================================


def _quantile(ordered: Sequence[float], q: float) -> float:
    """The type-7 quantile -- linear interpolation between order statistics,
    which is what R, numpy and every box plot a reader has seen use."""
    n = len(ordered)
    if n == 0:
        raise ValueError("no data to take a quantile of")
    if n == 1:
        return ordered[0]
    pos = (n - 1) * q
    low = math.floor(pos)
    high = min(low + 1, n - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (pos - low)


def _stdev(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))


def _silverman(values: Sequence[float]) -> float:
    """Silverman's rule of thumb: 0.9 * min(s, IQR/1.349) * n^(-1/5).

    The IQR term is what keeps a bimodal sample from being smoothed into one
    hump -- the standard deviation of a two-humped sample is large because the
    humps are far apart, not because either hump is wide.
    """
    ordered = sorted(values)
    n = len(ordered)
    spread = _stdev(ordered)
    iqr = _quantile(ordered, 0.75) - _quantile(ordered, 0.25)
    sigma = min(spread, iqr / 1.349) if iqr > 0 else spread
    if sigma <= 0:
        sigma = spread if spread > 0 else 1.0
    return 0.9 * sigma * n ** -0.2


def _kde(values: Sequence[float], grid: Sequence[float], bandwidth: float) -> list[float]:
    """A Gaussian-kernel density estimate evaluated on `grid`."""
    norm = 1.0 / (len(values) * bandwidth * math.sqrt(2.0 * math.pi))
    out = []
    for g in grid:
        acc = 0.0
        for v in values:
            z = (g - v) / bandwidth
            if abs(z) < 6.0:          # past six sigma the kernel is 1e-8 of its peak
                acc += math.exp(-0.5 * z * z)
        out.append(acc * norm)
    return out


def _box_stats(values: Sequence[float]) -> dict:
    """Quartiles, 1.5-IQR whiskers and the points outside them."""
    ordered = sorted(values)
    q1 = _quantile(ordered, 0.25)
    q2 = _quantile(ordered, 0.50)
    q3 = _quantile(ordered, 0.75)
    iqr = q3 - q1
    low_fence, high_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = [v for v in ordered if low_fence <= v <= high_fence]
    return {
        "q1": q1, "median": q2, "q3": q3,
        "low": min(inside) if inside else q1,
        "high": max(inside) if inside else q3,
        "outliers": tuple(v for v in ordered if v < low_fence or v > high_fence),
    }


def _beeswarm(positions: Sequence[float], diameter: float) -> list[float]:
    """Perpendicular offsets that keep every disc `diameter` from every other.

    The algorithm is the one the R `beeswarm` package calls "swarm": take the
    points in order along the value axis and give each the offset of smallest
    magnitude that clears everything already placed. A placed point at distance
    `d` along the axis forbids an interval of half-width sqrt(D^2 - d^2) around
    its own offset, so the candidate offsets are zero and the edges of those
    forbidden intervals -- there is never any reason to sit further out than
    the first free edge.
    """
    order = sorted(range(len(positions)), key=lambda i: (positions[i], i))
    offsets = [0.0] * len(positions)
    placed: list[tuple[float, float]] = []
    for index in order:
        at = positions[index]
        blocked = []
        for other, offset in placed:
            gap = abs(at - other)
            if gap < diameter - _EPS:
                half = math.sqrt(diameter * diameter - gap * gap)
                blocked.append((offset - half, offset + half))
        chosen = 0.0
        if not _clear(0.0, blocked):
            candidates = [edge for pair in blocked for edge in pair]
            free = [c for c in candidates if _clear(c, blocked)]
            if free:
                chosen = min(free, key=lambda c: (abs(c), c))
        offsets[index] = chosen
        placed.append((at, chosen))
    return offsets


def _clear(value: float, blocked: Sequence[tuple[float, float]]) -> bool:
    return all(value <= lo + 1e-7 or value >= hi - 1e-7 for lo, hi in blocked)


# =====================================================================
# path geometry the library has no idiom for
# =====================================================================

Cubic = tuple[Vec2, Vec2, Vec2, Vec2]

#: The Sankey band this panel used to compute by hand. It ships as
#: `inklet.plot.ribbon_cubics` now, argument for argument and tension for ease,
#: and produces the identical outline; what is left here is the arc and chord
#: geometry, which the library still has no idiom for.
_ribbon = ribbon_cubics


def _arc_cubics(radius: float, start: float, end: float,
                centre: Vec2 = Vec2(0.0, 0.0), max_span: float = 90.0) -> tuple[Cubic, ...]:
    """A circular arc as cubics, degrees from east, clockwise (y grows down).

    `inklet.arc` draws one; nothing public hands back the control points, and a
    chord ribbon needs them because its outline is two arcs and two bridges in
    a single subpath.
    """
    sweep = end - start
    if abs(sweep) <= _EPS:
        return ()
    count = max(1, math.ceil(abs(sweep) / max_span - 1e-9))
    step = sweep / count
    k = 4.0 / 3.0 * math.tan(math.radians(step) / 4.0) * radius
    chain: list[Cubic] = []
    for i in range(count):
        a0 = math.radians(start + step * i)
        a1 = math.radians(start + step * (i + 1))
        p0 = centre + Vec2(math.cos(a0), math.sin(a0)) * radius
        p3 = centre + Vec2(math.cos(a1), math.sin(a1)) * radius
        chain.append((
            p0,
            p0 + Vec2(-math.sin(a0), math.cos(a0)) * k,
            p3 - Vec2(-math.sin(a1), math.cos(a1)) * k,
            p3,
        ))
    return tuple(chain)


def _chord(radius: float, source: tuple[float, float],
           target: tuple[float, float]) -> tuple[Cubic, ...]:
    """The classic chord ribbon: two arcs joined by two curves through the centre.

    Each bridge is a quadratic whose control point is the circle's centre --
    that is what makes short chords hug the rim and long ones dive across --
    written here in its exact cubic form, where a quadratic's control C lifts
    to (P0 + 2C)/3 and (P3 + 2C)/3, and C is the origin.
    """
    src = _arc_cubics(radius, *source)
    dst = _arc_cubics(radius, *target)
    if not src or not dst:
        return ()
    a0, a1 = src[0][0], src[-1][3]
    b0, b1 = dst[0][0], dst[-1][3]
    third = 1.0 / 3.0
    return (src
            + ((a1, a1 * third, b0 * third, b0),)
            + dst
            + ((b1, b1 * third, a0 * third, a0),))


def _closed_path(chain: Sequence[Cubic], **style) -> Diagram:
    return inklet.path(curves=chain, closed=True, filled=True, **style)


def _rect(x0: float, y0: float, x1: float, y1: float, **style) -> Diagram:
    return inklet.polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1)), **style)


# =====================================================================
# small shared helpers
# =====================================================================


def _text(content: str, size: float, **style) -> Diagram:
    return inklet.text(content, size=size, kind="label", **style)


def _tiny(th) -> float:
    """The smallest type these panels use: annotation that has to fit inside
    the geometry rather than beside it.

    A fraction of the theme's own small size, not a pinned `pt(5)`. Five point
    is the floor for the print theme and nonsense for the slide one, and a
    panel that hardcodes it stops being rethemeable the moment anyone tries.
    """
    return th.font_size_small * 0.86


def _turned(node: Diagram, degrees: float, at: Vec2, side: str) -> tuple[Vec2, Diagram]:
    """A rotated label placed by an edge of the box it *actually* occupies.

    `anchor_point` reads the local bounding box, which for a rotated node is
    the box before the rotation, so `place(..., anchor="n")` on a node turned
    on its side lands the middle of one of its long edges instead of the top of
    the turned glyph. The offset is therefore taken from the rotated bbox here
    and applied to the centre, which is the one anchor rotation cannot move.
    """
    turned = node.rotated(degrees)
    box = turned.bbox
    step = {"n": Vec2(0.0, box.height / 2.0), "s": Vec2(0.0, -box.height / 2.0),
            "w": Vec2(box.width / 2.0, 0.0), "e": Vec2(-box.width / 2.0, 0.0)}[side]
    return (at + step, turned)


def _left_furniture(th, tick_texts: Sequence[str], axis_label: str) -> float:
    """How far a left axis reaches out from its spine.

    Reproduces `plot.axis`'s own arithmetic -- tick reach, tick pad, widest
    label, label pad, rotated axis name -- so a panel can subtract it from the
    width it was asked for instead of guessing at a margin.
    """
    reach = 0.55 * th.font_size + 0.35 * th.font_size
    widest = max(_text(t, th.font_size_small).bbox.width for t in tick_texts)
    name = inklet.text(axis_label, size=th.font_size).rotated(-90.0).bbox.width
    return reach + widest + 0.5 * th.font_size + name


# =====================================================================
# j -- violin + box + swarm, with stacked significance brackets
# =====================================================================

#: name, sample size, and the mixture of normals the orientation-selectivity
#: index is drawn from. AL is genuinely bimodal and RL has a low tail; a KDE
#: that smoothed either away would be the thing this panel is here to catch.
_OSI_GROUPS = (
    ("V1", 54, ((1.00, 0.62, 0.13),)),
    ("LM", 48, ((1.00, 0.55, 0.15),)),
    ("AL", 44, ((0.58, 0.36, 0.09), (0.42, 0.73, 0.08))),
    ("PM", 41, ((1.00, 0.45, 0.17),)),
    ("RL", 37, ((0.88, 0.71, 0.10), (0.12, 0.23, 0.06))),
)

#: (left group, right group, annotation). Deliberately overlapping spans, so
#: the third bracket has to find a level above the other two.
_OSI_TESTS = ((0, 1, "n.s."), (2, 4, "*"), (0, 3, "**"))

_OSI_TICKS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
_KDE_GRID = 96


def _osi_samples() -> tuple[tuple[str, tuple[float, ...]], ...]:
    return tuple(
        (name, _mixture(4100 + index, count, components, 0.02, 0.99))
        for index, (name, count, components) in enumerate(_OSI_GROUPS)
    )


def _density_profile(values: Sequence[float]) -> tuple[list[float], list[float]]:
    """The KDE of a sample on a grid, cut one bandwidth past its extremes and
    trimmed to the range the quantity can physically take.

    Seaborn's default is two bandwidths, which on a bounded index draws a
    several-millimetre taper of essentially zero width -- it reads as a spike
    rather than as the tail it is. One bandwidth is where the Gaussian kernel
    has already given up 40% of its height, so the outline still closes softly
    but does so within sight of the data.
    """
    bandwidth = _silverman(values)
    lo = max(0.0, min(values) - bandwidth)
    hi = min(1.0, max(values) + bandwidth)
    grid = [lo + (hi - lo) * i / (_KDE_GRID - 1) for i in range(_KDE_GRID)]
    return grid, _kde(values, grid, bandwidth)


def _violin_outline(grid: Sequence[float], density: Sequence[float], centre: float,
                    half: float, peak: float, to_mm) -> list[Vec2]:
    """The mirrored profile as one closed ring in panel millimetres.

    The two apex points appear once, not twice: a repeated knot is a
    zero-length segment, and a Catmull-Rom tangent taken across one is a
    division waiting to happen.
    """
    widths = [half * d / peak for d in density]
    right = [Vec2(centre + w, to_mm(g)) for w, g in zip(widths, grid)]
    left = [Vec2(centre - w, to_mm(g)) for w, g in zip(widths, grid)]
    return right + left[-2:0:-1]


def _bracket_layout(tests, centres, extents, tops, clearance, label_gap,
                    make_label):
    """Stack significance brackets over an occupancy profile.

    The profile starts as the drawn extent of every group -- violin, whiskers,
    outliers and all -- so the first bracket already clears the data. Each
    bracket is then pushed back into the profile as a span whose top is the top
    of its *label*, which is what makes the next one stack instead of overlap.
    Narrow spans are placed first so a wide bracket rises over a nested one
    rather than cutting through it.
    """
    profile = [(extents[i][0], extents[i][1], tops[i]) for i in range(len(centres))]
    placed = []
    for left, right, mark in sorted(tests, key=lambda t: (t[1] - t[0], t[0])):
        x0, x1 = centres[left], centres[right]
        lo, hi = min(x0, x1), max(x0, x1)
        ceiling = min((top for a, b, top in profile if b > lo - _EPS and a < hi + _EPS),
                      default=0.0)
        bar = ceiling - clearance
        node = make_label(mark)
        height = node.bbox.height
        placed.append((x0, x1, bar, node, height))
        profile.append((lo, hi, bar - label_gap - height))
    return placed


def panel_j(width: float = CONTENT_WIDTH) -> Diagram:
    """Orientation selectivity across five areas: violin, box, swarm, stats."""
    th = inklet.current_theme()
    groups = _osi_samples()
    names = tuple(name for name, _ in groups)
    stats = [_box_stats(values) for _, values in groups]

    tick_texts = tuple(f"{t:.1f}" for t in _OSI_TICKS)
    area_w = width - _left_furniture(th, tick_texts, "orientation selectivity")
    area_h = width * _ASPECT_J

    # Tiers are kept to the label plus a hair: the separation a reader needs
    # between two brackets is that they do not touch, not a blank line.
    bar_tick = th.gap("2xs") * 1.5          # how far a bracket's legs drop
    label_gap = 0.20 * th.font_size
    clearance = bar_tick + 0.30 * th.font_size
    return _build_osi(th, groups, stats, names, area_w, area_h,
                      bar_tick, label_gap, clearance)


def _build_osi(th, groups, stats, names, area_w, area_h, bar_tick,
               label_gap, clearance):
    """Panel j, in one pass.

    The y domain is the range the index can take, not the range this sample
    happens to reach: an orientation selectivity of 1.0 is a real number and
    the axis should arrive at it. That leaves the significance brackets to
    stack in the margin above the area, which is where they belong -- pushing
    the axis past 1.0 to make room inside would be an axis inventing headroom
    the quantity does not have, and it costs a third of the panel's height.
    """
    panel = inklet.panel(area_w, area_h, x=names, y=(0.0, 1.0))
    xs, ys = panel.x, panel.y
    half = xs.bandwidth * 0.46
    swarm_size = 0.66
    swarm_step = swarm_size + 0.14

    # One density scale for all five, so the widths compare. Per-group
    # normalisation would make every violin the same width and quietly throw
    # away the fact that PM is spread over twice the range V1 is.
    profiles = [_density_profile(values) for _, values in groups]
    peak = max(max(density) for _, density in profiles)

    # The rule at zero would be drawn exactly under the x spine, which is a
    # hairline doubled up rather than a gridline.
    panel.under(*[
        inklet.polyline(((-area_w / 2, ys.map(t)), (area_w / 2, ys.map(t))),
                     kind="gridline")
        for t in _OSI_TICKS if t > 0.0
    ])

    tops: list[float] = []
    extents: list[tuple[float, float]] = []
    centres: list[float] = []
    for index, (name, values) in enumerate(groups):
        centre = xs.map(name)
        centres.append(centre)
        outline = _violin_outline(*profiles[index], centre, half, peak, ys.map)
        tint = inklet.ramp((th.paper, th.color(index)))(0.30)
        panel.draw(inklet.curve(outline, smooth=0.5, closed=True,
                             fill=tint, stroke=th.ink_color(index),
                             stroke_width=th.stroke, filled=True))

        offsets = _beeswarm([ys.map(v) for v in values], swarm_step)
        panel.draw(inklet.place([
            (Vec2(centre + off, ys.map(v)),
             inklet.marker("circle", swarm_size, fill=th.ink_color(index),
                        opacity=0.55))
            for off, v in zip(offsets, values)
        ]))

        stat = stats[index]
        box_half = max(half * 0.30, 0.9)
        panel.draw(
            inklet.polyline(((centre, ys.map(stat["low"])),
                          (centre, ys.map(stat["high"]))),
                         stroke=th.ink, stroke_width=th.stroke),
            *[inklet.polyline(((centre - box_half * 0.55, ys.map(v)),
                            (centre + box_half * 0.55, ys.map(v))),
                           stroke=th.ink, stroke_width=th.stroke)
              for v in (stat["low"], stat["high"])],
            _rect(centre - box_half, ys.map(stat["q1"]),
                  centre + box_half, ys.map(stat["q3"]),
                  fill="none", stroke=th.ink, stroke_width=th.stroke, filled=False),
            inklet.polyline(((centre - box_half, ys.map(stat["median"])),
                          (centre + box_half, ys.map(stat["median"]))),
                         stroke=th.ink, stroke_width=th.thick),
        )
        if stat["outliers"]:
            panel.draw(inklet.place([
                (Vec2(centre, ys.map(v)),
                 inklet.marker("circle", swarm_size * 1.5, fill="none",
                            stroke=th.ink, stroke_width=th.hairline))
                for v in stat["outliers"]
            ]))

        reach = max(offsets, default=0.0)
        pull = min(offsets, default=0.0)
        extents.append((min(centre - half, centre + pull - swarm_size),
                        max(centre + half, centre + reach + swarm_size)))
        tops.append(min([p.y for p in outline]
                        + [ys.map(v) - swarm_size for v in values]
                        + [ys.map(v) - swarm_size for v in stat["outliers"]]))

    brackets = _bracket_layout(
        _OSI_TESTS, centres, extents, tops, clearance, label_gap,
        lambda mark: _text(mark, th.font_size_small,
                           font_weight="bold" if mark != "n.s." else None))

    for x0, x1, bar, node, height in brackets:
        panel.over(
            inklet.polyline(((x0, bar + bar_tick), (x0, bar), (x1, bar),
                          (x1, bar + bar_tick)),
                         stroke=th.ink, stroke_width=th.hairline),
            inklet.place([(Vec2((x0 + x1) / 2.0, bar - label_gap - height / 2.0), node)]),
        )

    panel.axis("bottom", label="visual area")
    panel.axis("left", label="orientation selectivity", ticks=_OSI_TICKS)
    return panel.build()


# =====================================================================
# l -- Sankey: the data-reduction cascade
# =====================================================================

#: label, count with its unit, share of the starting cohort still flowing, and
#: why the previous stage lost what it lost. The shares are the products of the
#: per-stage retentions quoted in the drop labels, so the widths and the
#: numbers cannot disagree.
_CASCADE = (
    ("movies acquired", "118 movies", 100.00, None),
    ("motion corrected", "104 movies", 88.14, "motion > 5 µm\n(14 movies)"),
    ("ROIs segmented", "8 610 ROIs", 77.10, "ROI QC fail\n(1 232 ROIs)"),
    ("somata", "7 341 cells", 65.74, "not a soma\n(1 269 ROIs)"),
    ("visually responsive", "3 962 cells", 35.48, "no visual drive\n(3 379 cells)"),
    ("orientation tuned", "1 888 cells", 16.90, "OSI < 0.3\n(2 074 cells)"),
)

#: Of the width left after the node labels, how much the flow itself gets. The
#: rest pays for the drop-off stubs and their reasons. There is no layout
#: engine for "three columns of different natures", so this is a judgement
#: call written down rather than a computed one -- see the gaps file.
_FLOW_SHARE = 0.50


def panel_l(width: float = CONTENT_WIDTH) -> Diagram:
    """Where the data goes: a vertical Sankey with drop-off branches."""
    th = inklet.current_theme()
    gap = th.gap("s")
    small = th.font_size_small

    names = [_text(f"{name}\n{count}", small, align="right")
             for name, count, _, _ in _CASCADE]
    label_w = max(n.bbox.width for n in names)

    drops = [prev - here for prev, here in
             zip([s[2] for s in _CASCADE], [s[2] for s in _CASCADE][1:])]
    # What the three columns are not: the node labels' gap to the bars, the
    # flow's gap to the drop stubs, and the stubs' gap to their reasons. Naming
    # it here rather than guessing at 3 gaps is the difference between the
    # panel measuring 84.0 and measuring 83.4.
    margins = gap + gap + gap * 0.7
    # The floors are what stops a theme whose type is twice as big as this
    # width can carry from producing a zero-width flow: the panel overruns its
    # measure instead, which is at least visible.
    spare = max(width * 0.35, width - label_w - margins)

    def split(reason_w: float) -> tuple[float, float, float]:
        flow = max(spare * 0.25, (spare - reason_w) / (1.0 + max(drops) / 100.0))
        return flow, flow * max(drops) / 100.0, reason_w

    # Wrapped text almost never fills the measure it was given, and the slack
    # is worth more to the ribbons than to the right margin: allot, measure
    # what the reasons really took, and give the difference back to the flow.
    # Narrowing the allotment to a width the text already fits inside cannot
    # change where it breaks, so one correction is exact rather than iterative.
    flow_w = spare * _FLOW_SHARE
    reasons = [inklet.text(stage[3], size=_tiny(th), align="left", kind="label",
                        width=spare - flow_w * (1.0 + max(drops) / 100.0))
               .styled(text_fill=th.muted)
               for stage in _CASCADE[1:]]
    flow_w, drop_zone, reason_w = split(max(r.bbox.width for r in reasons))

    stages = len(_CASCADE)
    area_h = width * _ASPECT_L
    panel = inklet.panel(flow_w, area_h, x=(0.0, 100.0), y=(float(stages - 1), 0.0))
    xs, ys = panel.x, panel.y
    bar_h = 1.2
    stub_right = flow_w / 2.0 + gap + drop_zone
    flow = inklet.ramp((th.color(2), th.color(5)))

    for index, (name, count, share, reason) in enumerate(_CASCADE):
        y = ys.map(index)
        panel.draw(_rect(xs.map(0.0), y - bar_h / 2.0, xs.map(share), y + bar_h / 2.0,
                         fill=th.ink, stroke="none"))
        panel.draw(inklet.place([
            (Vec2(xs.map(0.0) - gap, y), names[index]),
        ], anchor="e"))
        panel.draw(inklet.place([
            (Vec2(xs.map(share) + 0.8, y),
             _text(f"{share:.0f} %", _tiny(th)).styled(text_fill=th.muted)),
        ], anchor="w"))

        if index + 1 == stages:
            continue
        nxt = _CASCADE[index + 1][2]
        lost = share - nxt
        top = y + bar_h / 2.0
        bottom = ys.map(index + 1) - bar_h / 2.0

        # The retained ribbon: full width at both ends, left-aligned like the
        # bars, so what survives stays on one edge and the losses peel off the
        # other. Ordered first because it leaves the node first.
        panel.draw(_closed_path(
            _ribbon(Vec2(xs.map(0.0), top), Vec2(xs.map(nxt), top),
                    Vec2(xs.map(0.0), bottom), Vec2(xs.map(nxt), bottom),
                    Vec2(0.0, 1.0)),
            fill=flow((index + 1) / (stages - 1)), stroke="none", opacity=0.72))

        # The drop-off, stacked immediately outboard of the retained flow at
        # the node it leaves and right-aligned at its stub, so every reason
        # starts at the same x however big its loss.
        stub_y = y + (ys.map(index + 1) - y) * 0.56
        panel.draw(_closed_path(
            _ribbon(Vec2(xs.map(nxt), top), Vec2(xs.map(share), top),
                    Vec2(stub_right - lost / 100.0 * flow_w, stub_y - bar_h / 2.0),
                    Vec2(stub_right, stub_y - bar_h / 2.0),
                    Vec2(0.0, 1.0), ease=0.42),
            fill=th.color(6), stroke="none", opacity=0.55))
        panel.draw(_rect(stub_right - lost / 100.0 * flow_w, stub_y - bar_h / 2.0,
                         stub_right, stub_y + bar_h / 2.0,
                         fill=th.color(6), stroke="none"))
        panel.draw(inklet.place([
            (Vec2(stub_right + gap * 0.7, stub_y), reasons[index]),
        ], anchor="w"))

    panel.title("data reduction — ribbon width ∝ cohort retained")
    return panel.build()


# =====================================================================
# m -- chord diagram of inter-areal connectivity
# =====================================================================

#: Ordered along the cortical hierarchy, so index distance means something and
#: the seeded matrix below can use it.
_AREAS = ("V1", "LM", "AL", "RL", "AM", "PM", "LI", "POR")

#: How much projection each area sends overall, relative to V1.
_AREA_WEIGHT = (1.00, 0.62, 0.55, 0.48, 0.40, 0.46, 0.34, 0.30)

_CHORD_SEED = 7717

#: Blank degrees between neighbouring arcs, so the ring reads as eight areas
#: rather than as one wheel.
_ARC_GAP_DEG = 2.4

#: The strengths the key shows, as a percentage of all inter-areal projections.
#: The data runs from 0.44 % to 15.8 %, so these bracket it.
_CHORD_KEY = (15.0, 5.0, 1.0)


def _connectivity() -> list[list[float]]:
    """A symmetric projection-density matrix.

    Strength falls off with distance along the hierarchy and scales with how
    much each end projects at all, then gets a seeded jitter so the picture is
    not a smooth gradient pretending to be a measurement.
    """
    rng = random.Random(_CHORD_SEED)
    n = len(_AREAS)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            base = _AREA_WEIGHT[i] * _AREA_WEIGHT[j]
            near = math.exp(-abs(i - j) / 2.6)
            value = base * near * (0.45 + 1.1 * rng.random())
            matrix[i][j] = matrix[j][i] = value
    return matrix


def panel_m(width: float = CONTENT_WIDTH) -> Diagram:
    """Who talks to whom: arcs sized by total connectivity, chords by strength.

    A ring is as tall as it is wide, so a chord diagram given a whole column
    comes out square and eats a third of the page. The key beside it is not
    filler: a chord's thickness is the one quantity in this panel that nothing
    else states, and pinning it to a column of the width the ring itself would
    give those strengths lets the circle come down to four-thirds without any
    of it being decoration.

    The radius is solved rather than chosen: labels stand off the rim in eight
    different directions, so how much of the budget the circle may take depends
    on which label points sideways. Two corrections converge -- the drawing's
    width is the radius plus a constant that only depends on the labels, and
    both are known once it has been built once.
    """
    th = inklet.current_theme()
    pad = th.gap("s")
    reach = max(_text(name, th.font_size_small).bbox.width for name in _AREAS)
    outer = (width - width * 0.24) / 2.0 - reach - pad
    for _ in range(10):
        # The key is a function of the radius -- its swatches are drawn at the
        # thickness this ring gives them -- so the column it wants and the room
        # left for the circle chase each other. Both move linearly in the
        # radius and 2.7 is the sum of the two slopes, so the residual falls by
        # about three quarters a pass and ten passes land inside a micron.
        budget = width - _chord_key(th, outer).bbox.width - pad
        error = budget - _build_chord(th, outer, pad).bbox.width
        if abs(error) < 0.005:
            break
        outer += error / 2.7
    return inklet.hstack([_build_chord(th, outer, pad), _chord_key(th, outer)],
                      gap=pad, align="center")


def _swatch_thickness(inner: float, share: float) -> float:
    """How thick the ring draws a chord carrying `share` percent of the total.

    A foot's angular width is `usable * m[i][j] / grand` -- the arc's own span
    cancels out of it -- so thickness depends on the strength alone and the key
    can be exact rather than illustrative.
    """
    usable = 360.0 - len(_AREAS) * _ARC_GAP_DEG
    return inner * math.radians(usable * share / 200.0)


def _key_text(th, content: str, measure: float) -> Diagram:
    return inklet.text(content, size=_tiny(th), align="left", kind="label",
                    width=measure).styled(text_fill=th.muted)


_KEY_HEAD = "chord width ∝ share of all inter-areal projections"
_KEY_FOOT = "arc ∝ each area's own total"


def _chord_key(th, outer: float) -> Diagram:
    """Three chords at their true drawn thickness, with the share each is.

    The column is sized from the widest swatch rather than chosen: a band that
    is not plainly longer than it is thick reads as a bar, and the quantity
    here is the thickness. A wider key also buys height back -- every
    millimetre it takes is a millimetre off the diameter of a shape that is as
    tall as it is wide. Stacked tight the swatches read as a stepped bar chart
    for the same reason, so they get a full gap and the paper hairline the
    ring's own chords carry.
    """
    inner = outer - _rim(th, outer)
    length = _swatch_thickness(inner, max(_CHORD_KEY)) * 2.2
    numbers = max(_text(f"{s:g} %", _tiny(th)).bbox.width for s in _CHORD_KEY)
    key_w = length + th.gap("2xs") + numbers
    rows = [
        inklet.hstack([
            _rect(-length / 2.0, -_swatch_thickness(inner, share) / 2.0,
                  length / 2.0, _swatch_thickness(inner, share) / 2.0,
                  fill=th.color(1), stroke=th.paper,
                  stroke_width=th.hairline, opacity=0.45),
            _text(f"{share:g} %", _tiny(th)).styled(text_fill=th.muted),
        ], gap=th.gap("2xs"), align="center")
        for share in _CHORD_KEY
    ]
    return inklet.vstack(
        [_key_text(th, _KEY_HEAD, key_w)] + rows + [_key_text(th, _KEY_FOOT, key_w)],
        gap=th.gap("xs"), align="left")


def _rim(th, outer: float) -> float:
    """How thick the arcs around the rim are drawn."""
    return max(th.gap("s"), outer * 0.062)


def _build_chord(th, outer: float, pad: float) -> Diagram:
    matrix = _connectivity()
    n = len(_AREAS)
    totals = [sum(row) for row in matrix]
    grand = sum(totals)

    labels = [_text(name, th.font_size_small) for name in _AREAS]
    inner = outer - _rim(th, outer)

    # Angles: a fixed gap between neighbouring arcs, the rest shared out by
    # total connectivity. Twelve o'clock is -90 because y grows downward.
    gap_deg = _ARC_GAP_DEG
    usable = 360.0 - n * gap_deg
    starts: list[float] = []
    spans: list[float] = []
    cursor = -90.0 + gap_deg / 2.0
    for i in range(n):
        span = usable * totals[i] / grand
        starts.append(cursor)
        spans.append(span)
        cursor += span + gap_deg

    # Every area's arc is subdivided into one slot per partner, in a fixed
    # order, so a chord's two feet are reproducible and never overlap another
    # chord's foot on the same arc.
    slots: list[list[tuple[float, float]]] = []
    for i in range(n):
        at = starts[i]
        row: list[tuple[float, float]] = []
        for j in range(n):
            width_deg = spans[i] * matrix[i][j] / totals[i]
            row.append((at, at + width_deg))
            at += width_deg
        slots.append(row)

    items: list[Diagram] = []
    # Strongest chords first so they sit at the bottom of the stack: a wide
    # ribbon covers more of its neighbours than they cover of it, and the eye
    # should read the strong connection as the one underneath everything.
    #
    # Colour comes from the *quieter* end of each pair. The convention is to
    # colour by the source, but the source here is always the hub -- eight of
    # the twenty-eight chords would be one colour, and that colour is the
    # palette's black. Taking the partner's colour makes "who V1 talks to"
    # legible, which is the question the panel is for.
    pairs = sorted(((matrix[i][j], i, j) for i in range(n) for j in range(i + 1, n)),
                   key=lambda p: (-p[0], p[1], p[2]))
    for _, i, j in pairs:
        chain = _chord(inner, slots[i][j], slots[j][i])
        if not chain:
            continue
        quiet = j if totals[i] >= totals[j] else i
        items.append(_closed_path(chain, fill=th.color(quiet), stroke=th.paper,
                                  stroke_width=th.hairline, opacity=0.45))

    for i in range(n):
        items.append(inklet.sector(outer, starts[i], starts[i] + spans[i],
                                inner=inner, fill=th.color(i), stroke=th.paper,
                                stroke_width=th.hairline))
        mid = starts[i] + spans[i] / 2.0
        items.append(_radial_label(labels[i], mid, outer + pad))

    # Everything in the ring touches on purpose: chord feet tile each arc with
    # no gap, a ribbon lies against the two it passes, and the labels stand off
    # the rim by the one `pad` this panel solves for. `inklet.lint` reported
    # thirty-four of those as CROWDING; the declaration says they are the
    # drawing, and leaves the ring still answerable to the key beside it.
    return inklet.place(items, kind=inklet.abutting("chords"))


def _radial_label(node: Diagram, angle: float, radius: float) -> tuple[Vec2, Diagram]:
    """A label reading outward along its own radius, flipped where it would
    otherwise be upside down.

    Rotating by the arc's mid-angle puts the baseline along the radius, which
    is legible on the right of the circle and upside down on the left. The fix
    is the usual one: add half a turn and let the text run inward-to-outward
    the other way, which keeps every label the same distance from the rim.
    """
    turn = ((angle + 90.0) % 360.0) - 90.0
    flipped = 90.0 < turn < 270.0
    reach = radius + node.bbox.width / 2.0
    direction = Vec2(math.cos(math.radians(angle)), math.sin(math.radians(angle)))
    return (direction * reach, node.rotated(angle + 180.0 if flipped else angle))


# =====================================================================
# n -- dendrogram over a real average-linkage clustering
# =====================================================================

#: leaf name, and the categorical annotation that goes in the strip beneath it.
_CELL_TYPES = (
    ("L2/3 IT-1", "IT"), ("L2/3 IT-2", "IT"), ("L4 IT-1", "IT"), ("L4 IT-2", "IT"),
    ("L5 IT-1", "IT"), ("L5 IT-2", "IT"), ("L6 IT-1", "IT"), ("L6 IT-2", "IT"),
    ("L5 ET", "deep proj."), ("L6 CT", "deep proj."), ("L6b", "deep proj."),
    ("Pvalb-1", "MGE"), ("Pvalb-2", "MGE"), ("Sst-1", "MGE"), ("Sst-2", "MGE"),
    ("Vip", "CGE"),
)

_CLASSES = ("IT", "deep proj.", "MGE", "CGE")

#: Latent centroid per class in the feature space the distances come from, and
#: how far the types of that class scatter around it. IT and deep-projecting
#: types sit closer to each other than either does to the interneurons, which
#: is what makes the four-cluster cut interesting rather than automatic.
#: The scatter is deliberately a substantial fraction of the separation: at
#: this ratio the clustering recovers the classes but strands one deep-layer IT
#: type among the projection types, which is what a real transcriptomic
#: dendrogram does and what makes the annotation strip worth reading.
_CLASS_CENTRE = {
    "IT": (2.80, 0.56, -0.42, 1.26, 0.14, -0.70),
    "deep proj.": (1.96, -1.26, 0.84, 0.56, -0.98, 0.28),
    "MGE": (-2.52, 1.54, 1.12, -1.68, 0.70, 1.26),
    "CGE": (-2.10, -1.96, -1.54, -0.84, 1.82, -1.12),
}
_CLASS_SCATTER = {"IT": 0.7125, "deep proj.": 0.54, "MGE": 0.45, "CGE": 0.4125}

_DENDRO_SEED = 5231
_DENDRO_CLUSTERS = 4


def _features() -> list[tuple[float, ...]]:
    rng = random.Random(_DENDRO_SEED)
    out = []
    for _, cls in _CELL_TYPES:
        centre = _CLASS_CENTRE[cls]
        scatter = _CLASS_SCATTER[cls]
        noise = _normals(rng, len(centre))
        out.append(tuple(c + scatter * z for c, z in zip(centre, noise)))
    return out


def _distances(points: Sequence[Sequence[float]]) -> list[list[float]]:
    n = len(points)
    out = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = math.sqrt(sum((a - b) ** 2 for a, b in zip(points[i], points[j])))
            out[i][j] = out[j][i] = d
    return out


def _average_linkage(distance: Sequence[Sequence[float]]):
    """UPGMA, updated by Lance-Williams.

    Merging i and j into a cluster of size ni+nj leaves
    d(k, ij) = (ni*d(k,i) + nj*d(k,j)) / (ni+nj) -- the mean of every pair of
    points across the two clusters, which is exactly what average linkage
    means and is why the update needs the sizes and nothing else.

    Ties go to the pair found first in the active list, which is ordered, so
    the tree is a pure function of the matrix.
    """
    n = len(distance)
    d = [list(row) for row in distance]
    active = list(range(n))
    size = {i: 1 for i in range(n)}
    node = {i: i for i in range(n)}
    merges = []
    for step in range(n - 1):
        best = None
        for a in range(len(active)):
            for b in range(a + 1, len(active)):
                i, j = active[a], active[b]
                if best is None or d[i][j] < best[0]:
                    best = (d[i][j], i, j)
        height, i, j = best
        merges.append((node[i], node[j], height, size[i] + size[j]))
        for k in active:
            if k in (i, j):
                continue
            blended = (size[i] * d[i][k] + size[j] * d[j][k]) / (size[i] + size[j])
            d[i][k] = d[k][i] = blended
        size[i] += size[j]
        node[i] = n + step
        active.remove(j)
    return merges


def _dendrogram(merges, leaves: int):
    """Leaf order, x position and height for every node in the tree."""
    children = {leaves + k: (m[0], m[1]) for k, m in enumerate(merges)}
    height = {leaves + k: m[2] for k, m in enumerate(merges)}
    root = leaves + len(merges) - 1

    order: list[int] = []
    stack = [root]
    while stack:                       # explicit, so a deep tree cannot recurse out
        node = stack.pop()
        if node < leaves:
            order.append(node)
        else:
            a, b = children[node]
            stack.extend((b, a))
    position = {leaf: float(i) for i, leaf in enumerate(order)}
    for k in range(len(merges)):
        node = leaves + k
        a, b = children[node]
        position[node] = (position[a] + position[b]) / 2.0
    return order, position, height, children, root


def _colour_below(root: int, cut: float, height, children, leaves: int):
    """Assign a cluster index to every node whose whole subtree is under `cut`.

    Walking down from the root and claiming the first subtree that fits is what
    makes the clusters contiguous in leaf order, which is what makes the
    colouring legible: a cluster is a block of the tree, not a scatter of it.
    """
    colour: dict[int, int] = {}
    clusters = 0
    stack = [root]
    ordered: list[int] = []
    while stack:
        node = stack.pop()
        ordered.append(node)
        if node >= leaves and height[node] >= cut:
            a, b = children[node]
            stack.extend((b, a))
    for node in ordered:
        if node in colour:
            continue
        if node >= leaves and height[node] >= cut:
            continue
        index = clusters
        clusters += 1
        sub = [node]
        while sub:
            here = sub.pop()
            colour[here] = index
            if here >= leaves:
                sub.extend(children[here])
    return colour


def panel_n(width: float = CONTENT_WIDTH) -> Diagram:
    """Cell types clustered by average linkage, cut into four groups."""
    th = inklet.current_theme()
    leaves = len(_CELL_TYPES)
    merges = _average_linkage(_distances(_features()))
    order, position, height, children, root = _dendrogram(merges, leaves)

    heights = sorted(m[2] for m in merges)
    # The cut that leaves exactly `_DENDRO_CLUSTERS` clusters sits between the
    # merge that would form the last one and the merge that would join two.
    cut = (heights[leaves - _DENDRO_CLUSTERS - 1] + heights[leaves - _DENDRO_CLUSTERS]) / 2.0
    colour = _colour_below(root, cut, height, children, leaves)
    top = max(heights)

    tick_texts = tuple(f"{v:.0f}" for v in (0, 2, 4, 6, 8))
    area_w = width - _left_furniture(th, tick_texts, "linkage distance")
    area_h = width * _ASPECT_N
    panel = inklet.panel(area_w, area_h, x=(-0.6, leaves - 0.4), y=(0.0, top * 1.06))
    xs, ys = panel.x, panel.y

    def at(node: int) -> tuple[float, float]:
        return position[node], height.get(node, 0.0)

    for k in range(len(merges)):
        node = leaves + k
        a, b = children[node]
        xa, ya = at(a)
        xb, yb = at(b)
        h = height[node]
        stroke = (th.ink_color(_CLUSTER_INK[colour[node]]) if node in colour
                  else th.muted)
        panel.draw(inklet.polyline(
            ((xs.map(xa), ys.map(ya)), (xs.map(xa), ys.map(h)),
             (xs.map(xb), ys.map(h)), (xs.map(xb), ys.map(yb))),
            stroke=stroke,
            stroke_width=th.thick if node in colour else th.stroke,
            stroke_linejoin="miter"))

    panel.over(inklet.polyline(((-area_w / 2, ys.map(cut)), (area_w / 2, ys.map(cut))),
                            stroke=th.accent, stroke_width=th.hairline,
                            stroke_dash=(1.1, 0.9)))
    # On a plate: wherever the cut lands, some branch above it is a vertical
    # line running the height of the panel, and a label with nothing behind it
    # gets a rule straight through the middle of a word.
    note = inklet.frame(_text(f"cut → {_DENDRO_CLUSTERS} clusters", _tiny(th))
                     .styled(text_fill=th.accent),
                     pad=th.gap("2xs"), kind="label-plate").styled(
                         fill=th.paper, stroke="none")
    panel.over(inklet.place([(Vec2(area_w / 2, ys.map(cut) - th.gap("2xs")), note)],
                         anchor="se"))

    # Furniture below the plot area: a categorical strip, then the leaf names
    # turned on their side because sixteen of them will not fit any other way.
    strip_top = area_h / 2.0 + th.gap("2xs")
    strip_h = th.gap("s") * 0.8
    chip_w = min(xs.map(1.0) - xs.map(0.0), 3.2) * 0.82
    class_ink = {name: _CLASS_FILL[i] for i, name in enumerate(_CLASSES)}
    for leaf in range(leaves):
        name, cls = _CELL_TYPES[leaf]
        x = xs.map(position[leaf])
        panel.draw(_rect(x - chip_w / 2, strip_top, x + chip_w / 2, strip_top + strip_h,
                         fill=_class_colour(th, class_ink[cls]), stroke="none"))
        panel.draw(inklet.place([
            _turned(_text(name, _tiny(th)), -90.0,
                    Vec2(x, strip_top + strip_h + th.gap("xs")), "n"),
        ]))

    panel.axis("left", label="linkage distance")
    key = inklet.legend([(cls, _class_colour(th, class_ink[cls])) for cls in _CLASSES],
                     columns=len(_CLASSES), swatch=th.gap("s") * 0.8)
    return inklet.vstack([panel.build(), key], gap=th.gap("s"), align="center")


#: Palette slots for the two categorical scales this panel has to carry at
#: once. A theme offers exactly one palette, so the branch colours and the
#: annotation colours are carved out of it by hand and kept disjoint.
_CLUSTER_INK = (5, 3, 7, 2)
_CLASS_FILL = (1, 6, 4, -1)


def _class_colour(th, slot: int) -> str:
    return th.muted if slot < 0 else th.color(slot)


# =====================================================================
# looking at it
# =====================================================================

if __name__ == "__main__":
    import dataclasses

    TH = inklet.use_theme(dataclasses.replace(inklet.theme("nature"),
                                           font_family="Noto Sans"))

    def lettered(letter: str, node: Diagram) -> Diagram:
        tag = inklet.text(letter, size=TH.font_size_large, font_weight="bold")
        return inklet.hstack([tag, node], gap=1.5, align="top")

    left = inklet.vstack([lettered("j", panel_j()), lettered("l", panel_l())],
                      gap=10, align="left")
    right = inklet.vstack([lettered("m", panel_m()), lettered("n", panel_n())],
                       gap=10, align="left")

    fig = inklet.figure(width=inklet.COLUMN_DOUBLE + 12.0)
    fig.add(inklet.hstack([left, right], gap=10, align="top"))
    fig.save("stress/panels/relations.svg")
    print(fig.report())
