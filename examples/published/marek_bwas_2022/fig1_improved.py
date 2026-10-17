"""Marek, Tervo-Clemmens et al. (2022), Nature 603:654-660, Figure 1 (improved).

Same data as fig1.py (Source Data Fig. 1), same message: brain-behaviour
effects are tiny, and a study of 25 people can report almost any of them.

Changes from the original, each tied to a problem in it (see NOTES.md):
- histograms are outlined steps of the share of associations, one panel per
  phenotype pair, in one sequential hue for the three levels (no overlapping
  translucent fills, no normalisation that makes a 13-value series look like
  a 59,412-value one);
- the typical effect (median |r| 0.01) and the top-1% threshold (|r| 0.06) are
  marked on the x axis of every panel;
- sampling variability is three nested bands (min-max, 99%, 95%) in neutral
  greys, instead of two similar dashed grey styles, with the mean as one line;
  the sample size where the 95% interval first narrows to +-0.06 is marked;
- the two n = 25 subsamples are drawn in a colour-blind-safe pair with shape
  redundancy and labelled at the line ends, so no key has to be decoded;
- the psychopathology RSFC scatter is not drawn (its source sheet is empty).
"""
from pathlib import Path

import numpy as np

import inklet as i

from _data import BINS_RSFC, BINS_THICKNESS, effects, fit_line, resamples, scatter, subsample

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

# Sequential blue for the three levels, finest to coarsest (ordered categories).
LEVELS = ["#9ecae1", "#3182bd", "#08306b"]
INK = "#1d1d1d"
GREY_RANGE, GREY_99, GREY_95 = "#e4e4e4", "#bdbdbd", "#7f7f7f"
TYPICAL, TOP1 = "#f1a340", "#998ec3"     # reference marks (orange, purple: neither is a level)
SAMPLE_A, SAMPLE_B = "#0072b2", "#e69f00"  # Okabe-Ito blue and orange
LABEL_INK = {"A": "#00558a", "B": "#8a5a00"}  # darker text versions for contrast >= 4.5:1
FULL = "#222222"

BIN_EDGES = np.round(np.arange(-0.2, 0.2 + 1e-9, 0.02), 4)   # 0.02 wide: steps stay readable
PANEL_W, PANEL_H = 26, 27


def _minus(text):
    return text.replace("-", "−")


def level_shares(frame, columns):
    """Share of each level's associations per bin, in percent."""
    out = []
    for col in columns:
        values = frame[col].dropna().to_numpy(float)
        counts, _ = np.histogram(values, bins=BIN_EDGES)
        out.append(100 * counts / values.size)
    return out


def effect_panel(frame, columns, names, n_labels, title, top, xlabel=None, ylabel=None):
    # One y scale for all four panels, so their heights compare directly.
    shares = level_shares(frame, columns)
    p = i.plot_spec(PANEL_W, PANEL_H, x=(-0.2, 0.2), y=(0, top), clip=True)
    centres = (BIN_EDGES[:-1] + BIN_EDGES[1:]) / 2
    for share, colour, name in zip(shares, LEVELS, names):
        steps = []
        for k in range(len(centres)):
            steps.append((BIN_EDGES[k], share[k]))
            steps.append((BIN_EDGES[k + 1], share[k]))
        p.line(steps, stroke=colour, stroke_width=0.45, name=name)
    p.vspan(-0.01, 0.01, fill="#f0f0f0", stroke="none")
    p.vline(0.06, stroke=TOP1, stroke_width=0.3, dash="dotted")
    p.vline(-0.06, stroke=TOP1, stroke_width=0.3, dash="dotted")
    p.axes(x=xlabel, y=ylabel,
           x_options=dict(ticks=[-0.2, -0.1, 0.0, 0.1, 0.2], format="{:+.1f}"),
           y_options=dict(ticks=[t for t in (0, 10, 20, 30, 40) if t <= top], format="{:g}%"))
    p.legend(side="top", columns=1, names=names)
    p.title(title)
    return p


def sampling_panel(frame, bins, title, ylabel=None, xlabel=None, key=False):
    x = np.array(bins, float)
    cols = [frame[c].to_numpy(float) for c in frame.columns]
    mean = np.array([v.mean() for v in cols])
    lo, hi = np.array([v.min() for v in cols]), np.array([v.max() for v in cols])
    q99 = np.array([np.percentile(v, [0.5, 99.5]) for v in cols])
    q95 = np.array([np.percentile(v, [2.5, 97.5]) for v in cols])
    p = i.plot_spec(PANEL_W, PANEL_H, x=i.log((bins[0], bins[-1])), y=(-0.8, 1.3), clip=True)
    p.band(x, lo, hi, color=GREY_RANGE, name="min\u2013max")
    p.band(x, q99[:, 0], q99[:, 1], color=GREY_99, name="99%")
    p.band(x, q95[:, 0], q95[:, 1], color=GREY_95, name="95%")
    p.line(list(zip(x, mean)), stroke=INK, stroke_width=0.3, name="mean")
    p.hline(0.06, stroke=TOP1, stroke_width=0.3, dash="dotted")
    p.hline(-0.06, stroke=TOP1, stroke_width=0.3, dash="dotted")
    p.vline(1000, stroke=INK, stroke_width=0.3, dash="dotted", span=(-0.8, 0.2))
    p.axes(x=xlabel, y=ylabel,
           x_options=dict(ticks=[25, 100, 1000], format="{:,.0f}", minor=True),
           y_options=dict(ticks=[-0.5, 0, 0.5], format="{:+.1f}"))
    p.title(title)
    if key:
        p.legend(corner="ne", columns=2, names=["min\u2013max", "99%", "95%", "mean"])
    return p


def example_panel(name, ylim, yticks, ylabel, xlabel, xlim, xticks, xformat, title):
    frame, meta = scatter(name)
    p = i.plot_spec(PANEL_W + 8, PANEL_H + 4, x=xlim, y=ylim, clip=True)
    for key, colour, marker, label in [("dark", SAMPLE_A, "circle", "A"),
                                        ("light", SAMPLE_B, "diamond", "B")]:
        xc, yc = meta[key]
        x, y = subsample(frame, xc, yc)
        p.scatter(list(zip(x, y)), marker=marker, color=colour, stroke="#ffffff",
                  stroke_width=0.11, size=1.8, name=f"sample {label}")
        slope, intercept, r = fit_line(x, y)
        x0, x1 = xlim
        p.line([(x0, slope * x0 + intercept), (x1, slope * x1 + intercept)], stroke=colour,
               stroke_width=0.3, name=f"fit {label}")
        xe = x1
        ye = slope * xe + intercept
        sign = f"{r:+.2f}".replace("-", "−")
        p.text(xe, ye, f"{label}: r = {sign}", anchor="sw" if slope >= 0 else "nw",
               size=i.pt(6), color=LABEL_INK[label])
    fx, fy = subsample(frame, *meta["full"])
    slope, intercept, r_full = fit_line(fx, fy)
    x0, x1 = xlim
    p.line([(x0, slope * x0 + intercept), (x1, slope * x1 + intercept)], stroke=FULL,
           stroke_width=0.3, dash="dashed", name="full sample")
    p.axes(x=xlabel, y=ylabel, x_options=dict(ticks=xticks, format=xformat),
           y_options=dict(ticks=yticks))
    p.title(title)
    return p


def build_rows():
    th, rs = effects("a"), effects("b")
    groups = [(th, ["Vertex_cognition", "ROI_cognition", "Network_cognition"]),
              (th, ["Vertex_psy", "ROI_psy", "Network_psy"]),
              (rs, ["Edge_cog", "Component_cog", "Network_cog"]),
              (rs, ["Edge_psy", "Component_psy", "Network_psy"])]
    top = 10 * np.ceil(max(s.max() for f, c in groups for s in level_shares(f, c)) * 1.08 / 10)
    row1 = [
        effect_panel(th, ["Vertex_cognition", "ROI_cognition", "Network_cognition"], ["Vertex", "ROI", "Network"],
                     [59412, 333, 13], "Thickness and cognition", top,
                     xlabel="Correlation (//r//)", ylabel="Associations (%)"),
        effect_panel(th, ["Vertex_psy", "ROI_psy", "Network_psy"], ["Vertex", "ROI", "Network"],
                     [59412, 333, 13], "Thickness and psychopathology", top, xlabel="Correlation (//r//)"),
        effect_panel(rs, ["Edge_cog", "Component_cog", "Network_cog"], ["Edge", "Component", "Network"],
                     [77421, 100, 105], "RSFC and cognition", top, xlabel="Correlation (//r//)"),
        effect_panel(rs, ["Edge_psy", "Component_psy", "Network_psy"], ["Edge", "Component", "Network"],
                     [77421, 100, 105], "RSFC and psychopathology", top, xlabel="Correlation (//r//)"),
    ]
    e_cog = resamples("e_cognition")
    e_psy = resamples("e_psychopathology")
    f_cog = resamples("f_cognition")
    f_psy = resamples("f_psychopathology")
    row2 = [
        sampling_panel(e_cog, BINS_THICKNESS, "Thickness and cognition", ylabel="Correlation (//r//)",
                       xlabel="Sample size", key=True),
        sampling_panel(e_psy, BINS_THICKNESS, "Thickness and psychopathology", xlabel="Sample size"),
        sampling_panel(f_cog, BINS_RSFC, "RSFC and cognition", xlabel="Sample size"),
        sampling_panel(f_psy, BINS_RSFC, "RSFC and psychopathology", xlabel="Sample size"),
    ]
    row3 = [
        example_panel("g_cognition", (60, 150), [70, 150], "Cognitive ability",
                      "DMN thickness (mm)", (3.0, 3.55), [3.0, 3.5], "{:g}",
                      "Thickness and cognition"),
        example_panel("g_psychopathology", (18, 78), [20, 70], "Psychopathology",
                      "DMN thickness (mm)", (3.0, 3.55), [3.0, 3.5], "{:g}",
                      "Thickness and psychopathology"),
        example_panel("h_cognition", (60, 150), [70, 150], "Cognitive ability",
                      "DMN RSFC", (0.15, 0.57), [0.15, 0.5], "{:.2f}",
                      "RSFC and cognition"),
    ]
    return row1, row2, row3


NOTE = ("Shaded: median |r| = 0.01 across associations. Dotted: |r| = 0.06, the top 1% of all associations; "
        "in e-h, the 95% interval reaches \u00b10.06 at n = 1,000. Associations per level: thickness vertex 59,412, "
        "ROI 333, network 13; RSFC edge 77,421, component 100, network 105. Samples A and B are two "
        "independent n = 25 subsamples; the dashed line is the full sample (n = 3,604 thickness, n = 3,928 RSFC). "
        "Brain maps (c, d) and the psychopathology RSFC scatter (h, right) are not drawn: not in the source data.")


def compose(row1, row2, row3):
    doc = i.preset("scientific.nature", format="double-column").document(row_gap=6, gap=3)

    def grid(cells, letters, columns):
        sub = i.subfigure(columns=columns, gap=3, row_gap=2, share_plot_margins=True)
        for k, plot in enumerate(cells):
            sub.add(f"c{k}", plot, row=0, column=k)
        sub.letters(start=letters)
        return sub

    doc.add("row1", grid(row1, "a", 4), row=0, column=0)
    doc.add("row2", grid(row2, "e", 4), row=1, column=0)
    doc.add("row3", grid(row3, "i", 3), row=2, column=0)
    doc.add("note", i.text(NOTE, size=i.pt(6), align="left", width=170), row=3, column=0)
    return doc


def main():
    figure = compose(*build_rows()).compile()
    OUT.mkdir(parents=True, exist_ok=True)
    figure.save(OUT / "marek_bwas_2022_fig1_improved.svg", OUT / "marek_bwas_2022_fig1_improved.pdf")
    figure.save(OUT / "marek_bwas_2022_fig1_improved.png", dpi=200)
    print(figure.report())


if __name__ == "__main__":
    main()
