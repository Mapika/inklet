"""KATRIN Collaboration (2022), "Direct neutrino-mass measurement with
sub-electronvolt sensitivity", Nature Physics 18, 160-166, Figure 3 (improved).

The same 2D histogram of the fitted m_nu^2 and E_0 values, with the same
marginals, contours and best fit as fig3.py. Changes: a light-to-dark
sequential colormap (ColorBrewer Blues) in place of the single-hue ramp, so
that sparse bins sit near the white background and the core is darkest; dark
contours; a colour bar that says what the number is; contours labelled where
they are; the best fit and the physical boundary m_nu^2 = 0 labelled; and empty
bins shown as blank. Nothing is dropped: both contours, both marginals and the
full range of both axes are kept.
"""
from pathlib import Path

import inklet as i

from _data import hdr_contours, hdr_levels, load_histogram

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

INK = "#141414"              # contours: dark on the light-to-dark ramp
BOUNDARY = "#d55e00"         # m_nu^2 = 0 rule (Okabe-Ito vermillion): shows on every cell
MARGINAL = "#5b6470"
ENDPOINT_TICKS = [18573.60, 18573.65, 18573.70, 18573.75, 18573.80]

xs, ys, grid = load_histogram()
dx, dy = xs[1] - xs[0], ys[1] - ys[0]
XLIM = (xs[0] - dx / 2, xs[-1] + dx / 2)
YLIM = (ys[0] - dy / 2, ys[-1] + dy / 2)
levels = hdr_levels(grid)
marginal_m2 = grid.sum(axis=0) * dy
marginal_e0 = grid.sum(axis=1) * dx
# Best fit, as stated in the paper's text (Results, "Best-fit result and upper limit"):
#   "we find m_nu^2 = 0.26 eV^2 ... based on the Monte Carlo propagation technique"
#   "The ring-averaged fitted effective endpoint is E0 = (18,573.69 +- 0.03) eV."
best_m2, best_e0 = 0.26, 18573.69

# -- main panel ---------------------------------------------------------------
cells = [[v if v > 0 else None for v in row] for row in grid.tolist()]
scale = i.linear((0, float(grid.max())))
main = i.plot_spec(60, 50, x=XLIM, y=YLIM, clip=True)
main.matrix(cells, ramp=i.ramp("blues"), scale=scale, x=xs, y=ys, missing="#ffffff")

contours = {0.683: ("68.3%", hdr_contours(xs, ys, grid, levels[0.683])),
            0.954: ("95.4%", hdr_contours(xs, ys, grid, levels[0.954]))}
for mass, (label, rings) in contours.items():
    for ring in rings:
        main.line(ring, closed=True, stroke=INK, stroke_width=0.4,
                  name=f"{label} contour")

# Direct labels. The 95.4% ring is named at its right-hand tip, where it is
# clear. The 68.3% ring lies inside it, so its name sits in the empty upper
# left corner with a leader to the ring's upper-left edge.
rings_95 = max(contours[0.954][1], key=len)
x, y = max(rings_95, key=lambda p: p[0])
main.annotate(x, y, "95.4%", side="e", dot=False, halo=0.6, halo_color="#ffffff")

rings_68 = max(contours[0.683][1], key=len)
edge = max(rings_68, key=lambda p: (p[1] - YLIM[0]) / (YLIM[1] - YLIM[0])
           - (p[0] - XLIM[0]) / (XLIM[1] - XLIM[0]))
tag = (-1.05, 18573.735)
main.line([edge, (tag[0] + 0.06, tag[1] - 0.004)], stroke="#141414", stroke_width=0.2,
          name="68.3% leader")
main.text(tag[0], tag[1], "68.3%", anchor="w", halo=0.6, halo_color="#ffffff")

main.scatter([(best_m2, best_e0)], marker="cross", size=2.2, color="white",
             stroke="none", name="best fit")
main.vline(0, stroke=BOUNDARY, stroke_width=0.4, dash="dashed", front=True,
           label="m_{ν}^{2} = 0", label_side="e", label_offset=0.6)

main.axes(x="m_{ν}^{2} (eV^{2})", y="E_{0} (eV)",
          x_options=dict(ticks=[-1, 0, 1]),
          y_options=dict(ticks=ENDPOINT_TICKS, format=lambda v: f"{v:,.2f}"))
main.colorbar(corner="se", length=15, title="Probability\ndensity (eV^{-3})",
              ticks=[0, 20, 40])
main.outline()

# -- marginal histograms -------------------------------------------------------
top = i.plot_spec(60, 13, x=XLIM, y=(0, float(marginal_m2.max()) * 1.04))
top.bars(list(xs), list(marginal_m2), width=dx, color=MARGINAL, stroke="none")
right = i.plot_spec(14, 50, x=(0, float(marginal_e0.max()) * 1.04), y=YLIM)
right.bars(list(ys), list(marginal_e0), width=dy, orient="h", color=MARGINAL,
           stroke="none")

doc = i.preset("scientific.nature", format="single-column").document(
    columns=[1, 0.25], gap=1, row_gap=1, share_plot_margins=True)
doc.add("marginal-m2", top, row=0, column=0)
doc.add("heatmap", main, row=1, column=0)
doc.add("marginal-e0", right, row=1, column=1)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "katrin_2022_fig3_improved.svg", OUT / "katrin_2022_fig3_improved.pdf")
figure.save(OUT / "katrin_2022_fig3_improved.png", dpi=200)
print(figure.report())
