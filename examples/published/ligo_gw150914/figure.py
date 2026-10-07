"""LIGO GW150914, Abbott et al. (2016), PRL 116:061102, Figure 1 (strain rows).

The gravitational-wave event GW150914 seen by LIGO Hanford (H1, left) and
Livingston (L1, right): band-passed strain, the numerical-relativity waveform
projected onto each detector, and the residual after subtracting it. Data are
the GWOSC files published for Figure 1 (see SOURCE.md); times are seconds after
2015-09-14 09:50:45 UTC.
"""
from pathlib import Path

import numpy as np

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

H1, L1, H1_SHIFTED = "#c1121f", "#1d4e9e", "#f2a07b"
SHIFT = 0.0069          # s: H1 saw the signal 6.9 ms after L1 (paper, Fig. 1)
XLIM, XTICKS = (0.25, 0.46), [0.30, 0.35, 0.40, 0.45]
MM_PER_UNIT = 11.5      # one strain unit is the same height in every row


def load(name):
    return np.loadtxt(HERE / "data" / f"fig1-{name}.txt")   # time, strain * 1e21


def panel(ylim, yticks, *, bottom=False, ylabel=None, title=None):
    p = i.plot_spec(80, MM_PER_UNIT * (ylim[1] - ylim[0]), x=XLIM, y=ylim, clip=True)
    p.grid(x_options=dict(ticks=XTICKS), y_options=dict(ticks=yticks))
    p.axis("bottom", ticks=XTICKS, labels=bottom, label="Time (s)" if bottom else None)
    p.axis("left", ticks=yticks, label=ylabel)
    if title:
        p.title(title)
    return p


def trace(p, data, color, name, width=0.3):
    p.line(data, stroke=color, stroke_width=width, name=name)


ROWS = [((-1.55, 1.45), [-1.0, -0.5, 0.0, 0.5, 1.0]),
        ((-1.55, 1.45), [-1.0, -0.5, 0.0, 0.5, 1.0]),
        ((-1.0, 0.6), [-0.5, 0.0, 0.5])]

doc = i.preset("scientific.modern", format="double-column").document(
    columns=2, gap=4, row_gap=2, share_plot_margins=True)
for col, (det, color, site) in enumerate([("H", H1, "Hanford, Washington (H1)"),
                                          ("L", L1, "Livingston, Louisiana (L1)")]):
    left = col == 0
    observed = panel(*ROWS[0], title=site)
    keys = [f"{det}1 observed"]          # L1 is drawn over H1 but leads the key
    if det == "L":
        h = load("observed-H")
        trace(observed, np.c_[h[:, 0] - SHIFT, -h[:, 1]], H1_SHIFTED,
              "H1 observed (shifted, inverted)")
        keys.append("H1 observed (shifted, inverted)")
    trace(observed, load(f"observed-{det}"), color, f"{det}1 observed")
    observed.legend(corner="sw", names=keys)

    nr = panel(*ROWS[1], ylabel="Strain (10^{-21})" if left else None)
    trace(nr, load(f"waveform-{det}"), color, "Numerical relativity", width=0.25)
    nr.legend(corner="sw")

    residual = panel(*ROWS[2], bottom=True)
    trace(residual, load(f"residual-{det}"), color, "Residual")
    residual.legend(corner="sw")

    for row, p in enumerate([observed, nr, residual]):
        doc.add(f"{det}{row}", p, row=row, column=col)

figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "ligo_gw150914.svg", OUT / "ligo_gw150914.pdf")
figure.save(OUT / "ligo_gw150914.png", dpi=200)
print(figure.report())
