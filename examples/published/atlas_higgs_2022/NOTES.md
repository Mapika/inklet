# Notes: ATLAS Higgs couplings, Figure 5

## Outputs

| Script | Output (`gallery/published/`) | Size | Lint |
|---|---|---|---|
| `fig5.py` (faithful) | `atlas_higgs_2022_fig5.{svg,pdf,png}` (PNG at 200 dpi) | 89.0 × 93.6 mm (single column) | 5 infos: `FONT_SUBSTITUTED`, 4 `CROWDING` |
| `fig5_improved.py` (improved) | `atlas_higgs_2022_fig5_improved.{svg,pdf,png}` (PNG at 200 dpi) | 89.0 × 90.9 mm (single column) | 8 infos: `FONT_SUBSTITUTED`, 7 `CROWDING` |

No warnings. `fig5.py` is 143 lines, `fig5_improved.py` is 127 lines. `_data.py`
loads the two HEPData tables.

Lint, as printed by `figure.report()`:

* Both scripts: `FONT_SUBSTITUTED`, now INFO. Arial and Helvetica are not installed
  here, so the figures are set in Liberation Sans, which is metric-compatible with
  Arial. The layout is measured in that face. No `expected_fonts=` workaround is used.
* `fig5.py`, `CROWDING`: the labels b (0.57 mm from a mark), μ (0.21 mm), Z (0.60 mm)
  and W (0.53 mm). They sit against the W/Z/t cluster and the lowest μ point, as in the
  original, each on the clear side of its own point. The 1 mm clearance is not met.
* `fig5_improved.py`, `CROWDING`: the labels c (0.31 mm), t, Z, b, τ and μ (0.60 to
  0.64 mm) and W (0.76 mm). Each was checked at 4× zoom on the 200 dpi PNG: none touches
  a marker, a whisker or the SM line. At 89 mm the W/Z/t and τ/b pairs are a few
  tenths of a millimetre apart, and 1 mm clearance cannot be met for those labels at
  this width.

## Print width (measured)

* Original: 1024 × 1052 px. The tick digits of the lower panel (for example "1.4" and
  "0.8") are 21 px high, so cap_px = 21.
* Width = W_px × 1.77 / cap_px = 1024 × 1.77 / 21 = 86.3 mm. The nearest Nature width
  is 89 mm, so both figures are `format="single-column"`.
* Height at 89 mm: 89 × 1052 / 1024 = 91.4 mm. The faithful figure is 93.6 mm, 2.2 mm
  taller. The extra is the tick-label and axis-title band below the lower panel, set at
  7 pt with inklet's padding. The improved figure is 90.9 mm.

## Frame (measured)

The brief said the original is boxed. The pixels do not show that. I scanned the
1024-px original for full-length lines: each panel has a left spine and a bottom spine
only. There is no top edge and no right edge on either panel (the top-left and
top-right corners are open). Ticks point inward on the left and bottom. Log minor ticks
are on the left and bottom of the top panel and on the bottom of the lower one.

So the faithful figure uses the default open axes with inward ticks, not
`axes="box"`. `axes="box"` is used for the improved figure only, as the frame style
that suits physics. The faithful figure's axis ink is pure black (`ink="#000000"`),
not the profile's #1a1a1a.

## Matches the original

* Layout: two stacked panels on one mass axis. Top: log-log, κ_F m_F/vev (fermions) and
  √κ_V m_V/vev (bosons), 0.046 to 300 GeV, decades 10⁻⁴ to 10⁰. Bottom: κ_F or κ_V on
  a linear axis, 0.8 to 1.4. The panels are 75 mm wide, measured against the original's
  887 px plot width (77 mm at 89 mm print width).
* Bottom x ticks are powers of ten, 10⁻¹ to 10², as in the original. The default log
  label writes 0.1, 1, 10, 100 under four decades, so `format=power_label` is passed.
* Data: every value, mass and asymmetric error comes from the two HEPData tables.
  Nothing is recomputed. Check: the implied vev from κ·m/vev is 246.00 GeV for the
  fermions in both tables (for example τ: 0.92166 × 1.777 / 0.0066577 = 246.00).
* Series: circles (κ_c = κ_t) for six particles, and grey crosses (κ_c free) for the
  same six plus c. Colours are sampled from the original: μ #dd5212, τ #dd2d0a, b and t
  #cf7331, W and Z #006600, c #999999.
* SM line: red #f81c1c, 0.25 mm, y = m/vev over the top panel and y = 1 over the lower
  one. Drawn at vev = 246 GeV. (It was 0.35 mm before this pass; the original's line is
  thinner.)
* The c point: grey cross at 7.85 × 10⁻⁵ with its whisker up to 7.6 × 10⁻³. Its
  lower bound is zero, so `floor="none"` runs the whisker bare to the bottom of the
  top panel, as in the original, with no arrowhead. The grey arrow in the lower panel
  points down from the top edge to κ_c = 0.031.
* Key: top-left, with the original's three entries (κ_c = κ_t, κ_c free, SM
  prediction), now set in italic κ.
* Particle table: the original's shaded key is an inset in the top panel at the
  original's relative size, drawn in millimetres from the original's pixels (0.0869
  mm/px). Tile colours are the sampled ones.
* Axis labels: the top is two lines, `κ_F m_F/vev` over `or √κ_V m_V/vev`, with variables
  in italic. The lower is `κ_F or κ_V`. Particle names are italic.

## Differs, and why

* **Y-axis label.** The original is a stacked fraction. inklet's markup has no
  fraction, so each formula is one line of italic text, split over two lines.
* **Height.** 93.6 mm against 91.4 mm (see Print width).
* **Label positions.** Each name is beside its own point with a small offset. The
  original's exact offsets cannot be recovered from the picture.
* **Key.** The original's κ_c = κ_t key entry has its error bar. Here the marker alone.

## Pass 2 changes

Faithful (`fig5.py`):

1. Width kept at 89 mm (`single-column`), which the measurement confirms. Height
   101.9 → 93.6 mm, from `margin=0.5`, `row_gap=0.5` and the label padding on the lower x
   axis. The page margin was 4 mm, which had shrunk the plot to 68 mm; the plot is now
   75 mm.
2. Frame: open with inward ticks, as measured (see Frame). The previous version was
   also open, but the profile's #1a1a1a ink is now #000000.
3. Italic variables in the y labels, the key and the lower y label.
4. Lower x ticks as powers of ten (see Matches).
5. The c whisker uses `floor="none"` in place of a hand-computed whisker length.
6. SM line 0.35 → 0.25 mm.

Improved (`fig5_improved.py`):

1. Width 183 → 89 mm. The earlier 183 mm justification was the W/Z/t crowding. At 89 mm
   the W and Z points still overlap, exactly as in the original at the same width. That
   is the data, not a layout fault, so the width is set by the print size.
2. Frame: `axes="box"`, the journal frame for physics. The two panels meet on one edge
   (`row_gap=0`), so the κ_c whisker runs through the boundary as in the original.
3. Prose removed. The callout "κ_c = 0.03, off this scale" is now "0.03" beside the
   arrow. The key entries are "Fermions", "W, Z bosons", "κ_c = κ_t", "κ_c free" and
   "SM prediction", with no "(filled)" or "(open)". The explanation of the offsets,
   the families and the arrow moved to the caption below.
4. The key is compact (7 pt, five rows) in the top-left, above the data: clear of the SM
   line, the τ and b points, and the c whisker top at 7.6 × 10⁻³.
5. Labels: italic particle names. W sits below the W/Z pair, clear of the SM line and
   the W diamond. The first attempt sat on the SM line, and was moved.
6. Lower x axis: powers of ten, and a 0.9 mm label gap so the axis title does not
   touch the tick labels.
7. The κ_c whisker uses `floor="none"`, as in the faithful version.
8. Kept: Okabe-Ito colours (fermions blue, bosons orange), filled circles for
   κ_c = κ_t and open diamonds for κ_c free, the ±9% mass offset, dashed SM line, 7 pt
   text, every asymmetric error bar, the c whisker and the arrow.

## Suggested caption

**a**, Reduced couplings κ_F m_F/vev of the fermions (blue) and √κ_V m_V/vev of the W
and Z bosons (orange) against particle mass, on log axes. Filled circles, κ_c = κ_t;
open diamonds, κ_c free. Error bars are the asymmetric uncertainties as published (HEPData
record ins2104706, tables 5 and 6). The dashed line is the Standard Model prediction,
m/vev with vev = 246 GeV. For legibility the κ_c = κ_t points are drawn 8% to the left
of their mass and the κ_c-free points 9% to the right; the values are not moved. The
κ_c-free point for c lies at 7.9 × 10⁻⁵ with an upper bound of 7.6 × 10⁻³; its lower
bound is zero, so its whisker runs to the bottom of the panel. **b**, The coupling
modifiers κ_F (fermions) and κ_V (bosons) against particle mass, with the same colours
and symbols. The dashed line marks κ = 1. The arrow marks κ_c, whose best fit is 0.03 and
which lies below this scale.

## Checks against the paper

* κ for the top quark, κ_c = κ_t: 0.948 (+0.069, −0.065); the top-panel value
  0.652 = 0.948 × 169.2/246.
* κ_μ (κ_c = κ_t): 1.070 (+0.249, −0.307), the largest relative uncertainty.
* κ_W, κ_Z: 1.021 and 0.990 (κ_c = κ_t).
* κ_c (free): best fit 0.031, interval 0 to 3.06. The arrow marks this.
* p-values: 56% (κ_c = κ_t) and 65% (κ_c free) are in the paper's caption, not plotted.
