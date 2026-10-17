# Notes: JWST WASP-39b, Figure 3 (top panel)

## Outputs

| File | Size | Content |
|---|---|---|
| `gallery/published/jwst_wasp39b_2023_fig3.{svg,pdf,png}` | 183 × 70.3 mm (double column) | `fig3.py`, faithful |
| `gallery/published/jwst_wasp39b_2023_fig3_improved.{svg,pdf,png}` | 183 × 142.5 mm (double column) | `fig3_improved.py`, redesign |

PNG at dpi=200. `fig3.py` is 73 lines, `fig3_improved.py` 111 lines.

## Lint

* `fig3.py`: `inklet lint: 1 warning`: `FONT_SUBSTITUTED` (21 text primitives in
  Liberation Sans, not Arial). Environment, not the figure: Arial is not installed
  on this machine, and the Nature profile expects it. Logged as ISSUES item 3. The
  preset is kept as published.
* `fig3_improved.py`: `inklet lint: 1 warning`: the same `FONT_SUBSTITUTED`
  (39 primitives). No other diagnostics.

Both scripts print no UserWarnings on the final run.

## Which figure

Figure 3 is the one with the measured spectrum, the model fits and the
remove-one-gas variants. Figure 2 has the four reductions and Spitzer points
only. Fig. 3's top panel is reproduced; its bottom panel is not (see below).

## Matches the original

* Data: the 95 FIREFLy points at 3.014–5.548 µm, with 1σ vertical error bars,
  absolute (Rp/Rs)² converted to per cent as the published axis is.
* Series: the six remove-one-gas curves (no H₂O, no CO, no CO₂, no H₂S, no CH₄,
  no cloud) and the all-opacity best fit, all from the ScCHIMERA files.
* Key: the same eight entries in the same order and two-column layout
  (column-major: No H₂O, No CO, No CO₂, No H₂S | No CH₄, No cloud, All opacity,
  Data), in the upper-left corner over empty space. (The improved version
  uses a two-entry key at the top right instead; see below.)
* Colours: sampled from the legend swatches of the published PNG (No H₂O
  #000080, No CO #ff0000, No CO₂ #000000, No H₂S #ffa500, No CH₄ #add8e6,
  No cloud #808080, All opacity #0000ff). Data markers dark grey.
* Axes: x 3.0–5.5 µm (ticks every 0.5), y transit depth 2.10–2.30 % (ticks every
  0.05), no grid, drawn with inklet's `scientific.nature` axes. The x and y ranges
  are estimated from the published axis extents.
* Caption checks, from the data: best-fit header in `ScCHIMERA_MODEL.txt` gives
  [M/H] = +1 (10× solar), C/O = 0.35, log K_cld = −2.15 cm² g⁻¹ (≈ 7 × 10⁻³,
  matching the caption), χ²/N = 1.29 (caption 1.3). My own χ²/N from the data
  and the interpolated best fit is 1.29 (N = 95).

## Differs, and why

* **No bottom panel (molecular cross-sections).** The bundle has no cross-section
  data, and digitising the published curves is not allowed. The figure is the top
  panel only, so it is shorter than the original (70 mm against about 95 mm for
  the whole figure at the same width).
* **No right-hand "Scale heights" axis.** The bundle gives no zero point (the
  1-bar reference radius). The Fig. 2 caption gives 800 km per scale height, but
  that alone does not fix the offset, so the axis cannot be placed from the data.
* **The best-fit line is the high-resolution model, not a binned one.** The
  caption says the blue curve is binned to the data resolution. The bundle has
  only the unbinned 217-point curve (2.80–6.64 µm), so it is drawn over the data
  range only. The "No X" curves are binned to the data grid.
* **Fonts.** Liberation Sans in place of Arial (see Lint).
* **Axis ranges are estimates.** The original has no frame, so the left and right
  limits (2.9 and 5.6 µm) and the bottom and top (2.06 and 2.31 %) come from the
  tick positions in the published PNG.

## Improved version

Panel a shows the observed spectrum and the best fit. Panel b has six strips, one
per source, showing how much depth each source adds: best fit minus the fit with
that source removed, in ppm. The fit is interpolated onto the 95 data wavelengths,
which is the only approximation (the best fit is on a finer grid). Peaks, from
the model files: CO₂ 1,240 ppm at 4.36 µm; H₂O 753 ppm at 3.01 µm; clouds 425
ppm at 3.89 µm; CO 191 ppm at 4.77 µm; H₂S 149 ppm at 3.79 µm; CH₄ 72 ppm at
3.01 µm.

Each change, and the problem in the original it fixes:

1. **Seven overlapping, near-identical curves on one axis.** The original draws
   the six no-X curves and the best fit on one axis, so they overprint each other
   between 4.1 and 4.7 µm. Now the observed spectrum and best fit get a panel of
   their own (a), and the no-X curves are removed from it. The contribution of
   each source is drawn in its own strip (b), so no line overlays another.
2. **Legend far from the data.** The original key has eight entries to match to
   lines by colour. The redesign keeps only the two entries that need a key, the
   observed points and the best fit, in a real `legend(corner="ne")` in the top
   right, where the plot is empty and the key covers no data. The names are
   "Observed (FIREFLy), ±1σ" and "Best fit (ScCHIMERA)". The strips need no key:
   each is named at its right-hand end, with its peak value, in the strip's colour.
   (An earlier draft set the same two names as loose text in the corner, with no
   swatches; it was replaced by this key.)
3. **Colours not colour-blind safe.** The original uses navy against blue and red
   against orange. Each source now has a hue from the Okabe–Ito set: CO₂
   vermillion (#d55e00), H₂O blue (#0072b2), CO bluish green (#009e73), H₂S
   orange (#e69f00), CH₄ sky blue (#56b4e9); clouds are neutral grey (#7a7a7a).
   Text uses a darker shade of each hue so every label passes the 4.5:1 contrast
   check (lint `LOW_CONTRAST` fixed). H₂O and CH₄ are both blue hues; they differ
   in lightness and each has its own labelled strip, so they can be told apart
   without a key.
4. **Absorption features not labelled on the plot.** The CO₂ band at 4.3 µm is
   labelled beside its peak ("CO₂ band, 4.3 µm"). The H₂O band is labelled at
   3.0 µm, above the data ("H₂O: depth rises blueward of 3.6 µm"). The ~4 µm
   feature that the paper says the models cannot reproduce is labelled above the
   data, at 4.12 µm, 2.185 %, with a short downward arrow that stops just above
   the error bar of the small bump at 4.03 µm (its top is 2.154 %). Neither the
   text nor the arrow crosses a point or an error bar. The earlier label sat
   beneath the dip, where the bars and points crossed it.
5. **Ablation impact hard to read.** The original makes you compare the vertical
   gaps between eight lines. In the strips the gas contributions share one
   wavelength axis and one ppm scale (−60 to 1,300 ppm), so their sizes compare
   directly. Each strip is filled from zero, so the area shows the size. The
   scale is the same in every strip, so CH₄, at 72 ppm, looks flat, which is
   right: its effect is small.
6. **Overplotting of data and model.** The data are hollow rings with 1σ error
   bars, so the black best-fit line runs through them and is still visible.
7. **Summary numbers.** The best-fit parameters (10× solar, C/O = 0.35,
   χ²/N = 1.3) go in the top-left corner, where the plot is empty.
8. **Repeated axis labels.** The x-axis tick labels and "Wavelength (µm)" appear
   only under the bottom strip. The top panel and the other strips keep their
   ticks but drop the labels.
9. **Sign convention.** A title over the strips states what they show ("Depth
   added by each source: best fit minus the fit without it"), so a reader need
   not infer the sign. The axis of the first strip reads "Added depth (ppm)",
   which is also the unit of the other strips' tick labels. It is set beside the
   first strip and is not clipped.

Still missing from the improved version, as in the faithful one: the molecular
cross-section panel and the scale-height axis (no data).

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

## Verdict

The faithful version reproduces the top panel with the same data, series,
key and scales. It omits the bottom cross-section panel and the scale-height axis,
which the bundle cannot supply. The improved version uses the same data and
message: a clean observed-versus-model panel and six colour-blind-safe strips that
make each source's contribution comparable. It keeps every error bar and needs no
key.

Look-fix rounds: faithful, two (the best-fit line ran past 3.0 µm and was cropped;
the scale and keys then checked clean). Improved, four: the bottom-axis row was
off by one; the strip labels used 1,000 × too large units (fixed by computing
in absolute depth); two labels were too light and an error bar crossed the CO₂
label; the 500 ppm tick was dropped in the short strips. Review round (improved):
the two corner texts with no swatches became a real key; the 4 µm annotation moved
above the data with an arrow; the bare "ppm" label became "Added depth (ppm)".
Each was checked at full size, and the crops at 3.9–4.3 µm and the top-right
corner are clean.
