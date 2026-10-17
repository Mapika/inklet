# Source: Yengo et al. (2022), height GWAS, Figures 1 and 2

**Paper.** Loïc Yengo *et al.*, "A saturated map of common
genetic variants associated with human height", *Nature* **610**, 704–712
(2022). DOI: [10.1038/s41586-022-05275-y](https://doi.org/10.1038/s41586-022-05275-y).
Article: <https://www.nature.com/articles/s41586-022-05275-y>.
Figure 1: "Relationship between frequency and estimated effect sizes of minor
alleles". Figure 2: "Brisbane plot showing the genomic density of independent
genetic associations with height".

**Licence.** The article page states: "This article is licensed under a Creative
Commons Attribution 4.0 International License, which permits use, sharing,
adaptation, distribution and reproduction in any medium or format, as long as
you give appropriate credit to the original author(s) and the source, provide a
link to the Creative Commons license, and indicate if changes were made."
Attribution: Yengo, L. *et al.*, *Nature* 610, 704–712 (2022),
https://doi.org/10.1038/s41586-022-05275-y, CC BY 4.0.

**Retrieved.** 2026-10-17.

## Downloads

| URL | File in scratch | SHA-256 |
|---|---|---|
| <https://www.nature.com/articles/s41586-022-05275-y> | `article.html` (article page, captions and licence) | `0e81540e0fa4ad95e2d254b2ee4506e1714c8939bbd1146063d5ca77b322d645` |
| <https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs41586-022-05275-y/MediaObjects/41586_2022_5275_Fig1_HTML.png> | `original-fig1.png` (1060 × 779) | `5f30f34fb8771751c76497779acdf2cba67bc6808be788da9f7b303f4ad884b8` |
| <https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs41586-022-05275-y/MediaObjects/41586_2022_5275_Fig2_HTML.png> | `original-fig2.png` (2144 × 585) | `6b2da7c48c6509b80780de2c23a639969f4f263a8d75946f9cfa587dc3310901` |
| <https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-022-05275-y/MediaObjects/41586_2022_5275_MOESM5_ESM.xlsx> | `moesm5.xlsx` (Nature Source Data, Fig. 1) | `a5c94cba6c327f162d19f5a52e36d513820695363d36c1bc9ed17ce645346533` |
| <https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41586-022-05275-y/MediaObjects/41586_2022_5275_MOESM6_ESM.xlsx> | `moesm6.xlsx` (Nature Source Data, Fig. 2) | `c6aff97cc0293236f297a79abfabcf0ad7cddd13aed70c5a95b1cda1f59740be` |

The original PNG images and the article page are for viewing only; they are not
stored in the repository. The hashes are of the downloads as received.

## Files in `data/`

| File | Origin | Panel(s) it feeds |
|---|---|---|
| `data/fig1_source.csv` | `moesm5.xlsx`, sheet `Source Data Fig. 1`, all 12,111 rows, 3 columns | Figure 1 (both `fig1.py` and `fig1_improved.py`) |
| `data/fig2_source.csv` | `moesm6.xlsx`, sheet `Sheet1` (the only sheet), all 12,111 rows, 6 columns | Figure 2 (both `fig2.py` and `fig2_improved.py`) |

Both CSVs are the sheet values converted with openpyxl (normal mode), with no
values changed. The column headers are kept exactly as the workbook has them,
including the workbook's own typos ("Join Effect of Minor Allele", "P-value
Caregory", "ancesries", "Ethnicities"). Column meanings:

* `fig1_source.csv`: `Minor Allele Frequency` (a fraction, 0.00165 to 0.49991);
  `Join Effect of Minor Allele` (effect in height s.d. per minor allele,
  −0.2756 to +0.2560); `P-value Caregory` (one of five classes, written as
  interval notation: `[0,5e-100]` = P < 5 × 10⁻¹⁰⁰, `(5e-100,5e-50]`,
  `(5e-50,5e-20]`, `(5e-20,5e-10]`, `(5e-10,5e-08]` = 5 × 10⁻⁸ > P > 5 × 10⁻¹⁰).
  Class counts: 672, 1,110, 3,513, 5,192, 1,624 (sum 12,111).
* `fig2_source.csv`: `Chromosome` (1–22), `Position (hg37)`, `Signal Density
  (number of other COJO SNPs within 100 kb)` (0 to 24), and 0/1 flags
  `...African...`, `...East-Asian...`, `...Hispanic...`. Flag totals: African 3,
  East Asian 12, Hispanic 10; 24 SNPs carry at least one flag (one SNP,
  chr 18 position 220071, carries both the East Asian and the Hispanic flag).

## Processing (all in the figure scripts)

* Loading: `pandas.read_csv` on each CSV; columns renamed to short names
  (`maf`, `beta`, `cls`; `chr`, `pos`, `dens`, `afr`, `eas`, `his`). No rows are
  dropped or filtered; no values are transformed except as noted.
* Figure 1: MAF is multiplied by 100 to plot in percent. Effect sizes are
  plotted as given.
* Figure 1 power curves are **not data**. They are computed from the formula in
  the brief, with the caption's sample sizes and power: for a standardised
  trait, q² = 2f(1−f)β² and λ = N·q², and 90% power at two-sided α = 5 × 10⁻⁸
  needs √λ = z_{α/2} + z_{0.1}, so |β|(f) = (5.4513 + 1.2816) / √(2f(1−f)N),
  with N = 5 × 10⁵ and N = 5 × 10⁶, drawn at ±β over f = 0.001 to 0.5.
  The caption gives N = 0.5 and 5 million, P < 5 × 10⁻⁸ and 90% power; the
  check against the original image is in NOTES.md.
* Figure 2: each SNP is drawn as squares from 0 up to its density (density d
  gives d + 1 squares, so density 0 is one square on the baseline). For a flagged
  SNP the top square is left out and the ancestry marker stands in its place,
  because the source gives no height for the marker.
* Figure 2 x positions: `position + chromosome offset`, where offsets are the
  cumulative GRCh37 chromosome lengths (in Mb) from the list in each script.
  These are **layout constants, not data**; they are used only to space the
  chromosomes as the original does. The improved version adds a 12 Mb gap
  between chromosomes.
* Figure 2 y axis runs from 0 to 32 in both versions, so the key can sit above
  the tallest column (density 24). Faithful ticks are every 2; improved ticks
  every 5.

## Not available as data

* **Gene labels** (SPSB1, LINC00211, ACAN, …) on Figure 2 are not in the source
  data. They are omitted from both versions.
* **Marker heights.** The source gives each flagged SNP's density and flags, but
  not the height at which its ancestry marker was drawn. The faithful version
  places it on the column's top square, and the improved version does the same.
* **Power curves** are analytic and have no source data; they are the formula
  above, not digitised points.
* The **Supplementary Table 10** cited in both captions (the full list of the
  12,111 SNPs) is not part of the Source Data files used here. Only the
  per-SNP columns the two Source Data sheets contain are used.
* **Figure 1 point identities** (SNP IDs) are not provided, so no point can be
  labelled by name.
