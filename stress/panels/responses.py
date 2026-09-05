"""Response panels for the stress figure: raster, matrix, polar tuning, correlation.

Four panels of the same fictional study -- mouse visual cortex, two-photon
calcium imaging -- each there to break a different part of the engine.

    g   spike raster, ~10^4 marks + a zoomed inset with converging leaders
    h   response matrix as a heatmap, diverging ramp, colorbar, stipple for n.s.
    i   orientation tuning in polar coordinates, built from scratch
    k   correlation with a least-squares fit and a real confidence band

Two things are worth saying up front.

**The statistics are computed, not drawn.** The fit in (k) is an ordinary least
squares fit of the generated data; the band around it is the t-based confidence
interval for the mean response, from the residuals of that fit; the p-value is
the two-sided Student t tail, from a regularised incomplete beta evaluated
here. The significance mask in (h) is Benjamini-Hochberg over all 120 cells. A
band drawn to look plausible would prove nothing about a plotting library.

**Panel (g) is a volume experiment.** 10^4 marks is past the point where the
obvious construction works at all: `Envelope.union` chains one closure per
sibling and a support query recurses down the whole chain, so a panel with more
than 989 sibling marks raises `RecursionError` before it ever reaches the
renderer. The raster is therefore drawn as a handful of multi-subpath
`PathPrim`s -- one per layer group -- which for the same 10,239 ticks is also
6x smaller on disk, 16x faster to build and 32x faster to lint than the same
picture as one diagram per spike. `__main__` prints the measurements.
"""

from __future__ import annotations

import math
import random
from typing import Callable, Iterable, Sequence

import inklet
from inklet.core import Diagram, PathPrim, Rect, Subpath, Vec2

__all__ = ["panel_g", "panel_h", "panel_i", "panel_k"]

FULL_WIDTH = 178.0
COLUMN = 84.0


# =====================================================================
# small shared machinery
# =====================================================================


def _normal(rng: random.Random) -> float:
    """One standard normal. Box-Muller rather than `random.gauss`, which caches
    its second variate on the generator and so makes the value you get depend
    on how many normals anyone else drew first."""
    u1 = max(rng.random(), 1e-12)
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * rng.random())


def _fit_width(make: Callable[[float], Diagram], target: float,
               guess: float, passes: int = 6, tol: float = 0.02) -> Diagram:
    """Solve for the size parameter that makes the finished panel `target` wide.

    `inklet.panel(w, h)` sizes the plot *area*; the tick labels, the axis name and
    the colorbar hang outside it and nobody knows how wide they are until the
    text has been shaped. So the panel is built, measured, and rebuilt -- a
    secant search on "measured width as a function of the parameter", which
    needs no assumption about how the two are related. A polar plot's width
    grows at twice its radius and a scatter's at one times its area width;
    stepping by the raw error would oscillate on the first and crawl on the
    second.
    """
    x0 = guess
    node0 = make(x0)
    y0 = node0.bbox.width
    if abs(y0 - target) < tol or y0 <= 0:
        return node0
    best, error = node0, abs(y0 - target)
    x1 = max(x0 * target / y0, x0 * 0.05)
    node1 = make(x1)
    y1 = node1.bbox.width
    for _ in range(passes):
        if abs(y1 - target) < error:
            best, error = node1, abs(y1 - target)
        if abs(y1 - target) < tol or abs(y1 - y0) < 1e-9:
            break
        step = (target - y1) * (x1 - x0) / (y1 - y0)
        # A panel has furniture it cannot shrink -- a legend, a note, a
        # colorbar -- so below some width the measurement stops responding and
        # the secant's next guess runs off to zero or past it. Clamping the
        # step keeps the search inside the range where the answer can exist and
        # returns the closest fit instead of raising.
        x2 = min(max(x1 + step, x1 * 0.25), x1 * 4.0)
        x0, y0 = x1, y1
        x1, node1 = x2, make(x2)
        y1 = node1.bbox.width
    return node1 if abs(y1 - target) < error else best


def _at_origin(*items: Diagram) -> Diagram:
    """Group drawn nodes without moving them: each goes back to the coordinates
    it was drawn in, and the group's own frame is those coordinates."""
    return Diagram(children=tuple(inklet.align_to(i, "origin") for i in items),
                   kind="drawn")


def _corner(node: Diagram, area: Rect, where: str, pad: float) -> Diagram:
    """Put `node`'s own corner `pad` inside the matching corner of `area`.

    The offset is half the node's measured box, so an annotation sits against
    the corner of the plot however wide its text turns out to be.
    """
    box = node.bbox
    x = (area.x0 + pad + box.width / 2 if where in ("nw", "sw")
         else area.x1 - pad - box.width / 2)
    y = (area.y0 + pad + box.height / 2 if where in ("nw", "ne")
         else area.y1 - pad - box.height / 2)
    here = node.transform.apply(node.anchor_point("center"))
    return node.translated(x - here.x, y - here.y)


def _ticks_prim(segments: Iterable[tuple[Vec2, Vec2]], **style) -> Diagram:
    """Many two-point strokes as *one* node.

    `inklet.path` builds a single subpath, so ten thousand ticks would be ten
    thousand diagrams -- past the sibling ceiling `Envelope.union` imposes, and
    6x the bytes. `PathPrim` already holds a tuple of subpaths and the SVG
    backend already concatenates them into one `d`; this is the shortest way to
    reach that from outside the package.
    """
    subs = tuple(Subpath((a, b)) for a, b in segments)
    node = Diagram(prim=PathPrim(subs), kind="tick-mass")
    return node.styled(fill="none", **style)


_SUPERSCRIPT = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
_SUBSCRIPT = str.maketrans("0123456789-", "₀₁₂₃₄₅₆₇₈₉₋")


def _sci(value: float) -> str:
    """`3.4×10⁻²⁰`, with real superscript characters."""
    exponent = math.floor(math.log10(abs(value))) if value else 0
    mantissa = value / 10.0 ** exponent
    return f"{mantissa:.1f}×10{str(exponent).translate(_SUPERSCRIPT)}"


# -- the statistics ---------------------------------------------------


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Lentz's method)."""
    tiny, eps = 1e-300, 3e-16
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (tiny if abs(d) < tiny else d)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        for numerator in (m * (b - m) * x / ((qam + m2) * (a + m2)),
                          -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))):
            d = 1.0 + numerator * d
            d = 1.0 / (tiny if abs(d) < tiny else d)
            c = 1.0 + numerator / (tiny if abs(c) < tiny else c)
            h *= d * c
        if abs(d * c - 1.0) < eps:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                     + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def _t_two_sided(t: float, df: int) -> float:
    """P(|T| > |t|) for Student's t with `df` degrees of freedom."""
    return _betai(df / 2.0, 0.5, df / (df + t * t))


def _t_critical(alpha: float, df: int) -> float:
    """The t* with P(|T| > t*) = alpha. Bisection: 60 halvings of [0, 200]
    resolve t* to about 1e-16, which is far past what a band is drawn to."""
    lo, hi = 0.0, 200.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if _t_two_sided(mid, df) > alpha:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _normal_two_sided(z: float) -> float:
    return math.erfc(abs(z) / math.sqrt(2.0))


def _benjamini_hochberg(pvalues: Sequence[float], alpha: float = 0.05) -> float:
    """The largest p-value that survives BH at level `alpha`, or -1 if none do.

    Sorted ascending, the rule keeps every p(k) <= k/m * alpha up to the largest
    k that satisfies it -- so one threshold, applied to all m tests, is enough
    to say which cells are significant.
    """
    ordered = sorted(pvalues)
    m = len(ordered)
    kept = -1.0
    for k, p in enumerate(ordered, start=1):
        if p <= k / m * alpha:
            kept = p
    return kept


def _least_squares(points: Sequence[tuple[float, float]]):
    """Slope, intercept and everything a confidence band needs, from the data.

    Returns (slope, intercept, mean_x, sxx, residual_sd, r2, t_statistic).
    """
    n = len(points)
    mean_x = sum(p[0] for p in points) / n
    mean_y = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mean_x) ** 2 for p in points)
    sxy = sum((p[0] - mean_x) * (p[1] - mean_y) for p in points)
    syy = sum((p[1] - mean_y) ** 2 for p in points)
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    sse = syy - slope * sxy
    residual_sd = math.sqrt(sse / (n - 2))
    r2 = 1.0 - sse / syy
    t_stat = slope / (residual_sd / math.sqrt(sxx))
    return slope, intercept, mean_x, sxx, residual_sd, r2, t_stat


# =====================================================================
# g -- spike raster, full width, ~10^4 marks, with a zoomed inset
# =====================================================================

#: 60 neurons in three cortical layers, 5 s of recording, one grating from
#: 1000 to 3000 ms. Rates are per millisecond because the axis is milliseconds.
_G_NEURONS = 60
_G_LAYERS = (("L2/3", 20), ("L4", 20), ("L5", 20))
_G_SPAN = (0.0, 5000.0)
_G_STIM = (1000.0, 3000.0)
_G_ZOOM = (1000.0, 1200.0)
_G_BIN = 50.0


def _g_rate(t: float, gain: float) -> float:
    """Spikes per millisecond for one neuron at time t.

    Baseline, an onset transient that adapts with a 120 ms time constant down
    to a sustained plateau, and a smaller offset transient -- the shape a
    drifting grating actually pulls out of a V1 population.
    """
    on, off = _G_STIM
    rate = 0.014
    if on <= t < off:
        rate += 0.034 + 0.125 * math.exp(-(t - on) / 120.0)
    elif t >= off:
        rate += 0.050 * math.exp(-(t - off) / 90.0)
    return rate * gain


def _g_spikes() -> tuple[list[list[float]], int]:
    """One spike train per neuron, by thinning an inhomogeneous Poisson process.

    Thinning is the honest way to sample a time-varying rate: draw from a
    homogeneous process at the peak rate and keep each event with probability
    rate(t)/peak. The alternative -- binning and drawing counts -- puts every
    spike at a bin centre, which a raster shows as vertical stripes.
    """
    rng = random.Random(20260822)
    peak = 0.175
    trains: list[list[float]] = []
    for _ in range(_G_NEURONS):
        gain = 0.55 + 1.05 * rng.random()
        train: list[float] = []
        t = _G_SPAN[0]
        while True:
            t += -math.log(max(rng.random(), 1e-12)) / (peak * 1.7)
            if t >= _G_SPAN[1]:
                break
            if rng.random() < _g_rate(t, gain) / (peak * 1.7):
                train.append(t)
        trains.append(train)
    return trains, sum(len(s) for s in trains)


def _g_psth(trains: Sequence[Sequence[float]]) -> list[tuple[float, float]]:
    """Population firing rate in Hz per neuron, as the corners of a step."""
    bins = int((_G_SPAN[1] - _G_SPAN[0]) / _G_BIN)
    counts = [0] * bins
    for train in trains:
        for t in train:
            index = int((t - _G_SPAN[0]) / _G_BIN)
            if 0 <= index < bins:
                counts[index] += 1
    scale = 1000.0 / (_G_BIN * len(trains))
    steps: list[tuple[float, float]] = []
    for index, count in enumerate(counts):
        lo = _G_SPAN[0] + index * _G_BIN
        steps.append((lo, count * scale))
        steps.append((lo + _G_BIN, count * scale))
    return steps


def panel_g(width: float = FULL_WIDTH) -> Diagram:
    """Spike raster over a PSTH, with a zoomed inset called out by two leaders.

    The raster is the volume test: roughly 10^4 ticks. They are drawn as three
    multi-subpath paths, one per layer, because 10^4 sibling diagrams do not
    survive `Envelope.union`'s recursion -- see the module docstring.
    """
    th = inklet.current_theme()
    trains, _ = _g_spikes()
    psth = _g_psth(trains)
    top = max(v for _, v in psth)

    def make(area_w: float) -> Diagram:
        inset_w = 0.19 * width
        leader_gap = 0.055 * width
        raster_h, psth_h = 0.175 * width, 0.062 * width

        raster = inklet.panel(area_w, raster_h, x=_G_SPAN,
                           y=(-0.5, _G_NEURONS - 0.5))
        raster.background(fill=th.paper)
        _g_stimulus(raster, th, label=True)
        _g_ticks(raster, trains, th)
        _g_layer_labels(raster, th)
        raster.axis("left", label="neuron", count=4)

        # The window the inset magnifies, outlined over the ticks. Kept as a
        # handle: the leaders need to know where it lands after composition.
        source = inklet.polyline(_g_window(raster, _G_ZOOM), closed=True,
                              stroke=th.accent, stroke_width=th.stroke,
                              fill="none")
        raster.over(source)

        rates = inklet.panel(area_w, psth_h, x=_G_SPAN,
                          y=inklet.linear((0.0, top), nice=True))
        rates.background(fill=th.paper)
        _g_stimulus(rates, th, label=False)
        rates.draw(inklet.polygon(rates.map(_g_close(psth)),
                               fill=th.color(2), stroke="none", opacity=0.9))
        rates.line(psth, stroke=th.ink_color(2), stroke_width=th.hairline)
        rates.axes(x="time from stimulus onset / ms", y="rate / Hz",
                   count=6)

        inset = inklet.panel(inset_w, raster_h, x=_G_ZOOM,
                          y=(-0.5, _G_NEURONS - 0.5))
        inset.background(fill=th.paper)
        _g_ticks(inset, trains, th, window=_G_ZOOM, weight=th.stroke)
        inset.axis("bottom", label="time / ms", count=3)
        border = inklet.polyline(inset.area.corners, closed=True,
                              stroke=th.accent, stroke_width=th.stroke,
                              fill="none")
        inset.over(border)

        # Aligned on their tops, and with nothing above either plot area, the
        # raster and the inset present the same two edges to the leaders --
        # which is what lets the leaders leave the source window along the
        # boundary of the plot instead of dragging a rule across the data.
        body = inklet.hstack([inklet.column([raster, rates], gap=th.gap("xs")),
                           inset.build()], gap=leader_gap, align="top")
        return Diagram(children=(body, _g_leaders(body, source, border, th)),
                       kind="callout")

    return _fit_width(make, width, guess=0.62 * width)


def _g_window(panel: inklet.Panel, span: tuple[float, float]) -> tuple[Vec2, ...]:
    """The corners of a time window, in panel millimetres."""
    box = panel.area
    x0, x1 = panel.x.map(span[0]), panel.x.map(span[1])
    return (Vec2(x0, box.y0), Vec2(x1, box.y0),
            Vec2(x1, box.y1), Vec2(x0, box.y1))


def _g_stimulus(panel: inklet.Panel, th, *, label: bool) -> None:
    """The grating window as a pale band, its onset as a line."""
    panel.under(inklet.polygon(_g_window(panel, _G_STIM), fill=th.grid,
                            stroke="none"))
    box = panel.area
    onset = panel.x.map(_G_STIM[0])
    panel.over(inklet.polyline(((onset, box.y0), (onset, box.y1)),
                            stroke=th.accent, stroke_width=th.stroke,
                            fill="none"))
    if label:
        # Against the onset line rather than in a corner -- a caption for a
        # rule belongs on the rule -- and on the baseline side of it, because
        # the far side is where the zoom window and its leaders start.
        text = inklet.label("grating on", text_fill=th.accent)
        plate = inklet.frame(text, pad=0.4, kind="label-plate").styled(
            fill=th.paper, stroke="none")
        span = plate.bbox
        panel.over(plate.translated(
            onset - th.gap("xs") - span.width / 2 - span.center.x,
            box.y0 + th.gap("xs") + span.height / 2 - span.center.y))


def _g_rows(index: int) -> range:
    """Which raster rows belong to layer `index`.

    Rows count up the page but cortex is numbered down from the pia, so the
    layers are laid in reverse: L2/3 ends up at the top of the raster, where a
    reader expects the superficial cells to be.
    """
    start = sum(count for _, count in _G_LAYERS[index + 1:])
    return range(start, start + _G_LAYERS[index][1])


#: Palette slots for the three layers: orange, bluish green, reddish purple.
#: Deliberately not the palette's own blues -- the callout, the stimulus line
#: and the inset border are all `accent`, which in every theme here is a blue,
#: and a layer sharing that hue would read as part of the callout.
_G_SERIES = (1, 3, 7)


def _g_colour(index: int, th) -> str:
    """One colour per layer, dark enough to be read as *type*.

    `Theme.ink_color` defaults to a 3:1 contrast target, which is the threshold
    for a graphical object; the same hue also names the layer in a label, and
    text needs 4.5:1. Asking for the text ratio here keeps the ticks and their
    name exactly the same colour, which is the whole point of labelling in
    colour instead of adding a key.
    """
    return th.ink_color(_G_SERIES[index], min_ratio=4.5)


def _g_ticks(panel: inklet.Panel, trains, th, *,
             window: tuple[float, float] | None = None,
             weight: float | None = None) -> None:
    """Every spike as a two-point stroke, batched into one path per layer.

    A raster's rows are 0.4 mm apart at this size, so a tick reaches 36% of a
    row: any taller and neighbouring rows merge into a wash, any shorter and
    the sparse rows read as empty.
    """
    half = abs(panel.y.map(1) - panel.y.map(0)) * 0.36
    lo, hi = window if window is not None else _G_SPAN
    for index in range(len(_G_LAYERS)):
        segments = []
        for row in _g_rows(index):
            y = panel.y.map(row)
            for t in trains[row]:
                if lo <= t <= hi:
                    x = panel.x.map(t)
                    segments.append((Vec2(x, y - half), Vec2(x, y + half)))
        panel.draw(_ticks_prim(
            segments, stroke=_g_colour(index, th),
            stroke_width=th.hairline if weight is None else weight,
            stroke_linecap="butt"))


def _g_layer_labels(panel: inklet.Panel, th) -> None:
    """The layer each block of rows belongs to, named where the block is.

    A separate key would cost a line of figure height and make the reader look
    away from the raster to use it; the names go on the quiet post-stimulus end
    of each block instead, on opaque plates so a tick never runs through one.
    """
    box = panel.area
    for index, (name, _) in enumerate(_G_LAYERS):
        rows = _g_rows(index)
        text = inklet.label(name, text_fill=_g_colour(index, th))
        plate = inklet.frame(text, pad=0.4, kind="label-plate").styled(
            fill=th.paper, stroke="none")
        span = plate.bbox
        middle = panel.y.map((rows.start + rows.stop - 1) / 2)
        panel.over(plate.translated(
            box.x1 - th.gap("xs") - span.width / 2 - span.center.x,
            middle - span.center.y))


def _g_close(steps: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """A step outline closed down onto the baseline, so it can be filled as one
    polygon -- `PathPrim` has no fill rule, so the area under a curve has to be
    a single non-self-intersecting boundary."""
    return [(steps[0][0], 0.0)] + list(steps) + [(steps[-1][0], 0.0)]


def _g_leaders(body: Diagram, source: Diagram, border: Diagram, th) -> Diagram:
    """Two lines from the source window to the inset that magnifies it.

    This is the cross-panel part: the two ends live in different panels, and
    neither panel knows where the other ended up. `resolve()` on the composed
    body reports both in one frame, which is the only way to draw a line
    between them without hand-placing either panel.
    """
    placements = inklet.resolve(body)
    src = placements[source.id].bbox
    dst = placements[border.id].bbox
    style = dict(stroke=th.accent, stroke_width=th.hairline,
                 stroke_dash=(0.8, 0.6), fill="none")
    return _at_origin(
        inklet.polyline(((src.x1, src.y0), (dst.x0, dst.y0)), **style),
        inklet.polyline(((src.x1, src.y1), (dst.x0, dst.y1)), **style),
    )


# =====================================================================
# h -- response matrix: heatmap, diverging ramp, colorbar, n.s. stipple
# =====================================================================

_H_CONDITIONS = (
    "drifting grating 0°", "drifting grating 90°", "static grating",
    "full-field flash", "dark flash", "sparse noise", "dense noise",
    "natural movie A", "natural movie B", "looming disc", "receding disc",
    "blank screen",
)
_H_AREAS = ("V1 L2/3", "V1 L4", "V1 L5", "LM", "AL", "RL", "AM", "PM", "LI",
            "POR")

#: How strongly each area is driven by each of three latent stimulus factors:
#: oriented structure, luminance transients, and motion. The matrix is that
#: model plus measurement noise, so the heatmap has block structure a reader
#: can actually find rather than being a field of independent draws.
_H_FACTORS = (
    (1.30, 0.35, 0.15), (1.55, 0.30, 0.10), (1.10, 0.45, 0.35),
    (0.95, 0.30, 0.80), (0.55, 0.25, 1.45), (0.60, 0.20, 1.30),
    (0.35, 0.55, 1.05), (0.45, 0.70, 0.85), (0.30, 1.25, 0.40),
    (0.25, 1.40, 0.30),
)
_H_LOADINGS = (
    (1.60, 0.10, 0.55), (1.55, 0.10, 0.60), (1.35, 0.05, -0.20),
    (0.15, 1.70, -0.10), (-0.20, -1.35, 0.05), (0.55, 0.65, 0.20),
    (0.40, 0.85, 0.35), (0.85, 0.30, 1.25), (0.75, 0.35, 1.15),
    (0.20, 0.60, 1.60), (0.15, 0.45, -1.20), (-0.35, -0.25, -0.30),
)


#: Effect size in units of the trial-to-trial standard deviation. Chosen so the
#: matrix spans about +/-6 z, which is the range these experiments report, and
#: so that a third of the cells genuinely fail the significance test -- a
#: figure where everything is significant tests nothing about the stipple.
_H_ROW = 0.62
_H_GAIN = 2.4
_H_NOISE = 0.5


def _h_matrix() -> list[list[float]]:
    rng = random.Random(4711)
    return [[_H_GAIN * sum(f * l for f, l in zip(_H_FACTORS[r], _H_LOADINGS[c]))
             + _H_NOISE * _normal(rng)
             for c in range(len(_H_CONDITIONS))]
            for r in range(len(_H_AREAS))]


def panel_h(width: float = COLUMN) -> Diagram:
    """Areas x stimulus conditions, z-scored, with the non-significant cells
    struck through rather than recoloured -- a slash survives a greyscale
    reprint and a second hue does not."""
    th = inklet.current_theme()
    values = _h_matrix()
    extreme = max(abs(v) for row in values for v in row)
    limit = math.ceil(extreme * 2) / 2          # a round, symmetric domain

    # Every cell is one z-test; BH over all 120 keeps the false discovery rate
    # at 5% without the flat Bonferroni penalty that would strike out half the
    # real effects at this sample size.
    pvalues = [_normal_two_sided(v) for row in values for v in row]
    cutoff = _benjamini_hochberg(pvalues, 0.05)

    # Five stops, all from the theme's own palette: a diverging ramp needs a
    # light neutral at zero and equal weight on the two arms, which the
    # categorical palette can supply without inventing a colour.
    scheme = inklet.ramp([th.ink_color(5), th.color(2), th.grid, th.color(1),
                       th.color(6)])

    def make(area_w: float) -> Diagram:
        cell = area_w / len(_H_CONDITIONS)
        # Cells are wider than they are tall on purpose: the column labels are
        # set on their side and already cost more height than the matrix, and a
        # square cell would spend the page's height budget on white space.
        row = cell * _H_ROW
        # The category list is reversed because a band scale lays its first
        # category at the *start* of the range, and a y range runs bottom to
        # top -- so V1, which belongs at the top of a hierarchy, would
        # otherwise print at the bottom.
        height = row * len(_H_AREAS)
        grid = inklet.panel(
            area_w, height,
            x=_h_band(_H_CONDITIONS, area_w, th),
            y=_h_band(tuple(reversed(_H_AREAS)), height, th))
        _h_cells(grid, values, scheme, limit, cutoff, th)
        _h_row_labels(grid, th)
        _h_column_labels(grid, th)
        _h_note(grid, th)

        bar = inklet.colorbar(scheme, domain=(-limit, limit),
                           length=grid.height, thickness=th.font_size * 1.2,
                           side="right", label="z-scored ΔF/F₀",
                           count=5)
        return inklet.row([grid, bar], gap=th.gap("m"))

    return _fit_width(make, width, guess=0.66 * width)


def _h_band(categories: Sequence[str], extent: float, th) -> inklet.Scale:
    """A band scale whose gutter is a fixed width in millimetres.

    The default padding is a *fraction* of the step, so a matrix of cells that
    are wider than they are tall gets wide vertical gutters and narrow
    horizontal ones -- visibly a different grid in each direction. Solving
    `step * padding == gutter` gives the same hairline gap both ways, and
    `outer=0` puts the first and last cell edges exactly on the plot area so
    the outline hugs the matrix.
    """
    gutter = th.hairline * 2
    count = len(categories)
    padding = gutter * count / (extent + gutter)
    return inklet.band(categories, padding=padding, outer=0.0)


def _h_cells(grid: inklet.Panel, values, scheme, limit: float, cutoff: float,
             th) -> None:
    """One filled quad per cell, plus a slash on the ones that failed BH."""
    for r, area in enumerate(_H_AREAS):
        y0, y1 = grid.y.edges(area)
        for c, condition in enumerate(_H_CONDITIONS):
            x0, x1 = grid.x.edges(condition)
            value = values[r][c]
            fill = scheme((value + limit) / (2 * limit))
            grid.draw(inklet.polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1)),
                                  fill=fill, stroke="none"))
            if _normal_two_sided(value) > cutoff:
                # Inset by a fifth of the cell so the slash reads as a mark on
                # the cell rather than as a rule between two of them.
                dx, dy = (x1 - x0) * 0.2, (y1 - y0) * 0.2
                grid.over(inklet.polyline(((x0 + dx, y1 - dy), (x1 - dx, y0 + dy)),
                                       stroke=th.text_on(fill),
                                       stroke_width=th.hairline, fill="none"))
    grid.outline(stroke=th.ink, stroke_width=th.hairline)


def _h_row_labels(grid: inklet.Panel, th) -> None:
    """Area names down the left, one per row, right-aligned on the matrix.

    `grid.axis("left")` would be the obvious way and it is wrong here: once the
    rows are shorter than the axis's own minimum label spacing it thins them,
    and a band axis missing every other category names the wrong row. Placing
    them here is not a nudge -- each is offset by half its own measured width,
    which the axis cannot be told to do either.
    """
    right = grid.area.x0 - th.gap("xs")
    for area in _H_AREAS:
        label = inklet.label(area)
        box = label.bbox
        grid.over(label.translated(right - box.width / 2 - box.center.x,
                                   grid.y.map(area) - box.center.y))


def _h_column_labels(grid: inklet.Panel, th) -> None:
    """Condition names above the matrix, turned on their side.

    `inklet.axis` cannot rotate a tick label and its thinning would silently drop
    every other condition, which on a categorical axis is a lie about which
    column is which. So the labels are placed here: rotated to read
    bottom-to-top and pushed up by half their own measured height, which is
    the offset, not a nudge.
    """
    top = grid.area.y0 - th.gap("xs")
    for condition in _H_CONDITIONS:
        label = inklet.label(condition).rotated(-90.0)
        box = label.bbox
        grid.over(label.translated(grid.x.map(condition) - box.center.x,
                                   top - box.height / 2 - box.center.y))


def _h_note(grid: inklet.Panel, th) -> None:
    """What the slashes mean, under the matrix and flush with its left edge."""
    # Two lines, not one: the note is flush with the matrix's left edge, so a
    # single 72 mm line would set the panel's width all by itself and no amount
    # of shrinking the matrix could bring the panel back to the width it was
    # asked for.
    text = inklet.label("struck through: not significant\n"
                     "(Benjamini-Hochberg, FDR 5%)",
                     align="start", text_fill=th.muted)
    box = text.bbox
    grid.over(text.translated(
        grid.area.x0 + box.width / 2 - box.center.x,
        grid.area.y1 + th.gap("s") + box.height / 2 - box.center.y))


# =====================================================================
# i -- orientation tuning, in polar coordinates built from nothing
# =====================================================================

_I_DIRECTIONS = tuple(22.5 * i for i in range(16))
_I_SPOKES = tuple(45.0 * i for i in range(8))

#: (name, preferred direction, baseline, peak, tuning width, opposite-lobe
#: gain). A direction-selective cell has almost no second lobe; an
#: orientation-selective one has two lobes of nearly equal height.
_I_CELLS = (
    ("cell 07  DSI 0.82", 45.0, 3.0, 34.0, 2.6, 0.12),
    ("cell 19  DSI 0.11", 120.0, 4.5, 27.0, 3.4, 0.92),
    ("cell 31  DSI 0.48", 260.0, 2.5, 19.0, 1.9, 0.45),
)


def _i_response(direction: float, pref: float, base: float, peak: float,
                width: float, opposite: float) -> float:
    """A two-lobed von Mises: the standard description of a tuning curve, and
    the reason a tuning curve is smooth enough to interpolate at all."""
    def lobe(centre: float) -> float:
        delta = math.radians(direction - centre)
        return math.exp(width * (math.cos(delta) - 1.0))
    return base + peak * (lobe(pref) + opposite * lobe(pref + 180.0))


def _i_curves():
    """Sampled tuning curves and, for the first cell, a standard error per
    point. The error scales with the square root of the response, which is what
    a photon-limited measurement does."""
    rng = random.Random(90210)
    out = []
    for name, pref, base, peak, width, opposite in _I_CELLS:
        samples, errors = [], []
        for direction in _I_DIRECTIONS:
            mean = _i_response(direction, pref, base, peak, width, opposite)
            samples.append(max(0.4, mean + 0.9 * _normal(rng)))
            errors.append(0.55 * math.sqrt(mean) + 0.25)
        out.append((name, pref, samples, errors))
    return out


def _i_point(angle: float, radius: float) -> Vec2:
    """Polar to page. Angles run anticlockwise from east, the way a direction
    is quoted; y grows downward here, so the sine is negated exactly once and
    every other polar thing in this panel goes through this function."""
    theta = math.radians(angle)
    return Vec2(math.cos(theta) * radius, -math.sin(theta) * radius)


def _i_push_out(node: Diagram, angle: float, radius: float,
                gap: float) -> tuple[Vec2, Diagram]:
    """A label just clear of a circle of radius `radius`.

    The reach is the support function of the label's own box in the radial
    direction, so a wide label at 0 degrees is pushed out by half its width and
    a short one at 90 degrees by half its height. Centring every label on the
    same circle instead is what makes hand-rolled polar plots look lopsided.
    """
    box = node.bbox
    direction = _i_point(angle, 1.0)
    reach = radius + gap + (abs(direction.x) * box.width
                            + abs(direction.y) * box.height) / 2
    return (direction * reach, node)


def panel_i(width: float = COLUMN) -> Diagram:
    """Three tuning curves in polar coordinates.

    There is no polar support in the library, so the axes, the rings, the
    angular ticks and the curves are all built from `inklet.arc`, `inklet.path` and
    one coordinate transform.
    """
    th = inklet.current_theme()
    curves = _i_curves()
    ceiling = max(r + e for _, _, rs, es in curves for r, e in zip(rs, es))
    rings = inklet.linear((0.0, ceiling), nice=True).ticks(3)
    span = rings[-1]
    # A dial is square and a legend under it is mostly air, so the key goes
    # beside it and pays for itself in height. The cost is a floor on the
    # panel's width: below one, the entries are set on two lines instead, which
    # is the only way this panel can honour a width it was handed.
    narrow = width < 0.75 * COLUMN

    def make(radius: float) -> Diagram:
        scale = inklet.linear((0.0, span), (0.0, radius))
        plot = inklet.place(
            _i_grid(scale, rings, span, radius, th)
            + _i_data(curves, scale, radius, th)
            + _i_angular_labels(radius, th)
            + _i_radial_labels(scale, rings, th)
        )
        key = inklet.legend([(_i_key(name, narrow), th.ink_color(i * 2 + 1))
                          for i, (name, _, _, _) in enumerate(curves)])
        return inklet.hstack([plot, key], gap=th.gap("m"), align="center")

    return _fit_width(make, width, guess=0.28 * width)


def _i_key(name: str, narrow: bool) -> str:
    return name.replace("  ", "\n") if narrow else name


def _i_grid(scale, rings, span: float, radius: float, th) -> list:
    """Rings at the labelled radii, spokes every 45 degrees, and a rim."""
    items: list = [inklet.arc(scale.map(r), 0.0, 360.0, stroke=th.grid,
                           stroke_width=th.hairline, fill="none")
                   for r in rings if r > 0]
    items.append(_ticks_prim(
        [(Vec2(0.0, 0.0), _i_point(a, radius)) for a in _I_SPOKES],
        stroke=th.grid, stroke_width=th.hairline, stroke_linecap="butt"))
    items.append(inklet.arc(radius, 0.0, 360.0, stroke=th.ink,
                         stroke_width=th.hairline, fill="none"))
    return items


def _i_data(curves, scale, radius: float, th) -> list:
    """Each cell: a closed spline through its 16 samples, its preferred
    direction as a spoke, and -- on the first cell only -- radial whiskers."""
    items: list = []
    for index, (_, pref, samples, errors) in enumerate(curves):
        colour = th.ink_color(index * 2 + 1)
        points = [_i_point(a, scale.map(r))
                  for a, r in zip(_I_DIRECTIONS, samples)]
        items.append(inklet.curve(points, smooth=0.5, closed=True, stroke=colour,
                               stroke_width=th.thick, fill="none"))
        items.append(inklet.polyline((Vec2(0.0, 0.0), _i_point(pref, radius)),
                                  stroke=colour, stroke_width=th.stroke,
                                  stroke_dash=(1.2, 0.9), fill="none"))
        if index == 0:
            items.append(_i_whiskers(samples, errors, scale, colour, th))
            items.append(inklet.place(
                [(p, inklet.marker("circle", th.font_size * 0.42, fill=colour))
                 for p in points]))
    return items


def _i_whiskers(samples, errors, scale, colour, th) -> Diagram:
    """One radial bar per direction, with tangential caps.

    The caps are chords rather than arcs: at these radii the sagitta of a
    0.9 mm chord is under 5 micrometres, which is a tenth of the stroke.
    """
    segments = []
    for angle, value, error in zip(_I_DIRECTIONS, samples, errors):
        lo = _i_point(angle, scale.map(max(0.0, value - error)))
        hi = _i_point(angle, scale.map(value + error))
        segments.append((lo, hi))
        tangent = _i_point(angle + 90.0, th.font_size * 0.22)
        for end in (lo, hi):
            segments.append((end - tangent, end + tangent))
    return _ticks_prim(segments, stroke=colour, stroke_width=th.hairline,
                       stroke_linecap="butt")


def _i_angular_labels(radius: float, th) -> list:
    return [_i_push_out(inklet.label(f"{int(a)}°"), a, radius, th.gap("s"))
            for a in _I_SPOKES]


def _i_radial_labels(scale, rings, th) -> list:
    """Ring values on a bearing that misses every spoke, on opaque plates so a
    curve passing under a number does not run through it."""
    bearing = 112.5
    items = []
    for value in rings:
        if value <= 0:
            continue
        text = inklet.label(f"{value:g}")
        plate = inklet.frame(text, pad=0.4, kind="label-plate").styled(
            fill=th.paper, stroke="none")
        items.append((_i_point(bearing, scale.map(value)), plate))
    items.append(_i_push_out(inklet.label("ΔF/F₀ / %"), bearing,
                             scale.map(rings[-1]) + th.gap("m"), th.gap("xs")))
    return items


# =====================================================================
# k -- correlation with a least-squares fit and a real confidence band
# =====================================================================

_K_N = 120
_K_ALPHA = 0.05

#: Plot area height as a fraction of its width. A figure page is a height
#: budget before it is anything else, so panels are laid out wider than tall
#: and the data is given the extra width rather than the extra height.
_K_ASPECT = 0.56


def _k_points() -> list[tuple[float, float]]:
    """Locomotion against evoked response, one point per session.

    Speed is squared-uniform so the cloud is denser at rest, which is what a
    head-fixed mouse actually does; the response is linear in speed with
    homoscedastic noise, which is what the fit and the band assume.
    """
    rng = random.Random(31415)
    points = []
    for _ in range(_K_N):
        speed = 24.0 * rng.random() ** 2
        points.append((speed, 7.5 + 1.15 * speed + 8.5 * _normal(rng)))
    return points


def panel_k(width: float = COLUMN) -> Diagram:
    """Scatter, ordinary least squares fit, and the 95% confidence band for the
    mean -- computed from the residuals of that fit, not drawn to taste."""
    th = inklet.current_theme()
    points = _k_points()
    slope, intercept, mean_x, sxx, sd, r2, t_stat = _least_squares(points)
    critical = _t_critical(_K_ALPHA, _K_N - 2)
    p_value = _t_two_sided(t_stat, _K_N - 2)

    lo = min(p[0] for p in points)
    hi = max(p[0] for p in points)
    upper, lower = [], []
    for i in range(49):
        x = lo + (hi - lo) * i / 48
        centre = intercept + slope * x
        half = critical * sd * math.sqrt(1.0 / _K_N + (x - mean_x) ** 2 / sxx)
        upper.append((x, centre + half))
        lower.append((x, centre - half))

    x_scale = inklet.linear((lo, hi), nice=True)
    y_low = min(min(p[1] for p in points), min(v for _, v in lower))
    y_high = max(max(p[1] for p in points), max(v for _, v in upper))
    y_scale = inklet.linear((y_low, y_high), nice=True)

    def make(area_w: float) -> Diagram:
        plot = inklet.panel(area_w, area_w * _K_ASPECT, x=x_scale, y=y_scale)
        plot.background(fill=th.paper)
        plot.grid(count=5, stroke=th.grid)

        # One closed polygon: upper bound forward, lower bound reversed. Two
        # separate boundaries would need a fill rule, and `PathPrim` has none.
        plot.under(inklet.polygon(plot.map(upper + lower[::-1]),
                               fill=th.color(2), stroke="none", opacity=0.28))
        plot.line([(lo, intercept + slope * lo), (hi, intercept + slope * hi)],
                  stroke=th.ink_color(5), stroke_width=th.thick)
        plot.marks(inklet.marker("circle", th.font_size * 0.5, fill=th.ink,
                              opacity=0.55), points)
        _k_rugs(plot, points, th)
        plot.axes(x="running speed / cm s⁻¹",
                  y="ΔF/F₀ at preferred / %", count=5)
        # Bottom right: a rising fit leaves that corner empty, and a shorter
        # plot area has no room to spare above the cloud. Which corner is free
        # is a property of the data, not of the layout, so it is chosen here
        # rather than defaulted to.
        plot.over(_corner(_k_stats(r2, t_stat, p_value, th), plot.area, "se",
                          th.gap("s")))
        return plot.build()

    return _fit_width(make, width, guess=0.78 * width)


def _k_rugs(plot: inklet.Panel, points, th) -> None:
    """Marginal ticks inside each spine: the two one-dimensional distributions
    the scatter is a product of, at no cost in space."""
    box = plot.area
    reach = th.font_size * 0.55
    plot.draw(_ticks_prim(
        [(Vec2(plot.x.map(x), box.y1), Vec2(plot.x.map(x), box.y1 - reach))
         for x, _ in points],
        stroke=th.ink, stroke_width=th.hairline, stroke_linecap="butt",
        opacity=0.55))
    plot.draw(_ticks_prim(
        [(Vec2(box.x0, plot.y.map(y)), Vec2(box.x0 + reach, plot.y.map(y)))
         for _, y in points],
        stroke=th.ink, stroke_width=th.hairline, stroke_linecap="butt",
        opacity=0.55))


def _k_stats(r2: float, t_stat: float, p_value: float, th) -> Diagram:
    """r-squared, n, t and p, set with the characters those quantities are
    spelled with: a superscript two, a subscript df, a multiplication sign and
    a superscript minus in the exponent."""
    p_text = f"p = {_sci(p_value)}" if p_value else "p < 10⁻³⁰⁰"
    lines = (f"r² = {r2:.2f}   n = {_K_N}\n"
             f"t{str(_K_N - 2).translate(_SUBSCRIPT)} = {t_stat:.1f}   {p_text}\n"
             f"shaded: 95% CI of the mean")
    return inklet.label(lines, align="start", text_fill=th.muted)


# =====================================================================
# looking at it
# =====================================================================

def _volume_report() -> str:
    """What 10^4 marks actually cost, three ways.

    Panel (g) is in the figure to be measured, so the measurement is part of
    the deliverable. The same raster geometry is built as one diagram per
    spike (`marks`), as one polyline per spike, as one polyline per spike
    grouped into blocks of 256 (which is what it takes to keep the envelope
    recursion shallow), and as one multi-subpath path per layer, which is what
    `panel_g` ships. Every row is the same picture.
    """
    import time

    th = inklet.current_theme()
    trains, total = _g_spikes()
    lines = [f"spikes: {total} across {_G_NEURONS} neurons "
             f"({total / _G_NEURONS:.0f} each)"]

    def fresh() -> inklet.Panel:
        return inklet.panel(110.0, 31.0, x=_G_SPAN, y=(-0.5, _G_NEURONS - 0.5))

    def as_marks(panel: inklet.Panel) -> None:
        panel.marks(inklet.marker("circle", th.hairline * 2, fill=th.ink),
                    [(t, n) for n, train in enumerate(trains) for t in train])

    def segments(panel: inklet.Panel):
        half = abs(panel.y.map(1) - panel.y.map(0)) * 0.36
        for row, train in enumerate(trains):
            y = panel.y.map(row)
            for t in train:
                x = panel.x.map(t)
                yield Vec2(x, y - half), Vec2(x, y + half)

    def as_polylines(panel: inklet.Panel) -> None:
        panel.draw(*[inklet.polyline((a, b), stroke_width=th.hairline)
                     for a, b in segments(panel)])

    def as_blocks(panel: inklet.Panel, size: int = 256) -> None:
        items = [inklet.polyline((a, b), stroke_width=th.hairline)
                 for a, b in segments(panel)]
        while len(items) > size:
            items = [Diagram(children=tuple(items[i:i + size]))
                     for i in range(0, len(items), size)]
        panel.draw(*items)

    def as_paths(panel: inklet.Panel) -> None:
        _g_ticks(panel, trains, th)

    for name, fill in (("marker per spike", as_marks),
                       ("polyline per spike", as_polylines),
                       ("polyline, blocked 256", as_blocks),
                       ("path per layer  (shipped)", as_paths)):
        start = time.perf_counter()
        try:
            panel = fresh()
            fill(panel)
            node = panel.build()
            page = inklet.figure(width=node.bbox.width + 4)
            page.add(node)
            svg = page.to_svg()
            build = time.perf_counter() - start
            start = time.perf_counter()
            found = len(page.lint())
            check = time.perf_counter() - start
            nodes = sum(1 for _ in page.build()[0].walk())
            size = len(svg.encode())
            lines.append(
                f"  {name:26s} {build:6.3f}s build  {check:6.3f}s lint  "
                f"{size:9,d} B ({size / total:5.1f} B/mark)  "
                f"{nodes:7,d} nodes  {found} diagnostics")
        except RecursionError:
            lines.append(f"  {name:26s} RecursionError -- "
                         f"Envelope.union recurses once per sibling")
    return "\n".join(lines)


if __name__ == "__main__":
    import dataclasses
    import pathlib
    import time

    inklet.use_theme(dataclasses.replace(inklet.theme("nature"),
                                      font_family="Noto Sans"))

    def timed(name, fn, *args):
        start = time.perf_counter()
        node = fn(*args)
        print(f"  {name:8s} built in {time.perf_counter() - start:6.3f} s")
        return node

    print("panels")
    g = timed("panel_g", panel_g, FULL_WIDTH)
    h = timed("panel_h", panel_h, COLUMN)
    i = timed("panel_i", panel_i, COLUMN)
    k = timed("panel_k", panel_k, COLUMN)
    for name, node in (("g", g), ("h", h), ("i", i), ("k", k)):
        print(f"  {name}: {node.bbox.width:6.2f} x {node.bbox.height:6.2f} mm")

    # A proof sheet, not the figure: every panel at the millimetre size it
    # would print at, on a page wide enough that nothing is clipped.
    sheet = inklet.vstack([g, inklet.hstack([h, i, k], gap=10, align="top")],
                       gap=12, align="center")
    fig = inklet.figure(width=sheet.bbox.width + 8)
    fig.add(sheet)
    fig.save("stress/panels/responses.svg")

    start = time.perf_counter()
    report = fig.report()
    print(f"\nlint in {time.perf_counter() - start:.3f} s")
    print(report)

    # Panel g on its own page, which is the honest way to weigh it.
    alone = inklet.figure(width=FULL_WIDTH + 4)
    alone.add(panel_g(FULL_WIDTH))
    for precision in (3, 2, 1):
        svg = alone.to_svg(precision=precision)
        print(f"panel_g alone at precision={precision}: "
              f"{len(svg.encode()):,d} B")
    root, _ = alone.build()
    print(f"panel_g alone: {sum(1 for _ in root.walk()):,d} nodes")
    start = time.perf_counter()
    found = len(alone.lint())
    print(f"panel_g alone: lint {time.perf_counter() - start:.3f} s, "
          f"{found} diagnostics")

    print("\nvolume")
    print(_volume_report())

    # Determinism is a *between-runs* property: node ids come from a
    # process-wide counter, so building the same panel twice in one process
    # renumbers it. Run this script twice and compare the digests.
    import hashlib

    digest = hashlib.sha256(
        pathlib.Path("stress/panels/responses.svg").read_bytes()).hexdigest()
    print(f"\nsheet sha256: {digest}")
