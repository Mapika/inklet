"""Categorical, composition, comparison and time plots on one page.

A double-column figure with a panel for each plot type in this family:

    a  a waterfall from one year's revenue to the next
    b  bars of the mean with SEM error bars and every observation
    c  female-left / male-right diverging bars with dashed mean lines
    d  a population pyramid
    e  Likert responses centred on the neutral level
    f  a mosaic (Marimekko) plot
    g  a waffle chart
    h  a slope chart with two series highlighted
    i  a bump chart of ranks
    j  a stem plot of an impulse response
    k  parallel coordinates coloured by species
    l  a streamgraph
    m  a Gantt chart with a milestone
    n  an event timeline
    o  bullet charts against targets
    p  a calendar heatmap of daily values

All data are simulated or illustrative. Writes
examples/categorical_plot_types.svg, .pdf and .png, and prints the lint
report.

    PYTHONPATH=src .venv/bin/python examples/categorical_plot_types.py
"""

from __future__ import annotations

import datetime as dt
import math
import random

import inklet
from inklet.plot import calendar_weeks, stream_layers, unsigned

rng = random.Random(5)

# -- a: waterfall ------------------------------------------------------------

steps = ["2023", "sales", "serv.", "costs", "tax", "2024"]
waterfall = inklet.panel(35, 30, x=steps, y=(0, 220))
waterfall.grid(x=False, count=4)
waterfall.waterfall(steps, [120, 45, 22, -38, -14, None], totals=["2023", "2024"],
                    labels=True)
waterfall.axes(y="revenue / k€")

# -- b: bars with points -----------------------------------------------------


def sample(mean, sd, n=8):
    return [rng.gauss(mean, sd) for _ in range(n)]


conditions = ["vehicle", "drug"]
bars = inklet.panel(22, 30, x=conditions, y=(0, 14))
bars.barplot(conditions, [[sample(5, 1.2), sample(8, 1.5)],
                          [sample(6, 1.0), sample(11, 1.3)]], names=["WT", "KO"])
bars.axes(y="response / a.u.").legend(side="top")

# -- c: diverging bars -------------------------------------------------------

types = ["DN1", "DN2", "DN3", "DN4", "DN5", "DN6"]
diverging = inklet.panel(30, 30, x=(-30, 30), y=types)
diverging.diverging_bars(types, [[12, 8, 4, 20, 6, 3], [5, 6, 2, 4, 3, 1]],
                         [[10, 9, 7, 14, 9, 4], [4, 7, 3, 8, 2, 2]],
                         names=["sex-specific", "dimorphic"], reference=(8.1, 10.4),
                         titles=("female", "male"))
diverging.axis("bottom", format=unsigned, label="% output")
diverging.axis("left", spine=False, tick_size=0)
diverging.legend(side="top")

# -- d: population pyramid ---------------------------------------------------

ages = ["0-9", "10-19", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80+"]
pyramid = inklet.panel(25, 30, x=(-8, 8), y=ages)
pyramid.pyramid(ages, [5.1, 5.3, 6.0, 6.6, 6.9, 7.1, 6.2, 4.4, 2.9],
                [5.4, 5.6, 6.3, 6.9, 7.0, 6.9, 5.8, 3.7, 1.8], titles=("female", "male"))
pyramid.axes(x="population / %", x_options={"format": unsigned})

# -- e: Likert ---------------------------------------------------------------

levels = ["strongly disagree", "disagree", "neutral", "agree", "strongly agree"]
questions = ["recommend", "reliable", "fast", "easy"]
likert = inklet.panel(46, 20, x=(-100, 100), y=questions)
likert.likert(questions, [[20, 25, 25, 20, 10], [3, 7, 15, 45, 30],
                          [12, 18, 30, 25, 15], [5, 10, 20, 40, 25]], names=levels)
likert.axis("bottom", format=unsigned, label="responses / %")
likert.axis("left", spine=False, tick_size=0)
likert.legend(side="top", columns=3)

# -- f: mosaic ---------------------------------------------------------------

mosaic = inklet.panel(32, 30, x=(0, 100), y=(0, 100))
mosaic.mosaic(["N", "S", "E", "W"], [[30, 12, 8, 20], [20, 30, 10, 5], [10, 8, 12, 15]],
              names=["A", "B", "C"], labels=True)
mosaic.axis("left", format="{:.0f}%").legend(side="right")

# -- g: waffle ---------------------------------------------------------------

waffle = inklet.panel(24, 24)
waffle.waffle([46, 31, 15, 8], names=["neurons", "glia", "vascular", "other"])
waffle.legend(side="right")

# -- h: slope ----------------------------------------------------------------

slope = inklet.panel(16, 30, x=["2015", "2025"], y=(20, 70))
slope.slope({"DK": [42, 61], "ES": [30, 28], "IT": [33, 35], "FR": [45, 52],
             "PL": [25, 41]}, format="{:.0f}", highlight=["DK", "PL"])
slope.axis("top", spine=False, tick_size=0)

# -- i: bump -----------------------------------------------------------------

seasons = ["2021", "2022", "2023", "2024"]
bump = inklet.panel(36, 30, x=seasons, y=(5.5, 0.5))
bump.bump({"Lyon": [3, 5, 8, 9], "Nice": [8, 6, 5, 3], "Lens": [5, 9, 7, 8],
           "Metz": [9, 3, 2, 1], "Brest": [1, 2, 4, 6]}, numbers=True)
bump.axis("top", spine=False, tick_size=0)

# -- j: stem -----------------------------------------------------------------

stem = inklet.panel(34, 30, x=(-1, 32), y=(-0.8, 1.1))
stem.stem([(n, math.exp(-n / 8) * math.cos(n / 2)) for n in range(32)])
stem.axes(x="sample n", y="h[n]")

# -- k: parallel coordinates -------------------------------------------------

records, species = [], []
for s, (length, scale) in enumerate([(5, 1.0), (6.5, 1.4), (8, 1.9)]):
    for _ in range(12):
        size = length + rng.gauss(0, 0.5)
        records.append([size, size * 0.45 + rng.gauss(0, 0.3), 2 + s + rng.gauss(0, 0.4),
                        scale * size * 10 + rng.gauss(0, 8)])
        species.append(["setosa", "versicolor", "virginica"][s])
parallel = inklet.panel(38, 30, x=["length", "width", "depth", "mass"])
parallel.parallel(records, groups=species)
parallel.legend(side="top")

# -- l: bullet ---------------------------------------------------------------

bullet = inklet.panel(40, 12, x=(0, 300), y=["profit", "revenue"])
bullet.bullet(["revenue", "profit"], [270, 180], targets=[250, 210],
              ranges=[150, 225, 300])
bullet.axes(x="k€")

# -- m: streamgraph ----------------------------------------------------------

weeks = list(range(40))
plays = [[max(0.0, 3 + 2.5 * math.sin((w + 7 * g) / (4 + g)) + g * 0.3) for w in weeks]
         for g in range(5)]
layers = stream_layers(plays)
stream = inklet.panel(50, 24, x=(0, 39), y=(min(min(lo) for lo, _ in layers),
                                            max(max(hi) for _, hi in layers)))
stream.streamgraph(weeks, plays, names=["rock", "pop", "jazz", "folk", "hip-hop"])
stream.axis("bottom", label="week").legend(side="right")

# -- n: Gantt ----------------------------------------------------------------

rows = ["launch", "review", "build", "design", "scope"]
gantt = inklet.panel(56, 24, x=("2025-01-01", "2025-07-01"), y=rows)
gantt.gantt([("scope", "2025-01-06", "2025-01-31", "scope"),
             ("design", "2025-01-27", "2025-03-14", "design"),
             ("build", "2025-03-03", "2025-05-30", "build"),
             ("review", "2025-06-02", "2025-06-20"),
             ("launch", "2025-06-23", "2025-06-23")],
            groups=["plan", "plan", "make", "check", "check"], labels=True)
gantt.axes().legend(side="top")

# -- o: timeline -------------------------------------------------------------

timeline = inklet.panel(76, 22, x=("2020-01-01", "2025-01-01"))
timeline.timeline([("2020-03-11", "pandemic declared"), ("2020-12-08", "first vaccine"),
                   ("2021-05-01", "variant found"), ("2021-11-26", "omicron"),
                   ("2022-05-01", "restrictions end"), ("2023-05-05", "emergency over"),
                   ("2024-06-01", "review")])
timeline.axis("bottom")

# -- p: calendar -------------------------------------------------------------

start, end = dt.date(2025, 1, 1), dt.date(2025, 12, 31)
steps_per_day = {}
for d in range(365):
    day = start + dt.timedelta(days=d)
    if d % 17 != 3:
        steps_per_day[day] = (6000 + 3000 * math.sin(d / 20)
                              + (2500 if day.weekday() >= 5 else 0))
cell = 1.75
calendar = inklet.panel(calendar_weeks(start, end) * cell, 7 * cell)
calendar.calendar(steps_per_day, start=start, end=end)
calendar.colorbar(side="right", label="steps")

# -- the page ----------------------------------------------------------------

panels = inklet.letters([waterfall, bars, diverging, pyramid, likert, mosaic, waffle,
                         slope, bump, stem, parallel, stream, gantt, timeline, bullet,
                         calendar])
fig = inklet.figure(width=180, theme="nature")
fig.add(inklet.column([
    inklet.row(panels[0:4], gap=5, align="top"),
    inklet.row(panels[4:7], gap=8, align="top"),
    inklet.row(panels[7:11], gap=5, align="top"),
    inklet.row(panels[11:13], gap=8, align="top"),
    inklet.row(panels[13:15], gap=8, align="top"),
    panels[15],
], gap=7))
fig.save("examples/categorical_plot_types.svg")
fig.save("examples/categorical_plot_types.pdf")
with open("examples/categorical_plot_types.png", "wb") as out:
    out.write(fig.to_png(dpi=300))
print(inklet.format_report(fig.lint()))
