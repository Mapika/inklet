"""Marek, Tervo-Clemmens et al. (2022), Nature 603:654-660, Figure 1 (faithful).

Reproducible brain-wide association studies require thousands of individuals.
Panels a, b (effect-size histograms), e, f (sampling variability of the largest
association) and g, h (two n = 25 subsamples against the full sample) from the
ABCD Study data in Source Data Fig. 1. Panels c and d (brain surfaces) are not
drawn: their inputs are not in the source data's atlas. See NOTES.md.
"""
from pathlib import Path

import numpy as np

import inklet as i

from _data import (BINS_RSFC, BINS_THICKNESS, effects, fit_line, resamples, scatter,
                   subsample)

HERE = Path(__file__).resolve().parent


def tick_label(value):
    """Correlation tick: zero reads "0", other values unsigned, minus as U+2212."""
    if abs(value) < 1e-9:
        return "0"
    return f"{value:.1f}".replace("-", "\u2212")
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

# Colours sampled from the published PNG's legend swatches and lines.
GREEN = ["#c7e9c0", "#74c476", "#238b45"]     # vertex / ROI / network (cognition)
PURPLE = ["#dadaeb", "#9e9ac8", "#6a51a3"]    # vertex / ROI / network (psychopathology)
LINE_GREEN, LINE_PURPLE = "#74c476", "#9e9ac8"
DARK_GREEN, DARK_PURPLE = "#006d2c", "#54278f"
LIGHT_GREEN, LIGHT_PURPLE = "#c7e9c0", "#dadaeb"
BAND_GREEN, BAND_PURPLE = "#c7e9c0", "#cbc9e2"
CI99, CI95 = "#646464", "#afafaf"
INK = "#000000"

BIN_EDGES = np.round(np.arange(-0.2, 0.2 + 1e-9, 0.01), 4)   # 0.01 wide, from -0.2

HIST_W, HIST_H = 31, 25
SAMP_W, SAMP_H = 31, 26
SCAT_W, SCAT_H = 26, 21


def histogram_plot(frame, columns, colors, names, title, ylabel=None, xlabel=None):
    """Per-series normalised histograms, bins of 0.01 r, drawn opaque in order."""
    p = i.plot_spec(HIST_W, HIST_H, x=(-0.2, 0.2), y=(0, 2.3), clip=True)
    centres = (BIN_EDGES[:-1] + BIN_EDGES[1:]) / 2
    for col, color, name in zip(columns, colors, names):
        values = frame[col].dropna().to_numpy(float)
        counts, _ = np.histogram(values, bins=BIN_EDGES)
        heights = counts / counts.max()              # each series to its own tallest bin
        steps = []
        for k in range(len(centres)):
            steps.append((BIN_EDGES[k], heights[k]))
            steps.append((BIN_EDGES[k + 1], heights[k]))
        p.fill(steps, baseline=0.0, fill=color, fill_opacity=1.0, stroke="none", name=name)
    p.axes(x=xlabel, y=ylabel,
           x_options=dict(ticks=[-0.2, -0.1, 0.0, 0.1, 0.2], format="{:g}"),
           y_options=dict(ticks=[0, 0.5, 1.0], labels=False))
    p.legend(corner="ne", names=names)
    p.title(title)
    return p


def sampling_plot(frame, bins, line_color, band_color, title, ylabel=None, xlabel=None,
                  legend=False):
    """Mean across 1,000 resamples, min-max band, 95% and 99% percentile limits."""
    x = np.array(bins, float)
    cols = [c for c in frame.columns]
    col_values = [frame[c].to_numpy(float) for c in cols]
    mean = np.array([v.mean() for v in col_values])
    lo, hi = np.array([v.min() for v in col_values]), np.array([v.max() for v in col_values])
    p99 = np.array([np.percentile(v, [0.5, 99.5]) for v in col_values])
    p95 = np.array([np.percentile(v, [2.5, 97.5]) for v in col_values])
    p = i.plot_spec(SAMP_W, SAMP_H, x=i.log((bins[0], bins[-1])), y=(-1.0, 1.0), clip=True)
    p.band(x, lo, hi, color=band_color, name="min to max")
    p.line(list(zip(x, mean)), stroke=line_color, stroke_width=0.3, name="mean")
    p.line(list(zip(x, p99[:, 1])), stroke=CI99, stroke_width=0.3, dash="dashed", name="99% CI")
    p.line(list(zip(x, p99[:, 0])), stroke=CI99, stroke_width=0.3, dash="dashed", name="99% CI")
    p.line(list(zip(x, p95[:, 1])), stroke=CI95, stroke_width=0.3, dash="dashed", name="95% CI")
    p.line(list(zip(x, p95[:, 0])), stroke=CI95, stroke_width=0.3, dash="dashed", name="95% CI")
    p.axes(x=xlabel, y=ylabel,
           x_options=dict(ticks=[25, 200, 2000], format="{:,.0f}"),
           y_options=dict(ticks=[-1, -0.5, 0, 0.5, 1], format=tick_label))
    if legend:
        p.legend(corner="ne", names=["99% CI", "95% CI"])
    p.title(title)
    return p


def signed_r(r):
    return f"r = {r:+.2f}".replace("-", "\u2212")


NOT_DRAWN = []   # (panel, subsample, markers not drawn, markers in subsample), for NOTES


def scatter_plot(name, ylim, yticks, ylabel, xlabel, dark, light):
    frame, meta = scatter(name)
    p = i.plot_spec(SCAT_W, SCAT_H, x=(3.0 if name.startswith("g") else 0.15,
                                        3.55 if name.startswith("g") else 0.57),
                    y=ylim, clip=True)
    lo_x, hi_x = (3.0, 3.55) if name.startswith("g") else (0.15, 0.57)
    # A marker centred within 0.8 mm of an edge would be cut, so it is not drawn.
    # Fits and the legend r values use all 25 points.
    margin_x = 0.8 * (hi_x - lo_x) / SCAT_W
    margin_y = 0.8 * (ylim[1] - ylim[0]) / SCAT_H
    keys = []
    for key, marker, fill, stroke in [("dark", "circle", dark, dark), ("light", "diamond", light, "#405b4b")]:
        xc, yc = meta[key]
        x, y = subsample(frame, xc, yc)
        inside = ((x >= lo_x + margin_x) & (x <= hi_x - margin_x)
                  & (y >= ylim[0] + margin_y) & (y <= ylim[1] - margin_y))
        NOT_DRAWN.append((name, key, int((~inside).sum()), len(x)))
        p.scatter(list(zip(x[inside], y[inside])), marker=marker, color=fill, stroke=stroke,
                  stroke_width=0.15, size=1.5, name="n = 25" if key == "dark" else "n = 25\u200b")
        slope, intercept, r = fit_line(x, y)
        ends = [(lo_x, slope * lo_x + intercept), (hi_x, slope * hi_x + intercept)]
        p.line(ends, stroke=fill if key == "dark" else "#99ad8f", stroke_width=0.3,
               name=signed_r(r))
        keys += ["n = 25" if key == "dark" else "n = 25\u200b", signed_r(r)]
    fx, fy = subsample(frame, *meta["full"])
    slope, intercept, r_full = fit_line(fx, fy)
    p.line([(lo_x, slope * lo_x + intercept), (hi_x, slope * hi_x + intercept)],
           stroke=INK, stroke_width=0.3, dash="dashed", name=signed_r(r_full))
    p.legend(side="top", columns=2, names=[keys[0], keys[2], keys[1], keys[3], signed_r(r_full)])
    p.axes(x=xlabel, y=ylabel,
           x_options=dict(ticks=[3, 3.5] if name.startswith("g") else [0.15, 0.5],
                          format="{:g}" if name.startswith("g") else "{:.2f}"),
           y_options=dict(ticks=yticks))
    return p, r_full


def build():
    th = effects("a")
    rsfc = effects("b")

    # ---- panels a, b: effect-size histograms
    a_cog = histogram_plot(th, ["Vertex_cognition", "ROI_cognition", "Network_cognition"],
                           GREEN, ["Vertex", "ROI", "Network"], "Cognitive ability",
                           ylabel="Normalized count", xlabel="Correlation (//r//)")
    a_psy = histogram_plot(th, ["Vertex_psy", "ROI_psy", "Network_psy"],
                           PURPLE, ["Vertex", "ROI", "Network"], "Psychopathology")
    b_cog = histogram_plot(rsfc, ["Edge_cog", "Component_cog", "Network_cog"],
                           GREEN, ["Edge", "Component", "Network"], "Cognitive ability",
                           xlabel="Correlation (//r//)")
    b_psy = histogram_plot(rsfc, ["Edge_psy", "Component_psy", "Network_psy"],
                           PURPLE, ["Edge", "Component", "Network"], "Psychopathology")

    # ---- panels e, f: sampling variability
    e_cog = sampling_plot(resamples("e_cognition"), BINS_THICKNESS, LINE_GREEN, BAND_GREEN,
                          "Cognitive ability", ylabel="Correlation (//r//)", xlabel="Sample size", legend=True)
    e_psy = sampling_plot(resamples("e_psychopathology"), BINS_THICKNESS, LINE_PURPLE,
                          BAND_PURPLE, "Psychopathology")
    f_cog = sampling_plot(resamples("f_cognition"), BINS_RSFC, LINE_GREEN, BAND_GREEN,
                          "Cognitive ability", xlabel="Sample size")
    f_psy = sampling_plot(resamples("f_psychopathology"), BINS_RSFC, LINE_PURPLE, BAND_PURPLE,
                          "Psychopathology", xlabel="Sample size")

    # ---- panels g, h: two n = 25 subsamples
    g_cog, _ = scatter_plot("g_cognition", (70, 150), [70, 150], "Cognitive ability",
                            "DMN thickness (mm)", DARK_GREEN, LIGHT_GREEN)
    g_psy, _ = scatter_plot("g_psychopathology", (20, 75), [20, 70], "Psychopathology",
                            "DMN thickness (mm)", DARK_PURPLE, LIGHT_PURPLE)
    h_cog, _ = scatter_plot("h_cognition", (70, 150), [70, 150], "Cognitive ability",
                            "DMN RSFC", DARK_GREEN, LIGHT_GREEN)
    # h (right, psychopathology) is left out: its source sheet has no data rows.

    return dict(a=(a_cog, a_psy), b=(b_cog, b_psy), e=(e_cog, e_psy), f=(f_cog, f_psy),
                g=(g_cog, g_psy), h=(h_cog,))


def compose(panels):
    doc = i.preset("scientific.nature", format="double-column").document(
        columns=(0.07, 1.0, 1.0), row_gap=3, gap=3)
    doc.add("hdr-str", i.text("Structure: Cortical thickness", size=i.pt(7)), row=0, column=1)
    doc.add("hdr-fun", i.text("Function: RSFC", size=i.pt(7)), row=0, column=2)

    def pair(name, plots):
        # Always two slots, so a single plot keeps the size of a pair member and
        # the other slot stays empty (h-right is not in the source data).
        sub = i.subfigure(columns=2, gap=5, row_gap=2, share_plot_margins=True)
        for k, plot in enumerate(plots):
            sub.add(f"{name}{k}", plot, row=0, column=k)
        return sub

    def row(letter_start, cells):
        sub = i.subfigure(columns=2, gap=6, row_gap=2, share_plot_margins=True)
        for k, (name, plots) in enumerate(cells):
            sub.add(name, pair(name, plots), row=0, column=k)
        sub.letters(start=letter_start)
        return sub

    doc.add("lab-effect", i.text("Effect size", angle=90, size=i.pt(7)), row=1, column=0)
    doc.add("row-ab", row("a", [("a", panels["a"]), ("b", panels["b"])]), row=1, column=1, colspan=2)
    doc.add("lab-sampling", i.text("Sampling variability across studies", angle=90, size=i.pt(7)),
            row=2, column=0)
    doc.add("row-ef", row("e", [("e", panels["e"]), ("f", panels["f"])]), row=2, column=1, colspan=2)
    doc.add("row-gh", row("g", [("g", panels["g"]), ("h", panels["h"])]), row=3, column=1, colspan=2)
    return doc


def main():
    panels = build()
    for name, key, dropped, total in NOT_DRAWN:
        print(f"not drawn: {name} {key} subsample: {dropped} of {total} markers")
    figure = compose(panels).compile()
    OUT.mkdir(parents=True, exist_ok=True)
    figure.save(OUT / "marek_bwas_2022_fig1.svg", OUT / "marek_bwas_2022_fig1.pdf")
    figure.save(OUT / "marek_bwas_2022_fig1.png", dpi=200)
    print(figure.report())


if __name__ == "__main__":
    main()
