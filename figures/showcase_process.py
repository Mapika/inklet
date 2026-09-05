"""A process figure: a forked trunk, a rework loop, ports, and markup labels.

Round 2 gave `inklet.links` four shapes beyond a line from A to B. This puts the
ones a process flow actually needs on one 89mm column: `link(a, [b, c])` for a
stream that splits once and reaches two places, `loop=` for a step that feeds
itself, `offset=` for the pair of arrows that go out and come back between the
same two boxes, and `port=`/`target_port=` so those two leave and arrive at
different points on the faces they share. Every label is set with `inklet.text`
markup -- bold, an accent span, a superscript -- so the type carries emphasis
without anyone reaching for a style override.

Nothing here is placed by coordinate: the column is a `vstack`, the split is an
`hstack`, the probe is `beside` the column, and the links are routed afterwards
over whatever the layout settled on.

    .venv/bin/python figures/showcase_process.py
"""

from __future__ import annotations

import inklet

TH = inklet.use_theme("nature")

thaw = inklet.box("Thaw vial\n1 mL")
seed = inklet.box("Seed train")
reactor = inklet.box("Fed-batch\nbioreactor")
clarify = inklet.box("Depth\nfiltration")
capture = inklet.box("Protein A\ncapture")
polish = inklet.box("Anion\npolish")
release = inklet.box("Release\nassays")
probe = inklet.box("Inline\nRaman")

column = inklet.vstack(
    [thaw, seed, reactor, clarify,
     inklet.hstack([capture, polish], gap=TH.gap("m")),
     release],
    gap=TH.gap("l"),
)
# The probe hangs off the column rather than sitting in it: it watches the
# reactor, it is not a step of the process, and `beside` says exactly that.
board = inklet.beside(column, probe, inklet.Vec2(1, 0), gap=TH.gap("xl"))

caption = inklet.text(
    "**Figure 1.** Upstream and downstream unit operations for a "
    "//fed-batch// campaign. The Raman probe reads the reactor continuously "
    "and returns a feed set-point; the depth filtrate is split once and both "
    "chromatography steps pool into release testing.",
    size=TH.font_size_small, align="justify", width=89 - 2 * 4,
    text_fill=TH.muted,
)

fig = inklet.figure(width="89mm", theme=TH, margin=4)
fig.add(board, caption)

fig.link(thaw, seed, label="vial")
# A step that feeds itself. The side is named rather than left to "auto"
# because the probe has claimed the east of this column.
fig.link(seed, seed, loop="w", label="**3x**")
fig.link(seed, reactor, label="10^{6} mL^{-1}")

# Out and back between one pair of shapes: `offset` bows each route off the
# straight line, and the ports slide the ends apart along the faces they use.
fig.link(reactor, probe, port=-2.5, target_port=-2.5, offset=-2.2,
         label="{accent|sample}", label_side="center", label_offset=0.8)
fig.link(probe, reactor, port=2.5, target_port=2.5, offset=-2.2,
         label="feed rate", label_side="center", label_offset=0.8)

fig.link(reactor, clarify, label="harvest", label_side="start")
# One stem out of the filter, forking once to both chromatography steps.
fig.link(clarify, [capture, polish], stem=2.5, label="eluate",
         label_side="start")
fig.link(capture, release, label="//pool//")
fig.link(polish, release, label="//pool//")

if __name__ == "__main__":
    print(fig.report())
    fig.save("figures/out/showcase_process.svg")
    print("figures/out/showcase_process.svg  %.1f x %.1f mm"
          % (fig.page_rect(fig.build()[0].bbox).width,
             fig.page_rect(fig.build()[0].bbox).height))
