"""Cell fate as a Sankey: one labelled cohort, four intermediates, five fates.

The case `inklet` had no answer for: a figure where the *width* of a line is the
measurement. Every number here is a cell count out of a 1000-cell cohort, and
the whole point of the drawing is that a reader can compare two bands by eye
without a legend. Nothing is placed by hand -- the script says which
population feeds which and how many cells went, and `inklet.sankey` decides the
column order, the bar heights, the stacking at every node face and the
millimetres.

No RNG and no seed: the counts below are literals, chosen to sum exactly, so
two runs of this script differ in nothing at all. The one adversarial part is
deliberate -- `FLOWS` is written in the order a biologist would dictate it,
which is a bad column order, and the barycentre pass has to find a better one.
"""
import inklet

inklet.use_theme("nature")

#: Cells out of 1000, by (source population, fate, count). Written in dictation
#: order on purpose: see the module docstring.
FLOWS = [
    ("cohort", "ipc", 420),
    ("cohort", "org", 250),
    ("cohort", "glial", 210),
    ("cohort", "direct", 120),

    ("ipc", "deep", 150),
    ("ipc", "upper", 240),
    ("ipc", "dead", 30),

    ("org", "upper", 170),
    ("org", "deep", 60),
    ("org", "astro", 20),

    ("glial", "astro", 130),
    ("glial", "oligo", 70),
    ("glial", "dead", 10),

    ("direct", "deep", 95),
    ("direct", "upper", 15),
    ("direct", "dead", 10),
]

NAMES = {
    "cohort": "labelled\nprogenitors",
    "ipc": "intermediate\nprogenitor",
    "org": "outer radial\nglia",
    "glial": "glial\nprecursor",
    "direct": "direct\nneurogenic",
    "deep": "deep-layer\nneuron",
    "upper": "upper-layer\nneuron",
    "astro": "astrocyte",
    "oligo": "oligodendrocyte",
    "dead": "apoptotic",
}

TH = inklet.current_theme()
# Colour by lineage rather than by node index: the four intermediates carry the
# figure, so they get the palette, the pool they came from is neutral, and the
# fates are shaded towards paper so the bands arriving read louder than the
# bars they arrive at.
COLORS = {
    "cohort": TH.muted,
    "ipc": TH.color(5), "org": TH.color(2),
    "glial": TH.color(3), "direct": TH.color(1),
    "deep": inklet.mix(TH.color(5), TH.paper, 0.25),
    "upper": inklet.mix(TH.color(2), TH.paper, 0.25),
    "astro": inklet.mix(TH.color(3), TH.paper, 0.25),
    "oligo": inklet.mix(TH.color(6), TH.paper, 0.25),
    "dead": inklet.mix(TH.ink, TH.paper, 0.55),
}

#: Page furniture the drawing has to leave room for: the figure's own margins,
#: the gap to the scale key, and the key itself. The key is shaped twice --
#: once at a nominal height, only to be measured -- because its width is what
#: the Sankey's `length` has to come off, and its height is not knowable until
#: the Sankey has chosen a scale.
MARGIN, GAP = 2.0, 4.0
run = inklet.COLUMN_DOUBLE - 2 * MARGIN - GAP - inklet.bracket(
    (0, 0), (0, 10), text="100 cells", side="e").width

# `tint="target"` because the first column is one undifferentiated pool: by
# source, all four of its bands would be the same grey and the split -- which
# is the finding -- would be invisible until the second column.
fate = inklet.sankey(FLOWS, labels=NAMES, color=COLORS, tint="target",
                  length=run, breadth=64, node_width=2.4,
                  name="fate")

# The scale the reader needs to turn a band's thickness back into cells. It is
# drawn from `fate.unit`, the millimetres-per-cell the layout settled on, so it
# cannot drift out of step with the figure.
key = inklet.bracket((0, 0), (0, 100 * fate.unit), text="100 cells", side="e")

fig = inklet.figure(width=inklet.COLUMN_DOUBLE, theme="nature", margin=MARGIN)
fig.add(inklet.vstack([
    inklet.title("Cortical progenitor fate at P7, 1000 labelled cells"),
    inklet.hstack([fate.diagram, key], gap=GAP),
], gap=3))

print("%d nodes, %d flows, %d ribbon crossings, %.4f mm per cell"
      % (len(fate.nodes), len(fate.flows), fate.crossings, fate.unit))
# The control, at the same size: what the figure would look like if the layout
# drew the columns in the order this script dictates them.
print("dictation order would cross %d"
      % inklet.sankey(FLOWS, labels=NAMES, length=run, breadth=64, node_width=2.4,
                   order="given").crossings)
print(fig.report())
fig.save("stress/flow.svg")
