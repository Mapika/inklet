"""Yengo et al. (2022), Nature 610:704-712, Figure 1: improved version.

Same data and message as fig1.py: joint effect size against minor allele
frequency for the 12,111 genome-wide significant height SNPs, by P-value class,
with the effect sizes detectable at P < 5e-8 with 90% power for n = 0.5 and
5 million. Changes: log frequency axis with even ticks, a single-hue sequential
palette for the ordered P-value classes (colour-blind safe), smaller
semi-transparent markers with the most significant class drawn last, and one
key outside the data area. See NOTES.md for the list of changes.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

# P-value classes, least significant first: a sequential single-hue ramp, darker =
# more significant, from inklet ramp(["#4292c6", "#08306b"]).sample(5). The lightest
# step is 3.4:1 against white (WCAG graphical object threshold is 3:1). Drawn in this
# order, so the most significant class sits on top.
CLASSES = [
    ("(5e-10,5e-08]", "5 × 10^{−8} > //P// > 5 × 10^{−10}", "#4292c6"),
    ("(5e-20,5e-10]", "5 × 10^{−10} > //P// > 5 × 10^{−20}", "#3678ae"),
    ("(5e-50,5e-20]", "5 × 10^{−20} > //P// > 5 × 10^{−50}", "#295f97"),
    ("(5e-100,5e-50]", "5 × 10^{−50} > //P// > 5 × 10^{−100}", "#1a4781"),
    ("[0,5e-100]", "//P// < 5 × 10^{−100}", "#08306b"),
]
# Power curves: orange (solid) and vermilion (dashed), clear of the blue ramp.
CURVE_N = [(5e5, "90% power, //n// = 0.5 million", "#E69F00", None),
           (5e6, "90% power, //n// = 5 million", "#D55E00", (1.0, 0.6))]

# Two-sided alpha = 5e-8 (z = 5.4513) and 90% power (z = 1.2816).
Z_ALPHA, Z_POWER = 5.4513, 1.2816


def beta_for_power(maf, n):
    """|beta| (s.d. per minor allele) detectable with 90% power at P < 5e-8."""
    return (Z_ALPHA + Z_POWER) / np.sqrt(2 * maf * (1 - maf) * n)


def y_label(v):
    """Zero is written "0", as in the original; minus is U+2212."""
    return "0" if abs(v) < 1e-9 else f"{v:.1f}".replace("-", "−")


# -- data ---------------------------------------------------------------------
snps = pd.read_csv(HERE / "data" / "fig1_source.csv")
snps.columns = ["maf", "beta", "cls"]
snps["maf_pct"] = 100 * snps["maf"]

# -- figure -------------------------------------------------------------------
doc = i.preset("scientific.nature", format="single-column").document()
p = i.plot_spec(72, 50, x=i.log((0.1, 50)), y=(-0.3, 0.3), clip=True)
p.hline(0, stroke="#9a9a9a", stroke_width=0.11)

names = []
for key, label, color in CLASSES:
    sub = snps[snps.cls == key]
    name = f"{label} ({len(sub):,})"
    names.append(name)
    p.scatter(list(zip(sub.maf_pct, sub.beta)), size=0.7, color=color,
              fill_opacity=0.6, stroke="none", name=name)

f = np.geomspace(0.001, 0.5, 400)
curve_names = []
for n, label, color, dash in CURVE_N:
    b = beta_for_power(f, n)
    style = {} if dash is None else {"stroke_dash": dash}
    for sign in (1, -1):
        p.line(list(zip(100 * f, sign * b)), stroke=color, stroke_width=0.3,
               name=label, **style)
    curve_names.append(label)

p.axes(x="Minor allele frequency in cross-ancestry meta-analysis (%)",
       y="Joint effect size of minor allele (s.d.)",
       x_options=dict(ticks=[0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50], format="{:g}",
                      stroke="#000000", stroke_width=0.21),
       y_options=dict(ticks=[-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3],
                      format=y_label, stroke="#000000", stroke_width=0.21))
p.legend(side="top", columns=2, col_gap=1.0, font_size=i.pt(6), names=names[::-1] + curve_names)

doc.add("fig1", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "yengo_height_2022_fig1_improved.svg",
            OUT / "yengo_height_2022_fig1_improved.pdf")
figure.save(OUT / "yengo_height_2022_fig1_improved.png", dpi=200)
print(figure.report())
