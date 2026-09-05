"""Panels (c) and (d) of the electrolyser figure: what the catalyst looks like.

(c) SEM field with a lattice-image inset
    The `sem.png` raster with everything a micrograph owes its reader drawn in
    vector over it: a scale bar whose length is computed from the stated field
    of view, an ROI ring on one particle, a leader from that ring to a framed
    HR-TEM inset, and a dimension line across the inset's lattice fringes that
    lands on fringe maxima by construction. Nothing is baked into the pixels,
    so the annotations survive recolouring, rescaling and the linter.

(d) the particle-size distribution measured off that field
    A histogram of nanocube edge lengths drawn from the same lognormal the
    micrograph generator placed its cubes with, a fitted lognormal over it,
    and the median and geometric spread quoted from the fit.

Run it:

    .venv/bin/python stress/electro/imaging.py
    scripts/rasterise.sh stress/electro/imaging.svg stress/electro/imaging.png 3
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import inklet
from inklet.core.geom import Rect, Vec2

# Run as a script from anywhere, or imported as part of the package: the
# sibling modules resolve either way.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import common          # noqa: E402
import micrograph      # noqa: E402

#: How much of the SEM frame the inset covers. A third: big enough that the
#: fringes resolve at column width, small enough that the field it interrupts
#: still reads as a field.
_INSET_FRACTION = 0.34

#: The particle the HR-TEM zoomed into, as fractions of the SEM frame -- read
#: off the image, so it is data about the asset, not a layout coordinate. The
#: ring's radius is in the specimen's own nanometres for the same reason.
_ROI_UV = (0.519, 0.155)
_ROI_R_NM = 26.0

_SCALE_BAR_NM = 100.0

#: The lower grain of `micrograph.tem`: fringe-normal angle and a point well
#: inside both the grain and the particle's facets. Mirrors of the geometry
#: that module draws with -- the fringes are *at* this angle in the pixels,
#: which is what lets the dimension line below land on them.
_GRAIN_ANGLE = math.radians(-51.0)
_DIM_AT_NM = (3.9, 7.4)
_DIM_FRINGES = 8

#: n and the distribution the SEM's cubes were drawn from, quoted from
#: `micrograph.sem` rather than invented here: 430 cubes, lognormal edge
#: lengths about 34 nm, scaled by how near the cube sits to the detector.
_N_PARTICLES = 430
_EDGE_MEDIAN_NM = 34.0
_EDGE_SIGMA_LN = 0.34
_DEPTH_SCALE = (0.72, 0.5)


def _at(node: inklet.Diagram, x: float, y: float, anchor: str = "center") -> inklet.Diagram:
    """Move a node so `anchor` lands on (x, y) of the frame being drawn in.

    The same helper `stress/panels` uses: `inklet.place` positions one anchor per
    call, and compositing over a raster mixes "centre it here" with "hang it
    off this corner" in one coordinate system.
    """
    here = node.transform.apply(node.anchor_point(anchor))
    return node.translated(x - here.x, y - here.y)


def _plated(content: inklet.Diagram, theme) -> inklet.Diagram:
    """Text made readable on a micrograph: paper type on an ink plate.

    The plate is not only a look. The linter's contrast check measures text
    against the tightest filled *shape* under it -- a raster is not one -- so
    paper-white type straight on the image would be judged against the white
    page and reported unreadable. The plate is the backdrop that makes the
    contrast a checkable fact instead of a guess about pixels.
    """
    return inklet.frame(content, pad=theme.gap("xs") * 1.4).styled(
        fill=theme.ink, stroke="none")


def _tag(body: str, theme) -> inklet.Diagram:
    return _plated(inklet.label(body, text_fill=theme.paper, align="center"), theme)


# -- (c) the SEM field with its lattice inset ------------------------------


def _scale_bar(theme, length_nm: float, span_mm: float, fov_nm: float) -> inklet.Diagram:
    """A bar of a stated length in the specimen's nanometres.

    The drawn length is `length_nm / fov_nm` of the drawn frame -- derived, so
    the bar is correct at whatever width the panel is finally solved to. A bar
    placed by eye would be wrong every time `fit` changed the drive.
    """
    bar_mm = length_nm / fov_nm * span_mm
    bar = inklet.polyline([(0.0, 0.0), (bar_mm, 0.0)], stroke=theme.paper,
                       stroke_width=theme.thick, stroke_linecap="butt")
    return _plated(inklet.vstack(
        [bar, inklet.label(f"{length_nm:g} nm", text_fill=theme.paper)],
        gap=theme.gap("xs"), align="center"), theme)


def _fringe_dimension(inset_w: float, theme) -> tuple[
        tuple[float, float], tuple[float, float]]:
    """Endpoints of the d_{111} dimension, in the TEM image's own nanometres.

    Snapped: the line runs along the fringe normal and its centre is moved to
    the nearest fringe maximum (where `x cos a + y sin a` is a whole number of
    spacings), so both end ticks sit *on* bright fringes and a reader with a
    ruler measures exactly `_DIM_FRINGES` periods between them. Placing the
    ends by eye at this magnification would miss by half a fringe.
    """
    d = micrograph.D111
    n = Vec2(math.cos(_GRAIN_ANGLE), math.sin(_GRAIN_ANGLE))
    centre = Vec2(*_DIM_AT_NM)
    phase = centre.dot(n) / d
    centre = centre + n * ((round(phase) - phase) * d)
    half = n * (_DIM_FRINGES * d / 2.0)
    return ((centre.x - half.x, centre.y - half.y),
            (centre.x + half.x, centre.y + half.y))


def _inset(inset_w: float, theme) -> inklet.Diagram:
    """The HR-TEM inset: the raster, the d_{111} dimension, and its captions,
    framed in the accent that also draws the ROI ring -- the stroke match is
    what ties the two ends of the leader together."""
    end_a, end_b = _fringe_dimension(inset_w, theme)
    to_uv = lambda p: (p[0] / micrograph.TEM_NM, p[1] / micrograph.TEM_NM)
    tem = inklet.asset(common.ASSETS / "tem.png", width=inset_w, cutout=False,
                    name="tem", anchors={"dim0": to_uv(end_a),
                                         "dim1": to_uv(end_b)})
    box = tem.local_bbox
    p0, p1 = tem.anchor_point("dim0"), tem.anchor_point("dim1")

    # The dimension: a rule between the two snapped fringe maxima, with end
    # ticks along the fringes themselves. Accent-coloured because a grey line
    # on a grey lattice is invisible at exactly the spatial frequency of the
    # thing it measures.
    along = (p1 - p0).normalized()
    tick = along.perp() * (inset_w * 0.035)
    accent = dict(stroke=theme.color(1), stroke_width=theme.stroke)
    dimension = [inklet.polyline([(p0.x, p0.y), (p1.x, p1.y)], **accent)]
    dimension += [inklet.polyline([(p.x - tick.x, p.y - tick.y),
                                (p.x + tick.x, p.y + tick.y)], **accent)
                  for p in (p0, p1)]

    spacing = _tag(f"d_{{111}} = {micrograph.D111:g} nm", theme)
    # Under the lower end of the dimension, clamped inside the frame: the
    # dimension sits in the particle's lower-left grain, and the amorphous
    # support below it is the only part of the inset with nothing to say.
    low = p0 if p0.y > p1.y else p1
    tag_w, tag_h = spacing.local_bbox.width, spacing.local_bbox.height
    tag_x = min(max(low.x, box.x0 + tag_w / 2.0 + theme.gap("xs")),
                box.x1 - tag_w / 2.0 - theme.gap("xs"))
    caption = _tag("HR-TEM", theme)

    body = inklet.place(
        [tem] + dimension +
        [_at(spacing, tag_x, low.y + theme.gap("s") + tag_h / 2.0),
         _at(caption, box.x0 + caption.local_bbox.width / 2.0 + theme.gap("xs"),
             box.y0 + caption.local_bbox.height / 2.0 + theme.gap("xs"))])
    return inklet.frame(body, pad=0.0).styled(
        fill="none", stroke=theme.color(1), stroke_width=theme.stroke)


def _panel_c_content(span: float) -> inklet.Diagram:
    theme = inklet.current_theme()
    micrograph.ensure()
    # `cutout=False`: a micrograph's subject is the whole frame, and keying a
    # background out of it would hand the annotations a silhouette that means
    # nothing. Anchors are then fractions of the full frame.
    photo = inklet.asset(common.ASSETS / "sem.png", width=span, cutout=False,
                      name="sem", anchors={"roi": _ROI_UV})
    frame = photo.local_bbox
    roi_at = photo.anchor_point("roi")
    inset_w = span * _INSET_FRACTION
    ring_r = _ROI_R_NM / micrograph.SEM_NM * span

    ring = inklet.circle(inklet.spacer(ring_r * 2.0, ring_r * 2.0), pad=0.0,
                      fill="none", stroke=theme.color(1),
                      stroke_width=theme.stroke).named("roi-ring")
    inset = _inset(inset_w, theme)
    margin = theme.gap("m")

    items = [
        photo,
        _at(ring, roi_at.x, roi_at.y),
        # Top-right corner, where this field happens to be at its emptiest;
        # positioned off the frame's own box, so the corner is the corner at
        # any drive width.
        _at(inset, frame.x1 - margin, frame.y0 + margin, "ne"),
        _at(_tag("SEM, 5 kV, 45 000×", theme),
            frame.x0 + margin, frame.y0 + margin, "nw"),
        _at(_scale_bar(theme, _SCALE_BAR_NM, span, micrograph.SEM_NM),
            frame.x0 + margin, frame.y1 - margin, "sw"),
    ]

    content = inklet.place(items)
    # The leader that says "this particle, magnified": clipped on the ring at
    # one end and the inset's frame at the other. `through=(photo,)` declares
    # that running over the micrograph is the point -- both of its endpoints
    # live on the image -- so the linter can tell it from a line that wandered
    # across a figure element.
    leader = inklet.link(ring, inset, kind="line", head="none", standoff=0.5,
                      through=(photo,),
                      style=inklet.Style(stroke=theme.color(1),
                                      stroke_width=theme.hairline),
                      name="roi-leader")
    routed = inklet.route_all([leader], inklet.resolve(content))
    return inklet.Diagram(children=(content, routed), kind="panel")


def panel_c(width: float = 87.0) -> inklet.Diagram:
    """SEM field of Cu2O nanocubes, scale bar, ROI ring, HR-TEM inset."""
    return common.fit(_panel_c_content, width)


# -- (d) the size distribution off that field ------------------------------


def _edge_lengths():
    """Edge lengths drawn from the population `micrograph.sem` rendered.

    The generator draws, per cube, a depth and then a lognormal edge scaled by
    `0.72 + 0.5 * depth`; the two are independent, so drawing them as arrays
    is the same joint distribution. Its own seed, per `common.rng`: sharing
    the micrograph's stream would change this panel's data the moment that
    module drew one more blob.
    """
    gen = common.rng(430_812)
    depth = gen.uniform(0.0, 1.0, _N_PARTICLES)
    base, spread = _DEPTH_SCALE
    return (gen.lognormal(math.log(_EDGE_MEDIAN_NM), _EDGE_SIGMA_LN,
                          _N_PARTICLES) * (base + spread * depth))


def _panel_d_content(area_w: float, area_h: float) -> inklet.Diagram:
    import numpy as np

    theme = inklet.current_theme()
    sizes = _edge_lengths()
    # The fit is the lognormal MLE -- moments of log-size -- so the quoted
    # median and geometric spread are measurements of these 430 particles,
    # not the generator's inputs echoed back.
    logs = np.log(sizes)
    median = float(np.exp(logs.mean()))
    gsd = float(np.exp(logs.std()))

    step = 5.0
    lo = math.floor(sizes.min() / step) * step
    hi = math.ceil(sizes.max() / step) * step
    edges = np.arange(lo, hi + step / 2.0, step)
    counts, _ = np.histogram(sizes, bins=edges)
    top = math.ceil(counts.max() * 1.15 / 10.0) * 10.0

    plot = inklet.panel(area_w, area_h, x=(lo, hi), y=(0.0, top))
    # Bars are the data, so their positions are the data's business:
    # `kind="mark"` is what tells CROWDING that two adjacent bins touching is
    # a histogram, not a layout mistake.
    pale = inklet.mix(theme.ink, theme.paper, 0.85)
    for x0, x1, count in zip(edges[:-1], edges[1:], counts):
        if count == 0:
            continue
        plot.draw(inklet.polygon(
            plot.map(((x0, 0.0), (x1, 0.0), (x1, float(count)),
                      (x0, float(count)))),
            fill=pale, stroke=theme.muted, stroke_width=theme.hairline,
            kind="mark"))

    xs = np.linspace(lo, hi, 140)
    pdf = (np.exp(-((np.log(xs) - logs.mean()) ** 2) / (2.0 * logs.var()))
           / (xs * logs.std() * math.sqrt(2.0 * math.pi)))
    # The curve is expected *counts* -- pdf times n and the bin width -- so
    # it and the bars share a y axis instead of needing a second one.
    plot.line(list(zip(xs, _N_PARTICLES * step * pdf)),
              stroke=theme.accent, stroke_width=theme.thick)

    plot.line([(median, 0.0), (median, top * 0.92)], stroke=theme.ink,
              stroke_width=theme.hairline, stroke_dash=(1.2, 0.8))

    stats = inklet.vstack(
        [inklet.label(f"n = {_N_PARTICLES}", align="left"),
         inklet.label(f"median = {median:.1f} nm", align="left"),
         inklet.label(f"σ_{{g}} = {gsd:.2f}", align="left")],
        gap=theme.gap("xs") * 0.8, align="left")
    # Top right, in the room the right-skewed tail leaves empty; panel
    # coordinates from the area's own box, never the page's.
    box = stats.local_bbox
    plot.over(inklet.place([(Vec2(plot.area.x1 - theme.gap("s") - box.width / 2.0,
                               plot.area.y0 + theme.gap("s") + box.height / 2.0),
                          stats)]))

    plot.axes(x="edge length / nm", y="particles")
    return plot.build()


def panel_d(width: float = 87.0) -> inklet.Diagram:
    """Histogram of nanocube edge lengths with the fitted lognormal."""
    # Height off the target, not the drive: the fit loop narrows the area to
    # make room for the y labels, and a height that followed it would change
    # the panel's aspect with every pass.
    return common.fit(lambda drive: _panel_d_content(drive, width * 0.62), width)


# -- looking at it ---------------------------------------------------------

if __name__ == "__main__":
    import time

    started = time.perf_counter()
    inklet.use_theme("nature")

    fig = inklet.figure(width=common.PAGE_WIDTH, margin=2)
    fig.add(inklet.hstack([
        common.titled("c", panel_c(common.COLUMN)),
        common.titled("d", panel_d(common.COLUMN)),
    ], gap=5.0, align="top"))

    out = Path(__file__).with_suffix(".svg")
    fig.save(out)
    print(f"drawn in {time.perf_counter() - started:.1f} s -> {out}")
    print(fig.report())
