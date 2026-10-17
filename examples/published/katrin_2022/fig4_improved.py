"""KATRIN Collaboration (2022), "Direct neutrino-mass measurement with
sub-electronvolt sensitivity", Nature Physics 18, 160-166, Figure 4 (improved).

The same best-fit m_nu^2 values and total uncertainties as fig4.py, from
1991 to 2021. The original's problem: the early experiments' error bars run to
hundreds of eV^2, so the KATRIN results are a sliver at zero.

Here the figure is two panels stacked on one column. The top panel shows all
fourteen results on the full range, with every error bar drawn in full. The
bottom panel shows the same rows at a magnified scale; the band that joins
them marks the magnified window. Nothing is clipped or dropped: a row appears
in the bottom panel only if its whole error bar lies inside the window, and
the top panel shows all rows.
"""
from pathlib import Path

import inklet as i

from _data import load_experiments

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

GREY, KATRIN, INK = "#8c8c8c", "#0072b2", "#1a1a1a"
FULL_X = (-240, 70)
ZOOM_X = (-10, 10)                      # the magnified window, in eV^2

rows = load_experiments()               # oldest first; the top row is Los Alamos
n = len(rows)
row_y = {k: n - k for k in range(n)}    # top row y = 14
zoom_keys = [k for k in range(n)
             if ZOOM_X[0] <= rows[k][2] and rows[k][3] <= ZOOM_X[1]]
zoom_y = {k: len(zoom_keys) - idx for idx, k in enumerate(zoom_keys)}


def is_katrin(name):
    return name.startswith("KATRIN")


def colour(name):
    return KATRIN if is_katrin(name) else GREY


def draw(p, keys, y_of, *, cap=0.2, dot=2.0):
    for k in keys:
        name, best, lo, hi = rows[k]
        y, c = y_of[k], colour(name)
        p.line([(lo, y), (hi, y)], stroke=c, stroke_width=0.4)
        for end in (lo, hi):
            p.line([(end, y - cap), (end, y + cap)], stroke=c, stroke_width=0.4)
        p.scatter([(best, y)], color=c, size=dot, stroke="none")


def value_label(name, best, lo, hi):
    """'0.11 ± 0.33' when symmetric; otherwise the best fit with both offsets."""
    if abs((hi - best) - (best - lo)) < 1e-9:
        return f"{best:.2f} ± {hi - best:.2f}"
    return f"{best:.1f} (−{best - lo:.1f}, +{hi - best:.1f})".replace("-", "−")


# -- top: all fourteen results, full range -----------------------------------
top = i.plot_spec(60, 62, x=FULL_X, y=(0.5, n + 1.0), clip=True)
top.rect(FULL_X[0], 0.5, 0, n + 1.0, fill="#efefef", stroke="none")   # m^2 < 0
top.rect(ZOOM_X[0], 0.5, ZOOM_X[1], n + 1.0, fill="#dcebf7", stroke="none")
top.text(-120, n + 0.55, "unphysical, m_{ν}^{2} < 0", anchor="c", size=i.pt(6), text_fill="#5b5b5b")
top.vline(0, stroke=INK, stroke_width=0.35, label="m_{ν}^{2} = 0", label_side="w", label_offset=1.0)
draw(top, range(n), row_y)
top.axis("bottom", ticks=[-200, -100, 0])
top.axis("left", ticks=[row_y[k] for k in range(n)],
         format=lambda v: rows[n - int(round(v))][0])
top.title("All results, full range")

# -- bottom: the magnified window, same rows ---------------------------------
bottom = i.plot_spec(60, 40, x=ZOOM_X, y=(0.5, len(zoom_keys) + 0.5), clip=True)
bottom.rect(ZOOM_X[0], 0.5, 0, len(zoom_keys) + 0.5, fill="#efefef", stroke="none")
bottom.vline(0, stroke=INK, stroke_width=0.35)
draw(bottom, zoom_keys, zoom_y)
for k in zoom_keys:
    name, best, lo, hi = rows[k]
    if is_katrin(name):
        bottom.text(hi + 0.6, zoom_y[k], value_label(name, best, lo, hi), anchor="w",
                    size=i.pt(6), text_fill=KATRIN)
bottom.axis("bottom", ticks=[-10, -5, 0, 5, 10], label="Best-fit m_{ν}^{2} (eV^{2})")
bottom.axis("left", ticks=[zoom_y[k] for k in zoom_keys],
            format=lambda v: rows[zoom_keys[len(zoom_keys) - int(round(v))]][0])
bottom.title("Magnified: the blue band above, −10 to +10 eV^{2}")

doc = i.preset("scientific.nature", format="single-column").document(
    columns=1, row_gap=3, share_plot_margins=True)
doc.add("full-range", top, row=0)
doc.add("magnified", bottom, row=1)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "katrin_2022_fig4_improved.svg", OUT / "katrin_2022_fig4_improved.pdf")
figure.save(OUT / "katrin_2022_fig4_improved.png", dpi=200)
print(figure.report())
