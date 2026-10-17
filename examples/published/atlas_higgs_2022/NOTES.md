# Notes: ATLAS Higgs couplings, Figure 5

## Outputs

| Script | Output (`gallery/published/`) | Size | Lint |
|---|---|---|---|
| `fig5.py` (faithful) | `atlas_higgs_2022_fig5.{svg,pdf,png}` (PNG at 200 dpi) | 89 × 101.9 mm (single column) | 1 warning, 5 infos (see below) |
| `fig5_improved.py` (improved) | `atlas_higgs_2022_fig5_improved.{svg,pdf,png}` (PNG at 200 dpi) | 183 × 110.4 mm (double column) | 1 warning, 7 infos (see below) |

`fig5.py` is 139 lines, `fig5_improved.py` is 125 lines. `_data.py` loads the two HEPData tables.

Lint results, as printed by `figure.report()`:

* Both scripts: `FONT_SUBSTITUTED` (warning). The `scientific.nature` profile expects
  Arial or Helvetica; neither is installed here, so the figures are set in Liberation
  Sans. It is metric-compatible with Arial, so the measured layout is correct. The
  profile was not changed. The warning goes away on a machine with Arial.
* `fig5.py`, infos: `CROWDING` on the labels b, μ, Z and W (0.2 to 0.8 mm from a
  neighbouring mark). These labels sit against the dense W/Z/t cluster and the lowest
  μ point, as in the original, and each is on the clear side of its point. The
  lint's 1 mm clearance is not met. `INCONSISTENT_STROKE`: one element at 0.18 mm
  (inside the particle-table inset), whose source I did not identify. It was not set
  in the script.
* `fig5_improved.py`, infos: `CROWDING` on the labels c, t, Z, W, b, τ and μ, each
  0.3 to 0.6 mm from a neighbouring mark. The lint measures to the whisker caps as
  well as the marker bodies. I checked each label at full size (4× crops of the 200 dpi
  PNG, the W/Z pair, τ/b, μ, t and c): none touches a marker, a whisker or the SM line.
  The labels are on the sides listed below. The lint's 1 mm clearance cannot be met
  for labels this close to the W/Z/t and τ/b pairs at this width.

The remaining lint is the font warning, plus the crowding infos above. I did not hide
either with a different font or a different layout.

## Matches the original

* Layout: two stacked panels sharing the particle-mass axis. Top: log-log, κ_F m_F/vev
  (fermions) and √κ_V m_V/vev (bosons), 0.046 to 300 GeV, decades 10⁻⁴ to 10⁰. Bottom:
  κ_F or κ_V on a linear axis from 0.8 to 1.4, with ticks at 0.8, 1.0, 1.2 and 1.4.
  Both use the same mass axis, and the x-axis label is "Particle mass (GeV)".
* Data: every value, mass and asymmetric error is read from the two HEPData tables.
  Nothing is recomputed. Checks: the implied vev from κ·m/vev is 246.00 GeV for the
  fermions in both tables (for example τ: 0.92166 × 1.777 / 0.0066577 = 246.00).
* Series: the circles (κ_c = κ_t) for six particles, and the grey crosses (κ_c free)
  for the same six plus c. The colours are sampled from the original image:
  μ #dd5212, τ #dd2d0a, b and t #cf7331, W and Z #006600, c #999999.
* The SM line, red #f81c1c, is y = m/vev over the full width of the top panel and y = 1
  over the bottom. It is drawn at vev = 246 GeV.
* The c point: the grey cross at 7.85 × 10⁻⁵ with its whisker to 7.6 × 10⁻³ in the top
  panel, and the grey arrow in the bottom panel, pointing down from the top edge to
  κ_c = 0.031, below the panel.
* Key: top-left, with the original's three entries (κ_c = κ_t, κ_c free, SM
  prediction).
* Particle table: the original's shaded key (leptons, quarks, force carriers, Higgs
  boson) is redrawn as an inset in the top panel, in the same position and at the
  original's relative size (36 × 23 mm). Tile colours are the sampled ones.
* Axis tick labels, minor ticks and whisker caps: as in the original.

## Differs, and why

* **Y-axis label.** The original uses a stacked fraction (m_F over vev). inklet has no
  fraction markup, so the label is one line of text, κ_{F}·m_{F}/vev or
  √κ_{V}·m_{V}/vev.
* **Whisker to 0.** On a log axis, κ_c's lower bound of 0 cannot be drawn. The
  whisker runs to the bottom edge of the top panel, as in the original, where it ends
  at the axis.
* **Figure height.** 101.9 mm, against about 91 mm from the original's 1024 × 1052 px
  aspect ratio. The extra height is the axis-title band below the lower panel.
* **Labels.** Each particle is named beside its own point with a small offset, not in
  the original's exact positions. The original's offsets are not recoverable from the
  picture, and this keeps each name on the clear side of its point.
* **Inset.** The particle table is drawn with inklet rectangles and text, so tile
  positions are placed in millimetres from the original's pixels (0.0869 mm/px). The
  text colour on the dark tiles is white or black, chosen for contrast.

## Improved version

Changes, each with the problem in the original it fixes:

1. **Double column (183 mm) instead of single column.** The original's W, Z and t
   points, at 80 to 170 GeV, sit within a few millimetres of each other on a 90 mm
   plot, and every label fights for space. The common Nature rule for this brief is
   89 or 183 mm, so the width is 183 mm. I also rendered a 136 mm (1.5-column) test
   at the same scale: at that width the W and Z markers overlap each other and the W
   label touches its marker, so the cluster is not readable. 183 mm is kept for that
   reason, not because 136 mm is unsuitable as a Nature width.
2. **Labels for each particle at its point, and no lepton/quark legend.** The original
   needs the eye to travel from a 17-tile particle table to each point. Here the name
   is beside the point, so the table is not needed. The label sides are: μ, τ, b and
   t above-left of the filled point; Z above-left of its pair; W below-left of its
   filled point; c to the left of its diamond. W is below-left rather than below-right
   because the W diamond sits to the right of its circle (change 6), and the label
   would touch it.
3. **Colour key for the two families.** The original shows leptons and quarks as
   separate colours with a 17-tile table, and no key for the W/Z colour. The improved
   key has two coloured entries, "Fermions" (blue, the κ_F·m_F/vev points: μ, τ, b, t,
   c) and "W, Z bosons" (orange, the √κ_V·m_V/vev points). The bottom panel uses the
   same colours, and the key applies to both.
4. **Two scenarios differ by shape as well as colour.** The original shows κ_c = κ_t as
   filled circles and κ_c free as grey crosses, and the grey is close to the colour of
   the background. The improved figure uses filled circles for κ_c = κ_t and open,
   paper-filled black diamonds for κ_c free. The two are told apart by fill and outline,
   not by colour. The diamonds are 1.3 mm and the circles 1.4 mm across (the diamond is
   no larger than the circle), so neither reads as the heavier mark.
5. **Colour-blind-safe palette.** The original's red, orange, tan and green are hard to
   tell apart for the most common forms of colour blindness, and red and green in
   particular overlap. The improved figure uses two Okabe-Ito colours: blue for the
   fermions and orange for the vector bosons.
6. **Dodging of the two scenarios.** The κ_c = κ_t points sit at mass ÷ 1.09 (−8.3%)
   and the κ_c-free points at mass × 1.09 (+9.0%), the same on both panels. In the
   original the two scenarios sit at the same x, and their markers overprint: in the
   bottom panel κ_c = κ_t and κ_c free differ by only 0.006 to 0.014 for b, τ and t.
   With the ±9% offset each particle's two markers no longer touch. The values are not
   moved, and the offset is stated here and in SOURCE.md.
   The W/Z pair is still close: W (free, 87.6 GeV) and Z (κ_c = κ_t, 83.7 GeV) are only
   0.02 decades apart, so their markers touch. That is the data (80.4 and 91.2 GeV), not
   the offset, and no uniform offset separates it without moving the points by more.
   The W and Z filled circles are separated from each other by a small gap.
7. **SM reference line distinct from the data.** The original's SM line is solid red,
   the same colour as the τ point, and it runs through the data. The improved line is a
   dark grey dashed line, labelled "SM prediction" in the key and "SM" on the bottom
   panel, so it cannot be taken for data.
8. **The off-scale arrow is labelled.** The original's grey arrow has no text; a reader
   must infer that κ_c = 0.03. The improved arrow has the label "κ_c = 0.03, off this
   scale" beside it.
9. **Larger type.** The original's tick labels and key text are small for the panels
   they sit in. The improved figure sets all text at 7 pt, the profile's maximum, with
   the same font family as the faithful figure.
10. **Top y range.** The original's top panel extends to 3 (a blank band above the
    top point). The improved range ends at 1.6, which gives the data more height.
11. **Fewer elements.** The particle table, the tile colours and the lepton/quark
    grouping are gone. The figure carries the same data with less to read.

Kept from the original, as required: every asymmetric error bar on both panels, the
c whisker, and the off-scale arrow for κ_c.

## Verdict

The faithful version matches the original's panels, scales, series, key and particle
table, and uses the same data. Its main differences are the single-line y label and
the taller page; see "Differs". The improved version keeps every uncertainty and the
same message. Every point's κ is consistent with 1 within its own uncertainty, in both
scenarios, which is the figure's point. Values are as published in the HEPData tables.

## Checks against the paper

* κ for the top quark, κ_c = κ_t: 0.948 (+0.069, −0.065); the top-panel value
  0.652 = 0.948 × 169.2/246.
* κ_μ (κ_c = κ_t): 1.070 (+0.249, −0.307), the largest relative uncertainty.
* κ_W, κ_Z: 1.021 and 0.990 (κ_c = κ_t).
* κ_c (free): best fit 0.031, interval 0 to 3.06. The arrow marks this.
* p-values: 56% (κ_c = κ_t) and 65% (κ_c free) are in the caption text only; they are
  not plotted.
