"""Native 3D rendering of procedural solids and CC0 meshes.

The NIH cortical surface exercises concave silhouettes and self-occluding
folds. Two views of Keenan Crane's Spot demonstrate shaded open surfaces.
See meshes/README.md for attribution and terms.

Run: python stress/three_figure.py
"""

import dataclasses
import time
from pathlib import Path

import inklet
from inklet.three import Mat4, Vec3, load

MESHES = Path(__file__).parent / "meshes"
TH = inklet.use_theme(dataclasses.replace(inklet.theme("nature"), font_family="Noto Sans"))

started = time.perf_counter()


def pole(mesh, direction, name=""):
    """The vertex furthest along a direction: a landmark, found rather than
    guessed. Anchors want points that are really on the surface, and the
    extreme vertex is the one place a hand-typed coordinate cannot drift."""
    d = Vec3(*direction)
    return max(mesh.vertices, key=lambda v: v.dot(d)).as_tuple()


def caption(letter, text, node, width=None):
    head = inklet.text(f"({letter})", size=TH.font_size_small, align="start")
    body = inklet.label(text, align="start", width=width)
    return inklet.vstack([node, inklet.hstack([head, body], gap=1.2)],
                      gap=TH.gap("s"), align="left")


# -- (a) the coordinate frame ---------------------------------------------

frame = inklet.axes(width=24, view="isometric", labels=("x", "y", "z"))

# -- (b) the parametric catalogue -----------------------------------------

CATALOGUE = [
    ("cube", dict(style="shaded", view="isometric")),
    ("sphere", dict(style="shaded", view="three-quarter")),
    ("cylinder", dict(style="lineart", view="dimetric", segments=40)),
    ("cone", dict(style="shaded", view="three-quarter")),
    ("torus", dict(style="shaded", view="three-quarter", tube=0.2)),
]
catalogue = inklet.hstack(
    [inklet.vstack([inklet.solid(kind, width=17, **opts), inklet.label(kind)], gap=1.0)
     for kind, opts in CATALOGUE],
    gap=4.0, align="bottom")

# -- (c) the cortical surface, with landmarks -----------------------------

brain = load(MESHES / "brain-lh.obj")
cortex = inklet.model(
    brain, width=86, view=(78.0, 12.0), style="lineart", crease=72,
    name="cortex",
    anchors={
        "frontal": pole(brain, (0.0, 1.0, 0.0)),
        "occipital": pole(brain, (0.0, -1.0, 0.0)),
        "vertex": pole(brain, (0.0, 0.0, 1.0)),
        "temporal": pole(brain, (0.0, 0.0, -1.0)),
    },
)

# Which side each tag goes on is the one thing here that is not automatic, and
# it is not a coordinate either: it is which column of the stack the tag is
# put in. The arrow finds the rest.
tag = lambda text: inklet.box(text, width=22, pad=1.2)
tags = {"frontal": tag("frontal pole"), "occipital": tag("occipital pole"),
        "vertex": tag("vertex"), "temporal": tag("temporal pole")}
probe = inklet.box("probe\narray", width=17)

panel_c = inklet.vstack([
    tags["vertex"],
    inklet.hstack([
        inklet.vstack([tags["occipital"], tags["temporal"]], gap=30.0),
        cortex,
        inklet.vstack([tags["frontal"], probe], gap=26.0),
    ], gap=7.0),
], gap=2.0, align="center")

# -- (d) two shaded views of Spot ---------------------------------------

# Both files are y-up, and both are turned onto inklet's z before anything else
# looks at them -- so every direction below is the one the reader sees, not
# the one the exporter happened to write.
Y_TO_Z = Mat4.rotation(Vec3(1.0, 0.0, 0.0), 90.0)

spot = load(MESHES / "spot.obj").transformed(Y_TO_Z)
cow = inklet.model(spot, width=52, view=(-40.0, 14.0), style="shaded",
                crease=55, name="spot",
                anchors={"nose": pole(spot, (0.0, 1.0, 0.0))})

animal = load(MESHES / "spot.obj").transformed(Y_TO_Z)
spot = inklet.model(animal, width=40, view=(28.0, 14.0), style="shaded",
                  crease=70, name="spot-detail",
                  anchors={"ear": pole(animal, (0.0, 0.0, 1.0))})

note_cow = inklet.box("open surface:\neyes and mouth", width=30, pad=1.2)
note_spot = inklet.box("5856 faces,\nCC0 Spot", width=26, pad=1.2)

panel_d = inklet.hstack([
    inklet.vstack([note_cow, inklet.spacer(1.0, 26.0)], gap=0.0),
    cow,
    spot,
    inklet.vstack([note_spot, inklet.spacer(1.0, 30.0)], gap=0.0),
], gap=6.0, align="center")

# -- the page -------------------------------------------------------------

fig = inklet.figure(width=inklet.COLUMN_DOUBLE, margin=4)
fig.add(inklet.vstack([
    inklet.hstack([
        caption("a", "coordinate frame", frame),
        caption("b", "parametric solids, shaded and line art", catalogue),
    ], gap=10.0, align="bottom"),
    caption("c", "cortical surface, 18000 faces. The four tags point at named "
                 "3D landmarks; the probe leader stops on the silhouette",
            panel_c, width=150),
    caption("d", "two shaded views of Spot, 5856 faces; eyes and mouth are open", panel_d, width=150),
], gap=9.0, align="left"))

# Leaders to named 3D points: exact, because an anchor is a point and not a
# shape to be clipped against.
for key in ("frontal", "occipital", "vertex", "temporal"):
    fig.link(tags[key], cortex.at(key), kind="leader")

# ...and two that clip on the outline instead, which is the whole argument for
# contributing a trace. Aimed at the node rather than at one of its anchors,
# they stop where the surface really is and not on the rectangle around it.
fig.link(probe, cortex, standoff=1.0)
fig.link(note_spot, spot, standoff=1.0)
fig.link(note_cow, cow.at("nose"), kind="leader")

fig.save("stress/three_figure.svg")
print(f"drawn in {time.perf_counter() - started:.1f} s")
# CROWDING and OVERLAP are meaningless inside a shaded model -- its facets are
# meant to abut -- and they drown everything else out. See the report.
print(fig.report(rules=["EMPTY_DIAGRAM", "FONT_SUBSTITUTED", "HAIRLINE",
                        "INCONSISTENT_STROKE", "LINK_COLLAPSED",
                        "LINK_CROSSES", "LOW_CONTRAST", "LOW_DPI",
                        "OFF_CANVAS", "ROUTE_BLOCKED", "TEXT_OVERFLOW",
                        "TINY_TEXT"]))
