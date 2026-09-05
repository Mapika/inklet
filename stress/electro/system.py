"""Panels i-l: the electrolyser as a system rather than as an electrode.

Four views of the same operating point, every number from `electro/data.py`:

* `panel_i` follows 100 carbon atoms through one pass -- a single-column
  Sankey whose ribbons are closed cubic bands built the way
  `stress/panels/relations.panel_l` builds them, so a width *is* a flux.
* `panel_j` is the 500-hour pilot run: three strips on one clock, because the
  three quantities share nothing but time (the choice is argued at the
  function).
* `panel_k` is the process loop, and it is deliberately the router's exam:
  a recycle arm that has to get from the bottom of the flowsheet back to the
  top without crossing the forward path (`route="avoid"`), and an anolyte
  loop drawn orthogonally on the other side.
* `panel_l` is four cyclic voltammograms as small multiples on shared scales,
  furniture drawn once at the grid's edge rather than four times.

Colour discipline: a species is looked up in `common.SPECIES` wherever it
appears, so the C2H4 ribbon in (i), the FE trace in (j) and the product
stream in (k) are the same orange. Nothing here reads a file or the clock.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Sequence

import inklet
from inklet import Diagram, Vec2
from inklet.plot import ribbon_between

try:
    from . import common, data
except ImportError:                                     # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from electro import common, data

__all__ = ["panel_i", "panel_j", "panel_k", "panel_l"]

_EPS = 1e-9

#: The order carbon leaves the cell in, top to bottom: products by falling
#: flux, then the unconverted stream last -- so the big grey recycle band
#: underlines the products instead of splitting them.
_FLOW_ORDER = ("C2H4", "CO", "CH4", "HCOO", "recycle")


def _species_color(th, key: str) -> str:
    """The one colour a species is allowed to be, panel to panel. The recycle
    stream is not a species -- it is the absence of a reaction -- so it gets
    the muted ink instead of a palette slot."""
    return th.muted if key == "recycle" else th.color(common.SPECIES[key])


def _tiny(th) -> float:
    """Annotation type that has to fit inside geometry rather than beside it.
    A fraction of the theme's small size, not a pinned point value, for the
    reasons `stress/panels/relations._tiny` gives."""
    return th.font_size_small * 0.86


def _plate(th, node: Diagram) -> Diagram:
    """An opaque backing, so a label crossing a rule or a shaft stays legible
    without being dragged away from the thing it names."""
    return inklet.frame(node, pad=0.4, kind="label-plate").styled(
        fill=th.paper, stroke="none")


# =====================================================================
# ribbon geometry (the idiom of stress/panels/relations)
# =====================================================================

def _ribbon(a0: Vec2, a1: Vec2, b0: Vec2, b1: Vec2,
            tension: float = 0.55) -> Diagram:
    """A closed band from segment a0-a1 to segment b0-b1, flowing along +x.

    `inklet.plot.ribbon_between` does the geometry -- the hand-rolled copy this
    module used to carry produced the identical outline, `kind="mark"` and
    all. The flow direction is pinned rather than inferred because a stage
    whose flux has fallen to nothing has no end face to take a normal from.
    """
    return ribbon_between(a0, a1, b0, b1, along=Vec2(1.0, 0.0), ease=tension)


def _bar(x0: float, y0: float, x1: float, y1: float, **style) -> Diagram:
    return inklet.polygon(((x0, y0), (x1, y0), (x1, y1), (x0, y1)),
                       kind="mark", **style)


# =====================================================================
# i -- carbon-flux Sankey
# =====================================================================

#: Millimetres per carbon atom. Sets the drawing's height (100 atoms plus the
#: outlet gaps), chosen so the finished panel sits near the 3:2 the page's
#: column bands want.
_I_SCALE = 0.40
_I_GAP = 3.0          # between outlet bars: enough that the 0.7% CH4 label
                      # and its neighbours clear the crowding floor
_I_BAR = 3.0          # bar thickness -- identity, not data


def panel_i(width: float = common.COLUMN) -> Diagram:
    """One pass of carbon through the cell, ribbon width proportional to flux."""
    th = inklet.current_theme()
    return common.fit(lambda drive: _build_sankey(th, drive), width)


def _build_sankey(th, drive: float) -> Diagram:
    flux = data.CARBON
    total = sum(flux.values())
    heights = {k: flux[k] * _I_SCALE for k in _FLOW_ORDER}

    # Outlets: stacked with gaps. Inlet: the same order, contiguous, centred
    # on the outlet stack -- so no ribbon ever crosses another.
    out_h = sum(heights.values()) + _I_GAP * (len(_FLOW_ORDER) - 1)
    in_h = sum(heights.values())
    out_top = -out_h / 2.0
    in_top = -in_h / 2.0

    out_y: dict[str, float] = {}
    cursor = out_top
    for key in _FLOW_ORDER:
        out_y[key] = cursor
        cursor += heights[key] + _I_GAP
    in_y: dict[str, float] = {}
    cursor = in_top
    for key in _FLOW_ORDER:
        in_y[key] = cursor
        cursor += heights[key]

    # The parts round to 99.99; the balance the panel asserts is the rounded
    # total, which is what "closes at 100%" means for reported figures.
    feed = inklet.text(f"CO_{{2}} feed\n{total:.0f} C", size=th.font_size_small,
                    align="right")
    labels = {key: inklet.text(f"{common.SPECIES_LABEL[key]}  {flux[key]:.1f} %"
                            if key != "recycle"
                            else f"unconverted  {flux[key]:.1f} %",
                            size=_tiny(th), align="left")
              for key in _FLOW_ORDER}
    closure = inklet.text(f"Σ {total:.0f} %", size=_tiny(th))

    # The run is whatever the measured furniture leaves of the target width;
    # the floor keeps a huge theme from folding the ribbons to nothing.
    gap = th.gap("s")
    label_w = max(node.bbox.width for node in labels.values())
    fixed = (feed.bbox.width + gap + _I_BAR + _I_BAR + 1.2 + label_w
             + gap + closure.bbox.height + 1.6)
    run = max(drive - fixed, 14.0)

    x_in = 0.0
    x_out = x_in + _I_BAR + run

    # Everything goes through ONE `place` call: a placed group is re-centred
    # on its own bbox, so two calls sharing a coordinate frame silently stop
    # sharing it the moment their contents differ. Side-anchored text is
    # therefore shifted to its centre point here by half its own box.
    items: list = []

    def west(at: Vec2, node: Diagram) -> None:
        items.append((at + Vec2(node.bbox.width / 2.0, 0.0), node))

    def east(at: Vec2, node: Diagram) -> None:
        items.append((at - Vec2(node.bbox.width / 2.0, 0.0), node))

    for index, key in enumerate(_FLOW_ORDER):
        color = _species_color(th, key)
        h = heights[key]
        a0 = Vec2(x_in + _I_BAR, in_y[key])
        a1 = Vec2(x_in + _I_BAR, in_y[key] + h)
        b0 = Vec2(x_out, out_y[key])
        b1 = Vec2(x_out, out_y[key] + h)
        items.append(_ribbon(a0, a1, b0, b1).styled(
            fill=color, stroke="none", opacity=0.5))
        items.append(_bar(x_in, in_y[key], x_in + _I_BAR, in_y[key] + h,
                          fill=color, stroke="none"))
        items.append(_bar(x_out, out_y[key], x_out + _I_BAR, out_y[key] + h,
                          fill=color, stroke="none"))
        west(Vec2(x_out + _I_BAR + 1.2, out_y[key] + h / 2.0), labels[key])

    east(Vec2(x_in - gap, 0.0), feed)

    # The closing bracket: one rule spanning everything that left, its ticks
    # pointing back at the outlets, the rounded total on its far side. This
    # is the carbon balance made visible -- the bracket's reach *is* the sum.
    x_b = x_out + _I_BAR + 1.2 + label_w + gap
    tick = 0.8
    items.append(inklet.polyline(((x_b - tick, out_top), (x_b, out_top),
                               (x_b, out_top + out_h),
                               (x_b - tick, out_top + out_h)),
                              stroke=th.muted, stroke_width=th.hairline))
    items.append((Vec2(x_b + 0.8 + closure.bbox.height / 2.0, 0.0),
                  closure.rotated(90.0).styled(text_fill=th.muted)))

    drawing = inklet.place(items)

    head = inklet.label("where the carbon goes, single pass — ribbon ∝ C atoms",
                     text_fill=th.muted)
    return inklet.vstack([head, drawing], gap=th.gap("s"), align="left")


# =====================================================================
# j -- the 500-hour pilot run
# =====================================================================

#: Strip heights as fractions of the panel width. Current density and FE get
#: equal billing; the voltage is context and gets a shallower strip.
_J_ASPECTS = (0.115, 0.105, 0.075)

_J_OPERATING = 200.0        # mA/cm^2 -- the pilot's set point, drawn as a
                            # reference; data.J_LIMIT (320) is the transport
                            # ceiling the set point stays under.


def _endpoint_mean(series: Sequence[float], count: int = 6) -> tuple[float, float]:
    """The run's first and last `count` points, averaged -- a decline read
    from the data rather than from two noisy endpoints."""
    return (sum(series[:count]) / count, sum(series[-count:]) / count)


def panel_j(width: float = common.FULL) -> Diagram:
    """The pilot run: current density, FE(C2H4) and cell voltage on one clock.

    Three stacked strips sharing an x axis, not one panel with two y axes.
    The three quantities share nothing but time -- different units, different
    directions of "good" -- and twin y axes invite the reader to compare
    slopes across scales that were chosen independently, which is a claim the
    data does not make. Stacked, each quantity keeps an honest scale and the
    flush windows still line up down the column, which is the one comparison
    the panel *is* making.
    """
    th = inklet.current_theme()
    return common.fit(lambda drive: _build_run(th, drive), width)


def _build_run(th, drive: float) -> Diagram:
    area_w = max(drive - 16.0, 40.0)        # measured furniture comes off in fit

    j0, j1 = _endpoint_mean(data.CURRENT_DENSITY)
    fe0, fe1 = _endpoint_mean(data.FE_TRACE)
    v0, v1 = _endpoint_mean(data.CELL_VOLTAGE)

    current = _strip(th, area_w, common.FULL * _J_ASPECTS[0], (160.0, 220.0),
                     data.CURRENT_DENSITY, "j / mA cm^{−2}", th.accent,
                     ticks=(160, 180, 200, 220))
    _flush_windows(th, current)
    _reference_line(th, current)
    _flush_callout(th, current)
    _note(th, current, f"−{(j0 - j1) / j0 * 100.0:.0f} % over 500 h",
          corner="sw")

    fe = _strip(th, area_w, common.FULL * _J_ASPECTS[1], (50.0, 65.0),
                data.FE_TRACE, "FE(C_{2}H_{4}) / %",
                _species_color(th, "C2H4"), ticks=(50, 55, 60, 65))
    _flush_windows(th, fe)
    _note(th, fe, f"−{(fe0 - fe1) / fe0 * 100.0:.0f} % over 500 h",
          corner="sw")

    volts = _strip(th, area_w, common.FULL * _J_ASPECTS[2], (3.4, 3.8),
                   data.CELL_VOLTAGE, "U_{cell} / V", th.color(6),
                   ticks=(3.4, 3.6, 3.8), bottom=True)
    _flush_windows(th, volts)
    _note(th, volts, f"+{v1 - v0:.2f} V over 500 h", corner="nw")

    return inklet.column([current, fe, volts], gap=th.gap("xs"))


def _strip(th, area_w: float, area_h: float, domain: tuple[float, float],
           series: Sequence[float], label: str, color: str, *,
           ticks: Sequence[float], bottom: bool = False) -> inklet.Panel:
    p = inklet.panel(area_w, area_h, x=(0.0, 500.0), y=domain)
    p.line(list(zip(data.HOURS, series)), stroke=color, stroke_width=th.stroke)
    p.axis("left", label=label, ticks=list(ticks))
    if bottom:
        p.axis("bottom", label="time / h", ticks=[0, 100, 200, 300, 400, 500])
    else:
        # A spine with no ticks: the strips above the clock keep their frame
        # but say the time only once, at the bottom of the column.
        p.axis("bottom", tick_size=0, tick_pad=0, format=lambda v: "")
    return p


def _flush_windows(th, p: inklet.Panel) -> None:
    """The two electrolyte flushes, shaded under the data. `under` speaks
    panel millimetres, so the hours go through the x scale first."""
    for start, end in data.FLUSHES:
        x0, x1 = p.x.map(start), p.x.map(end)
        p.under(inklet.polygon(((x0, p.area.y0), (x1, p.area.y0),
                             (x1, p.area.y1), (x0, p.area.y1)),
                            fill=th.grid, stroke="none"))


def _reference_line(th, p: inklet.Panel) -> None:
    """The 200 mA/cm^2 set point, dashed across the run, named at the far
    right where the declined trace has left the headroom empty."""
    y = p.y.map(_J_OPERATING)
    p.over(inklet.polyline(((p.area.x0, y), (p.area.x1, y)),
                        stroke=th.ink, stroke_width=th.hairline,
                        stroke_dash=(1.2, 0.8)))
    tag = _plate(th, inklet.text(f"operating point  {_J_OPERATING:.0f} mA cm^{{−2}}",
                              size=_tiny(th), align="right",
                              text_fill=th.muted))
    box = tag.bbox
    p.over(tag.translated(p.area.x1 - 1.0 - box.width / 2.0 - box.center.x,
                          y - 1.0 - box.height / 2.0 - box.center.y))


def _flush_callout(th, p: inklet.Panel) -> None:
    """One label for the two identical windows, tied to the first by a short
    leader. Labelling both would say the same thing twice; labelling neither
    leaves two grey bars the caption has to rescue."""
    (start, end), _ = data.FLUSHES
    x1 = p.x.map(end)
    y = p.area.y0 + 2.2
    text = _plate(th, inklet.label("electrolyte flush", text_fill=th.muted))
    box = text.bbox
    p.over(
        inklet.polyline(((x1, y), (x1 + 3.0, y)), stroke=th.muted,
                     stroke_width=th.hairline),
        text.translated(x1 + 3.4 + box.width / 2.0 - box.center.x,
                        y - box.center.y),
    )


def _note(th, p: inklet.Panel, content: str, *, corner: str) -> None:
    """A computed annotation in whichever corner the trace leaves empty."""
    node = _plate(th, inklet.label(content, text_fill=th.muted))
    box = node.bbox
    x = p.area.x0 + 1.2 + box.width / 2.0 - box.center.x
    if corner == "sw":
        y = p.area.y1 - 1.2 - box.height / 2.0 - box.center.y
    else:
        y = p.area.y0 + 1.2 + box.height / 2.0 - box.center.y
    p.over(node.translated(x, y))


# =====================================================================
# k -- the pilot process loop
# =====================================================================


def panel_k(width: float = common.COLUMN) -> Diagram:
    """The flowsheet: forward path down the spine, recycle back up the left,
    anolyte loop on the right. The router's exam -- see the module docstring."""
    th = inklet.current_theme()
    return common.fit(lambda drive: _build_loop(th, drive), width)


def _build_loop(th, drive: float) -> Diagram:
    flux = data.CARBON
    total = sum(flux.values())
    fresh = total - flux["recycle"]

    # One measured width for the whole spine: a rank of process units reads
    # as a rank only if the boxes agree on their size.
    names = ("CO_{2} feed", "humidifier", "cell stack",
             "gas–liquid separator", "product knockout",
             "C_{2}H_{4} to compression")
    box_w = max(inklet.box(n).width for n in names)
    boxes = [inklet.box(n, width=box_w) for n in names]
    feed, humidifier, stack, separator, knockout, compression = boxes

    # The gap is label room: every spine arrow carries a stream name beside
    # its shaft, and the shaft is only as long as the gap. 6mm is the least
    # that holds an arrowhead, two standoffs and a plated label's height.
    entry = inklet.label(f"fresh CO_{{2}}  {fresh:.0f} C")
    spine = inklet.vstack([entry] + boxes, gap=6.0)

    # Two ports on the stack's east face. Both anolyte links would otherwise
    # aim at the box's centre, and their orthogonal elbows would leave and
    # arrive along the very same centre-height segment -- one line wearing
    # two arrows. An anchor is a position, used verbatim, which is exactly
    # what a manifold connection wants.
    stack.anchor("anolyte_out", (1.0, 0.28))
    stack.anchor("anolyte_in", (1.0, 0.72))

    side_w = max(inklet.box(n).width for n in ("anolyte\nreservoir", "pump"))
    reservoir = inklet.box("anolyte\nreservoir", width=side_w)
    pump = inklet.box("pump", width=side_w)
    # Centred against the spine, the two-box column lands beside the stack
    # and the separator -- exactly the rows its links want to reach.
    side = inklet.vstack([reservoir, pump], gap=8.0)

    content = inklet.hstack([spine, side], gap=drive * 0.14, align="center")

    def stream(text: str) -> Diagram:
        return _plate(th, inklet.label(text))

    arrow = dict(standoff=0.5, arrow_size=th.arrow_size)
    forward = inklet.Style(stroke=th.ink, stroke_width=th.stroke, fill=th.ink)
    product = inklet.Style(stroke=_species_color(th, "C2H4"),
                        stroke_width=th.thick, fill=_species_color(th, "C2H4"))
    loop = inklet.Style(stroke=th.muted, stroke_width=th.stroke, fill=th.muted)

    links = [
        inklet.link(entry, feed, style=forward, name="fresh", **arrow),
        inklet.link(feed, humidifier, style=forward, name="feed-hum",
                 label=stream(f"CO_{{2}}  {total:.0f} C"), **arrow),
        inklet.link(humidifier, stack, style=forward, name="hum-stack",
                 label=stream("wet CO_{2}"), **arrow),
        inklet.link(stack, separator, style=forward, name="stack-sep",
                 label=stream("gas + liquid"), **arrow),
        inklet.link(separator, knockout, style=forward, name="sep-knock",
                 label=stream("gas"), **arrow),
        inklet.link(knockout, compression, style=product, name="knock-comp",
                 label=stream(f"C_{{2}}H_{{4}}  {flux['C2H4']:.1f} C"), **arrow),
        # The recycle arm. `route="avoid"` rather than a posed elbow: the arm
        # has to clear five boxes and every forward arrow, and the router is
        # the thing on trial here. The label rides the detour's long run.
        inklet.link(knockout, feed, route="avoid", style=loop, name="recycle",
                 label=stream(f"unconverted CO_{{2}}  {flux['recycle']:.0f} C"),
                 **arrow),
        # The anolyte loop, orthogonal on the right: out along the top pair,
        # back along the bottom pair.
        # `label_side="end"`: the route's start corner is where the pump
        # return arrives at the stack, and a mid-shaft label sits on that
        # arrowhead. The label is one word: this link is a short two-elbow
        # jog, and a plate as wide as the whole jog was found to sit *on* it,
        # whiting out its own shaft. "anolyte" is already on the return leg,
        # so the O2 -- what the anode adds -- is the only news to carry.
        inklet.link(stack.at("anolyte_out"), reservoir, route="orthogonal",
                 style=loop, name="anolyte-out", label=stream("O_{2}"),
                 label_side="end", label_offset=1.4, **arrow),
        inklet.link(reservoir, pump, style=loop, name="anolyte-res-pump", **arrow),
        # `label_side="start"`: the return's long run leaves the pump along
        # open paper; its far end climbs the corridor beside the spine, where
        # a mid-shaft label lands on the forward path's stream names.
        inklet.link(pump, stack.at("anolyte_in"), route="orthogonal", style=loop,
                 name="anolyte-in", label=stream("anolyte"),
                 label_side="start", **arrow),
    ]
    routed = inklet.route_all(links, inklet.resolve(content))
    return Diagram(children=(content, routed), kind="panel")


# =====================================================================
# l -- cyclic voltammograms, small multiples
# =====================================================================

#: Plot-area aspect of each multiple. Four of them plus shared furniture come
#: out near 3:2 for the finished panel.
_L_ASPECT = 0.72


def _half_wave(volts: Sequence[float], currents: Sequence[float]) -> float:
    """E at half the forward sweep's rise: interpolated where the cathodic
    current first crosses midway between its extremes. Measured off the trace
    it marks, never asserted."""
    half = len(volts) // 2
    v_f, i_f = volts[:half], currents[:half]
    target = (max(i_f) + min(i_f)) / 2.0
    for k in range(1, len(i_f)):
        if (i_f[k - 1] - target) * (i_f[k] - target) <= 0.0:
            t = (target - i_f[k - 1]) / ((i_f[k] - i_f[k - 1]) or _EPS)
            return v_f[k - 1] + t * (v_f[k] - v_f[k - 1])
    return v_f[-1]


def panel_l(width: float = common.COLUMN) -> Diagram:
    """Loading series CVs: 2x2 small multiples, one pair of scales, one pair
    of axis names."""
    th = inklet.current_theme()
    return common.fit(lambda drive: _build_cvs(th, drive), width)


def _build_cvs(th, drive: float) -> Diagram:
    # Shared domains, computed once over all four traces and rounded out --
    # small multiples that rescale per facet stop being comparable.
    volts_all = [v for vv, _ in data.CVS.values() for v in vv]
    amps_all = [i for _, ii in data.CVS.values() for i in ii]
    x_dom = (math.floor(min(volts_all) * 5.0) / 5.0, 0.0)
    y_dom = (math.floor(min(amps_all)), math.ceil(max(amps_all)))

    x_ticks = [-1.2, -0.8, -0.4, 0.0]
    y_ticks = [-12, -8, -4, 0]

    gap = th.gap("xs")
    area_w = max((drive - 12.0) / 2.0, 16.0)
    area_h = area_w * _L_ASPECT

    def facet(index: int, loading: float) -> Diagram:
        volts, currents = data.CVS[loading]
        left_col = index % 2 == 0
        bottom_row = index >= 2
        p = inklet.panel(area_w, area_h, x=x_dom, y=y_dom)
        p.line(list(zip(volts, currents)), stroke=th.accent,
               stroke_width=th.stroke)

        # The reduction wave, marked at its measured half-wave potential.
        e_half = _half_wave(volts, currents)
        at = p.x.map(e_half)
        p.over(inklet.polyline(((at, p.area.y0), (at, p.area.y1)),
                            stroke=th.muted, stroke_width=th.hairline,
                            stroke_dash=(1.2, 0.8)))
        if index == 0:
            tag = _plate(th, inklet.text("E_{1/2}", size=_tiny(th),
                                      text_fill=th.muted))
            box = tag.bbox
            p.over(tag.translated(at - 1.0 - box.width / 2.0 - box.center.x,
                                  p.area.y1 - 1.4 - box.height / 2.0
                                  - box.center.y))

        # The loading, in the top-left corner the cathodic wave leaves empty.
        name = _plate(th, inklet.text(f"{loading:g} mg cm^{{−2}}",
                                   size=_tiny(th)))
        box = name.bbox
        p.over(name.translated(p.area.x0 + 1.0 + box.width / 2.0 - box.center.x,
                               p.area.y0 + 1.0 + box.height / 2.0 - box.center.y))

        # Edge facets carry the tick labels; inner edges keep the spine only,
        # so the grid shares one set of numbers.
        p.axis("left", ticks=y_ticks) if left_col else \
            p.axis("left", tick_size=0, tick_pad=0, format=lambda v: "")
        p.axis("bottom", ticks=x_ticks) if bottom_row else \
            p.axis("bottom", tick_size=0, tick_pad=0, format=lambda v: "")
        return p

    facets = [facet(i, loading) for i, loading in enumerate(data.LOADINGS)]
    # `inklet.column` aligns plot areas, not bounding boxes -- a bottom facet's
    # outermost tick label overhangs its area, and stacking by bbox would
    # shove the two facets of a column a millimetre out of register.
    left = inklet.column([facets[0], facets[2]], gap=gap)
    right = inklet.column([facets[1], facets[3]], gap=gap)
    body = inklet.hstack([left, right], gap=gap, align="top")

    # Shared axis names, once each. Padding by the furniture asymmetry and
    # centring puts each name on the middle of the plot region rather than
    # the middle of the panel-plus-tick-labels.
    x_furn = left.bbox.width - right.bbox.width         # left tick labels
    y_furn = left.bbox.height - 2.0 * area_h - gap      # bottom tick labels
    x_name = inklet.pad(inklet.text("E / V vs RHE", size=th.font_size_small),
                     0, 0, 0, x_furn)
    y_name = inklet.pad(inklet.text("j / mA cm^{−2}",
                              size=th.font_size_small).rotated(-90.0),
                     0, 0, y_furn, 0)
    return inklet.hstack([y_name,
                       inklet.vstack([body, x_name], gap=th.gap("2xs"),
                                  align="center")],
                      gap=th.gap("xs"), align="center")


# =====================================================================
# looking at it
# =====================================================================

if __name__ == "__main__":
    inklet.use_theme("nature")

    band = inklet.hstack([common.titled("i", panel_i()),
                       common.titled("k", panel_k())],
                      gap=common.FULL - 2.0 * common.COLUMN, align="top")
    page = inklet.vstack([
        band,
        common.titled("j", panel_j()),
        common.titled("l", panel_l()),
    ], gap=6.0, align="left")

    fig = inklet.figure(width=common.PAGE_WIDTH)
    fig.add(page)
    print(fig.report())
    fig.save("stress/electro/system.svg")
    for letter, node in (("i", panel_i()), ("j", panel_j()),
                         ("k", panel_k()), ("l", panel_l())):
        print(f"panel_{letter}: {node.bbox.width:.2f} x {node.bbox.height:.2f} mm")
