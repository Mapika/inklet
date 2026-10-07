"""Volcano plot of DEX vs untreated airway smooth muscle (Himes et al. 2014, Fig. 1A).

Cuffdiff 2.0.2 gene-level results from GEO GSE52778, as the paper plotted
them: every gene with a finite fold change, -log10 p against Cuffdiff's
log2(fold_change), which is log2(untreated / DEX) -- hence the paper's
"-log2 fold change" axis, on which DEX-induced genes lie to the left. The 316
genes with q < 0.05 are coloured; the genes the paper validates by qRT-PCR
(Fig. 1B) and CRISPLD2, its headline gene, are named.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import inklet as i

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "gallery" / "published"

genes = pd.read_csv(HERE / "data" / "dex_vs_untreated_gene_exp.tsv", sep="\t")
# Cuffdiff writes +/-1.79769e+308 for a gene absent from one condition.
genes = genes[genes["log2_fold_change"].abs() < 1e300].reset_index(drop=True)
fold, p, q = (genes[c].to_numpy() for c in ("log2_fold_change", "p_value", "q_value"))
assert (q < 0.05).sum() == 316                  # the paper's significant set

BLUE, RED = "#2b6cb0", "#d23b2f"     # the paper's two classes: q < 0.05 blue, rest red
HIGHLIGHT = ["CRISPLD2", "DUSP1", "FKBP5", "KLF15", "PER1", "TSC22D3"]

plot = i.plot_spec(x=(-16, 16), y=(0, 17))
# Ring the named genes, under the volcano's dots: four share the p = 0 row.
at = i.plot.volcano_points(fold, p)["points"]
plot.scatter([at[k] for k in np.flatnonzero(genes["gene"].isin(HIGHLIGHT))],
             color=BLUE, size=0.95, stroke="#111111", stroke_width=0.25)
plot.volcano(fold, p, q=q, fold_threshold=0, thresholds=False, size=0.7,
             color={"up": BLUE, "down": BLUE, "ns": RED},
             name={"up": "//q// < 0.05 (316 genes)", "ns": "//q// ≥ 0.05"},
             labels=genes["gene"].tolist(), highlight=HIGHLIGHT,
             label_options={"font_style": "italic"})
# q is monotone in p, so q = 0.05 falls at the largest p among the significant genes.
plot.hline(-np.log10(p[q < 0.05].max()), stroke="#888888", stroke_width=0.2,
           dash="dashed", label="//q// = 0.05")
plot.axes(x="−log_{2} fold change", y="−log_{10} //P//",
          x_options={"ticks": [-15, -10, -5, 0, 5, 10, 15]},
          y_options={"ticks": [0, 5, 10, 15]})
plot.legend(corner="ne")

doc = i.preset("scientific.modern", format="single-column").document()
doc.add("a", plot, min_height=80)
figure = doc.compile()
OUT.mkdir(parents=True, exist_ok=True)
figure.save(OUT / "rnaseq_volcano.png", dpi=200)
figure.save(OUT / "rnaseq_volcano.svg")
figure.save(OUT / "rnaseq_volcano.pdf")
print(figure.report())
