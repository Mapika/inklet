"""KATRIN Collaboration (2022), "Direct neutrino-mass measurement with
sub-electronvolt sensitivity", Nature Physics 18, 160-166, Figure 4.

Comparison of the best-fit neutrino mass squared, m_nu^2, with its total
uncertainty for the historical tritium experiments (1991-2021) and the two
KATRIN results. The original plots all fourteen rows on one axis from -240 to
+70 eV^2, with a magnified inset of the modern results. Data are the Nature
Source Data for Fig. 4 (see SOURCE.md).
"""
from pathlib import Path

import inklet as i

from _data import load_experiments

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

GROUP_COLOR = {"Los Alamos": "#127d7d", "Tokyo": "#ef8a17", "Zürich": "#7d1d8f",
               "Mainz": "#2e9a2e", "Beijing": "#6b6b6b", "Livermore": "#d9a300",
               "Troitsk": "#d62b2b", "KATRIN": "#1f7ae0"}
FULL_X = (-240, 70)
ZOOM_X = (-10, 3)                          # the inset window, in m^2 (eV^2)

rows = load_experiments()                  # oldest first: top row is Los Alamos
n = len(rows)
row_y = {k: n - k for k in range(n)}       # y = 14 at the top, 1 at the bottom
# The inset shows the rows whose whole error bar lies inside the window.
zoom_rows = [k for k in range(n) if ZOOM_X[0] <= rows[k][2] and rows[k][3] <= ZOOM_X[1]]
ZOOM_Y = (min(row_y[k] for k in zoom_rows) - 0.5, max(row_y[k] for k in zoom_rows) + 0.5)


def colour(name):
    return GROUP_COLOR[name.split(" (")[0]]


def draw_rows(p, keys, *, cap=0.22, dot=2.0):
    """Each experiment: a dot at the best fit and a bar from lower to upper bound."""
    for k in keys:
        name, best, lo, hi = rows[k]
        y, c = row_y[k], colour(name)
        p.line([(lo, y), (hi, y)], stroke=c, stroke_width=0.35, name=name)
        for end in (lo, hi):
            p.line([(end, y - cap), (end, y + cap)], stroke=c, stroke_width=0.35)
        p.scatter([(best, y)], color=c, size=dot, stroke="none")


def labels_for(keys):
    return [rows[k][0] for k in keys], [row_y[k] for k in keys]


# -- inset: the modern results at magnified scale ----------------------------
sub = i.plot_spec(30, 36, x=ZOOM_X, y=ZOOM_Y, clip=True)   # built at its printed size
sub.vline(0, stroke="#9a9a9a", stroke_width=0.5)
draw_rows(sub, zoom_rows, cap=0.18, dot=1.6)
sub.axis("bottom", ticks=[-8, -6, -4, -2, 0, 2], label="Zoom: m_{ν}^{2} (eV^{2})")
sub.axis("left", ticks=[])                     # rows are named on the main axis
sub.outline()


# -- main panel: all fourteen results ----------------------------------------
main = i.plot_spec(60, 86, x=FULL_X, y=(0.5, n + 0.5), clip=True)
main.vline(0, stroke="#9a9a9a", stroke_width=0.5)
draw_rows(main, range(n))
names, ticks = labels_for(range(n))
main.axes(x="Best-fit m_{ν}^{2} (eV^{2})",
          x_options=dict(ticks=[-200, -100, 0]),
          y_options=dict(ticks=ticks, format=lambda v: names[n - int(round(v))]))
main.rect(ZOOM_X[0], ZOOM_Y[0], ZOOM_X[1], ZOOM_Y[1], stroke="#555555", stroke_width=0.2,
          fill="none")
main.inset(sub, corner="sw", width=None, zoom=(ZOOM_X[0], ZOOM_X[1], ZOOM_Y[0], ZOOM_Y[1]))
main.outline()

doc = i.preset("scientific.nature", format="single-column").document()
doc.add("results", main)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "katrin_2022_fig4.svg", OUT / "katrin_2022_fig4.pdf")
figure.save(OUT / "katrin_2022_fig4.png", dpi=200)
print(figure.report())
