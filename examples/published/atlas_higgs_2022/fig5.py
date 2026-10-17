"""ATLAS Collaboration (2022), "A detailed map of Higgs boson interactions by the
ATLAS experiment ten years after the discovery", Nature 607, 52-59, Figure 5.

Reduced coupling strengths: kappa_F m_F / vev for fermions and sqrt(kappa_V) m_V / vev
for vector bosons against particle mass (top), and the coupling modifiers kappa
themselves (bottom). Circles: kappa_c = kappa_t. Grey crosses: kappa_c free. Data are
the HEPData tables for this figure (record ins2104706, see SOURCE.md).
"""
from pathlib import Path

import inklet as i
from inklet.draw.path import polyline
from inklet.draw.shapes import marker

import _data

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

RED, GREY, BLACK = "#f81c1c", "#999999", "#000000"      # SM line, free-kappa_c, ink
COLOUR = {"μ": "#dd5212", "τ": "#dd2d0a", "b": "#cf7331", "t": "#cf7331",
          "W": "#006600", "Z": "#006600", "c": GREY}     # sampled from the original
XLIM = (0.046, 300.0)
TOP_YLIM, BOTTOM_YLIM = (4.7e-5, 3.1), (0.73, 1.47)
TOP_TICKS = [1e-4, 1e-3, 1e-2, 1e-1, 1.0]
ARROW_X = 0.62                                              # c mass, GeV
CAP = 0.7                                                   # whisker end caps, mm

kc_tied = {r["name"]: r for r in _data.load(_data.WITHOUT_KC)}
kc_free = {r["name"]: r for r in _data.load(_data.WITH_KC)}


def points(rows, field):
    """(mass, value) pairs, and the (down, up) error distances, for a field."""
    xy = [(r["mass"], r[field][0]) for r in rows]
    err = [(r[field][1], r[field][2]) for r in rows]
    return xy, err


# -- top panel: kappa m / vev, log-log ----------------------------------------
top = i.plot_spec(77, 57.5, x=i.log(XLIM), y=i.log(TOP_YLIM))
top.line([(XLIM[0], XLIM[0] / _data.VEV), (XLIM[1], XLIM[1] / _data.VEV)],
         stroke=RED, stroke_width=0.35)

free_rows = list(kc_free.values())
xy, err = points(free_rows, "top")
# c's lower bound is 0, which a log axis cannot show: its whisker runs to the panel floor.
err = [(d, u) if r["name"] != "c" else (r["top"][0] - TOP_YLIM[0], r["top"][2])
       for r, (d, u) in zip(free_rows, err)]
top.errorbars(xy, yerr=err, cap=CAP, stroke=GREY, stroke_width=0.25)
top.scatter(xy, marker="plus", size=2.0, color=GREY, stroke_width=0.35)

tied_rows = list(kc_tied.values())
for r in tied_rows:
    xy, err = points([r], "top")
    top.errorbars(xy, yerr=err, cap=CAP, stroke=COLOUR[r["name"]], stroke_width=0.25)
    top.scatter(xy, size=1.5, color=COLOUR[r["name"]])

# Each particle is named beside its own point (no key): (anchor, offset in mm, right and down).
LABEL = {"μ": (kc_tied["μ"], "se", (-0.8, -0.9)), "τ": (kc_tied["τ"], "nw", (1.4, 1.4)),
         "b": (kc_tied["b"], "sw", (0.4, -0.9)), "t": (kc_tied["t"], "nw", (1.8, 1.2)),
         "Z": (kc_tied["Z"], "sw", (0.6, -0.9)), "W": (kc_tied["W"], "ne", (-0.5, 1.2)),
         "c": (kc_free["c"], "e", (-0.8, -1.2))}
for name, (row, anchor, offset) in LABEL.items():
    top.text(row["mass"], row["top"][0], f"//{name}//", anchor=anchor, offset=offset)

top.legend(corner="nw", entries=[
    ("κ_{c} = κ_{t}", marker("circle", 1.5, fill=BLACK, stroke="none")),
    ("κ_{c} is a free parameter", marker("plus", 2.0, stroke=GREY)),
    ("SM prediction", polyline([(0, 0), (3.5, 0)], stroke=RED, stroke_width=0.35)),
])
top.axis("bottom", ticks=[0.1, 1, 10, 100], labels=False, minor=True)
top.axis("left", ticks=TOP_TICKS, minor=True, label="κ_{F}·m_{F}/vev  or  √κ_{V}·m_{V}/vev")

# Particle table: the original's shaded key, drawn in millimetres inside an inset.
MM = 0.0869                                 # mm per pixel of the 1024-px original
TILE_W, TILE_H = 63 * MM, 53 * MM
COL = [0.0, 67 * MM, 134 * MM]              # lepton / force-carrier columns
QCOL = [220 * MM, 287 * MM, 354 * MM]       # quark columns
ROW_TOP = [(628 - 407) * MM, (628 - 466) * MM]
FORCE_TOP = (628 - 574) * MM
HIGGS_X = 314 * MM
GRID_W, GRID_H = 418 * MM, (628 - 375) * MM + 1.0
TILES = [  # (x, top, label, fill)
    (COL[0], ROW_TOP[0], "//ν//_{e}", None), (COL[1], ROW_TOP[0], "//ν//_{μ}", None),
    (COL[2], ROW_TOP[0], "//ν//_{τ}", None), (COL[0], ROW_TOP[1], "//e//", None),
    (COL[1], ROW_TOP[1], "//μ//", "#dd5212"), (COL[2], ROW_TOP[1], "//τ//", "#dd2d0a"),
    (QCOL[0], ROW_TOP[0], "//u//", None), (QCOL[1], ROW_TOP[0], "//c//", GREY),
    (QCOL[2], ROW_TOP[0], "//t//", "#cf7331"), (QCOL[0], ROW_TOP[1], "//d//", None),
    (QCOL[1], ROW_TOP[1], "//s//", None), (QCOL[2], ROW_TOP[1], "//b//", "#cf7331"),
    (COL[0], FORCE_TOP, "//g//", None), (COL[1], FORCE_TOP, "//γ//", None),
    (COL[2], FORCE_TOP, "//Z//", "#006600"), (COL[2] + 67 * MM, FORCE_TOP, "//W//", "#006600"),
    (HIGGS_X, FORCE_TOP, "//H//", None),
]
grid = i.plot_spec(GRID_W, GRID_H, x=(0, GRID_W), y=(0, GRID_H))
for x, top_y, label, fill in TILES:
    y0 = top_y - TILE_H
    grid.rect(x, y0, x + TILE_W, top_y, fill=fill or "#ffffff", stroke="#333333",
              stroke_width=0.11)
    grid.text(x + TILE_W / 2, y0 + TILE_H / 2, label, anchor="center",
              color="#ffffff" if fill in ("#006600", "#dd2d0a") else "#000000")
for x, y, label in [(8.55, 21.9, "Leptons"), (27.7, 21.9, "Quarks"),
                    (11.4, 7.1, "Force carriers"), (30.1, 7.1, "Higgs boson")]:
    grid.text(x, y, label, anchor="center")
top.inset(grid, corner="se", width=None, pad=1.0, plate=False)

# -- bottom panel: kappa, linear -----------------------------------------------
bottom = i.plot_spec(77, 26.5, x=i.log(XLIM), y=BOTTOM_YLIM)
bottom.hline(1.0, stroke=RED, stroke_width=0.35)

# kappa_c = 0.031 lies below this panel, so it is not plotted; an arrow points to it.
in_range = [r for r in free_rows if r["name"] != "c"]
xy, _ = points(in_range, "kappa")
err = [(r["kappa"][1], r["kappa"][2]) for r in in_range]
bottom.errorbars(xy, yerr=err, cap=CAP, stroke=GREY, stroke_width=0.25)
bottom.scatter(xy, marker="plus", size=2.0, color=GREY, stroke_width=0.35)
bottom.arrow((ARROW_X, BOTTOM_YLIM[1]), (ARROW_X, BOTTOM_YLIM[0] + 0.01),
             stroke=GREY, stroke_width=0.35)

for r in tied_rows:
    xy, _ = points([r], "kappa")
    err = [(r["kappa"][1], r["kappa"][2])]
    bottom.errorbars(xy, yerr=err, cap=CAP, stroke=COLOUR[r["name"]], stroke_width=0.25)
    bottom.scatter(xy, size=1.5, color=COLOUR[r["name"]])

bottom.axis("bottom", ticks=[0.1, 1, 10, 100], label="Particle mass (GeV)")
bottom.axis("left", ticks=[0.8, 1.0, 1.2, 1.4], label="κ_{F} or κ_{V}")

doc = i.preset("scientific.nature", format="single-column").document(
    columns=1, row_gap=1.5, share_plot_margins=True)
doc.add("top", top, row=0)
doc.add("bottom", bottom, row=1)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "atlas_higgs_2022_fig5.svg", OUT / "atlas_higgs_2022_fig5.pdf")
figure.save(OUT / "atlas_higgs_2022_fig5.png", dpi=200)
print(figure.report())
