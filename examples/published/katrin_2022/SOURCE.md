# Source: KATRIN 2022, Figures 3 and 4

**Paper.** The KATRIN Collaboration, "Direct neutrino-mass measurement with
sub-electronvolt sensitivity", *Nature Physics* **18**, 160–166 (2022),
published 14 February 2022.
DOI: [10.1038/s41567-021-01463-1](https://doi.org/10.1038/s41567-021-01463-1).
Article: <https://www.nature.com/articles/s41567-021-01463-1>.
Figure 3: distribution of fitted m_ν² and E₀ values. Figure 4: comparison of
best-fit values and total uncertainties with previous neutrino-mass experiments.

**Data.** Nature Source Data, "Source Data Fig. 3" (2D histogram, file
`41567_2021_1463_MOESM7_ESM.txt`) and "Source Data Fig. 4" (file
`41567_2021_1463_MOESM8_ESM.txt`), linked from the article's Source Data section
(supplementary-material ESM files, `media.springernature.com`).

**Licence.** The article page states: "This article is licensed under a Creative
Commons Attribution 4.0 International License, which permits use, sharing,
adaptation, distribution and reproduction in any medium or format, as long as you
give appropriate credit to the original author(s) and the source, provide a link to
the Creative Commons license, and indicate if changes were made." (CC BY 4.0.)
Attribution: The KATRIN Collaboration, *Nature Physics* 18, 160–166 (2022),
https://doi.org/10.1038/s41567-021-01463-1. Changes: the figures are redrawn with
inklet; the data files are unchanged; the contours in Fig. 3 are derived (see NOTES.md).

**Retrieved.** 2026-10-17.

## Downloads

| Role | URL |
|---|---|
| Article page (captions, licence) | https://www.nature.com/articles/s41567-021-01463-1 |
| Fig. 3 image (reference only, not in the repo) | https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs41567-021-01463-1/MediaObjects/41567_2021_1463_Fig3_HTML.png |
| Fig. 4 image (reference only, not in the repo) | https://media.springernature.com/full/springer-static/image/art%3A10.1038%2Fs41567-021-01463-1/MediaObjects/41567_2021_1463_Fig4_HTML.png |
| Source Data Fig. 3 | https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41567-021-01463-1/MediaObjects/41567_2021_1463_MOESM7_ESM.txt |
| Source Data Fig. 4 | https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41567-021-01463-1/MediaObjects/41567_2021_1463_MOESM8_ESM.txt |

## Files in `data/`

Both files are byte-for-byte copies of the Nature downloads, under their original
names.

| File | Origin | Panel(s) it feeds |
|---|---|---|
| `data/41567_2021_1463_MOESM7_ESM.txt` | Source Data Fig. 3, tab-separated 2D histogram: `BinCenterNeutrinoMassSquared` (eV²), `BinCenterEndpoint` (eV), `HistogramEntry` (1/eV³); 6 header lines, a units row, then 1764 rows (42 × 42 bins) | Fig. 3: heatmap, both marginal histograms, both contours, best-fit cross |
| `data/41567_2021_1463_MOESM8_ESM.txt` | Source Data Fig. 4, tab-separated: `experiment`, `mnu2`, `uncertainty neg`, `uncertainty pos`, `reference` (eV²); 14 experiments | Fig. 4: every row, both panels |

SHA-256 of the downloads, as fetched (`sha256sum`):

```
a5d80949946eb8946556278ab1ddf4acaab676e2c0115759fff5e1ff2fca40c0  41567_2021_1463_MOESM7_ESM.txt   (Source Data Fig. 3)
f0240ddd46552bf1e265dcff68940c4bb33c3caa818a09f64183e252393af902  41567_2021_1463_MOESM8_ESM.txt   (Source Data Fig. 4)
44c01e701bb550c3cd5401ce99bbf6d5a5d47b64d2c6703d718d7afa04fcf78e  41567_2021_1463_Fig3_HTML.png     (reference image)
eba497419433bd553483897009c92de1145e36d85524fd8037038d76a5e5524a  41567_2021_1463_Fig4_HTML.png     (reference image)
1cea4eddca0549bc136f2ad7ea0533191f619259dee4bd5a1b1be7e53239f8c1  article page, as HTML             (reference)
```

## Processing done in the scripts

Shared loading is in `_data.py`. Nothing is interpolated, smoothed, or resampled.

**Fig. 3** (`fig3.py`, `fig3_improved.py`)

* The histogram is read with `numpy.genfromtxt` (skipping the 7 header lines) and
  placed on a 42 × 42 grid by its bin centres. Values are unchanged.
* The entries are a probability density: Σ(entry × Δm² × ΔE₀) = 1.0000, so the colour
  bar is labelled in 1/eV³ (faithful) or as a probability density in eV⁻³ (improved).
* **Marginals** are derived by summing the grid: the m_ν² marginal is Σ_E₀ entry × ΔE₀
  (1/eV²) and the E₀ marginal is Σ_m² entry × Δm² (1/eV). They are drawn as bars with
  the bin widths. The original's marginals are not in the data, so these are derived.
* **Contours are derived, not in the data.** The Fig. 3 caption says "the 1σ (black
  line) and 2σ (blue line) contours are indicated"; the Source Data file has only the
  histogram. Following the requested method, `Panel.contour(hdr=(0.683, 0.954))` (inklet's
  public contour of a grid) sorts the 1764 bins by count, takes the running sum as a
  fraction of all entries, and sets the level at which it first reaches 68.3% and 95.4%.
  Level 68.3% = 13.38 (1/eV³), which encloses 68.8% of the entries in 60 bins; level
  95.4% = 1.855 (1/eV³), which encloses 95.45% in 163 bins, including one isolated 1-bin
  island. The contour runs marching squares on the bin centres, at those levels. The
  contours show the bins at or above each level, so the enclosed share is exact on the
  grid, but the outline is the bin-centre contour, not a smoothed one.
* **Best-fit cross.** Not in the data. Its position is the paper's text values: the
  best fit m_ν² = 0.26 eV² ("For the best fit of the neutrino mass squared, we find ...
  = 0.26 ... eV² based on the Monte Carlo propagation technique (Fig. 3)") and the
  ring-averaged endpoint E₀ = 18,573.69 ± 0.03 eV ("The ring-averaged fitted effective
  endpoint is E 0 = (18,573.69 ± 0.03) eV"), both in the Results text.

**Fig. 4** (`fig4.py`, `fig4_improved.py`)

* The file has five header lines, a column header and a units row; the units row is
  dropped by testing `mnu2` for a number.
* Rows are taken in the file's reverse order, so the plot runs from Los Alamos (1991)
  at the top to KATRIN (combined) at the bottom.
* Labels are expanded from the file's two-digit years: `Mainz (05)` → `Mainz (2005)`
  (years 90–99 become 19xx, others 20xx); `KATRIN (comb.)` → `KATRIN (combined)`.
* Error bars: the file's `uncertainty neg` and `uncertainty pos` are signed offsets
  from the best fit. The bar runs from `mnu2 − |neg|` to `mnu2 + |pos|`. For KATRIN (2019)
  this is −1.0 (−2.1 to −0.1).

## Not available as data

* The Fig. 3 contours (derived as above). The best-fit cross uses the paper's text
  values, which are not in the Source Data.
* The colours of the Fig. 4 series (the original's colours are approximated by eye) and
  the original's colour map for Fig. 3 (single-hue blue ramp, approximated by eye).
  The improved Fig. 3 uses inklet's `blues` palette, not the original's colours.
* The Fig. 4 caption's caveat about the Los Alamos and Livermore final-state
  distributions is text, not data; it is not drawn in the figure.
* The Fig. 3 colour bar's tick values (0, 20, 40) are chosen to match the original's
  bar; the scale itself (0 to the histogram maximum, 45.67 1/eV³) comes from the data.
