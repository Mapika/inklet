"""KATRIN Collaboration (2022), "Direct neutrino-mass measurement with
sub-electronvolt sensitivity", Nature Physics 18, 160-166, Figure 3.

Distribution of the fitted neutrino mass squared (m_nu^2) and effective
endpoint (E_0) from the Monte Carlo propagation: a 2D histogram drawn as a
heatmap, with marginal histograms along the top and right edges, the 1 sigma
and 2 sigma contours, and the best-fit cross. Data are the Nature Source Data
for Fig. 3 (see SOURCE.md); the contours are derived from the histogram.
"""
from pathlib import Path

import inklet as i

from _data import hdr_contours, hdr_levels, load_histogram

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

BLUE, INK = "#1e90ff", "#111111"
RAMP = ["#ffffff", "#9fd3ff", "#2e8bf0", "#0c3f8f", "#06214f"]
ENDPOINT_TICKS = [18573.60, 18573.65, 18573.70, 18573.75, 18573.80]

xs, ys, grid = load_histogram()
dx, dy = xs[1] - xs[0], ys[1] - ys[0]
XLIM = (xs[0] - dx / 2, xs[-1] + dx / 2)      # the bin edges
YLIM = (ys[0] - dy / 2, ys[-1] + dy / 2)
levels = hdr_levels(grid)

marginal_m2 = grid.sum(axis=0) * dy           # per eV^2
marginal_e0 = grid.sum(axis=1) * dx           # per eV
# Best fit, as stated in the paper's text (Results, "Best-fit result and upper limit"):
#   "we find m_nu^2 = 0.26 eV^2 ... based on the Monte Carlo propagation technique"
#   "The ring-averaged fitted effective endpoint is E0 = (18,573.69 +- 0.03) eV."
best_m2, best_e0 = 0.26, 18573.69

# -- main panel: heatmap, contours, best fit ----------------------------------
scale = i.linear((0, float(grid.max())))
main = i.plot_spec(60, 50, x=XLIM, y=YLIM, clip=True)
# Bins with no entries are left empty (white), not painted as a low count.
cells = [[v if v > 0 else None for v in row] for row in grid.tolist()]
main.matrix(cells, ramp=i.ramp(RAMP), scale=scale, x=xs, y=ys, missing="#ffffff")
for mass, color, name in [(0.683, INK, "1 sigma contour (68.3%)"),
                          (0.954, BLUE, "2 sigma contour (95.4%)")]:
    for ring in hdr_contours(xs, ys, grid, levels[mass]):
        main.line(ring, closed=True, stroke=color, stroke_width=0.35, name=name)
main.scatter([(best_m2, best_e0)], marker="cross", size=2.2, color="white",
             stroke="none", name="best fit")
main.axes(x="m_{ν}^{2} (eV^{2})", y="E_{0} (eV)",
          x_options=dict(ticks=[-1, 0, 1]),
          y_options=dict(ticks=ENDPOINT_TICKS, format=lambda v: f"{v:,.2f}"))
main.colorbar(corner="se", length=15, title="Normalized\nentries (1/eV^{3})",
              ticks=[0, 20, 40])
main.outline()                                # the original has a full frame

# -- marginal histograms, with the same data ranges ---------------------------
top = i.plot_spec(60, 13, x=XLIM, y=(0, float(marginal_m2.max()) * 1.04))
top.bars(list(xs), list(marginal_m2), width=dx, color=BLUE, stroke="#ffffff", stroke_width=0.1)
right = i.plot_spec(14, 50, x=(0, float(marginal_e0.max()) * 1.04), y=YLIM)
right.bars(list(ys), list(marginal_e0), width=dy, orient="h", color=BLUE,
           stroke="#ffffff", stroke_width=0.1)

doc = i.preset("scientific.nature", format="single-column").document(
    columns=[1, 0.25], gap=1, row_gap=1, share_plot_margins=True)
doc.add("marginal-m2", top, row=0, column=0)
doc.add("heatmap", main, row=1, column=0)
doc.add("marginal-e0", right, row=1, column=1)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "katrin_2022_fig3.svg", OUT / "katrin_2022_fig3.pdf")
figure.save(OUT / "katrin_2022_fig3.png", dpi=200)
print(figure.report())
