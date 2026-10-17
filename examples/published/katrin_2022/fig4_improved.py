"""KATRIN Collaboration (2022), "Direct neutrino-mass measurement with
sub-electronvolt sensitivity", Nature Physics 18, 160-166, Figure 4 (improved).

The same best-fit m_nu^2 values and total uncertainties as fig4.py, from
1991 to 2021. The original's problem: the early experiments' error bars run to
hundreds of eV^2, so the KATRIN results are a sliver at zero.

Here the figure is two panels stacked on one column. The top panel (a) shows
all fourteen results on the full range, with every error bar drawn in full.
The bottom panel (b) shows the same rows at a magnified scale. The blue band in
(a) is the window of (b), and the two share that blue, so the link is visual.
Nothing is clipped or dropped: a row appears in (b) only if its whole error bar
lies inside the window, and (a) shows all rows.
"""
from pathlib import Path

import inklet as i

from _data import load_experiments

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

GREY, KATRIN, INK = "#8c8c8c", "#0072b2", "#1a1a1a"
KATRIN_TEXT = "#005a8c"                 # KATRIN's blue, darkened to 4.5:1 on the window
UNPHYSICAL, WINDOW = "#efefef", "#dcebf7"      # m^2 < 0 shading; the magnified window
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


# -- (a) all fourteen results, full range ------------------------------------
top = i.plot_spec(66, 62, x=FULL_X, y=(0.5, n + 1.0), clip=True)
top.rect(FULL_X[0], 0.5, 0, n + 1.0, fill=UNPHYSICAL, stroke="none")      # m^2 < 0
top.rect(ZOOM_X[0], 0.5, ZOOM_X[1], n + 0.5, fill=WINDOW, stroke="none")  # the window
top.vline(0, stroke=INK, stroke_width=0.35, label="//m//_{ν}^{2} = 0", label_side="w",
          label_offset=1.0)
draw(top, range(n), row_y)
top.axes(x="Best-fit //m//_{ν}^{2} (eV^{2})",
         x_options=dict(ticks=[-200, -100, 0]),
         y_options=dict(ticks=[row_y[k] for k in range(n)],
                        format=lambda v: rows[n - int(round(v))][0]))

# -- (b) the magnified window, same rows -------------------------------------
bottom = i.plot_spec(66, 40, x=ZOOM_X, y=(0.5, len(zoom_keys) + 0.5), clip=True)
bottom.background(fill=WINDOW)
bottom.vline(0, stroke=INK, stroke_width=0.35)
draw(bottom, zoom_keys, zoom_y)
for k in zoom_keys:
    name, best, lo, hi = rows[k]
    if is_katrin(name):
        bottom.text(hi + 0.6, zoom_y[k], value_label(name, best, lo, hi), anchor="w",
                    size=i.pt(6), text_fill=KATRIN_TEXT)
bottom.axes(x="Best-fit //m//_{ν}^{2} (eV^{2})",
            x_options=dict(ticks=[-10, -5, 0, 5, 10]),
            y_options=dict(ticks=[zoom_y[k] for k in zoom_keys],
                           format=lambda v: rows[zoom_keys[len(zoom_keys) - int(round(v))]][0]))

preset = i.preset("scientific.nature", format="single-column", axes="box")
doc = preset.document(columns=1, margin=0.5, row_gap=3, share_plot_margins=True)
doc.add("full-range", top, row=0)
doc.add("magnified", bottom, row=1)
doc.letters({"full-range": "a", "magnified": "b"})
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "katrin_2022_fig4_improved.svg", OUT / "katrin_2022_fig4_improved.pdf")
figure.save(OUT / "katrin_2022_fig4_improved.png", dpi=200)
print(figure.report())
