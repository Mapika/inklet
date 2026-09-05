"""An explainer: a drilled solid, dimension lines, a callout, a set caption.

The parts here are `inklet.three` geometry rather than a drawing of geometry --
`Mesh.drill` cuts a real hole, so the bore has a rim the silhouette pass can
find and an inner wall the hidden-line pass can hide, and `solids.tube` gives
the ferrule its own bore at its own segment count. Everything written on top is
placed from anchors: `anchor3d` puts a name on a 3D point, `anchor_point` reads
it back in millimetres, and `inklet.dimension` and `inklet.annotate` take it from
there. No coordinate in this file is a page coordinate.

The caption is one `inklet.text` block with markup in it -- a bold run, an italic
run and a subscript -- so the emphasis is part of the string rather than three
diagrams stacked by hand.

    .venv/bin/python figures/showcase_part.py
"""

from __future__ import annotations

import inklet
from inklet.three import Mat4, Vec3, anchor3d, build, solids

TH = inklet.use_theme("nature")

BORE = 0.085           # radius of each through-hole, in mesh units
PORTS = (-0.30, 0.30)  # their x positions; the plate is 1.0 long

plate = build("box", size_x=1.0, size_y=0.62, size_z=0.10)
for side, x in zip(("inlet", "outlet"), PORTS):
    plate = plate.drill("z", radius=BORE, at=(x, 0.0, 0.0), group=side)

# A ferrule pressed into the outlet, standing proud of the face. `tube` rather
# than a drilled cylinder: the bore gets its own segment count, so the hole
# stays as round as the outside at this size.
ferrule = solids.tube(radius=0.15, bore=BORE, height=0.30).transformed(
    Mat4.translation(Vec3(PORTS[1], 0.0, 0.16)))

rig = inklet.scene(
    [("plate", plate), ("ferrule", ferrule, {"color": TH.color(1)})],
    width=62, view="three-quarter", style="shaded", shading="flat",
)

# Three named points on the object, in the mesh's own coordinates, so the
# writing follows the part when the camera moves.
EDGE = -0.31   # the front face; the bottom front edge is the one facing us
anchor3d(rig, "front-left", (-0.5, EDGE, -0.05))
anchor3d(rig, "front-right", (0.5, EDGE, -0.05))
for side, x in zip(("inlet", "outlet"), PORTS):
    anchor3d(rig, side, (x, EDGE, -0.05))

# Both dimensions lie along that one edge, the way a machinist's drawing
# stacks them: the pitch nearest the part, the overall length outside it.
pitch = inklet.dimension(rig.anchor_point("inlet"), rig.anchor_point("outlet"),
                      "28.8", offset=4.0, size=TH.font_size_small)
span = inklet.dimension(rig.anchor_point("front-left"),
                     rig.anchor_point("front-right"),
                     "48.0", offset=10.0, size=TH.font_size_small)

drawing = inklet.drawn([rig, span, pitch])

# The callout hangs off the ferrule itself, so the leader stops on its
# silhouette rather than on the corner of a box around it.
called = inklet.annotate(drawing.find("ferrule"), "PEEK ferrule\n1.6 mm o.d.",
                      side="ne", clear=3.0, within=drawing,
                      size=TH.font_size_small)

caption = inklet.text(
    "**Figure 3.** Cathode manifold, //as machined//. Both ports are through-"
    "drilled at ø1.7 mm and reamed; the outlet carries a pressed PEEK ferrule. "
    "Dimensions in mm. Wetted volume 41 µL at 20 °C, H_{2}O.",
    size=TH.font_size_small, align="justify", width=89 - 2 * 4,
    text_fill=TH.muted,
)

fig = inklet.figure(width="89mm", theme=TH, margin=4)
fig.add(inklet.vstack([called, caption], gap=TH.gap("l"), align="center"))

if __name__ == "__main__":
    print(fig.report())
    fig.save("figures/out/showcase_part.svg")
