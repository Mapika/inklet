# Notes: KATRIN 2022, Figures 3 and 4

## Outputs

All in `gallery/published/`, each as `.svg`, `.pdf` and `.png` (200 dpi). Single
column (89 mm) throughout.

| Script | Output | Size |
|---|---|---|
| `fig3.py` | `katrin_2022_fig3` | 89 × 80.1 mm |
| `fig3_improved.py` | `katrin_2022_fig3_improved` | 89 × 80.1 mm |
| `fig4.py` | `katrin_2022_fig4` | 89 × 101.8 mm |
| `fig4_improved.py` | `katrin_2022_fig4_improved` | 89 × 136.0 mm |

The SVG of Fig. 3 is 1.3 MB because the 42 × 42 heatmap is kept as 1764 vector
cells (inklet's vector choice below its 2000-cell raster threshold).

Shared code: `_data.py` (loads both data files, derives the Fig. 3 contours and
marginals, parses the Fig. 4 table).

## Lint

Run as `PYTHONPATH=<worktree>/src .venv/bin/python <script>`.

* `fig3.py`: `inklet lint: 5 warnings, 6 infos`. Explained below.
* `fig3_improved.py`: `inklet lint: 9 warnings, 10 infos`. Explained below.
* `fig4.py`: `inklet lint: 1 warning, 1 info`. Explained below.
* `fig4_improved.py`: `inklet lint: 2 warnings, 1 info`. Explained below.

The warnings common to all four:

* **FONT_SUBSTITUTED.** This sandbox has no Arial, so inklet's preset falls back to
  Liberation Sans. The fix is to install Arial; the figures are otherwise unaffected.
* **INCONSISTENT_STROKE (info).** The figures use several stroke weights on purpose
  (heatmap cell edges, contour lines and halos, spines, data rules). Left as is.

The other diagnostics are false positives, each checked against the data:

* **OVERLAP / CROWDING on the Fig. 3 colour bar, its tick labels, and the labels.**
  lint counts an empty matrix cell (a bin with 0 entries, drawn white or viridis's
  missing colour) as a mark, so text over blank bins is reported. I checked the
  lower-right corner, where the faithful key sits: 330 bins, of which one is
  non-empty (0.032 against a peak of 45.7, under the key's title). In the improved
  figure the key covers four cells, of which at most that same 0.032 bin holds any
  entries. The labels "68.3%", "95.4%" and
  "m²ν = 0" sit on the viridis tails or on blank bins, with a white halo.
* **LINK_CROSSES (improved Fig. 3).** The "95.4%" label's leader runs over the
  heatmap by one millimetre. A leader has to cross the data to reach a contour, so
  the crossing is intended.
* **OVERLAP on "m²ν = 0" (improved Fig. 4).** The label sits on the pale grey
  "unphysical" region (m²ν < 0), which is a shaded rectangle, not data.
* **CROWDING on the Fig. 4 labels.** The labels "unphysical, m²ν < 0" and "m²ν = 0"
  sit close to the top row's marks; no overlap, so left as is.

## Matches the original

* **Fig. 3.** One panel: a heatmap of the 42 × 42 histogram, the marginal histograms
  along the top and right (sharing axes), the colour bar inside the lower-right corner
  with the same "Normalized entries (1/eV³)" quantity, the best-fit cross, the
  white-on-blue colour ramp from white at zero to dark navy, the 1σ contour in black
  and the 2σ contour in blue, the m_ν² range −1.5…1.7 eV² (bin edges) and the E₀ range
  18,573.57…18,573.80 eV with thousands separators, and a full frame.
* **Fig. 4.** One panel with all 14 rows, labelled on the left, Los Alamos (1991) at the
  top to KATRIN (combined) at the bottom; error bars run from the lower to the upper
  bound; the x range −240…+70 eV² with ticks −200, −100, 0; a grey zero line; a
  magnified inset of the modern results at the lower left (−10 to 3 eV², with ticks
  −8 to 2), joined to a rectangle drawn around the same rows in the main panel.

## Differs, and why

* **Fig. 3 contours are derived, not read from the paper.** The caption says the 1σ and
  2σ contours are indicated, but the Source Data holds only the histogram. Per the
  method the task asked for, the contours are the highest-density regions: bins sorted
  by count, with the level at which the running sum reaches 68.3% and 95.4% of all
  entries. Level 68.3% is 13.38 (1/eV³) and encloses 68.8% of the entries in 60 bins;
  level 95.4% is 1.855 (1/eV³), enclosing 95.45% in 163 bins (one of its rings is a
  single-bin island at m² ≈ −0.8 eV²). **The original's contours may come from a
  different method** (for example a fit to the distribution, or a contour of the
  smoothed density), so their shape can differ from these. The contours follow the
  bin centres and are not smoothed.
* **Fig. 3 marginals are derived.** The original's top and right histograms are not
  in the data. They are the sums of the grid (the same bins, the same data), so
  their shapes match the data exactly; their heights have no axis, as in the original.
* **Fig. 3 best-fit cross is placed from the histogram.** The paper gives m_ν² = 0.26
  eV² but not the E₀ best fit. The cross is at the histogram's maximum bin (0.264 eV²,
  18,573.703 eV), which agrees with the original's cross to within about 0.01 eV in E₀ by eye.
* **Fig. 3 colour.** The original uses a single-hue blue ramp that I approximated by eye;
  the faithful version uses a five-stop white-to-navy ramp, and the improved version
  uses viridis.
* **Fig. 3 empty bins.** Zero-count bins are drawn white in the faithful version and
  as blank (white) in the improved one; they are passed to inklet as missing values, so
  they carry no colour of their own.
* **Fig. 4 colours.** The original's per-experiment colours are not in the data. The
  faithful version uses hues close to the original's, by eye. The labels are
  inklet's own text.
* **Fig. 4 inset.** The original's inset is a magnified copy of the modern rows. Here
  it is built at its printed size (30 × 36 mm) and drawn with `width=None`, so its
  type is not shrunk; its rows and x range are the same as the window's. The rows
  shown are those whose whole error bar lies in −10…3 eV²: Mainz (1999), Troitsk
  (1999), Mainz (2005), Troitsk (2011), KATRIN (2019), (2021), and (combined).
  Troitsk (1995), at −22 ± 4.8 eV², is outside the window and appears only in the
  main panel.
* **Fig. 4 axis ends.** Labels are the full years (the source has two-digit years
  and "comb.").

## Improved version

### Fig. 3

* **Colour map, not a single-hue ramp.** The original's white-to-navy ramp varies
  mostly in lightness. Viridis is perceptually uniform, changes both hue and lightness
  in order, and is CVD-safe. Empty bins are drawn as blank, so the white field means
  "no entries" and does not look like the lowest density.
* **A colour bar that says what the number is.** The original's label "Normalized
  entries (1/eV³)" does not say that the values integrate to one. The bar now reads
  "Probability density (eV⁻³)", which is what the data are (Σ entry × Δm² × ΔE₀ = 1).
* **Contours labelled directly.** The original has no labels and the reader must match
  line colour to the caption. The improved figure names "68.3%" with a leader into the
  empty upper-left corner, and "95.4%" at the right-hand end of its outer ring. Each
  label has a white halo so it reads over the cells.
* **m²ν = 0 marked.** The physical boundary is a dashed line at m²ν = 0, labelled,
  because the half-plane m²ν < 0 is unphysical. The original does not mark it.
* **Best-fit cross kept, unlabelled.** Its E₀ position is derived, so it is not given a
  value on the figure; the paper's m_ν² = 0.26 eV² is in the key-numbers table below.
* **Marginals in neutral grey.** So the blue of the heatmap is not repeated, and the
  eye goes to the 2D distribution.

### Fig. 4

* **Squashed sliver.** Most early uncertainties are tens of eV² (±25 to ±107 eV²),
  so they fill the axis, while the modern ones (±0.33 to ±0.34 eV²) are dots at zero. Two stacked
  panels solve it without dropping any error bar:
  * the top panel has all 14 rows on the full −240…+70 eV² range; each bar is drawn in
    full, so nothing is clipped;
  * the bottom panel has the same rows magnified to −10…+10 eV², for the seven rows
    whose whole bar lies in that window (Troitsk 1995 is in the top panel only).
  The shaded blue band across the top panel is the magnified window, so the link is
  explicit; the bottom panel's title points to it.
* **KATRIN highlighted.** The three KATRIN results are blue; every other experiment is
  grey, so the eye goes to the modern results.
* **Values printed next to the KATRIN bars.** Their best fits and uncertainties are
  printed beside the bars: 0.11 ± 0.33 (combined), 0.26 ± 0.34 (2021), and −1.0 (−1.1,
  +0.9) for 2019, with the asymmetric offsets given where they differ. These are the
  data's numbers.
* **m²ν = 0 boundary labelled.** The original has a grey line at zero with no label.
  The improved figure draws a black line labelled "m²ν = 0", and shades the
  unphysical region m²ν < 0 (the paper calls it "non-physical regime of m²ν < 0").
* **Labelled experiments on both axes.** Each row is named on the left, as in the
  original; the bottom panel repeats the names, since it is a separate panel.

## Key numbers checked against the paper

| Quantity | From the data | Paper | Status |
|---|---|---|---|
| Fig. 3: histogram total | Σ entry × Δm² × ΔE₀ = 1.0000 | (normalisation) | matches |
| Fig. 3: best-fit m_ν² | histogram mode 0.264 eV²; marginal median 0.134 eV² | 0.26 (weighted median) | **the mode matches; the median does not** (see below) |
| Fig. 3: E₀ | histogram mode 18,573.703 eV; E₀ marginal median 18,573.694 eV | "E₀ = 18,574 eV" (approximate) | consistent |
| Fig. 3: peak density | 45.67 (1/eV³) | colour bar to ~45 | matches |
| Fig. 4: KATRIN (2021) | 0.26, −0.34/+0.34 | (0.26 ± 0.34) eV² | matches |
| Fig. 4: full range | lowest bar −226 (Los Alamos), highest +58 (Beijing) | axis −240…+70 | fits |
| Fig. 4: rows | 14 | 13 referenced experiments plus KATRIN (combined) | matches |

**Discrepancy, unresolved.** The paper says the best fit is "the one-dimensional
weighted median of the distribution" and gives 0.26 eV². The m_ν² marginal of the
Source Data histogram has a median of 0.134 eV² and a mean of 0.174 eV²; 55% of its
weight lies below 0.26 eV². Its mode (0.264 eV²) is the paper's value. The cause is not
established: the paper's weighting may not be the bin counts of this export, or the
export may be a different sample. The figures plot the data as given; the mismatch is
not corrected, and the best-fit cross is placed at the mode for that reason.

## Checks

* Two or more look-fix rounds on each figure. Fixes made during these rounds: the
  marginal bar widths (`width=` is in data units, so a horizontal bar set to 1 eV on a
  0.2-eV axis made the page 1,100 mm tall); the colour bar length and corner (it
  overlapped the 95.4% tails); the inset rendered at 0.7 scale (text under 5 pt), now
  built at printed size; the Fig. 4 inset's y tick numbers (1–7) and title, removed;
  the improved Fig. 3 contour labels, moved off the rings with a halo and a leader.
* Fig. 4 rows: the parsed table was printed and checked against the raw file (14 rows;
  best fits and offsets match, e.g. KATRIN (2021) 0.26 with −0.34/+0.34).
* Scripts run in a few seconds and read only from `data/`.
