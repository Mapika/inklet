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

from _data import bin_edges, load_histogram

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

INK = "#141414"              # contours: dark on the light-to-dark ramp
BOUNDARY = "#d55e00"         # m_nu^2 = 0 rule (Okabe-Ito vermillion): shows on every cell
MARGINAL = "#5b6470"
ENDPOINT_TICKS = [18573.60, 18573.65, 18573.70, 18573.75, 18573.80]

xs, ys, grid = load_histogram()
dx, dy = xs[1] - xs[0], ys[1] - ys[0]
m2_edges, e0_edges = bin_edges(xs), bin_edges(ys)
XLIM = (m2_edges[0], m2_edges[-1])
YLIM = (e0_edges[0], e0_edges[-1])
marginal_m2 = grid.sum(axis=0) * dy
marginal_e0 = grid.sum(axis=1) * dx
# Best fit, as stated in the paper's text (Results, "Best-fit result and upper limit"):
#   "we find m_nu^2 = 0.26 eV^2 ... based on the Monte Carlo propagation technique"
#   "The ring-averaged fitted effective endpoint is E0 = (18,573.69 +- 0.03) eV."
best_m2, best_e0 = 0.26, 18573.69

# -- main panel ---------------------------------------------------------------
cells = [[v if v > 0 else None for v in row] for row in grid.tolist()]
scale = i.linear((0, float(grid.max())))
main = i.plot_spec(56, 46, x=XLIM, y=YLIM, clip=True)
main.matrix(cells, ramp=i.ramp("blues"), scale=scale, x=xs.tolist(), y=ys.tolist(),
            missing="#ffffff")
main.contour(xs.tolist(), ys.tolist(), grid.tolist(), hdr=(0.683, 0.954),
             color=INK, stroke_width=0.4)

# Direct labels. Both rings are named in the empty upper-left corner, each with a
# leader to its ring: the 95.4% ring's upper edge, and the 68.3% ring's upper-left
# edge. The points are read off the rendered contours.
for label, tag, edge in [("95.4%", (-0.95, 18573.775), (-0.10, 18573.703)),
                         ("68.3%", (-1.05, 18573.735), (-0.16, 18573.690))]:
    main.line([edge, (tag[0] + 0.06, tag[1] - 0.004)], stroke=INK, stroke_width=0.21,
              name=f"{label} leader")
    main.text(tag[0], tag[1], label, anchor="w", halo=0.6, halo_color="#ffffff")

main.scatter([(best_m2, best_e0)], marker="cross", size=2.2, color="white",
             stroke="none", stroke_width=0.4, name="best fit")
main.vline(0, stroke=BOUNDARY, stroke_width=0.4, dash="dashed", front=True,
           label="//m//_{ν}^{2} = 0", label_side="e", label_offset=0.6)

main.axes(x="//m//_{ν}^{2} (eV^{2})", y="//E//_{0} (eV)",
          x_options=dict(ticks=[-1, 0, 1]),
          y_options=dict(ticks=ENDPOINT_TICKS, format=lambda v: f"{v:,.2f}"))
main.colorbar(corner="se", length=13, title="Probability\ndensity (eV^{-3})",
              ticks=[0, 20, 40])

# -- marginal histograms -------------------------------------------------------
top = i.plot_spec(56, 13, x=XLIM, y=(0, float(marginal_m2.max()) * 1.04))
top.hist(marginal_m2.tolist(), bins=m2_edges.tolist(), prebinned=True, color=MARGINAL,
         stroke="none")
right = i.plot_spec(17, 46, x=(0, float(marginal_e0.max()) * 1.04), y=YLIM)
right.hist(marginal_e0.tolist(), bins=e0_edges.tolist(), prebinned=True, orient="h",
           color=MARGINAL, stroke="none")

preset = i.preset("scientific.nature", format="single-column", axes="box")
doc = preset.document(columns=[71, 17], margin=0.5, gap=0.5, row_gap=0.5,
                      share_plot_margins=True)
doc.add("marginal-m2", top, row=0, column=0)
doc.add("heatmap", main, row=1, column=0)
doc.add("marginal-e0", right, row=1, column=1)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "katrin_2022_fig3_improved.svg", OUT / "katrin_2022_fig3_improved.pdf")
figure.save(OUT / "katrin_2022_fig3_improved.png", dpi=200)
print(figure.report())
