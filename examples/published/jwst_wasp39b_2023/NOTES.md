# Notes: JWST WASP-39b, Figure 3 (top panel)

## Outputs

| File | Size | Content |
|---|---|---|
| `gallery/published/jwst_wasp39b_2023_fig3.{svg,pdf,png}` | 89 × 54.6 mm (single column) | `fig3.py`, faithful |
| `gallery/published/jwst_wasp39b_2023_fig3_improved.{svg,pdf,png}` | 89 × 122.4 mm (single column) | `fig3_improved.py`, redesign |

PNG at dpi=200. `fig3.py` is 76 lines, `fig3_improved.py` 116 lines.

## Print width (pass 2)

Measured on `original-fig3.png` (1052 × 549 px):

* Cap height of the tick digit "5" in "3.5" on the x axis: 21 px (rows 489–509).
  The "W" of "Wavelength" is also 21 px, so the axis title and the tick labels
  are the same size.
* Width: 1052 px × 1.77 mm / 21 px = 88.7 mm. Snapped to **89 mm**
  (single column).
* Cross-check: the original's frame is 862 px wide, so the top plot box is
  72.9 × 26.9 mm (862 × 318.5 px at 11.82 px/mm). Plot limits come from the
  frame and the inward tick marks: x 2.89–5.67 µm (3.0 at px 161.5, 5.5 at px
  934.5, 309.2 px per µm), y 2.057–2.311 % (2.30 at px 14.5, 2.10 at px 265.5).

The original's aspect ratio (549/1052) would give 46.4 mm for the whole figure.
This pass draws only the top panel, so the height follows the top panel's
proportions (the plot box is the original's top panel size), not the whole
figure's. The bottom panel is not in the bundle.

## Lint

* `fig3.py`: `inklet lint: 1 info`: `FONT_SUBSTITUTED` (21 text primitives in
  Liberation Sans, metric-compatible with Arial). Environment, not the figure:
  Arial is not installed here. Now INFO, not a warning. No `expected_fonts` workaround.
* `fig3_improved.py`: `inklet lint: 1 info`: the same `FONT_SUBSTITUTED`
  (38 primitives). No other diagnostics. The strips have no
  `AXIS_TITLE_OVERHANG`: the "Δ depth (ppm)" title is taller than its strip and
  overhangs it, which lint accepts.

Both scripts print no UserWarnings. The faithful script's last run also printed
none.

## Which figure

Figure 3 is the one with the measured spectrum, the model fits and the
remove-one-gas variants. Figure 2 has the four reductions and Spitzer points
only. Fig. 3's top panel is reproduced; its bottom panel is not (see below).

## Matches the original

* Data: the 95 FIREFLy points at 3.014–5.548 µm, with 1σ vertical error bars,
  absolute (Rp/Rs)² converted to per cent as the published axis is. Points and
  error bars stay dark grey, as in the original.
* Series: the six remove-one-gas curves (no H₂O, no CO, no CO₂, no H₂S, no CH₄,
  no cloud) and the all-opacity best fit, all from the ScCHIMERA files.
* Key: the same eight entries in the same order and two-column layout
  (column-major: No H₂O, No CO, No CO₂, No H₂S | No CH₄, No cloud, All opacity,
  Data), inside the top-left corner as in the original. Its rows are packed
  close (`row_gap=0.2`, `pad=0.6`) so it clears the first points at 3.0 µm.
* Colours: sampled from the legend swatches of the published PNG (No H₂O
  #000080, No CO #ff0000, No CO₂ #000000, No H₂S #ffa500, No CH₄ #add8e6,
  No cloud #808080, All opacity #0000ff).
* Axes: a closed black frame whose top and right edges are plain lines, with
  inward major and minor ticks on the bottom and left axes only
  (`axes="frame"`, `scientific.nature`), no grid. (The first pass used
  `axes="box"`, which mirrors ticks onto the top and right edges; the original
  has none there.)
* Data points: 0.9 mm across, as in the original (11 px of a 1052 px image
  printed at 89 mm), with 0.2 mm error bars. Ticks as the original:
  x every 0.5 µm from 3.0 to 5.5, y every 0.05 % from 2.10 to 2.30.
* Caption checks, from the data: best-fit header in `ScCHIMERA_MODEL.txt` gives
  [M/H] = +1 (10× solar), C/O = 0.35, log K_cld = −2.15 cm² g⁻¹ (≈ 7 × 10⁻³,
  matching the caption), χ²/N = 1.29 (caption 1.3). My own χ²/N from the data
  and the interpolated best fit is 1.29 (N = 95).
* Variables: the figure's labels contain no variables, so no italics are needed.
  Units and chemical formulas are upright. The improved version italicises the
  σ in "±1σ".

## Differs, and why

* **No bottom panel (molecular cross-sections).** The bundle has no cross-section
  data, and digitising the published curves is not allowed. The figure is the top
  panel only, so its height is that of the top panel.
* **No right-hand "Scale heights" axis.** The bundle gives no zero point (the
  1-bar reference radius). The Fig. 2 caption gives 800 km per scale height, but
  that alone does not fix the offset, so the axis cannot be placed from the data.
* **The best fit is binned here, by us.** The caption says the blue curve is
  binned to the data resolution, but the bundle has only the unbinned
  217-point curve (2.80–6.64 µm). `fig3.py` averages it over each of the 95
  data bins (centre ± half the `bin_width_um` of FIREFLy), the grid the "No X"
  curves come on, so all seven curves are smooth at the same resolution.
* **Fonts.** Liberation Sans in place of Arial (see Lint).

## Improved version

Panel a shows the observed spectrum and the best fit. Panel b has six strips,
one per source, showing how much depth each source adds: best fit minus the fit
with that source removed, in ppm. The fit is interpolated onto the 95 data
wavelengths, which is the only approximation (the best fit is on a finer grid).
Peaks, from the model files: CO₂ 1,240 ppm at 4.36 µm; H₂O 753 ppm at 3.01 µm;
clouds 425 ppm at 3.89 µm; CO 191 ppm at 4.77 µm; H₂S 149 ppm at 3.79 µm; CH₄
72 ppm at 3.01 µm.

### Size

89 mm, the same as the faithful version. Each plot is 72.9 mm wide, the width of
the original's top panel. At the preset's type size, the longest strip label
("CO₂: 1,240 ppm") fits inside its strip with no overlap, and the tick labels and
axis titles are the same size as in the faithful version. 120 mm and 136 mm were not needed: a wider
page would only add empty space at the right of the plots. The height, 122 mm,
comes from seven rows: the top panel (26.9 mm), six strips (9 mm each) and the
x-axis labels under the bottom strip.

### Changes in pass 2

Removed from inside the figure (moved to the caption):

* the "Best fit: 10× solar metallicity, C/O = 0.35, χ²/N = 1.3" line;
* the strip-stack title "Depth added by each source (ppm): …";
* the sentence labels "H₂O: depth rises blueward of 3.6 µm" and "unmodelled
  feature, ~4 µm", with the arrow that pointed at the 4.03 µm bump;
* the long strip labels ("CO₂ peak 1,240 ppm at 4.36 µm"): each strip now
  carries only "CO₂: 1,240 ppm" in its own colour;
* "CO₂ band, 4.3 µm" in the top panel.

Added:

* short labels "CO₂" (at the 4.3 µm band, left of the rise) and "H₂O" (at the
  blue end) in the top panel;
* one y title for the strips, "Δ depth (ppm)", on the middle strip (row 3,
  Clouds), which overhangs the strip height and passes lint;
* panel letters: **a** for the top panel and **b** for the strip group. The
  strips are one nested subfigure so they count as one lettered cell (see
  ISSUES 4);
* the key is two entries ("Observed, ±1σ", "Best fit") at the top right, where
  the plot is empty above 2.24 %.

Kept: the Okabe–Ito colours (with darker text shades for contrast), the hollow
data markers with every 1σ bar, the black best fit, one shared ppm scale for
all strips, and the zero line in each strip.

## Checks against the paper text

* Caption: "The model is well matched to the data (χ²/N = 1.3)". Computed: 1.29. ✓
* Caption: "strong CO₂ absorption (4.1–4.6 µm)". The CO₂ effect is above 100 ppm
  from 4.19 to 4.67 µm, peaking at 4.36 µm. ✓
* Caption: "the rise in transit depth bluewards of 3.6 µm owing to water".
  The H₂O effect is largest at the blue end (753 ppm at 3.01 µm) and falls to
  about 20 ppm at 4.5 µm. ✓
* Text: "the apparent lack of methane (3.0–3.5 µm)". The CH₄ effect is at most
  72 ppm (mean 3.5 ppm), the smallest of the six. ✓
* Text: "a feature near 4.0 µm that cannot be reproduced". The residual dip at
  4.0–4.1 µm lies below the best fit (2.09–2.10 %). ✓
* Text: "clouds, CO and H₂S ... more subtle modulations". Effects of 425, 191 and
  149 ppm, against 1,240 ppm for CO₂. ✓

## Suggested caption

**a**, Transmission spectrum of WASP-39b. Open circles with 1σ error bars are the
FIREFLy data. The black line is the best fit from the ScCHIMERA model with all
opacity sources, for 10× solar metallicity, a carbon-to-oxygen ratio of 0.35 and
cloud opacity of 7 × 10⁻³ cm² g⁻¹ (χ²/*N* = 1.3, *N* = 95 points). The labels
mark the CO₂ band at 4.3 µm and the rise in depth towards 3.0 µm, which the water
absorption causes. The dip near 4.0 µm lies below the model; the paper notes that
the models do not reproduce this feature.

**b**, Depth added by each opacity source, in parts per million of transit depth.
Each curve is the best fit minus the fit with that gas or the clouds removed, so
a larger value means that source contributes more at that wavelength. The strips
share one wavelength axis and one ppm scale. The best fit is interpolated onto the
95 data wavelengths, where the remove-one-gas models are binned. The peak for each
source is given: CO₂ 1,240 ppm at 4.36 µm, H₂O 753 ppm at 3.01 µm, clouds 425 ppm
at 3.89 µm, CO 191 ppm at 4.77 µm, H₂S 149 ppm at 3.79 µm and CH₄ 72 ppm at
3.01 µm.

Data: Ahrer *et al.*, *Nature* **614**, 649–652 (2023), Fig. 3 (top panel); CC BY 4.0.

## Look-fix rounds

Faithful, three rounds. (1) The best-fit line ran past 3.0 µm and was cropped;
fixed with the measured limits. (2) The 8-entry key covered the 3.0 µm points
inside the top-left corner; `corner="best"` moved the key beside the plot and
narrowed the plot to 42.5 mm (`PLOT_WIDTH_OVERRIDDEN`). The key now sits above
the frame with `side="top"`. (3) The full image checked clean: frame, inward
ticks, key and data.

Improved, four rounds. (1) Letters were given to all seven cells, so the strips
read `b` to `g`; the strips became one nested subfigure with the letter `b`.
(2) The strip labels sat on the top frame; they were lowered, and at 120 ppm
below the top they crowded the H₂O curve (lint CROWDING), so they are 70 ppm
below the top. (3) The 4 µm sentence label and its arrow were removed, and the
CO₂ label moved beside the 4.3 µm band. (4) Full-size crops of the strips and
the top panel are clean: no overlapping text, and no label over a line or point.

## Verdict

The faithful version reproduces the top panel at the original's print width
(89 mm), with a closed black frame, inward ticks, the same data, series, colours
and scales. It omits the bottom cross-section panel and the scale-height axis,
which the bundle cannot supply, and its key sits above the frame. The improved
version uses the same data and message: a clean observed-versus-model panel and
six colour-blind-safe strips that make each source's contribution comparable.
It keeps every error bar, and every explanation is in the caption.
