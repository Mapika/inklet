"""A broken axis, and the linter that makes it survivable.

Three plates of a knockout screen come back in the tens and one comes back in
the hundreds. On a linear axis the three that carry the argument are three
stubs at the bottom; on a log axis a difference of *counts* is drawn as a
difference of orders. The third answer is to cut the empty middle out of the
scale, mark the cut on the spine and on the bar that crosses it, and say in the
caption what the reader has been shown -- which is what `inklet.broken` and
`inklet.lint`'s `BREAK_DISTORTS` are for, together.

Left: the honest linear version, for comparison. Right: the break. The report
this script prints is the point of the example -- the figure on the right is
legible and the linter says, in so many words, by how much it is lying.

    python examples/broken_axis.py
"""

import inklet

inklet.use_theme("nature")

STRAINS = ["wt", "ΔcheA", "ΔcheY", "ΔfliC"]
COLONIES = [12, 31, 44, 385]

# The empty middle. Nothing between 45 and 330 was measured, and nothing in inklet
# will decide that for you: the pair is written down here or the axis is not
# broken at all.
BREAK = (45, 330)

W, H = 29.0, 32.0

# --- left: everything on one scale -------------------------------------------

flat = inklet.panel(W, H, x=STRAINS, y=(0, 400))
flat.grid(x=False)
flat.bars(STRAINS, COLONIES)
flat.axes(y="colonies")
left = inklet.vstack([inklet.title("a"), flat.build()], gap=1.5, align="left")

# --- right: the middle cut out -----------------------------------------------

cut = inklet.panel(W, H, x=STRAINS, y=inklet.broken((0, 400), breaks=[BREAK]))
cut.grid(x=False)
cut.bars(STRAINS, COLONIES)
# The journal's convention: the gap is marked on the axis *and* on every bar
# that runs through it, because a bar drawn straight across the gap is the one
# shape in the figure whose length stands for nothing.
cut.break_marks()
cut.axes(y="colonies")
right = inklet.vstack([inklet.title("b"), cut.build()], gap=1.5, align="left")

fig = inklet.figure(width="89mm")
fig.add(inklet.hstack([left, right], gap=6, align="top"))

# Two findings, both `info`, both about panel (b): one bar crosses the break,
# and the tallest bar reads about three times the shortest where the data says
# thirty. Neither is a defect to fix -- they are the sentence the caption owes.
print(fig.report())
fig.save("examples/broken_axis.svg")
