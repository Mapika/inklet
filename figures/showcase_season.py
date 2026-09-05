"""A data figure: a raster heatmap and its colorbar, a legend, dates, a peak.

Four things round 2 added, on one 89mm column and sharing one axis: a matrix
big enough that `Panel.matrix` ships it as a PNG at one pixel per cell rather
than as ten thousand rectangles, a `colorbar` that takes its ramp and its scale
from that matrix so the key cannot disagree with the picture, a `legend` built
from the names the series were drawn under, and a `dates` axis whose ticks walk
the calendar instead of adding 30.44 days.

`inklet.column` puts the two plot *areas* on one vertical line -- not the two
bounding boxes, which would drift apart by however wide each panel's y numbers
happen to be. The peak is named in data coordinates with `Panel.annotate`; no
millimetre appears anywhere in this file except the two panel sizes.

    .venv/bin/python figures/showcase_season.py
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import inklet

TH = inklet.use_theme("nature")

W = 58.0
SPAN = ("2024-01-01", "2024-12-31")
WEEKS = 52
DEPTHS = 24            # 0 to 12 m, half a metre a cell

NEW_YEAR = date(2024, 1, 1)

#: The middle of each week, and the week boundaries the cells are drawn on.
DATES = [NEW_YEAR + timedelta(days=7 * w + 3) for w in range(WEEKS)]
EDGES = [NEW_YEAR + timedelta(days=7 * w) for w in range(WEEKS + 1)]


def bloom(week: float) -> float:
    """Two blooms a year -- a sharp spring one, a broad late-summer one."""
    return (18.0 * math.exp(-((week - 17.0) / 2.6) ** 2)
            + 9.0 * math.exp(-((week - 35.0) / 6.0) ** 2) + 0.8)


def surface_temp(week: float) -> float:
    return 11.0 - 8.0 * math.cos((week + 2.0) / WEEKS * 2 * math.pi)


# Chlorophyll falls off below the thermocline, and the thermocline deepens
# through the season, so the field is the surface signal times a depth taper.
FIELD = [[bloom(w) * math.exp(-max(0.0, d * 0.5 - 2.0 - 0.09 * w) ** 2 / 8.0)
          for w in range(WEEKS)] for d in range(DEPTHS)]
CHLORO = [round(bloom(w), 2) for w in range(WEEKS)]
DEEP = [round(FIELD[12][w], 2) for w in range(WEEKS)]
TEMP = [round(surface_temp(w), 2) for w in range(WEEKS)]

PEAK = max(range(WEEKS), key=CHLORO.__getitem__)

# --- the surface series, two scales, one legend ------------------------------

top = inklet.panel(W, 20, x=SPAN, y=(0, 22))
top.line(list(zip(DATES, CHLORO)), name="surface", stroke=TH.ink_color(3))
top.line(list(zip(DATES, DEEP)), name="6 m", stroke=TH.ink_color(5),
         stroke_dash=(1.2, 0.8))
top.annotate(DATES[PEAK], CHLORO[PEAK],
             f"spring bloom\n**{CHLORO[PEAK]:.0f}** µg L^{{-1}}",
             side="ne", dot=True)
# Temperature belongs to the other axis, and the axis is painted in its own
# colour, so it needs no legend row of its own -- which leaves the key
# describing exactly the two series the panel drew, and `legend()` builds it
# from what they were named.
warm = top.twin_y((0, 30), label="surface T / °C", color=TH.color(6))
warm.line(list(zip(DATES, TEMP)), stroke=TH.ink_color(6),
          stroke_width=TH.hairline)
top.axis("left", label="chl //a// / µg L^{-1}")
top.legend(side="top", columns=2)

# --- the depth field, as pixels, with the key it was drawn from --------------

shades = inklet.ramp("tol-ylorbr")
level = inklet.linear((0.0, 20.0))

heat = inklet.panel(W, 26, x=SPAN, y=(12, 0))
heat.matrix(FIELD, ramp=shades, scale=level, raster=True,
            x=EDGES, y=[d * 0.5 for d in range(DEPTHS + 1)])
# No x label: a date axis writes the part every tick shares -- here the
# year -- once past the last tick, so naming the axis "2024" would print
# it twice.
heat.axes(y="depth / m")
heat.colorbar(label="chl //a// / µg L^{-1}")

fig = inklet.figure(width="89mm", theme=TH, margin=4)
fig.add(inklet.column([top, heat], gap=TH.gap("m")))

if __name__ == "__main__":
    print(fig.report())
    fig.save("figures/out/showcase_season.svg")
