"""Yengo et al. (2022), Nature 610:704-712, Figure 1.

Joint effect size (s.d. of height per minor allele) against minor allele
frequency for the 12,111 quasi-independent genome-wide significant SNPs of the
cross-ancestry height meta-analysis, coloured by P-value class, with the
theoretical effect sizes detectable at P < 5e-8 with 90% power for sample sizes
of 0.5 and 5 million. Data: Nature Source Data (see SOURCE.md).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

# Five P-value classes, most significant first (the key order of the original).
CLASSES = [
    ("[0,5e-100]", "P < 5 × 10^{-100}", "#EE82EE"),
    ("(5e-100,5e-50]", "5 × 10^{-50} > P > 5 × 10^{-100}", "#2E8B57"),
    ("(5e-50,5e-20]", "5 × 10^{-20} > P > 5 × 10^{-50}", "#1E90FF"),
    ("(5e-20,5e-10]", "5 × 10^{-10} > P > 5 × 10^{-20}", "#DAA520"),
    ("(5e-10,5e-08]", "5 × 10^{-8} > P > 5 × 10^{-10}", "#CDC673"),
]
GREY, CORAL = "#BEBEBE", "#FF7256"

# Power curves: (Z_ALPHA + Z_POWER) = sqrt(lambda) for two-sided alpha = 5e-8, power 90%.
Z_ALPHA, Z_POWER = 5.4513, 1.2816
SAMPLE_SIZES = [(5e5, "90% power (n = 0.5 million)", GREY),
                (5e6, "90% power (n = 5 million)", CORAL)]


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
p = i.plot_spec(72, 60, x=(0, 50), y=(-0.3, 0.3), clip=True)
p.hline(0, stroke=GREY, stroke_width=0.11)

for key, label, color in CLASSES:
    sub = snps[snps.cls == key]
    n = len(sub)
    p.scatter(list(zip(sub.maf_pct, sub.beta)), size=1.1, color=color,
              stroke="none", name=f"{label} ({n:,} SNPs)")

# Power curves, both signs, from the MAF where the curve enters the plot.
f = np.geomspace(0.001, 0.5, 400)
for n, label, color in SAMPLE_SIZES:
    b = beta_for_power(f, n)
    for sign in (1, -1):
        p.line(list(zip(100 * f, sign * b)), stroke=color, stroke_width=0.25,
               name=label)

p.axes(x="MAF (%) in cross-ancestry meta-analysis",
       y="Joint effect sizes (s.d.) of minor alleles\nin cross-ancestry meta-analysis",
       x_options=dict(ticks=[1, 5, 10, 20, 30, 40, 50]),
       y_options=dict(ticks=[-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3],
                      format=y_label))
p.legend(corner="ne", names=[f"{lab} ({(snps.cls == k).sum():,} SNPs)"
                             for k, lab, _ in CLASSES])

p.legend(corner="se", names=[label for _, label, _ in SAMPLE_SIZES])

doc.add("fig1", p)
figure = doc.compile()

OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "yengo_height_2022_fig1.svg", OUT / "yengo_height_2022_fig1.pdf")
figure.save(OUT / "yengo_height_2022_fig1.png", dpi=200)
print(figure.report())
