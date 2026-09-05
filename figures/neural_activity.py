"""Learning curves, spike raster, and endpoint statistics from simulated data.

Run from the repository root: python figures/neural_activity.py.
All observations are generated locally from fixed seeds; no anatomical assets
or experimental observations are used.
"""
from __future__ import annotations
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import inklet
import mouse_brain_data as data

TH = inklet.use_theme("nature")
GAP = 5.0
OPSIN = TH.color(5)
OPSIN_INK = inklet.readable(OPSIN, TH.paper)
CONTROL = inklet.mix(TH.ink, TH.paper, 0.42)
LIGHT = inklet.mix(OPSIN, TH.paper, 0.86)

def panel_c(width: float, height: float = 30.0) -> inklet.Diagram:
    curves = {group: data.learning(group) for group in data.GROUPS}
    colour = {"ChR2": OPSIN, "eYFP": CONTROL}

    p = inklet.panel(width, height, x=(0.6, 8.4), y=(45.0, 95.0))
    p.grid(x=False, y=True, count=4, stroke=TH.grid, stroke_width=TH.hairline)
    # Chance, named on the axis rather than in the key: a reader who does not
    # know that 50% is chance on a two-port task cannot read the panel, and a
    # legend row spends a whole line saying so.
    p.hline(50.0, stroke=TH.muted, stroke_width=TH.hairline,
            stroke_dash=(1.1, 0.9), label="chance", label_side="n")
    for group in data.GROUPS:
        curve = curves[group]
        p.band(data.DAYS, curve.lo, curve.hi, color=colour[group],
               fill_opacity=0.20, stroke="none")
    for group in data.GROUPS:
        curve = curves[group]
        p.line(list(zip(data.DAYS, curve.mean)), stroke=colour[group],
               stroke_width=TH.stroke,
               name=f"{group} (//n// = {data.COHORT[group]})")
        p.marks(inklet.marker("circle", 1.0, fill=colour[group], stroke=TH.paper,
                           stroke_width=TH.hairline),
                list(zip(data.DAYS, curve.mean)))
    p.axis("bottom", ticks=list(data.DAYS), label="training session (d)")
    p.axis("left", ticks=[50, 60, 70, 80, 90], label="correct (%)")
    # North-west: the curves both start at chance and climb, so the top left
    # is the one quarter of the panel the data never reaches.
    p.legend(corner="nw", swatch=1.5)
    return p


def _steps(low: float, high: float, by: float) -> list[float]:
    """Tick positions from `low` to `high` inclusive -- `range` for floats."""
    return [low + by * i for i in range(int(round((high - low) / by)) + 1)]


def panel_d(width: float) -> inklet.Diagram:
    trains = data.spike_trains()
    centres, rates = data.psth(trains)
    span = data.WINDOW

    raster = inklet.panel(width, 24.0, x=span, y=(data.TRIALS + 0.5, 0.5))
    raster.vspan(*data.STIM, fill=LIGHT, stroke="none")
    tick = inklet.polyline([(0.0, -0.38), (0.0, 0.38)], stroke=TH.ink,
                        stroke_width=TH.hairline, kind="mark-line")
    for index, train in enumerate(trains):
        raster.marks(tick, [(t, index + 1) for t in train])
    raster.axis("left", ticks=[1, 10, 20, data.TRIALS], label="trial")
    raster.text(sum(data.STIM) / 2.0, 0.5, "473 nm, 0.5 s",
                size=TH.font_size_small * 0.92, text_fill=OPSIN_INK,
                anchor="s", offset=(0.0, -0.8))

    top = 10.0 * math.ceil(max(rates) / 10.0)
    hist = inklet.panel(width, 16.0, x=span, y=(0.0, top))
    hist.vspan(*data.STIM, fill=LIGHT, stroke="none")
    # `fill` runs a straight edge between the points it is given, so a filled
    # histogram has to be handed the staircase itself: two points per bin, at
    # the bin's own edges. Feeding it bin centres draws a mountain range whose
    # peaks sit half a bin away from the counts they claim to show.
    stair = [(centres[0] - data.BIN / 2.0, 0.0)]
    for centre, value in zip(centres, rates):
        stair.append((centre - data.BIN / 2.0, value))
        stair.append((centre + data.BIN / 2.0, value))
    stair.append((centres[-1] + data.BIN / 2.0, 0.0))
    hist.fill(stair, fill=inklet.mix(TH.ink, TH.paper, 0.62), stroke="none")
    hist.step(list(zip(centres, rates)), where="mid", stroke=TH.ink,
              stroke_width=TH.hairline)
    hist.axis("bottom", ticks=[-0.5, 0.0, 0.5, 1.0, 1.5],
              label="time from cue (s)")
    hist.axis("left", ticks=[int(t) for t in _steps(0.0, top, 10.0)],
              label="rate (Hz)")
    return inklet.column([raster, hist], gap=1.6)


def panel_e(width: float, height: float = 30.0) -> inklet.Diagram:
    scores = {group: data.endpoint(group) for group in data.GROUPS}
    colour = {"ChR2": OPSIN, "eYFP": CONTROL}
    p_value = data.permutation_p(scores["ChR2"], scores["eYFP"])

    p = inklet.panel(width, height, x=list(data.GROUPS), y=(55.0, 107.0))
    p.grid(x=False, y=True, count=3, stroke=TH.grid, stroke_width=TH.hairline)
    # One dot per animal, laid out by the beeswarm. What this replaces was a
    # golden-ratio jitter that never jittered: it offset each animal by
    # millimetres and then asked `p.x.invert` for the data value under that
    # offset, and a band scale answers with the nearest *category*, so all
    # twenty-three animals came back on their own tick. Nine pairs of them
    # were closer together than a dot is wide, which on paper is one animal
    # drawn over another. The swarm moves dots sideways and never along the
    # value axis, so every dot still sits at the score it earned -- which is
    # what lets the mean, the interval and the bracket be drawn over the very
    # numbers the dots stand for.
    p.swarm({group: scores[group] for group in data.GROUPS}, size=0.85,
            hollow=True, max_width=6.0,
            colors=[colour[group] for group in data.GROUPS])
    for group in data.GROUPS:
        values = scores[group]
        centre = p.x.map(group)
        mean, sem = data.mean_sem(values)
        p.errorbars([(group, mean)], yerr=sem, stroke=colour[group],
                    stroke_width=TH.stroke, cap=1.6)
        p.draw(inklet.polyline([(centre - 3.6, p.y.map(mean)),
                             (centre + 3.6, p.y.map(mean))],
                            stroke=colour[group], stroke_width=TH.stroke,
                            kind="mark-line"))
    # The bracket sits at 101, a point clear of the highest animal, and its
    # label sits above the bracket -- so the top of the y range has to leave
    # room for a line of type as well as for the data. 105 did not: the `***`
    # overhung the plot box by 0.66 mm and ate into the gap to panel (d).
    # 107 is the first round number that clears it, and it costs nothing
    # visible because the ticks stop at 100 either way.
    p.bracket(data.GROUPS[0], data.GROUPS[1], 101.0,
              text=data.stars(p_value), size=TH.font_size_small)
    # No axis name under the ticks: the ticks are the group names, and
    # "group" written beneath them is a line of type that says nothing.
    p.axis("bottom", ticks=list(data.GROUPS))
    p.axis("left", ticks=[60, 70, 80, 90, 100], label="session 8 correct (%)")
    return p

def build():
    parts = [panel_c(47.0, height=34.0), panel_d(55.0), panel_e(29.0, height=34.0)]
    fig = inklet.figure(width=183, theme=TH, margin=4)
    fig.add(inklet.column([
        inklet.row(inklet.letters(parts), gap=GAP, align="top"),
        inklet.text("Simulated learning, spike timing and endpoint observations. No experiment was performed.",
                    width=175, size=TH.font_size_small),
    ], gap=6))
    return fig


if __name__ == "__main__":
    out = Path("out/neural-activity")
    out.mkdir(parents=True, exist_ok=True)
    build().save(out / "neural-activity.svg", out / "neural-activity.pdf")
