# Notes: Yengo et al. (2022), Figures 1 and 2

## Outputs

Each script writes `.svg`, `.pdf` and `.png` (200 dpi) to `gallery/published/`.
Sizes are the page sizes (PNG pixels at 200 dpi).

| Script | Output | Page |
|---|---|---|
| `fig1.py` | `yengo_height_2022_fig1.{svg,pdf,png}` | 89.0 × 76.2 mm (single column) |
| `fig1_improved.py` | `yengo_height_2022_fig1_improved.{svg,pdf,png}` | 183.0 × 94.2 mm (double column) |
| `fig2.py` | `yengo_height_2022_fig2.{svg,pdf,png}` | 183.0 × 71.6 mm (double column) |
| `fig2_improved.py` | `yengo_height_2022_fig2_improved.{svg,pdf,png}` | 183.0 × 77.6 mm (double column) |

`data/fig1_source.csv` (437 KB) and `data/fig2_source.csv` (238 KB); both under
1 MB, so no `.gz`.

## Lint

- `fig1.py`: `inklet lint: 1 warning`, which is FONT_SUBSTITUTED only.
- `fig1_improved.py`: `inklet lint: 1 warning`, FONT_SUBSTITUTED only.
- `fig2.py`: `inklet lint: 1 warning`, FONT_SUBSTITUTED only.
- `fig2_improved.py`: `inklet lint: 1 warning`, FONT_SUBSTITUTED only.

FONT_SUBSTITUTED: the Nature preset expects Arial, which is not installed in
this sandbox. The text is set in Liberation Sans, which is metric-compatible
with Arial, so layout is the same as with Arial. Nothing else is reported.

## Matches the original

Figure 1 (`fig1.py`):

- Single panel, linear MAF axis from 0 to 50%, ticks at 1, 5, 10, 20, 30, 40, 50
  (the original's ticks, on its linear scale). The original's y range −0.3 to
  0.3 with ticks at 0.1 steps; the zero tick is unlabelled, as in the original.
- All 12,111 SNPs; the five classes with the original's names, counts (672,
  1,110, 3,513, 5,192, 1,624) and key order, with the key in the upper right.
- Colours sampled from the original: P < 5 × 10⁻¹⁰⁰ #EE82EE, 5 × 10⁻⁵⁰–10⁻¹⁰⁰
  #2E8B57, 5 × 10⁻²⁰–10⁻⁵⁰ #1E90FF, 5 × 10⁻¹⁰–10⁻²⁰ #DAA520,
  5 × 10⁻⁸–10⁻¹⁰ #CDC673; power curves #BEBEBE (n = 0.5 M) and #FF7256 (n = 5 M).
- Both signs of the power curves, the grey zero line, and the two power-curve
  entries in a second key at the lower right, with the original's labels
  ("90% power (n = 0.5 million)", "90% power (n = 5 million)").
- Curves drawn over the points, as in the original.

Figure 2 (`fig2.py`):

- Chromosomes 1 to 22 along the genome, in the original's spacing (GRCh37
  lengths), with odd chromosomes gold and even chromosomes black, as in the
  original. Colours sampled: gold #DAA520, black #000000.
- Density ticks every 2 from 0 to 30 (the axis runs to 32 so the key sits above
  the tallest column); "Density of GWS / SNPs within 100 kb"
  as the y label; "Chromosome" on x with rotated chromosome numbers.
- Red solid mean line at 2 and red dashed median line at 1, with the original's
  key text: "Mean genome-wide density: 2 (LOCO-S.E. = 0.14)" and "Median
  genome-wide density: 1 (LOCO-S.E. = 0)".
- Ancestry markers in the original's colours and shapes: African blue square
  (#1E90FF), East Asian pink circle (#EE82EE), Hispanic green triangle (#43CD80),
  with the key "Associations contributed by" in the upper right.
- Column of squares from 0 up to each SNP's density, with the maximum at 24 on
  chromosome 15 (ACAN in the original), so the top of that column is at 24 as in
  the original.

## Differs, and why

Figure 1 (`fig1.py`):

- **Font.** Liberation Sans, not Arial (see Lint).
- **Proportions.** 89 × 76 mm. The original is about 1.36 : 1 (width to height),
  ours 1.17 : 1, because the two-line y label and the key take more height at
  this size. The data area is 72 × 60 mm.
- **Axis start.** The original's x axis line starts at 1% and its y axis sits
  just left of 0%; ours starts at 0%. The leftmost points (MAF 0.16%) are inside
  the plot in both.
- **Marker size.** 1.1 mm diameter, estimated from the original at 300 dpi
  (dots about 14 px across at 1060 px width). Not measured exactly.
- **Power key.** Its two entries are a second `legend()` call, which draws a
  second key (see ISSUES-yengo_height_2022.md #2).

Figure 2 (`fig2.py`):

- **Gene labels** (SPSB1, LINC00211, ACAN, …) are omitted. They are not in the
  Source Data files.
- **Ancestry marker heights.** The source gives each flagged SNP's density and
  flags, not the height of its marker. Each marker stands on its column's top
  square. The original places them at other heights in some columns.
- **Chromosome gaps.** None, as in the original.
- **Square size.** 0.8 mm, estimated from the original.
- **Plot height.** 56 mm of data area, so the y ticks at 2 are legible at 6 pt;
  the original is more compressed vertically (its total height is 71.6 mm here,
  against about 50 mm for the original's aspect at 183 mm width).
- **Key placement.** Mean and median lines in the upper left, the ancestry key
  in the upper right above the tallest column (ACAN, density 24). Both are inside
  the data area but in empty space, so they cover no data.
- **Squares in the SVG are rasterised** (`raster=True`), to keep the SVG at
  183 KB rather than 10.8 MB. The PNG and PDF look the same (see
  ISSUES-yengo_height_2022.md #4).

## Improved version

### Figure 1 (`fig1_improved.py`)

Each change, with the problem it fixes in the original:

1. **Log MAF axis, 0.1 to 50%, with 1-2-5 ticks** (0.1, 0.2, 0.5, 1, 2, 5, 10,
   20, 50). Fixes the awkward frequency axis: the original is linear with uneven
   ticks (1, 5, 10, 20, …), which compresses the low frequencies where most
   SNPs and the power curves are steep. In the original, 1,170 of 12,111 SNPs
   lie below 5% MAF, all squeezed into the left tenth of the axis.
2. **Smaller, semi-transparent markers (0.7 mm, 60% opacity) and the most
   significant class drawn last.** Fixes heavy overplotting at low allele
   frequency: in the original, 1.1 mm opaque dots stack into a solid band, and
   the draw order hides classes under one another. Drawing the most significant
   class last puts the rare, strongest signals on top.
3. **One key outside the data area, on the right.** Fixes the original's key
   sitting inside the plot over the data at the top right, and the second key at
   the bottom right. The five classes and the two curves are in one ordered key.
4. **Single-hue sequential palette for the five ordered P-value classes**, from
   light (least significant, #9ecae1) to dark (most significant, #08306b). Fixes
   the yellow, olive, gold and green categories of the original, which are not
   colour-blind-safe and carry no order. The ramp is single-hue, so it is safe
   for the common forms of colour blindness.
5. **Power curves in Okabe-Ito orange (#E69F00, solid, n = 0.5 M) and vermilion
   (#D55E00, dashed, n = 5 M).** The original's grey and coral curves are close
   to the khaki and gold classes and to each other; the hue and dash both
   distinguish these curves from the blue ramp and from each other.
6. **Y label shortened to "Joint effect size of minor allele (s.d.)"**, the same
   quantity, with ticks at 0.1 steps and the zero line.
7. **Double-column width (183 mm).** The wider plot gives the log axis room, and
   leaves space for the key outside the data area.

Keep-every-uncertainty: Figure 1 has no error bars in the original; the power
curves are the only uncertainty-like element and both are kept in full. Nothing
is dropped.

### Figure 2 (`fig2_improved.py`)

1. **Chromosomes separated by 12 Mb gaps and shaded in alternate light bands.**
   The original has no gaps and alternates gold and black squares, so the
   boundaries of short chromosomes (21 and 22 in particular) are hard to see.
2. **One ink colour (#2F4B7C) for all squares.** The original's gold and black
   alternation is a chromosome code only; the bands now carry that role.
3. **Okabe-Ito markers for the ancestry groups** (vermilion diamond for African,
   reddish purple circle for East Asian, bluish green triangle for Hispanic),
   larger and with a white edge. Fixes small markers that are hard to see
   against the baseline in the original.
4. **One key for all five entries, above the plot.** Fixes the two separate keys
   inside the data area in the original.
5. **Y ticks at 5, y range 0 to 32, markers not clipped.** Fixes the crowded
   ticks at 2 and the markers at density 0 being cut in half by the axis.
6. **Squares rasterised in the SVG** (183 KB rather than 5.6 MB).

## Verification

Numbers checked against the paper and the Source Data:

- Figure 1 rows: 12,111, matching "12,111 quasi-independent GWS SNPs" in the
  caption. Class counts 672 + 1,110 + 3,513 + 5,192 + 1,624 = 12,111, matching the
  original's key.
- Largest effect +0.256 at MAF 1.94% (P < 5 × 10⁻¹⁰⁰); smallest −0.276 at MAF
  1.44%. Both are visible at those positions in the original (the top pink point
  near 2%, the bottom one near 1.4%).
- MAF range 0.165% to 49.99%; 80 SNPs below 1%, 299 below 2%, 1,170 below 5%.
- Power curves. The caption gives N = 0.5 million and 5 million, P < 5 × 10⁻⁸ and
  90% power. With the formula in SOURCE.md, the curves are at:

  | MAF | n = 0.5 M (formula) | n = 5 M (formula) |
  |---|---|---|
  | 0.1% | 0.213 | 0.067 |
  | 1% | 0.068 | 0.021 |
  | 5% | 0.031 | 0.010 |
  | 50% | 0.0135 | 0.0043 |

  The grey curve's top at 0.1% (0.213) matches the original's grey tip at
  about ±0.21, and the grey curve matches the original pixel by pixel at 2.2%
  (predicted ±0.046, measured +0.047/−0.046), 12.6% (predicted ±0.020, measured
  ±0.021) and 6.5% (predicted ±0.027, measured +0.029/−0.028). The pixel
  calibration is the x and y tick positions in the original PNG (16.7 px per
  percent; 1085 px per unit of effect). The coral curve's left end measures
  about ±0.06, against 0.067 to 0.075 predicted for MAF 0.08 to 0.1%. That end is
  steep and the pixel estimate less certain, so this is a looser check. The n =
  5 M curve is too close to the zero line to measure at most MAFs.
- Figure 2 totals: 12,111 SNPs; mean density 2.00 (caption: 2) and median 1
  (caption: 1), both from the file; maximum density 24 on chromosome 15
  (ACAN in the original's figure).
- Ancestry flags: the caption gives 3 African + 11 East Asian + 10 Hispanic =
  24, one flag per SNP. The file gives 3 + 12 + 10 = 25 flags on 24 SNPs: one SNP
  (chr 18, position 220071) carries both the East Asian and the Hispanic flag.
  The data are used as given; the East Asian count of 12 is the file's.

## Look-fix rounds

- Figure 1 faithful: 3 rounds (curve weight, key position, y ticks and
  zero label, curve key moved to a second key).
- Figure 1 improved: 3 rounds (marker size and opacity, curve weight, key
  outside the plot).
- Figure 2 faithful: 4 rounds (key position, y range, label spacing, median
  label text and rotated tick labels).
- Figure 2 improved: 3 rounds (key moved above the plot, clipping off for markers
  at density 0, raster squares).

## Not verified

- Arial rendering (see Lint).
- The original's exact marker and line widths, which are estimated from the
  image, not from the source files.
- The original's ancestry marker heights (not in the data).
