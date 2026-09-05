"""Multi-panel layout, the shape most real figures actually take."""

import inklet

inklet.use_theme("nature")

# Panel a: a task timeline built from a row of unequal boxes.
epochs = inklet.hstack(
    [inklet.box("baseline"), inklet.box("cue"), inklet.box("delay"), inklet.box("response")],
    gap=1.5,
)
panel_a = inklet.vstack([inklet.title("a"), epochs], gap=2, align="left")

# Panel b: a branching flow, laid out as a grid so the columns line up.
source = inklet.box("raw traces")
branches = inklet.hstack([inklet.box("shuffled"), inklet.box("observed")], gap=8)
sink = inklet.box("effect size")
# `letters`, not a title stacked on top: this vstack is centre-aligned so the
# branch sits under the middle of the trunk, and a title inside it centres
# too -- the "b" ends up over the middle of the diagram while a, c and d sit
# at their top-left corners. `letters` hangs the letter off the box instead,
# so the flow keeps its centring and the letter still lines up with the rest.
flow = inklet.vstack([source, branches, sink], gap=5)
panel_b = inklet.letters([flow], start="b")[0]

# Panel c: the measurement itself -- bars with the spread on them, and a
# second quantity read against a twin axis on the right.
TH = inklet.use_theme("nature")
GROUPS = ["ctrl", "cue", "delay", "resp"]
EFFECT = [0.12, 0.48, 0.61, 0.29]
SPREAD = [0.04, 0.07, 0.05, 0.06]
LATENCY = [180, 240, 310, 205]

bars = inklet.panel(52, 32, x=GROUPS, y=(0, 0.8))
bars.bars(GROUPS, EFFECT)
bars.errorbars(list(zip(GROUPS, EFFECT)), yerr=SPREAD)
bars.hline(0.5, label="criterion", stroke_dash=(0.9, 0.7))
bars.axis("bottom")
bars.axis("left", label="effect size")
latency = bars.twin_y((0, 400), label="latency / ms", color=TH.color(5))
latency.line(list(zip(GROUPS, LATENCY)), stroke=TH.color(5))
latency.scatter(list(zip(GROUPS, LATENCY)), color=TH.color(5))
panel_c = inklet.vstack([inklet.title("c"), bars.build()], gap=2, align="left")

# Panel d: the same measurement split by animal, sharing one pair of axes.
BY_ANIMAL = [
    [0.10, 0.44, 0.58, 0.26],
    [0.14, 0.51, 0.66, 0.31],
    [0.11, 0.46, 0.59, 0.28],
    [0.13, 0.49, 0.63, 0.30],
]
by_animal = []
for values in BY_ANIMAL:
    cell = inklet.panel(28, 14, x=GROUPS, y=(0, 0.8))
    cell.line(list(zip(GROUPS, values)))
    cell.scatter(list(zip(GROUPS, values)))
    by_animal.append(cell)
grid = inklet.facets(by_animal, cols=2, count=3, x_label="epoch",
                  y_label="effect size")
panel_d = inklet.vstack([inklet.title("d"), grid], gap=2, align="left")

fig = inklet.figure(width="183mm", theme="nature")
fig.add(inklet.vstack([
    inklet.hstack([panel_a, panel_b], gap=10, align="top"),
    inklet.hstack([panel_c, panel_d], gap=14, align="top"),
], gap=10, align="left"))
for target in branches.children:
    fig.link(source, target)
    fig.link(target, sink)

print(fig.report())
fig.save("examples/panels.svg")
