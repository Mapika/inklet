"""Panels e-h: the electrochemistry and the operando spectroscopy.

Four views of the same catalyst doing the same chemistry:

    e   Faradaic efficiency against potential, stacked to 100%, with the
        total current density on a second axis
    f   Tafel analysis of the partial currents, and where transport takes over
    g   operando XRD: the oxide reducing to metal under load, full width
    h   operando FTIR: the surface species that appear as the potential falls

Everything numeric comes from `data`; everything chromatic comes from the
theme via `common.SPECIES`, so the C2H4 that is orange in (e) is orange in
(f) and stays orange in whatever panel another module draws it into. The
panels compute their annotations -- Tafel slopes, the reduction half-time,
the XRD peak positions -- from the same arrays they plot, so a quoted number
cannot drift from the picture under it.
"""

from __future__ import annotations

import math
from typing import Sequence

import inklet
from inklet import Diagram, Vec2

import common
import data

__all__ = ["panel_e", "panel_f", "panel_g", "panel_h"]


# =====================================================================
# small shared machinery
# =====================================================================


def _species_colour(th, key: str) -> str:
    """One colour per species, dark enough to be read as *type*.

    The same slot has to survive three duties: a filled bar in (e), a 0.25mm
    fit line in (f), and the text that quotes that line's slope. Text needs
    4.5:1 against the paper, and asking for it once here -- rather than 3:1
    for the geometry and 4.5:1 for the words -- keeps all three exactly the
    same colour, which is the point of `common.SPECIES` existing at all.
    (Same argument as `responses._g_colour`.)
    """
    return th.ink_color(common.SPECIES[key], min_ratio=4.5)


def _rect(x0: float, y0: float, x1: float, y1: float, **style) -> Diagram:
    return inklet.polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1)), **style)


def _plate(node: Diagram, th) -> Diagram:
    """Opaque backing for a label that has to sit on data ink."""
    return inklet.frame(node, pad=0.4, kind="label-plate").styled(
        fill=th.paper, stroke="none")


def _at(node: Diagram, x: float, y: float) -> Diagram:
    """Move `node` so its centre lands on (x, y) in the frame it is drawn
    into -- the offset arithmetic `panel.over` cannot do for us, since `over`
    takes finished geometry."""
    here = node.transform.apply(node.anchor_point("center"))
    return node.translated(x - here.x, y - here.y)


def _corner(node: Diagram, area, where: str, pad: float) -> Diagram:
    """`node`'s own corner `pad` inside the matching corner of `area`, however
    wide the text turns out to be. (The `responses._corner` idiom.)"""
    box = node.bbox
    x = (area.x0 + pad + box.width / 2 if where in ("nw", "sw")
         else area.x1 - pad - box.width / 2)
    y = (area.y0 + pad + box.height / 2 if where in ("nw", "ne")
         else area.y1 - pad - box.height / 2)
    return _at(node, x, y)


# =====================================================================
# e -- Faradaic efficiency, stacked to 100%, with the total current
# =====================================================================

#: Bottom of the stack upward. C2H4 sits on the baseline so the one number
#: this figure is judged by can be read straight off the axis; H2 goes on
#: top, where its monotonic rise is the top edge's own story; the minor
#: products live in between, where a reader expects the small print.
_E_STACK = ("C2H4", "CO", "HCOO", "CH4", "H2")

#: Plot-area height as a fraction of the asked-for width, so the panel keeps
#: its proportions when a layout hands it a different column.
_E_ASPECT = 0.62


def panel_e(width: float = common.COLUMN) -> Diagram:
    """FE by species at each potential, with j_total overlaid on a right axis.

    The current goes on a second y axis rather than an annotation row: the
    bend at the transport limit is a *shape*, and a row of seven numbers has
    no shape. The axis runs 0 to J_LIMIT so the line's approach to the top of
    the frame is itself the statement that the cell has hit its ceiling.
    """
    th = inklet.current_theme()
    overlay = th.ink_color(6)   # vermillion: no species owns slot 6, and it
                                # stays visible crossing the H2 stack's black

    def make(area_w: float) -> Diagram:
        area_h = _E_ASPECT * width
        p = inklet.panel(area_w, area_h,
                      x=inklet.band(data.POTENTIALS, padding=0.22),
                      y=(0.0, 100.0))
        for index, potential in enumerate(data.POTENTIALS):
            x0, x1 = p.x.edges(potential)
            base = 0.0
            for species in _E_STACK:
                fe = data.FARADAIC[species][index]
                if fe <= 0.0:
                    continue
                shade = _species_colour(th, species)
                # Stroked in its own fill: two abutting fills are antialiased
                # separately and leave a pale seam; half a hairline of the
                # same colour on each side buries it symmetrically, the same
                # cure `Panel.matrix` applies by overlapping its cells.
                # kind="mark": the position is the measurement.
                p.draw(_rect(x0, p.y.map(base), x1, p.y.map(base + fe),
                             fill=shade, stroke=shade,
                             stroke_width=th.hairline, kind="mark"))
                base += fe

        # The second scale reuses the panel's own vertical range, which is the
        # whole trick of a twin axis: same millimetres, different meaning.
        j = inklet.linear((0.0, data.J_LIMIT)).with_range(p.height / 2,
                                                       -p.height / 2)
        points = [Vec2(p.x.map(v), j.map(cur))
                  for v, cur in zip(data.POTENTIALS, data.TOTAL_CURRENT)]
        p.over(inklet.polyline(points, stroke=overlay, stroke_width=th.stroke,
                            stroke_dash=(1.4, 1.0), fill="none", kind="mark"))
        p.over(inklet.place([(pt, inklet.marker("circle", th.font_size * 0.55,
                                          fill=th.paper, stroke=overlay,
                                          stroke_width=th.stroke))
                          for pt in points]))
        # `Panel.axis` only knows the panel's own scales, so the right axis is
        # built from the current scale and hung on the area edge by hand --
        # the same `align_to(..., "origin")` + translate `Panel.axis` does.
        p.over(inklet.align_to(
            inklet.axis(j, side="right", label="j_{total} / mA cm^{−2}", count=4),
            "origin").translated(p.area.x1, 0.0))

        p.axis("bottom", label="E / V vs RHE", format=lambda v: f"{v:.2f}")
        p.axis("left", label="Faradaic efficiency / %")

        swatch = inklet.place([
            inklet.polyline(((-2.0, 0.0), (2.0, 0.0)), stroke=overlay,
                         stroke_width=th.stroke, stroke_dash=(1.4, 1.0),
                         fill="none"),
            (Vec2(0.0, 0.0), inklet.marker("circle", th.font_size * 0.55,
                                        fill=th.paper, stroke=overlay,
                                        stroke_width=th.stroke)),
        ])
        key = inklet.legend(
            [(common.SPECIES_LABEL[s], _species_colour(th, s))
             for s in _E_STACK] + [("j_{total}", swatch)],
            columns=3)
        return inklet.vstack([p.build(), key], gap=th.gap("s"), align="center")

    return common.fit(make, width)


# =====================================================================
# f -- Tafel plot of the partial currents
# =====================================================================

_F_ASPECT = 0.62

#: The x domain brackets the data (0.0077 to 206 mA/cm^2) and reaches past
#: J_LIMIT so the asymptote is inside the frame rather than on its edge.
_F_DOMAIN = (5e-3, 500.0)

#: How many low-overpotential points the kinetic fit uses -- the default of
#: `data.tafel_slope`, restated so the drawn fit and the quoted slope cover
#: the same points by construction.
_F_KINETIC = 4


def _tafel_fit(species: str) -> tuple[float, float, list[tuple[float, float]]]:
    """Slope (mV/dec), intercept (V), and the fitted (j, eta) points.

    The slope is `data.tafel_slope`'s number, verbatim. Only the intercept is
    derived here -- from the same points and that same slope -- so the line
    on the page carries exactly the slope the annotation quotes.
    """
    slope_mv = data.tafel_slope(species, _F_KINETIC)
    pairs = [(j, abs(v) - data.E_EQ)
             for v, j in zip(data.POTENTIALS[:_F_KINETIC],
                             data.PARTIAL_CURRENT[species][:_F_KINETIC])
             if j > 0.0]
    logs = [math.log10(j) for j, _ in pairs]
    etas = [eta for _, eta in pairs]
    intercept = sum(etas) / len(etas) - slope_mv / 1000.0 * sum(logs) / len(logs)
    return slope_mv, intercept, pairs


def panel_f(width: float = common.COLUMN) -> Diagram:
    """Overpotential against log partial current, fits, and the transport wall.

    CH4 is drawn but not fitted: `data.tafel_slope` refuses it, because CH4
    is below the detection limit over the whole kinetic branch -- every point
    it does have is already transport-influenced, and a slope fitted there
    would be a number about the diffusion layer, not the catalyst. Its row in
    the key says so instead of quoting a slope; its markers, like everyone
    else's, are tied to the row by colour alone.
    """
    th = inklet.current_theme()
    # Transport owns the picture once it costs the kinetics 10% of their
    # current: j = j_k * J/(j_k + J) = 0.9 j_k exactly at j_k = J/9. Shading
    # starts there -- a derived boundary, not a tuned one.
    bend = data.J_LIMIT / 9.0

    def make(area_w: float) -> Diagram:
        area_h = _F_ASPECT * width
        p = inklet.panel(area_w, area_h, x=inklet.log(_F_DOMAIN), y=(0.45, 1.30))
        box = p.area

        # kind="mark": the band's left edge is arithmetic on J_LIMIT, so its
        # position is data and its distance to the points inside it is not a
        # layout question (cookbook, "Telling the linter a position is data").
        p.under(inklet.polygon(((p.x.map(bend), box.y0),
                             (box.x1, box.y0), (box.x1, box.y1),
                             (p.x.map(bend), box.y1)),
                            fill=inklet.mix(th.ink, th.paper, 0.93),
                            stroke="none", kind="mark"))
        at_limit = p.x.map(data.J_LIMIT)
        p.under(inklet.polyline(((at_limit, box.y0), (at_limit, box.y1)),
                             stroke=th.muted, stroke_width=th.stroke,
                             stroke_dash=(1.4, 1.0), fill="none",
                             kind="mark"))
        tag = inklet.label(f"j_{{lim}} = {data.J_LIMIT:.0f} mA cm^{{−2}}",
                        text_fill=th.muted).rotated(-90.0)
        # Low on the rule, not centred: H2 hugs the limit near the top of the
        # panel, so mid-height there is no lane a turned label fits in. High
        # current only ever comes with high overpotential here, which leaves
        # the rule's lower stretch empty by the same physics that empties the
        # top-left corner for the key.
        p.over(_at(tag, at_limit - 1.2 - tag.bbox.width / 2,
                   box.y1 - tag.bbox.height / 2 - th.gap("s")))

        rows: list[Diagram] = []
        for species in _E_STACK:
            colour = _species_colour(th, species)
            series = [(j, abs(v) - data.E_EQ)
                      for v, j in zip(data.POTENTIALS,
                                      data.PARTIAL_CURRENT[species])
                      if j > 0.0]           # a zero has no logarithm; CO's
                                            # last point is below detection
            try:
                slope_mv, intercept, fitted = _tafel_fit(species)
            except ValueError:
                # No slope to quote, and no room to say so at the points
                # themselves: CH4's top marker sits 3.7mm from HCOO's, less
                # than a label plus the linter's clearance on either side.
                rows.append(inklet.label(
                    f"{common.SPECIES_LABEL[species]}  no kinetic branch",
                    align="start", text_fill=colour))
                slope_mv = None
            if slope_mv is not None:
                lo = min(j for j, _ in fitted) / 2.0
                hi = max(j for j, _ in fitted) * 3.0
                p.line([(lo, intercept + slope_mv / 1000.0 * math.log10(lo)),
                        (hi, intercept + slope_mv / 1000.0 * math.log10(hi))],
                       stroke=colour, stroke_width=th.stroke, kind="mark")
                rows.append(inklet.label(
                    f"{common.SPECIES_LABEL[species]}  "
                    f"{slope_mv:.1f} mV dec^{{−1}}",
                    align="start", text_fill=colour))
            p.marks(inklet.marker("circle", th.font_size * 0.5, fill=colour),
                    series)

        # Top-left is empty by the physics: low current only ever comes with
        # low overpotential here, so the key costs no data ink.
        p.over(_corner(inklet.vstack(rows, gap=th.gap("2xs") * 1.5, align="left"),
                       box, "nw", th.gap("s")))
        p.axes(x="partial current density j_{i} / mA cm^{−2}",
               y="overpotential η / V")
        return p.build()

    return common.fit(make, width)


# =====================================================================
# g -- operando XRD, full width
# =====================================================================

#: Heatmap height as a fraction of the panel width. 16 patterns land on rows
#: a little over 3mm tall -- enough for the transition to read as a band, not
#: so much that a full-width panel eats a third of the page.
_G_ASPECT = 0.30

#: Of the drive width, how much the map takes against the trace plot. The
#: map carries 64 columns and the traces two lines, so the split is not even.
_G_MAP_SHARE = 0.74

#: Time ticks: a round subset of the acquisition schedule itself, so every
#: label sits on a real pattern. Automatic thinning would keep the stride-2
#: series 0, 8, 16, 25, ... -- truthful, but a reader orients by round times.
_G_TIME_TICKS = (0, 30, 60, 90, 150)


def _argpeak(rows: Sequence[int], lo: float, hi: float) -> float:
    """The 2-theta of the strongest reflection in a window, measured from the
    mean of the given patterns -- so a phase label sits where *this* data
    peaks, not where a textbook says the peak should be. The window only says
    where to look."""
    profile = [sum(data.XRD[r][i] for r in rows) / len(rows)
               for i in range(len(data.TWO_THETA))]
    best = max((i for i, a in enumerate(data.TWO_THETA) if lo <= a <= hi),
               key=lambda i: profile[i])
    return data.TWO_THETA[best]


def _half_time() -> tuple[float, int, float]:
    """When the Cu(111) area overtakes the Cu2O(111) area.

    Quoted as the crossing of the two integrated traces, interpolated between
    the patterns that bracket it -- an observable read off `XRD_OXIDE` and
    `XRD_METAL`, not the generator's hidden sigmoid. Returns the time, the
    index of the pattern before the crossing, and the fraction between it and
    the next, which is what the y placement needs.
    """
    for k in range(len(data.XRD_TIMES) - 1):
        before = data.XRD_OXIDE[k] - data.XRD_METAL[k]
        after = data.XRD_OXIDE[k + 1] - data.XRD_METAL[k + 1]
        if before >= 0.0 > after:
            f = before / (before - after)
            t = data.XRD_TIMES[k] + f * (data.XRD_TIMES[k + 1]
                                         - data.XRD_TIMES[k])
            return t, k, f
    raise ValueError("the metal trace never overtakes the oxide trace")


def panel_g(width: float = common.FULL) -> Diagram:
    """The oxide reducing under load: intensity map, integrated traces, key.

    The traces share the map's time axis by sharing its *scale*: both panels
    are built on the same band over `XRD_TIMES` at the same height, and
    `inklet.row` aligns plot areas -- so a horizontal line through a pattern in
    the map passes through that pattern's point in the traces with no
    coordinate ever written down.

    Cu(200) at 50.4 degrees falls outside the measured 28-43.75 degree
    window, so it is not labelled: a label for a reflection the data does not
    contain would be an annotation of nothing.
    """
    th = inklet.current_theme()
    value = inklet.linear((0.0, 1.0))          # one object for map and key, so
    shades = inklet.ramp("tol-ylorbr")         # they cannot disagree (cookbook)
    times = data.XRD_TIMES
    yscale = inklet.band(times, padding=0.0, outer=0.0)
    step = data.TWO_THETA[1] - data.TWO_THETA[0]
    # Half a step beyond the sampled centres, so the edge cells fill to the
    # frame instead of hanging half outside it.
    xdom = (data.TWO_THETA[0] - step / 2, data.TWO_THETA[-1] + step / 2)

    early, late = (0, 1, 2), (13, 14, 15)
    ox111 = _argpeak(early, xdom[0], 40.0)
    ox200 = _argpeak(early, 40.0, 43.0)
    cu111 = _argpeak(late, 42.5, xdom[1])
    t_half, k_half, f_half = _half_time()

    # Vermillion for the phase that is literally a red solid; blue for the
    # metal, maximally apart from it under CVD. At 4.5:1 because the same
    # colours also *write* -- the phase names are text on paper.
    oxide_c = th.ink_color(6, min_ratio=4.5)
    metal_c = th.ink_color(5, min_ratio=4.5)

    def make(drive: float) -> Diagram:
        heat_w = _G_MAP_SHARE * drive
        tr_w = drive - heat_w
        heat_h = _G_ASPECT * width

        heat = inklet.panel(heat_w, heat_h, x=xdom, y=yscale)
        heat.matrix(data.XRD, ramp=shades, scale=value,
                    x=data.TWO_THETA, y=times)
        heat.outline(stroke=th.ink, stroke_width=th.hairline)
        heat.axis("bottom", label="2θ / degrees", count=4)
        heat.axis("left", label="time / min", ticks=_G_TIME_TICKS,
                  format=lambda t: f"{t:g}")

        # Phase labels go *above* the map, not on it: a plate over the cells
        # would cover the very intensities the panel exists to show, and the
        # linter rightly reports the collision. Each label stands over its
        # reflection with a leader tick down to the frame; the middle one
        # takes a second tier, because Cu2O(200) and Cu(111) are one degree
        # apart and their names are wider than that.
        box = heat.area
        # 2.8, not a rounder factor: the matrix cells overlap the frame edge
        # by their antialias bleed, so the first tier needs the linter's
        # millimetre measured from the cells' true tops, not from the frame.
        drop = th.gap("2xs") * 2.8
        row_h = inklet.label("Cu").bbox.height + 1.6
        for name, angle, colour, tier in (
                ("Cu_{2}O (111)", ox111, oxide_c, 0),
                ("Cu_{2}O (200)", ox200, oxide_c, 1),
                ("Cu (111)", cu111, metal_c, 0)):
            label = inklet.label(name, text_fill=colour)
            span = label.bbox
            at = heat.x.map(angle)
            top = box.y0 - drop - tier * row_h
            heat.over(inklet.polyline(((at, box.y0), (at, top + 0.3)),
                                   stroke=th.muted, stroke_width=th.hairline,
                                   fill="none"))
            # Clamped to the frame: Cu(111) diffracts half a degree from the
            # window edge, and a centred name would hang out over the gap.
            x = min(max(at, box.x0 + span.width / 2),
                    box.x1 - span.width / 2)
            heat.over(_at(label, x, top - span.height / 2))

        traces = inklet.panel(tr_w, heat_h, x=(0.0, 0.6), y=yscale)
        for series, colour in ((data.XRD_OXIDE, oxide_c),
                               (data.XRD_METAL, metal_c)):
            traces.line(list(zip(series, times)), stroke=colour,
                        stroke_width=th.stroke)
            traces.marks(inklet.marker("circle", th.font_size * 0.45,
                                    fill=colour), zip(series, times))
        traces.axis("bottom", label="peak area / a.u.", count=3)
        # The map already names the reflections in full; the traces only need
        # to say which phase is which. Each name goes in the open field its
        # own curve leaves behind -- the oxide starts strong at the bottom,
        # so the bottom-middle is empty of metal; and vice versa at the top.
        tbox = traces.area
        for name, colour, x_at, y_at in (("Cu_{2}O", oxide_c, 0.24, times[1]),
                                         ("Cu", metal_c, 0.27, times[-2])):
            traces.over(_at(inklet.label(name, text_fill=colour),
                            traces.x.map(x_at), traces.y.map(y_at)))

        # The half-time, in both frames. Interpolating between the two
        # bracketing band centres keeps the rule honest about the sampling:
        # the crossing happened somewhere inside a 10-minute gap.
        y_half = (yscale_mm := traces.y).map(times[k_half]) + f_half * (
            yscale_mm.map(times[k_half + 1]) - yscale_mm.map(times[k_half]))
        for pane in (heat, traces):
            b = pane.area
            pane.over(inklet.polyline(((b.x0, y_half), (b.x1, y_half)),
                                   stroke=th.accent, stroke_width=th.hairline,
                                   stroke_dash=(1.1, 0.9), fill="none",
                                   kind="mark"))
        # Two lines rather than one: set on one line the note is 12mm wide
        # and there is no 12mm of empty trace field at that height -- broken,
        # it fits under the rule against the right spine, where the curves
        # have already crossed away to the left.
        note = inklet.label(f"t_{{1/2}} = {t_half:.0f} min".replace(" = ", " =\n"),
                         text_fill=th.accent, align="end")
        traces.over(_at(note, tbox.x1 - th.gap("2xs") - note.bbox.width / 2,
                        y_half + th.gap("2xs") + note.bbox.height / 2))

        key = inklet.colorbar(shades, domain=(0.0, 1.0), scale=value,
                           length=heat_h, thickness=th.font_size * 1.2,
                           side="right", label="intensity / a.u.", count=3)
        return inklet.row([heat, traces, key], gap=th.gap("m"))

    return common.fit(make, width)


# =====================================================================
# h -- operando FTIR waterfall
# =====================================================================

_H_ASPECT = 0.68

#: Vertical spacing between traces, as a fraction of the tallest band in the
#: series. At 0.8 a strong band may just graze the trace above -- the classic
#: waterfall overlap -- while the baselines stay unmistakably separate.
_H_OFFSET_OF_PEAK = 0.8

#: The absorbance the scale bar demonstrates.
_H_BAR = 0.2


def panel_h(width: float = common.COLUMN) -> Diagram:
    """Four spectra offset into a waterfall, bands named, potentials labelled.

    The wavenumber axis runs high on the left to low on the right, because
    that is how every IR spectrum since the dispersive instruments has been
    printed and a reader's band positions are memorised in that frame; the
    library takes a descending domain natively, so the reversal is one line.

    There is a scale bar instead of a y axis: the offsets make each trace's
    ordinate origin arbitrary, so axis numbers would attach meaning to
    positions that have none. The one honest fact -- how tall 0.2 a.u. is --
    is exactly what a bar states, at a fraction of the margin an axis costs.
    """
    th = inklet.current_theme()
    peak = max(max(row) for row in data.FTIR)
    offset = _H_OFFSET_OF_PEAK * peak
    ceiling = offset * (len(data.FTIR) - 1) + max(data.FTIR[-1]) + 0.05
    # Left to right: high to low. The round 2000 end leaves the 1905 band a
    # margin; the data itself stops at 1995/1200.
    xdom = (2000.0, 1200.0)

    def make(area_w: float) -> Diagram:
        area_h = _H_ASPECT * width
        p = inklet.panel(area_w, area_h, x=xdom, y=(-0.06, ceiling))
        box = p.area

        # Band guides first, under the traces. Two staggered tiers of
        # horizontal labels: rotated assignments would cost 16mm of height,
        # and at these band spacings alternate tiers are enough to keep
        # neighbours clear. A guide runs up to its own label, so the tier a
        # label sits in can never detach it from its band.
        # 1.8mm of air between the two tiers' boxes: neighbouring assignments
        # overlap in x, so the tiers are what separates them and the gap has
        # to clear the linter's 1mm floor on its own.
        row_h = max(inklet.label(b[4]).bbox.height for b in data.FTIR_BANDS) + 1.8
        ordered = sorted(data.FTIR_BANDS, key=lambda b: -b[0])
        for rank, (centre, _, _, _, assignment) in enumerate(ordered):
            tier = rank % 2
            at = p.x.map(centre)
            label = inklet.label(assignment, text_fill=th.muted)
            top = box.y0 - th.gap("2xs") - tier * row_h
            p.under(inklet.polyline(((at, box.y1), (at, top)),
                                 stroke=th.grid, stroke_width=th.hairline,
                                 stroke_dash=(0.9, 0.7), fill="none",
                                 kind="gridline"))
            p.over(_at(label, at, top - label.bbox.height / 2 - 0.3))

        # The waterfall, first spectrum at the bottom: the potential falls as
        # the run proceeds, so height tracks time exactly as it does in (g).
        for index, (potential, row) in enumerate(zip(data.FTIR_POTENTIALS,
                                                     data.FTIR)):
            lift = index * offset
            p.line([(k, v + lift) for k, v in zip(data.WAVENUMBERS, row)],
                   stroke=th.ink, stroke_width=th.stroke)
            # Labelled at the low-wavenumber end, the one stretch (below the
            # 1382 band) where every spectrum is flat baseline.
            tag = inklet.label(f"{potential:.2f} V")
            p.over(_at(tag, box.x1 - th.gap("xs") - tag.bbox.width / 2,
                       p.y.map(lift + 0.06) - tag.bbox.height / 2))

        # The scale bar, in the margin a y axis would have occupied.
        bar_x = box.x0 - th.gap("s")
        y0, y1 = p.y.map(0.05), p.y.map(0.05 + _H_BAR)
        cap = 0.8
        p.over(inklet.polyline(((bar_x, y0), (bar_x, y1)), stroke=th.ink,
                            stroke_width=th.stroke, fill="none"),
               inklet.polyline(((bar_x - cap, y0), (bar_x + cap, y0)),
                            stroke=th.ink, stroke_width=th.stroke,
                            fill="none"),
               inklet.polyline(((bar_x - cap, y1), (bar_x + cap, y1)),
                            stroke=th.ink, stroke_width=th.stroke,
                            fill="none"))
        tag = inklet.label(f"{_H_BAR:g} a.u.").rotated(-90.0)
        p.over(_at(tag, bar_x - th.gap("2xs") - tag.bbox.width / 2,
                   (y0 + y1) / 2))

        p.axis("bottom", label="wavenumber / cm^{−1}", count=5)
        return p.build()

    return common.fit(make, width)


# =====================================================================
# looking at it
# =====================================================================

if __name__ == "__main__":
    import dataclasses
    import time

    # The nature theme, in the face this machine actually has: Helvetica is
    # not installed here, and shipping a figure shaped in a silently
    # substituted font is what FONT_SUBSTITUTED exists to catch. Same dodge
    # as `stress/panels/responses.py`.
    inklet.use_theme(dataclasses.replace(inklet.theme("nature"),
                                      font_family="Noto Sans"))

    def timed(name, fn, *args):
        start = time.perf_counter()
        node = fn(*args)
        print(f"  {name} built in {time.perf_counter() - start:6.3f} s  "
              f"{node.bbox.width:6.2f} x {node.bbox.height:6.2f} mm")
        return node

    print("panels")
    e = timed("panel_e", panel_e, common.COLUMN)
    f = timed("panel_f", panel_f, common.COLUMN)
    g = timed("panel_g", panel_g, common.FULL)
    h = timed("panel_h", panel_h, common.COLUMN)

    # A proof sheet of this module's four panels at print size -- the full
    # figure composes all twelve elsewhere.
    sheet = inklet.vstack([
        inklet.hstack([common.titled("e", e), common.titled("f", f)],
                   gap=common.FULL - 2 * common.COLUMN, align="top"),
        common.titled("g", g),
        common.titled("h", h),
    ], gap=8.0, align="left")

    fig = inklet.figure(width=common.PAGE_WIDTH)
    fig.add(sheet)
    print(fig.report())
    fig.save("stress/electro/kinetics.svg")
