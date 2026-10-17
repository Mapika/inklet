# Notes: KATRIN 2022, Figures 3 and 4

## Outputs

All in `gallery/published/`, each as `.svg`, `.pdf` and `.png` (200 dpi). Every
figure is 89 mm wide, the single column, and its height follows the original's
aspect ratio.

| Script | Output | Size |
|---|---|---|
| `fig3.py` | `katrin_2022_fig3` | 89 × 69.5 mm |
| `fig3_improved.py` | `katrin_2022_fig3_improved` | 89 × 69.5 mm |
| `fig4.py` | `katrin_2022_fig4` | 89 × 95.8 mm |
| `fig4_improved.py` | `katrin_2022_fig4_improved` | 89 × 126.9 mm |

The SVG of Fig. 3 is about 1.3 MB because the 42 × 42 heatmap is kept as 1764
vector cells (inklet's vector choice below its 2000-cell raster threshold).

Shared code: `_data.py` loads both data files, and gives the bin edges of the
Fig. 3 grid. The contours come from `Panel.contour(hdr=)` and the marginals from
`Panel.hist(prebinned=True)`, so the figures use no private inklet helper.

## Print width (pass 2)

Measured on the original PNGs (`scratchpad/katrin/`), with the cap height of a tick
digit "0" on the bottom axis, read at a threshold of 128. A 7 pt Arial cap is
1.77 mm, so the width is W_px × 1.77 / cap_px.

| Figure | Original (W × H px) | Cap height (px) | Width | Chosen |
|---|---|---|---|---|
| Fig. 3 | 1030 × 800 | 20 | about 91 mm | 89 mm, height 69.1 mm |
| Fig. 4 | 1021 × 1098 | 18 to 20 | about 90 to 100 mm | 89 mm, height 95.7 mm |

Both snap to 89 mm, the single column. The previous pass already used 89 mm, so
the width did not change; the heights did, to match the originals.

## Lint

Run as `PYTHONPATH=<worktree>/src .venv/bin/python <script>`.

* `fig3.py`: `inklet lint: 1 info`.
* `fig3_improved.py`: `inklet lint: 1 info`.
* `fig4.py`: `inklet lint: 1 info`.
* `fig4_improved.py`: `inklet lint: 1 info`.

The one info in each is **FONT_SUBSTITUTED**. This sandbox has no Arial, so inklet
sets the text in Liberation Sans, which has the same metrics. The figures are
otherwise unaffected: install Arial to remove the info. No `expected_fonts=None`
workaround is needed. The earlier warnings are gone: the layout now honours the
authored plot widths (no PLOT_WIDTH_OVERRIDDEN), and the strokes use three
weights (0.21 mm frame and ticks, 0.35 mm data and contour, 0.4 mm contour and
cross, with 0.10 mm for the marginal bar edges) instead of several.

## What changed in pass 2

**Faithful versions.**

* Frame: `i.preset("scientific.nature", format="single-column", axes="box")`
  gives a closed black frame with inward major and minor ticks. The old open
  axes and the explicit `outline()` calls are gone.
* Italic variables: `//m//_{ν}^{2}` and `//E//_{0}` in Fig. 3, and `//m//_{ν}^{2}`
  in Fig. 4. Units stay upright.
* Fig. 3: the contours come from `Panel.contour(hdr=(0.683, 0.954))` in place of the
  private `inklet.plot.outlines._contours`. The colours are given largest region
  first (95.4% blue, 68.3% black), because `hdr=` sorts its shares that way. The
  marginals are `Panel.hist(counts, bins=edges, prebinned=True)` rather than hand-built
  bars. The cross is 0.35 mm, so it is as heavy as the contours. The colour bar is
  13 mm long, not 15, so its title clears a data cell.
* Fig. 4: the original labels both x edges, so the top axis now has ticks at
  −200, −100 and 0. The right-hand mirror is unlabelled, as in the original. The
  zero rule is light grey, as in the original, and 0.35 mm. The inset's axis title is
  now `//m//_{ν}^{2} (eV^{2})`, with no "Zoom:" prefix, since the original's inset has
  no such title. The inset's rows are level with the same rows on the main axis, which
  they were not before (see Differs).
* Error bars keep their per-experiment colours, because the original's are coloured,
  not black. Axes, frame and ticks are black.

**Improved versions.**

* Fig. 3 improved: the labels are "68.3%" and "95.4%", and "//m//_{ν}^{2} = 0" at the
  boundary line. I found no sentence-like label in this figure. The colour-bar
  title, "Probability density (eV^{-3})", is a quantity label and was kept.
* The 95.4% label moved from the outer ring's tip to the empty upper-left corner,
  with a leader to the ring. At the tip it overlapped ten pale cells (OVERLAP).
  The leader ends were read off the rendered contour.
* Fig. 4 improved: the panel titles "All results, full range" and "Magnified: the
  blue band above, −10 to +10 eV^{2}" are removed, and so is the "unphysical,
  m_ν² < 0" text. The explanation is in the suggested caption below.
* The link between the two panels is shading: the blue window in panel a and the
  background of panel b share the colour #dcebf7. The grey m² < 0 region stays in
  panel a. Panel letters a and b are added.
* KATRIN value labels are kept ("0.26 ± 0.34" and so on). Their colour is darkened to
  #005a8c, because the KATRIN blue #0072b2 is only 4.26:1 on the window blue, below
  the 4.5:1 that lint asks for.

## Matches the original

* **Fig. 3.** One panel: a heatmap of the 42 × 42 histogram, the marginal histograms
  along the top and right, the colour bar inside the lower-right corner with the same
  "Normalized entries (1/eV³)" quantity, the best-fit cross, the white-on-blue ramp
  from white at zero to dark navy, a black 1σ contour and a blue 2σ contour, the
  m_ν² range −1.5…1.7 eV² (bin edges), the E₀ range 18,573.57…18,573.80 eV with
  thousands separators, and a closed frame. The print size matches the original's.
* **Fig. 4.** One panel with all 14 rows, labelled on the left, Los Alamos (1991) at
  the top to KATRIN (combined) at the bottom; error bars run from the lower to the
  upper bound; the x range −240…+70 eV², labelled at the top and the bottom with
  −200, −100 and 0; a grey zero line; the magnified inset of the modern results at
  the lower left, joined to a rectangle drawn around the same rows in the main panel.

## Differs, and why

* **Heatmap tick direction.** On a heatmap, `axes="box"` keeps the labelled ticks
  outward and draws the top and right edges as a bare frame. The library does this
  on purpose: an inward tick on a cell reads as a comb over the colour. The original's
  ticks point inward, so this is a visible difference from the original's look.
  Panel frames in Fig. 4 do use inward ticks.
* **Fig. 4 top mirror.** The original's right-hand edge is unlabelled, and so is ours.
  Its top edge is labelled in both.
* **Fig. 3 contours are derived, not read from the paper.** The caption says the 1σ and
  2σ contours are indicated, but the Source Data holds only the histogram. Following
  the method, the contours are the highest-density regions of the grid:
  `Panel.contour(hdr=(0.683, 0.954))` takes the bins by count, and the level at which
  the running sum reaches 68.3% and 95.4% of all entries. Level 68.3% is 13.38 (1/eV³),
  and encloses 68.8% of the entries in 60 bins. Level 95.4% is 1.855 (1/eV³), and
  encloses 95.45% in 163 bins, one of whose rings is a single-bin island at
  m² ≈ −0.8 eV². **The original's contours may come from a different method** (for
  example a fit to the distribution, or a contour of the smoothed density), so their
  shape can differ. The contours are not smoothed.
* **Fig. 3 marginals are derived.** The original's top and right histograms are not
  in the data. They are the sums of the grid, so their shapes match the data exactly.
  Their heights have no axis, as in the original.
* **Fig. 3 best-fit cross is at the paper's stated values.** The paper's text gives
  both (Results, "Best-fit result and upper limit"):
  > "For the best fit of the neutrino mass squared, we find m_ν² = 0.26 (with the
  > uncertainty typeset as +0.34 above and −0.34 below) eV² based on the Monte Carlo
  > propagation technique (Fig. 3)." (The source has the formula as a TeX expression.)
  > "The ring-averaged fitted effective endpoint is E 0 = (18,573.69 ± 0.03) eV."
  The cross is drawn at (0.26 eV², 18,573.69 eV). It is not put at the histogram's mode
  (0.264 eV², 18,573.703 eV), which lies about 0.013 eV above the stated endpoint.
* **Fig. 3 colour.** The original uses a single-hue blue ramp that I approximated by
  eye; the faithful version uses a five-stop white-to-navy ramp, and the improved
  version uses ColorBrewer's `blues` (see below). Zero-count bins are drawn white in
  both: they are passed to inklet as missing values, so they carry no colour of their own.
* **Fig. 4 colours.** The original's per-experiment colours are not in the data. The
  faithful version uses hues close to the original's, by eye. The labels are inklet's
  own text.
* **Fig. 4 inset.** The original's inset is a magnified copy of the modern rows. Here
  it is built at its printed size (30 × 36.3 mm) and drawn with `width=None`, so its
  type is not shrunk. Its rows and x range are those of the window. Its rows sit on
  the main panel's row pitch, so each inset row is level with its label on the main
  axis, as in the original. The main panel's y range therefore runs 1.5 rows below
  the last row, which is where the inset's own axis sits. Before this, the inset's
  rows were level with nothing on the main axis. The rows shown are
  those whose whole error bar lies in −10…3 eV²: Mainz (1999), Troitsk (1999), Mainz
  (2005), Troitsk (2011), KATRIN (2019), (2021), and (combined). Troitsk (1995), at
  −22 ± 4.8 eV², is outside the window and appears only in the main panel.
* **Fig. 4 axis ends.** Labels are the full years (the source has two-digit years and
  "comb.").
* **Fig. 4 error bars.** The paper's caption says they are "generated from combined
  statistical and systematic uncertainties", and gives no confidence level. The
  suggested caption repeats this, and does not add one.

## Improved version: colour and layout choices

### Fig. 3

* **Light-to-dark colour map.** The first improved version used viridis, whose lowest
  values are dark purple, so the sparse tails (near −1.5 eV² and 18,573.57 eV, and the
  scattered top-right cells) read as the most prominent marks and exaggerate noise.
  The improved figure uses ColorBrewer's `blues` (inklet's palette name): pale at low
  density and dark at the core, monotonic in lightness, and CVD-safe. (`blues` is a
  ColorBrewer sequential scheme, not one of the perceptually uniform maps; `cividis_r`
  was the other option, with a pale-yellow low end and a grey middle.)
* **A colour bar that says what the number is.** The original's label "Normalized
  entries (1/eV³)" does not say that the values integrate to one. The bar now reads
  "Probability density (eV⁻³)", which is what the data are (Σ entry × Δm² × ΔE₀ = 1).
* **Contours labelled directly.** Both rings are dark (near-black), because white lines
  disappear on the pale low end of the ramp. "68.3%" and "95.4%" are named in the empty
  upper-left corner, each with a leader to its ring. Both labels have a white halo.
* **m_ν² = 0 marked.** The physical boundary is a dashed vermillion line (#d55e00,
  Okabe-Ito) at m_ν² = 0, running the full height of the heatmap, with its label at
  the top end. Vermillion stays visible on every cell.
* **Best-fit cross kept, unlabelled.** It is at the paper's values, (0.26 eV², 18,573.69
  eV). The numbers are in the key-numbers table below.
* **Marginals in neutral grey,** so the blue of the heatmap is not repeated, and the
  eye goes to the 2D distribution.

### Fig. 4

* **Two panels, one column.** Most early uncertainties are tens of eV² (±25 to
  ±107 eV²), so they fill the axis, while the modern ones (±0.33 to ±0.34 eV²) are dots
  at zero. Two stacked panels solve it without dropping any error bar: panel a has all
  14 rows on the full −240…+70 eV² range, and panel b has the same rows magnified to
  −10…+10 eV², for the seven rows whose whole bar lies in that window (Troitsk 1995 is
  in panel a only).
* **KATRIN highlighted.** The three KATRIN results are blue; every other experiment is
  grey, so the eye goes to the modern results.
* **Values printed next to the KATRIN bars.** Their best fits and uncertainties are
  printed beside the bars: 0.11 ± 0.33 (combined), 0.26 ± 0.34 (2021), and −1.0 (−1.1,
  +0.9) for 2019, with the asymmetric offsets given where they differ. These are the
  data's numbers.
* **Unphysical region.** The m² < 0 region is shaded grey in panel a, and the blue
  window marks the magnified range. The caption says what both mean.

## Suggested caption

### Fig. 3 (improved)

**Distribution of the fitted neutrino mass squared and endpoint.** A two-dimensional
histogram (42 × 42 bins) of the m_ν² and E₀ values from the Monte Carlo propagation,
coloured by probability density in eV⁻³, so that the density integrates to one over
the plotted range. Black contours enclose the 68.3% and 95.4% highest-density
regions. The white cross marks the best fit, m_ν² = 0.26 eV² and E₀ = 18,573.69 eV.
The dashed line marks m_ν² = 0; values below it are unphysical. The top and right
histograms are the projections of the distribution onto each axis. Source Data for
Fig. 3.

### Fig. 4 (improved)

**Best-fit neutrino mass squared from tritium experiments.** **a**, Best-fit m_ν² for
the historical tritium experiments (1991 to 2021) and the two KATRIN results, with
total uncertainties, combined statistical and systematic, as horizontal bars. Grey
points are previous experiments and blue points are KATRIN. The grey region is
unphysical (m_ν² < 0), and the blue band is the window shown in **b**, from −10 to
+10 eV². **b**, The KATRIN-era results and the modern tritium results whose whole bar
lies in that window, on a magnified scale. The blue background is the same window as
the band in **a**. Values are best fit ± uncertainty, in eV²; asymmetric uncertainties
are given as offsets. Troitsk (1995) lies outside the window and appears only in **a**.
Source Data for Fig. 4.

## Key numbers checked against the paper

| Quantity | From the data | Paper | Status |
|---|---|---|---|
| Fig. 3: histogram total | Σ entry × Δm² × ΔE₀ = 1.0000 | (normalisation) | matches |
| Fig. 3: best-fit m_ν² (cross) | 0.26, the value used for the cross | 0.26 eV² (text) | matches, but the histogram's own median is 0.134 eV² (see below) |
| Fig. 3: E₀ (cross) | 18,573.69 eV, the value used for the cross | 18,573.69 ± 0.03 eV (text) | matches |
| Fig. 3: histogram mode | 0.264 eV², 18,573.703 eV | (not stated) | not used |
| Fig. 3: peak density | 45.67 (1/eV³) | colour bar to ~45 | matches |
| Fig. 4: KATRIN (2021) | 0.26, −0.34/+0.34 | (0.26 ± 0.34) eV² | matches |
| Fig. 4: full range | lowest bar −226 (Los Alamos), highest +58 (Beijing) | axis −240…+70 | fits |
| Fig. 4: rows | 14 | 13 referenced experiments plus KATRIN (combined) | matches |

**Discrepancy, unresolved.** The paper says the best fit is "the one-dimensional
weighted median of the distribution" and gives 0.26 eV². The m_ν² marginal of the
Source Data histogram has a median of 0.134 eV² and a mean of 0.174 eV²; 55% of its
weight lies below 0.26 eV². The histogram's two-dimensional mode is at 0.264 eV²,
close to the paper's value, but a mode is not the weighted median the paper defines.
The cause is not established: the paper's weighting may not be the bin counts of this
export, or the export may be a different sample. The figures plot the data as given;
the mismatch is not corrected. The cross uses the paper's stated values, not the
histogram's mode.

## Checks

* Pass 2: both scripts of each figure run from `examples/published/katrin_2022/`.
  Each PNG was viewed at full size after its last change. Fixes made in this pass: the
  95.4% label moved off the tip cells; the KATRIN value labels darkened for contrast;
  the band of the Fig. 4 improved panel a stopped below the m² = 0 label; the 95.4%
  leader endpoint corrected from the rendered pixels; the stroke weights folded to
  three.
* Pass 1 (earlier): two or more look-fix rounds on each figure, including the marginal
  bar widths, the colour bar, the inset text size, and the Fig. 3 contour labels.
* Fig. 4 rows: the parsed table was printed and checked against the raw file (14 rows;
  best fits and offsets match, e.g. KATRIN (2021) 0.26 with −0.34/+0.34).
* Contour levels confirmed in pass 2 with `inklet.plot.mass_levels`: 13.381 and 1.855,
  enclosing 68.8% (60 bins) and 95.45% (163 bins).
* Scripts run in a few seconds and read only from `data/`.
