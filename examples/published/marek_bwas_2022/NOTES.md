# Notes: Marek et al. (2022), Figure 1

## Outputs

| Script | Output | Size |
|---|---|---|
| `fig1.py` (faithful) | `gallery/published/marek_bwas_2022_fig1.{png,svg,pdf}` | 183 × 142.2 mm (double column) |
| `fig1_improved.py` | `gallery/published/marek_bwas_2022_fig1_improved.{png,svg,pdf}` | 183 × 147.2 mm (double column) |

Lint, from `figure.report(expect={"SERIES_FLATTENED"})`:

* `fig1.py`: `inklet lint: 3 infos, 4 acknowledgeds`. Acknowledged: four
  `SERIES_FLATTENED` on the mean line in panels e and f. The mean is flat across
  sample size by design (it is the finding that the mean does not move while the
  intervals shrink), so the warning is kept on record and acknowledged, not hidden.
  Infos: two `DATA_CLIPPED`, for the fit lines of g cognitive subsample B (r = −0.64)
  and h cognitive subsample B (r = −0.60). Each line runs past the top of its
  y range at one end, and is drawn to the frame on purpose (see "Differs" 9). And
  `FONT_SUBSTITUTED` (Arial is not installed here; Liberation Sans has Arial's metrics).
* `fig1_improved.py`: `inklet lint: 1 info`: `FONT_SUBSTITUTED` only.

## Pass 2: print size, frame and style

* **Print width, measured.** The original PNG is 1404 px wide. The tick digit
  "1" (in "0.1", panel a, and in "1.0", panel e) is 14.5 px tall, which is the
  cap height (cap_px = 14.5). A 7 pt Arial cap is 1.77 mm, so the printed width
  is 1404 × 1.77 / 14.5 ≈ 171 mm. That snaps to 183 mm (136 mm is 35 mm away).
  Cross-check: the original's histogram x axis is 243 px, which is 31.7 mm at
  183 mm (`HIST_W` is 31 mm). At 89 mm it would be 15.7 mm. Both figures are 183 mm.
* **Height.** The original is 1211 px tall, which is 157.8 mm at 183 mm wide.
  This figure does not draw the anatomy row (c and d, about 35 mm of the
  original), so it keeps the height of its own rows rather than stretching the
  gaps to fill a row it does not have: 142.2 mm faithful, 147.2 mm improved. The
  plot sizes match the original (histograms 25 mm tall against 24.8 mm measured,
  sampling panels 26 mm, scatters 21 mm against 21 mm measured).
* **Frame.** Open left and bottom axes, as the original. `axes="open"` (the default).
* **Ink.** The original's axes, numbers and reference lines are pure black
  (0, 0, 0). The `scientific.nature` ink is #1a1a1a, so the faithful figure sets
  `ink="#000000"`. The improved figure keeps the journal ink.
* **Italics.** Variables are italic: r in the axis labels and the legend values
  ("//r// = 0.50"), and n in "//n// = 25". Units, numbers and labels stay upright.
  Legend values drop the plus sign, as the original does ("r = 0.50", not
  "r = +0.50"). The improved figure keeps "+" in its line labels, as asked.
* **CI dashes.** Sampled from the original's dashed lines (plateau values):
  99% CI #646464 (dark grey, unchanged); 95% CI #c8c8c8 (was #afafaf). The
  full-sample fit is black, as in the original.
* **Histograms.** Drawn with `Panel.hist(..., prebinned=True)` instead of a
  hand-built step fill. Same bars and heights.
* **Letters.** Kept as one `sub.letters(start=...)` per row. `doc.letters({...})`
  by cell name needs the pair cells at top level, and then each row's two pairs
  lose the shared plot margins (`share_plot_margins=True`). It is not simpler here.
* **Acknowledged warning.** `report(expect={"SERIES_FLATTENED"})` for the flat
  mean lines in e and f.
* **Duplicate legend names.** Still needed. `legend(names=)` rejects a repeated
  name, so the light subsample keeps its trailing zero-width space. See
  `ISSUES-marek_bwas_2022.md`, "Pass 2".
* **Improved layout.** The footnote is removed (it is now the caption below). Row
  gap is 4 mm (was 6), panels are 27 mm tall, and the sampling key stays inside
  the top-left of panel e. A `side="top"` key on one panel pushed that plot out of
  line with its neighbours, and a 26 mm panel gave a `CROWDING` info, so 27 mm stays.

## Panels left out

* **c and d** (brain surfaces): their inputs (per-ROI/network |r| on an atlas) are
  not in the atlas-free source data. Their row is removed, so the faithful figure
  has rows a/b, e/f, g/h. The panel letters a, b, e–h are kept as in the original.
* **h, right** (RSFC vs psychopathology scatter): sheet `H_right` contains only its
  header row (checked in normal mode and in the sheet XML). In the faithful figure,
  h-left keeps the size of the g scatters and sits in its original left slot of the
  RSFC column, and the right slot is empty. In the improved figure, panel h is one
  plot in a row of three.
* The caption's panel letters for the scatters read "f, g" then "g", then "h":
  the caption means g and h, and the text says "Fig. 1g, h". We follow the figure.

## Matches the original

* **Layout.** Two columns headed "Structure: Cortical thickness" and "Function:
  RSFC". Row labels "Effect size" and "Sampling variability across studies". Each
  letter covers a pair of plots, cognitive ability (left) and psychopathology
  (right). Titles match the original's.
* **Data.** Every plotted value is read from the Source Data workbook; nothing is
  digitised or invented (see SOURCE.md).
* **Axis ranges and ticks.** Histograms −0.2 to 0.2 (ticks −0.2, −0.1, 0, 0.1, 0.2)
  with no y tick labels; sampling panels −1 to 1 on y; scatters 3–3.5 mm and
  0.15–0.5 on x; cognitive 70–150 and psychopathology 20–70 on y.
* **Colours.** Sampled from the original image: Greens #c7e9c0 / #74c476 /
  #238b45 (vertex/ROI/network, edge/component/network) and Purples #dadaeb /
  #9e9ac8 / #6a51a3. Band tint #c7e9c0 (cognition) and #cbc9e2 (psychopathology).
  99% CI dashed #646464, 95% CI dashed #c8c8c8 (sampled in pass 2). The full-sample dashed fit is black.
* **Keys.** Same text as the original: "Vertex / ROI / Network", "Edge /
  Component / Network", "99% CI", "95% CI", "//n// = 25", and "//r// = 0.50 ..." on the
  fit lines (no plus sign, as the original).
* **Subsample colours.** Dark = the subsample whose legend r is positive. For g,
  that is `DMN_25_2`/`Cog_25_2` (data r = +0.501; the other subsample r = −0.639).
  For h, it is `DMN_25_1`/`Cog_25_1` (r = +0.584; other −0.600). The data match
  the legend values: g psychopathology r = +0.652 and −0.484 (legend +0.65,
  −0.48).
* **Full-sample fit.** Data r: −0.082 (g cognitive; legend −0.08), +0.054 (g
  psychopathology; legend +0.05), +0.050 (h cognitive; legend +0.05).

## Differs, and why

1. **Histogram bins.** The bins are not in the data. I used 0.01-wide bins from
   −0.2 to 0.2. Check against the original: the 13-value network series of
   cognitive thickness has bin counts of 2 at −0.07 and −0.05 (the tallest bins,
   full height) and 1 at −0.09 and −0.03 (half height), which is what the original
   shows. At 0.02 width the tallest bin holds 3 values, which gives a different
   pattern.
2. **Histogram heights.** The caption says "normalized to per panel maximum bin".
   The figure cannot be that: a 13-value series would be invisible beside a
   59,412-value series. Each series is scaled to its own tallest bin, so each
   reaches full height as in the original.
3. **Histogram bars.** Opaque, drawn in order vertex, ROI, network, so the darker
   network bars sit on top. The original's overlap looks translucent; this is a
   simplification. The y range is 0 to 2.3 (in units of the normalised height), so
   the key sits above the bars instead of on them (the original puts its key over
   the bars).
4. **Confidence bands for e and f.** The method is not stated. The dashed lines
   here are the 0.5/99.5 and 2.5/97.5 percentiles of the 1,000 resamples. The text
   gives "r ± 0.52" for the 99% CI at n = 25. From the data, the percentile
   half-width is ±0.48 (E cognitive thickness, mean −0.113, 0.5% −0.592, 99.5%
   +0.375) and 2.576 × SD = ±0.52. So the text matches a Gaussian (mean ± z·SD)
   and the figure looks closer to percentiles: the E psychopathology 99% limits
   read from the image are +0.54 and −0.40, against percentiles +0.54 and −0.42
   (Gaussian ±0.52 would give −0.45). The percentile version is used.
5. **Shading.** The min–max band is drawn as in the caption (min to max across
   the 1,000 resamples).
6. **Sample-size axis.** A true log axis from 25 to the last bin (3,604 for
   thickness, 3,928 for RSFC). Ticks at 25, 200 and 2,000. In the original the
   "200" label sits a little to the right of its log position (about 1.5 mm, read
   from the image); we use the log position.
7. **Scatter keys.** The original key is a two-row legend above each pair. Here
   each scatter has its own key above it with the same texts. The two subsample
   series both display "n = 25", but inklet requires distinct names, so the light
   series carries a trailing zero-width space in its name (not visible).
8. **Full-sample points.** The original does not draw the 3,604 (or 3,928)
   full-sample points, only the fitted line; the legend's black "n = 3,604" square
   is the dashed line here ("r = −0.08"). Same drawing, different key entry.
9. **Scatter points** are 0.95 mm across, as in the original (about 7 px of a
   1404 px image printed at 183 mm). **Scatter ranges and cut markers.** The axis ranges are the original's:
   cognitive y 70–150, psychopathology y 20–75 (the original stops at 70, which
   would cut the point at 72; 75 keeps it), x 3–3.55 mm and 0.15–0.57. Points
   outside a range, or within a marker radius of an edge (where it would be cut),
   are not drawn. Their fits and r values use all 25 points, because the legend
   r values are fits to all 25. Markers not drawn, out of 25 per subsample:
   * g cognitive, dark (A subsample): 2 (DMN 3.000 and 3.140, both at cognition 67).
   * g cognitive, light (B subsample): 1 (3.473, 58).
   * h cognitive, light (B subsample): 2 (0.229, 152, above the top; 0.416, 65,
     below the bottom).
   * g psychopathology: none. Total 5 of 150 markers. The full-sample points were
     never drawn (see 8).
   Nothing is partially drawn: the crops at 3x show no fragments at any edge.
   Lint reports `DATA_CLIPPED` (info) for the two fit lines that leave the frame
   at one end. The markers are not in that count: the script drops every marker
   that is outside or within a radius of an edge before plotting, so lint never sees
   them. A marker only partly inside would be cut without any report
   (ISSUES-marek_bwas_2022.md item 10).
10. **Tick labels.** Correlation ticks read "1.0", "0.5", "0", "−0.5", "−1.0":
    no plus sign and zero as "0", as in the original. The histogram axes use
    the same zero rule.
11. **Style.** `scientific.nature` in inklet, sans-serif in Liberation Sans, no
    Arial (not installed).

## Improved version

The improved figure keeps the same data, uncertainty and message: effects are
tiny (|r| mostly below 0.05), and 25 people give intervals of ±0.5 (99%).

Changes and the problem each fixes:

* **Histograms are outlined steps of the share of associations** (percent per
  bin, each level's own total), one sequential blue for the three ordered levels,
  one y scale across the four panels. Fixes: the original's overlapping
  translucent fills in three shades of one hue (hard to separate, not
  colour-blind-safe); and per-series normalisation, which drew a 13-value network
  series at the same height as a 59,412-value vertex series, so the sample size was
  invisible. The n for each level is in the footnote.
* **Reference marks on each histogram.** A grey band at ±0.01 (median |r|) and
  dotted lines at ±0.06 (top 1% of associations). Fixes: the "effects are tiny"
  message was only in the caption.
* **Sampling variability as three nested neutral bands** (min–max, 99%, 95%)
  with the mean as one dark line; the mean is not colour-coded. Fixes: the 95% and
  99% limits were two similar dashed grey styles, hard to tell apart; and colour
  was doing two jobs (green/purple meant phenotype and also sat on the mean and the
  band).
* **Where the 95% interval reaches ±0.06.** A dotted vertical line at n = 1,000:
  the data give 95% limits of −0.167 to −0.048 (E cognitive thickness) and
  +0.105 to +0.225 (F cognitive RSFC), both ±0.06. Fixes: "intervals become
  narrow" had no marked sample size.
* **Log sample-size axis with three labelled ticks** (25, 100, 1,000) and minor
  ticks at the other log positions. Fixes: the original's uneven tick labels (25,
  200, 2,000) and the crowding of labels at small n.
* **Scatter samples in an Okabe–Ito blue and orange**, with a circle and a
  diamond, and each fit labelled at its line end: "A: r = +0.50", "B: r = −0.64".
  The full-sample fit is a dashed black line, named in the footnote. Fixes: the
  three-row keys above each pair (crowded, with two entries for one colour); and
  the dark/light shades that encoded both the sample and the sign of r. Text on
  orange uses a darker orange for contrast ≥ 4.5:1.
* **Four columns, labelled by what is compared** (thickness or RSFC, and
  cognition or psychopathology), replacing the structure/function headers and the
  rotated row labels. Panel letters a–k.
* **No footnote on the figure.** Pass 2 moved the footnote into the caption below:
  the reference marks, n per level, the full sample sizes, and the panels not
  drawn (c, d, and the empty h-right). A reader still finds which data are missing,
  without prose inside the plot.
* **Scatter row, three panels across** instead of a half-empty grid, because
  the psychopathology RSFC scatter has no data.

Lint for the improved version: one `FONT_SUBSTITUTED` only.

Points are 1.1 mm across with white edges, a little larger than the original's
0.9 mm so overlapping points stay separate. Scatter ranges were widened so that
every marker is fully inside (margin 0.55 mm,
the marker radius). The ranges are x 2.95–3.6 mm (g) and 0.12–0.62 (h), cognitive
y 50–160 with ticks 70, 110, 150, and psychopathology y 18–78 with ticks 20, 70.
The script counts markers outside the margin for each sample; the count is 0 for
all six. Zero reads "0" on the histogram x-axes and the level y-ticks, and the
±0.5 ticks are signed.

## Verification numbers

Checked against the data and the paper's text.

| Quantity | Figure / data | Paper | Note |
|---|---|---|---|
| Median \|r\|, vertex cognition | 0.0167 | "median 0.01" across ~11 million associations | Same order; the 11 million are not in this workbook. Vertex psychopathology 0.0124; edge cognition 0.022; edge psychopathology 0.013. |
| 99th percentile \|r\|, vertex cognition | 0.066 | "top 1% > 0.06" | Consistent. Vertex psychopathology 0.047 and edge psychopathology 0.052 are below 0.06; edge cognition 0.092 is above. |
| 99% CI at n = 25 | ±0.48 (percentile) or ±0.52 (2.576 × SD), E cognitive thickness | "r ± 0.52" | The text matches the Gaussian form; see Differs 4. |
| 95% CI at n = 1,000 | ±0.060 (E cognitive) and ±0.060 (F cognitive) | not stated | Used to place the dotted line in the improved figure. |
| Mean across resamples | ≈ −0.11 (thickness cognition, all n); ≈ +0.165 (RSFC cognition) | not stated | Flat across n, as drawn. |
| Full-sample r (g, h) | −0.082, +0.054, +0.050 | −0.08, +0.05, +0.05 (legends) | Match. |
| Subsample r (g, h) | +0.501 / −0.639; +0.652 / −0.484; +0.584 / −0.600 | +0.50 / −0.64; +0.65 / −0.48; +0.58 / −0.60 | Match. |

## Not verified

* The paper's "largest replicated |r| = 0.16", "11 million associations" and the
  split-half n = 1,964 figure: not in the source workbook.
* Exact placement of the original's tick labels (estimated by eye from the PNG).
* The CI method for the dashed lines (percentile vs Gaussian) is a judgement; see
  Differs 4.

## Suggested caption

For `fig1_improved.py`. The footnote that was on the figure is in this legend.

**Fig. 1 | Brain-wide associations are small, and a study of 25 people can
report almost any of them.** **a–d**, Share of associations in each 0.02-wide bin
of correlation r, for the three levels of each measure: thickness vertex (59,412
associations), ROI (333) and network (13); RSFC edge (77,421), component (100) and
network (105). The grey band marks median |r| = 0.01 across associations; the
dotted lines mark |r| = 0.06, the top 1% of all associations. **e–h**, Mean of r
across 1,000 resamples at each sample size (25 to 2,800), with min–max, 99% and
95% ranges. Sample sizes are full-sample values: n = 3,604 (thickness) and 3,928
(RSFC). Dotted lines at ±0.06 and the vertical line at n = 1,000 mark where the
95% range reaches ±0.06. **i–k**, Two independent subsamples of n = 25 (A, blue;
B, orange) from the ABCD Study, each with its least-squares fit (r labelled). The
dashed black line is the fit to the full sample. Every marker of both subsamples
is inside its axes. Brain surfaces (c and d of the original) are not shown, and
the psychopathology RSFC scatter is omitted because its source data are empty.

## Nature tick labels at 7 pt

The preset's tick labels went from 6 to 7 pt. In the improved figure the
histogram x axes show −0.2, 0 and +0.2 (the ±0.1 labels no longer fit in a
27 mm panel), and the sampling key in panel e is set at 6 pt so it clears the
y tick labels.
