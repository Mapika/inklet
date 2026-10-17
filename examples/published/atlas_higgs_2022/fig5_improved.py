"""ATLAS Collaboration (2022), Nature 607, 52-59, Figure 5, redrawn for legibility.

Same data and message as fig5.py: every particle's reduced coupling against its mass,
and the coupling modifiers kappa below, each with its asymmetric uncertainty. Changes
from the original are listed in NOTES.md.
"""
from pathlib import Path

import inklet as i
from inklet.draw.path import polyline
from inklet.draw.shapes import marker

import _data

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

FERMION, BOSON = "#0072b2", "#e69f00"      # Okabe-Ito blue and orange: colour-blind safe
INK, DARK, WHITE = "#000000", "#333333", "#ffffff"
FAMILY = {"μ": FERMION, "τ": FERMION, "b": FERMION, "t": FERMION, "c": FERMION,
          "W": BOSON, "Z": BOSON}
XLIM = (0.046, 300.0)
TOP_YLIM, BOTTOM_YLIM = (4.7e-5, 1.6), (0.73, 1.47)
DODGE = 0.09                                # kappa_c = kappa_t points /1.09, free points x1.09
ARROW_X = 0.62 * (1 + DODGE)                # c mass, with the other free points
CAP = 0.9                                   # whisker end caps, mm
DASH = (2.0, 1.2)                           # SM reference line
SIZE_TIED, SIZE_FREE = 1.4, 1.3             # diamonds no larger than the circles

tied = {r["name"]: r for r in _data.load(_data.WITHOUT_KC)}
free = {r["name"]: r for r in _data.load(_data.WITH_KC)}


def at(row, scenario):
    """Mass with the scenario's small horizontal offset; the values are never moved."""
    return row["mass"] / (1 + DODGE) if scenario == "tied" else row["mass"] * (1 + DODGE)


def point(panel, row, field, scenario, floor=None):
    """One point with its asymmetric whisker: filled and coloured for kappa_c = kappa_t,
    open and black for kappa_c free (so the two scenarios differ in shape, not only colour).
    A lower bound of zero cannot be drawn on a log axis, so with `floor` the whisker stops there."""
    value, down, up = row[field]
    x = at(row, scenario)
    if floor is not None and down >= value:
        down = value - floor
    if scenario == "free":
        panel.errorbars([(x, value)], yerr=[(down, up)], cap=CAP, stroke=INK, stroke_width=0.25)
        # paper-filled diamond: it hides its own whisker where they cross
        panel.scatter([(x, value)], marker="diamond", size=SIZE_FREE, color=WHITE, stroke=INK,
                      stroke_width=0.35)
    else:
        colour = FAMILY[row["name"]]
        panel.errorbars([(x, value)], yerr=[(down, up)], cap=CAP, stroke=colour, stroke_width=0.25)
        panel.scatter([(x, value)], size=SIZE_TIED, color=colour)


# -- top panel: kappa m / vev, log-log ----------------------------------------
top = i.plot_spec(150, 62, x=i.log(XLIM), y=i.log(TOP_YLIM))
top.line([(XLIM[0], XLIM[0] / _data.VEV), (XLIM[1], XLIM[1] / _data.VEV)],
         stroke=DARK, stroke_width=0.35, stroke_dash=DASH)
for r in free.values():
    point(top, r, "top", "free", floor=TOP_YLIM[0])
for r in tied.values():
    point(top, r, "top", "tied")

# Each particle is named beside its point. anchor = the label corner or edge that sits on
# the point; offsets in mm, with y positive downwards.
# Each particle is named next to its filled point, on the side that touches no other mark,
# whisker or the SM line. Fermions sit on the line's upper-left side (the line rises to the
# right); W is below-right of its pair and Z above-left. anchor = the label corner that
# sits on the point; offsets in mm, with y positive downwards.
NAMES = {"μ": ((tied["μ"], "tied"), "se", (-1.0, -1.2)),
         "τ": ((tied["τ"], "tied"), "se", (-0.6, -0.8)),
         "b": ((tied["b"], "tied"), "se", (-0.6, -0.8)),
         "t": ((tied["t"], "tied"), "se", (-0.6, -0.8)),
         "Z": ((tied["Z"], "tied"), "se", (-0.5, -0.8)),
         "W": ((tied["W"], "tied"), "ne", (-0.6, 1.2)),
         "c": ((free["c"], "free"), "e", (-1.1, -1.5))}
for name, ((row, scenario), anchor, offset) in NAMES.items():
    top.text(at(row, scenario), row["top"][0], f"//{name}//", anchor=anchor,
             offset=offset, size="7pt")

top.legend(corner="nw", entries=[
    ("Fermions", marker("circle", SIZE_TIED, fill=FERMION, stroke="none")),
    ("W, Z bosons", marker("circle", SIZE_TIED, fill=BOSON, stroke="none")),
    ("κ_{c} = κ_{t} (filled)", marker("circle", SIZE_TIED, fill=DARK, stroke="none")),
    ("κ_{c} free (open)", marker("diamond", SIZE_FREE, fill=WHITE, stroke=INK, stroke_width=0.35)),
    ("SM prediction", polyline([(0, 0), (4.0, 0)], stroke=DARK, stroke_width=0.35,
                               stroke_dash=DASH)),
], font_size="7pt")
top.axis("bottom", ticks=[0.1, 1, 10, 100], labels=False, minor=True)
top.axis("left", ticks=[1e-4, 1e-3, 1e-2, 1e-1, 1.0], minor=True,
         label="κ_{F} m_{F}/vev or √κ_{V} m_{V}/vev", label_font_size="7pt")

# -- bottom panel: kappa, linear -----------------------------------------------
bottom = i.plot_spec(150, 30, x=i.log(XLIM), y=BOTTOM_YLIM)
bottom.hline(1.0, stroke=DARK, stroke_width=0.35, stroke_dash=DASH,
             label="SM", label_side="n")
for name, r in free.items():
    if name != "c":                       # kappa_c = 0.031 is below this panel: see the arrow
        point(bottom, r, "kappa", "free")
for r in tied.values():
    point(bottom, r, "kappa", "tied")

bottom.arrow((ARROW_X, BOTTOM_YLIM[1]), (ARROW_X, BOTTOM_YLIM[0] + 0.01),
             stroke=INK, stroke_width=0.35)
bottom.text(ARROW_X, 1.27, "κ_{c} = 0.03,\noff this scale", anchor="w",
            offset=(1.0, 0.0), size="7pt")

bottom.axis("bottom", ticks=[0.1, 1, 10, 100], label="Particle mass (GeV)", minor=True)
bottom.axis("left", ticks=[0.8, 1.0, 1.2, 1.4], label="κ_{F} or κ_{V}")

doc = i.preset("scientific.nature", format="double-column").customize(font_pt=7).document(
    columns=1, row_gap=2, share_plot_margins=True)
doc.add("top", top, row=0)
doc.add("bottom", bottom, row=1)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "atlas_higgs_2022_fig5_improved.svg",
            OUT / "atlas_higgs_2022_fig5_improved.pdf")
figure.save(OUT / "atlas_higgs_2022_fig5_improved.png", dpi=200)
print(figure.report())
