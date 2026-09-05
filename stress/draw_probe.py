"""Everything `inklet.draw` and `inklet.plot` can draw, on one page.

Three bands: the primitives on their own, a scatter, and a line plot. The
point is not that each call returns a Diagram -- the tests cover that -- but
that the results are *looked at*: curves smooth, markers centred on their data,
ticks not colliding, axis labels not clipped, and panels of different modalities
lining up on their plot areas rather than on their furniture.
"""
import dataclasses
import math

import inklet

TH = inklet.use_theme(dataclasses.replace(inklet.theme("nature"), font_family="Noto Sans"))


def noise(seed: int):
    """A deterministic pseudo-random stream. `random` would do, but the figure
    has to be byte-identical across processes and Python versions."""
    state = seed
    while True:
        state = (1103515245 * state + 12345) % (1 << 31)
        yield state / (1 << 31)


def captioned(node, text):
    return inklet.vstack([node, inklet.label(text)], gap=2, align="center")


# --- band one: the primitives ------------------------------------------------

ZIGZAG = [(0, 0), (5, -8), (10, 0), (15, -8), (20, 0)]
PENTAGON = [(7.5 * math.cos(math.radians(-90 + 72 * i)),
             7.5 * math.sin(math.radians(-90 + 72 * i))) for i in range(5)]
WAVE = [(x * 2.6, -6 * math.sin(x * 0.8)) for x in range(9)]

polyline = captioned(inklet.polyline(ZIGZAG), "polyline")
polygon = captioned(inklet.polygon(PENTAGON, fill=TH.color(2), stroke=TH.ink), "polygon")

# The curve and the points it must pass through, in one frame -- if the spline
# missed a knot, the marker would sit off it.
smooth = inklet.place(
    [inklet.curve(WAVE, smooth=0.5, stroke=TH.ink_color(1))]
    + [(p, inklet.marker("circle", 1.2, fill=TH.ink_color(1))) for p in WAVE]
)
curve = captioned(smooth, "curve + place")

pie = inklet.place([
    inklet.sector(7.5, start, start + span, fill=TH.color(i), stroke=TH.paper)
    for i, (start, span) in enumerate(((-90, 130), (40, 95), (135, 135)))
])
wedges = captioned(pie, "sector")

rings = inklet.place([
    inklet.arc(7.5, -40, 200, stroke=TH.ink),
    inklet.arc(5, 20, 340, stroke=TH.ink_color(0)),
    # `ink_color`, not `color`: the annulus is the only mark in this swatch
    # with no stroke on it, so its fill is doing the whole job of being seen,
    # and Okabe-Ito's yellow is 1.3:1 on white. `ink_color` is the same hue
    # taken down to text contrast, which is what a fill standing alone needs.
    inklet.sector(7.5, 200, 320, inner=5, fill=TH.ink_color(4), stroke="none"),
])
arcs = captioned(rings, "arc")

glyphs = inklet.hstack(
    [inklet.marker(kind, 2.4, fill=TH.color(i), stroke=TH.ink_color(i))
     for i, kind in enumerate(inklet.draw.MARKER_KINDS)], gap=1.8, align="center")
markers = captioned(glyphs, "marker")

# The escape hatch: cubics given outright, drawn as real beziers.
LOOP = (
    ((0, 0), (6, -10), (14, -10), (20, 0)),
    ((20, 0), (14, 10), (6, 10), (0, 0)),
)
lens = captioned(inklet.path(curves=LOOP, closed=True, fill=TH.color(5),
                          stroke=TH.ink), "path(curves=...)")

primitives = inklet.hstack(
    [polyline, polygon, curve, wedges, arcs, markers, lens], gap=5, align="bottom")


# --- band two: a scatter -----------------------------------------------------

def cloud(seed, slope, spread, count=90):
    stream = noise(seed)
    points = []
    for _ in range(count):
        x = next(stream) * 10
        wobble = (next(stream) + next(stream) + next(stream) - 1.5) * spread
        points.append((x, 1.4 + slope * x + wobble))
    return points

A, B = cloud(7, 0.28, 1.1), cloud(31, 0.10, 0.9)

scatter = inklet.panel(62, 46, x=(0, 10), y=(0, 6))
scatter.background(fill=TH.paper)
scatter.grid(count=5, stroke=TH.grid)
scatter.marks(inklet.marker("circle", 1.8, fill=TH.color(1), opacity=0.85), A)
scatter.marks(inklet.marker("triangle", 1.8, fill=TH.color(2), opacity=0.85), B)
# A fitted line over the data, drawn in the same coordinates as the marks.
scatter.line([(0, 1.4), (10, 1.4 + 2.8)], stroke=TH.ink_color(1), stroke_width=TH.thick)
scatter.axes(x="stimulus / a.u.", y="response / mV")
scatter.title("scatter")

key = inklet.legend(
    [("high gain", inklet.marker("circle", 1.8, fill=TH.color(1))),
     ("low gain", inklet.marker("triangle", 1.8, fill=TH.color(2)))],
    title="cell type",
)


# --- band three: lines, a log axis, a colorbar -------------------------------

DECAY = [(t / 4, 5.2 * math.exp(-t / 9) + 0.35) for t in range(41)]
RISE = [(t / 4, 5.4 * (1 - math.exp(-t / 5)) + 0.3) for t in range(41)]

lines = inklet.panel(62, 46, x=(0, 10), y=(0, 6))
lines.grid(x=False, stroke=TH.grid)
lines.line(DECAY, smooth=0.5, stroke=TH.color(1), stroke_width=TH.thick)
lines.line(RISE, smooth=0.5, stroke=TH.color(2), stroke_width=TH.thick)
lines.marks(inklet.marker("plus", 2.0, stroke=TH.ink), DECAY[::8])
lines.axes(x="time / s", y="fluorescence")
lines.title("lines")

decades = inklet.panel(52, 46, x=(0, 10), y=inklet.log((0.01, 100)))
decades.grid(x=False, stroke=TH.grid)
decades.line([(t / 4, 0.02 * math.exp(t / 5.2)) for t in range(41)],
             stroke=TH.ink_color(3), stroke_width=TH.thick)
decades.marks(inklet.marker("diamond", 1.8, fill=TH.ink_color(3)),
              [(t, 0.02 * math.exp(4 * t / 5.2)) for t in range(11)])
decades.axes(x="time / s", y="counts")
decades.title("log scale")

bar = inklet.colorbar("tol-sunset", domain=(-2, 2), length=46,
                   label="z-score", side="right")

fig = inklet.figure(width=inklet.COLUMN_DOUBLE)
fig.add(inklet.vstack([
    primitives,
    inklet.hstack([scatter.build(), key], gap=6, align="center"),
    # `row` lines the panels up on their plot *areas*: the log panel's tick
    # labels are wider than the linear one's, and stacking by bounding box
    # would leave the two areas at different heights.
    inklet.row([lines, decades, bar], gap=9),
], gap=10, align="center"))

fig.save("stress/draw_probe.svg")
print(fig.report())
