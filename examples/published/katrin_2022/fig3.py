"""KATRIN Collaboration (2022), "Direct neutrino-mass measurement with
sub-electronvolt sensitivity", Nature Physics 18, 160-166, Figure 3.

Distribution of the fitted neutrino mass squared (m_nu^2) and effective
endpoint (E_0) from the Monte Carlo propagation: a 2D histogram drawn as a
heatmap, with marginal histograms along the top and right edges, the 1 sigma
and 2 sigma contours, and the best-fit cross. Data are the Nature Source Data
for Fig. 3 (see SOURCE.md); the contours are the highest-density regions of
the histogram, drawn by Panel.contour.
"""
from pathlib import Path

import inklet as i

from _data import bin_edges, load_histogram

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

BLUE, INK = "#1e90ff", "#111111"
RAMP = ["#ffffff", "#9fd3ff", "#2e8bf0", "#0c3f8f", "#06214f"]
ENDPOINT_TICKS = [18573.60, 18573.65, 18573.70, 18573.75, 18573.80]

xs, ys, grid = load_histogram()
dx, dy = xs[1] - xs[0], ys[1] - ys[0]
m2_edges, e0_edges = bin_edges(xs), bin_edges(ys)
XLIM = (m2_edges[0], m2_edges[-1])
YLIM = (e0_edges[0], e0_edges[-1])

marginal_m2 = grid.sum(axis=0) * dy           # per eV^2
marginal_e0 = grid.sum(axis=1) * dx           # per eV
# Best fit, as stated in the paper's text (Results, "Best-fit result and upper limit"):
#   "we find m_nu^2 = 0.26 eV^2 ... based on the Monte Carlo propagation technique"
#   "The ring-averaged fitted effective endpoint is E0 = (18,573.69 +- 0.03) eV."
best_m2, best_e0 = 0.26, 18573.69

# -- main panel: heatmap, contours, best fit ----------------------------------
scale = i.linear((0, float(grid.max())))
main = i.plot_spec(56, 46, x=XLIM, y=YLIM, clip=True)
# Bins with no entries are left empty (white), not painted as a low count.
cells = [[v if v > 0 else None for v in row] for row in grid.tolist()]
main.matrix(cells, ramp=i.ramp(RAMP), scale=scale, x=xs.tolist(), y=ys.tolist(),
            missing="#ffffff")
# hdr= lists the shares largest first, so the colours are given the same way:
# 95.4% (blue) then 68.3% (black).
main.contour(xs.tolist(), ys.tolist(), grid.tolist(), hdr=(0.683, 0.954),
             color=[BLUE, INK], stroke_width=0.35)
main.scatter([(best_m2, best_e0)], marker="cross", size=2.2, color="white",
             stroke="none", stroke_width=0.35, name="best fit")
main.axes(x="//m//_{ν}^{2} (eV^{2})", y="//E//_{0} (eV)",
          x_options=dict(ticks=[-1, 0, 1]),
          y_options=dict(ticks=ENDPOINT_TICKS, format=lambda v: f"{v:,.2f}"))
main.colorbar(corner="se", length=13, title="Normalized\nentries (1/eV^{3})",
              ticks=[0, 20, 40])

# -- marginal histograms, from the same bin counts ----------------------------
top = i.plot_spec(56, 13, x=XLIM, y=(0, float(marginal_m2.max()) * 1.04))
top.hist(marginal_m2.tolist(), bins=m2_edges.tolist(), prebinned=True, color=BLUE,
         stroke="#ffffff", stroke_width=0.1)
right = i.plot_spec(17, 46, x=(0, float(marginal_e0.max()) * 1.04), y=YLIM)
right.hist(marginal_e0.tolist(), bins=e0_edges.tolist(), prebinned=True, orient="h",
           color=BLUE, stroke="#ffffff", stroke_width=0.1)

preset = i.preset("scientific.nature", format="single-column", axes="box")
doc = preset.document(columns=[71, 17], margin=0.5, gap=0.5, row_gap=0.5,
                      share_plot_margins=True)
doc.add("marginal-m2", top, row=0, column=0)
doc.add("heatmap", main, row=1, column=0)
doc.add("marginal-e0", right, row=1, column=1)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "katrin_2022_fig3.svg", OUT / "katrin_2022_fig3.pdf")
figure.save(OUT / "katrin_2022_fig3.png", dpi=200)
print(figure.report())
