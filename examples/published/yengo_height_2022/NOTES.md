# Notes: Yengo et al. (2022), Figures 1 and 2

## Outputs

Each script writes `.svg`, `.pdf` and `.png` (200 dpi) to `gallery/published/`.
Sizes are the page sizes (PNG pixels at 200 dpi).

| Script | Output | Page |
|---|---|---|
| `fig1.py` | `yengo_height_2022_fig1.{svg,pdf,png}` | 89.0 × 66.3 mm (single column) |
| `fig1_improved.py` | `yengo_height_2022_fig1_improved.{svg,pdf,png}` | 89.0 × 79.1 mm (single column) |
| `fig2.py` | `yengo_height_2022_fig2.{svg,pdf,png}` | 183.0 × 61.6 mm (double column) |
| `fig2_improved.py` | `yengo_height_2022_fig2_improved.{svg,pdf,png}` | 183.0 × 77.6 mm (double column) |

`data/fig1_source.csv` (437 KB) and `data/fig2_source.csv` (238 KB); both under
1 MB, so no `.gz`.

## Lint

- `fig1.py`: `inklet lint: 1 info`, which is FONT_SUBSTITUTED only.
- `fig1_improved.py`: `inklet lint: 1 info`, FONT_SUBSTITUTED only.
- `fig2.py`: `inklet lint: 1 info`, FONT_SUBSTITUTED only.
- `fig2_improved.py`: `inklet lint: 1 info`, FONT_SUBSTITUTED only.

FONT_SUBSTITUTED is now INFO, not a warning: the Nature preset expects Arial,
which is not installed in this sandbox. The text is set in Liberation Sans,
which is metric-compatible with Arial, so layout is the same as with Arial.
Nothing else is reported. (Pass 1 reported it as a warning, and the
`expected_fonts=None` workaround is gone.)

## Matches the original

Figure 1 (`fig1.py`):

- Single panel, linear MAF axis from 0 to 50%, ticks at 1, 5, 10, 20, 30, 40, 50
  (the original's ticks, on its linear scale). The original's y range −0.3 to
  0.3 with ticks at 0.1 steps, including the zero tick, labelled "0" as in the
  original. The default formatter would write "0.0" (ISSUES-yengo_height_2022.md #6),
  so `y_label()` writes zero as "0" and uses a true minus sign.
- All 12,111 SNPs; the five classes with the original's names, counts (672,
  1,110, 3,513, 5,192, 1,624) and key order, with the key in the upper right.
  The names are set in italic `//P//`, as in the original.
- Colours sampled from the original: P < 5 × 10⁻¹⁰⁰ #EE82EE, 5 × 10⁻⁵⁰–10⁻¹⁰⁰
  #2E8B57, 5 × 10⁻²⁰–10⁻⁵⁰ #1E90FF, 5 × 10⁻¹⁰–10⁻²⁰ #DAA520,
  5 × 10⁻⁸–10⁻¹⁰ #CDC673; power curves #BEBEBE (n = 0.5 M) and #FF7256 (n = 5 M).
- Both signs of the power curves, the grey zero line, and the two power-curve
  entries at the lower right, with the original's labels ("90% power (//n// =
  0.5 million)", "90% power (//n// = 5 million)"), each with a line swatch in
  its curve's colour. They are drawn as swatches and text, not as a second key,
  because a panel carries one key (see Pass 2).
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
- **Proportions.** 89 × 66.3 mm, against 89 × 65.4 mm for the original's own
  aspect (Pass 2 measurement). The data area is 72 × 50 mm, which is the
  original's plot proportion at this width.
- **Axis start.** The original's x axis line starts at 1% and its y axis sits
  just left of 0%; ours starts at 0%. The leftmost points (MAF 0.16%) are inside
  the plot in both.
- **Marker size.** 1.1 mm diameter, estimated from the original at 300 dpi
  (dots about 14 px across at 1060 px width). Not measured exactly.
- **Power key.** A panel carries one key, and a second `legend()` call replaces
  the first (ISSUES-yengo_height_2022.md #7). The power-curve entries are
  therefore swatches and text, not a second key (see Pass 2).

Figure 2 (`fig2.py`):

- **Gene labels** (SPSB1, LINC00211, ACAN, …) are omitted. They are not in the
  Source Data files.
- **Ancestry marker heights.** The source gives each flagged SNP's density and
  flags, not the height of its marker. Each marker stands on its column's top
  square. The original places them at other heights in some columns.
- **Chromosome gaps.** None, as in the original.
- **Square size.** 0.8 mm, estimated from the original.
- **Plot height.** 46 mm of data area, 61.6 mm in total. The original's aspect
  at 183 mm gives about 50 mm in total. Its tick labels are about 5.4 pt at this
  width (Pass 2 measurement), so 7 pt ticks every 2 units need more height than
  the original gives them. The height is kept above the original's for the ticks.
- **Key placement.** Mean and median lines in the upper left, and the ancestry
  key under them, also upper left. The original puts the ancestry key upper right,
  but the ACAN column (density 24) rises under its text there, so it is moved.
  Both keys are in empty space and cover no data. The y range starts at −0.6, not
  0, so the triangles on density-0 SNPs are not cut by the axis (MARKER_CUT).
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
3. **One key above the plot, in two columns, with the SNP counts only.** Fixes
   the original's two keys inside the data area. The key covers no data, and the
   plot keeps its 89 mm width. The counts are in parentheses, and "SNPs" is said
   once in the caption.
4. **Single-hue sequential palette for the five ordered P-value classes**, from
   mid blue (least significant, #4292c6) to navy (most significant, #08306b),
   sampled from inklet `ramp(["#4292c6", "#08306b"]).sample(5)`: #4292c6,
   #3678ae, #295f97, #1a4781, #08306b. Fixes the yellow, olive, gold and green
   categories of the original, which are not colour-blind-safe and carry no
   order. The ramp is single-hue, so it is safe for the common forms of colour
   blindness. The lightest step is 3.4:1 against white (the WCAG 3:1 threshold
   for graphical objects). A first version started at #9ecae1, about 1.9:1 with
   the markers at 60% opacity, which nearly disappeared on the white background;
   that is why the ramp now starts darker. cividis and viridis (both shipped by
   inklet) were considered and rejected: their light ends are yellow, which has
   the same problem on white.
5. **Power curves in Okabe-Ito orange (#E69F00, solid, n = 0.5 M) and vermilion
   (#D55E00, dashed, n = 5 M).** The original's grey and coral curves are close
   to the khaki and gold classes and to each other; the hue and dash both
   distinguish these curves from the blue ramp and from each other.
6. **Y label shortened to "Joint effect size of minor allele (s.d.)"**, the same
   quantity, with ticks at 0.1 steps and the zero line.
7. **Single-column width (89 mm), as the faithful version.** Pass 1 had 183 mm
   with a key on the right. The key now sits above the plot, which costs height,
   not width (79.1 mm in total). See Pass 2.

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

Pass 1:

- Figure 1 faithful: 4 rounds (curve weight, key position, y ticks, the zero
  label "0" restored and formatted, curve key as a second legend call).
- Figure 1 improved: 4 rounds (marker size and opacity, curve weight, key
  outside the plot, lightest class of the ramp darkened for contrast).
- Figure 2 faithful: 4 rounds (key position, y range, label spacing, median
  label text and rotated tick labels).
- Figure 2 improved: 3 rounds (key moved above the plot, clipping off for markers
  at density 0, raster squares).

Pass 2 (see the section below): figure 1 faithful 4 rounds (the second key was
lost, the power key became swatches, the key row gap was tightened so it covers
no data, the axes went black); figure 2 faithful 3 rounds (the triangles on
density 0 were cut, the ancestry key crossed the ACAN column, the axes went
black); figure 1 improved 2 rounds (the key moved above the plot and was
shortened to two columns); figure 2 improved none (it was checked and left as
it was).

## Not verified

- Arial rendering (see Lint).
- The original's exact marker and line widths, which are estimated from the
  image, not from the source files.
- The original's ancestry marker heights (not in the data).

## Pass 2

### Print width, measured from the original

Measured in the original PNGs. The cap height is that of a flat-topped tick digit,
and a 7 pt Arial cap is 1.77 mm, so the width is W_px × 1.77 / cap_px mm.

- Figure 1: 1060 px wide. The tick digits "1" and "5" are 21 px tall (rows
  719 to 739), so 1060 × 1.77 / 21 = 89.3 mm. Snapped to **89 mm**, the
  single-column width. The original's height at that width is 779 / 1060 × 89 =
  65.4 mm.
- Figure 2: 2144 px wide. The y tick digits are 16 px tall, so 2144 × 1.77 / 16 =
  237 mm. Snapped to the nearest Nature width, **183 mm**. The original's height at
  183 mm is 585 / 2144 × 183 = 49.9 mm. At 183 mm its tick digits are 16 px of
  11.7 px/mm, about 1.37 mm, or 5.4 pt, not 7 pt, so the original's text is small
  against its plot. The faithful figure keeps 7 pt, as the rule says; this is the
  main remaining difference (see below).

### Lint

Every script: `inklet lint: 1 info`, FONT_SUBSTITUTED only, the Liberation Sans
note (see Lint above). No warnings, so no justifications are needed.

### What changed, and why

Figure 1 faithful (`fig1.py`):

- Width already 89 mm. Height 76.2 mm to 66.3 mm, the original's aspect.
- Italics: `//P//` in the five class names and `//n//` in both power-curve labels.
- Open axes kept, now black at 0.21 mm (the box frame's weight, which does not
  read as grey), with outward ticks as the original has them. The grey zero line
  and grey n = 0.5 M curve stay grey, because they are grey in the original.
- One key (the five classes, upper right) plus the two power curves as swatches
  and labels at the lower right. A second `legend()` call replaced the first, so
  the first pass's second key was silently lost (ISSUES-yengo_height_2022.md #7).
  The class key uses `row_gap=0.4` so that it stays above the two data markers
  at MAF 43% and 44%, which it otherwise covered.

Figure 2 faithful (`fig2.py`):

- Width 183 mm, as before. Height 56 to 46 mm of data area (61.6 mm in total).
- y range from −0.6 instead of 0. The triangles on density-0 SNPs were cut in
  half by the axis (`MARKER_CUT`); the lower bound lets them draw whole.
- The ancestry key moved from the upper right to under the mean and median key at
  the upper left. The ACAN column reaches density 24 under the upper-right text.
- Open axes now black, as in the original.
- No italics: the figure has no variables.

Figure 1 improved (`fig1_improved.py`):

- Width 183 mm to 89 mm, the same as the faithful version.
- The key moved from the right side (which needed the width) to above the plot, in
  two columns, with each class count in parentheses and the word "SNPs" moved to
  the caption.
- Italic `//P//` and `//n//` in the key.
- Open axes black, to match the faithful version.
- Palette, log MAF axis, marker size and opacity and the Okabe-Ito curves are
  unchanged.

Figure 2 improved (`fig2_improved.py`):

- Checked: 183 mm, `inklet lint: 1 info`, and the picture has no overlap or
  clipping. It contains no variables and no explanatory prose, so nothing else
  changed. Its axes are still the grey theme default; the spec asked for it to
  be kept as it was.

### Prose removed from the improved versions

None was found inside the improved figures. Their titles, footnotes and callouts
had already been removed in pass 1, and the only words moved out are the SNP
counts "SNPs", which now go in the caption.

### Remaining differences from the original's look

- Text size: at 183 mm the original's tick labels are about 5.4 pt. Ours are 7 pt
  to keep the rule, so figure 2 looks more spaced and its plot is shorter
  relative to the labels. Its height is 61.6 mm, against 49.9 mm for the original.
- Figure 2 has no gene labels and no ancestry marker heights (not in the source).
- Figure 1 improved is taller than the original (79.1 mm against 65.4 mm) because
  the key is above the plot.

## Suggested caption

**Figure 1 | Effect size against minor allele frequency for the genome-wide
significant height SNPs.** **a**, Joint effect size (s.d. of height per minor
allele) against minor allele frequency (MAF) for the 12,111 quasi-independent
genome-wide significant SNPs of the cross-ancestry meta-analysis, coloured by
P-value class; the number of SNPs in each class is given in parentheses. The
curves show the effect sizes detectable at P < 5 × 10^−8 with 90% power for sample
sizes of 0.5 million (orange) and 5 million (vermilion). Data from Source Data.

**Figure 2 | Genomic density of genome-wide significant height SNPs.** **a**,
Density of genome-wide significant, quasi-independent SNPs along the genome, by
chromosome (1 to 22, alternately shaded). Each SNP is a column of squares from 0
to its signal density, the number of other independent SNPs within 100 kb.
Columns of SNPs whose signal is contributed by African, East Asian or Hispanic
ancestry groups carry a marker at their top. The mean (solid red) and median
(dashed red) genome-wide densities are 2 and 1, with LOCO standard errors of 0.14
and 0. Data from Source Data.
