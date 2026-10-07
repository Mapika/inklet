# Notes: Himes et al. 2014, PLoS ONE, Figure 1A (volcano plot)

Output: `gallery/published/rnaseq_volcano.{png,svg,pdf}`, 89 mm (single
column) × 88 mm. `figure.report()`: `inklet lint: clean, 0 diagnostics`.
`figure.py` is 55 lines. The SVG is 2.9 MB because all 21,842 points stay vector;
pass `raster=True` to `volcano()` for a small file.

## What matches the original

- The same results table the paper plotted: Cuffdiff 2.0.2 gene-level DEX vs
  untreated output deposited with the paper on GEO (GSE52778), every gene
  with a finite fold change (21,842 of 23,273).
- The same axes and orientation: y = −log10 P (raw Cuffdiff p), x =
  Cuffdiff's `log2(fold_change)`, which is log2(untreated / DEX); the paper
  titles it "−Log2[Fold Change]" and so does this figure. As in the paper,
  DEX-induced genes (FKBP5, KLF15, DUSP1, …) sit on the left. Same ranges:
  x −15…15 with ticks every 5, y 0…~16 with ticks every 5.
- The same two-class colouring: blue for the 316 genes with q < 0.05
  (identical set and count to the caption), red for every other gene, which
  gives the paper's characteristic red "V" under the blue wings and the long
  red tails of low-expression genes out to ±15.
- Overall shape point for point: the asymmetric wings (217 of 316 significant
  genes on the induced side), the isolated points at (−7.6, 8.9), (2.5, 13.9),
  (−5.0, 12.2) — ZBTB16, KCTD12, STEAP4.

## What differs, and why

- **Gene labels added.** The original Figure 1A has none. Named here are the
  five genes the paper validates by qRT-PCR in Figure 1B (DUSP1, FKBP5,
  KLF15, TSC22D3, PER1) and its headline gene CRISPLD2, named by
  `volcano(..., highlight=[...])` in italics, with the six points ringed so
  the four that share the top row can be told apart (the ring positions come
  from `inklet.plot.volcano_points`, the volcano's own placement).
- **q = 0.05 line added**: a dashed rule at p = 0.00115, the largest raw p
  among the 316 significant genes. The colours come from `volcano(q=...)`,
  which classes by q while plotting raw p; since the BH q-value is monotone
  in p, the significant set is exactly p ≤ 0.00115 and the rule marks the
  colour boundary. `figure.py` asserts the count of 316. The original has no threshold lines and explains
  the colours only in the caption; this figure carries a key instead.
- **p = 0 genes.** Ten genes (DUSP1, FKBP5, KLF15, C7, …) have p reported as
  0. ggplot2 drew −log10(0) = Inf at the very top edge of the panel (~16.5);
  inklet's `volcano` draws them at the smallest positive p (2.2 × 10⁻¹⁶,
  y = 15.65), the same row as TSC22D3. The y range is 0–17 so they sit
  inside the plot.
- **Style.** inklet `scientific.modern` instead of ggplot2's grey panel and
  white grid; smaller points (0.7 mm); a true minus sign on negative ticks.
  The blue and red are kept close to the paper's (#2b6cb0, #d23b2f).
- **Panel B** (qRT-PCR fold changes in three cell lines) is not recreated:
  its values are not published as data.

## Verdict

Faithful recreation of Figure 1A from the authors' own deposited results:
same data, same axes and orientation, same significant set and colour
classes; additions (labels, threshold line, key) are clearly extra
annotation rather than changes to the data display.
